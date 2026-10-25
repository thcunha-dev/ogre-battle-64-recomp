#ifndef PLAYABLE_KNIGHT_OF_DANIKA_GATE_H
#define PLAYABLE_KNIGHT_OF_DANIKA_GATE_H

#include <stdbool.h>
#include <stdint.h>

/* Verified Rev-A renderer identity contract. */
#define DANIKA_CLASS_ID 0x71u
#define DRAGOON_CLASS_ID 0x14u

/*
 * Side is intentionally explicit and fail-closed.  DANIKA_SIDE_UNKNOWN must be
 * used until a live battle-participant owner/team field is independently
 * proven.  Camera/layout/interpolation flags are forbidden as substitutes.
 */
typedef enum DanikaSide {
    DANIKA_SIDE_UNKNOWN = 0,
    DANIKA_SIDE_ALLIED = 1,
    DANIKA_SIDE_ENEMY = 2,
} DanikaSide;

static inline bool danika_is_identity(uint8_t renderer_class_id) {
    return renderer_class_id == DANIKA_CLASS_ID;
}

static inline bool danika_should_use_player_override(uint8_t renderer_class_id,
                                                      DanikaSide side) {
    return danika_is_identity(renderer_class_id) && side == DANIKA_SIDE_ALLIED;
}

static inline uint8_t danika_player_animation_donor(uint8_t renderer_class_id,
                                                     DanikaSide side) {
    return danika_should_use_player_override(renderer_class_id, side)
               ? DRAGOON_CLASS_ID
               : renderer_class_id;
}

#endif /* PLAYABLE_KNIGHT_OF_DANIKA_GATE_H */
