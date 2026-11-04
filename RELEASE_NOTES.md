# 0.5.0 preview — Identify port and configuration sharing

- RGB layout: Identify port blinks a selected port cyan/dark for three seconds and restores previous colors. Apply RGB once before identification so restoration is possible. Animations resume; fan control continues in the shared worker.
- Export/Import tab: export the current RGB layout and saved fan profiles to a portable JSON file.
- Review imports and map temperature sensors to this computer. Unmapped profiles stay unapplied until a sensor is selected.
- Existing saved files are backed up before replacement. Failed imports attempt rollback. Import never activates RGB, curves or login startup automatically.
- Keep all existing RGB, fan-curve and daisy-chain layout functionality.

47 automated tests pass, including identification restoration, continued motor control, portable sensor hints, strict import validation, stale-sensor rejection and multi-file rollback. Desktop and live hub verification are pending. This is a test branch, not a replacement for the published 0.4.0 preview.

Individual motor duty is still unverified. No speculative USB motor commands are included.
