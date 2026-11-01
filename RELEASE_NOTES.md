# 0.4.0 RGB layout preview

Adds a PC-case canvas with draggable fans, LED strips and Strimer-style ARGB cables. Assign one group per hub port, then choose its RGB color, effect, brightness, speed and orientation. Save the layout locally and explicitly apply it through the existing USB worker using detected LED counts.

Unassigned ports turn dark when applying a layout. All-port RGB and layout RGB replace each other. The new tab issues no motor-duty commands; individual motor speed remains unverified. Separate cable USB controllers are not supported.

Automated tests cover per-port stream offsets (including empty ports), independent effects, input validation, failed-save recovery, RGB-only apply routing and installed imports. Desktop visual/dragging and new live per-port hardware tests remain pending.

The existing 0.3.3 preview release remains available separately.
