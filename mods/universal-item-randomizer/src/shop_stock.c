// Universal Item Randomizer - town shop stock source rewrite
//
// Bank AB builds a raw, zero-terminated u16 item_word list in a 0x200-byte heap
// buffer and stores its pointer at 0x80219F40. func_ovlAB_80214FA0 consumes that
// source to build the sorted equipment/consumable caches used by the list UI,
// detail panel, price calculation and purchase. Rewriting the raw source keeps
// all of those surfaces on the same replacement id.
//
// func_ovlAB_80219600 always seeds the raw list with consumables
// 1,2,3,4,5,6,8 before appending equipment words with bit15 set. Requiring that
// exact signature prevents us from treating a stale/reused heap pointer as a
// newly constructed shop list. After one deterministic rewrite the signature no
// longer matches, so the same shop is not rerolled every frame. Reopening a shop
// reconstructs the vanilla signature and is mapped again to the same ids.

#include "modding.h"

RECOMP_IMPORT("*", unsigned int recomp_get_config_u32(const char* id));
RECOMP_IMPORT("*", void recomp_log(const char* message));

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
#define CONSUMABLE_TABLE_CLASS   0x04u
#define CONSUMABLE_ID_MAX        40u
#define CONSUMABLE_SAFE_MAX      2u
#define CONSUMABLE_KEY_MIN       3u

static const unsigned short k_shop_signature[] = { 1u, 2u, 3u, 4u, 5u, 6u, 8u };

static unsigned short s_equip_map[EQUIP_ID_MAX + 1u];
static unsigned short s_consumable_map[CONSUMABLE_ID_MAX + 1u];
static unsigned int s_seed;
static unsigned char s_ready;
static unsigned char s_key_items_enabled;
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

// Record-9 banks all share RAM 0x80214FA0. Before touching Bank-AB state, prove
// that the shop module is actually resident. These first four Rev-A words are
// unique in the complete 40 MiB cart (ROM 0x1977B0) and cover both the Bank-AB
// state load and the function prologue.
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

static unsigned int consumable_class(unsigned int id) {
    return rd8(CONSUMABLE_TABLE + id * CONSUMABLE_TABLE_STRIDE + CONSUMABLE_TABLE_CLASS);
}

static int consumable_id_valid(unsigned int id) {
    unsigned int name;
    if (id < 1u || id > CONSUMABLE_ID_MAX) return 0;
    name = rd32(CONSUMABLE_TABLE + id * CONSUMABLE_TABLE_STRIDE);
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

static void build_cycle_map(unsigned short* map,
                            const unsigned short* sources,
                            unsigned int count,
                            unsigned int salt) {
    unsigned short targets[EQUIP_ID_MAX];
    unsigned int state;
    unsigned int i;

    if (count == 0u) return;
    for (i = 0u; i < count; i++) targets[i] = sources[i];
    if (count > 1u) {
        state = mix32(s_seed ^ salt ^ (count * 0x9E3779B9u));
        if (state == 0u) state = 0xA341316Cu;
        for (i = count - 1u; i > 0u; i--) {
            unsigned int j = rng_next(&state) % i;
            unsigned short tmp = targets[i];
            targets[i] = targets[j];
            targets[j] = tmp;
        }
    }
    for (i = 0u; i < count; i++) map[sources[i]] = targets[i];
}

static void init_maps(void) {
    unsigned short equip_pool[EQUIP_ID_MAX];
    unsigned short safe_pool[CONSUMABLE_ID_MAX];
    unsigned short key_pool[CONSUMABLE_ID_MAX];
    unsigned int equip_count = 0u;
    unsigned int safe_count = 0u;
    unsigned int key_count = 0u;
    unsigned int id;

    if (s_ready) return;
    s_seed = recomp_get_config_u32("seed");
    if (s_seed == 0u) s_seed = 1u;
    s_key_items_enabled = recomp_get_config_u32("key_items") != 0u;
    s_shops_enabled = recomp_get_config_u32("shops") != 0u;

    for (id = 0u; id <= EQUIP_ID_MAX; id++) s_equip_map[id] = (unsigned short)id;
    for (id = 0u; id <= CONSUMABLE_ID_MAX; id++) s_consumable_map[id] = (unsigned short)id;

    for (id = 1u; id <= EQUIP_ID_MAX; id++) {
        if (equip_id_valid(id)) equip_pool[equip_count++] = (unsigned short)id;
    }
    for (id = 1u; id <= CONSUMABLE_ID_MAX; id++) {
        unsigned int cls;
        if (!consumable_id_valid(id)) continue;
        cls = consumable_class(id);
        if (cls <= CONSUMABLE_SAFE_MAX) safe_pool[safe_count++] = (unsigned short)id;
        else if (cls >= CONSUMABLE_KEY_MIN) key_pool[key_count++] = (unsigned short)id;
    }

    build_cycle_map(s_equip_map, equip_pool, equip_count, 0x45515549u);
    build_cycle_map(s_consumable_map, safe_pool, safe_count, 0x434F4E53u);
    if (s_key_items_enabled) {
        build_cycle_map(s_consumable_map, key_pool, key_count, 0x4B455953u);
    }
    s_ready = 1u;
}

static unsigned short mapped_item_word(unsigned short raw) {
    unsigned int id = raw & 0x7FFFu;
    if ((raw & 0x8000u) != 0u) {
        if (id <= EQUIP_ID_MAX) return (unsigned short)(0x8000u | s_equip_map[id]);
    }
    else if (id <= CONSUMABLE_ID_MAX) {
        return s_consumable_map[id];
    }
    return raw;
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

// Validate the complete raw list before touching it. This is intentionally
// stricter than the signature alone because 0x80219F40 lives in Bank-AB state
// and may temporarily hold a stale/reused heap pointer during transitions.
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
        else {
            if (!consumable_id_valid(id)) return 0u;
        }
    }
    return 0u; // no terminator inside the 0x200-byte allocation
}

static void rewrite_shop_stock(void) {
    unsigned int ptr;
    unsigned int count;
    unsigned int i;

    init_maps();
    if (!s_shops_enabled) return;
    if (!bank_ab_present()) return;

    ptr = rd32(SHOP_STOCK_PTR);
    if (!stock_pointer_valid(ptr)) return;
    if (!stock_has_vanilla_signature(ptr)) return;

    count = validated_stock_count(ptr);
    if (count < sizeof(k_shop_signature) / sizeof(k_shop_signature[0])) return;

    for (i = 0u; i < count; i++) {
        unsigned int addr = ptr + i * 2u;
        unsigned short raw = rd16(addr);
        unsigned short replacement = mapped_item_word(raw);
        if (replacement != raw) wr16(addr, replacement);
    }

    if (recomp_get_config_u32("log") != 0u) {
        recomp_log("universal-item-randomizer: shop stock mapped");
    }
}

// The Bank-N loader calls the currently resident record-9 stock builder before
// the shop's per-frame Bank-AB state machine consumes the source. The Rev-A
// caller returns immediately after setting a transition flag, so the main frame
// hook has a clean window before the next screen update. The Bank-AB fingerprint
// plus vanilla-stock signature make this idempotent and safe across arena/heap
// reuse.
RECOMP_HOOK("func_80072944")
void universal_item_randomizer_shop_tick(void) {
    rewrite_shop_stock();
}
