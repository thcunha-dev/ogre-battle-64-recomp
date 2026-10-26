# Knight of Danika - Allied Gameplay Test

This is a developer smoke test for gameplay only. It converts the first generic allied Fighter (`0x02`) in the persistent player roster to Knight of Danika (`0x71`).

## Safety

- Use a copy/disposable save.
- Do **not** save over an important save while the mod is enabled.
- The mod does not scan or modify live enemy battle participants.
- Disable the mod and restart the game to stop the runtime conversion.

## Test

1. Enable only `Knight of Danika - Allied Gameplay Test` among Danika test mods.
2. Load a save that has at least one generic Fighter.
3. Open the organization screen and locate the Fighter that changed class.
4. Put that character in a deployable unit.
5. Enter a battle/map and verify:
   - the game does not crash;
   - the character remains class `0x71`;
   - the character can be deployed;
   - battle starts normally;
   - attacks/turns resolve;
   - front/rear presentation, weapon and animation behavior are noted.
6. Do not save the game after the test.

The goal is not balance yet. The goal is to prove that class `0x71` can survive the full allied gameplay path. Any visual/pose/weapon problems become the next targeted fixes.
