// Gatekeeper Hybrid v1
//
// Goal: keep the selected player character as Gatekeeper (0x71) in the
// persistent roster/UI, while making only its live battle participant use the
// proven playable Dragoon (0x14) combat package.  This is a compatibility
// bridge for rear-facing animation / 2H stance work; enemy memory is never
// touched.
//
// DEVELOPMENT BUILD: use a disposable/copy save.  The second Fighter in the
// persistent player roster is converted to Gatekeeper 0x71 for the test.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO                0x80000000u
#define RDRAM_HI                0x80800000u

#define CHAR_TABLE              0x80193BE0u
#define CHAR_STRIDE             0x38u
#define CHAR_CLASS              0x12u
#define CHAR_LEVEL              0x13u
#define CHAR_EXP                0x35u
#define CHAR_COUNT              100u

#define FIGHTER_CLASS_ID        0x02u
#define DRAGOON_CLASS_ID        0x14u
#define GATEKEEPER_CLASS_ID     0x71u

#define BATTLE_STATE_PTR        0x801CE8DCu
#define BATTLE_SLOT_STRIDE      0xF8u
#define BATTLE_PARTICIPANT_OFF  0x1C4u
#define BATTLE_VALID_OFF        0x20Cu
#define BATTLE_SLOT_COUNT       20u

#define PARTICIPANT_CLASS       0x30u
#define PARTICIPANT_LEVEL       0x31u
#define PARTICIPANT_EXP         0x32u
#define PARTICIPANT_ROSTER_IDX  0xF6u

#define BATTLE_TABLE_PTR        0x801BA6D8u
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

static unsigned char s_target_roster = 0xFFu;
static unsigned char s_converted;
static unsigned char s_wait_logged;
static unsigned char s_live_bridge_logged;
static unsigned char s_visual_bridge_logged;
static unsigned int s_last_table;
static unsigned short s_dragoon_selector;

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

static unsigned int roster_addr(unsigned int roster_idx) {
    return CHAR_TABLE + roster_idx * CHAR_STRIDE;
}

static void convert_second_fighter_to_gatekeeper(void) {
    unsigned int i;
    unsigned int fighter_seen = 0u;

    if (s_converted && s_target_roster < CHAR_COUNT) {
        unsigned int addr = roster_addr((unsigned int)s_target_roster) + CHAR_CLASS;
        if (rd8(addr) == (unsigned char)GATEKEEPER_CLASS_ID) {
            return;
        }
        s_converted = 0u;
        s_target_roster = 0xFFu;
    }

    for (i = 0u; i < CHAR_COUNT; ++i) {
        unsigned int addr = roster_addr(i) + CHAR_CLASS;
        if (rd8(addr) != (unsigned char)FIGHTER_CLASS_ID) {
            continue;
        }
        fighter_seen += 1u;
        if (fighter_seen == 2u) {
            wr8(addr, (unsigned char)GATEKEEPER_CLASS_ID);
            s_target_roster = (unsigned char)i;
            s_converted = 1u;
            recomp_log("GATEKEEPER_HYBRID roster_second_Fighter_02_to_71");
            return;
        }
    }

    if (!s_wait_logged) {
        s_wait_logged = 1u;
        recomp_log("GATEKEEPER_HYBRID waiting_for_second_Fighter_02");
    }
}

static int participant_matches_target(unsigned int participant,
                                      unsigned int roster_idx) {
    unsigned int roster;

    if (roster_idx != (unsigned int)s_target_roster ||
        roster_idx >= CHAR_COUNT ||
        !valid_range(participant, 0xF8u)) {
        return 0;
    }

    roster = roster_addr(roster_idx);
    return rd8(participant + PARTICIPANT_LEVEL) == rd8(roster + CHAR_LEVEL) &&
           rd8(participant + PARTICIPANT_EXP) == rd8(roster + CHAR_EXP);
}

static unsigned int find_target_participant(void) {
    unsigned int state;
    unsigned int i;

    if (!s_converted || s_target_roster >= CHAR_COUNT) {
        return 0u;
    }

    state = rd32(BATTLE_STATE_PTR);
    if (!valid_range(state, 0x300u)) {
        return 0u;
    }

    for (i = 0u; i < BATTLE_SLOT_COUNT; ++i) {
        unsigned int slot = state + i * BATTLE_SLOT_STRIDE;
        unsigned int participant;
        unsigned int roster_idx;

        if (!valid_range(slot + BATTLE_VALID_OFF, 4u) ||
            rd32(slot + BATTLE_VALID_OFF) == 0u) {
            continue;
        }

        participant = slot + BATTLE_PARTICIPANT_OFF;
        if (!valid_range(participant, 0xF8u)) {
            continue;
        }

        roster_idx = (unsigned int)rd16(participant + PARTICIPANT_ROSTER_IDX);
        if (participant_matches_target(participant, roster_idx)) {
            return participant;
        }
    }

    return 0u;
}

static void bridge_live_participant_to_dragoon(void) {
    unsigned int participant = find_target_participant();
    unsigned int current;

    if (participant == 0u) {
        return;
    }

    current = (unsigned int)rd8(participant + PARTICIPANT_CLASS);
    if (current == GATEKEEPER_CLASS_ID || current == FIGHTER_CLASS_ID) {
        wr8(participant + PARTICIPANT_CLASS, (unsigned char)DRAGOON_CLASS_ID);
        if (!s_live_bridge_logged) {
            s_live_bridge_logged = 1u;
            recomp_log("GATEKEEPER_HYBRID live_participant_uses_Dragoon_14");
        }
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
    if (selector == 0u || selector == INVALID_SELECTOR ||
        selector_in_set(set, *count, selector)) {
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

static unsigned short discover_dragoon_selector(unsigned int table) {
    unsigned short soldier[SELECTOR_SET_MAX];
    SelectorCount dragoon[SELECTOR_SET_MAX];
    unsigned int soldier_count = 0u;
    unsigned int dragoon_count = 0u;
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
            } else if (class_id == DRAGOON_CLASS_ID) {
                add_counted_selector(dragoon, &dragoon_count, selector);
            }
        }
    }

    for (g = 0u; g < dragoon_count; ++g) {
        unsigned int count;
        if (selector_in_set(soldier, soldier_count, dragoon[g].selector)) {
            continue;
        }
        count = (unsigned int)dragoon[g].count;
        if (count > best_count) {
            best_count = count;
            best = dragoon[g].selector;
            ties = 1u;
        } else if (count == best_count && count != 0u &&
                   dragoon[g].selector != best) {
            ties += 1u;
        }
    }

    return (best_count != 0u && ties == 1u) ? best : 0u;
}

static void preload_dragoon_visual_for_gatekeeper_records(void) {
    unsigned int table = rd32(BATTLE_TABLE_PTR);
    unsigned short selector;
    unsigned int g;

    if (!s_converted || !valid_range(table, 0x80u)) {
        return;
    }

    if (table != s_last_table) {
        s_last_table = table;
        s_dragoon_selector = 0u;
        s_visual_bridge_logged = 0u;
    }

    selector = s_dragoon_selector;
    if (selector == 0u) {
        selector = discover_dragoon_selector(table);
        if (selector == 0u) {
            return;
        }
        s_dragoon_selector = selector;
    }

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
            if (class_id == GATEKEEPER_CLASS_ID && current != selector) {
                wr16(record + RECORD_SELECTOR, selector);
            }
        }
    }

    if (!s_visual_bridge_logged) {
        s_visual_bridge_logged = 1u;
        recomp_log("GATEKEEPER_HYBRID preloaded_Dragoon_visual_for_71");
    }
}

RECOMP_HOOK("func_80072944")
void gatekeeper_hybrid_tick(void) {
    convert_second_fighter_to_gatekeeper();
    bridge_live_participant_to_dragoon();
}

RECOMP_HOOK("func_80093380")
void gatekeeper_hybrid_preload(unsigned int destination, unsigned int size) {
    (void)destination;
    (void)size;
    bridge_live_participant_to_dragoon();
    preload_dragoon_visual_for_gatekeeper_records();
}
