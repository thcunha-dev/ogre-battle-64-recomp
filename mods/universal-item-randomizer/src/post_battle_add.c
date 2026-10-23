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
#define LIST_COUNT               3u
#define COUNT_MAX                99u

void universal_item_randomizer_force_use_repair(void);
void universal_item_randomizer_log_post_battle(void);

static unsigned short rd16(unsigned int addr) { return *(volatile unsigned short*)addr; }
static unsigned char rd8(unsigned int addr) { return *(volatile unsigned char*)addr; }
static void wr16(unsigned int addr, unsigned short v) { *(volatile unsigned short*)addr = v; }
static void wr8(unsigned int addr, unsigned char v) { *(volatile unsigned char*)addr = v; }

static unsigned char saturated_count(unsigned int current, unsigned int amount) {
    // Both inputs originate from <=16-bit guest values, so addition is safe in
    // host unsigned int. Clamp before narrowing to u8: never wrap through 0xFF.
    unsigned int total = current + amount;
    return (unsigned char)(total > COUNT_MAX ? COUNT_MAX : total);
}

RECOMP_PATCH
void func_80172820(unsigned int original_id, unsigned int amount) {
    unsigned int id;
    unsigned int empty = EQUIP_SLOTS;
    unsigned int i;

    original_id &= 0xFFFFu;
    amount &= 0xFFFFu;
    if (original_id == 0u || amount == 0u) return;
    id = uir_map_equipment_id(original_id);
    universal_item_randomizer_log_post_battle();

    for (i = 0u; i < EQUIP_SLOTS; i++) {
        unsigned int record = EQUIP_LIST + i * LIST_STRIDE;
        unsigned int slot_id = rd16(record);
        if (slot_id == id) {
            unsigned int count = rd8(record + LIST_COUNT);
            wr8(record + LIST_COUNT, saturated_count(count, amount));
            universal_item_randomizer_force_use_repair();
            return;
        }
        if (slot_id == 0u && empty == EQUIP_SLOTS) empty = i;
    }

    if (empty != EQUIP_SLOTS) {
        unsigned int record = EQUIP_LIST + empty * LIST_STRIDE;
        wr16(record, (unsigned short)id);
        wr8(record + LIST_COUNT, saturated_count(0u, amount));
    }

    // Native func_80172820 calls the full +0x02 rebuild after the add, not just
    // the equipment half. Reproduce that behavior so both owned lists and the
    // repair shadows are coherent before the caller observes them.
    universal_item_randomizer_force_use_repair();
}
