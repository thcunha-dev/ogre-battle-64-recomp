// Knight of Danika bank-C code-byte probe - read-only diagnostics.
//
// The battle EXP award routine in bank J iterates 20 participant indices, calls
// func_801C9008(index), then applies these bank-C filters before using the
// participant in its EXP calculation:
//   func_801C8BA4, func_801C8E50, func_801C8EBC,
//   func_801C8B88, func_801C8C5C, plus lhu(participant+0x20)==0.
// Those generated bank functions are not tracked in Git.  While the battle bank
// is resident, take one bounded byte snapshot of the containing code window so
// the offline analyzer can recover their MIPS control flow and determine whether
// one of them is an actual side/team predicate.
//
// Safety: reads only. No RECOMP_HOOK, no RECOMP_PATCH, no RAM writes.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO 0x80000000u
#define RDRAM_HI 0x80800000u
#define LIVE_BATTLE_PTR 0x801CE8DCu

// Bank-C record-10 arena is ROM 0x1F0A00 -> RAM 0x801AD5C0.  The documented
// participant filters/getter fall inside this compact contiguous window.
#define BANKC_FILTER_BLOCK      0x801C8B80u
#define BANKC_FILTER_BLOCK_SIZE 0x500u
#define BANKC_DUMP_CHUNK        16u

static unsigned int s_dumped_for_base;

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

static int window_has_signal(unsigned int address, unsigned int size) {
    unsigned int i;
    unsigned int nonzero = 0u;
    unsigned int nonff = 0u;
    unsigned int sample = size < 64u ? size : 64u;

    if (!valid_range(address, size)) {
        return 0;
    }
    for (i = 0u; i < sample; i++) {
        unsigned int value = rd8(address + i);
        nonzero |= value;
        nonff |= value ^ 0xFFu;
    }
    return nonzero != 0u && nonff != 0u;
}

static void log_window(unsigned int address, unsigned int size) {
    unsigned int offset;

    for (offset = 0u; offset < size; offset += BANKC_DUMP_CHUNK) {
        char line[192];
        unsigned int pos = 0u;
        unsigned int i;
        unsigned int count = size - offset;
        if (count > BANKC_DUMP_CHUNK) {
            count = BANKC_DUMP_CHUNK;
        }

        append_text(line, &pos, "DANIKA_BANKC name=exp_filters addr=");
        append_hex(line, &pos, address, 8u);
        append_text(line, &pos, " off=");
        append_hex(line, &pos, offset, 4u);
        append_text(line, &pos, " bytes=");
        for (i = 0u; i < count; i++) {
            append_hex(line, &pos, rd8(address + offset + i), 2u);
        }
        line[pos] = '\0';
        recomp_log(line);
    }
}

void danika_bankc_probe_tick(void) {
    unsigned int base = rd32(LIVE_BATTLE_PTR);

    if (base < RDRAM_LO || base >= RDRAM_HI) {
        s_dumped_for_base = 0u;
        return;
    }
    if (s_dumped_for_base == base) {
        return;
    }
    if (!window_has_signal(BANKC_FILTER_BLOCK, BANKC_FILTER_BLOCK_SIZE)) {
        return;
    }

    s_dumped_for_base = base;
    log_window(BANKC_FILTER_BLOCK, BANKC_FILTER_BLOCK_SIZE);
}
