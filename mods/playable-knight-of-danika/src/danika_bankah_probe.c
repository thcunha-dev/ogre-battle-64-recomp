// Knight of Danika bank-AH battle-setup probe - read-only diagnostics.
//
// Upstream instruction-level work proves that the short streamed fragment
// ROM 0x23A370 -> RAM 0x801D0860 (size 0xE80) constructs battle participants:
//   func_801D0AAC reads the setup table at 0x801D16D0;
//   func_801D1508 allocates/tags a battle unit slot.
//
// The fragment is transient: bank J later reuses the same RAM arena, so a
// once-per-frame sampler can miss it.  Hook the RETURN of the base PI-DMA
// helper and dump only when the exact ROM/RAM/size triple has just completed.
// This is observation-only: no RAM writes, no patch, no game-state mutation.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define RDRAM_LO 0x80000000u
#define RDRAM_HI 0x80800000u

#define BANKAH_ROM_START 0x0023A370u
#define BANKAH_RAM_START 0x801D0860u
#define BANKAH_SIZE      0x00000E80u
#define BANKAH_CODE_SIZE 0x00000E70u
#define BANKAH_DUMP_CHUNK 16u

static unsigned int s_dumped;

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
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

static void log_window(void) {
    unsigned int offset;

    for (offset = 0u; offset < BANKAH_SIZE; offset += BANKAH_DUMP_CHUNK) {
        char line[192];
        unsigned int pos = 0u;
        unsigned int i;
        unsigned int count = BANKAH_SIZE - offset;
        if (count > BANKAH_DUMP_CHUNK) {
            count = BANKAH_DUMP_CHUNK;
        }

        append_text(line, &pos, "DANIKA_BANKAH addr=");
        append_hex(line, &pos, BANKAH_RAM_START, 8u);
        append_text(line, &pos, " off=");
        append_hex(line, &pos, offset, 4u);
        append_text(line, &pos, " bytes=");
        for (i = 0u; i < count; i++) {
            append_hex(line, &pos, rd8(BANKAH_RAM_START + offset + i), 2u);
        }
        line[pos] = '\0';
        recomp_log(line);
    }
}

RECOMP_HOOK_RETURN("func_8009DA50")
void danika_bankah_after_dma(unsigned int rom, unsigned int ram,
                             unsigned int size) {
    if (s_dumped != 0u) {
        return;
    }
    if (rom != BANKAH_ROM_START || ram != BANKAH_RAM_START ||
        size != BANKAH_SIZE) {
        return;
    }
    if (!valid_range(BANKAH_RAM_START, BANKAH_SIZE) ||
        !window_has_signal(BANKAH_RAM_START, BANKAH_CODE_SIZE)) {
        return;
    }

    s_dumped = 1u;
    recomp_log("DANIKA_BANKAH_CAPTURE rom=0023A370 ram=801D0860 size=00000E80");
    log_window();
}
