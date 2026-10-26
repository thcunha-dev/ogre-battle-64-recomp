// Knight of Danika native Change Class candidate injection test.
//
// TEST ONLY. This does NOT write the persistent roster and does NOT touch
// enemy/live battle participants. It temporarily replaces one Dragoon 0x14
// transition candidate (record +0x44) with Knight of Danika 0x71 in RAM.
// The class table itself is not saved to the player's save file.
//
// Evidence behind this test:
//   * class record base = 0x80187C34, stride = 0x48;
//   * Dragoon 0x14 record = 0x801881D4;
//   * +0x41..+0x44 are consumed by the native class-transition selection path;
//   * Dragoon +0x44 currently contains class 0x11;
//   * Danika class id = 0x71.
//
// Safety guard: patch only when the byte is exactly the expected 0x11.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define DRAGOON_TRANSITION_SLOT_4 0x80188218u
#define EXPECTED_ORIGINAL_CLASS   0x11u
#define DANIKA_CLASS_ID           0x71u

static unsigned char s_done;
static unsigned char s_logged_mismatch;

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
}

static void wr8(unsigned int address, unsigned char value) {
    *(volatile unsigned char*)address = value;
}

RECOMP_HOOK("func_80072944")
void danika_native_menu_test_tick(void) {
    unsigned char value;

    if (s_done) {
        return;
    }

    value = rd8(DRAGOON_TRANSITION_SLOT_4);

    if (value == (unsigned char)DANIKA_CLASS_ID) {
        s_done = 1u;
        return;
    }

    if (value != (unsigned char)EXPECTED_ORIGINAL_CLASS) {
        if (!s_logged_mismatch) {
            s_logged_mismatch = 1u;
            recomp_log("DANIKA_NATIVE_MENU unexpected_dragoon_transition_byte");
        }
        return;
    }

    wr8(DRAGOON_TRANSITION_SLOT_4, (unsigned char)DANIKA_CLASS_ID);
    s_done = 1u;
    recomp_log("DANIKA_NATIVE_MENU injected_dragoon_candidate_71");
}
