// Universal Item Randomizer - Ogre Battle 64: Recomp
//
// Deterministic, save-safe replacement randomizer. The mapping is rebuilt from
// external mod config every launch; no seed, flags or randomizer metadata are
// written into Ogre Battle 64's native save.

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

#define EQUIP_LIST               0x80196B20u
#define EQUIP_SLOTS              278u
#define CONSUMABLE_LIST          0x80193AE0u
#define CONSUMABLE_SLOTS         40u
#define LIST_STRIDE              4u
#define LIST_USED                2u
#define LIST_COUNT               3u
#define COUNT_MAX                99u

#define RDRAM_LO                 0x80000000u
#define RDRAM_HI                 0x80800000u

#define LIST_CONSUMABLE          0u
#define LIST_EQUIPMENT           1u

// Return addresses (jal address + 8) for the proven Bank-N grant callers.
#define RA_MAP_OBJECT_A          0x801ADEB0u
#define RA_MAP_OBJECT_B          0x801AE190u
#define RA_GROUND_PICKUP         0x801BB93Cu
#define RA_BATTLE_REWARD         0x801E53E4u

// Bank-R is the map/tutorial setup module. Its direct grant calls include the
// literal starter/tutorial batches and helper grants that establish the map's
// initial consumable state. Keep these vanilla unless STARTING ITEMS is enabled.
#define RA_SETUP_R_LO            0x80215000u
#define RA_SETUP_R_HI            0x80217300u

static unsigned short s_equip_map[EQUIP_ID_MAX + 1u];
static unsigned short s_consumable_map[CONSUMABLE_ID_MAX + 1u];
static unsigned int s_seed;
static unsigned char s_ready;
static unsigned char s_key_items_enabled;
static unsigned char s_starting_items_enabled;
static unsigned char s_shops_enabled;

static unsigned int rd32(unsigned int addr) {
    return *(volatile unsigned int*)addr;
}

static unsigned short rd16(unsigned int addr) {
    return *(volatile unsigned short*)addr;
}

static unsigned char rd8(unsigned int addr) {
    return *(volatile unsigned char*)addr;
}

static void wr16(unsigned int addr, unsigned short value) {
    *(volatile unsigned short*)addr = value;
}

static void wr8(unsigned int addr, unsigned char value) {
    *(volatile unsigned char*)addr = value;
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
        build_cycle_map(s_consumable_map, key_pool, key_count, 0x4B455953u); // "KEYS"
    }
}

static void randomizer_init(void) {
    if (s_ready) {
        return;
    }

    s_seed = recomp_get_config_u32("seed");
    if (s_seed == 0u) {
        s_seed = 1u;
    }
    s_key_items_enabled = recomp_get_config_u32("key_items") != 0u;
    s_starting_items_enabled = recomp_get_config_u32("starting_items") != 0u;
    s_shops_enabled = recomp_get_config_u32("shops") != 0u;

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

static unsigned short mapped_item_word(unsigned short raw) {
    unsigned int list = (raw & 0x8000u) ? LIST_EQUIPMENT : LIST_CONSUMABLE;
    unsigned int id = raw & 0x7FFFu;
    return (unsigned short)((raw & 0x8000u) | mapped_id(list, id));
}

// The original func_ovlN_801DC740 behavior for either inventory list: find the
// id and increment count (clamped at 99), otherwise claim the first empty slot
// and set count=1. The game's grant routine does not rewrite +0x02 (used count),
// so neither does this replacement.
static void grant_vanilla(unsigned int base, unsigned int slots, unsigned int id) {
    unsigned int empty = slots;
    unsigned int i;

    if (id == 0u) {
        return;
    }

    for (i = 0u; i < slots; i++) {
        unsigned int record = base + i * LIST_STRIDE;
        unsigned int slot_id = rd16(record);

        if (slot_id == id) {
            unsigned int count = rd8(record + LIST_COUNT);
            if (count < COUNT_MAX) {
                wr8(record + LIST_COUNT, (unsigned char)(count + 1u));
            }
            return;
        }
        if (slot_id == 0u && empty == slots) {
            empty = i;
        }
    }

    if (empty != slots) {
        unsigned int record = base + empty * LIST_STRIDE;
        wr16(record, (unsigned short)id);
        wr8(record + LIST_COUNT, 1u);
    }
}

static int caller_is_proven_gameplay_grant(unsigned int caller_ra) {
    return caller_ra == RA_MAP_OBJECT_A ||
           caller_ra == RA_MAP_OBJECT_B ||
           caller_ra == RA_GROUND_PICKUP ||
           caller_ra == RA_BATTLE_REWARD;
}

static int caller_is_setup_grant(unsigned int caller_ra) {
    return caller_ra >= RA_SETUP_R_LO && caller_ra < RA_SETUP_R_HI;
}

static int should_randomize_grant(unsigned int caller_ra) {
    if (caller_is_proven_gameplay_grant(caller_ra)) {
        return 1;
    }
    if (caller_is_setup_grant(caller_ra)) {
        return s_starting_items_enabled != 0u;
    }

    // Unknown direct callers include paths still being classified (shops and
    // scripted gifts). Keep them vanilla by default; SHOPS is the explicit
    // opt-in for broad direct-grant randomization during this validation phase.
    return s_shops_enabled != 0u;
}

// Bank-N universal grant replacement. __builtin_return_address(0) is captured
// before helpers are called, so on MIPS it identifies the game's jal caller.
// Save loading reconstructs the inventory from packed save data and does not
// call this grant routine, so existing inventory is never re-randomized.
RECOMP_PATCH
void func_ovlN_801DC740(unsigned int item_word, unsigned int ignored) {
    unsigned int caller_ra = (unsigned int)__builtin_return_address(0);
    unsigned short raw = (unsigned short)item_word;
    unsigned short delivered;
    unsigned int id;

    (void)ignored;
    randomizer_init();

    delivered = should_randomize_grant(caller_ra) ? mapped_item_word(raw) : raw;
    id = delivered & 0x7FFFu;

    if ((delivered & 0x8000u) != 0u) {
        grant_vanilla(EQUIP_LIST, EQUIP_SLOTS, id);
    }
    else {
        grant_vanilla(CONSUMABLE_LIST, CONSUMABLE_SLOTS, id);
    }
}

// Bootstrap the deterministic maps early so the first acquisition does not pay
// all table-validation/shuffle work in the middle of a reward or pickup path.
RECOMP_HOOK("func_80072944")
void universal_item_randomizer_tick(void) {
    randomizer_init();
}
