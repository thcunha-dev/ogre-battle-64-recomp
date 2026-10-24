# Universal Item Randomizer 0.3.1 — Stock Runtime QA

This is a **QA-only** build for the official Ogre Battle 64 Recomp v0.8.3 Windows/Linux/macOS runtime.

It intentionally omits the streamed Bank-N replacement for `func_ovlN_801DC740`. The official v0.8.3 runtime cannot resolve that replacement because it does not include the custom Bank-N function registry used by the final Universal Item Randomizer runtime build.

## What this QA build can validate

- deterministic seed mapping;
- Table-O map/drop source rewriting and popup/delivery consistency;
- Table-P ground pickup source rewriting;
- persisted battle-reward source rewriting;
- post-battle `func_80172820(id,count)` equipment adds;
- shop stock rewrite with `RANDOMIZE SHOPS=ON`;
- native save compatibility with the mod enabled/disabled;
- close/reopen with the same seed;
- changing seed affects future acquisitions only;
- transient `+0x02` used-count repair, including slot-indexed semantics;
- full-inventory and count-saturation behavior on covered routes.

## What this QA build intentionally does NOT validate

- Bank-R starting/setup direct grants;
- any unclassified direct Bank-N grant path;
- the final custom-runtime Bank-N replacement itself.

Those remain requirements for the integrated build before 1.0.

## Install on official v0.8.3

1. Use the official v0.8.3 Ogre Battle 64 Recomp build.
2. Copy `universal-item-randomizer-stock-qa.nrm` into the `mods/` folder beside the executable.
3. Launch the port, open MODS and enable **Universal Item Randomizer - Stock Runtime QA**.
4. Start with seed `123456`, `RANDOMIZE SHOPS=OFF`, `KEY ITEMS=OFF`, `LOG=ON`.
5. Follow `TESTING.md` / `QA-CHECKLIST.md`, skipping tests explicitly marked as requiring the integrated Bank-N build.

Do not use this QA package as a release build. Its mod id is deliberately different from the final randomizer so both packages cannot be confused by the runtime config.
