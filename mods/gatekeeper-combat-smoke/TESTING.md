# Gatekeeper Combat Smoke Test

This is a **developer-only** smoke test for the playable Gatekeeper project.

## What this build does

At runtime it scans only the proven persistent **player roster** and converts the
**second Fighter (`0x02`) encountered in roster order** into Gatekeeper / Knight
of Danika (`0x71`).

It does not touch live battle/enemy participant memory and it does not globally
replace class resources.

## Important save warning

The class byte belongs to persistent roster RAM. Use a disposable/copy save and
**do not save over an important save while this test mod is enabled**.

## Test procedure

1. Disable older Danika/Gatekeeper development swap mods so only this smoke test performs the class conversion.
2. Load a normal save containing at least two Fighters.
3. Open the army/organization screen.
4. Find the Fighter that became Gatekeeper. The console should contain:
   `GATEKEEPER_SMOKE fighter2 02->71 i=XX`
5. Put that Gatekeeper into a deployed combat unit.
6. Enter a normal battle and observe:
   - whether the class reaches battle without crash;
   - front and rear body presentation;
   - idle stance;
   - attack animation;
   - whether a weapon appears;
   - whether the weapon is one-handed or two-handed;
   - any missing/corrupt frame, palette or anchor.
7. Do **not** save the game after the test if you want your original roster unchanged.

If the roster has fewer than two Fighters when the hook first runs, the mod stays
read-only and retries later. It logs `GATEKEEPER_SMOKE waiting_for_second_fighter`
only once.

## Scope of this milestone

This build intentionally does **not** yet patch rear animation, greatsword
anchors, equipment eligibility, stats, promotion requirements or class-menu
availability. Its purpose is to obtain a clean, reproducible player-side battle
baseline for class `0x71` before redirecting only the missing presentation pieces
to Dragoon `0x14`.
