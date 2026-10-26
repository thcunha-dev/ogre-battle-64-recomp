// Knight of Danika playable-class candidate.
//
// Stable architecture:
//   * enemy/original Danika remains class 0x71 and is never modified;
//   * hidden Dragoon class 0x9C becomes the player-only Danika carrier;
//   * its built-in class alias at +0x45 is redirected from Dragoon 0x14 to
//     Danika 0x71, so normal class accessors resolve Danika data through the
//     game's own alias mechanism;
//   * the first generic allied Fighter 0x02 is converted to class 0x9C.
//
// This avoids hooks into streamed/banked battle code entirely. The only hook is
// the already-proven resident per-frame function func_80072944.
//
// TEST/DEVELOPMENT SAFETY:
//   * use a backup/disposable save;
//   * do not save over an important save while this development build is active.

#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define CHAR_TABLE              0x80193BE0u
#define CHAR_STRIDE             0x38u
#define CHAR_CLASS              0x12u
#define CHAR_COUNT              100u

#define CLASS_TABLE             0x80187C34u
#define CLASS_STRIDE            0x48u
#define CLASS_ALIAS             0x45u

#define FIGHTER_CLASS_ID        0x02u
#define DRAGOON_CLASS_ID        0x14u
#define DANIKA_CLASS_ID         0x71u
#define PLAYABLE_DANIKA_ID      0x9Cu

static unsigned char s_alias_ready;
static unsigned char s_converted;
static unsigned char s_logged_wait;

static unsigned char rd8(unsigned int address) {
    return *(volatile const unsigned char*)address;
}

static void wr8(unsigned int address, unsigned char value) {
    *(volatile unsigned char*)address = value;
}

static unsigned int class_addr(unsigned int class_id, unsigned int off) {
    return CLASS_TABLE + class_id * CLASS_STRIDE + off;
}

static void prepare_playable_danika_alias(void) {
    unsigned int alias_addr;
    unsigned char alias;

    if (s_alias_ready) {
        return;
    }

    alias_addr = class_addr(PLAYABLE_DANIKA_ID, CLASS_ALIAS);
    alias = rd8(alias_addr);

    // Vanilla hidden Dragoon is 0x9C -> alias 0x14. Accept an already-applied
    // 0x71 as well so reloads are idempotent. Anything else fails closed.
    if (alias == (unsigned char)DRAGOON_CLASS_ID) {
        wr8(alias_addr, (unsigned char)DANIKA_CLASS_ID);
        s_alias_ready = 1u;
        recomp_log("DANIKA_PLAYABLE alias_9C_14_to_71");
    } else if (alias == (unsigned char)DANIKA_CLASS_ID) {
        s_alias_ready = 1u;
        recomp_log("DANIKA_PLAYABLE alias_9C_already_71");
    }
}

static void convert_one_allied_fighter(void) {
    unsigned int i;

    if (!s_alias_ready || s_converted) {
        return;
    }

    for (i = 0u; i < CHAR_COUNT; ++i) {
        unsigned int addr = CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS;
        if (rd8(addr) == (unsigned char)FIGHTER_CLASS_ID) {
            wr8(addr, (unsigned char)PLAYABLE_DANIKA_ID);
            s_converted = 1u;
            recomp_log("DANIKA_PLAYABLE Fighter_02_to_PlayableDanika_9C");
            return;
        }
    }

    if (!s_logged_wait) {
        s_logged_wait = 1u;
        recomp_log("DANIKA_PLAYABLE waiting_for_Fighter_02");
    }
}

RECOMP_HOOK("func_80072944")
void danika_playable_tick(void) {
    prepare_playable_danika_alias();
    convert_one_allied_fighter();
}
