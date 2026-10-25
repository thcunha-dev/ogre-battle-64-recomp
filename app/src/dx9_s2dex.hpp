#pragma once

// S2DEX2 object/sprite core for the Ogre Battle 64 D3D9 renderer.
// This mirrors the validated WebGL implementation used by the game's NJPEG
// background path. It owns no graphics API objects and is safe to validate in
// the public compile gate.

#include <algorithm>
#include <cstdint>

#include "gbi.hpp"

namespace ogre::dx9s2d {

inline uint32_t rd32(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) |
           (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) |
           (static_cast<uint32_t>(p[3]) << 24);
}

struct ObjSprite {
    int32_t objX = 0, objY = 0;       // s10.2
    uint16_t scaleW = 0, scaleH = 0;  // u5.10
    uint16_t imageW = 0, imageH = 0;  // u10.5
    uint16_t imageStride = 0;         // TMEM line in 64-bit words
    uint16_t imageAdrs = 0;           // TMEM address in 64-bit words
    uint8_t imageFmt = 0, imageSiz = 0, imagePal = 0, imageFlags = 0;
};

inline bool decode_obj_sprite(const uint8_t* rdram, uint32_t address, ObjSprite& s) {
    const uint32_t a = address & 0x1FFFFFFFu;
    if (!rdram || static_cast<uint64_t>(a) + 24u > gbi::kRdramSize) return false;
    const uint8_t* p = rdram + a;
    const uint32_t w0 = rd32(p + 0);
    const uint32_t w1 = rd32(p + 4);
    const uint32_t w2 = rd32(p + 8);
    const uint32_t w3 = rd32(p + 12);
    const uint32_t w4 = rd32(p + 16);
    const uint32_t w5 = rd32(p + 20);
    s.objX = static_cast<int16_t>(w0 >> 16);
    s.scaleW = static_cast<uint16_t>(w0);
    s.imageW = static_cast<uint16_t>(w1 >> 16);
    s.objY = static_cast<int16_t>(w2 >> 16);
    s.scaleH = static_cast<uint16_t>(w2);
    s.imageH = static_cast<uint16_t>(w3 >> 16);
    s.imageStride = static_cast<uint16_t>(w4 >> 16);
    s.imageAdrs = static_cast<uint16_t>(w4);
    s.imageFmt = static_cast<uint8_t>(w5 >> 24);
    s.imageSiz = static_cast<uint8_t>(w5 >> 16);
    s.imagePal = static_cast<uint8_t>(w5 >> 8);
    s.imageFlags = static_cast<uint8_t>(w5);
    return true;
}

struct ObjMtx {
    int32_t a = 0x10000, b = 0, c = 0, d = 0x10000;
    int16_t x = 0, y = 0;
    uint16_t baseScaleX = 1024, baseScaleY = 1024;
    bool subMtx = false;
};

inline bool set_obj_matrix(const uint8_t* rdram, uint32_t address,
                           uint32_t index, ObjMtx& m) {
    const uint32_t a = address & 0x1FFFFFFFu;
    const uint32_t need = index == 0 ? 24u : (index == 2 ? 8u : 0u);
    if (!need || !rdram || static_cast<uint64_t>(a) + need > gbi::kRdramSize) return false;
    const uint8_t* p = rdram + a;
    if (index == 0) {
        m.a = static_cast<int32_t>(rd32(p + 0));
        m.b = static_cast<int32_t>(rd32(p + 4));
        m.c = static_cast<int32_t>(rd32(p + 8));
        m.d = static_cast<int32_t>(rd32(p + 12));
        const uint32_t w4 = rd32(p + 16);
        const uint32_t w5 = rd32(p + 20);
        m.x = static_cast<int16_t>(w4 >> 16);
        m.y = static_cast<int16_t>(w4);
        m.baseScaleX = static_cast<uint16_t>(w5 >> 16);
        m.baseScaleY = static_cast<uint16_t>(w5);
        m.subMtx = false;
    } else {
        const uint32_t w0 = rd32(p + 0);
        const uint32_t w1 = rd32(p + 4);
        m.a = 0x10000; m.b = 0; m.c = 0; m.d = 0x10000;
        m.x = static_cast<int16_t>(w0 >> 16);
        m.y = static_cast<int16_t>(w0);
        m.baseScaleX = static_cast<uint16_t>(w1 >> 16);
        m.baseScaleY = static_cast<uint16_t>(w1);
        m.subMtx = true;
    }
    return true;
}

struct ObjectRect {
    float x0 = 0, y0 = 0, x1 = 0, y1 = 0;
    float u0 = 0, v0 = 0, u1 = 0, v1 = 0;
    float imageW = 0, imageH = 0;
};

inline ObjectRect compute_object_rect(const ObjSprite& s, const ObjMtx& m,
                                      bool full_matrix) {
    ObjectRect out;
    out.imageW = static_cast<float>(s.imageW) / 32.0f;
    out.imageH = static_cast<float>(s.imageH) / 32.0f;
    const float scaleW = static_cast<float>(std::max<uint16_t>(s.scaleW, 1)) / 1024.0f;
    const float scaleH = static_cast<float>(std::max<uint16_t>(s.scaleH, 1)) / 1024.0f;
    const float objX = static_cast<float>(s.objX) / 4.0f;
    const float objY = static_cast<float>(s.objY) / 4.0f;
    const float objW = out.imageW / scaleW + objX;
    const float objH = out.imageH / scaleH + objY;
    const float mx = static_cast<float>(m.x) / 4.0f;
    const float my = static_cast<float>(m.y) / 4.0f;
    const float bsX = static_cast<float>(std::max<uint16_t>(m.baseScaleX, 1)) / 1024.0f;
    const float bsY = static_cast<float>(std::max<uint16_t>(m.baseScaleY, 1)) / 1024.0f;

    if (full_matrix && !m.subMtx) {
        const float ma = static_cast<float>(m.a) / 65536.0f;
        const float mb = static_cast<float>(m.b) / 65536.0f;
        const float mc = static_cast<float>(m.c) / 65536.0f;
        const float md = static_cast<float>(m.d) / 65536.0f;
        out.x0 = ma * objX + mb * objY + mx;
        out.y0 = mc * objX + md * objY + my;
        out.x1 = ma * objW + mb * objH + mx;
        out.y1 = mc * objW + md * objH + my;
    } else {
        out.x0 = mx + objX / bsX;
        out.y0 = my + objY / bsY;
        out.x1 = mx + objW / bsX;
        out.y1 = my + objH / bsY;
    }

    const bool flipS = (s.imageFlags & 0x01u) != 0;
    const bool flipT = (s.imageFlags & 0x10u) != 0;
    out.u0 = flipS ? out.imageW : 0.0f;
    out.u1 = flipS ? 0.0f : out.imageW;
    out.v0 = flipT ? out.imageH : 0.0f;
    out.v1 = flipT ? 0.0f : out.imageH;
    return out;
}

// S2DEX2 opcodes collide with F3DEX2. Keep their names explicit at the callsite.
constexpr uint8_t OBJ_RECTANGLE = 0x01;
constexpr uint8_t OBJ_SPRITE = 0x02;
constexpr uint8_t OBJ_RECTANGLE_R = 0xDA;
constexpr uint8_t OBJ_MOVEMEM = 0xDC;
constexpr uint8_t RDPHALF_0 = 0xE4;

} // namespace ogre::dx9s2d
