// Knight of Danika allied gameplay smoke test.
//
// TEST ONLY. Converts the first generic allied Fighter (class 0x02) in the
// proven persistent player roster to Knight of Danika (0x71). This is solely
// to prove map/unit/battle gameplay before native Change Class integration.
//
// Safety:
//   * only scans the proven player roster at 0x80193BE0;
//   * only changes class byte +0x12;
//   * only changes an exact Fighter 0x02 to Danika 0x71;
//   * never touches live battle/enemy participant memory;
//   * retries until the roster is loaded, then writes once;
//   * do NOT save over an important save while enabled.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define CHAR_TABLE       0x80193BE0u
#define CHAR_STRIDE      0x38u
#define CHAR_CLASS       0x12u
#define CHAR_COUNT       100u
#define FIGHTER_CLASS_ID 0x02u
#define DANIKA_CLASS_ID  0x71u

static unsigned char s_done;
static unsigned char s_wait_logged;

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
}

static void wr8(unsigned int address, unsigned char value) {
    *(volatile unsigned char*)address = value;
}

RECOMP_HOOK("func_80072944")
void danika_gameplay_test_tick(void) {
    unsigned int i;

    if (s_done) {
        return;
    }

    for (i = 0u; i < CHAR_COUNT; ++i) {
        unsigned int addr = CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS;
        if (rd8(addr) == (unsigned char)FIGHTER_CLASS_ID) {
            wr8(addr, (unsigned char)DANIKA_CLASS_ID);
            s_done = 1u;
            recomp_log("DANIKA_GAMEPLAY Fighter_02_to_Danika_71");
            return;
        }
    }

    if (!s_wait_logged) {
        s_wait_logged = 1u;
        recomp_log("DANIKA_GAMEPLAY waiting_for_Fighter_02");
    }
}
