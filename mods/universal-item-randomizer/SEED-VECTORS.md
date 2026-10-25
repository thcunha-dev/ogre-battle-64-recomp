# Universal Item Randomizer 0.3.1 — golden seed vectors

These vectors are part of the public deterministic-seed contract. They are
validated by `tools/test_randomizer_golden_vectors.py` and should not change
unless seed compatibility is intentionally versioned/broken.

## QA seed 123456 — equipment

The Rev-A equipment pool is the audited legitimate id range `1..277`. For seed
`123456`, selected exact replacements are:

| original equipment id | replacement id |
|---:|---:|
| 1 | 270 |
| 2 | 239 |
| 3 | 37 |
| 4 | 115 |
| 5 | 112 |
| 6 | 125 |
| 7 | 40 |
| 8 | 186 |
| 10 | 60 |
| 20 | 138 |
| 50 | 146 |
| 100 | 189 |
| 150 | 243 |
| 200 | 223 |
| 250 | 259 |
| 277 | 245 |

Equipment `item_word` values keep bit15. Example: raw equipment word `0x8001`
must therefore become `0x810E` because replacement id 270 is `0x010E`.

## Secondary fixture — seed 12345

A smaller independent fixture prevents the test from accidentally hard-coding a
single seed:

| original equipment id | replacement id |
|---:|---:|
| 1 | 95 |
| 2 | 30 |
| 3 | 179 |
| 100 | 185 |
| 200 | 162 |
| 277 | 253 |

## How to use during in-game QA

1. Set `SEED = 123456`.
2. Identify an acquisition whose original equipment id is in the first table.
3. Acquire it through any covered route.
4. The displayed/purchased/granted replacement must equal the table.
5. Acquire the same original id through a second covered route when possible;
   it must produce the same replacement.
6. Save, close, reopen: the already-owned replacement id must remain unchanged.

Consumables are deliberately not hard-coded in this document because their
permutation is split by audited runtime class (ordinary vs key/quest) rather than
one sequential `1..40` pool. Their deterministic behavior remains covered by the
shared mapper/invariant and persistence tests.
