#!/usr/bin/env python3
"""
Stomp — Guitar Tab Manager
Entry point. Pass --no-gpio to run without GPIO (keyboard only mode).
"""
import sys

def main():
    use_gpio = "--no-gpio" not in sys.argv
    from app.app import StompApp
    app = StompApp(use_gpio=use_gpio)
    app.mainloop()


try:
    if __name__ == "__main__":
        main()
except KeyboardInterrupt:
    print("Ending")

