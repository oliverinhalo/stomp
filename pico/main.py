from machine import Pin
import time
import sys

left = Pin(15, Pin.IN, Pin.PULL_UP)
middle = Pin(14, Pin.IN, Pin.PULL_UP)
right = Pin(13, Pin.IN, Pin.PULL_UP)

def read_buttons():
    return (
        not left.value(),
        not middle.value(),
        not right.value()
    )

last = (0, 0, 0)

while True:
    current = read_buttons()

    if current != last:
        print(f"{int(current[0])},{int(current[1])},{int(current[2])}")
        last = current

    time.sleep(0.01)
