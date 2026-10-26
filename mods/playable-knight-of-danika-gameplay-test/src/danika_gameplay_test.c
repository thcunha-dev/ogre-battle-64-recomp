// Knight of Danika playable gameplay build.
//
// The persistent allied roster uses the real Gatekeeper class id 0x71. The
// battle engine keeps a separate live participant copy, so this build also
// proves and synchronizes that cached class before model creation. Ownership is
// established only through the proven roster index at participant+0xF6 plus
// matching level/EXP; enemy participants are never modified.
//
// DEVELOPMENT SAFETY: use a backup/disposable save while automatic Fighter ->
// Gatekeeper conversion remains enabled.

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
#define DANIKA_CLASS_ID         0x71u

#define BATTLE_STATE_PTR        0x801CE8DCu
#define BATTLE_SLOT_STRIDE      0xF8u
#define BATTLE_PARTICIPANT_OFF  0x1C4u
#define BATTLE_VALID_OFF        0x20Cu
#define BATTLE_SLOT_COUNT       20u
#define PARTICIPANT_LEVEL       0x31u
#define PARTICIPANT_EXP         0x32u
#define PARTICIPANT_ROSTER_IDX  0xF6u
#define PARTICIPANT_SCAN_MAX    0xF6u
#define PARTICIPANT_CLASS_HINT  0x30u
#define INVALID_PART_CLASS_OFF  0xFFu

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

static unsigned char s_converted;
static unsigned char s_wait_logged;
static unsigned char s_target_roster = 0xFFu;
static unsigned char s_participant_class_off = INVALID_PART_CLASS_OFF;
static unsigned char s_live_sync_logged;
static unsigned int s_last_battle_state;
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

static unsigned int roster_addr(unsigned int roster_idx) {
    return CHAR_TABLE + roster_idx * CHAR_STRIDE;
}

static int participant_matches_roster(unsigned int participant,
                                      unsigned int roster_idx) {
    unsigned int roster;

    if (roster_idx >= CHAR_COUNT || !valid_range(participant, 0xF8u)) {
        return 0;
    }

    roster = roster_addr(roster_idx);
    return rd8(participant + PARTICIPANT_LEVEL) == rd8(roster + CHAR_LEVEL) &&
           rd8(participant + PARTICIPANT_EXP) == rd8(roster + CHAR_EXP);
}

static int get_live_participant(unsigned int state, unsigned int slot_index,
                                unsigned int* out_participant,
                                unsigned int* out_roster_idx) {
    unsigned int slot;
    unsigned int participant;
    unsigned int roster_idx;

    slot = state + slot_index * BATTLE_SLOT_STRIDE;
    if (!valid_range(slot + BATTLE_VALID_OFF, 4u) ||
        rd32(slot + BATTLE_VALID_OFF) == 0u) {
        return 0;
    }

    participant = slot + BATTLE_PARTICIPANT_OFF;
    if (!valid_range(participant, 0xF8u)) {
        return 0;
    }

    roster_idx = (unsigned int)rd16(participant + PARTICIPANT_ROSTER_IDX);
    if (!participant_matches_roster(participant, roster_idx)) {
        return 0;
    }

    *out_participant = participant;
    *out_roster_idx = roster_idx;
    return 1;
}

static int offset_matches_roster_classes(unsigned int state, unsigned int off,
                                         unsigned int* out_witnesses,
                                         unsigned int* out_distinct) {
    unsigned int i;
    unsigned int witnesses = 0u;
    unsigned int distinct = 0u;
    unsigned int first_class = 0xFFu;

    if (off >= PARTICIPANT_SCAN_MAX || off == PARTICIPANT_LEVEL ||
        off == PARTICIPANT_EXP) {
        return 0;
    }

    for (i = 0u; i < BATTLE_SLOT_COUNT; ++i) {
        unsigned int participant;
        unsigned int roster_idx;
        unsigned int roster_class;

        if (!get_live_participant(state, i, &participant, &roster_idx)) {
            continue;
        }
        if (roster_idx == (unsigned int)s_target_roster) {
            continue;
        }

        roster_class = (unsigned int)rd8(roster_addr(roster_idx) + CHAR_CLASS);
        if ((unsigned int)rd8(participant + off) != roster_class) {
            return 0;
        }

        witnesses += 1u;
        if (first_class == 0xFFu) {
            first_class = roster_class;
            distinct = 1u;
        } else if (roster_class != first_class) {
            distinct = 2u;
        }
    }

    *out_witnesses = witnesses;
    *out_distinct = distinct;
    return witnesses >= 2u && distinct >= 2u;
}

static unsigned int find_target_participant(unsigned int state) {
    unsigned int i;

    if (s_target_roster >= CHAR_COUNT) {
        return 0u;
    }

    for (i = 0u; i < BATTLE_SLOT_COUNT; ++i) {
        unsigned int participant;
        unsigned int roster_idx;
        if (get_live_participant(state, i, &participant, &roster_idx) &&
            roster_idx == (unsigned int)s_target_roster) {
            return participant;
        }
    }
    return 0u;
}

static unsigned char discover_participant_class_offset(unsigned int state,
                                                       unsigned int target) {
    unsigned int witnesses;
    unsigned int distinct;
    unsigned int off;
    unsigned int candidate_count = 0u;
    unsigned int candidate = INVALID_PART_CLASS_OFF;

    // Class directly precedes the already-proven level byte in the natural
    // participant layout. Accept +0x30 only after cross-checking it against at
    // least two live allied characters of different classes.
    if (offset_matches_roster_classes(state, PARTICIPANT_CLASS_HINT,
                                      &witnesses, &distinct)) {
        unsigned int current = (unsigned int)rd8(target + PARTICIPANT_CLASS_HINT);
        if (current == FIGHTER_CLASS_ID || current == DANIKA_CLASS_ID) {
            return (unsigned char)PARTICIPANT_CLASS_HINT;
        }
    }

    // Fallback: derive the byte empirically. A candidate must reproduce every
    // proven allied roster class, with at least two distinct classes, and must
    // still contain the target's old Fighter/new Gatekeeper class. Ties fail
    // closed rather than guessing.
    for (off = 0u; off < PARTICIPANT_SCAN_MAX; ++off) {
        unsigned int current;
        if (!offset_matches_roster_classes(state, off, &witnesses, &distinct)) {
            continue;
        }
        current = (unsigned int)rd8(target + off);
        if (current != FIGHTER_CLASS_ID && current != DANIKA_CLASS_ID) {
            continue;
        }
        candidate = off;
        candidate_count += 1u;
    }

    if (candidate_count != 1u) {
        return INVALID_PART_CLASS_OFF;
    }
    return (unsigned char)candidate;
}

static void sync_target_live_participant(void) {
    unsigned int state;
    unsigned int target;
    unsigned int current;

    if (!s_converted || s_target_roster >= CHAR_COUNT) {
        return;
    }

    state = rd32(BATTLE_STATE_PTR);
    if (!valid_range(state, 0x300u)) {
        return;
    }

    if (state != s_last_battle_state) {
        s_last_battle_state = state;
        s_participant_class_off = INVALID_PART_CLASS_OFF;
        s_live_sync_logged = 0u;
    }

    target = find_target_participant(state);
    if (target == 0u) {
        return;
    }

    if (s_participant_class_off == INVALID_PART_CLASS_OFF) {
        s_participant_class_off = discover_participant_class_offset(state, target);
        if (s_participant_class_off == INVALID_PART_CLASS_OFF) {
            return;
        }
    }

    current = (unsigned int)rd8(target + (unsigned int)s_participant_class_off);
    if (current == FIGHTER_CLASS_ID) {
        wr8(target + (unsigned int)s_participant_class_off,
            (unsigned char)DANIKA_CLASS_ID);
    } else if (current != DANIKA_CLASS_ID) {
        return;
    }

    if (!s_live_sync_logged) {
        s_live_sync_logged = 1u;
        recomp_log("DANIKA_PLAYABLE live_participant_class_synced_to_71");
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
    return (best_count != 0u && ties == 1u) ? best : 0u;
}

static void prepare_gatekeeper_visual(void) {
    unsigned int table = rd32(BATTLE_TABLE_PTR);
    unsigned short selector;
    unsigned int g;

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
            }
        }
    }

    if (!s_visual_ready_logged) {
        s_visual_ready_logged = 1u;
        recomp_log("DANIKA_PLAYABLE Gatekeeper_selector_preloaded_before_models");
    }
}

static void convert_one_allied_fighter(void) {
    unsigned int i;

    if (s_converted) {
        if (s_target_roster < CHAR_COUNT &&
            rd8(roster_addr((unsigned int)s_target_roster) + CHAR_CLASS) ==
                (unsigned char)DANIKA_CLASS_ID) {
            return;
        }
        s_converted = 0u;
        s_target_roster = 0xFFu;
    }

    for (i = 0u; i < CHAR_COUNT; ++i) {
        unsigned int addr = roster_addr(i) + CHAR_CLASS;
        if (rd8(addr) == (unsigned char)FIGHTER_CLASS_ID) {
            wr8(addr, (unsigned char)DANIKA_CLASS_ID);
            s_target_roster = (unsigned char)i;
            s_converted = 1u;
            s_participant_class_off = INVALID_PART_CLASS_OFF;
            s_last_battle_state = 0u;
            recomp_log("DANIKA_PLAYABLE Fighter_02_to_Gatekeeper_71");
            return;
        }
    }

    if (!s_wait_logged) {
        s_wait_logged = 1u;
        recomp_log("DANIKA_PLAYABLE waiting_for_Fighter_02");
    }
}

RECOMP_HOOK("func_80072944")
void danika_playable_tick(void) {
    convert_one_allied_fighter();
    sync_target_live_participant();
}

RECOMP_HOOK("func_80093380")
void danika_visual_preload_hook(unsigned int destination, unsigned int size) {
    (void)destination;
    (void)size;
    sync_target_live_participant();
    prepare_gatekeeper_visual();
}
