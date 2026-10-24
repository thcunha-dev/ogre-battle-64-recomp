// Universal Item Randomizer - town shop stock source rewrite
//
// Bank AB builds a raw, zero-terminated u16 item_word list in a 0x200-byte heap
// buffer and stores its pointer at 0x80219F40. func_ovlAB_80214FA0 consumes that
// source to build the sorted equipment/consumable caches used by the list UI,
// detail panel, price calculation and purchase. Rewriting the raw source keeps
// all of those surfaces on the same replacement id.

#include "modding.h"
#include "randomizer_map.h"

RECOMP_IMPORT("*", unsigned int recomp_get_config_u32(const char* id));
RECOMP_IMPORT("*", void recomp_log(const char* message));

void universal_item_randomizer_use_repair_tick_impl(void);

#define RDRAM_LO                 0x80000000u
#define RDRAM_HI                 0x80800000u
#define BANK_AB_CODE             0x80214FA0u
#define SHOP_STOCK_PTR           0x80219F40u
#define SHOP_STOCK_BYTES         0x200u
#define SHOP_STOCK_MAX_WORDS     (SHOP_STOCK_BYTES / 2u)
#define EQUIP_TABLE              0x8018C42Cu
#define EQUIP_TABLE_STRIDE       0x20u
#define EQUIP_ID_MAX             277u
#define CONSUMABLE_TABLE         0x8018E6ECu
#define CONSUMABLE_TABLE_STRIDE  0x0Cu
#define CONSUMABLE_ID_MAX        40u

static const unsigned short k_shop_signature[] = { 1u, 2u, 3u, 4u, 5u, 6u, 8u };

static unsigned char s_config_ready;
static unsigned char s_shops_enabled;

static unsigned int rd32(unsigned int addr) { return *(volatile unsigned int*)addr; }
static unsigned short rd16(unsigned int addr) { return *(volatile unsigned short*)addr; }
static unsigned char rd8(unsigned int addr) { return *(volatile unsigned char*)addr; }
static void wr16(unsigned int addr, unsigned short value) { *(volatile unsigned short*)addr = value; }

static int bank_ab_present(void) {
    return rd32(BANK_AB_CODE + 0x00u) == 0x3C038022u &&
           rd32(BANK_AB_CODE + 0x04u) == 0x90639D44u &&
           rd32(BANK_AB_CODE + 0x08u) == 0x27BDFF90u &&
           rd32(BANK_AB_CODE + 0x0Cu) == 0xAFBF006Cu;
}

static int readable_string_pointer(unsigned int ptr) {
    return ptr >= RDRAM_LO && ptr < RDRAM_HI && rd8(ptr) != 0u;
}

static int equip_id_valid(unsigned int id) {
    unsigned int name;
    if (id < 1u || id > EQUIP_ID_MAX) return 0;
    name = rd32(EQUIP_TABLE + id * EQUIP_TABLE_STRIDE);
    return readable_string_pointer(name);
}

static int consumable_id_valid(unsigned int id) {
    unsigned int name;
    if (id < 1u || id > CONSUMABLE_ID_MAX) return 0;
    name = rd32(CONSUMABLE_TABLE + id * CONSUMABLE_TABLE_STRIDE);
    return readable_string_pointer(name);
}

static void init_config(void) {
    if (s_config_ready) return;
    s_shops_enabled = recomp_get_config_u32("shops") != 0u;
    s_config_ready = 1u;
}

static int stock_pointer_valid(unsigned int ptr) {
    if ((ptr & 1u) != 0u) return 0;
    if (ptr < RDRAM_LO) return 0;
    if (ptr > RDRAM_HI - SHOP_STOCK_BYTES) return 0;
    return 1;
}

static int stock_has_vanilla_signature(unsigned int ptr) {
    unsigned int i;
    for (i = 0u; i < sizeof(k_shop_signature) / sizeof(k_shop_signature[0]); i++) {
        if (rd16(ptr + i * 2u) != k_shop_signature[i]) return 0;
    }
    return 1;
}

static unsigned int validated_stock_count(unsigned int ptr) {
    unsigned int i;
    for (i = 0u; i < SHOP_STOCK_MAX_WORDS; i++) {
        unsigned int raw = rd16(ptr + i * 2u);
        unsigned int id;
        if (raw == 0u) return i;
        id = raw & 0x7FFFu;
        if ((raw & 0x8000u) != 0u) {
            if (!equip_id_valid(id)) return 0u;
        }
        else if (!consumable_id_valid(id)) {
            return 0u;
        }
    }
    return 0u;
}

static void rewrite_shop_stock(void) {
    unsigned int ptr;
    unsigned int count;
    unsigned int i;

    init_config();
    if (!s_shops_enabled || !bank_ab_present()) return;
    ptr = rd32(SHOP_STOCK_PTR);
    if (!stock_pointer_valid(ptr) || !stock_has_vanilla_signature(ptr)) return;
    count = validated_stock_count(ptr);
    if (count < sizeof(k_shop_signature) / sizeof(k_shop_signature[0])) return;

    uir_map_init();
    for (i = 0u; i < count; i++) {
        unsigned int addr = ptr + i * 2u;
        unsigned short raw = rd16(addr);
        unsigned short replacement = uir_map_item_word(raw);
        if (replacement != raw) wr16(addr, replacement);
    }

    if (recomp_get_config_u32("log") != 0u) {
        recomp_log("universal-item-randomizer: shop stock mapped");
    }
}

// One secondary frame hook handles both non-acquisition maintenance tasks.
// RecompModTool packages two hooks for func_80072944 reliably; keeping the shop
// and transient +0x02 repair behind this same record avoids the tool crash seen
// with three independent hook records while preserving their execution order.
RECOMP_HOOK("func_80072944")
void universal_item_randomizer_secondary_tick(void) {
    rewrite_shop_stock();
    universal_item_randomizer_use_repair_tick_impl();
}
