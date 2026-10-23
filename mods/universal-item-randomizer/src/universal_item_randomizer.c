// Universal Item Randomizer - Ogre Battle 64: Recomp
//
// Phase 1 of the replacement randomizer: build a deterministic, one-to-one
// mapping from the mod's external SEED. No mapping state is written to the
// game's save. The frame hook only initializes the mapping; acquisition hooks
// are added after bank-function replacements are visible to code mods.

#include "modding.h"

RECOMP_IMPORT("*", unsigned int recomp_get_config_u32(const char* id));
RECOMP_IMPORT("*", void recomp_log(const char* message));

#define EQUIP_TABLE              0x8018C42Cu
#define EQUIP_TABLE_STRIDE       0x20u
#define EQUIP_TABLE_NAME         0x00u
#define EQUIP_ID_MAX             277u

#define CONSUMABLE_TABLE         0x8018E6ECu
#define CONSUMABLE_TABLE_STRIDE  0x0Cu
#define CONSUMABLE_TABLE_NAME    0x00u
#define CONSUMABLE_TABLE_CLASS   0x04u
#define CONSUMABLE_ID_MAX        40u
#define CONSUMABLE_SAFE_MAX      2u
#define CONSUMABLE_KEY_MIN       3u

#define RDRAM_LO                 0x80000000u
#define RDRAM_HI                 0x80800000u

#define LIST_CONSUMABLE          0u
#define LIST_EQUIPMENT           1u

static unsigned short s_equip_map[EQUIP_ID_MAX + 1u];
static unsigned short s_consumable_map[CONSUMABLE_ID_MAX + 1u];
static unsigned int s_seed;
static unsigned char s_ready;
static unsigned char s_key_items_enabled;

static unsigned int rd32(unsigned int addr) {
    return *(volatile unsigned int*)addr;
}

static unsigned char rd8(unsigned int addr) {
    return *(volatile unsigned char*)addr;
}

static int readable_string_pointer(unsigned int ptr) {
    return ptr >= RDRAM_LO && ptr < RDRAM_HI && rd8(ptr) != 0u;
}

static int equip_id_valid(unsigned int id) {
    unsigned int name;
    if (id < 1u || id > EQUIP_ID_MAX) {
        return 0;
    }
    name = rd32(EQUIP_TABLE + id * EQUIP_TABLE_STRIDE + EQUIP_TABLE_NAME);
    return readable_string_pointer(name);
}

static unsigned int consumable_class(unsigned int id) {
    return rd8(CONSUMABLE_TABLE + id * CONSUMABLE_TABLE_STRIDE + CONSUMABLE_TABLE_CLASS);
}

static int consumable_id_valid(unsigned int id) {
    unsigned int name;
    if (id < 1u || id > CONSUMABLE_ID_MAX) {
        return 0;
    }
    name = rd32(CONSUMABLE_TABLE + id * CONSUMABLE_TABLE_STRIDE + CONSUMABLE_TABLE_NAME);
    return readable_string_pointer(name);
}

// Small deterministic PRNG used only while building the permutation. Mapping
// lookup itself consumes no RNG, so acquisition order cannot change results.
static unsigned int mix32(unsigned int x) {
    x ^= x >> 16;
    x *= 0x7FEB352Du;
    x ^= x >> 15;
    x *= 0x846CA68Bu;
    x ^= x >> 16;
    return x;
}

static unsigned int rng_next(unsigned int* state) {
    unsigned int x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

// Sattolo's algorithm makes one cycle instead of an arbitrary permutation.
// For a pool with >1 entry this guarantees source != replacement for every
// item, while still remaining one-to-one (no A->X and B->X collisions).
static void build_cycle_map(unsigned short* map,
                            const unsigned short* sources,
                            unsigned int count,
                            unsigned int salt) {
    unsigned short targets[EQUIP_ID_MAX];
    unsigned int state;
    unsigned int i;

    if (count == 0u) {
        return;
    }
    for (i = 0u; i < count; i++) {
        targets[i] = sources[i];
    }
    if (count > 1u) {
        state = mix32(s_seed ^ salt ^ (count * 0x9E3779B9u));
        if (state == 0u) {
            state = 0xA341316Cu;
        }
        for (i = count - 1u; i > 0u; i--) {
            // Sattolo: j is [0, i-1], deliberately excluding i.
            unsigned int j = rng_next(&state) % i;
            unsigned short tmp = targets[i];
            targets[i] = targets[j];
            targets[j] = tmp;
        }
    }
    for (i = 0u; i < count; i++) {
        map[sources[i]] = targets[i];
    }
}

static void build_equipment_map(void) {
    unsigned short pool[EQUIP_ID_MAX];
    unsigned int count = 0u;
    unsigned int id;

    for (id = 0u; id <= EQUIP_ID_MAX; id++) {
        s_equip_map[id] = (unsigned short)id;
    }
    for (id = 1u; id <= EQUIP_ID_MAX; id++) {
        if (equip_id_valid(id)) {
            pool[count++] = (unsigned short)id;
        }
    }
    build_cycle_map(s_equip_map, pool, count, 0x45515549u); // "EQUI"
}

static void build_consumable_map(void) {
    unsigned short safe_pool[CONSUMABLE_ID_MAX];
    unsigned short key_pool[CONSUMABLE_ID_MAX];
    unsigned int safe_count = 0u;
    unsigned int key_count = 0u;
    unsigned int id;

    for (id = 0u; id <= CONSUMABLE_ID_MAX; id++) {
        s_consumable_map[id] = (unsigned short)id;
    }

    for (id = 1u; id <= CONSUMABLE_ID_MAX; id++) {
        unsigned int cls;
        if (!consumable_id_valid(id)) {
            continue;
        }
        cls = consumable_class(id);
        if (cls <= CONSUMABLE_SAFE_MAX) {
            safe_pool[safe_count++] = (unsigned short)id;
        }
        else if (cls >= CONSUMABLE_KEY_MIN) {
            key_pool[key_count++] = (unsigned short)id;
        }
    }

    build_cycle_map(s_consumable_map, safe_pool, safe_count, 0x434F4E53u); // "CONS"
    if (s_key_items_enabled) {
        // Even when explicitly enabled, quest/key items remain inside their own
        // pool; they can never turn into a normal heal/use item or equipment.
        build_cycle_map(s_consumable_map, key_pool, key_count, 0x4B455953u); // "KEYS"
    }
}

static void randomizer_init(void) {
    if (s_ready) {
        return;
    }

    s_seed = recomp_get_config_u32("seed");
    if (s_seed == 0u) {
        // Zero is deliberately deterministic too. Never derive a seed from a
        // frame counter: a restart with the same config must rebuild the same
        // mapping without storing anything in the native save.
        s_seed = 1u;
    }
    s_key_items_enabled = recomp_get_config_u32("key_items") != 0u;

    build_equipment_map();
    build_consumable_map();
    s_ready = 1u;

    if (recomp_get_config_u32("log") != 0u) {
        recomp_log("universal-item-randomizer: deterministic mapping ready");
    }
}

static unsigned short mapped_id(unsigned int list, unsigned int id) {
    randomizer_init();
    if (list == LIST_EQUIPMENT) {
        if (id <= EQUIP_ID_MAX) {
            return s_equip_map[id];
        }
    }
    else if (id <= CONSUMABLE_ID_MAX) {
        return s_consumable_map[id];
    }
    return (unsigned short)id;
}

// Preserve bit 15 exactly. This is the word the game's grant routine consumes.
static unsigned short mapped_item_word(unsigned short raw) {
    unsigned int list = (raw & 0x8000u) ? LIST_EQUIPMENT : LIST_CONSUMABLE;
    unsigned int id = raw & 0x7FFFu;
    return (unsigned short)((raw & 0x8000u) | mapped_id(list, id));
}

// Safe bootstrap hook: initialize only. It intentionally does not touch the
// inventory or randomize acquisitions. This gives the first build a way to
// validate config/table access before the Bank-N grant replacement is enabled.
RECOMP_HOOK("func_80072944")
void universal_item_randomizer_tick(void) {
    randomizer_init();
}

// Keep these helpers alive in the mod ELF before the grant replacement starts
// using them; volatile sinks prevent -O2 from discarding the mapping lookup.
static volatile unsigned short s_linker_keep;
RECOMP_HOOK_RETURN("func_80072944")
void universal_item_randomizer_keep(void) {
    if (s_ready) {
        s_linker_keep = mapped_item_word(0u);
    }
}
