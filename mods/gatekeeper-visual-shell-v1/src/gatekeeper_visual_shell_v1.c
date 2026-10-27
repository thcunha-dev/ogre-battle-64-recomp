// Gatekeeper Visual Shell v1
//
// Keep a fully coherent playable Dragoon (0x14) as the logical combat class,
// including its 2H motion and dynamic weapon pipeline, while replacing only
// Dragoon render selectors with Gatekeeper (0x71) selectors discovered from
// the game's own loaded visual table. No live participant writes are used.
//
// DEVELOPMENT BUILD: use a disposable/copy save. The second Fighter in the
// persistent player roster is converted to Dragoon 0x14 with Dragoon defaults.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO                0x80000000u
#define RDRAM_HI                0x80800000u

#define CHAR_TABLE              0x80193BE0u
#define CHAR_STRIDE             0x38u
#define CHAR_CLASS              0x12u
#define CHAR_EQUIP0             0x2Au
#define CHAR_COUNT              100u

#define CLASS_EQUIP_TABLE       0x80187C62u
#define CLASS_STRIDE            0x48u
#define CLASS_EQUIP_SLOTS       4u

#define FIGHTER_CLASS_ID        0x02u
#define DRAGOON_CLASS_ID        0x14u
#define GATEKEEPER_CLASS_ID     0x71u

#define BATTLE_TABLE_PTR        0x801BA6D8u
#define RECORD_STRIDE           0x1Au
#define RECORD_SELECTOR         0x00u
#define RECORD_CLASS            0x02u
#define RECORD_MAX              64u
#define INVALID_SELECTOR        0xFFFFu
#define KNOWN_GROUP_COUNT       8u
#define GROUP_SELECTOR_MAX      16u
#define GROUP_RECORD_MAX        16u

static const unsigned char s_known_groups[KNOWN_GROUP_COUNT] = {
    0x3Eu, 0x25u, 0x04u, 0x35u, 0x34u, 0x39u, 0x0Eu, 0x00u
};

static unsigned char s_converted;
static unsigned char s_wait_logged;
static unsigned char s_visual_logged;
static unsigned int s_last_table;

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
}

static unsigned short rd16(unsigned int address) {
    return *(volatile const unsigned short*)address;
}

static unsigned int rd32(unsigned int address) {
    return *(volatile const unsigned int*)address;
}

static void wr8(unsigned int address, unsigned char value) {
    *(volatile unsigned char*)address = value;
}

static void wr16(unsigned int address, unsigned short value) {
    *(volatile unsigned short*)address = value;
}

static int valid_range(unsigned int address, unsigned int bytes) {
    if (address < RDRAM_LO || address >= RDRAM_HI) {
        return 0;
    }
    return bytes <= (RDRAM_HI - address);
}

static void apply_dragoon_defaults(unsigned int character) {
    unsigned int slot;
    unsigned int defaults = CLASS_EQUIP_TABLE + DRAGOON_CLASS_ID * CLASS_STRIDE;

    for (slot = 0u; slot < CLASS_EQUIP_SLOTS; ++slot) {
        unsigned short item = rd16(defaults + slot * 2u);
        wr16(character + CHAR_EQUIP0 + slot * 2u, item);
    }
}

static void convert_second_fighter_to_dragoon(void) {
    unsigned int i;
    unsigned int fighter_seen = 0u;

    if (s_converted) {
        return;
    }

    for (i = 0u; i < CHAR_COUNT; ++i) {
        unsigned int character = CHAR_TABLE + i * CHAR_STRIDE;
        unsigned int class_addr = character + CHAR_CLASS;

        if (rd8(class_addr) != (unsigned char)FIGHTER_CLASS_ID) {
            continue;
        }

        fighter_seen += 1u;
        if (fighter_seen == 2u) {
            apply_dragoon_defaults(character);
            wr8(class_addr, (unsigned char)DRAGOON_CLASS_ID);
            s_converted = 1u;
            recomp_log("GATEKEEPER_SHELL Fighter2_to_Dragoon_with_defaults");
            return;
        }
    }

    if (!s_wait_logged) {
        s_wait_logged = 1u;
        recomp_log("GATEKEEPER_SHELL waiting_for_second_Fighter_02");
    }
}

static int get_group_base(unsigned int table, unsigned int group,
                          unsigned int* out_base) {
    unsigned int off_addr = table + group * 2u;
    signed short offset;
    unsigned int base;

    if (!valid_range(off_addr, 2u)) {
        return 0;
    }

    offset = (signed short)rd16(off_addr);
    if (offset == 0 || offset == (signed short)-1) {
        return 0;
    }

    base = (unsigned int)((signed int)table + (signed int)offset);
    if (!valid_range(base, RECORD_STRIDE)) {
        return 0;
    }

    *out_base = base;
    return 1;
}

static int selector_exists(const unsigned short* selectors,
                           unsigned int count,
                           unsigned short selector) {
    unsigned int i;
    for (i = 0u; i < count; ++i) {
        if (selectors[i] == selector) {
            return 1;
        }
    }
    return 0;
}

static void add_unique_selector(unsigned short* selectors,
                                unsigned int* count,
                                unsigned short selector) {
    if (selector == 0u || selector == INVALID_SELECTOR ||
        selector_exists(selectors, *count, selector)) {
        return;
    }

    if (*count < GROUP_SELECTOR_MAX) {
        selectors[*count] = selector;
        *count += 1u;
    }
}

static unsigned int patch_one_group(unsigned int table, unsigned int group) {
    unsigned int base;
    unsigned short gatekeeper_selectors[GROUP_SELECTOR_MAX];
    unsigned int dragoon_records[GROUP_RECORD_MAX];
    unsigned int gatekeeper_count = 0u;
    unsigned int dragoon_count = 0u;
    unsigned int slot;
    unsigned int patched = 0u;

    if (!get_group_base(table, group, &base)) {
        return 0u;
    }

    for (slot = 0u; slot < RECORD_MAX; ++slot) {
        unsigned int record = base + slot * RECORD_STRIDE;
        unsigned short selector;
        unsigned int class_id;

        if (!valid_range(record, RECORD_STRIDE)) {
            break;
        }

        selector = rd16(record + RECORD_SELECTOR);
        if (selector == INVALID_SELECTOR) {
            break;
        }

        class_id = (unsigned int)rd16(record + RECORD_CLASS) & 0xFFu;
        if (class_id == GATEKEEPER_CLASS_ID) {
            add_unique_selector(gatekeeper_selectors, &gatekeeper_count, selector);
        } else if (class_id == DRAGOON_CLASS_ID && dragoon_count < GROUP_RECORD_MAX) {
            dragoon_records[dragoon_count] = record;
            dragoon_count += 1u;
        }
    }

    if (gatekeeper_count == 0u || dragoon_count == 0u) {
        return 0u;
    }

    // Fail closed. If Gatekeeper exposes one body selector for this group,
    // apply it to every Dragoon record in the group. If there are multiple
    // selectors, only use an ordinal mapping when record counts match exactly.
    if (gatekeeper_count == 1u) {
        unsigned int i;
        for (i = 0u; i < dragoon_count; ++i) {
            if (rd16(dragoon_records[i] + RECORD_SELECTOR) != gatekeeper_selectors[0]) {
                wr16(dragoon_records[i] + RECORD_SELECTOR, gatekeeper_selectors[0]);
                patched += 1u;
            }
        }
        return patched;
    }

    if (gatekeeper_count == dragoon_count) {
        unsigned int i;
        for (i = 0u; i < dragoon_count; ++i) {
            if (rd16(dragoon_records[i] + RECORD_SELECTOR) != gatekeeper_selectors[i]) {
                wr16(dragoon_records[i] + RECORD_SELECTOR, gatekeeper_selectors[i]);
                patched += 1u;
            }
        }
    }

    return patched;
}

static void apply_gatekeeper_visual_shell(void) {
    unsigned int table = rd32(BATTLE_TABLE_PTR);
    unsigned int g;
    unsigned int patched = 0u;

    if (!s_converted || !valid_range(table, 0x80u)) {
        return;
    }

    if (table != s_last_table) {
        s_last_table = table;
        s_visual_logged = 0u;
    }

    for (g = 0u; g < KNOWN_GROUP_COUNT; ++g) {
        patched += patch_one_group(table, (unsigned int)s_known_groups[g]);
    }

    if (patched != 0u && !s_visual_logged) {
        s_visual_logged = 1u;
        recomp_log("GATEKEEPER_SHELL Dragoon_class_kept_Gatekeeper_selectors_applied");
    }
}

RECOMP_HOOK("func_80072944")
void gatekeeper_visual_shell_tick(void) {
    convert_second_fighter_to_dragoon();
}

RECOMP_HOOK("func_80093380")
void gatekeeper_visual_shell_preload(unsigned int destination, unsigned int size) {
    (void)destination;
    (void)size;
    apply_gatekeeper_visual_shell();
}
