// Knight of Danika native class-transition injection test.
//
// TEST ONLY. This does NOT write the persistent roster and does NOT touch
// enemy/live battle participants. It temporarily replaces the two proven
// Dragoon 0x14 transition CLASS-ID bytes (+0x41 and +0x43) with Knight of
// Danika 0x71 in RAM. The threshold bytes (+0x42 and +0x44) are untouched.
// The class table itself is not saved to the player's save file.
//
// Evidence behind this test:
//   * class record base = 0x80187C34, stride = 0x48;
//   * Dragoon 0x14 record = 0x801881D4;
//   * func_8016EA54 treats +0x41/+0x43 as returned class IDs;
//   * func_8016EA54 treats +0x42/+0x44 as comparison thresholds;
//   * Dragoon values are +0x41=0x02, +0x42=0x06, +0x43=0x05, +0x44=0x11;
//   * Danika class id = 0x71.
//
// Safety guard: patch each class slot only when it contains its exact expected
// original value. No write occurs on an unexpected class-table layout.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define DRAGOON_CLASS_SLOT_A      0x80188215u /* record +0x41 */
#define DRAGOON_THRESHOLD_A       0x80188216u /* record +0x42; read-only */
#define DRAGOON_CLASS_SLOT_B      0x80188217u /* record +0x43 */
#define DRAGOON_THRESHOLD_B       0x80188218u /* record +0x44; read-only */
#define EXPECTED_CLASS_A          0x02u
#define EXPECTED_THRESHOLD_A      0x06u
#define EXPECTED_CLASS_B          0x05u
#define EXPECTED_THRESHOLD_B      0x11u
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
    unsigned char class_a;
    unsigned char threshold_a;
    unsigned char class_b;
    unsigned char threshold_b;

    if (s_done) {
        return;
    }

    class_a = rd8(DRAGOON_CLASS_SLOT_A);
    threshold_a = rd8(DRAGOON_THRESHOLD_A);
    class_b = rd8(DRAGOON_CLASS_SLOT_B);
    threshold_b = rd8(DRAGOON_THRESHOLD_B);

    if (class_a == (unsigned char)DANIKA_CLASS_ID &&
        class_b == (unsigned char)DANIKA_CLASS_ID &&
        threshold_a == (unsigned char)EXPECTED_THRESHOLD_A &&
        threshold_b == (unsigned char)EXPECTED_THRESHOLD_B) {
        s_done = 1u;
        return;
    }

    if (class_a != (unsigned char)EXPECTED_CLASS_A ||
        threshold_a != (unsigned char)EXPECTED_THRESHOLD_A ||
        class_b != (unsigned char)EXPECTED_CLASS_B ||
        threshold_b != (unsigned char)EXPECTED_THRESHOLD_B) {
        if (!s_logged_mismatch) {
            s_logged_mismatch = 1u;
            recomp_log("DANIKA_NATIVE_MENU unexpected_dragoon_transition_layout");
        }
        return;
    }

    wr8(DRAGOON_CLASS_SLOT_A, (unsigned char)DANIKA_CLASS_ID);
    wr8(DRAGOON_CLASS_SLOT_B, (unsigned char)DANIKA_CLASS_ID);
    s_done = 1u;
    recomp_log("DANIKA_NATIVE_MENU injected_dragoon_transition_classes_71");
}
