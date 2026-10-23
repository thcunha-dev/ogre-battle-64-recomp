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
#define LIST_COUNT               3u
#define COUNT_MAX                99u

// Sources that feed both the popup/reward text and func_ovlN_801DC740.
#define DROP_TABLE               0x801EDB38u
#define DROP_ENTRY_STRIDE        8u
#define DROP_ENTRY_MAX           35u
#define DROP_ITEM_A              2u
#define DROP_TYPE_FIRST          0x0027u
#define DROP_TYPE_LAST           0x0050u
#define DROP_LAST_TYPE_ADDR      (DROP_TABLE + (DROP_ENTRY_MAX - 1u) * DROP_ENTRY_STRIDE)

#define PICKUP_COUNT             0x801F1002u
#define PICKUP_IDS               0x801F1004u
#define PICKUP_MAX               64u

#define REWARD_QUEUE             0x801936D8u
#define REWARD_SLOTS             20u

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

// Source shadows: a value written by this mod is not transformed again on the
// next frame. If the game reloads/changes a source slot, the new raw value differs
// from the shadow and is mapped once.
static unsigned short s_drop_written[DROP_ENTRY_MAX * 3u];
static unsigned char s_drop_valid[DROP_ENTRY_MAX * 3u];
static unsigned char s_drop_present;
static unsigned short s_pickup_written[PICKUP_MAX];
static unsigned char s_pickup_valid[PICKUP_MAX];
static unsigned short s_reward_written[REWARD_SLOTS];
static unsigned char s_reward_valid[REWARD_SLOTS];

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

// Sattolo makes one cycle: source != target for pools >1 and no two sources
// collide on the same replacement.
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
    build_cycle_map(s_equip_map, pool, count, 0x45515549u);
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
    build_cycle_map(s_consumable_map, safe_pool, safe_count, 0x434F4E53u);
    if (s_key_items_enabled) {
        build_cycle_map(s_consumable_map, key_pool, key_count, 0x4B455953u);
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
        return id <= EQUIP_ID_MAX ? s_equip_map[id] : (unsigned short)id;
    }
    return id <= CONSUMABLE_ID_MAX ? s_consumable_map[id] : (unsigned short)id;
}

static unsigned short mapped_item_word(unsigned short raw) {
    unsigned int list = (raw & 0x8000u) ? LIST_EQUIPMENT : LIST_CONSUMABLE;
    unsigned int id = raw & 0x7FFFu;
    return (unsigned short)((raw & 0x8000u) | mapped_id(list, id));
}

static int drop_table_present(void) {
    return rd16(DROP_TABLE) == DROP_TYPE_FIRST &&
           rd16(DROP_LAST_TYPE_ADDR) == DROP_TYPE_LAST;
}

static int drop_table_readable(void) {
    unsigned int column;
    for (column = 0u; column < 3u; column++) {
        unsigned int raw = rd16(DROP_TABLE + DROP_ITEM_A + column * 2u);
        unsigned int id = raw & 0x7FFFu;
        if ((raw & 0x8000u) != 0u) {
            if (id != 0u && id > EQUIP_ID_MAX) return 0;
        }
        else if (id != 0u && id > CONSUMABLE_ID_MAX) {
            return 0;
        }
    }
    return 1;
}

static void rewrite_drop_table(void) {
    unsigned int entry;
    unsigned int column;
    int present = drop_table_present() && drop_table_readable();

    if (!present) {
        if (s_drop_present) {
            for (entry = 0u; entry < DROP_ENTRY_MAX * 3u; entry++) {
                s_drop_valid[entry] = 0u;
            }
        }
        s_drop_present = 0u;
        return;
    }
    s_drop_present = 1u;

    for (entry = 0u; entry < DROP_ENTRY_MAX; entry++) {
        for (column = 0u; column < 3u; column++) {
            unsigned int index = entry * 3u + column;
            unsigned int addr = DROP_TABLE + entry * DROP_ENTRY_STRIDE + DROP_ITEM_A + column * 2u;
            unsigned short raw = rd16(addr);
            unsigned short replacement;

            if (s_drop_valid[index] && raw == s_drop_written[index]) {
                continue;
            }
            replacement = mapped_item_word(raw);
            if (replacement != raw) {
                wr16(addr, replacement);
                raw = replacement;
            }
            s_drop_written[index] = raw;
            s_drop_valid[index] = 1u;
        }
    }
}

static void rewrite_pickup_list(void) {
    unsigned int count;
    unsigned int i;

    if (!s_drop_present) {
        for (i = 0u; i < PICKUP_MAX; i++) s_pickup_valid[i] = 0u;
        return;
    }

    count = rd8(PICKUP_COUNT);
    if (count > PICKUP_MAX) {
        return;
    }
    for (i = 0u; i < PICKUP_MAX; i++) {
        if (i >= count) {
            s_pickup_valid[i] = 0u;
            continue;
        }
        {
            unsigned int addr = PICKUP_IDS + i * 2u;
            unsigned short raw = rd16(addr);
            unsigned short replacement;
            if (s_pickup_valid[i] && raw == s_pickup_written[i]) {
                continue;
            }
            replacement = mapped_item_word(raw);
            if (replacement != raw) {
                wr16(addr, replacement);
                raw = replacement;
            }
            s_pickup_written[i] = raw;
            s_pickup_valid[i] = 1u;
        }
    }
}

static void rewrite_reward_queue(void) {
    unsigned int i;
    for (i = 0u; i < REWARD_SLOTS; i++) {
        unsigned int addr = REWARD_QUEUE + i * 2u;
        unsigned short raw = rd16(addr);
        unsigned short replacement;

        if (raw == 0u) {
            s_reward_valid[i] = 0u;
            s_reward_written[i] = 0u;
            continue;
        }
        if (s_reward_valid[i] && raw == s_reward_written[i]) {
            continue;
        }
        replacement = mapped_item_word(raw);
        if (replacement != raw) {
            wr16(addr, replacement);
            raw = replacement;
        }
        s_reward_written[i] = raw;
        s_reward_valid[i] = 1u;
    }
}

// Original func_ovlN_801DC740 list semantics: increment an existing stack
// (maximum 99), otherwise claim the first empty record and set count=1. The
// original writes id/+0x03 only; +0x02 is intentionally left untouched.
static void grant_vanilla(unsigned int base, unsigned int slots, unsigned int id) {
    unsigned int empty = slots;
    unsigned int i;

    if (id == 0u) return;
    for (i = 0u; i < slots; i++) {
        unsigned int record = base + i * LIST_STRIDE;
        unsigned int slot_id = rd16(record);
        if (slot_id == id) {
            unsigned int count = rd8(record + LIST_COUNT);
            if (count < COUNT_MAX) wr8(record + LIST_COUNT, (unsigned char)(count + 1u));
            return;
        }
        if (slot_id == 0u && empty == slots) empty = i;
    }
    if (empty != slots) {
        unsigned int record = base + empty * LIST_STRIDE;
        wr16(record, (unsigned short)id);
        wr8(record + LIST_COUNT, 1u);
    }
}

static int caller_source_already_mapped(unsigned int caller_ra) {
    // These sources are rewritten before the game builds the message and calls
    // the grant, so the incoming item word is already the final replacement.
    return caller_ra == RA_MAP_OBJECT_A ||
           caller_ra == RA_MAP_OBJECT_B ||
           caller_ra == RA_GROUND_PICKUP ||
           caller_ra == RA_BATTLE_REWARD;
}

static int caller_is_setup_grant(unsigned int caller_ra) {
    return caller_ra >= RA_SETUP_R_LO && caller_ra < RA_SETUP_R_HI;
}

static int should_randomize_direct_grant(unsigned int caller_ra) {
    if (caller_source_already_mapped(caller_ra)) return 0;
    if (caller_ra == RA_MAP_OBJECT_B) return 0; // Table O source is already deterministically mapped
    if (caller_is_setup_grant(caller_ra)) return s_starting_items_enabled != 0u;
    // Unknown direct callers are preserved by default. SHOPS is an explicit
    // validation-mode opt-in until every direct caller has been classified.
    return s_shops_enabled != 0u;
}

RECOMP_PATCH
void func_ovlN_801DC740(unsigned int item_word, unsigned int ignored) {
    unsigned int caller_ra = (unsigned int)__builtin_return_address(0);
    unsigned short raw = (unsigned short)item_word;
    unsigned short delivered;
    unsigned int id;

    (void)ignored;
    randomizer_init();
    delivered = should_randomize_direct_grant(caller_ra) ? mapped_item_word(raw) : raw;
    id = delivered & 0x7FFFu;

    if ((delivered & 0x8000u) != 0u) {
        grant_vanilla(EQUIP_LIST, EQUIP_SLOTS, id);
    }
    else {
        grant_vanilla(CONSUMABLE_LIST, CONSUMABLE_SLOTS, id);
    }
}

// Frame hook only prepares deterministic source values before the game consumes
// them. It never scans or mutates the owned inventory, so save reconstruction
// cannot be mistaken for an acquisition.
RECOMP_HOOK("func_80072944")
void universal_item_randomizer_tick(void) {
    randomizer_init();
    rewrite_drop_table();
    rewrite_pickup_list();
    rewrite_reward_queue();
}
