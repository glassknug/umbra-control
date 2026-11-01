"""Deterministic LED effects and a single-owner USB animation worker."""
import colorsys
import math
import queue
import threading
import time
from dataclasses import dataclass

import asiahorse as usb
from fan_curves import curve_duty, sensor_id, smooth_duty, validate_points
from sensors import read_sensors

EFFECTS = ("Solid color", "Breathing", "Rainbow", "Color cycle", "Chase")


@dataclass(frozen=True)
class Settings:
    effect: str = "Solid color"
    color: tuple = (113, 230, 207)
    brightness: float = 0.7
    speed: float = 1.0



@dataclass(frozen=True)
class SceneSettings:
    # Ports are 1-based in the UI; the wire LED stream remains in port order.
    ports: tuple
    effect: str = "RGB layout"

    def __post_init__(self):
        used = set()
        for port, settings in self.ports:
            if type(port) is not int or not 1 <= port <= 10 or port in used:
                raise ValueError("Assign each RGB port (1–10) only once")
            if not isinstance(settings, Settings) or settings.effect not in EFFECTS:
                raise ValueError("Invalid per-port effect")
            used.add(port)


def static_settings(settings):
    if isinstance(settings, SceneSettings):
        return all(s.effect == "Solid color" for _, s in settings.ports)
    return settings.effect == "Solid color"


def make_frame(ports, settings, elapsed):
    """Repeat the effect independently on each port; speed = cycles / 4 seconds."""
    if isinstance(settings, SceneSettings):
        mapped = dict(settings.ports)
        frame = []
        for port, count in enumerate(ports, 1):
            chosen = mapped.get(port, Settings(brightness=0))
            frame.extend(make_frame([count], chosen, elapsed))
        return frame
    if settings.effect not in EFFECTS:
        raise ValueError("Unknown effect")
    phase = elapsed * settings.speed / 4
    level = max(0, min(1, settings.brightness))
    frame = []
    for count in ports:
        for led in range(count):
            gain = 1
            rgb = settings.color
            if settings.effect == "Breathing":
                gain = (1 + math.cos(phase * math.tau)) / 2
            elif settings.effect == "Rainbow":
                rgb = tuple(255 * c for c in colorsys.hsv_to_rgb((led / count - phase) % 1, 1, 1))
            elif settings.effect == "Color cycle":
                rgb = tuple(255 * c for c in colorsys.hsv_to_rgb(phase % 1, 1, 1))
            elif settings.effect == "Chase":
                # A bright head and fading tail, wrapping around each LED chain.
                distance = (phase * count - led) % count
                gain = max(0, 1 - distance / max(1, count / 4))
            frame.append(tuple(max(0, min(255, round(c * level * gain))) for c in rgb))
    return frame


def send_frame(hub, colors):
    if not colors:
        raise ValueError("No LEDs detected")
    count = math.ceil(len(colors) / usb.LEDS_PER_PACKET)
    if count > 255:
        raise ValueError("Too many LEDs")
    for index in range(count):
        chunk = colors[index * 20:(index + 1) * 20]
        chunk += [(0, 0, 0)] * (20 - len(chunk))
        # Never send index 0: this firmware drops off the bus.
        written = usb.write(hub, usb.rgb_packet(count, index + 1, chunk))
        if written != usb.PAYLOAD + 1:
            raise OSError("Incomplete USB write")


class Player:
    """Only this worker touches HID. Tk communicates through queues."""
    def __init__(self):
        self.port_counts = ()
        self.events = queue.Queue()
        self.fan_events = queue.Queue()
        self.commands = queue.Queue()
        self.closing = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def start(self, settings):
        self.commands.put(("start", settings))

    def stop(self):
        self.commands.put(("stop", None))

    def off(self):
        self.start(Settings(brightness=0))

    def fan_manual(self, percent):
        percent = float(percent)
        if not 30 <= percent <= 100:
            raise ValueError("Fan duty must be 30–100%")
        self.commands.put(("fan_manual", percent))

    def fan_curve(self, points, sensor):
        if not sensor:
            raise ValueError("Select a temperature sensor first")
        self.commands.put(("fan_curve", (validate_points(points), sensor)))

    def fan_full(self):
        self.fan_manual(100)

    def close(self):
        self.closing.set()
        self.commands.put(("close", None))

    def _connect(self):
        hub = usb.open_hub()
        try:
            ports = usb.topology(hub)
            if not sum(ports):
                raise RuntimeError("Could not read LED counts. Check the hub connections.")
            usb.write(hub, usb.native(bytes([0xFD, 0x01])))
        finally:
            hub.close()
        if self.closing.wait(0.5):
            return None, ports
        hub = usb.stabilize()
        return hub, ports

    @staticmethod
    def _fan_write(hub, percent, claim=False):
        def write(body):
            if usb.write(hub, usb.native(bytes(body))) != usb.PAYLOAD + 1:
                raise OSError("Incomplete fan-control write")
        if claim:
            write([0xFB, 100])
            write([0x08, 0x01])
        write([0xFB, round(percent)])

    def _run(self):
        hub = None
        settings = None
        ports = []
        start = 0
        repeats = 0
        fan_plan = None
        fan_owned = False
        previous = None
        next_sample = 0
        last_sample = time.monotonic()
        try:
            while not self.closing.is_set():
                try:
                    command, value = self.commands.get(timeout=0.05 if settings else 0.2)
                except queue.Empty:
                    command = None
                if command == "close":
                    break
                if command == "stop":
                    settings = None
                    self.events.put("Stopped · last frame stays lit. Use Turn off RGB to switch off.")
                elif command == "start":
                    settings = value
                    start = time.monotonic()
                    repeats = 0
                elif command == "fan_manual":
                    fan_plan = ("manual", value)
                    next_sample = 0
                elif command == "fan_curve":
                    fan_plan = ("curve", value)
                    next_sample = 0
                try:
                    if settings is not None and not ports:
                        # Switching RGB mode re-enumerates USB: reapply fan settings afterwards.
                        if hub is not None:
                            hub.close()
                            hub = None
                        self.events.put("Connecting to hub…")
                        hub, ports = self._connect()
                        self.port_counts = tuple(ports)
                        fan_owned = False
                        previous = None
                        next_sample = 0
                        start = time.monotonic()
                        if hub is None:
                            break
                    if fan_plan is not None and hub is None:
                        hub = usb.open_hub()
                        fan_owned = False
                    if self.closing.is_set():
                        break
                    if fan_plan is not None and time.monotonic() >= next_sample:
                        now = time.monotonic()
                        temp = None
                        fault = False
                        if fan_plan[0] == "manual":
                            target = fan_plan[1]
                        else:
                            points, identity = fan_plan[1]
                            matches = [s for s in read_sensors() if s.kind == "temperature" and sensor_id(s) == identity]
                            temp = matches[0].value if len(matches) == 1 else None
                            fault = temp is None or not math.isfinite(temp) or not -20 <= temp <= 130
                            target = curve_duty(points, temp)
                        duty = smooth_duty(previous, target, now - last_sample)
                        # Remember ownership before any write, so shutdown still attempts full duty on failure.
                        claim = not fan_owned
                        fan_owned = True
                        self._fan_write(hub, duty, claim)
                        previous = duty
                        last_sample = now
                        next_sample = now + 1
                        self.fan_events.put(dict(temperature=temp, duty=round(duty),
                            mode="Sensor unavailable · requesting 100%" if fault else
                            "Overtemperature · requesting 100%" if temp is not None and temp >= 85 else
                            "Curve active" if fan_plan[0] == "curve" else "Manual duty"))
                    if settings is not None:
                        send_frame(hub, make_frame(ports, settings, time.monotonic() - start))
                        repeats += 1
                        if repeats == 1:
                            self.events.put(f"{settings.effect} · {sum(ports)} LED · {sum(n > 0 for n in ports)} ports")
                        if static_settings(settings) and repeats >= 5:
                            settings = None
                except (OSError, RuntimeError, ValueError, SystemExit) as exc:
                    self.events.put(f"Could not control hub: {exc}")
                    if fan_plan is not None:
                        self.fan_events.put(dict(temperature=None, duty=None, mode=f"USB error: {exc}. Check cooling; control stopped."))
                    if fan_owned and hub is not None:
                        try:
                            self._fan_write(hub, 100)
                        except OSError:
                            self.events.put("Could not request 100% after USB failure. Check cooling.")
                    fan_plan = None
                    settings = None
                    previous = None
                    ports = []
                    self.port_counts = ()
                    fan_owned = False
                    if hub is not None:
                        hub.close()
                        hub = None
        finally:
            if hub is not None:
                try:
                    if fan_owned:
                        self._fan_write(hub, 100)
                except OSError as exc:
                    self.events.put(f"Could not request 100% on exit: {exc}. Check cooling.")
                finally:
                    hub.close()
