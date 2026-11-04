# Umbra USB protocol notes

Adapted from the original Linux project by ToeTagger / LuxDev372, with fan-control findings contributed by glassknug. See README.md for credits and hardware-validation limits.

## Protocol documentation

Everything below was cross-validated from two independent sources (a
Wireshark capture and a published SignalRGB plugin) plus live testing;
the checksum math reproduces both sources byte-for-byte.

**Transport:** USB HID, 65-byte output reports = report ID `0x00` + 64-byte
payload, zero-padded.

**Checksum:** 8-bit additive over all preceding packet bytes:
`sum = (sum + byte) & 0xFF`, appended as the final meaningful byte.

**Native command packet:**

```
52 42 <len> 00 <body...> <checksum>      len = body length + 5
```

| Body      | Meaning                                          |
|-----------|--------------------------------------------------|
| `00`      | Status query (hub replies with a `52 42` frame)  |
| `01 FF`   | Topology query (reply below)                     |
| `FD 01`   | Enter software-controlled RGB mode (see quirks!) |
| `08 00`   | Motherboard fan-control sync on (3.5.5 UI path)  |
| `08 01`   | Software fan control (3.5.5 UI path)             |
| `FB nn`   | Hub-wide motor duty percentage, `nn` is 0–100    |

**Topology reply:** ten 5-byte records starting at offset 6:
`[led_count, ?, ?, port_index, ?]` for ports 0–9.

**Direct RGB streaming packet:**

```
88 <packet_count> <packet_index> <20 x R,G,B> <checksum>
```

Frame = all ports' LEDs concatenated in port order 0–9, padded with black
to `packet_count * 20` slots. `packet_count = ceil(total_leds / 20)`.

## Hard-won quirks (read before coding against this)

1. **The packet index is 1-BASED.** Sending index 0 makes the firmware
   drop off the USB bus entirely. This cost us an evening.
2. **`FD 01` (software mode) makes the hub re-enumerate.** It disappears
   from USB and returns, possibly under a different hidraw node — and the
   *old* node can linger briefly, so a quick reopen can grab a corpse.
   Reopen and **ping with a status query until it answers** before
   streaming ("proof of life before paint").
3. **Colors latch.** The hub holds the last streamed frame indefinitely
   with zero refresh — event-driven control works fine. Power loss resets
   to the hub's built-in effects (a warm reboot does not: the hub is
   SATA-powered).
4. **The diodes have no gamma.** High-brightness mixed colors wash toward
   white; run saturated colors dark (true amber ≈ `200,110,10`, not
   `245,189,99`).
5. **Return-to-hardware-effects command: unknown.** `FD 00` is untried.
   A full power cycle restores the hub's own effects.
6. **The pip `hidapi` wheel may use the libusb backend**, which ignores
   hidraw permissions and fails to open the device. This tool avoids the
   problem by using `/dev/hidraw` directly — no dependencies.


## Individual motor-control investigation

Static inspection of the supplied UMBRA 3.5.5 Windows program shows `ARGB_pwm_speed(device, percentage)` building an `FB <percentage>` body with no port field. The examined speed-selector handlers use their index to choose a preset percentage and store one shared `FAN_speed`. `write_argb_fan_all` writes JSON settings rather than HID traffic. The examined `argb_fan_set(device, id)` selects a lighting configuration, not a verified motor-duty target.

These inspected paths do not establish individual motor control; other revisions or undocumented capabilities remain unknown. The layout preview sends only the previously implemented hub-wide commands.


## Follow-up on independent motor speeds (November 4, 2026)

The manufacturer describes independent color/lighting control for arrays separately from adjustable PWM curves and software/motherboard PWM ownership. Its public download center still lists UMBRA software 3.5.5. Neither establishes a USB motor-duty command with a port field. The SignalRGB implementation documents independent ARGB channels, not per-port motor-duty control.

References checked:
- https://asiahorse.store/products/umbra-argb-pwm-hub?variant=52003330195769
- https://asiahorse.store/pages/software-download-center
- https://github.com/maihcx/AsiaHorse-Umbra-ARGB-Hub-SignalRGB-Plugin

To implement independent motor duty on the Umbra hub, obtain model/firmware-specific documentation or a capture showing two ports held at different requested duties. Determine port addressing, ownership, restoration and fail-safe behavior before implementation. A separate PWM control path per group, such as individually controllable motherboard headers, is another architecture; sharing an ARGB port does not provide motor-speed addressing. No such alternate backend or unverified packet is enabled in this preview.
