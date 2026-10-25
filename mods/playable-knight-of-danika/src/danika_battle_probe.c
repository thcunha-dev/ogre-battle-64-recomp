// Knight of Danika battle probe - read-only runtime diagnostics.
//
// Purpose: observe the battle resource records consumed by func_801B3D1C so
// the playable-Danika restoration can identify, from real battles, the exact
// allied-side signature and the player Dragoon visual selector without guessing.
//
// Proven static layout (Rev A):
//   D_801BA6D8 -> signed-halfword offset table indexed by current resource group
//   group base + slot*0x1A -> one battle render record
//     +0x00 s16 visual asset selector (1-based package 0x3B6CD0 index)
//     +0x02 s16 class word (low byte is class id)
//     +0x0C s16 renderer context flags
//
// Safety contract: this file never writes game memory. It does not patch or
// replace any game function. The only hook is the already-established base
// per-frame function func_80072944, and the hook merely reads RAM and emits a
// bounded log when a battle record changes.

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

#define INVALID_SELECTOR 0xFFFFu

static unsigned int s_last_table;
static unsigned int s_last_group = 0xFFFFFFFFu;
static unsigned int s_signature[BATTLE_RECORD_MAX];
static unsigned char s_seen[BATTLE_RECORD_MAX];

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

static void log_record(unsigned int group, unsigned int slot,
                       unsigned int record) {
    char line[192];
    unsigned int pos = 0u;
    unsigned int selector = rd16(record + REC_SELECTOR);
    unsigned int class_word = rd16(record + REC_CLASS);

    append_text(line, &pos, "DANIKA_PROBE g=");
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

static unsigned int record_signature(unsigned int record) {
    unsigned int a = rd16(record + REC_SELECTOR);
    unsigned int b = rd16(record + REC_CLASS);
    unsigned int c = rd16(record + REC_FLAGS);
    unsigned int d = rd16(record + REC_10);

    // A compact change detector only; collisions can at worst suppress a
    // duplicate diagnostic line. It never influences gameplay.
    return (a * 0x45D9F3Bu) ^ (b << 16) ^ (c * 0x119DE1F3u) ^ d;
}

static void clear_seen(void) {
    unsigned int i;
    for (i = 0u; i < BATTLE_RECORD_MAX; i++) {
        s_seen[i] = 0u;
        s_signature[i] = 0u;
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

        signature = record_signature(record);
        if (!s_seen[slot] || s_signature[slot] != signature) {
            s_seen[slot] = 1u;
            s_signature[slot] = signature;
            log_record(group, slot, record);
        }
    }
}
