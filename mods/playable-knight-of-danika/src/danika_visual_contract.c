#include "danika_visual_override.h"

/*
 * MIPS/toolchain contract only.
 *
 * This deliberately has no RECOMP_HOOK/RECOMP_PATCH and is not called by the
 * diagnostic runtime.  Linking it into the probe ELF proves that the exact
 * fail-closed selector resolver used by the future playable-Danika patch is
 * valid for the target MIPS ABI before any live mutation is enabled.
 */
unsigned int danika_mips_visual_contract(
    uint8_t renderer_class_id,
    unsigned int side_value,
    unsigned int original_visual_selector,
    unsigned int dragoon_player_visual_selector)
{
    DanikaSide side = DANIKA_SIDE_UNKNOWN;

    if (side_value == (unsigned int)DANIKA_SIDE_ALLIED) {
        side = DANIKA_SIDE_ALLIED;
    } else if (side_value == (unsigned int)DANIKA_SIDE_ENEMY) {
        side = DANIKA_SIDE_ENEMY;
    }

    return danika_select_visual_asset(
        renderer_class_id,
        side,
        original_visual_selector,
        dragoon_player_visual_selector);
}
