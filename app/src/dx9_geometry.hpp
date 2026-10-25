#pragma once

// GL/D3D-independent F3DEX2 geometry core for the low-end D3D9 renderer.
// The state transitions mirror web_renderer.cpp: row-vector matrices, N64 Mtx
// 16.16 decode, Vtx byte order, G_TEXTURE scale, viewport and modelview stack.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

#include "gbi.hpp"
#include "dx9_texture.hpp"

namespace ogre::dx9geom {

constexpr int kMaxVertices = 32;

struct Vec4 { float x = 0, y = 0, z = 0, w = 1; };

struct Mat4 {
    float m[16]{};
    static Mat4 identity() {
        Mat4 out{};
        out.m[0] = out.m[5] = out.m[10] = out.m[15] = 1.0f;
        return out;
    }
};

inline Vec4 mul(const Vec4& v, const Mat4& M) {
    return {
        v.x*M.m[0] + v.y*M.m[4] + v.z*M.m[8]  + v.w*M.m[12],
        v.x*M.m[1] + v.y*M.m[5] + v.z*M.m[9]  + v.w*M.m[13],
        v.x*M.m[2] + v.y*M.m[6] + v.z*M.m[10] + v.w*M.m[14],
        v.x*M.m[3] + v.y*M.m[7] + v.z*M.m[11] + v.w*M.m[15]
    };
}

inline Mat4 mul_mat4(const Mat4& A, const Mat4& B) {
    Mat4 out{};
    for (int r = 0; r < 4; ++r) {
        for (int c = 0; c < 4; ++c) {
            float sum = 0.0f;
            for (int k = 0; k < 4; ++k) sum += A.m[r*4+k] * B.m[k*4+c];
            out.m[r*4+c] = sum;
        }
    }
    return out;
}

inline bool read_matrix(const uint8_t* rdram, uint32_t address, Mat4& out) {
    if (!rdram || static_cast<uint64_t>(address) + 64u > gbi::kRdramSize) return false;
    const uint8_t* p = rdram + address;
    for (int r = 0; r < 4; ++r) {
        for (int c = 0; c < 4; ++c) {
            // dx9tex::n64h applies the runtime word-half swap. This is exactly
            // web_renderer.cpp's rd16(index r*4+(c^1)).
            const int off = (r * 4 + c) * 2;
            const int16_t ip = static_cast<int16_t>(dx9tex::n64h(p, off));
            const uint16_t fp = dx9tex::n64h(p + 32, off);
            out.m[r*4+c] = static_cast<float>(ip) + static_cast<float>(fp) / 65536.0f;
        }
    }
    return true;
}

struct RawVertex {
    int16_t x = 0, y = 0, z = 0;
    uint16_t flag = 0;
    int16_t s = 0, t = 0;
    uint8_t r = 255, g = 255, b = 255, a = 255;
};

inline RawVertex read_vertex(const uint8_t* p) {
    RawVertex v;
    v.x = static_cast<int16_t>(dx9tex::n64h(p, 0));
    v.y = static_cast<int16_t>(dx9tex::n64h(p, 2));
    v.z = static_cast<int16_t>(dx9tex::n64h(p, 4));
    v.flag = dx9tex::n64h(p, 6);
    v.s = static_cast<int16_t>(dx9tex::n64h(p, 8));
    v.t = static_cast<int16_t>(dx9tex::n64h(p, 10));
    v.r = dx9tex::n64b(p, 12);
    v.g = dx9tex::n64b(p, 13);
    v.b = dx9tex::n64b(p, 14);
    v.a = dx9tex::n64b(p, 15);
    return v;
}

struct State {
    Mat4 projection = Mat4::identity();
    std::vector<Mat4> modelview_stack{Mat4::identity()};
    RawVertex vertices[kMaxVertices]{};
    uint32_t geometry_mode = 0;
    bool viewport_set = false;
    float view_scale[3] = {1, 1, 1};
    float view_trans[3] = {0, 0, 0};
    int32_t tex_sc = 0, tex_tc = 0;
    float tex_scale_s = 1.0f, tex_scale_t = 1.0f;
    bool texture_on = false;
};

inline void load_vertices(State& st, const uint8_t* rdram, uint32_t address,
                          int start, int count) {
    start = std::clamp(start, 0, kMaxVertices);
    count = std::clamp(count, 0, kMaxVertices - start);
    if (!rdram || static_cast<uint64_t>(address) + static_cast<uint64_t>(count) * 16u >
                      gbi::kRdramSize) return;
    for (int i = 0; i < count; ++i) {
        st.vertices[start + i] = read_vertex(rdram + address + static_cast<uint32_t>(i) * 16u);
    }
}

inline void set_viewport(State& st, const uint8_t* rdram, uint32_t address) {
    if (!rdram || static_cast<uint64_t>(address) + 16u > gbi::kRdramSize) return;
    const uint8_t* p = rdram + address;
    for (int i = 0; i < 3; ++i) {
        st.view_scale[i] = static_cast<float>(static_cast<int16_t>(dx9tex::n64h(p, i*2))) / 4.0f;
        st.view_trans[i] = static_cast<float>(static_cast<int16_t>(dx9tex::n64h(p, 8 + i*2))) / 4.0f;
    }
    st.viewport_set = true;
}

// F3DEX2 stores the PUSH bit inverted in G_MTX (the SDK macro XORs the bit).
// The row-vector renderer also pre-multiplies a newly supplied matrix: the new
// matrix acts on the vertex first. Both details are required to match the
// validated WebGL renderer and RT64; getting either wrong makes OB64's per-object
// matrices accumulate and progressively moves geometry off-screen.
inline void apply_matrix(State& st, const Mat4& mat, uint32_t stored_flags) {
    const uint32_t flags = stored_flags ^ gbi::MTX_PUSH;
    const bool projection = (flags & gbi::MTX_PROJECTION) != 0;
    const bool load = (flags & gbi::MTX_LOAD) != 0;
    const bool push = (flags & gbi::MTX_PUSH) != 0;
    if (projection) {
        st.projection = load ? mat : mul_mat4(mat, st.projection);
        return;
    }
    if (st.modelview_stack.empty()) st.modelview_stack.push_back(Mat4::identity());
    if (push && st.modelview_stack.size() < 32) {
        const Mat4 saved = st.modelview_stack.back();
        st.modelview_stack.push_back(saved);
    }
    Mat4& cur = st.modelview_stack.back();
    cur = load ? mat : mul_mat4(mat, cur);
}

inline void pop_modelview(State& st, uint32_t count) {
    while (count-- && st.modelview_stack.size() > 1) st.modelview_stack.pop_back();
}

inline void set_texture(State& st, uint32_t w0, uint32_t w1) {
    st.tex_sc = static_cast<int32_t>((w1 >> 16) & 0xFFFFu);
    st.tex_tc = static_cast<int32_t>(w1 & 0xFFFFu);
    st.tex_scale_s = static_cast<float>(st.tex_sc) / 65536.0f;
    st.tex_scale_t = static_cast<float>(st.tex_tc) / 65536.0f;
    st.texture_on = ((w0 >> 1) & 0x7Fu) != 0;
}

struct TransformedVertex {
    float x = 0, y = 0, z = 0, rhw = 1;
    float s = 0, t = 0;
    uint8_t r = 255, g = 255, b = 255, a = 255;
    bool valid = false;
};

inline TransformedVertex transform_vertex(const State& st, int index,
                                          int fallback_width, int fallback_height) {
    TransformedVertex out;
    if (index < 0 || index >= kMaxVertices || st.modelview_stack.empty()) return out;
    const RawVertex& src = st.vertices[index];
    Vec4 pos{static_cast<float>(src.x), static_cast<float>(src.y), static_cast<float>(src.z), 1.0f};
    pos = mul(pos, st.modelview_stack.back());
    pos = mul(pos, st.projection);
    // Match the validated WebGL path: geometry at/behind the camera is rejected.
    if (!std::isfinite(pos.w) || pos.w <= 0.0f) return out;
    const float inv_w = 1.0f / pos.w;
    const float nx = pos.x * inv_w;
    const float ny = pos.y * inv_w;
    const float nz = pos.z * inv_w;
    if (!std::isfinite(nx) || !std::isfinite(ny) || !std::isfinite(nz)) return out;

    // RSP screen Y points down. web_renderer maps scr_y = -NDC.y*scale + trans;
    // D3D9 pretransformed screen coordinates already use Y-down, so retain that
    // screen value directly rather than converting back through GL NDC.
    if (st.viewport_set) {
        out.x = nx * st.view_scale[0] + st.view_trans[0];
        out.y = -ny * st.view_scale[1] + st.view_trans[1];
        out.z = nz * st.view_scale[2] + st.view_trans[2];
    } else {
        out.x = (nx * 0.5f + 0.5f) * static_cast<float>(std::max(1, fallback_width));
        out.y = (-ny * 0.5f + 0.5f) * static_cast<float>(std::max(1, fallback_height));
        out.z = nz * 0.5f + 0.5f;
    }
    out.rhw = inv_w;
    out.s = (static_cast<float>(src.s) * st.tex_scale_s) / 32.0f;
    out.t = (static_cast<float>(src.t) * st.tex_scale_t) / 32.0f;
    out.r = src.r; out.g = src.g; out.b = src.b; out.a = src.a;
    out.valid = std::isfinite(out.x) && std::isfinite(out.y) && std::isfinite(out.rhw);
    return out;
}

inline uint32_t shade_argb(const TransformedVertex& v) {
    return (static_cast<uint32_t>(v.a) << 24) |
           (static_cast<uint32_t>(v.r) << 16) |
           (static_cast<uint32_t>(v.g) << 8) |
           static_cast<uint32_t>(v.b);
}

inline void decode_tri_word(uint32_t w, int& i0, int& i1, int& i2) {
    i0 = static_cast<int>(((w >> 16) & 0xFFu) >> 1);
    i1 = static_cast<int>(((w >> 8) & 0xFFu) >> 1);
    i2 = static_cast<int>((w & 0xFFu) >> 1);
}

} // namespace ogre::dx9geom
