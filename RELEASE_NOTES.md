# Umbra Control for Linux 0.3.3 preview

First standalone preview under the Umbra Control name.

- Five RGB effects with color, brightness and speed controls.
- USB fan curves, manual duty, saved profiles and application shortcuts.
- Live CPU temperature and temperature/requested-duty history.
- Close-to-minimize background operation and explicit Quit.
- Optional saved-curve startup after desktop login, disabled by default.
- Application-menu integration and bundled icon.
- Packaging fix for the startup dependency missing in 0.3.2.

## Validation

22 automated tests pass, including startup-module imports from an isolated installed copy.
All five RGB effects and GUI operation have been reported working on Bazzite.
USB motor-speed changes were hardware-tested at requested 100% → 75% → 100%.

This is a preview. Lower duty values, other hub revisions, combined RGB/curve operation and login startup need further hardware testing. Displayed duty is a request, not measured RPM. Quit requests 100%; crash, suspend or USB loss can interrupt control.

## Installation

Extract the source archive and follow README.md for Tk and USB permissions. Run `python3 install_desktop.py` without sudo, then open Umbra Control from the application menu.

Original driver and RGB-protocol credits remain in README.md and LICENSE.
