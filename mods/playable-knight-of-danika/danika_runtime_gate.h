#ifndef PLAYABLE_KNIGHT_OF_DANIKA_RUNTIME_GATE_H
#define PLAYABLE_KNIGHT_OF_DANIKA_RUNTIME_GATE_H

#include <stdbool.h>
#include <stdint.h>

#include "danika_gate.h"
#include "danika_visual_override.h"

/*
 * Runtime-evidence gate for the eventual live selector override.
 *
 * This header deliberately contains no game-memory access.  It accepts only
 * already-validated evidence and returns a selector decision.  The caller must
 * independently prove descriptor<->participant alignment and player ownership.
 * Unknown/ambiguous evidence always returns the vanilla selector.
 */
typedef struct DanikaRuntimeEvidence {
    bool descriptor_participant_alignment_proven;
    bool participant_is_persistent_player_roster;
    bool descriptor_class_matches_roster_class;
    bool allied_dragoon_selector_proven;
    uint8_t descriptor_class_id;
    uint8_t roster_class_id;
    unsigned int original_selector;
    unsigned int allied_dragoon_selector;
} DanikaRuntimeEvidence;

static inline DanikaSide danika_runtime_side(const DanikaRuntimeEvidence* ev)
{
    if (ev == 0) {
        return DANIKA_SIDE_UNKNOWN;
    }
    if (!ev->descriptor_participant_alignment_proven ||
        !ev->participant_is_persistent_player_roster ||
        !ev->descriptor_class_matches_roster_class) {
        return DANIKA_SIDE_UNKNOWN;
    }
    if (ev->descriptor_class_id != ev->roster_class_id) {
        return DANIKA_SIDE_UNKNOWN;
    }

    /* Persistent player-roster provenance is the ownership proof. */
    return DANIKA_SIDE_ALLIED;
}

static inline unsigned int danika_runtime_visual_selector(
    const DanikaRuntimeEvidence* ev)
{
    DanikaSide side;

    if (ev == 0) {
        return DANIKA_INVALID_VISUAL_SELECTOR;
    }

    side = danika_runtime_side(ev);
    if (!ev->allied_dragoon_selector_proven) {
        return ev->original_selector;
    }

    return danika_select_visual_asset(
        ev->descriptor_class_id,
        side,
        ev->original_selector,
        ev->allied_dragoon_selector);
}

#endif
