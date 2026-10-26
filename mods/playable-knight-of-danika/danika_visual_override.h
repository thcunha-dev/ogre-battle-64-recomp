#ifndef PLAYABLE_KNIGHT_OF_DANIKA_VISUAL_OVERRIDE_H
#define PLAYABLE_KNIGHT_OF_DANIKA_VISUAL_OVERRIDE_H

#include "danika_gate.h"

#define DANIKA_INVALID_VISUAL_SELECTOR 0xFFFFu

/*
 * Proven visual data path:
 *   battle_record+0x00 -> descriptor+0x50 -> func_801AD13C arg0
 *   battle_record+0x02 -> descriptor+0x4C -> class word / class id
 *
 * The player-Dragoon selector is deliberately injected as an argument rather
 * than hard-coded until it has been extracted from independently identified
 * live battle data.  Zero and 0xFFFF are treated as unresolved/invalid.
 * func_801AD13C consumes the selector as a 1-based pointer-table index
 * (base + id*4, load -4), so an unproven selector must never be substituted.
 *
 * This resolver changes visual selection only.  It never changes the class
 * word: playable Danika remains class 0x71.  Unknown-side, enemy, non-Danika,
 * or invalid-donor inputs always fail closed to the original vanilla selector.
 */
static inline int danika_visual_selector_is_valid(unsigned int selector)
{
    return selector != 0u && selector != DANIKA_INVALID_VISUAL_SELECTOR;
}

static inline unsigned int danika_select_visual_asset(
    uint8_t renderer_class_id,
    DanikaSide side,
    unsigned int original_visual_selector,
    unsigned int dragoon_player_visual_selector)
{
    if (!danika_should_use_player_override(renderer_class_id, side)) {
        return original_visual_selector;
    }

    if (!danika_visual_selector_is_valid(dragoon_player_visual_selector)) {
        return original_visual_selector;
    }

    return dragoon_player_visual_selector;
}

#endif /* PLAYABLE_KNIGHT_OF_DANIKA_VISUAL_OVERRIDE_H */
