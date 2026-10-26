// Knight of Danika battle probe - read-only runtime diagnostics.
//
// Purpose: observe both the battle visual records consumed by func_801B3D1C
// and the independently verified live battle-participant structure.  The two
// snapshots let the offline analyzer correlate persistent-roster classes with
// visual selectors without guessing an allied/enemy bit.
//
// Proven static visual layout (Rev A):
//   D_801BA6D8 -> signed-halfword offset table indexed by current resource group
//   group base + slot*0x1A -> one battle render record
//     +0x00 s16 visual asset selector (1-based package 0x3B6CD0 index)
//     +0x02 s16 class word (low byte is class id)
//     +0x0C s16 renderer context flags
//
// Independently verified live-participant layout (EXP-overflow restoration):
//   *(0x801CE8DC) -> live battle/result state
//   slot n = base + n*0xF8
//   participant n = slot + 0x1C4
//     slot +0x20C word != 0 -> participant is in use
//     participant +0x31 level
//     participant +0x32 EXP
//     participant +0xF6 persistent roster index
//   persistent roster = 0x80193BE0 + index*0x38; class is +0x12
//
// Safety contract: this file never writes game memory. It does not patch or
// replace any game function. The only hook is the already-established base
// per-frame function func_80072944, and the hook merely reads RAM and emits
// bounded/change-driven diagnostics.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO 0x80000000u
#define RDRAM_HI 0x80800000u

#define BATTLE_RECORD_TABLE_PTR 0x801BA6D8u
#define BATTLE_RESOURCE_GROUP   0x801BA72Du
#define BATTLE_RECORD_STRIDE    0x1Au
#define BATTLE_RECORD_MAX       24u

#define REC_SELECTOR 0x00u
#define REC_CLASS    0x02u
#define REC_04       0x04u
#define REC_06       0x06u
#define REC_08       0x08u
#define REC_0A       0x0Au
#define REC_FLAGS    0x0Cu
#define REC_0E       0x0Eu
#define REC_10       0x10u

#define LIVE_BATTLE_PTR 0x801CE8DCu
#define CHAR_TABLE      0x80193BE0u
#define CHAR_STRIDE     0x38u
#define CHAR_CLASS      0x12u
#define CHAR_COUNT      100u
#define PART_STRIDE     0xF8u
#define PART_OFF        0x1C4u
#define PART_VALID      0x20Cu
#define PART_LEVEL      0x31u
#define PART_EXP        0x32u
#define PART_TAIL       0xF0u
#define PART_CHARIDX    0xF6u
#define PART_MAX        20u

#define INVALID_SELECTOR 0xFFFFu
#define INVALID_CLASS    0xFFu

static unsigned int s_last_table;
static unsigned int s_last_group = 0xFFFFFFFFu;
static unsigned int s_signature[BATTLE_RECORD_MAX];
static unsigned char s_seen[BATTLE_RECORD_MAX];

static unsigned int s_last_part_base;
static unsigned int s_part_signature[PART_MAX];
static unsigned char s_part_seen[PART_MAX];

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
}

static unsigned short rd16(unsigned int address) {
    return *(volatile const unsigned short*)address;
}

static unsigned int rd32(unsigned int address) {
    return *(volatile const unsigned int*)address;
}

static int valid_range(unsigned int address, unsigned int bytes) {
    if (address < RDRAM_LO || address >= RDRAM_HI) {
        return 0;
    }
    return bytes <= (RDRAM_HI - address);
}

static char hex_digit(unsigned int value) {
    value &= 0xFu;
    return value < 10u ? (char)('0' + value) : (char)('A' + (value - 10u));
}

static void append_char(char* out, unsigned int* pos, char value) {
    if (*pos < 190u) {
        out[*pos] = value;
        *pos += 1u;
    }
}

static void append_text(char* out, unsigned int* pos, const char* text) {
    while (*text != '\0' && *pos < 190u) {
        out[*pos] = *text;
        *pos += 1u;
        text++;
    }
}

static void append_hex(char* out, unsigned int* pos, unsigned int value,
                       unsigned int digits) {
    unsigned int shift;
    while (digits != 0u) {
        digits--;
        shift = digits * 4u;
        append_char(out, pos, hex_digit(value >> shift));
    }
}

static void append_bytes(char* out, unsigned int* pos, unsigned int address,
                         unsigned int count) {
    unsigned int i;
    for (i = 0u; i < count; i++) {
        append_hex(out, pos, rd8(address + i), 2u);
    }
}

static void log_context(unsigned int table, unsigned int group) {
    char line[192];
    unsigned int pos = 0u;

    append_text(line, &pos, "DANIKA_PROBE context table=0x");
    append_hex(line, &pos, table, 8u);
    append_text(line, &pos, " group=0x");
    append_hex(line, &pos, group, 2u);
    line[pos] = '\0';
    recomp_log(line);
}

static void log_part_context(unsigned int base) {
    char line[192];
    unsigned int pos = 0u;

    append_text(line, &pos, "DANIKA_PART context base=0x");
    append_hex(line, &pos, base, 8u);
    line[pos] = '\0';
    recomp_log(line);
}

static void log_record(const char* prefix, unsigned int group, unsigned int slot,
                       unsigned int record) {
    char line[192];
    unsigned int pos = 0u;
    unsigned int selector = rd16(record + REC_SELECTOR);
    unsigned int class_word = rd16(record + REC_CLASS);

    append_text(line, &pos, prefix);
    append_text(line, &pos, " g=");
    append_hex(line, &pos, group, 2u);
    append_text(line, &pos, " slot=");
    append_hex(line, &pos, slot, 2u);
    append_text(line, &pos, " sel=");
    append_hex(line, &pos, selector, 4u);
    append_text(line, &pos, " class=");
    append_hex(line, &pos, class_word, 4u);
    append_text(line, &pos, " id=");
    append_hex(line, &pos, class_word & 0xFFu, 2u);
    append_text(line, &pos, " f04=");
    append_hex(line, &pos, rd16(record + REC_04), 4u);
    append_text(line, &pos, " f06=");
    append_hex(line, &pos, rd16(record + REC_06), 4u);
    append_text(line, &pos, " f08=");
    append_hex(line, &pos, rd16(record + REC_08), 4u);
    append_text(line, &pos, " f0A=");
    append_hex(line, &pos, rd16(record + REC_0A), 4u);
    append_text(line, &pos, " flags=");
    append_hex(line, &pos, rd16(record + REC_FLAGS), 4u);
    append_text(line, &pos, " f0E=");
    append_hex(line, &pos, rd16(record + REC_0E), 4u);
    append_text(line, &pos, " f10=");
    append_hex(line, &pos, rd16(record + REC_10), 4u);
    line[pos] = '\0';
    recomp_log(line);
}

static void log_participant(const char* prefix, unsigned int index,
                            unsigned int part, unsigned int roster,
                            unsigned int roster_class) {
    char line[192];
    unsigned int pos = 0u;

    append_text(line, &pos, prefix);
    append_text(line, &pos, " i=");
    append_hex(line, &pos, index, 2u);
    append_text(line, &pos, " roster=");
    append_hex(line, &pos, roster, 2u);
    append_text(line, &pos, " rclass=");
    append_hex(line, &pos, roster_class, 2u);
    append_text(line, &pos, " lvl=");
    append_hex(line, &pos, rd8(part + PART_LEVEL), 2u);
    append_text(line, &pos, " exp=");
    append_hex(line, &pos, rd8(part + PART_EXP), 2u);
    append_text(line, &pos, " head=");
    append_bytes(line, &pos, part, 16u);
    append_text(line, &pos, " tail=");
    append_bytes(line, &pos, part + PART_TAIL, 8u);
    line[pos] = '\0';
    recomp_log(line);
}

static unsigned int record_signature(unsigned int record) {
    unsigned int a = rd16(record + REC_SELECTOR);
    unsigned int b = rd16(record + REC_CLASS);
    unsigned int c = rd16(record + REC_FLAGS);
    unsigned int d = rd16(record + REC_10);

    // A compact change detector only; collisions can at worst suppress a
    // duplicate diagnostic line. It never influences gameplay.
    return (a * 0x45D9F3Bu) ^ (b << 16) ^ (c * 0x119DE1F3u) ^ d;
}

static unsigned int participant_signature(unsigned int part, unsigned int roster,
                                          unsigned int roster_class) {
    unsigned int sig = (roster << 24) ^ (roster_class << 16);
    unsigned int i;

    // Identity-oriented fingerprint.  EXP/level are intentionally excluded so
    // normal attacks/result progression do not spam logs every frame.
    for (i = 0u; i < 8u; i++) {
        sig = (sig * 33u) ^ rd8(part + PART_TAIL + i);
    }
    return sig;
}

static int plausible_record(unsigned int record) {
    unsigned int selector = rd16(record + REC_SELECTOR);
    unsigned int class_id = rd16(record + REC_CLASS) & 0xFFu;

    if (selector == 0u || selector == INVALID_SELECTOR) {
        return 0;
    }
    return class_id != 0u && class_id != INVALID_CLASS;
}

static void clear_seen(void) {
    unsigned int i;
    for (i = 0u; i < BATTLE_RECORD_MAX; i++) {
        s_seen[i] = 0u;
        s_signature[i] = 0u;
    }
}

static void clear_part_seen(void) {
    unsigned int i;
    for (i = 0u; i < PART_MAX; i++) {
        s_part_seen[i] = 0u;
        s_part_signature[i] = 0u;
    }
}

static void scan_live_participants(void) {
    unsigned int base = rd32(LIVE_BATTLE_PTR);
    unsigned int index;
    unsigned int new_context = 0u;

    if (base < RDRAM_LO || base >= RDRAM_HI) {
        if (s_last_part_base != 0u) {
            s_last_part_base = 0u;
            clear_part_seen();
        }
        return;
    }

    if (base != s_last_part_base) {
        s_last_part_base = base;
        clear_part_seen();
        log_part_context(base);
        new_context = 1u;
    }

    for (index = 0u; index < PART_MAX; index++) {
        unsigned int slot = base + index * PART_STRIDE;
        unsigned int valid_addr = slot + PART_VALID;
        unsigned int part = slot + PART_OFF;
        unsigned int roster;
        unsigned int roster_class = INVALID_CLASS;
        unsigned int signature;

        if (!valid_range(valid_addr, 4u) || !valid_range(part, PART_STRIDE)) {
            break;
        }
        if (rd32(valid_addr) == 0u) {
            s_part_seen[index] = 0u;
            s_part_signature[index] = 0u;
            continue;
        }

        roster = rd8(part + PART_CHARIDX);
        if (roster < CHAR_COUNT) {
            unsigned int class_addr = CHAR_TABLE + roster * CHAR_STRIDE + CHAR_CLASS;
            if (valid_range(class_addr, 1u)) {
                roster_class = rd8(class_addr);
            }
        }

        signature = participant_signature(part, roster, roster_class);
        if (!s_part_seen[index] || s_part_signature[index] != signature) {
            s_part_seen[index] = 1u;
            s_part_signature[index] = signature;
            log_participant(new_context ? "DANIKA_PART_SNAPSHOT" : "DANIKA_PART",
                            index, part, roster, roster_class);
        }
    }
}

RECOMP_HOOK("func_80072944")
void danika_battle_probe_tick(void) {
    unsigned int table = rd32(BATTLE_RECORD_TABLE_PTR);
    unsigned int group;
    unsigned int offset_addr;
    unsigned int group_base;
    signed short group_offset;
    unsigned int slot;
    unsigned int new_context = 0u;

    // Participant capture is independent from the renderer table and remains
    // useful even during frames where the visual group has not been installed.
    scan_live_participants();

    if (!valid_range(table, 2u)) {
        if (s_last_table != 0u) {
            s_last_table = 0u;
            s_last_group = 0xFFFFFFFFu;
            clear_seen();
        }
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

    if (table != s_last_table || group != s_last_group) {
        s_last_table = table;
        s_last_group = group;
        clear_seen();
        log_context(table, group);
        new_context = 1u;
    }

    for (slot = 0u; slot < BATTLE_RECORD_MAX; slot++) {
        unsigned int record = group_base + slot * BATTLE_RECORD_STRIDE;
        unsigned int selector;
        unsigned int signature;

        if (!valid_range(record, BATTLE_RECORD_STRIDE)) {
            break;
        }

        selector = rd16(record + REC_SELECTOR);
        if (selector == INVALID_SELECTOR) {
            break;
        }

        if (!plausible_record(record)) {
            continue;
        }

        signature = record_signature(record);
        if (!s_seen[slot] || s_signature[slot] != signature) {
            s_seen[slot] = 1u;
            s_signature[slot] = signature;
            log_record(new_context ? "DANIKA_SNAPSHOT" : "DANIKA_PROBE",
                       group, slot, record);
        }
    }
}
