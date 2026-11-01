# Umbra Control for Linux 0.4.0 preview — RGB layout

Build a lighting layout that matches your PC, with independent RGB settings for each Umbra port.

## New: RGB layout

- Drag fans, LED strips and Strimer-style ARGB cables into a graphical PC case.
- Name each port group and assign its physical hub port (1–10).
- For a Fan object, choose **Fan count · daisy chain** to display 1–10 fans together.
- Arrange groups **horizontally or vertically**, then move the whole group into place.
- Set each port group's color, effect, brightness and animation speed.
- Save device types, positions, orientation, fan counts and lighting settings locally.
- Existing layouts open with a default count of one fan.
- Apply uses the LED counts read from the hub and the existing shared USB worker.

The count is a visual setting. Fans/devices on the same port share an effect. **Unassigned ports turn dark when Apply layout RGB is pressed.** Loading a saved layout does not apply it automatically.

ARGB cable shapes are for compatible lighting attached to Umbra's ARGB outputs. They do not add support for separate USB cable controllers. Individual fan motor control is not included; existing fan curves still control hub-wide duty.

## Existing features retained

Five RGB effects; temperature-based fan curves; profiles and app shortcuts; live CPU temperature and graphs; background operation; optional login startup; and application-menu integration.

## Installation and update

Quit any running copy. Extract the complete attached ZIP and open a terminal in its `umbra-control-linux` folder. After the Tk and USB permission setup described in README.md, run without sudo:

```bash
python3 install_desktop.py
```

Start **Umbra Control** from the application menu. Profiles and saved layouts remain in your user configuration folder.

## Validation

**37 automated tests pass**, including port offsets, independent effects, daisy-chain count migration/persistence, group geometry, failed-save recovery, installed imports and RGB playback alongside fan control.

User screenshots from Bazzite show the new interface, multi-fan groups, cable placement and distinct lighting colors per port group. Other hub revisions, more effects and combined-operation scenarios need further hardware testing. Fan duty is requested percentage, not measured RPM; lower motor duty values and login startup still need broader validation.

Original community driver and protocol credits and the MIT license are preserved.
