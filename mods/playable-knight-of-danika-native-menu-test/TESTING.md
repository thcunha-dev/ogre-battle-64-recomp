# Knight of Danika - Native Change Class Test

This build is a **temporary RAM-only candidate injection test**.

## What it does

It changes exactly one byte in the Dragoon `0x14` class record while the game is running:

- Dragoon transition slot `+0x44`
- expected original value: `0x11`
- temporary test value: Knight of Danika `0x71`

It does **not** write the persistent player roster, save data, enemy participants, or the Danika `0x71` class record.

## Test

1. Disable older Danika developer test mods.
2. Enable only `Knight of Danika - Native Change Class Test`.
3. Load a copy/disposable save.
4. Open **Organization -> Change Class / Trocar Classe**.
5. Select a normal **Dragoon** (`0x14`).
6. Check every class candidate offered by the native menu.
7. If Knight of Danika/Gatekeeper appears, select it and confirm only if you are using a disposable save.
8. Report exactly what happened: option absent, option appears but cannot be selected, successful class change, crash, or visual problem.

The test is intentionally scoped to Dragoon because the native transition metadata for Dragoon is already proven and gives us a controlled donor path into Danika `0x71`.
