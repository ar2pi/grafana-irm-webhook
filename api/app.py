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
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Try to import GPIO libraries for Raspberry Pi support (Pi 5 uses gpiod)
try:
    import gpiod
    from gpiod.line import Direction, Value

    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    gpiod = None
    Direction = None
    Value = None

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
        self.gpio_pin = config.get("gpio_pin", 18)  # Default GPIO pin 18
        self.gpio_initialized = False
        self.gpio_request = None  # gpiod request object

        # Initialize GPIO if using Raspberry Pi
        if self.lightbulb_type == "raspberry_pi" and GPIO_AVAILABLE:
            self._init_gpio()

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
                    self.gpio_pin: gpiod.LineSettings(
                        direction=Direction.OUTPUT, output_value=Value.INACTIVE
                    )
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

            # For blinking patterns based on severity
            if state:
                self._blink_pattern(alert_data)

            logger.info(
                f"Raspberry Pi LED {'turned on' if state else 'turned off'} on pin {self.gpio_pin}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to control Raspberry Pi LED: {e}")
            return False

    def _blink_pattern(self, alert_data: Dict[str, Any]):
        """Create blinking pattern based on alert severity"""
        try:
            if self.gpio_request is None:
                logger.error("GPIO request not initialized for blink pattern")
                return

            severity = alert_data.get("alert_group", {}).get("severity", "warning")

            # Define blink patterns for different severities
            patterns = {
                "critical": (0.1, 0.1, 5),  # Fast blink: 100ms on, 100ms off, 5 times
                "high": (0.2, 0.2, 3),  # Medium blink: 200ms on, 200ms off, 3 times
                "warning": (0.5, 0.5, 2),  # Slow blink: 500ms on, 500ms off, 2 times
                "info": (1.0, 0.5, 1),  # Single long blink: 1s on, 0.5s off, 1 time
                "low": (0.3, 0.3, 1),  # Single short blink: 300ms on, 300ms off, 1 time
            }

            on_time, off_time, repeats = patterns.get(severity.lower(), (0.5, 0.5, 2))

            # Perform the blinking pattern
            for _ in range(repeats):
                self.gpio_request.set_value(self.gpio_pin, Value.ACTIVE)
                time.sleep(on_time)
                self.gpio_request.set_value(self.gpio_pin, Value.INACTIVE)
                if _ < repeats - 1:  # Don't sleep after the last blink
                    time.sleep(off_time)

            # Keep LED on after pattern
            self.gpio_request.set_value(self.gpio_pin, Value.ACTIVE)

        except Exception as e:
            logger.error(f"Error in blink pattern: {e}")

    def cleanup_gpio(self):
        """Clean up GPIO resources"""
        try:
            if self.gpio_request is not None:
                # Turn off LED before cleanup
                try:
                    self.gpio_request.set_value(self.gpio_pin, Value.INACTIVE)
                except Exception:
                    pass
                # Release the gpiod request
                try:
                    # The request object will be released when set to None
                    # gpiod automatically handles cleanup when the object is deleted
                    del self.gpio_request
                except Exception:
                    pass
                self.gpio_request = None
                self.gpio_initialized = False
                logger.info("GPIO cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up GPIO: {e}")


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables or config file"""
    config = {
        "lightbulb_type": os.getenv("LIGHTBULB_TYPE", "raspberry_pi"),
        "gpio_pin": int(os.getenv("GPIO_PIN", "18")),
        "webhook_secret": os.getenv("WEBHOOK_SECRET"),
        "port": int(os.getenv("PORT", 5000)),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
    }

    return config


# Load configuration
config = load_config()
lightbulb_controller = LightbulbController(config)

# Add cleanup handler for GPIO
import atexit

atexit.register(lightbulb_controller.cleanup_gpio)


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


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Grafana IRM Webhook Server on port {config['port']}")
    logger.info(f"Lightbulb type: {config['lightbulb_type']}")

    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=config["port"],
        reload=config["debug"],
        log_level="info",
    )
