// Knight of Danika bank-J code-byte probe - read-only diagnostics.
//
// The two result-sync functions that establish the live participant <->
// persistent roster bridge live in streamed bank J, whose generated assembly is
// gitignored and requires the original ROM.  When a battle/result state is live,
// this probe takes a one-time byte snapshot of those VRAM windows directly from
// RDRAM.  If the port keeps the original overlay bytes resident, the offline
// analyzer can reconstruct the decisive MIPS instructions without requiring a
// ROM upload.  If it does not, the dump is simply reported as non-code data.
//
// Safety: reads only.  No RECOMP_HOOK, no RECOMP_PATCH, no RAM writes.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

void danika_bankc_probe_tick(void);
void danika_join_probe_tick(void);

#define RDRAM_LO 0x80000000u
#define RDRAM_HI 0x80800000u
#define LIVE_BATTLE_PTR 0x801CE8DCu

// Proven from the working EXP-overflow restoration / bank-J map.
#define BANKJ_SYNC_RECORD_TO_PART 0x801D8DC4u
#define BANKJ_SYNC_RECORD_TO_PART_SIZE 0xCCu
#define BANKJ_SYNC_PART_TO_RECORD 0x801D8E90u
#define BANKJ_SYNC_PART_TO_RECORD_SIZE 0x180u
#define BANKJ_DUMP_CHUNK 16u

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

static void log_window(const char* name, unsigned int address,
                       unsigned int size) {
    unsigned int offset;

    for (offset = 0u; offset < size; offset += BANKJ_DUMP_CHUNK) {
        char line[192];
        unsigned int pos = 0u;
        unsigned int i;
        unsigned int count = size - offset;
        if (count > BANKJ_DUMP_CHUNK) {
            count = BANKJ_DUMP_CHUNK;
        }

        append_text(line, &pos, "DANIKA_BANKJ name=");
        append_text(line, &pos, name);
        append_text(line, &pos, " addr=");
        append_hex(line, &pos, address, 8u);
        append_text(line, &pos, " off=");
        append_hex(line, &pos, offset, 4u);
        append_text(line, &pos, " bytes=");
        for (i = 0u; i < count; i++) {
            unsigned int value = rd8(address + offset + i);
            append_hex(line, &pos, value, 2u);
        }
        line[pos] = '\0';
        recomp_log(line);
    }
}

void danika_bankj_probe_tick(void) {
    unsigned int base;

    // Bank C is resident during the normal battle and contains the EXP filters
    // that may directly encode side/team eligibility. The descriptor/participant
    // join probe runs in this same read-only chain and does not assume alignment;
    // it only records evidence needed to prove or reject it.
    danika_bankc_probe_tick();
    danika_join_probe_tick();

    base = rd32(LIVE_BATTLE_PTR);
    if (base < RDRAM_LO || base >= RDRAM_HI) {
        s_dumped_for_base = 0u;
        return;
    }
    if (s_dumped_for_base == base) {
        return;
    }

    // Wait until both known sync windows contain some nontrivial bytes.  This
    // avoids permanently consuming the one-shot while the streamed bank is not
    // installed yet.
    if (!window_has_signal(BANKJ_SYNC_RECORD_TO_PART,
                           BANKJ_SYNC_RECORD_TO_PART_SIZE) ||
        !window_has_signal(BANKJ_SYNC_PART_TO_RECORD,
                           BANKJ_SYNC_PART_TO_RECORD_SIZE)) {
        return;
    }

    s_dumped_for_base = base;
    log_window("record_to_part", BANKJ_SYNC_RECORD_TO_PART,
               BANKJ_SYNC_RECORD_TO_PART_SIZE);
    log_window("part_to_record", BANKJ_SYNC_PART_TO_RECORD,
               BANKJ_SYNC_PART_TO_RECORD_SIZE);
}
