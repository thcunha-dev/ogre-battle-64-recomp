// Knight of Danika allied gameplay + early battle visual smoke test.
//
// TEST ONLY. Converts the first generic allied Fighter (class 0x02) in the
// proven persistent player roster to Knight of Danika (0x71), remembers that
// exact roster index, then applies a visual selector donor at the ENTRY of the
// native battle visual initializer func_801AE794.
//
// Why v3 exists:
//   v2 changed the selector from a late per-frame hook. User testing proved
//   that this changed only a formation/icon artifact while the combat model
//   remained Soldier-like. That is strong evidence that the visual asset had
//   already been loaded before the v2 write. v3 moves the exact same guarded
//   selector override earlier, before func_801AE794 consumes the render table.
//
// Battle visual donor priority:
//   1. Dragoon 0x14, when exactly one is loaded in the current render group;
//   2. Knight 0x05, when exactly one is loaded (diagnostic fallback only).
//
// Safety / fail-closed rules:
//   * roster write is only class byte +0x12: exact Fighter 0x02 -> Danika 0x71;
//   * remembers the exact player-roster index converted by this mod;
//   * never writes live participant memory;
//   * battle visual write is ONLY render-record +0x00 selector;
//   * render-record class word +0x02 remains 0x71;
//   * requires the remembered roster index to be an active live participant;
//   * requires exactly ONE active render record whose low class byte is 0x71;
//   * if an enemy Danika is also present (two 0x71 records), no visual write;
//   * donor selector must be unique, nonzero and not 0xFFFF;
//   * no global Dragoon/Knight/Danika class-table data is modified;
//   * do NOT save over an important save while this test mod is enabled.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO 0x80000000u
#define RDRAM_HI 0x80800000u

#define CHAR_TABLE       0x80193BE0u
#define CHAR_STRIDE      0x38u
#define CHAR_CLASS       0x12u
#define CHAR_COUNT       100u
#define FIGHTER_CLASS_ID 0x02u
#define KNIGHT_CLASS_ID  0x05u
#define DRAGOON_CLASS_ID 0x14u
#define DANIKA_CLASS_ID  0x71u

#define LIVE_BATTLE_PTR  0x801CE8DCu
#define PART_STRIDE      0xF8u
#define PART_OFF         0x1C4u
#define PART_VALID       0x20Cu
#define PART_CHARIDX     0xF6u
#define PART_MAX         20u

#define BATTLE_RECORD_TABLE_PTR 0x801BA6D8u
#define BATTLE_RESOURCE_GROUP   0x801BA72Du
#define BATTLE_RECORD_STRIDE    0x1Au
#define BATTLE_RECORD_MAX       24u
#define REC_SELECTOR            0x00u
#define REC_CLASS               0x02u

#define INVALID_SELECTOR 0xFFFFu
#define INVALID_ROSTER   0xFFu

static unsigned char s_converted;
static unsigned char s_wait_logged;
static unsigned char s_target_roster = INVALID_ROSTER;
static unsigned int s_last_visual_context;
static unsigned char s_visual_logged;

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

static void convert_one_allied_fighter(void) {
    unsigned int i;

    if (s_converted) {
        return;
    }

    for (i = 0u; i < CHAR_COUNT; ++i) {
        unsigned int addr = CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS;
        if (rd8(addr) == (unsigned char)FIGHTER_CLASS_ID) {
            wr8(addr, (unsigned char)DANIKA_CLASS_ID);
            s_target_roster = (unsigned char)i;
            s_converted = 1u;
            recomp_log("DANIKA_GAMEPLAY_V3 Fighter_02_to_Danika_71 target_saved");
            return;
        }
    }

    if (!s_wait_logged) {
        s_wait_logged = 1u;
        recomp_log("DANIKA_GAMEPLAY_V3 waiting_for_Fighter_02");
    }
}

static int converted_ally_is_active_participant(void) {
    unsigned int base;
    unsigned int i;
    unsigned int matches = 0u;

    if (!s_converted || s_target_roster >= CHAR_COUNT) {
        return 0;
    }

    if (rd8(CHAR_TABLE + (unsigned int)s_target_roster * CHAR_STRIDE + CHAR_CLASS) !=
        (unsigned char)DANIKA_CLASS_ID) {
        return 0;
    }

    base = rd32(LIVE_BATTLE_PTR);
    if (!valid_range(base, 4u)) {
        return 0;
    }

    for (i = 0u; i < PART_MAX; ++i) {
        unsigned int slot = base + i * PART_STRIDE;
        unsigned int part = slot + PART_OFF;
        unsigned int valid_addr = slot + PART_VALID;

        if (!valid_range(valid_addr, 4u) || !valid_range(part + PART_CHARIDX, 1u)) {
            break;
        }
        if (rd32(valid_addr) == 0u) {
            continue;
        }
        if (rd8(part + PART_CHARIDX) == s_target_roster) {
            matches += 1u;
        }
    }

    return matches == 1u;
}

static void try_battle_visual_override_early(void) {
    unsigned int table;
    unsigned int group;
    unsigned int offset_addr;
    signed short group_offset;
    unsigned int group_base;
    unsigned int slot;
    unsigned int danika_count = 0u;
    unsigned int danika_record = 0u;
    unsigned int dragoon_count = 0u;
    unsigned int dragoon_selector = 0u;
    unsigned int knight_count = 0u;
    unsigned int knight_selector = 0u;
    unsigned int donor_selector = 0u;
    unsigned int context;

    if (!converted_ally_is_active_participant()) {
        return;
    }

    table = rd32(BATTLE_RECORD_TABLE_PTR);
    if (!valid_range(table, 2u)) {
        return;
    }

    group = (unsigned int)rd8(BATTLE_RESOURCE_GROUP);
    offset_addr = table + group * 2u;
    if (!valid_range(offset_addr, 2u)) {
        return;
    }

    group_offset = (signed short)rd16(offset_addr);
    group_base = (unsigned int)((signed int)table + (signed int)group_offset);
    if (!valid_range(group_base, BATTLE_RECORD_STRIDE)) {
        return;
    }

    context = table ^ (group << 24) ^ group_base;
    if (context != s_last_visual_context) {
        s_last_visual_context = context;
        s_visual_logged = 0u;
    }

    for (slot = 0u; slot < BATTLE_RECORD_MAX; ++slot) {
        unsigned int record = group_base + slot * BATTLE_RECORD_STRIDE;
        unsigned int selector;
        unsigned int class_id;

        if (!valid_range(record, BATTLE_RECORD_STRIDE)) {
            break;
        }

        selector = (unsigned int)rd16(record + REC_SELECTOR);
        if (selector == INVALID_SELECTOR) {
            break;
        }

        class_id = (unsigned int)rd16(record + REC_CLASS) & 0xFFu;

        if (class_id == DANIKA_CLASS_ID) {
            danika_count += 1u;
            danika_record = record;
        } else if (class_id == DRAGOON_CLASS_ID &&
                   selector != 0u && selector != INVALID_SELECTOR) {
            dragoon_count += 1u;
            dragoon_selector = selector;
        } else if (class_id == KNIGHT_CLASS_ID &&
                   selector != 0u && selector != INVALID_SELECTOR) {
            knight_count += 1u;
            knight_selector = selector;
        }
    }

    if (danika_count != 1u || danika_record == 0u) {
        return;
    }

    if (dragoon_count == 1u) {
        donor_selector = dragoon_selector;
    } else if (dragoon_count == 0u && knight_count == 1u) {
        donor_selector = knight_selector;
    } else {
        return;
    }

    if (donor_selector == 0u || donor_selector == INVALID_SELECTOR) {
        return;
    }

    if (((unsigned int)rd16(danika_record + REC_CLASS) & 0xFFu) != DANIKA_CLASS_ID) {
        return;
    }

    if ((unsigned int)rd16(danika_record + REC_SELECTOR) != donor_selector) {
        wr16(danika_record + REC_SELECTOR, (unsigned short)donor_selector);
    }

    if (!s_visual_logged) {
        s_visual_logged = 1u;
        if (dragoon_count == 1u) {
            recomp_log("DANIKA_GAMEPLAY_V3 early_visual_71_using_Dragoon_14");
        } else {
            recomp_log("DANIKA_GAMEPLAY_V3 early_visual_71_using_Knight_05_fallback");
        }
    }
}

RECOMP_HOOK("func_80072944")
void danika_gameplay_test_tick(void) {
    convert_one_allied_fighter();
}

// Runs at native visual-initializer entry, before func_801AE794 consumes
// battle_record+0x00 through func_801B3D1C / func_801AD13C.
RECOMP_HOOK("func_801AE794")
void danika_gameplay_visual_init_pre(void) {
    try_battle_visual_override_early();
}
