// Knight of Danika allied class-swap test.
//
// DEV/TEST ONLY. This intentionally writes one byte in the player's persistent
// roster so we can prove that class 0x71 is accepted as an allied unit before
// enabling the final presentation hook.
//
// Safety contract:
//   * only scans the proven player persistent roster at 0x80193BE0;
//   * only writes the class byte (+0x12) of the first entry whose class is
//     exactly playable Dragoon 0x14;
//   * only writes Knight of Danika 0x71;
//   * never scans or writes live enemy/battle participant memory;
//   * executes at most once per process run.
//
// Because this changes persistent roster RAM, DO NOT save over an important
// save file while this test mod is enabled. Use a disposable/copy save.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define CHAR_TABLE        0x80193BE0u
#define CHAR_STRIDE       0x38u
#define CHAR_CLASS        0x12u
#define CHAR_COUNT        100u

#define DRAGOON_CLASS_ID  0x14u
#define DANIKA_CLASS_ID   0x71u

static unsigned char s_attempted;

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
}

static void wr8(unsigned int address, unsigned char value) {
    *(volatile unsigned char*)address = value;
}

static char hex_digit(unsigned int value) {
    value &= 0xFu;
    return value < 10u ? (char)('0' + value) : (char)('A' + value - 10u);
}

static void log_result(const char* prefix, unsigned int roster_index) {
    char line[96];
    unsigned int pos = 0u;
    const char* text = prefix;

    while (*text != '\0' && pos < 80u) {
        line[pos++] = *text++;
    }

    if (roster_index < CHAR_COUNT && pos < 91u) {
        line[pos++] = ' ';
        line[pos++] = 'i';
        line[pos++] = '=';
        line[pos++] = hex_digit(roster_index >> 4);
        line[pos++] = hex_digit(roster_index);
    }

    line[pos] = '\0';
    recomp_log(line);
}

RECOMP_HOOK("func_80072944")
void danika_class_swap_test_tick(void) {
    unsigned int i;

    if (s_attempted) {
        return;
    }
    s_attempted = 1u;

    for (i = 0u; i < CHAR_COUNT; i++) {
        unsigned int class_addr = CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS;
        unsigned int class_id = rd8(class_addr);

        if (class_id == DRAGOON_CLASS_ID) {
            wr8(class_addr, (unsigned char)DANIKA_CLASS_ID);
            log_result("DANIKA_CLASS_SWAP 14->71", i);
            return;
        }
    }

    log_result("DANIKA_CLASS_SWAP no_dragoon_found", CHAR_COUNT);
}
