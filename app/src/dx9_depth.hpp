#pragma once

// Direct3D 9 depth-state bridge for Ogre Battle 64's N64 RDP.
//
// This file is deliberately graphics-API independent. It centralizes the N64
// OTHERMODE_L depth bits and the screen-Z normalization needed by the D3D9
// pre-transformed vertex path. The constants match RT64's
// shared/rt64_f3d_defines.h (Z_CMP/Z_UPD/ZMODE_*).

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace ogre::dx9depth {

constexpr uint32_t kZCompare = 0x0010u;
constexpr uint32_t kZUpdate  = 0x0020u;
constexpr uint32_t kZModeMask = 0x0C00u;
constexpr uint32_t kZModeOpaque = 0x0000u;
constexpr uint32_t kZModeInterpenetrating = 0x0400u;
constexpr uint32_t kZModeTranslucent = 0x0800u;
constexpr uint32_t kZModeDecal = 0x0C00u;
constexpr float kN64MaxScreenZ = 1023.0f;

struct Mode {
    bool compare = false;
    bool update = false;
    uint32_t zmode = kZModeOpaque;

    bool enabled() const { return compare || update; }
    bool decal() const { return zmode == kZModeDecal; }
};

inline Mode decode(uint32_t othermode_l) {
    Mode out;
    out.compare = (othermode_l & kZCompare) != 0;
    out.update = (othermode_l & kZUpdate) != 0;
    out.zmode = othermode_l & kZModeMask;
    return out;
}

// F3DEX2's viewport maps post-divide Z into the N64's 0..G_MAXZ (0..1023)
// screen-depth domain. D3D9 XYZRHW vertices instead require Z in [0,1]. When
// no N64 viewport has been supplied, dx9_geometry already emits [0,1].
inline float normalize_screen_z(float z, bool viewport_set) {
    if (!std::isfinite(z)) return 1.0f;
    const float d3d_z = viewport_set ? (z / kN64MaxScreenZ) : z;
    return std::clamp(d3d_z, 0.0f, 1.0f);
}

// Ogre Battle 64 clears its depth image through the RDP's normal colour-image
// fill path: SETZIMG identifies the depth address, then SETCIMG points at that
// same address and a fill rectangle initializes it. This helper keeps the
// recognition rule in one place for the D3D9 backend.
inline bool is_depth_clear_target(uint32_t cimg_address, uint32_t zimg_address) {
    return zimg_address != 0 && cimg_address == zimg_address;
}

} // namespace ogre::dx9depth
