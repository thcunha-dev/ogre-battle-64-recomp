#ifndef PLAYABLE_KNIGHT_OF_DANIKA_VISUAL_OVERRIDE_H
#define PLAYABLE_KNIGHT_OF_DANIKA_VISUAL_OVERRIDE_H

#include "danika_gate.h"

/*
 * Proven visual data path:
 *   battle_record+0x00 -> descriptor+0x50 -> func_801AD13C arg0
 *   battle_record+0x02 -> descriptor+0x4C -> class word / class id
 *
 * The diagnostic donor selector is deliberately injected as an argument rather
 * than hard-coded until the exact player-Dragoon selector has been extracted
 * from live battle data.  Zero is treated as unresolved because func_801AD13C
 * uses the selector as a 1-based pointer-table index (base + id*4, load -4).
 *
 * This function is therefore safe to land before the donor id is known: every
 * unresolved, enemy, unknown-side, or non-Danika path returns vanilla data.
 */
static inline unsigned int danika_select_visual_asset(
    unsigned int renderer_class_id,
    DanikaBattleSide side,
    unsigned int original_visual_selector,
    unsigned int dragoon_player_visual_selector)
{
    if (!danika_should_use_player_override(renderer_class_id, side)) {
        return original_visual_selector;
    }

    if (dragoon_player_visual_selector == 0u) {
        return original_visual_selector;
    }

    return dragoon_player_visual_selector;
}

#endif
