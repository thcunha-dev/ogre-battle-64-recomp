// Shared deterministic mapper for every Universal Item Randomizer acquisition
// path. Keeping one implementation prevents shop, battle and Bank-N grants from
// drifting to different replacements for the same seed.

#include "modding.h"
#include "randomizer_map.h"

RECOMP_IMPORT("*", unsigned int recomp_get_config_u32(const char* id));

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
    if (id < 1u || id > EQUIP_ID_MAX) return 0;
    name = rd32(EQUIP_TABLE + id * EQUIP_TABLE_STRIDE + EQUIP_TABLE_NAME);
    return readable_string_pointer(name);
}

static unsigned int consumable_class(unsigned int id) {
    return rd8(CONSUMABLE_TABLE + id * CONSUMABLE_TABLE_STRIDE + CONSUMABLE_TABLE_CLASS);
}

static int consumable_id_valid(unsigned int id) {
    unsigned int name;
    if (id < 1u || id > CONSUMABLE_ID_MAX) return 0;
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

// Sattolo produces one cycle: no fixed points for pools >1 and a one-to-one
// mapping, so replacements never collide inside a class.
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

void uir_map_init(void) {
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

unsigned short uir_map_equipment_id(unsigned int id) {
    uir_map_init();
    return id <= EQUIP_ID_MAX ? s_equip_map[id] : (unsigned short)id;
}

unsigned short uir_map_consumable_id(unsigned int id) {
    uir_map_init();
    return id <= CONSUMABLE_ID_MAX ? s_consumable_map[id] : (unsigned short)id;
}

unsigned short uir_map_item_word(unsigned short raw) {
    unsigned int id = raw & 0x7FFFu;
    if ((raw & 0x8000u) != 0u) {
        return (unsigned short)((raw & 0x8000u) | uir_map_equipment_id(id));
    }
    return uir_map_consumable_id(id);
}
