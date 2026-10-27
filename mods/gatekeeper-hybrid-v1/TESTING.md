# Gatekeeper Hybrid v1 — test protocol

This build exists to establish a safe playable combat baseline.

## What it does

- Finds the **second** Fighter (`0x02`) in the player's persistent roster.
- Converts only that roster entry to Gatekeeper (`0x71`).
- Keeps roster/UI identity as Gatekeeper.
- During battle only, finds that exact live participant by roster index and
  corroborates level + EXP.
- Changes only that live participant's class byte to playable Dragoon (`0x14`).
- Before battle models are created, Gatekeeper render records are redirected to
  the Dragoon visual selector discovered from the game's own loaded resource
  table.

## Why

Direct Gatekeeper 0x71 can reach menus but may black-screen during battle load
with an arbitrary Fighter/equipment combination. Dragoon 0x14 is a proven
player-side combat package and is visually/animation-wise close to the original
Gatekeeper's 2H attack style. This bridge lets us prove rear-facing animation,
2H motion, and dynamic weapon rendering before replacing the Dragoon body with
Gatekeeper-specific rear graphics.

## Safety

- Disable all older Danika/Gatekeeper test mods.
- Use a copy/disposable save.
- Do not save over your main save while this build is active.
- Enemy participant memory is never intentionally written.
- The persistent roster write is only the second exact Fighter 0x02 -> 0x71.

## What to observe

1. Does the second Fighter become Gatekeeper in menu/formation?
2. Does training/battle load instead of staying on a black screen?
3. In battle, does the unit now use a Dragoon-like rear body/stance?
4. Is the currently equipped weapon visible?
5. Does the weapon appear to be held/animated with the Dragoon 2H motion?
6. Any missing body parts, bad palette, or crash after the first attack?

Expected v1 limitation: the body in combat may look like a Dragoon. That is
intentional. The next visual milestone is to retain this safe player-side
skeleton/motion while replacing/recoloring the body toward the Gatekeeper.
