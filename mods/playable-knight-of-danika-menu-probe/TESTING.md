# Knight of Danika - Native Change Class Menu Probe

This build is **read-only**. It does not change class IDs, roster data, saves, enemies, or battle state.

## One-pass test

1. Enable only `Knight of Danika - Native Class Menu Probe` among Danika developer probes.
2. Start/load a normal save.
3. Open the organization screen and enter **Change Class / Trocar Classe**.
4. Select one ordinary character that is allowed to use Change Class.
5. Move the cursor across at least two available class choices, then back out without saving anything.
6. Copy the console/log lines beginning with `DANIKA_`.

Expected baseline:

```text
DANIKA_MENU_PROBE ready read_only
DANIKA_SELECTED i=.. class=..
DANIKA_MENU +.. ..->..
```

The changed offsets reveal which native state bytes carry selected character / candidate / page / confirmation state. This is intended to be the last diagnostic before inserting class `0x71` into the real native Change Class path.
