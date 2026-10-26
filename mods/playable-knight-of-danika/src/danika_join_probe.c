// Knight of Danika descriptor <-> participant join probe - read-only.
//
// This is the last ownership bridge diagnostic. It logs the renderer descriptor
// slot and live battle participant slot with the same numeric index, without
// assuming that those indices are semantically linked. Offline/runtime review
// can then prove or reject the alignment by comparing class identity across all
// live slots. No result from this file changes gameplay.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO 0x80000000u
#define RDRAM_HI 0x80800000u

#define DESC_BASE_PTR   0x801BA690u
#define DESC_COUNT      0x801BA694u
#define DESC_STRIDE     0xF8u
#define DESC_CLASS      0x4Cu
#define DESC_SELECTOR   0x50u

#define LIVE_BATTLE_PTR 0x801CE8DCu
#define PART_STRIDE     0xF8u
#define PART_OFF        0x1C4u
#define PART_VALID      0x20Cu
#define PART_CHARIDX    0xF6u
#define PART_MAX        20u

#define CHAR_TABLE      0x80193BE0u
#define CHAR_STRIDE     0x38u
#define CHAR_CLASS      0x12u
#define CHAR_COUNT      100u

static unsigned int s_last_desc_base;
static unsigned int s_last_part_base;
static unsigned int s_last_count;

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
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
    return value < 10u ? (char)('0' + value) : (char)('A' + value - 10u);
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

static void log_join(unsigned int index, unsigned int desc,
                     unsigned int part_slot) {
    char line[192];
    unsigned int pos = 0u;
    unsigned int dclass = rd32(desc + DESC_CLASS) & 0xFFu;
    unsigned int selector = rd32(desc + DESC_SELECTOR);
    unsigned int valid = rd32(part_slot + PART_VALID) != 0u;
    unsigned int roster = 0xFFu;
    unsigned int rclass = 0xFFu;

    if (valid) {
        unsigned int part = part_slot + PART_OFF;
        if (valid_range(part + PART_CHARIDX, 1u)) {
            roster = rd8(part + PART_CHARIDX);
            if (roster < CHAR_COUNT) {
                unsigned int addr = CHAR_TABLE + roster * CHAR_STRIDE + CHAR_CLASS;
                if (valid_range(addr, 1u)) {
                    rclass = rd8(addr);
                }
            }
        }
    }

    append_text(line, &pos, "DANIKA_JOIN i=");
    append_hex(line, &pos, index, 2u);
    append_text(line, &pos, " dclass=");
    append_hex(line, &pos, dclass, 2u);
    append_text(line, &pos, " dsel=");
    append_hex(line, &pos, selector, 8u);
    append_text(line, &pos, " pvalid=");
    append_hex(line, &pos, valid, 1u);
    append_text(line, &pos, " roster=");
    append_hex(line, &pos, roster, 2u);
    append_text(line, &pos, " rclass=");
    append_hex(line, &pos, rclass, 2u);
    append_text(line, &pos, " classmatch=");
    append_hex(line, &pos, valid && dclass == rclass, 1u);
    line[pos] = '\0';
    recomp_log(line);
}

void danika_join_probe_tick(void) {
    unsigned int desc_base = rd32(DESC_BASE_PTR);
    unsigned int count = rd32(DESC_COUNT);
    unsigned int part_base = rd32(LIVE_BATTLE_PTR);
    unsigned int i;

    if (count == 0u || count > PART_MAX ||
        !valid_range(desc_base, count * DESC_STRIDE) ||
        !valid_range(part_base, PART_OFF + PART_MAX * PART_STRIDE)) {
        if (!valid_range(desc_base, DESC_STRIDE) ||
            !valid_range(part_base, PART_OFF + PART_STRIDE)) {
            s_last_desc_base = 0u;
            s_last_part_base = 0u;
            s_last_count = 0u;
        }
        return;
    }

    if (desc_base == s_last_desc_base && part_base == s_last_part_base &&
        count == s_last_count) {
        return;
    }

    s_last_desc_base = desc_base;
    s_last_part_base = part_base;
    s_last_count = count;

    for (i = 0u; i < count; i++) {
        unsigned int desc = desc_base + i * DESC_STRIDE;
        unsigned int slot = part_base + i * PART_STRIDE;
        if (!valid_range(desc + DESC_SELECTOR, 4u) ||
            !valid_range(slot + PART_VALID, 4u)) {
            break;
        }
        log_join(i, desc, slot);
    }
}
