#include <assert.h>
#include <stdbool.h>
#include <stdint.h>

#include "../mods/playable-knight-of-danika/danika_runtime_gate.h"

static DanikaRuntimeEvidence base(void)
{
    DanikaRuntimeEvidence ev = {
        .descriptor_participant_alignment_proven = true,
        .persistent_roster_link_proven = true,
        .descriptor_class_matches_roster_class = true,
        .ownership_proven = true,
        .allied_dragoon_selector_proven = true,
        .proven_side = DANIKA_SIDE_ALLIED,
        .descriptor_class_id = DANIKA_CLASS_ID,
        .roster_class_id = DANIKA_CLASS_ID,
        .original_selector = 0x44u,
        .allied_dragoon_selector = 0x2Au,
    };
    return ev;
}

int main(void)
{
    DanikaRuntimeEvidence ev = base();

    assert(danika_runtime_identity_proven(&ev));
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_ALLIED);
    assert(danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == 0x2Au);

    ev = base();
    ev.descriptor_participant_alignment_proven = false;
    assert(!danika_runtime_identity_proven(&ev));
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.persistent_roster_link_proven = false;
    assert(!danika_runtime_identity_proven(&ev));
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.descriptor_class_matches_roster_class = false;
    assert(!danika_runtime_identity_proven(&ev));
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.roster_class_id = DRAGOON_CLASS_ID;
    assert(!danika_runtime_identity_proven(&ev));
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    /* Persistent roster provenance alone must never become ALLY. */
    ev = base();
    ev.ownership_proven = false;
    assert(danika_runtime_identity_proven(&ev));
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    /* Explicit ENEMY proof preserves the original Danika path. */
    ev = base();
    ev.proven_side = DANIKA_SIDE_ENEMY;
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_ENEMY);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    /* Invalid/unknown side values fail closed even with ownership_proven=true. */
    ev = base();
    ev.proven_side = DANIKA_SIDE_UNKNOWN;
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.allied_dragoon_selector_proven = false;
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.allied_dragoon_selector = 0u;
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.allied_dragoon_selector = DANIKA_INVALID_VISUAL_SELECTOR;
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    /* Other allied classes may have a proven side but never receive Danika override. */
    ev = base();
    ev.descriptor_class_id = DRAGOON_CLASS_ID;
    ev.roster_class_id = DRAGOON_CLASS_ID;
    assert(danika_runtime_identity_proven(&ev));
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_ALLIED);
    assert(!danika_runtime_override_ready(&ev));
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    assert(!danika_runtime_identity_proven(0));
    assert(danika_runtime_side(0) == DANIKA_SIDE_UNKNOWN);
    assert(!danika_runtime_override_ready(0));
    assert(danika_runtime_visual_selector(0) == DANIKA_INVALID_VISUAL_SELECTOR);
    return 0;
}
