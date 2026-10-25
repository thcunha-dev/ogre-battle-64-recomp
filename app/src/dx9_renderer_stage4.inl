// Ogre Battle 64: Person of Lordly Caliber - Direct3D 9 low-end renderer.
// Stage 4: guest colour targets + fillrect + bounded texture decode +
// COPY/1-cycle/2-cycle TEXRECT through one precompiled ps_3_0 RDP shader.

#include "renderer.hpp"
#include "dx9_texture.hpp"
#include "dx9_rdp_state.hpp"
#include "dx9_shader.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <d3d9.h>

#if defined(_MSC_VER) || defined(__clang__)
#pragma comment(lib, "d3d9.lib")
#endif

#include "ultramodern/renderer_context.hpp"
#include "ultramodern/ultramodern.hpp"
#include "gbi.hpp"
#include "milestones.hpp"

namespace ogre {
namespace {

gbi::WorkloadStats g_workload;
std::mutex g_stats_mutex;
char g_stats_snapshot[4096] = {};

void refresh_stats_snapshot() {
    const std::string summary = gbi::format_summary(g_workload);
    snprintf(g_stats_snapshot, sizeof(g_stats_snapshot), "%s", summary.c_str());
}

struct ViSize { int width = 0; int height = 0; };

inline bool vi_visible(const ultramodern::renderer::ViRegs& r) {
    return ((r.VI_STATUS_REG & 3u) != 0u) && (((r.VI_H_START_REG >> 16) & 0x3FFu) > 0u);
}

inline ViSize vi_framebuffer_size(const ultramodern::renderer::ViRegs& r) {
    ViSize out;
    const uint32_t width = r.VI_WIDTH_REG;
    if (!width) return out;
    const uint32_t xs = r.VI_X_SCALE_REG & 0xFFFu;
    const uint32_t ys = r.VI_Y_SCALE_REG & 0xFFFu;
    if (!xs || !ys) return out;
    const uint32_t hs = (r.VI_H_START_REG >> 16) & 0x3FFu;
    const uint32_t he = r.VI_H_START_REG & 0x3FFu;
    const uint32_t vs = (r.VI_V_START_REG >> 16) & 0x3FFu;
    const uint32_t ve = r.VI_V_START_REG & 0x3FFu;
    if (he <= hs || ve <= vs) return out;
    const float xscale = 1024.0f / static_cast<float>(xs);
    const float yscale = 1024.0f / static_cast<float>(ys);
    int sx = static_cast<int>(width);
    if ((r.VI_STATUS_REG & 0x40u) != 0u) {
        const float estimate = static_cast<float>(he - hs) / xscale;
        if (estimate < static_cast<float>(width) / 1.875f) sx /= 2;
    }
    const float ratio = static_cast<float>(sx) / static_cast<float>(width);
    if (ratio <= 0.0f) return out;
    int sy = static_cast<int>(std::lround(static_cast<float>(ve - vs) /
                                          (2.0f * yscale * ratio)));
    if (sx <= 0 || sy <= 0) return out;
    sy += 2;
    sy = static_cast<int>(std::lround(static_cast<float>(sy) / 4.0f)) * 4;
    if (sx > 2048 || sy > 2048) return {};
    return {sx, sy};
}

inline int overscan_crop() {
    static const int crop = [] {
        const char* v = getenv("OGRE_OVERSCAN");
        return std::clamp(v ? atoi(v) : 1, 0, 8);
    }();
    return crop;
}
inline ViSize visible_framebuffer_size(const ViSize& in) {
    const int c = overscan_crop();
    return {(in.width > c) ? in.width - c : in.width,
            (in.height > c) ? in.height - c : in.height};
}

inline uint16_t rd16(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 0) | (p[1] << 8));
}
inline uint16_t n64h(const uint8_t* p, int off) { return rd16(p + (off ^ 2)); }
inline uint8_t n64b(const uint8_t* p, int off) { return p[off ^ 3]; }
inline uint32_t p0(uint32_t w, uint8_t pos, uint8_t bits) {
    if (bits >= 32) return w;
    return (w >> pos) & ((1u << bits) - 1u);
}
inline uint32_t fb_bpp(uint8_t siz) { return siz == gbi::IM_SIZ_32b ? 4u : 2u; }

inline void rgba16_to_bgra8(uint16_t v, uint8_t* out) {
    const uint32_t r = (v >> 11) & 31u, g = (v >> 6) & 31u, b = (v >> 1) & 31u;
    out[0] = static_cast<uint8_t>((b << 3) | (b >> 2));
    out[1] = static_cast<uint8_t>((g << 3) | (g >> 2));
    out[2] = static_cast<uint8_t>((r << 3) | (r >> 2));
    out[3] = (v & 1u) ? 255 : 0;
}

inline void set_rgba(float out[4], uint32_t w) {
    out[0] = static_cast<float>((w >> 24) & 0xFFu) / 255.0f;
    out[1] = static_cast<float>((w >> 16) & 0xFFu) / 255.0f;
    out[2] = static_cast<float>((w >> 8) & 0xFFu) / 255.0f;
    out[3] = static_cast<float>(w & 0xFFu) / 255.0f;
}

constexpr int kMaxFramebufferSide = 1024;
constexpr DWORD kCopyFvf = D3DFVF_XYZRHW | D3DFVF_TEX1;
constexpr DWORD kRdpFvf = D3DFVF_XYZRHW | D3DFVF_DIFFUSE | D3DFVF_TEX2;

struct CopyVertex { float x, y, z, rhw, u, v; };
struct RdpVertex {
    float x, y, z, rhw;
    DWORD diffuse;
    float u0, v0;
    float u1, v1;
};

struct RdpState {
    uint32_t othermode_h = 0, othermode_l = 0;
    uint32_t fill_color = 0;
    bool scissor_enabled = false;
    int scissor_x0 = 0, scissor_y0 = 0, scissor_x1 = 0, scissor_y1 = 0;
    uint32_t cimg_address = 0, cimg_row_bytes = 0;
    uint16_t cimg_width = 0;
    uint8_t cimg_siz = 0, cimg_fmt = 0;
    dx9tex::TextureState tex;
    dx9rdp::Combiner combiner;
    dx9rdp::Blender blender;
    float prim[4] = {1, 1, 1, 1};
    float env[4] = {1, 1, 1, 1};
    float fog[4] = {0, 0, 0, 1};
    float blend[4] = {0, 0, 0, 0};
};

struct Dx9Framebuffer {
    IDirect3DTexture9* texture = nullptr;
    IDirect3DSurface9* surface = nullptr;
    int width = 0, height = 0;
    uint8_t siz = 0, fmt = 0;
    uint32_t row_bytes = 0;
    bool dirty = false;
    uint32_t last_write_seq = 0;
};

struct TileGpu {
    IDirect3DTexture9* texture = nullptr;
    int width = 0, height = 0;
    int origin_s = 0, origin_t = 0;
    uint8_t fmt = 0, siz = 0;
    uint64_t source_generation = 0, palette_stamp = 0;
};

class DX9Renderer final : public ultramodern::renderer::RendererContext {
  public:
    DX9Renderer(uint8_t* rdram, ultramodern::renderer::WindowHandle window_handle)
        : rdram_(rdram), hwnd_(reinterpret_cast<HWND>(window_handle.window)) {
        setup_result = ultramodern::renderer::SetupResult::Success;
        chosen_api = ultramodern::renderer::GraphicsApi::Auto;
        if (!hwnd_) return;
        d3d_ = Direct3DCreate9(D3D_SDK_VERSION);
        if (!d3d_) return;

        D3DCAPS9 caps{};
        if (SUCCEEDED(d3d_->GetDeviceCaps(D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, &caps))) {
            sm3_supported_ = caps.PixelShaderVersion >= D3DPS_VERSION(3, 0);
            fprintf(stderr,
                    "[dx9] caps: VS=%u.%u PS=%u.%u maxTexture=%ux%u HW-T&L=%d SM3=%d\n",
                    static_cast<unsigned>(D3DSHADER_VERSION_MAJOR(caps.VertexShaderVersion)),
                    static_cast<unsigned>(D3DSHADER_VERSION_MINOR(caps.VertexShaderVersion)),
                    static_cast<unsigned>(D3DSHADER_VERSION_MAJOR(caps.PixelShaderVersion)),
                    static_cast<unsigned>(D3DSHADER_VERSION_MINOR(caps.PixelShaderVersion)),
                    static_cast<unsigned>(caps.MaxTextureWidth), static_cast<unsigned>(caps.MaxTextureHeight),
                    (caps.DevCaps & D3DDEVCAPS_HWTRANSFORMANDLIGHT) ? 1 : 0,
                    sm3_supported_ ? 1 : 0);
        }
        if (!create_device()) return;
        configure_fixed_state();
        create_white_texture();
        if (sm3_supported_) rdp_shader_ = dx9shader::create_rdp_pixel_shader(device_);
        OGRE_MILESTONE("RENDERER", "Direct3D 9 low-end renderer initialized (RDP stage 4, SM3=%d)",
                       rdp_shader_ ? 1 : 0);
    }

    ~DX9Renderer() override {
        std::lock_guard<std::mutex> lock(device_mutex_);
        release_default_pool_resources(false);
        release_tile_textures();
        if (white_tex_) { white_tex_->Release(); white_tex_ = nullptr; }
        if (rdp_shader_) { rdp_shader_->Release(); rdp_shader_ = nullptr; }
        if (device_) { device_->Release(); device_ = nullptr; }
        if (d3d_) { d3d_->Release(); d3d_ = nullptr; }
    }

    bool valid() override { return device_ != nullptr; }
    bool update_config(const ultramodern::renderer::GraphicsConfig& old_config,
                       const ultramodern::renderer::GraphicsConfig& new_config) override {
        return old_config != new_config;
    }
    void enable_instant_present() override { instant_present_ = true; }

    void send_dl(const OSTask* task) override {
        const unsigned frame = ++display_list_count_;
        if (rdram_) {
            const uint32_t dl = task->t.data_ptr & 0x3FFFFFFu;
            {
                std::lock_guard<std::mutex> stats_lock(g_stats_mutex);
                gbi::analyze_dl(rdram_, dl, task->t.data_size, g_workload);
                refresh_stats_snapshot();
            }
            std::lock_guard<std::mutex> device_lock(device_mutex_);
            if (reset_device_if_needed()) {
                const uint32_t ucode = static_cast<uint32_t>(task->t.ucode) & 0x1FFFFFFFu;
                execute_rdp(dl, ucode == 0x000A5110u);
            }
        }
        if (frame <= 8 || (frame % 300) == 0) {
            OGRE_MILESTONE("DX9-DL",
                           "dl=%u fills=%u copyRects=%u shaderRects=%u skipped=%u texUploads=%u fbs=%zu",
                           frame, fill_count_, copy_texrect_count_, shader_texrect_count_,
                           skipped_texrect_count_, texture_upload_count_, framebuffers_.size());
        }
        if (instant_present_) present_vi();
    }

    void send_dummy_workload(uint32_t fb_address) override { last_dummy_fb_ = fb_address & 0xFFFFFFu; }
    void update_screen() override { ++vi_swap_count_; present_vi(); }
    void shutdown() override {
        sync_framebuffers();
        std::lock_guard<std::mutex> stats_lock(g_stats_mutex);
        refresh_stats_snapshot();
        OGRE_MILESTONE("RENDERER",
                       "DX9 stage4 shutdown: DL=%u VI=%u fills=%u copyRects=%u shaderRects=%u skipped=%u",
                       display_list_count_.load(), vi_swap_count_.load(), fill_count_,
                       copy_texrect_count_, shader_texrect_count_, skipped_texrect_count_);
        OGRE_MILESTONE("GFX-WORKLOAD", "%s", g_stats_snapshot);
    }
    uint32_t get_display_framerate() const override { return 60; }
    float get_resolution_scale() const override { return 1.0f; }

    void sync_framebuffers() {
        std::lock_guard<std::mutex> lock(device_mutex_);
        if (device_) writeback_all_framebuffers();
    }

  private:
    struct ExecCtx {
        DX9Renderer* self = nullptr;
        RdpState state{};
        uint32_t segments[16] = {};
        bool s2dex = false;
        bool pending_texrect = false, pending_flip = false, have_half1 = false;
        uint32_t rect_w0 = 0, rect_w1 = 0, half1 = 0;
    };

    bool client_size(UINT& w, UINT& h) const {
        RECT r{};
        if (!hwnd_ || !GetClientRect(hwnd_, &r)) return false;
        const LONG cw = r.right - r.left, ch = r.bottom - r.top;
        if (cw <= 0 || ch <= 0) return false;
        w = static_cast<UINT>(cw); h = static_cast<UINT>(ch); return true;
    }

    bool create_device() {
        UINT w = 640, h = 480;
        client_size(w, h);
        memset(&pp_, 0, sizeof(pp_));
        pp_.Windowed = TRUE;
        pp_.SwapEffect = D3DSWAPEFFECT_DISCARD;
        pp_.hDeviceWindow = hwnd_;
        pp_.BackBufferFormat = D3DFMT_UNKNOWN;
        pp_.BackBufferWidth = w; pp_.BackBufferHeight = h; pp_.BackBufferCount = 1;
        pp_.EnableAutoDepthStencil = FALSE;
        pp_.PresentationInterval = D3DPRESENT_INTERVAL_ONE;
        const DWORD common = D3DCREATE_FPU_PRESERVE | D3DCREATE_MULTITHREADED;
        HRESULT hr = d3d_->CreateDevice(D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd_,
            common | D3DCREATE_HARDWARE_VERTEXPROCESSING, &pp_, &device_);
        if (FAILED(hr)) {
            hr = d3d_->CreateDevice(D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd_,
                common | D3DCREATE_SOFTWARE_VERTEXPROCESSING, &pp_, &device_);
        }
        if (FAILED(hr) || !device_) return false;
        backbuffer_width_ = w; backbuffer_height_ = h; return true;
    }

    void configure_fixed_state() {
        if (!device_) return;
        device_->SetRenderState(D3DRS_LIGHTING, FALSE);
        device_->SetRenderState(D3DRS_ZENABLE, FALSE);
        device_->SetRenderState(D3DRS_ZWRITEENABLE, FALSE);
        device_->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
        device_->SetRenderState(D3DRS_DITHERENABLE, TRUE);
        device_->SetRenderState(D3DRS_SCISSORTESTENABLE, FALSE);
        device_->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
        for (DWORD s = 0; s < 2; ++s) {
            device_->SetSamplerState(s, D3DSAMP_MINFILTER, D3DTEXF_POINT);
            device_->SetSamplerState(s, D3DSAMP_MAGFILTER, D3DTEXF_POINT);
            device_->SetSamplerState(s, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
            device_->SetSamplerState(s, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP);
            device_->SetSamplerState(s, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);
        }
        device_->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
        device_->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
        device_->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_SELECTARG1);
        device_->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_TEXTURE);
        device_->SetTextureStageState(1, D3DTSS_COLOROP, D3DTOP_DISABLE);
    }

    bool create_white_texture() {
        if (white_tex_) return true;
        HRESULT hr = device_->CreateTexture(1, 1, 1, 0, D3DFMT_A8R8G8B8,
                                            D3DPOOL_MANAGED, &white_tex_, nullptr);
        if (FAILED(hr) || !white_tex_) return false;
        D3DLOCKED_RECT lr{};
        if (FAILED(white_tex_->LockRect(0, &lr, nullptr, 0))) return false;
        *static_cast<DWORD*>(lr.pBits) = 0xFFFFFFFFu;
        white_tex_->UnlockRect(0);
        return true;
    }

    void release_scanout() {
        if (scanout_tex_) { scanout_tex_->Release(); scanout_tex_ = nullptr; }
        scanout_w_ = scanout_h_ = 0;
    }
    static void release_fb(Dx9Framebuffer& fb) {
        if (fb.surface) { fb.surface->Release(); fb.surface = nullptr; }
        if (fb.texture) { fb.texture->Release(); fb.texture = nullptr; }
        fb.dirty = false;
    }
    void release_tile_textures() {
        for (auto& t : tile_gpu_) {
            if (t.texture) t.texture->Release();
            t = TileGpu{};
        }
    }
    void release_default_pool_resources(bool writeback) {
        if (writeback) writeback_all_framebuffers();
        release_scanout();
        for (auto& kv : framebuffers_) release_fb(kv.second);
        framebuffers_.clear();
    }

    bool reset_device_if_needed() {
        if (!device_) return false;
        const HRESULT coop = device_->TestCooperativeLevel();
        if (coop == D3DERR_DEVICELOST) return false;
        UINT w = backbuffer_width_, h = backbuffer_height_;
        if (!client_size(w, h)) return false;
        const bool resize = w != backbuffer_width_ || h != backbuffer_height_;
        if (coop != D3DERR_DEVICENOTRESET && !resize) return true;
        release_default_pool_resources(coop != D3DERR_DEVICENOTRESET);
        pp_.BackBufferWidth = w; pp_.BackBufferHeight = h;
        if (FAILED(device_->Reset(&pp_))) return false;
        backbuffer_width_ = w; backbuffer_height_ = h;
        configure_fixed_state();
        return true;
    }

    void decode_guest_row(uint32_t address, uint32_t pitch, int y, int width,
                          uint8_t siz, uint8_t* dst) const {
        const uint64_t row_addr = static_cast<uint64_t>(address) + static_cast<uint64_t>(y) * pitch;
        if (!rdram_ || row_addr + pitch > gbi::kRdramSize) {
            memset(dst, 0, static_cast<size_t>(width) * 4); return;
        }
        const uint8_t* src = rdram_ + row_addr;
        for (int x = 0; x < width; ++x) {
            uint8_t* d = dst + x * 4;
            if (siz == gbi::IM_SIZ_32b) {
                const int off = x * 4;
                d[0] = n64b(src, off + 2); d[1] = n64b(src, off + 1);
                d[2] = n64b(src, off + 0); d[3] = n64b(src, off + 3);
            } else rgba16_to_bgra8(n64h(src, x * 2), d);
        }
    }

    bool init_fb_from_rdram(Dx9Framebuffer& fb, uint32_t address) {
        IDirect3DSurface9* sys = nullptr;
        HRESULT hr = device_->CreateOffscreenPlainSurface(static_cast<UINT>(fb.width),
            static_cast<UINT>(fb.height), D3DFMT_A8R8G8B8, D3DPOOL_SYSTEMMEM, &sys, nullptr);
        if (FAILED(hr) || !sys) return false;
        D3DLOCKED_RECT lr{};
        if (SUCCEEDED(sys->LockRect(&lr, nullptr, 0))) {
            for (int y = 0; y < fb.height; ++y) {
                auto* dst = static_cast<uint8_t*>(lr.pBits) + static_cast<size_t>(y) * lr.Pitch;
                decode_guest_row(address, fb.row_bytes, y, fb.width, fb.siz, dst);
            }
            sys->UnlockRect();
            hr = device_->UpdateSurface(sys, nullptr, fb.surface, nullptr);
        }
        sys->Release(); return SUCCEEDED(hr);
    }

    int target_height(const RdpState& st, int bottom) const {
        int h = std::max(1, bottom);
        if (st.scissor_enabled) h = std::max(h, st.scissor_y1);
        if (auto* vi = ultramodern::renderer::get_vi_regs()) {
            const ViSize s = vi_framebuffer_size(*vi);
            if (vi_visible(*vi) && s.height > 0) h = std::max(h, s.height);
        }
        if (h < 240 && st.cimg_width == 320) h = 240;
        return std::clamp(h, 1, kMaxFramebufferSide);
    }

    Dx9Framebuffer* ensure_fb(const RdpState& st, int bottom) {
        if (!st.cimg_address || !st.cimg_width ||
            (st.cimg_siz != gbi::IM_SIZ_16b && st.cimg_siz != gbi::IM_SIZ_32b)) return nullptr;
        const int w = std::clamp<int>(st.cimg_width, 1, kMaxFramebufferSide);
        int h = target_height(st, bottom);
        const uint32_t pitch = st.cimg_row_bytes ? st.cimg_row_bytes
                                                 : (static_cast<uint32_t>(w) << st.cimg_siz >> 1);
        Dx9Framebuffer& fb = framebuffers_[st.cimg_address];
        if (fb.texture && fb.width == w && fb.siz == st.cimg_siz &&
            fb.row_bytes == pitch && fb.height >= h) return &fb;
        if (fb.texture) {
            if (fb.dirty) writeback_framebuffer(st.cimg_address, fb);
            h = std::max(h, fb.height); release_fb(fb);
        }
        fb.width = w; fb.height = h; fb.siz = st.cimg_siz; fb.fmt = st.cimg_fmt; fb.row_bytes = pitch;
        HRESULT hr = device_->CreateTexture(static_cast<UINT>(w), static_cast<UINT>(h), 1,
            D3DUSAGE_RENDERTARGET, D3DFMT_A8R8G8B8, D3DPOOL_DEFAULT, &fb.texture, nullptr);
        if (FAILED(hr) || !fb.texture) return nullptr;
        if (FAILED(fb.texture->GetSurfaceLevel(0, &fb.surface)) || !fb.surface) {
            release_fb(fb); return nullptr;
        }
        init_fb_from_rdram(fb, st.cimg_address);
        return &fb;
    }

    static DWORD address_mode(uint8_t mode) {
        if (mode & 2u) return D3DTADDRESS_CLAMP;
        if (mode & 1u) return D3DTADDRESS_MIRROR;
        return D3DTADDRESS_WRAP;
    }

    bool ensure_tile(RdpState& st, int index) {
        const int ti = index & 7;
        dx9tex::TileState& t = st.tex.tiles[ti];
        if (!t.image_source_valid || t.image_stride <= 0) return false;
        const int x0 = t.uls >> 2, y0 = t.ult >> 2;
        const int w = dx9tex::tile_width(t), h = dx9tex::tile_height(t);
        if (w <= 0 || h <= 0 || w > 1024 || h > 1024) return false;
        const bool palette_enabled = (st.othermode_h & 0xC000u) != 0;
        const uint64_t pal_stamp = t.fmt == gbi::IM_FMT_CI
            ? (tlut_generation_ * 2u + (palette_enabled ? 1u : 0u)) : 0u;
        TileGpu& g = tile_gpu_[ti];
        if (g.texture && g.width == w && g.height == h && g.origin_s == x0 && g.origin_t == y0 &&
            g.source_generation == t.source_generation && g.palette_stamp == pal_stamp &&
            g.fmt == t.fmt && g.siz == t.siz) return true;

        std::vector<uint8_t> rgba;
        dx9tex::decode_texture_rect(rdram_, t.image_address, t.fmt, t.siz, t.image_stride,
            x0, y0, w, h, tlut_, tlut_valid_, t.palette, palette_enabled, st.tex.convert_k, rgba);
        if (!g.texture || g.width != w || g.height != h) {
            if (g.texture) g.texture->Release();
            g.texture = nullptr;
            if (FAILED(device_->CreateTexture(static_cast<UINT>(w), static_cast<UINT>(h), 1, 0,
                D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &g.texture, nullptr)) || !g.texture) return false;
        }
        D3DLOCKED_RECT lr{};
        if (FAILED(g.texture->LockRect(0, &lr, nullptr, 0))) return false;
        for (int y = 0; y < h; ++y) {
            uint8_t* d = static_cast<uint8_t*>(lr.pBits) + static_cast<size_t>(y) * lr.Pitch;
            const uint8_t* s = rgba.data() + static_cast<size_t>(y) * w * 4;
            for (int x = 0; x < w; ++x) {
                d[x*4+0]=s[x*4+2]; d[x*4+1]=s[x*4+1]; d[x*4+2]=s[x*4+0]; d[x*4+3]=s[x*4+3];
            }
        }
        g.texture->UnlockRect(0);
        g.width=w; g.height=h; g.origin_s=x0; g.origin_t=y0; g.fmt=t.fmt; g.siz=t.siz;
        g.source_generation=t.source_generation; g.palette_stamp=pal_stamp;
        ++texture_upload_count_; return true;
    }

    void execute_rdp(uint32_t dl, bool s2dex) {
        ExecCtx ctx{}; ctx.self = this; ctx.s2dex = s2dex;
        ctx.state.cimg_address = last_cimg_address_;
        ctx.state.cimg_row_bytes = last_cimg_row_bytes_;
        ctx.state.cimg_width = last_cimg_width_;
        ctx.state.cimg_siz = last_cimg_siz_;
        ctx.state.cimg_fmt = last_cimg_fmt_;
        ctx.state.combiner.decode(0, 0);
        auto visitor = [](void* u, const gbi::DlCommand& c) {
            auto* ctx = static_cast<ExecCtx*>(u); ctx->self->exec_command(*ctx, c);
        };
        gbi::walk_dl(rdram_, dl, visitor, &ctx);
    }

    void exec_command(ExecCtx& ctx, const gbi::DlCommand& c) {
        RdpState& st = ctx.state;
        const uint32_t w0 = c.w0, w1 = c.w1;
        switch (c.op) {
            case gbi::OP_MOVEWORD:
                gbi::set_segment_from_moveword(ctx.segments, w0, w1); break;
            case gbi::OP_SETCIMG:
                st.cimg_fmt=static_cast<uint8_t>(p0(w0,21,3));
                st.cimg_siz=static_cast<uint8_t>(p0(w0,19,2));
                st.cimg_width=static_cast<uint16_t>(p0(w0,0,12)+1);
                st.cimg_address=w1 & 0xFFFFFFu;
                st.cimg_row_bytes=st.cimg_address ? (static_cast<uint32_t>(st.cimg_width)<<st.cimg_siz>>1) : 0;
                last_cimg_address_=st.cimg_address; last_cimg_row_bytes_=st.cimg_row_bytes;
                last_cimg_width_=st.cimg_width; last_cimg_siz_=st.cimg_siz; last_cimg_fmt_=st.cimg_fmt;
                break;
            case gbi::OP_RDPSETOTHERMODE:
                st.othermode_h=p0(w0,0,24); st.othermode_l=w1 & 0xFFFFFFu; break;
            case gbi::OP_SETOTHERMODE_H: {
                const uint32_t size=p0(w0,0,8)+1;
                const uint32_t off=static_cast<uint32_t>(std::max(0,32-static_cast<int>(p0(w0,8,8))-static_cast<int>(size)));
                const uint32_t mask=size>=32?0xFFFFFFFFu:(((1u<<size)-1u)<<off);
                st.othermode_h=(st.othermode_h & ~mask)|w1; break;
            }
            case gbi::OP_SETOTHERMODE_L: {
                const uint32_t size=p0(w0,0,8)+1;
                const uint32_t off=static_cast<uint32_t>(std::max(0,32-static_cast<int>(p0(w0,8,8))-static_cast<int>(size)));
                const uint32_t mask=size>=32?0xFFFFFFFFu:(((1u<<size)-1u)<<off);
                st.othermode_l=((st.othermode_l & ~mask)|w1)&0xFFFFFFu; break;
            }
            case gbi::OP_SETSCISSOR:
                st.scissor_enabled=true; st.scissor_x0=static_cast<int>(p0(w0,12,12))>>2;
                st.scissor_y0=static_cast<int>(p0(w0,0,12))>>2;
                st.scissor_x1=static_cast<int>(p0(w1,12,12))>>2;
                st.scissor_y1=static_cast<int>(p0(w1,0,12))>>2; break;
            case gbi::OP_SETFILLCOLOR: st.fill_color=w1; break;
            case gbi::OP_SETPRIMCOLOR: set_rgba(st.prim,w1); break;
            case gbi::OP_SETENVCOLOR: set_rgba(st.env,w1); break;
            case gbi::OP_SETFOGCOLOR: set_rgba(st.fog,w1); break;
            case gbi::OP_SETBLENDCOLOR: set_rgba(st.blend,w1); break;
            case gbi::OP_SETCOMBINE: st.combiner.decode(w0,w1); break;
            case gbi::OP_SETCONVERT:
                st.tex.convert_k[0]=static_cast<int32_t>(p0(w0,13,9));
                st.tex.convert_k[1]=static_cast<int32_t>(p0(w0,4,9));
                st.tex.convert_k[2]=static_cast<int32_t>((p0(w0,0,4)<<5)|p0(w1,27,5));
                st.tex.convert_k[3]=static_cast<int32_t>(p0(w1,18,9));
                st.tex.convert_k[4]=static_cast<int32_t>(p0(w1,9,9));
                st.tex.convert_k[5]=static_cast<int32_t>(p0(w1,0,9)); break;
            case gbi::OP_FILLRECT: {
                int xl=static_cast<int>(p0(w1,12,12))>>2, yl=static_cast<int>(p0(w1,0,12))>>2;
                int xh=static_cast<int>(p0(w0,12,12))>>2, yh=static_cast<int>(p0(w0,0,12))>>2;
                const uint32_t cyc=(st.othermode_h>>20)&3u;
                if (cyc==dx9rdp::kCycCopy || cyc==dx9rdp::kCycFill) { xl&=~3; yl&=~3; xh|=3; yh|=3; }
                draw_fill(st,xl,yl,xh,yh); break;
            }
            case gbi::OP_SETTIMG:
                st.tex.timg_fmt=static_cast<uint8_t>(p0(w0,21,3)); st.tex.timg_siz=static_cast<uint8_t>(p0(w0,19,2));
                st.tex.timg_width=static_cast<uint16_t>(p0(w0,0,12)+1); st.tex.timg_address=gbi::resolve_address(ctx.segments,w1); break;
            case gbi::OP_SETTILE: {
                const int i=static_cast<int>(p0(w1,24,3)); auto& t=st.tex.tiles[i];
                t.fmt=static_cast<uint8_t>(p0(w0,21,3)); t.siz=static_cast<uint8_t>(p0(w0,19,2));
                t.line=static_cast<uint16_t>(p0(w0,9,9)); t.tmem=static_cast<uint16_t>(p0(w0,0,9));
                t.palette=static_cast<uint8_t>(p0(w1,20,4)); t.cmt=static_cast<uint8_t>(p0(w1,18,2));
                t.cms=static_cast<uint8_t>(p0(w1,8,2)); t.maskt=static_cast<uint8_t>(p0(w1,14,4));
                t.masks=static_cast<uint8_t>(p0(w1,4,4)); t.shiftt=static_cast<uint8_t>(p0(w1,10,4));
                t.shifts=static_cast<uint8_t>(p0(w1,0,4)); dx9tex::claim_tile_load(st.tex,i); break;
            }
            case gbi::OP_SETTILESIZE: {
                const int i=static_cast<int>(p0(w1,24,3)); auto& t=st.tex.tiles[i];
                t.uls=static_cast<uint16_t>(p0(w0,12,12)); t.ult=static_cast<uint16_t>(p0(w0,0,12));
                t.lrs=static_cast<uint16_t>(p0(w1,12,12)); t.lrt=static_cast<uint16_t>(p0(w1,0,12)); break;
            }
            case gbi::OP_LOADTILE:
            case gbi::OP_LOADBLOCK:
                dx9tex::note_tile_load(st.tex,static_cast<int>(p0(w1,24,3)),++texture_load_generation_); break;
            case gbi::OP_LOADTLUT: {
                const int i=static_cast<int>(p0(w1,24,3)); const auto& t=st.tex.tiles[i];
                const uint16_t count=static_cast<uint16_t>((p0(w1,12,12)>>2)+1);
                const uint32_t bank=static_cast<uint32_t>(t.palette)*16u;
                const uint32_t base=st.tex.timg_address+((p0(w0,12,12)>>2)<<st.tex.timg_siz>>1);
                for (uint16_t n=0;n<count && bank+n<256 && base+n*2+1<gbi::kRdramSize;++n)
                    tlut_[bank+n]=dx9tex::n64be16(rdram_,base+n*2);
                tlut_valid_=true; ++tlut_generation_; break;
            }
            case gbi::OP_TEXTURE: st.tex.active_tile=static_cast<int>(p0(w0,8,3)); break;
            case gbi::OP_TEXRECT:
            case gbi::OP_TEXRECTFLIP:
                if (!ctx.s2dex) { ctx.pending_texrect=true; ctx.pending_flip=c.op==gbi::OP_TEXRECTFLIP;
                    ctx.have_half1=false; ctx.rect_w0=w0; ctx.rect_w1=w1; } break;
            case gbi::OP_RDPHALF_1:
                if (ctx.pending_texrect && !ctx.s2dex) { ctx.half1=w1; ctx.have_half1=true; } break;
            case gbi::OP_RDPHALF_2:
                if (ctx.pending_texrect && ctx.have_half1 && !ctx.s2dex) {
                    draw_texrect(st,ctx.rect_w0,ctx.rect_w1,ctx.half1,w1,ctx.pending_flip);
                    ctx.pending_texrect=false; ctx.have_half1=false;
                } break;
            default: break;
        }
    }

    void draw_fill(const RdpState& st, int xl, int yl, int xh, int yh) {
        if (xh<xl || yh<yl) return;
        Dx9Framebuffer* fb=ensure_fb(st,yh+1); if (!fb || !fb->surface) return;
        LONG l=std::clamp<LONG>(xl,0,fb->width), t=std::clamp<LONG>(yl,0,fb->height);
        LONG r=std::clamp<LONG>(xh+1,0,fb->width), b=std::clamp<LONG>(yh+1,0,fb->height);
        if (st.scissor_enabled) { l=std::max<LONG>(l,st.scissor_x0); t=std::max<LONG>(t,st.scissor_y0);
            r=std::min<LONG>(r,st.scissor_x1); b=std::min<LONG>(b,st.scissor_y1); }
        if (r<=l || b<=t) return;
        IDirect3DSurface9* old=nullptr; if (FAILED(device_->GetRenderTarget(0,&old))) return;
        if (FAILED(device_->SetRenderTarget(0,fb->surface))) { old->Release(); return; }
        D3DVIEWPORT9 vp{0,0,static_cast<DWORD>(fb->width),static_cast<DWORD>(fb->height),0,1}; device_->SetViewport(&vp);
        const uint32_t raw=st.fill_color;
        D3DRECT rect{l,t,r,b};
        const HRESULT hr=device_->Clear(1,&rect,D3DCLEAR_TARGET,
            D3DCOLOR_ARGB(raw&0xFFu,(raw>>24)&0xFFu,(raw>>16)&0xFFu,(raw>>8)&0xFFu),1,0);
        device_->SetRenderTarget(0,old); old->Release();
        if (SUCCEEDED(hr)) { fb->dirty=true; fb->last_write_seq=++framebuffer_write_seq_; ++fill_count_; }
    }

    void set_sampler(DWORD unit, const dx9tex::TileState& t, bool bilerp) {
        device_->SetSamplerState(unit,D3DSAMP_MINFILTER,bilerp?D3DTEXF_LINEAR:D3DTEXF_POINT);
        device_->SetSamplerState(unit,D3DSAMP_MAGFILTER,bilerp?D3DTEXF_LINEAR:D3DTEXF_POINT);
        device_->SetSamplerState(unit,D3DSAMP_MIPFILTER,D3DTEXF_NONE);
        device_->SetSamplerState(unit,D3DSAMP_ADDRESSU,address_mode(t.cms));
        device_->SetSamplerState(unit,D3DSAMP_ADDRESSV,address_mode(t.cmt));
    }

    static void normalized_uv(const TileGpu* g, float raw_s, float raw_t, float& u, float& v) {
        if (!g || g->width<=0 || g->height<=0) { u=0; v=0; return; }
        u=(raw_s-static_cast<float>(g->origin_s))/static_cast<float>(g->width);
        v=(raw_t-static_cast<float>(g->origin_t))/static_cast<float>(g->height);
    }

    void draw_texrect(RdpState& st, uint32_t g0, uint32_t g1, uint32_t h1, uint32_t h2, bool flip) {
        const uint32_t cyc=(st.othermode_h>>20)&3u;
        const bool copy=cyc==dx9rdp::kCycCopy;
        const bool programmable=cyc==dx9rdp::kCyc1 || cyc==dx9rdp::kCyc2;
        if (!copy && (!programmable || !rdp_shader_ || !st.combiner.valid)) { ++skipped_texrect_count_; return; }

        const int tile=static_cast<int>(p0(g1,24,3));
        st.tex.active_tile=tile;
        const bool have0=ensure_tile(st,tile);
        const int tile1=(tile+1)&7;
        const bool have1=ensure_tile(st,tile1);
        TileGpu* tg0=have0?&tile_gpu_[tile&7]:nullptr;
        TileGpu* tg1=have1?&tile_gpu_[tile1]:nullptr;
        if (copy && !tg0) { ++skipped_texrect_count_; return; }

        const int xl=static_cast<int>(p0(g1,12,12))>>2, yl=static_cast<int>(p0(g1,0,12))>>2;
        const int xh=static_cast<int>(p0(g0,12,12))>>2, yh=static_cast<int>(p0(g0,0,12))>>2;
        if (xh<=xl || yh<=yl) return;
        Dx9Framebuffer* fb=ensure_fb(st,yh); if (!fb || !fb->surface) return;

        const int16_t s0=static_cast<int16_t>(h1>>16), t0=static_cast<int16_t>(h1&0xFFFFu);
        const int16_t dsdx=static_cast<int16_t>(h2>>16), dtdy=static_cast<int16_t>(h2&0xFFFFu);
        const float us=static_cast<float>(s0)/32.0f, vs=static_cast<float>(t0)/32.0f;
        const float du=static_cast<float>(dsdx)/1024.0f, dv=static_cast<float>(dtdy)/1024.0f;
        const float rw=static_cast<float>(xh-xl), rh=static_cast<float>(yh-yl);
        float raw[4][2]{};
        if (flip) {
            raw[0][0]=us; raw[0][1]=vs; raw[1][0]=us+dv*rh; raw[1][1]=vs;
            raw[2][0]=us; raw[2][1]=vs+du*rw; raw[3][0]=us+dv*rh; raw[3][1]=vs+du*rw;
        } else {
            raw[0][0]=us; raw[0][1]=vs; raw[1][0]=us+du*rw; raw[1][1]=vs;
            raw[2][0]=us; raw[2][1]=vs+dv*rh; raw[3][0]=us+du*rw; raw[3][1]=vs+dv*rh;
        }

        IDirect3DSurface9* old=nullptr; if (FAILED(device_->GetRenderTarget(0,&old))) return;
        if (FAILED(device_->SetRenderTarget(0,fb->surface))) { old->Release(); return; }
        D3DVIEWPORT9 vp{0,0,static_cast<DWORD>(fb->width),static_cast<DWORD>(fb->height),0,1}; device_->SetViewport(&vp);
        if (st.scissor_enabled) {
            RECT sc{std::clamp(st.scissor_x0,0,fb->width),std::clamp(st.scissor_y0,0,fb->height),
                    std::clamp(st.scissor_x1,0,fb->width),std::clamp(st.scissor_y1,0,fb->height)};
            device_->SetScissorRect(&sc); device_->SetRenderState(D3DRS_SCISSORTESTENABLE,TRUE);
        } else device_->SetRenderState(D3DRS_SCISSORTESTENABLE,FALSE);
        const bool bilerp=((st.othermode_h>>12)&3u)!=0u;
        set_sampler(0,st.tex.tiles[tile&7],bilerp); set_sampler(1,st.tex.tiles[tile1],bilerp);
        device_->SetTexture(0,tg0?tg0->texture:white_tex_); device_->SetTexture(1,tg1?tg1->texture:white_tex_);

        const float l=static_cast<float>(xl)-0.5f, top=static_cast<float>(yl)-0.5f;
        const float r=static_cast<float>(xh)-0.5f, bot=static_cast<float>(yh)-0.5f;
        HRESULT hr=E_FAIL;
        if (copy) {
            device_->SetPixelShader(nullptr); device_->SetRenderState(D3DRS_ALPHABLENDENABLE,FALSE);
            device_->SetFVF(kCopyFvf);
            CopyVertex q[4]{};
            const float px[4][2]={{l,top},{r,top},{l,bot},{r,bot}};
            for (int i=0;i<4;++i) {
                float u=0,v=0; normalized_uv(tg0,raw[i][0],raw[i][1],u,v);
                q[i]={px[i][0],px[i][1],0,1,u,v};
            }
            if (SUCCEEDED(device_->BeginScene())) {
                hr=device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP,2,q,sizeof(CopyVertex)); device_->EndScene();
            }
        } else {
            st.blender.decode(st.othermode_l,st.othermode_h);
            dx9shader::Constants constants;
            constants.build(st.combiner,st.blender,st.prim,st.env,st.fog,st.blend,
                static_cast<float>(st.tex.convert_k[4]&0x1FF)/255.0f,
                static_cast<float>(st.tex.convert_k[5]&0x1FF)/255.0f,cyc);
            device_->SetPixelShader(rdp_shader_);
            dx9shader::upload_constants(device_,constants);
            dx9shader::apply_framebuffer_blend(device_,st.blender);
            device_->SetFVF(kRdpFvf);
            RdpVertex q[4]{};
            const float px[4][2]={{l,top},{r,top},{l,bot},{r,bot}};
            for (int i=0;i<4;++i) {
                float u0=0,v0=0,u1=0,v1=0;
                normalized_uv(tg0,raw[i][0],raw[i][1],u0,v0);
                normalized_uv(tg1,raw[i][0],raw[i][1],u1,v1);
                q[i]={px[i][0],px[i][1],0,1,0xFFFFFFFFu,u0,v0,u1,v1};
            }
            if (SUCCEEDED(device_->BeginScene())) {
                hr=device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP,2,q,sizeof(RdpVertex)); device_->EndScene();
            }
            device_->SetPixelShader(nullptr);
        }
        device_->SetTexture(0,nullptr); device_->SetTexture(1,nullptr);
        device_->SetRenderState(D3DRS_SCISSORTESTENABLE,FALSE);
        device_->SetRenderTarget(0,old); old->Release();
        if (SUCCEEDED(hr)) {
            fb->dirty=true; fb->last_write_seq=++framebuffer_write_seq_;
            if (copy) ++copy_texrect_count_; else ++shader_texrect_count_;
        }
    }

    Dx9Framebuffer* framebuffer_containing(uint32_t address) {
        Dx9Framebuffer* best=nullptr; uint32_t seq=0;
        for (auto& kv:framebuffers_) {
            auto& fb=kv.second; if (!fb.surface || !fb.row_bytes) continue;
            const uint64_t end=static_cast<uint64_t>(kv.first)+static_cast<uint64_t>(fb.row_bytes)*fb.height;
            if (address>=kv.first && address<end && fb.last_write_seq>=seq) { best=&fb; seq=fb.last_write_seq; }
        }
        return best;
    }
    uint32_t fb_address(const Dx9Framebuffer* wanted) const {
        for (const auto& kv:framebuffers_) if (&kv.second==wanted) return kv.first; return 0;
    }

    bool present_gpu_fb(const ultramodern::renderer::ViRegs& vi,const ViSize& size) {
        const uint32_t address=vi.VI_ORIGIN_REG&0xFFFFFFu;
        Dx9Framebuffer* fb=nullptr; auto it=framebuffers_.find(address);
        if (it!=framebuffers_.end() && it->second.surface) fb=&it->second;
        if (!fb) fb=framebuffer_containing(address);
        if (!fb || !fb->surface || !fb->row_bytes) return false;
        const uint32_t base=fb_address(fb); if (address<base) return false;
        const uint32_t diff=address-base, bpp=fb_bpp(fb->siz);
        const int sy=static_cast<int>(diff/fb->row_bytes), sx=static_cast<int>((diff%fb->row_bytes)/bpp);
        const ViSize vis=visible_framebuffer_size(size);
        RECT src{sx,sy,std::min(fb->width,sx+vis.width),std::min(fb->height,sy+vis.height)};
        if (src.right<=src.left || src.bottom<=src.top) return false;
        IDirect3DSurface9* back=nullptr;
        if (FAILED(device_->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back)) || !back) return false;
        device_->SetRenderTarget(0,back); device_->Clear(0,nullptr,D3DCLEAR_TARGET,0xFF000000u,1,0);
        RECT dst{0,0,static_cast<LONG>(backbuffer_width_),static_cast<LONG>(backbuffer_height_)};
        const HRESULT hr=device_->StretchRect(fb->surface,&src,back,&dst,D3DTEXF_POINT); back->Release();
        if (FAILED(hr)) return false;
        const HRESULT pr=device_->Present(nullptr,nullptr,nullptr,nullptr);
        return SUCCEEDED(pr)||pr==D3DERR_DEVICELOST;
    }

    bool ensure_scanout(int w,int h) {
        if (scanout_tex_ && w==scanout_w_ && h==scanout_h_) return true;
        release_scanout();
        if (FAILED(device_->CreateTexture(static_cast<UINT>(w),static_cast<UINT>(h),1,D3DUSAGE_DYNAMIC,
            D3DFMT_A8R8G8B8,D3DPOOL_DEFAULT,&scanout_tex_,nullptr)) || !scanout_tex_) return false;
        scanout_w_=w; scanout_h_=h; return true;
    }
    bool upload_vi(const ultramodern::renderer::ViRegs& vi,const ViSize& s) {
        if (!ensure_scanout(s.width,s.height)) return false;
        const uint32_t type=vi.VI_STATUS_REG&3u; if (type!=2u && type!=3u) return false;
        const uint8_t siz=type==3u?gbi::IM_SIZ_32b:gbi::IM_SIZ_16b;
        const uint32_t address=vi.VI_ORIGIN_REG&0xFFFFFFu,pitch=vi.VI_WIDTH_REG*fb_bpp(siz);
        if (!address || !pitch || static_cast<uint64_t>(address)+static_cast<uint64_t>(pitch)*s.height>gbi::kRdramSize) return false;
        D3DLOCKED_RECT lr{}; if (FAILED(scanout_tex_->LockRect(0,&lr,nullptr,D3DLOCK_DISCARD))) return false;
        for (int y=0;y<s.height;++y) decode_guest_row(address,pitch,y,s.width,siz,
            static_cast<uint8_t*>(lr.pBits)+static_cast<size_t>(y)*lr.Pitch);
        scanout_tex_->UnlockRect(0); return true;
    }
    bool draw_scanout() {
        IDirect3DSurface9* back=nullptr;
        if (FAILED(device_->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back)) || !back) return false;
        device_->SetRenderTarget(0,back); back->Release(); device_->SetPixelShader(nullptr);
        D3DVIEWPORT9 vp{0,0,backbuffer_width_,backbuffer_height_,0,1}; device_->SetViewport(&vp);
        const float l=-0.5f,t=-0.5f,r=static_cast<float>(backbuffer_width_)-0.5f,b=static_cast<float>(backbuffer_height_)-0.5f;
        CopyVertex q[4]={{l,t,0,1,0,0},{r,t,0,1,1,0},{l,b,0,1,0,1},{r,b,0,1,1,1}};
        device_->SetTexture(0,scanout_tex_); device_->SetFVF(kCopyFvf); device_->SetRenderState(D3DRS_ALPHABLENDENABLE,FALSE);
        HRESULT hr=E_FAIL; if (SUCCEEDED(device_->BeginScene())) { hr=device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP,2,q,sizeof(CopyVertex)); device_->EndScene(); }
        device_->SetTexture(0,nullptr); if (FAILED(hr)) return false;
        const HRESULT pr=device_->Present(nullptr,nullptr,nullptr,nullptr); return SUCCEEDED(pr)||pr==D3DERR_DEVICELOST;
    }
    void present_vi() {
        std::lock_guard<std::mutex> lock(device_mutex_); if (!reset_device_if_needed()) return;
        auto* vi=ultramodern::renderer::get_vi_regs(); if (!vi || !vi_visible(*vi)) return;
        const ViSize s=vi_framebuffer_size(*vi); if (s.width<=0 || s.height<=0) return;
        if (!present_gpu_fb(*vi,s)) { if (!upload_vi(*vi,s)) return; draw_scanout(); }
    }

    bool writeback_framebuffer(uint32_t address,Dx9Framebuffer& fb) {
        if (!fb.dirty || !fb.surface || !rdram_ || !fb.row_bytes) return true;
        if (static_cast<uint64_t>(address)+static_cast<uint64_t>(fb.row_bytes)*fb.height>gbi::kRdramSize) return false;
        IDirect3DSurface9* sys=nullptr;
        HRESULT hr=device_->CreateOffscreenPlainSurface(static_cast<UINT>(fb.width),static_cast<UINT>(fb.height),
            D3DFMT_A8R8G8B8,D3DPOOL_SYSTEMMEM,&sys,nullptr); if (FAILED(hr)||!sys) return false;
        hr=device_->GetRenderTargetData(fb.surface,sys); if (FAILED(hr)) { sys->Release(); return false; }
        D3DLOCKED_RECT lr{}; hr=sys->LockRect(&lr,nullptr,D3DLOCK_READONLY); if (FAILED(hr)) { sys->Release(); return false; }
        const uint32_t bpp=fb_bpp(fb.siz);
        for (int y=0;y<fb.height;++y) {
            const uint8_t* src=static_cast<const uint8_t*>(lr.pBits)+static_cast<size_t>(y)*lr.Pitch;
            uint8_t* dst=rdram_+address+static_cast<uint32_t>(y)*fb.row_bytes;
            for (int x=0;x<fb.width;++x) {
                const uint8_t* p=src+x*4; const uint32_t off=static_cast<uint32_t>(x)*bpp;
                if (fb.siz==gbi::IM_SIZ_32b) {
                    dst[(off+0)^3]=p[2]; dst[(off+1)^3]=p[1]; dst[(off+2)^3]=p[0]; dst[(off+3)^3]=p[3];
                } else {
                    const uint16_t v=static_cast<uint16_t>(((p[2]>>3)<<11)|((p[1]>>3)<<6)|((p[0]>>3)<<1)|((((p[3]%8)&4)!=0)?1:0));
                    dst[off^2]=static_cast<uint8_t>(v&0xFF); dst[(off^2)+1]=static_cast<uint8_t>(v>>8);
                }
            }
        }
        sys->UnlockRect(); sys->Release(); fb.dirty=false; ++framebuffer_readbacks_; return true;
    }
    void writeback_all_framebuffers() { for (auto& kv:framebuffers_) writeback_framebuffer(kv.first,kv.second); }

    uint8_t* rdram_=nullptr;
    HWND hwnd_=nullptr;
    IDirect3D9* d3d_=nullptr;
    IDirect3DDevice9* device_=nullptr;
    IDirect3DPixelShader9* rdp_shader_=nullptr;
    IDirect3DTexture9* white_tex_=nullptr;
    IDirect3DTexture9* scanout_tex_=nullptr;
    D3DPRESENT_PARAMETERS pp_{};
    UINT backbuffer_width_=0, backbuffer_height_=0;
    int scanout_w_=0, scanout_h_=0;
    bool sm3_supported_=false, instant_present_=false;
    uint32_t last_dummy_fb_=0;
    std::mutex device_mutex_;
    std::map<uint32_t,Dx9Framebuffer> framebuffers_;
    TileGpu tile_gpu_[8]{};
    uint16_t tlut_[256]{};
    bool tlut_valid_=false;
    uint64_t tlut_generation_=0, texture_load_generation_=0;
    uint32_t framebuffer_write_seq_=0;
    uint32_t last_cimg_address_=0,last_cimg_row_bytes_=0;
    uint16_t last_cimg_width_=0;
    uint8_t last_cimg_siz_=0,last_cimg_fmt_=0;
    unsigned framebuffer_readbacks_=0,texture_upload_count_=0,fill_count_=0;
    unsigned copy_texrect_count_=0,shader_texrect_count_=0,skipped_texrect_count_=0;
    std::atomic<unsigned> display_list_count_{0},vi_swap_count_{0};
};

DX9Renderer* g_active_renderer=nullptr;
} // namespace

std::unique_ptr<ultramodern::renderer::RendererContext> create_renderer(
    uint8_t* rdram,ultramodern::renderer::WindowHandle window_handle,bool developer_mode) {
    (void)developer_mode;
    auto renderer=std::make_unique<DX9Renderer>(rdram,window_handle);
    g_active_renderer=renderer.get(); return renderer;
}
} // namespace ogre

extern "C" {
void ogre_sync_framebuffers() { if (ogre::g_active_renderer) ogre::g_active_renderer->sync_framebuffers(); }
const char* ogre_gfx_stats() { std::lock_guard<std::mutex> lock(ogre::g_stats_mutex); return ogre::g_stats_snapshot; }
}
