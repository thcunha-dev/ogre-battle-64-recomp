#pragma once

// Shared CPU-side RDP combiner/blender decode for the D3D9 backend.
// Numeric selector values and bit layouts match web_renderer.cpp / RT64.
// This file contains no D3D calls so it can be compile-validated independently.

#include <cstdint>

namespace ogre::dx9rdp {

constexpr uint32_t kCyc1 = 0;
constexpr uint32_t kCyc2 = 1;
constexpr uint32_t kCycCopy = 2;
constexpr uint32_t kCycFill = 3;

enum ColorSel {
    CSEL_COMBINED = 0, CSEL_TEXEL0, CSEL_TEXEL1, CSEL_PRIMITIVE, CSEL_SHADE,
    CSEL_ENVIRONMENT, CSEL_KEY_CENTER, CSEL_KEY_SCALE, CSEL_COMBINED_ALPHA,
    CSEL_TEXEL0_ALPHA, CSEL_TEXEL1_ALPHA, CSEL_PRIMITIVE_ALPHA, CSEL_SHADE_ALPHA,
    CSEL_ENV_ALPHA, CSEL_LOD_FRACTION, CSEL_PRIM_LOD_FRAC, CSEL_NOISE, CSEL_K4,
    CSEL_K5, CSEL_ONE, CSEL_ZERO
};

enum AlphaSel {
    ASEL_COMBINED = 0, ASEL_TEXEL0, ASEL_TEXEL1, ASEL_PRIMITIVE, ASEL_SHADE,
    ASEL_ENVIRONMENT, ASEL_LOD_FRACTION, ASEL_PRIM_LOD_FRAC, ASEL_ONE, ASEL_ZERO
};

constexpr int cs_a(int i) {
    return i <= 5 ? i : (i == 6 ? CSEL_ONE : (i == 7 ? CSEL_NOISE : CSEL_ZERO));
}
constexpr int cs_b(int i) {
    return i <= 5 ? i : (i == 6 ? CSEL_KEY_CENTER : (i == 7 ? CSEL_K4 : CSEL_ZERO));
}
constexpr int cs_c(int i) {
    return i <= 5 ? i
         : i == 6 ? CSEL_KEY_SCALE
         : i == 7 ? CSEL_COMBINED_ALPHA
         : i == 8 ? CSEL_TEXEL0_ALPHA
         : i == 9 ? CSEL_TEXEL1_ALPHA
         : i == 10 ? CSEL_PRIMITIVE_ALPHA
         : i == 11 ? CSEL_SHADE_ALPHA
         : i == 12 ? CSEL_ENV_ALPHA
         : i == 13 ? CSEL_LOD_FRACTION
         : i == 14 ? CSEL_PRIM_LOD_FRAC
         : i == 15 ? CSEL_K5
         : CSEL_ZERO;
}
constexpr int cs_d(int i) { return i <= 5 ? i : (i == 6 ? CSEL_ONE : CSEL_ZERO); }
constexpr int as_abd(int i) { return i <= 5 ? i : (i == 6 ? ASEL_ONE : ASEL_ZERO); }
constexpr int as_c(int i) { return i <= 5 ? i : (i == 6 ? ASEL_PRIM_LOD_FRAC : ASEL_ZERO); }

struct Combiner {
    int ra[2] = {}, rb[2] = {}, rc[2] = {}, rd[2] = {};
    int ca[2] = {}, cb[2] = {}, cc[2] = {}, cd[2] = {};
    int aa[2] = {}, ab[2] = {}, ac[2] = {}, ad[2] = {};
    uint32_t L = 0, H = 0;
    bool valid = false;

    void decode(uint32_t Lword, uint32_t Hword) {
        for (int cyc = 0; cyc < 2; ++cyc) {
            const bool sc = cyc == 1;
            ra[cyc] = sc ? (Lword >> 5) & 0xF : (Lword >> 20) & 0xF;
            rb[cyc] = sc ? (Hword >> 24) & 0xF : (Hword >> 28) & 0xF;
            rc[cyc] = sc ? (Lword >> 0) & 0x1F : (Lword >> 15) & 0x1F;
            rd[cyc] = sc ? (Hword >> 6) & 0x7 : (Hword >> 15) & 0x7;
            ca[cyc] = cs_a(ra[cyc]);
            cb[cyc] = cs_b(rb[cyc]);
            cc[cyc] = cs_c(rc[cyc]);
            cd[cyc] = cs_d(rd[cyc]);

            const int a_a = sc ? (Hword >> 21) & 0x7 : (Lword >> 12) & 0x7;
            const int a_b = sc ? (Hword >> 3) & 0x7 : (Hword >> 12) & 0x7;
            const int a_c = sc ? (Hword >> 18) & 0x7 : (Lword >> 9) & 0x7;
            const int a_d = sc ? (Hword >> 0) & 0x7 : (Hword >> 9) & 0x7;
            aa[cyc] = as_abd(a_a);
            ab[cyc] = as_abd(a_b);
            ac[cyc] = as_c(a_c);
            ad[cyc] = as_abd(a_d);
        }
        L = Lword;
        H = Hword;
        valid = true;
    }
};

enum BlendPM { BPM_CC = 0, BPM_FRAMEBUFFER_COLOR, BPM_BLEND_COLOR, BPM_FOG_COLOR };
enum BlendA { BA_CC_ALPHA = 0, BA_FOG_ALPHA, BA_SHADE_ALPHA, BA_ZERO };
enum BlendB { BB_ONE_MINUS_A = 0, BB_FRAMEBUFFER_ALPHA, BB_ONE, BB_ZERO };
enum BlendApprox { BAPPROX_NONE = 0, BAPPROX_SQUARE_MIX, BAPPROX_MULTIPLY_MIX };

struct Blender {
    uint16_t inputs = 0;
    int p[2] = {}, m[2] = {}, a[2] = {}, b[2] = {};
    int approx = BAPPROX_NONE;
    bool force_blend = false;
    int cycles = 0;
    int blend_cycles = 0;
    bool alpha_blend = false;
    uint32_t L = 0;

    static int dec_p(uint16_t bi, int c) { return c ? (bi >> 12) & 3 : (bi >> 14) & 3; }
    static int dec_m(uint16_t bi, int c) { return c ? (bi >> 4) & 3 : (bi >> 6) & 3; }
    static int dec_a(uint16_t bi, int c) { return c ? (bi >> 8) & 3 : (bi >> 10) & 3; }
    static int dec_b(uint16_t bi, int c) { return c ? (bi >> 0) & 3 : (bi >> 2) & 3; }

    void decode(uint32_t othermode_l, uint32_t othermode_h) {
        L = othermode_l;
        inputs = static_cast<uint16_t>((othermode_l >> 16) & 0xFFFF);
        for (int c = 0; c < 2; ++c) {
            p[c] = dec_p(inputs, c);
            m[c] = dec_m(inputs, c);
            a[c] = dec_a(inputs, c);
            b[c] = dec_b(inputs, c);
        }
        force_blend = (othermode_l & 0x4000u) != 0;
        const uint32_t cyc = (othermode_h >> 20) & 3u;
        cycles = (cyc == kCyc2) ? 2 : (cyc == kCyc1 ? 1 : 0);
        blend_cycles = force_blend ? cycles : (cycles > 0 ? cycles - 1 : 0);
        approx = check_approximation();
        alpha_blend = compute_uses_alpha_blend();
    }

    int check_approximation() const {
        struct CycReq { bool passthrough = false, numerator_overflow = false, fb = false; };
        CycReq req[2];
        for (int c = 0; c < blend_cycles && c < 2; ++c) {
            const bool any_zero = (a[c] == BA_ZERO) || (b[c] == BB_ZERO);
            const bool dup_1ma = (p[c] == m[c]) && (b[c] == BB_ONE_MINUS_A);
            if (any_zero || dup_1ma) req[c].passthrough = true;
            else if (b[c] != BB_ONE_MINUS_A) req[c].numerator_overflow = true;
            if (p[c] == BPM_FRAMEBUFFER_COLOR || m[c] == BPM_FRAMEBUFFER_COLOR) req[c].fb = true;
        }
        bool simple = true;
        if (req[0].numerator_overflow && req[0].fb) {
            simple = false;
        } else if (blend_cycles == 2) {
            if (req[0].fb && !req[0].passthrough) simple = false;
            else if (req[1].numerator_overflow && req[1].fb) simple = false;
        }
        if (simple || blend_cycles != 2) return BAPPROX_NONE;
        if (p[0] == BPM_CC && m[0] == BPM_FRAMEBUFFER_COLOR && a[0] == BA_CC_ALPHA &&
            b[0] == BB_ONE_MINUS_A && p[1] == BPM_CC && m[1] == BPM_FRAMEBUFFER_COLOR &&
            a[1] == BA_CC_ALPHA && b[1] == BB_ONE_MINUS_A) {
            return BAPPROX_SQUARE_MIX;
        }
        if (p[0] != BPM_FRAMEBUFFER_COLOR && m[0] == BPM_FRAMEBUFFER_COLOR &&
            b[0] == BB_ONE_MINUS_A && p[1] == BPM_CC && m[1] == BPM_FRAMEBUFFER_COLOR &&
            b[1] == BB_ONE_MINUS_A) {
            return BAPPROX_MULTIPLY_MIX;
        }
        return BAPPROX_NONE;
    }

    bool compute_uses_alpha_blend() const {
        auto uses_cycle = [&](int c, bool all_inputs) {
            if (all_inputs) {
                if (p[c] == BPM_FRAMEBUFFER_COLOR && a[c] != BA_ZERO) return true;
                if (m[c] == BPM_FRAMEBUFFER_COLOR && b[c] != BB_ZERO) return true;
                return false;
            }
            return p[c] == BPM_FRAMEBUFFER_COLOR;
        };
        if (cycles >= 2 && uses_cycle(1, force_blend)) return true;
        if (cycles >= 1 && uses_cycle(0, (cycles >= 2) || force_blend)) return true;
        return false;
    }
};

inline void rgba8_to_float4(uint32_t rgba, float out[4]) {
    out[0] = static_cast<float>((rgba >> 24) & 0xFFu) / 255.0f;
    out[1] = static_cast<float>((rgba >> 16) & 0xFFu) / 255.0f;
    out[2] = static_cast<float>((rgba >> 8) & 0xFFu) / 255.0f;
    out[3] = static_cast<float>(rgba & 0xFFu) / 255.0f;
}

} // namespace ogre::dx9rdp
