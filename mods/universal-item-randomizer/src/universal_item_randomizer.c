// Universal Item Randomizer - Ogre Battle 64: Recomp
//
// Deterministic, save-safe replacement randomizer. The mapping is rebuilt from
// external mod config every launch; no seed, flags or randomizer metadata are
// written into Ogre Battle 64's native save.

#include "modding.h"
#include "randomizer_map.h"

RECOMP_IMPORT("*", unsigned int recomp_get_config_u32(const char* id));
RECOMP_IMPORT("*", void recomp_log(const char* message));

#define EQUIP_ID_MAX             277u
#define CONSUMABLE_ID_MAX        40u

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

static unsigned char s_ready;
static unsigned char s_starting_items_enabled;

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

static void randomizer_init(void) {
    if (s_ready) return;
    s_starting_items_enabled = recomp_get_config_u32("starting_items") != 0u;
    uir_map_init();
    s_ready = 1u;
    if (recomp_get_config_u32("log") != 0u) {
        recomp_log("universal-item-randomizer: deterministic mapping ready");
    }
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

            if (s_drop_valid[index] && raw == s_drop_written[index]) continue;
            replacement = uir_map_item_word(raw);
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
    if (count > PICKUP_MAX) return;

    for (i = 0u; i < PICKUP_MAX; i++) {
        if (i >= count) {
            s_pickup_valid[i] = 0u;
            continue;
        }
        {
            unsigned int addr = PICKUP_IDS + i * 2u;
            unsigned short raw = rd16(addr);
            unsigned short replacement;
            if (s_pickup_valid[i] && raw == s_pickup_written[i]) continue;
            replacement = uir_map_item_word(raw);
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
        if (s_reward_valid[i] && raw == s_reward_written[i]) continue;
        replacement = uir_map_item_word(raw);
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
    if (caller_is_setup_grant(caller_ra)) return s_starting_items_enabled != 0u;
    // Unknown direct callers stay vanilla. Shops have their own Bank-AB source
    // rewrite, so no config switch is allowed to turn an unclassified grant
    // into a randomized one accidentally.
    return 0;
}

RECOMP_PATCH
void func_ovlN_801DC740(unsigned int item_word, unsigned int ignored) {
    unsigned int caller_ra = (unsigned int)__builtin_return_address(0);
    unsigned short raw = (unsigned short)item_word;
    unsigned short delivered;
    unsigned int id;

    (void)ignored;
    randomizer_init();
    delivered = should_randomize_direct_grant(caller_ra) ? uir_map_item_word(raw) : raw;
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
