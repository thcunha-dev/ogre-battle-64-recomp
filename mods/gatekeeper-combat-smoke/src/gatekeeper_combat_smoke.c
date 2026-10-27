// Gatekeeper playable combat smoke test.
//
// DEV/TEST ONLY. Converts the second player-roster Fighter (class 0x02) into
// Gatekeeper / Knight of Danika (class 0x71) so the allied class can be placed
// in formation and observed in real combat.
//
// Safety contract:
//   * scans only the proven persistent PLAYER roster at 0x80193BE0;
//   * targets the SECOND exact Fighter 0x02 encountered in roster order;
//   * writes only that record's class byte (+0x12), changing 0x02 -> 0x71;
//   * never scans or writes live battle/enemy participant memory;
//   * performs at most one gameplay write per process;
//   * retries read-only until two Fighters exist (save/roster may load late).
//
// This is intentionally the smallest possible test for "can Gatekeeper enter
// player-side battle?". It does NOT yet patch rear animation, greatsword
// anchors, equipment legality, stats, or promotion requirements.
//
// Because the class byte lives in persistent roster RAM, DO NOT save over an
// important save while this development mod is enabled. Use a copy/disposable
// save for the smoke test.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define CHAR_TABLE          0x80193BE0u
#define CHAR_STRIDE         0x38u
#define CHAR_CLASS          0x12u
#define CHAR_COUNT          100u

#define FIGHTER_CLASS_ID    0x02u
#define GATEKEEPER_CLASS_ID 0x71u
#define TARGET_FIGHTER_ORD  2u

static unsigned char s_done;
static unsigned char s_logged_waiting;

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

static void log_index(const char* prefix, unsigned int roster_index) {
    char line[112];
    unsigned int pos = 0u;
    const char* text = prefix;

    while (*text != '\0' && pos < 96u) {
        line[pos++] = *text++;
    }

    if (roster_index < CHAR_COUNT && pos < 107u) {
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
void gatekeeper_combat_smoke_tick(void) {
    unsigned int i;
    unsigned int fighter_ordinal = 0u;

    if (s_done) {
        return;
    }

    for (i = 0u; i < CHAR_COUNT; i++) {
        unsigned int class_addr = CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS;
        unsigned int class_id = rd8(class_addr);

        if (class_id != FIGHTER_CLASS_ID) {
            continue;
        }

        fighter_ordinal++;
        if (fighter_ordinal != TARGET_FIGHTER_ORD) {
            continue;
        }

        wr8(class_addr, (unsigned char)GATEKEEPER_CLASS_ID);
        s_done = 1u;
        log_index("GATEKEEPER_SMOKE fighter2 02->71", i);
        return;
    }

    if (!s_logged_waiting) {
        s_logged_waiting = 1u;
        log_index("GATEKEEPER_SMOKE waiting_for_second_fighter", CHAR_COUNT);
    }
}
