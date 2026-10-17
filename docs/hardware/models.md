# Tested models

Models the plugin has been run on, and what was checked. Any model
[qnap8528](https://github.com/0xGiddi/qnap8528) supports should work,
since everything is discovered at runtime; this table records evidence,
not a whitelist. To add a model, follow
[../testing/model-testing.md](../testing/model-testing.md).

**Status:** *verified* = every row checked on hardware by the maintainer;
*reported* = a tester's model test report, part 2 included; *partial* =
read-only report or some checks only.

| Model | QM2 card | Plugin | Status | Fans | LEDs | Buttons | Notes | Source |
|-|-|-|-|-|-|-|-|-|
| TS-877 | — | — | planned | 2 groups (`pwm1`, `pwm7`), 4 fans | status, ident, hdd1-6, ssd1-2, m2ssd1-2; no hardware activity blink on bays | to check | LCD and buzzer researched, not tested | [ts-877.md](ts-877.md) |
| TS-253D | QM2-2P-244A-A1 | 8.0.0 | verified | 1 group, stall measured | status, 2 bays, QM2 slots | Reset = BTN_1, USB Copy = BTN_2 | reference box | [ts-253d.md](ts-253d.md) |
