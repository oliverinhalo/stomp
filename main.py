#!/usr/bin/env python3
"""
Stomp — Guitar Tab Manager
Entry point. Pass --no-gpio to run without GPIO (keyboard only mode).
"""
import logging
import os
import sys

LOG_FILE = os.path.join(os.path.dirname(__file__), "stomp.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("stomp")


def main():
    use_gpio = "--no-gpio" not in sys.argv
    logger.info("Starting Stomp main (use_gpio=%s)", use_gpio)
    from app.app import StompApp
    app = StompApp(use_gpio=use_gpio)
    app.mainloop()


try:
    if __name__ == "__main__":
        main()
except KeyboardInterrupt:
    print("Ending")

