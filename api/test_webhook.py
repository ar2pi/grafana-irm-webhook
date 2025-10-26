#!/usr/bin/env python3
"""
Test script for Grafana IRM Webhook
Simulates Grafana IRM webhook payloads for testing
"""

import json
import time
from datetime import datetime

import requests

# Test configuration
WEBHOOK_URL = "http://localhost:5000/webhook/grafana-irm"
TEST_URL = "http://localhost:5000/webhook/test"
HEALTH_URL = "http://localhost:5000/health"


def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")


def test_webhook():
    """Test webhook endpoint"""
    print("Testing LED control endpoint...")
    try:
        response = requests.post(TEST_URL, timeout=10)
        if response.status_code == 200:
            print("✅ LED control test passed")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ LED control test failed: {response.status_code}")
            print(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ LED control test failed: {e}")


def test_grafana_alert(severity="warning", status="firing"):
    """Test with simulated Grafana IRM alert payload"""
    print(f"Testing Grafana IRM alert (severity: {severity}, status: {status})...")

    # Simulate Grafana IRM webhook payload
    payload = {
        "event_type": (
            "alert_group_created" if status == "firing" else "alert_group_resolved"
        ),
        "alert_group": {
            "id": "test-alert-001",
            "title": f"Test Alert - {severity.upper()}",
            "severity": severity,
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
            "resolved_at": (
                datetime.utcnow().isoformat() if status == "resolved" else None
            ),
        },
        "alert_payload": {
            "message": f"This is a test {severity} alert",
            "labels": {
                "severity": severity,
                "alertname": "TestAlert",
                "instance": "test-instance",
            },
            "annotations": {
                "summary": f"Test {severity} alert summary",
                "description": f"This is a test {severity} alert description",
            },
        },
    }

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 200:
            print(f"✅ Grafana IRM alert test passed ({severity})")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Grafana IRM alert test failed: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Grafana IRM alert test failed: {e}")


def main():
    """Run all tests"""
    print("🧪 Starting Grafana IRM LED Controller Tests")
    print("=" * 50)

    # Test health endpoint
    test_health()
    print()

    # Test webhook endpoint
    test_webhook()
    print()

    # Test different alert severities
    severities = ["critical", "high", "warning", "info", "low"]
    for severity in severities:
        test_grafana_alert(severity, "firing")
        time.sleep(1)  # Small delay between tests
        print()

    # Test alert resolution
    test_grafana_alert("warning", "resolved")
    print()

    print("🏁 Tests completed!")


if __name__ == "__main__":
    main()
