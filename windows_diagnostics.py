"""Enumerate matching HID interfaces; --probe queries status/topology only."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true', help='Open the hub and query status and LED counts; no mode or motor changes')
    parser.add_argument('--sensors', action='store_true', help='Read configured CPU/GPU sensors only; no HID commands')
    args = parser.parse_args()
    if sys.platform != 'win32':
        print('This diagnostic is for Windows.'); return 1
    try:
        if args.sensors:
            import time
            import windows_sensors
            from sensors import cpu_temperature
            try:
                for _ in range(150):
                    sensors=windows_sensors.read_sensors()
                    if sensors or 'Waiting' not in windows_sensors.status():break
                    time.sleep(.1)
                print(windows_sensors.status())
                for sensor in sensors:
                    print(f'{sensor.key} | {sensor.label} | {sensor.kind} | {sensor.value}')
                cpu=cpu_temperature(sensors)
                print('CPU temperature:',cpu.value if cpu else 'unavailable')
                return 0 if cpu and cpu.value is not None else 1
            finally:windows_sensors.stop()
        import hid
        import asiahorse as usb
        devices = hid.enumerate(usb.VID, usb.PID)
        print('Python:', sys.version.split()[0])
        print('Matching Umbra HID interfaces:', len(devices))
        for i, d in enumerate(devices, 1):
            print(f"Interface {i}: product={d.get('product_string')!r}, interface={d.get('interface_number')}, usage_page={d.get('usage_page')}, usage={d.get('usage')}, release={d.get('release_number')}")
        if args.probe:
            h = usb.open_hub()
            try:
                usb.write(h, usb.native(bytes([0])))
                reply = usb.read_reply(h)
                if not reply.startswith(b'RB'):
                    raise OSError('No valid status reply. Close other controllers and try again.')
                print('Status reply:', reply.hex(' '))
                counts = usb.topology(h)
                print('LED counts P1-P10:', counts)
                if not sum(counts):
                    raise OSError('No LED topology read; do not start RGB yet.')
                print('Status/topology probe passed. No RGB-mode or motor commands sent.')
            finally:
                h.close()
        return 0
    except (ImportError, OSError, SystemExit) as exc:
        print('Diagnostic failed:', exc); return 1


if __name__ == '__main__':
    raise SystemExit(main())
