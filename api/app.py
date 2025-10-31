#!/usr/bin/env python3
"""
Grafana IRM Webhook Server
Receives alerts from Grafana IRM and controls a smart lightbulb
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Try to import GPIO libraries for Raspberry Pi support (Pi 5 uses gpiod)
try:
    import gpiod
    from gpiod.line import Direction, Value

    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    gpiod = None  # type: ignore
    Direction = None  # type: ignore
    Value = None  # type: ignore

# Load environment variables from .env file
load_dotenv()

# Configure logging based on DEBUG environment variable
debug_mode = os.getenv("DEBUG", "false").lower() == "true"
log_level = logging.DEBUG if debug_mode else logging.INFO
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Grafana IRM Webhook Server",
    description="Receives alerts from Grafana IRM and controls a smart lightbulb",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Pydantic models for request/response validation
class AlertGroup(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    severity: Optional[str] = "warning"
    status: Optional[str] = "firing"
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None


class AlertPayload(BaseModel):
    message: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    annotations: Optional[Dict[str, str]] = None


class GrafanaWebhookPayload(BaseModel):
    event_type: Optional[str] = None
    alert_group: Optional[AlertGroup] = None
    alert_payload: Optional[AlertPayload] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    lightbulb_type: str


class WebhookResponse(BaseModel):
    status: str
    action: Optional[str] = None
    alert_title: Optional[str] = None
    message: Optional[str] = None
    timestamp: str


class LightbulbController:
    """Controller for smart lightbulb operations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lightbulb_type = config.get("lightbulb_type", "raspberry_pi")

        # Raspberry Pi GPIO configuration
        self.gpio_pin = config.get("gpio_pin")  # Default GPIO pin 18
        self.gpio_initialized = False
        self.gpio_request = None  # gpiod request object

        # Initialize GPIO if using Raspberry Pi
        #if self.lightbulb_type == "raspberry_pi" and GPIO_AVAILABLE:
        #    self._init_gpio()

    def turn_on(self, alert_data: Dict[str, Any]) -> bool:
        """Turn on the LED when an alert is received"""
        try:
            if self.lightbulb_type == "raspberry_pi":
                return self._control_raspberry_pi_light(True, alert_data)
            else:
                logger.error(f"Unsupported lightbulb type: {self.lightbulb_type}")
                return False
        except Exception as e:
            logger.error(f"Error turning on LED: {e}")
            return False

    def turn_off(self, alert_data: Dict[str, Any]) -> bool:
        """Turn off the LED when alert is resolved"""
        try:
            if self.lightbulb_type == "raspberry_pi":
                return self._control_raspberry_pi_light(False, alert_data)
            else:
                logger.error(f"Unsupported lightbulb type: {self.lightbulb_type}")
                return False
        except Exception as e:
            logger.error(f"Error turning off LED: {e}")
            return False

    def blink(self, alert_data: Dict[str, Any]) -> bool:
        """Blink the LED"""
        try:
            self.turn_on(alert_data)
            time.sleep(1)
            self.turn_off(alert_data)
            time.sleep(1)
            self.turn_on(alert_data)
            time.sleep(1)
            self.turn_off(alert_data)
            return True
        except Exception as e:
            logger.error(f"Error blinking LED: {e}")
            return False
        return True

    def get_status(self) -> str:
        """Get the current status of the LED (on/off) by reading the GPIO pin"""
        try:
            if self.lightbulb_type == "raspberry_pi":
                # If GPIO is initialized, read the actual value from hardware
                if self.gpio_initialized and self.gpio_request is not None and GPIO_AVAILABLE:
                    try:
                        # Read the current GPIO pin value from hardware
                        pin_value = self.gpio_request.get_value(self.gpio_pin)
                        return "on" if pin_value == Value.ACTIVE else "off"
                    except Exception as e:
                        logger.warning(f"Failed to read GPIO value: {e}")
                        return "error"
                else:
                    # GPIO not initialized yet, assume off
                    return "off"
            else:
                logger.error(f"Unsupported lightbulb type: {self.lightbulb_type}")
                return "unknown"
        except Exception as e:
            logger.error(f"Error getting LED status: {e}")
            return "error"

    def _init_gpio(self):
        """Initialize GPIO for Raspberry Pi using gpiod (Pi 5 compatible)"""
        try:
            if not GPIO_AVAILABLE:
                logger.error(
                    "gpiod library not available. Install with: pip install gpiod"
                )
                return False

            # Create gpiod request for the GPIO pin
            self.gpio_request = gpiod.request_lines(
                "/dev/gpiochip0",
                consumer="grafana-irm-webhook",
                config={
                    self.gpio_pin: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)
                },
            )
            self.gpio_initialized = True
            logger.info(f"GPIO initialized on pin {self.gpio_pin} using gpiod")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            self.gpio_initialized = False
            return False

    def _control_raspberry_pi_light(
        self, state: bool, alert_data: Dict[str, Any]
    ) -> bool:
        """Control Raspberry Pi GPIO LED using gpiod"""
        try:
            if not GPIO_AVAILABLE:
                logger.error("gpiod library not available")
                return False

            if not self.gpio_initialized:
                if not self._init_gpio():
                    return False

            if self.gpio_request is None:
                logger.error("GPIO request not initialized")
                return False

            # Control the LED
            value = Value.ACTIVE if state else Value.INACTIVE
            self.gpio_request.set_value(self.gpio_pin, value)

            logger.info(
                f"Raspberry Pi LED {'turned on' if state else 'turned off'} on pin {self.gpio_pin}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to control Raspberry Pi LED: {e}")
            return False

    def cleanup_gpio(self):
        """Clean up GPIO resources"""
        try:
            self._control_raspberry_pi_light(False, {})

            # The request object will be released when set to None
            # gpiod automatically handles cleanup when the object is deleted
            if self.gpio_request is not None:
                del self.gpio_request

            self.gpio_request = None
            self.gpio_initialized = False

            logger.info("GPIO cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up GPIO: {e}")


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables or config file"""

    logger.info(f"DEBUG: {debug_mode}")
    logger.info(f"LOG_LEVEL: {log_level}")
    logger.info(f"LIGHTBULB_TYPE: {os.getenv('LIGHTBULB_TYPE')}")
    logger.info(f"GPIO_PIN: {os.getenv('GPIO_PIN')}")
    logger.info(f"WEBHOOK_SECRET: {os.getenv('WEBHOOK_SECRET')}")
    logger.info(f"PORT: {os.getenv('PORT')}")

    config = {
        "lightbulb_type": os.getenv("LIGHTBULB_TYPE", "raspberry_pi"),
        "gpio_pin": int(os.getenv("GPIO_PIN", "17")),
        "webhook_secret": os.getenv("WEBHOOK_SECRET"),
        "port": int(os.getenv("PORT", 5000)),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
    }

    return config


# Load configuration
config = load_config()
lightbulb_controller = LightbulbController(config)

if __name__ == "__main__":
    logger.info(f"Starting Grafana IRM Webhook Server on port {config['port']}")
    logger.info(f"Lightbulb type: {config['lightbulb_type']}")

    try:
        uvicorn.run(
            "api.app:app",
            host="0.0.0.0",
            port=config["port"],
            reload=config["debug"],
            log_level="info",
        )

    except KeyboardInterrupt:
        pass

    finally:
        lightbulb_controller.cleanup_gpio()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        lightbulb_type=config["lightbulb_type"],
    )


@app.post("/webhook/grafana-irm", response_model=WebhookResponse)
async def grafana_irm_webhook(payload: GrafanaWebhookPayload):
    """Main webhook endpoint for Grafana IRM alerts"""
    try:
        logger.info(
            f"Received Grafana IRM webhook: {payload.model_dump_json(indent=2)}"
        )

        # Extract alert information
        alert_group = payload.alert_group or AlertGroup()
        alert_payload = payload.alert_payload or AlertPayload()

        # Determine if this is an alert creation or resolution
        event_type = payload.event_type or ""
        is_resolved = (
            event_type == "alert_group_resolved" or alert_group.status == "resolved"
        )

        # Prepare alert data for lightbulb control
        alert_data = {
            "alert_group": alert_group.model_dump(),
            "alert_payload": alert_payload.model_dump(),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Control the lightbulb
        if is_resolved:
            success = lightbulb_controller.turn_off(alert_data)
            action = "turned off"
        else:
            success = lightbulb_controller.turn_on(alert_data)
            action = "turned on"

        if success:
            logger.info(
                f"Lightbulb {action} successfully for alert: {alert_group.title or 'Unknown'}"
            )
            return WebhookResponse(
                status="success",
                action=action,
                alert_title=alert_group.title or "Unknown",
                timestamp=datetime.utcnow().isoformat(),
            )
        else:
            logger.error(
                f"Failed to {action} lightbulb for alert: {alert_group.title or 'Unknown'}"
            )
            raise HTTPException(status_code=500, detail=f"Failed to {action} lightbulb")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/test", response_model=WebhookResponse)
async def test_webhook():
    """Test endpoint to verify lightbulb control"""
    try:
        test_alert_data = {
            "alert_group": {
                "title": "Test Alert",
                "severity": "warning",
                "status": "firing",
            },
            "alert_payload": {"message": "This is a test alert"},
            "event_type": "alert_group_created",
            "timestamp": datetime.utcnow().isoformat(),
        }

        success = lightbulb_controller.turn_on(test_alert_data)

        if success:
            return WebhookResponse(
                status="success",
                message="Test lightbulb control successful",
                timestamp=datetime.utcnow().isoformat(),
            )
        else:
            raise HTTPException(status_code=500, detail="Test lightbulb control failed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in test webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/led/on")
async def led_on():
    """Endpoint to turn on the LED"""
    try:
        lightbulb_controller.turn_on({})
        logger.info(f"LED turned on")
        return JSONResponse(content={"message": "LED turned on"}, status_code=200)
    except Exception as e:
        logger.error(f"Error in turning led on: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/led/off")
async def led_off():
    """Endpoint to turn off the LED"""
    try:
        lightbulb_controller.turn_off({})
        logger.info(f"LED turned off")
        return JSONResponse(content={"message": "LED turned off"}, status_code=200)
    except Exception as e:
        logger.error(f"Error in turning led off: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/led/blink")
async def led_blink():
    """Endpoint to blink the LED"""
    try:
        lightbulb_controller.blink({})
        logger.info(f"LED blinked")
        return JSONResponse(content={"message": "LED blinked"}, status_code=200)
    except Exception as e:
        logger.error(f"Error in blinking led: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/led/status")
async def led_status():
    """Endpoint to get the status of the LED"""
    try:
        status = lightbulb_controller.get_status()
        logger.info(f"LED status: {status}")
        return JSONResponse(content={"message": "LED status", "status": status}, status_code=200)
    except Exception as e:
        logger.error(f"Error in getting led status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
