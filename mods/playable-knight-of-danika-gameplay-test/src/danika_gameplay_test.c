// Knight of Danika playable gameplay build.
//
// Architecture proven from the real battle init path:
//   * the allied character keeps the real Gatekeeper class id 0x71;
//   * enemy/original Gatekeepers also remain 0x71;
//   * func_801B3BD8 loads resource 0x315736 and publishes its visual table at
//     D_801BA6D8;
//   * immediately after that, the banked init path calls resident memset helper
//     func_80093380, long before func_801AE794 creates battle models;
//   * we hook that resident helper as a safe synchronization point. No banked
//     function is hooked or replaced.
//
// The resource itself supplies the Gatekeeper asset selector. We scan the eight
// battle groups proven by D_801B9540, collect selectors associated with class
// 0x71, reject any selector also used by Soldier 0x02, then normalize every
// class-0x71 record to the unique best Gatekeeper selector before model creation.
// This means enemy Gatekeepers remain Gatekeepers; no Dragoon/Knight donor is
// used and no participant/enemy memory is modified.
//
// DEVELOPMENT SAFETY: use a backup/disposable save while the automatic Fighter
// -> Gatekeeper conversion is enabled.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO                0x80000000u
#define RDRAM_HI                0x80800000u

#define CHAR_TABLE              0x80193BE0u
#define CHAR_STRIDE             0x38u
#define CHAR_CLASS              0x12u
#define CHAR_COUNT              100u
#define FIGHTER_CLASS_ID        0x02u
#define DANIKA_CLASS_ID         0x71u

#define BATTLE_TABLE_PTR        0x801BA6D8u
#define BATTLE_GROUP            0x801BA72Du
#define RECORD_STRIDE           0x1Au
#define RECORD_SELECTOR         0x00u
#define RECORD_CLASS            0x02u
#define RECORD_MAX              64u
#define INVALID_SELECTOR        0xFFFFu

#define KNOWN_GROUP_COUNT       8u
#define SELECTOR_SET_MAX        24u

static const unsigned char s_known_groups[KNOWN_GROUP_COUNT] = {
    0x3Eu, 0x25u, 0x04u, 0x35u, 0x34u, 0x39u, 0x0Eu, 0x00u
};

typedef struct SelectorCount {
    unsigned short selector;
    unsigned char count;
} SelectorCount;

static unsigned char s_converted;
static unsigned char s_wait_logged;
static unsigned char s_target_roster = 0xFFu;
static unsigned short s_gatekeeper_selector;
static unsigned int s_last_table;
static unsigned char s_visual_ready_logged;

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

static int selector_in_set(const unsigned short* set, unsigned int count,
                           unsigned short selector) {
    unsigned int i;
    for (i = 0u; i < count; ++i) {
        if (set[i] == selector) {
            return 1;
        }
    }
    return 0;
}

static void add_unique_selector(unsigned short* set, unsigned int* count,
                                unsigned short selector) {
    if (selector == 0u || selector == INVALID_SELECTOR) {
        return;
    }
    if (selector_in_set(set, *count, selector)) {
        return;
    }
    if (*count < SELECTOR_SET_MAX) {
        set[*count] = selector;
        *count += 1u;
    }
}

static void add_counted_selector(SelectorCount* set, unsigned int* count,
                                 unsigned short selector) {
    unsigned int i;

    if (selector == 0u || selector == INVALID_SELECTOR) {
        return;
    }

    for (i = 0u; i < *count; ++i) {
        if (set[i].selector == selector) {
            if (set[i].count != 0xFFu) {
                set[i].count += 1u;
            }
            return;
        }
    }

    if (*count < SELECTOR_SET_MAX) {
        set[*count].selector = selector;
        set[*count].count = 1u;
        *count += 1u;
    }
}

static unsigned short discover_gatekeeper_selector(unsigned int table) {
    unsigned short soldier[SELECTOR_SET_MAX];
    SelectorCount danika[SELECTOR_SET_MAX];
    unsigned int soldier_count = 0u;
    unsigned int danika_count = 0u;
    unsigned int g;
    unsigned int best_count = 0u;
    unsigned short best = 0u;
    unsigned int ties = 0u;

    for (g = 0u; g < KNOWN_GROUP_COUNT; ++g) {
        unsigned int base;
        unsigned int slot;

        if (!get_group_base(table, (unsigned int)s_known_groups[g], &base)) {
            continue;
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
            if (class_id == FIGHTER_CLASS_ID) {
                add_unique_selector(soldier, &soldier_count, selector);
            } else if (class_id == DANIKA_CLASS_ID) {
                add_counted_selector(danika, &danika_count, selector);
            }
        }
    }

    // The true Gatekeeper selector must not also be a Soldier selector. Choose
    // the selector reproduced by the largest number of Danika records. A tie is
    // rejected rather than guessed.
    for (g = 0u; g < danika_count; ++g) {
        unsigned int count;
        if (selector_in_set(soldier, soldier_count, danika[g].selector)) {
            continue;
        }
        count = (unsigned int)danika[g].count;
        if (count > best_count) {
            best_count = count;
            best = danika[g].selector;
            ties = 1u;
        } else if (count == best_count && count != 0u &&
                   danika[g].selector != best) {
            ties += 1u;
        }
    }

    if (best_count == 0u || ties != 1u) {
        return 0u;
    }
    return best;
}

static unsigned int normalize_gatekeeper_records(unsigned int table,
                                                 unsigned short selector) {
    unsigned int g;
    unsigned int writes = 0u;

    for (g = 0u; g < KNOWN_GROUP_COUNT; ++g) {
        unsigned int base;
        unsigned int slot;

        if (!get_group_base(table, (unsigned int)s_known_groups[g], &base)) {
            continue;
        }

        for (slot = 0u; slot < RECORD_MAX; ++slot) {
            unsigned int record = base + slot * RECORD_STRIDE;
            unsigned short current;
            unsigned int class_id;

            if (!valid_range(record, RECORD_STRIDE)) {
                break;
            }

            current = rd16(record + RECORD_SELECTOR);
            if (current == INVALID_SELECTOR) {
                break;
            }

            class_id = (unsigned int)rd16(record + RECORD_CLASS) & 0xFFu;
            if (class_id == DANIKA_CLASS_ID && current != selector) {
                wr16(record + RECORD_SELECTOR, selector);
                writes += 1u;
            }
        }
    }

    return writes;
}

static void prepare_gatekeeper_visual(void) {
    unsigned int table = rd32(BATTLE_TABLE_PTR);
    unsigned short selector;

    if (!valid_range(table, 0x80u)) {
        return;
    }

    if (table != s_last_table) {
        s_last_table = table;
        s_gatekeeper_selector = 0u;
        s_visual_ready_logged = 0u;
    }

    selector = s_gatekeeper_selector;
    if (selector == 0u) {
        selector = discover_gatekeeper_selector(table);
        if (selector == 0u) {
            return;
        }
        s_gatekeeper_selector = selector;
    }

    (void)normalize_gatekeeper_records(table, selector);

    if (!s_visual_ready_logged) {
        s_visual_ready_logged = 1u;
        recomp_log("DANIKA_PLAYABLE Gatekeeper_selector_preloaded_before_models");
    }
}

static void convert_one_allied_fighter(void) {
    unsigned int i;

    if (s_converted) {
        // Keep a cheap sanity check so a different save/reload cannot silently
        // make us treat an unrelated roster slot as our converted character.
        if (s_target_roster < CHAR_COUNT &&
            rd8(CHAR_TABLE + (unsigned int)s_target_roster * CHAR_STRIDE + CHAR_CLASS) ==
                (unsigned char)DANIKA_CLASS_ID) {
            return;
        }
        s_converted = 0u;
        s_target_roster = 0xFFu;
    }

    for (i = 0u; i < CHAR_COUNT; ++i) {
        unsigned int addr = CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS;
        if (rd8(addr) == (unsigned char)FIGHTER_CLASS_ID) {
            wr8(addr, (unsigned char)DANIKA_CLASS_ID);
            s_target_roster = (unsigned char)i;
            s_converted = 1u;
            recomp_log("DANIKA_PLAYABLE Fighter_02_to_Gatekeeper_71");
            return;
        }
    }

    if (!s_wait_logged) {
        s_wait_logged = 1u;
        recomp_log("DANIKA_PLAYABLE waiting_for_Fighter_02");
    }
}

// Proven resident frame hook: roster conversion only.
RECOMP_HOOK("func_80072944")
void danika_playable_tick(void) {
    convert_one_allied_fighter();
}

// Proven resident memset helper. In the battle initialization path this call
// occurs immediately after func_801B3BD8 publishes D_801BA6D8 and before the
// banked model loader runs, giving us the missing safe pre-load window.
RECOMP_HOOK("func_80093380")
void danika_visual_preload_hook(unsigned int destination, unsigned int size) {
    (void)destination;
    (void)size;
    prepare_gatekeeper_visual();
}
