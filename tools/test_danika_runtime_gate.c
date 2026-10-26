#include <assert.h>
#include <stdbool.h>
#include <stdint.h>

#include "../mods/playable-knight-of-danika/danika_runtime_gate.h"

static DanikaRuntimeEvidence base(void)
{
    DanikaRuntimeEvidence ev = {
        .descriptor_participant_alignment_proven = true,
        .participant_is_persistent_player_roster = true,
        .descriptor_class_matches_roster_class = true,
        .allied_dragoon_selector_proven = true,
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

    assert(danika_runtime_side(&ev) == DANIKA_SIDE_ALLIED);
    assert(danika_runtime_visual_selector(&ev) == 0x2Au);

    ev = base();
    ev.descriptor_participant_alignment_proven = false;
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.participant_is_persistent_player_roster = false;
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.descriptor_class_matches_roster_class = false;
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.roster_class_id = DRAGOON_CLASS_ID;
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_UNKNOWN);
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.allied_dragoon_selector_proven = false;
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.allied_dragoon_selector = 0u;
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.allied_dragoon_selector = DANIKA_INVALID_VISUAL_SELECTOR;
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    ev = base();
    ev.descriptor_class_id = DRAGOON_CLASS_ID;
    ev.roster_class_id = DRAGOON_CLASS_ID;
    assert(danika_runtime_side(&ev) == DANIKA_SIDE_ALLIED);
    assert(danika_runtime_visual_selector(&ev) == ev.original_selector);

    assert(danika_runtime_side(0) == DANIKA_SIDE_UNKNOWN);
    assert(danika_runtime_visual_selector(0) == DANIKA_INVALID_VISUAL_SELECTOR);
    return 0;
}
