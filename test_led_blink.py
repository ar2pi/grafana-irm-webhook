#!/usr/bin/env python3
"""
Test LED blink on Raspberry Pi 5
"""

import time

import gpiod
from gpiod.line import Direction, Value

LINE = 17

with gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="blink-example",
    config={
        LINE: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)
    },
) as request:
    try:
        while True:
            request.set_value(LINE, Value.ACTIVE)
            time.sleep(1)
            request.set_value(LINE, Value.INACTIVE)
            time.sleep(1)

    except KeyboardInterrupt:
        pass

    finally:
        request.set_value(LINE, Value.INACTIVE)
