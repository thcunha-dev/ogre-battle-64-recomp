#ifndef PLAYABLE_KNIGHT_OF_DANIKA_RUNTIME_GATE_H
#define PLAYABLE_KNIGHT_OF_DANIKA_RUNTIME_GATE_H

#include <stdbool.h>
#include <stdint.h>

#include "danika_gate.h"
#include "danika_visual_override.h"

/*
 * Runtime-evidence gate for the eventual live selector override.
 *
 * This header deliberately contains no game-memory access. It accepts only
 * already-validated evidence and returns a selector decision. Descriptor <->
 * participant alignment, roster identity and ownership are separate proofs.
 *
 * IMPORTANT: persistent-roster provenance is NOT ownership proof by itself.
 * The caller must supply ownership_proven=true plus a concrete proven side.
 * Unknown/ambiguous/conflicting evidence always returns the vanilla selector.
 */
typedef struct DanikaRuntimeEvidence {
    bool descriptor_participant_alignment_proven;
    bool persistent_roster_link_proven;
    bool descriptor_class_matches_roster_class;
    bool ownership_proven;
    bool allied_dragoon_selector_proven;
    DanikaSide proven_side;
    uint8_t descriptor_class_id;
    uint8_t roster_class_id;
    unsigned int original_selector;
    unsigned int allied_dragoon_selector;
} DanikaRuntimeEvidence;

static inline bool danika_runtime_identity_proven(const DanikaRuntimeEvidence* ev)
{
    if (ev == 0) {
        return false;
    }
    if (!ev->descriptor_participant_alignment_proven ||
        !ev->persistent_roster_link_proven ||
        !ev->descriptor_class_matches_roster_class) {
        return false;
    }
    return ev->descriptor_class_id == ev->roster_class_id;
}

static inline DanikaSide danika_runtime_side(const DanikaRuntimeEvidence* ev)
{
    if (!danika_runtime_identity_proven(ev) || !ev->ownership_proven) {
        return DANIKA_SIDE_UNKNOWN;
    }

    if (ev->proven_side == DANIKA_SIDE_ALLIED ||
        ev->proven_side == DANIKA_SIDE_ENEMY) {
        return ev->proven_side;
    }

    return DANIKA_SIDE_UNKNOWN;
}

static inline bool danika_runtime_override_ready(const DanikaRuntimeEvidence* ev)
{
    if (ev == 0) {
        return false;
    }
    if (danika_runtime_side(ev) != DANIKA_SIDE_ALLIED) {
        return false;
    }
    if (!ev->allied_dragoon_selector_proven) {
        return false;
    }
    if (ev->allied_dragoon_selector == 0u ||
        ev->allied_dragoon_selector == DANIKA_INVALID_VISUAL_SELECTOR) {
        return false;
    }
    return danika_should_use_player_override(
        ev->descriptor_class_id,
        DANIKA_SIDE_ALLIED);
}

static inline unsigned int danika_runtime_visual_selector(
    const DanikaRuntimeEvidence* ev)
{
    if (ev == 0) {
        return DANIKA_INVALID_VISUAL_SELECTOR;
    }

    if (!danika_runtime_override_ready(ev)) {
        return ev->original_selector;
    }

    return danika_select_visual_asset(
        ev->descriptor_class_id,
        DANIKA_SIDE_ALLIED,
        ev->original_selector,
        ev->allied_dragoon_selector);
}

#endif
