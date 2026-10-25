#pragma once

// GL-independent N64 texture state/decoder used by the Direct3D 9 low-end
// renderer. Semantics are ported from web_renderer.cpp, whose F3DEX2/RDP path
// has already been validated against RT64. This header deliberately owns no
// D3D objects: the backend keeps one upload texture per RDP tile (8 maximum).

#include <algorithm>
#include <cstdint>
#include <vector>

#include "gbi.hpp"

namespace ogre::dx9tex {

constexpr int kMaxTiles = 8;

inline uint16_t rd16(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 0) | (p[1] << 8));
}
inline uint16_t n64h(const uint8_t* p, int off) { return rd16(p + (off ^ 2)); }
inline uint8_t n64b(const uint8_t* p, int off) { return p[off ^ 3]; }
inline uint16_t n64be16(const uint8_t* p, uint32_t addr) {
    return static_cast<uint16_t>((n64b(p, static_cast<int>(addr)) << 8) |
                                 n64b(p, static_cast<int>(addr) + 1));
}

inline int bytes_per_texel(uint8_t siz) {
    switch (siz) {
        case gbi::IM_SIZ_4b: return 0;
        case gbi::IM_SIZ_8b: return 1;
        case gbi::IM_SIZ_16b: return 2;
        case gbi::IM_SIZ_32b: return 4;
        default: return 1;
    }
}

inline void rgba16_to_rgba8(uint16_t v, uint8_t out[4]) {
    const uint32_t r = (v >> 11) & 0x1F;
    const uint32_t g = (v >> 6) & 0x1F;
    const uint32_t b = (v >> 1) & 0x1F;
    out[0] = static_cast<uint8_t>((r << 3) | (r >> 2));
    out[1] = static_cast<uint8_t>((g << 3) | (g >> 2));
    out[2] = static_cast<uint8_t>((b << 3) | (b >> 2));
    out[3] = (v & 1) ? 255 : 0;
}

inline void ia16_to_rgba8(uint16_t v, uint8_t out[4]) {
    const uint8_t i = static_cast<uint8_t>(v >> 8);
    const uint8_t a = static_cast<uint8_t>(v & 0xFF);
    out[0] = out[1] = out[2] = i;
    out[3] = a;
}

inline void yuv16_to_rgba8(uint8_t y, uint8_t u, uint8_t v, const int32_t* convert_k,
                           uint8_t out[4]) {
    auto sext9 = [](int32_t k) -> float {
        const int32_t m = k & 0x1FF;
        return static_cast<float>((m >= 256) ? (m - 512) : m);
    };
    static const int32_t kJpeg[4] = {175, 469, 423, 222};
    if ((convert_k[0] + convert_k[1] + convert_k[2] + convert_k[3]) == 0) {
        convert_k = kJpeg;
    }
    const float k0 = 2.0f * sext9(convert_k[0]) + 1.0f;
    const float k1 = 2.0f * sext9(convert_k[1]) + 1.0f;
    const float k2 = 2.0f * sext9(convert_k[2]) + 1.0f;
    const float k3 = 2.0f * sext9(convert_k[3]) + 1.0f;
    const float yf = static_cast<float>(y);
    const float uf = static_cast<float>(u) - 128.0f;
    const float vf = static_cast<float>(v) - 128.0f;
    auto clamp255 = [](float c) -> uint8_t {
        c = std::clamp(c, 0.0f, 255.0f);
        return static_cast<uint8_t>(c + 0.5f);
    };
    out[0] = clamp255(yf + (k0 * vf) / 256.0f);
    out[1] = clamp255(yf + (k1 * uf + k2 * vf) / 256.0f);
    out[2] = clamp255(yf + (k3 * uf) / 256.0f);
    out[3] = 255;
}

struct TileState {
    uint8_t fmt = 0, siz = 0;
    uint16_t line = 0, tmem = 0;
    uint8_t palette = 0;
    uint8_t cmt = 0, cms = 0;
    uint8_t maskt = 0, masks = 0;
    uint8_t shiftt = 0, shifts = 0;
    uint16_t uls = 0, ult = 0, lrs = 0, lrt = 0;

    uint32_t image_address = 0;
    int image_stride = 0;
    bool image_source_valid = false;
    uint64_t source_generation = 0;
};

struct TextureState {
    uint32_t timg_address = 0;
    uint8_t timg_fmt = 0, timg_siz = 0;
    uint16_t timg_width = 0;
    TileState tiles[kMaxTiles]{};
    int active_tile = 0;
    int32_t convert_k[6] = {0, 0, 0, 0, 0, 0};

    struct PendingLoad {
        uint32_t address = 0;
        int stride = 0;
        int load_tile = -1;
        uint64_t generation = 0;
        bool valid = false;
    } pending_load;
};

inline void set_tile_image(TextureState& st, int tile, uint32_t address, int stride,
                           uint64_t generation) {
    TileState& t = st.tiles[tile & (kMaxTiles - 1)];
    t.image_address = address;
    t.image_stride = stride;
    t.image_source_valid = address != 0 && stride > 0;
    t.source_generation = generation;
}

inline void note_tile_load(TextureState& st, int tile, uint64_t generation) {
    const int stride = static_cast<int>(st.timg_width) << st.timg_siz >> 1;
    st.pending_load.address = st.timg_address;
    st.pending_load.stride = stride;
    st.pending_load.load_tile = tile;
    st.pending_load.generation = generation;
    st.pending_load.valid = true;
    set_tile_image(st, tile, st.timg_address, stride, generation);
}

inline void claim_tile_load(TextureState& st, int tile) {
    if (!st.pending_load.valid || tile == st.pending_load.load_tile) return;
    set_tile_image(st, tile, st.pending_load.address, st.pending_load.stride,
                   st.pending_load.generation);
    st.pending_load.valid = false;
}

inline int tile_width(const TileState& t) {
    const int x0 = t.uls >> 2;
    const int x1 = t.lrs >> 2;
    return std::max(1, x1 - x0 + 1);
}
inline int tile_height(const TileState& t) {
    const int y0 = t.ult >> 2;
    const int y1 = t.lrt >> 2;
    return std::max(1, y1 - y0 + 1);
}

// Decode [x0,x0+w) x [y0,y0+h) from the tile's source image to RGBA8.
// CI without texture-LUT mode is reinterpreted as intensity, matching RT64.
inline void decode_texture_rect(const uint8_t* rdram, uint32_t timg_address,
                                uint8_t fmt, uint8_t siz, int row_bytes,
                                int x0, int y0, int w, int h,
                                const uint16_t* tlut, bool tlut_valid,
                                uint8_t palette, bool palette_enabled,
                                const int32_t* convert_k,
                                std::vector<uint8_t>& out) {
    out.assign(static_cast<size_t>(w) * h * 4, 0);
    if (!rdram || row_bytes <= 0 || w <= 0 || h <= 0) return;
    if (fmt == gbi::IM_FMT_CI && !palette_enabled) fmt = gbi::IM_FMT_I;
    const int bpp = bytes_per_texel(siz);

    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            const int tx = x0 + x;
            const int ty = y0 + y;
            uint8_t rgba[4] = {0, 0, 0, 255};

            if (fmt == gbi::IM_FMT_YUV && siz == gbi::IM_SIZ_16b) {
                const uint32_t word_addr = timg_address +
                    static_cast<uint32_t>(ty * row_bytes + (tx >> 1) * 4);
                if (word_addr + 3 < gbi::kRdramSize) {
                    const uint8_t yy = (tx & 1) ? n64b(rdram, static_cast<int>(word_addr) + 3)
                                                : n64b(rdram, static_cast<int>(word_addr) + 1);
                    const uint8_t u = n64b(rdram, static_cast<int>(word_addr));
                    const uint8_t v = n64b(rdram, static_cast<int>(word_addr) + 2);
                    yuv16_to_rgba8(yy, u, v, convert_k, rgba);
                }
            } else if (siz == gbi::IM_SIZ_4b) {
                const uint32_t byte_addr = timg_address +
                    static_cast<uint32_t>(ty * row_bytes + tx / 2);
                if (byte_addr < gbi::kRdramSize) {
                    const uint8_t byte = n64b(rdram, static_cast<int>(byte_addr));
                    const uint8_t nib = (tx & 1) ? (byte & 0xF) : (byte >> 4);
                    if (fmt == gbi::IM_FMT_IA) {
                        const uint8_t i = static_cast<uint8_t>((nib >> 1) * 255 / 7);
                        rgba[0] = rgba[1] = rgba[2] = i;
                        rgba[3] = (nib & 1) ? 255 : 0;
                    } else if (fmt == gbi::IM_FMT_I) {
                        const uint8_t i = static_cast<uint8_t>(nib * 255 / 15);
                        rgba[0] = rgba[1] = rgba[2] = rgba[3] = i;
                    } else if (fmt == gbi::IM_FMT_CI && tlut_valid) {
                        const uint16_t e = tlut[static_cast<unsigned>(palette) * 16u + nib];
                        if ((e >> 15) & 1) rgba16_to_rgba8(e, rgba);
                        else ia16_to_rgba8(e, rgba);
                    }
                }
            } else {
                const uint32_t byte_addr = timg_address +
                    static_cast<uint32_t>(ty * row_bytes + tx * bpp);
                if (byte_addr < gbi::kRdramSize) {
                    if (siz == gbi::IM_SIZ_8b) {
                        const uint8_t v = n64b(rdram, static_cast<int>(byte_addr));
                        if (fmt == gbi::IM_FMT_IA) {
                            const uint8_t i = static_cast<uint8_t>((v >> 4) * 255 / 15);
                            const uint8_t a = static_cast<uint8_t>((v & 0xF) * 255 / 15);
                            rgba[0] = rgba[1] = rgba[2] = i;
                            rgba[3] = a;
                        } else if (fmt == gbi::IM_FMT_I) {
                            rgba[0] = rgba[1] = rgba[2] = rgba[3] = v;
                        } else if (fmt == gbi::IM_FMT_CI && tlut_valid) {
                            const uint16_t e = tlut[v];
                            if ((e >> 15) & 1) rgba16_to_rgba8(e, rgba);
                            else ia16_to_rgba8(e, rgba);
                        }
                    } else if (siz == gbi::IM_SIZ_16b && byte_addr + 1 < gbi::kRdramSize) {
                        const uint16_t v = n64be16(rdram, byte_addr);
                        if (fmt == gbi::IM_FMT_IA) ia16_to_rgba8(v, rgba);
                        else rgba16_to_rgba8(v, rgba);
                    } else if (siz == gbi::IM_SIZ_32b && byte_addr + 3 < gbi::kRdramSize) {
                        const uint16_t hi = n64be16(rdram, byte_addr);
                        const uint16_t lo = n64be16(rdram, byte_addr + 2);
                        rgba[0] = static_cast<uint8_t>(hi & 0xFF);
                        rgba[1] = static_cast<uint8_t>(lo >> 8);
                        rgba[2] = static_cast<uint8_t>(lo & 0xFF);
                        rgba[3] = static_cast<uint8_t>(hi >> 8);
                    }
                }
            }

            const size_t o = (static_cast<size_t>(y) * w + x) * 4;
            out[o + 0] = rgba[0];
            out[o + 1] = rgba[1];
            out[o + 2] = rgba[2];
            out[o + 3] = rgba[3];
        }
    }
}

}  // namespace ogre::dx9tex
