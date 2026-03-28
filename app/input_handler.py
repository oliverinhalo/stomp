import glob
import logging
import time
import threading

# Input event constants
EVT_LEFT          = "left"
EVT_RIGHT         = "right"
EVT_MIDDLE        = "middle"
EVT_MIDDLE_LONG   = "middle_long"
EVT_MIDDLE_TRIPLE = "middle_triple"
EVT_SPACE         = "space"
EVT_ZOOM_OUT      = "zoom_out"
EVT_ZOOM_IN       = "zoom_in"
EVT_PAGE_PREV     = "page_prev"
EVT_PAGE_NEXT     = "page_next"
EVT_UNLOCK        = "unlock"
EVT_LOCK          = "lock"

LONG_PRESS_THRESHOLD = 0.8   # seconds
SIMULTANEOUS_WINDOW  = 0.25  # seconds for multi-pedal detection
TRIPLE_TAP_WINDOW   = 0.5   # seconds for triple middle detection


logger = logging.getLogger(__name__)

class InputHandler:
    """
    Unified input handler for 3-pedal GPIO and keyboard fallback.
    Fires callbacks for: left, right, middle, middle_long, space, unlock.
    """

    def __init__(self, pin_left=17, pin_middle=27, pin_right=22, use_gpio=True, use_serial=False, serial_port="/dev/ttyACM0"):
        self.callbacks = {}
        self._press_times = {}
        self._held = {}
        self._lock = threading.Lock()
        self._use_gpio = use_gpio
        self._running = False
        self._simultaneous_fired = False
        self._simultaneous_suppressed = set()
        self._middle_taps = []
        self._middle_timer = None
        self._serial_port = serial_port
        self._ser = None
        self._serial_thread = None
        self._serial_lock = threading.Lock()

        if use_serial:
            self._start_serial(serial_port)
            logger.info("Serial input enabled, starting serial thread")
        if use_gpio:
            self._init_gpio(pin_left, pin_middle, pin_right)

    def _init_gpio(self, pin_left, pin_middle, pin_right):
        try:
            from gpiozero import Button
            self._btns = {
                EVT_LEFT:   Button(pin_left,   pull_up=True, bounce_time=0.05, hold_time=LONG_PRESS_THRESHOLD),
                EVT_MIDDLE: Button(pin_middle, pull_up=True, bounce_time=0.05, hold_time=LONG_PRESS_THRESHOLD),
                EVT_RIGHT:  Button(pin_right,  pull_up=True, bounce_time=0.05, hold_time=LONG_PRESS_THRESHOLD),
            }

            self._btns[EVT_LEFT].when_pressed   = lambda: self._on_press(EVT_LEFT)
            self._btns[EVT_MIDDLE].when_pressed  = lambda: self._on_press(EVT_MIDDLE)
            self._btns[EVT_RIGHT].when_pressed   = lambda: self._on_press(EVT_RIGHT)

            self._btns[EVT_LEFT].when_released   = lambda: self._on_release(EVT_LEFT)
            self._btns[EVT_MIDDLE].when_released = lambda: self._on_release(EVT_MIDDLE)
            self._btns[EVT_RIGHT].when_released  = lambda: self._on_release(EVT_RIGHT)

            self._btns[EVT_MIDDLE].when_held     = self._on_middle_held

        except Exception as e:
            logger.warning("GPIO init failed: %s — keyboard only mode", e)
            self._use_gpio = False

    def _on_press(self, name):
        now = time.time()
        with self._lock:
            self._press_times[name] = now
            self._held[name] = True

        # Check for simultaneous 2-pedal press (space or unlock gesture)
        threading.Timer(SIMULTANEOUS_WINDOW, self._check_simultaneous, args=[name, now]).start()

    def _check_simultaneous(self, name, press_time):
        with self._lock:
            active = {k for k, v in self._held.items() if v}

        if self._simultaneous_fired:
            return

        if active == {EVT_LEFT, EVT_RIGHT, EVT_MIDDLE}:
            self._simultaneous_fired = True
            self._simultaneous_suppressed = set(active)
            self._fire(EVT_LOCK)
            return

        if active == {EVT_LEFT, EVT_RIGHT}:
            self._simultaneous_fired = True
            self._simultaneous_suppressed = set(active)
            self._fire(EVT_UNLOCK)
            return

        if active == {EVT_LEFT, EVT_MIDDLE}:
            self._simultaneous_fired = True
            self._simultaneous_suppressed = set(active)
            self._fire(EVT_ZOOM_OUT)
            return

        if active == {EVT_RIGHT, EVT_MIDDLE}:
            self._simultaneous_fired = True
            self._simultaneous_suppressed = set(active)
            self._fire(EVT_ZOOM_IN)
            return

    def _on_release(self, name):
        with self._lock:
            press_time = self._press_times.pop(name, None)
            self._held[name] = False

            if name in self._simultaneous_suppressed:
                self._simultaneous_suppressed.discard(name)
                if not self._simultaneous_suppressed:
                    self._simultaneous_fired = False
                return

        if press_time is None:
            return

        duration = time.time() - press_time
        if name == EVT_MIDDLE and duration < LONG_PRESS_THRESHOLD:
            now = time.time()
            self._middle_taps.append(now)
            self._middle_taps = [t for t in self._middle_taps if now - t < TRIPLE_TAP_WINDOW]
            if len(self._middle_taps) >= 3:
                self._middle_taps.clear()
                if self._middle_timer:
                    self._middle_timer.cancel()
                    self._middle_timer = None
                self._fire(EVT_MIDDLE_TRIPLE)
                return

            if self._middle_timer:
                self._middle_timer.cancel()
            self._middle_timer = threading.Timer(TRIPLE_TAP_WINDOW, self._flush_middle_tap)
            self._middle_timer.start()
            return

        if name != EVT_MIDDLE and duration < LONG_PRESS_THRESHOLD:
            self._fire(name)
        elif name == EVT_MIDDLE and duration >= LONG_PRESS_THRESHOLD:
            self._flush_middle_tap(cancel=True)
            self._fire(EVT_MIDDLE_LONG)

    def _on_middle_held(self):
        self._flush_middle_tap(cancel=True)
        self._fire(EVT_MIDDLE_LONG)

    def _flush_middle_tap(self, cancel=False):
        with self._lock:
            if self._middle_timer:
                self._middle_timer.cancel()
                self._middle_timer = None
            if cancel:
                self._middle_taps.clear()
                return
            if self._middle_taps:
                self._middle_taps.clear()
                self._fire(EVT_MIDDLE)

    def _fire(self, event):
        cb = self.callbacks.get(event)
        if cb:
            cb()

    def on(self, event, callback):
        self.callbacks[event] = callback

    def bind_keyboard(self, root):
        """Bind keyboard keys as pedal fallback. Call after Tk root exists."""
        root.bind("<Left>",  lambda e: self._fire(EVT_LEFT))
        root.bind("<Right>", lambda e: self._fire(EVT_RIGHT))
        root.bind("<Prior>", lambda e: self._fire(EVT_PAGE_PREV))
        root.bind("<Next>", lambda e: self._fire(EVT_PAGE_NEXT))
        root.bind("<u>",     lambda e: self._fire(EVT_UNLOCK))
        root.bind("<Up>",    lambda e: self._fire(EVT_LEFT))
        root.bind("<Down>",  lambda e: self._fire(EVT_RIGHT))


    def _find_serial_ports(self):
        candidates = []
        if self._serial_port:
            candidates.append(self._serial_port)
        candidates.extend(sorted(glob.glob("/dev/ttyACM*")))
        candidates.extend(sorted(glob.glob("/dev/ttyUSB*")))
        ports = [p for i, p in enumerate(candidates) if p not in candidates[:i]]
        logger.debug("Serial port candidates: %s", ports)
        return ports

    def _open_serial(self, port):
        import serial

        try:
            ser = serial.Serial(port, 115200, timeout=1)
            with self._serial_lock:
                self._ser = ser
            logger.info("Serial connected on %s", port)
            return True
        except Exception as e:
            logger.warning("Serial failed on %s: %s", port, e)
            return False

    def _close_serial(self):
        with self._serial_lock:
            if getattr(self, '_ser', None):
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None

    def _start_serial(self, port):
        self._serial_port = port
        self._serial_thread = threading.Thread(target=self._serial_loop, daemon=True)
        self._serial_thread.start()

    def _serial_loop(self):
        last_state = (0, 0, 0)

        while True:
            if self._ser is None:
                for port in self._find_serial_ports():
                    if self._open_serial(port):
                        break
                if self._ser is None:
                    time.sleep(2)
                    continue

            try:
                with self._serial_lock:
                    ser = self._ser
                if ser is None:
                    continue

                line = ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue

                parts = line.split(",")
                if len(parts) != 3:
                    continue

                state = tuple(int(x) for x in parts)

                # Map to events
                mapping = [EVT_LEFT, EVT_MIDDLE, EVT_RIGHT]

                for i, (prev, curr) in enumerate(zip(last_state, state)):
                    name = mapping[i]
                    if curr == 1 and prev == 0:
                        self._on_press(name)
                    elif curr == 0 and prev == 1:
                        self._on_release(name)

                last_state = state

            except Exception as e:
                logger.exception("Serial loop error")
                self._close_serial()
                last_state = (0, 0, 0)
                time.sleep(1)
                self._close_serial()
                last_state = (0, 0, 0)
                time.sleep(1)