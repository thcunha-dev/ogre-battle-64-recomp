// Universal Item Randomizer - secondary post-battle equipment add path
//
// func_80172820(id,count) is separate from the Bank-N grant routine. Reverse
// engineering found exactly one jal in the game: Bank-L func_ovlL_80235334,
// which feeds it u16 ids and u16 counts from a 14-entry post-battle table.
// Randomize that real acquisition path without touching load reconstruction.

#include "modding.h"
#include "randomizer_map.h"

#define EQUIP_LIST               0x80196B20u
#define EQUIP_SLOTS              278u
#define LIST_STRIDE              4u
#define LIST_USE                 2u
#define LIST_COUNT               3u
#define COUNT_MAX                99u

#define ROSTER_CHARS             0x80193BE0u
#define ROSTER_CHAR_STRIDE       0x38u
#define ROSTER_CHAR_COUNT        100u
#define ROSTER_CHAR_GATE         0x11u
#define ROSTER_CHAR_CLASS        0x12u
#define ROSTER_CHAR_IDS          0x2Au
#define ROSTER_CLASS_TABLE       0x80187C62u
#define ROSTER_CLASS_STRIDE      0x48u
#define ROSTER_CLASS_KEY         0x17u

static unsigned short rd16(unsigned int addr) { return *(volatile unsigned short*)addr; }
static unsigned char rd8(unsigned int addr) { return *(volatile unsigned char*)addr; }
static void wr16(unsigned int addr, unsigned short v) { *(volatile unsigned short*)addr = v; }
static void wr8(unsigned int addr, unsigned char v) { *(volatile unsigned char*)addr = v; }

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

// func_80172820 calls the game's full +0x02 rebuild after changing a count.
// Recreate the equipment half immediately so callers in the same frame observe
// the same invariant even though the mod cannot jal directly to func_8016B774.
static void rebuild_equipment_use(void) {
    unsigned short refs[EQUIP_SLOTS];
    unsigned int i;

    for (i = 0u; i < EQUIP_SLOTS; i++) refs[i] = 0u;
    for (i = 0u; i < ROSTER_CHAR_COUNT; i++) {
        unsigned int base = ROSTER_CHARS + i * ROSTER_CHAR_STRIDE;
        unsigned int cls;
        unsigned int j;
        if (rd8(base + ROSTER_CHAR_GATE) == 0u) continue;
        cls = rd8(base + ROSTER_CHAR_CLASS);
        for (j = 0u; j < 4u; j++) {
            unsigned int id = rd16(base + ROSTER_CHAR_IDS + j * 2u);
            if (id != 0u && id < EQUIP_SLOTS && refs[id] != 0xFFFFu) refs[id]++;
        }
        for (j = 0u; j < 4u; j++) {
            unsigned int id = class_equipment_id(j, cls, j);
            if (id != 0u && id < EQUIP_SLOTS && refs[id] != 0xFFFFu) refs[id]++;
        }
    }
    for (i = 0u; i < EQUIP_SLOTS; i++) {
        unsigned int record = EQUIP_LIST + i * LIST_STRIDE;
        unsigned int id = rd16(record);
        unsigned int use = (id != 0u && id < EQUIP_SLOTS) ? refs[id] : 0u;
        wr8(record + LIST_USE, (unsigned char)(use > 255u ? 255u : use));
    }
}

RECOMP_PATCH
void func_80172820(unsigned int original_id, unsigned int amount) {
    unsigned int id;
    unsigned int empty = EQUIP_SLOTS;
    unsigned int i;

    original_id &= 0xFFFFu;
    amount &= 0xFFFFu;
    if (original_id == 0u) return;
    id = uir_map_equipment_id(original_id);

    for (i = 0u; i < EQUIP_SLOTS; i++) {
        unsigned int record = EQUIP_LIST + i * LIST_STRIDE;
        unsigned int slot_id = rd16(record);
        if (slot_id == id) {
            unsigned int count = rd8(record + LIST_COUNT);
            unsigned int next = (count + amount) & 0xFFu;
            if (next >= 100u) next = COUNT_MAX;
            wr8(record + LIST_COUNT, (unsigned char)next);
            rebuild_equipment_use();
            return;
        }
        if (slot_id == 0u && empty == EQUIP_SLOTS) empty = i;
    }

    if (empty != EQUIP_SLOTS) {
        unsigned int record = EQUIP_LIST + empty * LIST_STRIDE;
        unsigned int count = amount & 0xFFu;
        wr16(record, (unsigned short)id);
        wr8(record + LIST_COUNT, (unsigned char)count);
    }
    rebuild_equipment_use();
}
