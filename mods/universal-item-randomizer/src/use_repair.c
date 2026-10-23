// Universal Item Randomizer - transient +0x02 repair
//
// Ogre Battle 64 does not save the +0x02 "in use" byte of either owned-item
// list. It is rebuilt from the roster by func_8016B774. The universal grant
// replacement intentionally writes only the fields the original grant writes
// (id/count), so a newly occupied record can inherit stale +0x02 data from an
// old empty slot. This repair changes only that transient byte; it never changes
// item ids, counts, seed state or the native save representation.

#include "modding.h"

#define EQUIP_LIST               0x80196B20u
#define EQUIP_SLOTS              278u
#define CONSUMABLE_LIST          0x80193AE0u
#define CONSUMABLE_SLOTS         40u
#define CONSUMABLE_ID_MAX        40u
#define LIST_STRIDE              4u
#define LIST_USE                 2u

#define ROSTER_UNITS             0x80197210u
#define ROSTER_UNIT_STRIDE       0x19u
#define ROSTER_UNIT_COUNT        30u
#define ROSTER_UNIT_GATE         0x01u
#define ROSTER_UNIT_IDS          0x0Du
#define ROSTER_UNIT_ID_COUNT     10u

#define ROSTER_CHARS             0x80193BE0u
#define ROSTER_CHAR_STRIDE       0x38u
#define ROSTER_CHAR_COUNT        100u
#define ROSTER_CHAR_GATE         0x11u
#define ROSTER_CHAR_CLASS        0x12u
#define ROSTER_CHAR_IDS          0x2Au

#define ROSTER_CLASS_TABLE       0x80187C62u
#define ROSTER_CLASS_STRIDE      0x48u
#define ROSTER_CLASS_KEY         0x17u

static unsigned short s_equip_refs[EQUIP_SLOTS];
// Consumable ids are 1..40 while the owned list has 40 records. This table is
// indexed by item id, not by owned-list slot, so it needs entries 0..40.
static unsigned short s_consumable_refs[CONSUMABLE_ID_MAX + 1u];
static unsigned short s_equip_shadow[EQUIP_SLOTS];
static unsigned short s_consumable_shadow[CONSUMABLE_SLOTS];
static unsigned char s_shadow_ready;

static unsigned short rd16(unsigned int addr) {
    return *(volatile unsigned short*)addr;
}

static unsigned char rd8(unsigned int addr) {
    return *(volatile unsigned char*)addr;
}

static void wr8(unsigned int addr, unsigned char value) {
    *(volatile unsigned char*)addr = value;
}

static unsigned int class_equipment_id(unsigned int class_index,
                                       unsigned int cls,
                                       unsigned int slot) {
    unsigned int table = ROSTER_CLASS_TABLE + class_index * ROSTER_CLASS_STRIDE;
    unsigned int entry = table;

    if (rd8(table + ROSTER_CLASS_KEY) != (cls & 0xFFu)) {
        entry = ROSTER_CLASS_TABLE + cls * ROSTER_CLASS_STRIDE;
    }
    return rd16(entry + slot * 2u) & 0xFFFFu;
}

static void add_ref(unsigned int list, unsigned int id) {
    if (id == 0u) return;
    if (list == 0u) {
        if (id < EQUIP_SLOTS && s_equip_refs[id] != 0xFFFFu) s_equip_refs[id]++;
    }
    else {
        if (id <= CONSUMABLE_ID_MAX && s_consumable_refs[id] != 0xFFFFu) s_consumable_refs[id]++;
    }
}

static unsigned int roster_chars(void) {
    unsigned int i;
    unsigned int count = 0u;
    for (i = 0u; i < ROSTER_CHAR_COUNT; i++) {
        if (rd8(ROSTER_CHARS + i * ROSTER_CHAR_STRIDE + ROSTER_CHAR_GATE) != 0u) count++;
    }
    return count;
}

static unsigned int roster_units(void) {
    unsigned int i;
    unsigned int count = 0u;
    for (i = 0u; i < ROSTER_UNIT_COUNT; i++) {
        if ((rd8(ROSTER_UNITS + i * ROSTER_UNIT_STRIDE + ROSTER_UNIT_GATE) & 1u) != 0u) count++;
    }
    return count;
}

static int roster_populated(void) {
    return roster_chars() != 0u && roster_units() != 0u;
}

static void build_refs(void) {
    unsigned int i;

    for (i = 0u; i < EQUIP_SLOTS; i++) s_equip_refs[i] = 0u;
    for (i = 0u; i <= CONSUMABLE_ID_MAX; i++) s_consumable_refs[i] = 0u;

    for (i = 0u; i < ROSTER_UNIT_COUNT; i++) {
        unsigned int base = ROSTER_UNITS + i * ROSTER_UNIT_STRIDE;
        unsigned int j;
        if ((rd8(base + ROSTER_UNIT_GATE) & 1u) == 0u) continue;
        for (j = 0u; j < ROSTER_UNIT_ID_COUNT; j++) {
            add_ref(1u, rd8(base + ROSTER_UNIT_IDS + j));
        }
    }

    for (i = 0u; i < ROSTER_CHAR_COUNT; i++) {
        unsigned int base = ROSTER_CHARS + i * ROSTER_CHAR_STRIDE;
        unsigned int cls;
        unsigned int j;
        if (rd8(base + ROSTER_CHAR_GATE) == 0u) continue;
        cls = rd8(base + ROSTER_CHAR_CLASS);
        for (j = 0u; j < 4u; j++) {
            add_ref(0u, rd16(base + ROSTER_CHAR_IDS + j * 2u));
        }
        for (j = 0u; j < 4u; j++) {
            add_ref(0u, class_equipment_id(j, cls, j));
        }
    }
}

static unsigned char clamp_use(unsigned int value) {
    return (unsigned char)(value > 255u ? 255u : value);
}

static void full_repair_and_snapshot(void) {
    unsigned int i;
    build_refs();

    for (i = 0u; i < EQUIP_SLOTS; i++) {
        unsigned int record = EQUIP_LIST + i * LIST_STRIDE;
        unsigned int id = rd16(record);
        s_equip_shadow[i] = (unsigned short)id;
        wr8(record + LIST_USE,
            (unsigned char)((id != 0u && id < EQUIP_SLOTS) ? clamp_use(s_equip_refs[id]) : 0u));
    }
    for (i = 0u; i < CONSUMABLE_SLOTS; i++) {
        unsigned int record = CONSUMABLE_LIST + i * LIST_STRIDE;
        unsigned int id = rd16(record);
        s_consumable_shadow[i] = (unsigned short)id;
        wr8(record + LIST_USE,
            (unsigned char)((id != 0u && id <= CONSUMABLE_ID_MAX) ? clamp_use(s_consumable_refs[id]) : 0u));
    }
    s_shadow_ready = 1u;
}

static int ids_changed(void) {
    unsigned int i;
    for (i = 0u; i < EQUIP_SLOTS; i++) {
        if (rd16(EQUIP_LIST + i * LIST_STRIDE) != s_equip_shadow[i]) return 1;
    }
    for (i = 0u; i < CONSUMABLE_SLOTS; i++) {
        if (rd16(CONSUMABLE_LIST + i * LIST_STRIDE) != s_consumable_shadow[i]) return 1;
    }
    return 0;
}

// The native func_80172820 add-count path invokes the game's complete
// func_8016B774 rebuild after it changes inventory. Its replacement cannot jal
// that base guest helper directly, so it calls this mod-local equivalent. Keep
// this forced form separate from the cheap frame tick: a count-only add may not
// change any id, but the native routine still performs the rebuild immediately.
void universal_item_randomizer_force_use_repair(void) {
    if (!roster_populated()) {
        s_shadow_ready = 0u;
        return;
    }
    full_repair_and_snapshot();
}

// Called by the combined secondary frame hook in shop_stock.c. This function
// is intentionally a normal mod-local call rather than a third RECOMP_HOOK
// record: RecompModTool currently becomes unstable with three hook records for
// the same guest function. No acquisition is inferred here.
void universal_item_randomizer_use_repair_tick_impl(void) {
    if (!roster_populated()) {
        s_shadow_ready = 0u;
        return;
    }
    if (!s_shadow_ready || ids_changed()) {
        full_repair_and_snapshot();
    }
}
