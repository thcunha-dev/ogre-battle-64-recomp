// Ogre Battle 64: Person of Lordly Caliber - Direct3D 9 low-end renderer.
//
// Low-end Windows backend for GeForce 410M-class hardware. This path deliberately
// does not link RT64, DXGI, D3D12 or Vulkan. Stage 2 adds the first real RDP
// drawing path: persistent G_SETCIMG targets, G_FILLRECT execution, direct VI
// presentation from D3D9 render targets, and framebuffer readback to RDRAM.
//
// The command semantics mirror app/src/web_renderer.cpp. New RDP features are
// ported from that validated implementation rather than rediscovered by tests.

#include "renderer.hpp"

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

struct ViSize {
    int width = 0;
    int height = 0;
};

inline bool vi_visible(const ultramodern::renderer::ViRegs& r) {
    return ((r.VI_STATUS_REG & 3u) != 0u) && (((r.VI_H_START_REG >> 16) & 0x3FFu) > 0u);
}

// Port of the same RT64 VI::fbSize rule used by web_renderer.cpp.
inline ViSize vi_framebuffer_size(const ultramodern::renderer::ViRegs& r) {
    ViSize out;
    const uint32_t width = r.VI_WIDTH_REG;
    if (width == 0) return out;

    const uint32_t x_scale = r.VI_X_SCALE_REG & 0xFFFu;
    const uint32_t y_scale = r.VI_Y_SCALE_REG & 0xFFFu;
    if (x_scale == 0 || y_scale == 0) return out;

    const uint32_t h_word = r.VI_H_START_REG;
    const uint32_t v_word = r.VI_V_START_REG;
    const uint32_t h_start = (h_word >> 16) & 0x3FFu;
    const uint32_t h_end = h_word & 0x3FFu;
    const uint32_t v_start = (v_word >> 16) & 0x3FFu;
    const uint32_t v_end = v_word & 0x3FFu;
    if (h_end <= h_start || v_end <= v_start) return out;

    const float x_scale_f = 1024.0f / static_cast<float>(x_scale);
    const float y_scale_f = 1024.0f / static_cast<float>(y_scale);
    int size_x = static_cast<int>(width);
    if ((r.VI_STATUS_REG & 0x40u) != 0) {
        const float estimated = static_cast<float>(h_end - h_start) / x_scale_f;
        if (estimated < (static_cast<float>(width) / 1.875f)) size_x /= 2;
    }

    const float scale_ratio = static_cast<float>(size_x) / static_cast<float>(width);
    if (scale_ratio <= 0.0f) return out;
    int size_y = static_cast<int>(std::lround(
        static_cast<float>(v_end - v_start) / (2.0f * y_scale_f * scale_ratio)));
    if (size_x <= 0 || size_y <= 0) return out;
    size_y += 2;
    size_y = static_cast<int>(std::lround(static_cast<float>(size_y) / 4.0f)) * 4;
    if (size_x > 2048 || size_y > 2048) return {};
    out.width = size_x;
    out.height = size_y;
    return out;
}

inline int overscan_crop() {
    static const int crop = [] {
        const char* v = getenv("OGRE_OVERSCAN");
        return std::clamp(v ? atoi(v) : 1, 0, 8);
    }();
    return crop;
}

inline ViSize visible_framebuffer_size(const ViSize& in) {
    const int crop = overscan_crop();
    return {(in.width > crop) ? in.width - crop : in.width,
            (in.height > crop) ? in.height - crop : in.height};
}

inline uint16_t rd16(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 0) | (p[1] << 8));
}
inline uint16_t n64h(const uint8_t* p, int off) { return rd16(p + (off ^ 2)); }
inline uint8_t n64b(const uint8_t* p, int off) { return p[off ^ 3]; }
inline uint32_t p0(uint32_t w, uint8_t pos, uint8_t bits) {
    return (bits >= 32) ? w : ((w >> pos) & ((1u << bits) - 1u));
}

inline void rgba16_to_bgra8(uint16_t v, uint8_t* out) {
    const uint32_t r = (v >> 11) & 0x1F;
    const uint32_t g = (v >> 6) & 0x1F;
    const uint32_t b = (v >> 1) & 0x1F;
    out[0] = static_cast<uint8_t>((b << 3) | (b >> 2));
    out[1] = static_cast<uint8_t>((g << 3) | (g >> 2));
    out[2] = static_cast<uint8_t>((r << 3) | (r >> 2));
    out[3] = (v & 1u) ? 0xFF : 0x00;
}

inline uint32_t bytes_per_fb_texel(uint8_t siz) {
    return siz == gbi::IM_SIZ_32b ? 4u : 2u;
}

struct PresentVertex {
    float x, y, z, rhw;
    float u, v;
};
constexpr DWORD kPresentFvf = D3DFVF_XYZRHW | D3DFVF_TEX1;
constexpr uint32_t kCycCopy = 2;
constexpr uint32_t kCycFill = 3;
constexpr int kMaxFramebufferSide = 1024;

struct RdpState {
    uint32_t othermode_h = 0;
    uint32_t othermode_l = 0;
    uint32_t fill_color = 0;
    bool scissor_enabled = false;
    int scissor_x0 = 0, scissor_y0 = 0, scissor_x1 = 0, scissor_y1 = 0;
    uint32_t cimg_address = 0;
    uint32_t cimg_row_bytes = 0;
    uint16_t cimg_width = 0;
    uint8_t cimg_siz = 0;
    uint8_t cimg_fmt = 0;
};

struct Dx9Framebuffer {
    IDirect3DTexture9* texture = nullptr;
    IDirect3DSurface9* surface = nullptr;
    int width = 0;
    int height = 0;
    uint8_t siz = 0;
    uint8_t fmt = 0;
    uint32_t row_bytes = 0;
    bool initialized = false;
    bool dirty = false;
    uint32_t last_write_seq = 0;
};

class DX9Renderer final : public ultramodern::renderer::RendererContext {
  public:
    DX9Renderer(uint8_t* rdram, ultramodern::renderer::WindowHandle window_handle)
        : rdram_(rdram), hwnd_(reinterpret_cast<HWND>(window_handle.window)) {
        setup_result = ultramodern::renderer::SetupResult::Success;
        chosen_api = ultramodern::renderer::GraphicsApi::Auto;

        if (hwnd_ == nullptr) {
            fprintf(stderr, "[dx9] no HWND supplied by SDL\n");
            return;
        }
        d3d_ = Direct3DCreate9(D3D_SDK_VERSION);
        if (d3d_ == nullptr) {
            fprintf(stderr, "[dx9] Direct3DCreate9 failed\n");
            return;
        }

        D3DCAPS9 caps{};
        if (SUCCEEDED(d3d_->GetDeviceCaps(D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, &caps))) {
            fprintf(stderr, "[dx9] caps: VS=%u.%u PS=%u.%u maxTexture=%ux%u HW-T&L=%d\n",
                    D3DSHADER_VERSION_MAJOR(caps.VertexShaderVersion),
                    D3DSHADER_VERSION_MINOR(caps.VertexShaderVersion),
                    D3DSHADER_VERSION_MAJOR(caps.PixelShaderVersion),
                    D3DSHADER_VERSION_MINOR(caps.PixelShaderVersion),
                    caps.MaxTextureWidth, caps.MaxTextureHeight,
                    (caps.DevCaps & D3DDEVCAPS_HWTRANSFORMANDLIGHT) ? 1 : 0);
        }
        if (!create_device()) return;
        configure_fixed_function_state();
        OGRE_MILESTONE("RENDERER", "Direct3D 9 low-end renderer initialized (RDP stage 2)");
        fprintf(stderr, "[dx9] renderer initialized: pure D3D9, no RT64/DXGI/D3D12/Vulkan\n");
        fflush(stderr);
    }

    ~DX9Renderer() override {
        std::lock_guard<std::mutex> lock(device_mutex_);
        release_default_pool_resources(false);
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
        if (rdram_ != nullptr) {
            const uint32_t dl_offset = task->t.data_ptr & 0x3FFFFFFu;
            {
                std::lock_guard<std::mutex> stats_lock(g_stats_mutex);
                gbi::analyze_dl(rdram_, dl_offset, task->t.data_size, g_workload);
                refresh_stats_snapshot();
            }
            std::lock_guard<std::mutex> device_lock(device_mutex_);
            if (reset_device_if_needed()) execute_rdp(dl_offset);
        }

        if (frame <= 8 || (frame % 300) == 0) {
            OGRE_MILESTONE("DX9-DL",
                           "display list %u: ucode=0x%08X data=0x%08X size=0x%X fills=%u targets=%zu",
                           frame, static_cast<unsigned>(task->t.ucode),
                           static_cast<unsigned>(task->t.data_ptr),
                           static_cast<unsigned>(task->t.data_size), fill_count_, framebuffers_.size());
        }
        if (instant_present_) present_vi();
    }

    void send_dummy_workload(uint32_t fb_address) override {
        last_dummy_fb_ = fb_address & 0x00FFFFFFu;
    }

    void update_screen() override {
        ++vi_swap_count_;
        present_vi();
    }

    void shutdown() override {
        sync_framebuffers();
        std::lock_guard<std::mutex> stats_lock(g_stats_mutex);
        refresh_stats_snapshot();
        OGRE_MILESTONE("RENDERER", "DX9 renderer shut down (%u DLs, %u VI swaps, %u fills)",
                       display_list_count_.load(), vi_swap_count_.load(), fill_count_);
        OGRE_MILESTONE("GFX-WORKLOAD", "%s", g_stats_snapshot);
    }

    uint32_t get_display_framerate() const override { return 60; }
    float get_resolution_scale() const override { return 1.0f; }

    void sync_framebuffers() {
        std::lock_guard<std::mutex> lock(device_mutex_);
        if (device_ == nullptr) return;
        writeback_all_framebuffers();
    }

  private:
    struct ExecCtx {
        DX9Renderer* self = nullptr;
        RdpState state{};
        uint32_t segments[16] = {};
    };

    bool client_size(UINT& width, UINT& height) const {
        RECT r{};
        if (hwnd_ == nullptr || !GetClientRect(hwnd_, &r)) return false;
        const LONG w = r.right - r.left;
        const LONG h = r.bottom - r.top;
        if (w <= 0 || h <= 0) return false;
        width = static_cast<UINT>(w);
        height = static_cast<UINT>(h);
        return true;
    }

    bool create_device() {
        UINT width = 640, height = 480;
        client_size(width, height);
        memset(&pp_, 0, sizeof(pp_));
        pp_.Windowed = TRUE;
        pp_.SwapEffect = D3DSWAPEFFECT_DISCARD;
        pp_.hDeviceWindow = hwnd_;
        pp_.BackBufferFormat = D3DFMT_UNKNOWN;
        pp_.BackBufferWidth = width;
        pp_.BackBufferHeight = height;
        pp_.BackBufferCount = 1;
        pp_.EnableAutoDepthStencil = FALSE;
        pp_.PresentationInterval = D3DPRESENT_INTERVAL_ONE;

        // ogre_sync_framebuffers() may run from the recompiled game thread, so
        // D3D9 must permit calls from more than the gfx thread. Our mutex keeps
        // batches serialized; MULTITHREADED makes the API contract legal too.
        const DWORD common = D3DCREATE_FPU_PRESERVE | D3DCREATE_MULTITHREADED;
        HRESULT hr = d3d_->CreateDevice(D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd_,
                                        common | D3DCREATE_HARDWARE_VERTEXPROCESSING,
                                        &pp_, &device_);
        if (FAILED(hr)) {
            fprintf(stderr, "[dx9] hardware VP failed (0x%08lX); trying software VP\n",
                    static_cast<unsigned long>(hr));
            hr = d3d_->CreateDevice(D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd_,
                                    common | D3DCREATE_SOFTWARE_VERTEXPROCESSING,
                                    &pp_, &device_);
        }
        if (FAILED(hr) || device_ == nullptr) {
            fprintf(stderr, "[dx9] CreateDevice failed (0x%08lX)\n",
                    static_cast<unsigned long>(hr));
            return false;
        }
        backbuffer_width_ = width;
        backbuffer_height_ = height;
        return true;
    }

    void configure_fixed_function_state() {
        if (!device_) return;
        device_->SetRenderState(D3DRS_LIGHTING, FALSE);
        device_->SetRenderState(D3DRS_ZENABLE, FALSE);
        device_->SetRenderState(D3DRS_ZWRITEENABLE, FALSE);
        device_->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
        device_->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
        device_->SetRenderState(D3DRS_DITHERENABLE, TRUE);
        device_->SetSamplerState(0, D3DSAMP_MINFILTER, D3DTEXF_POINT);
        device_->SetSamplerState(0, D3DSAMP_MAGFILTER, D3DTEXF_POINT);
        device_->SetSamplerState(0, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
        device_->SetSamplerState(0, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP);
        device_->SetSamplerState(0, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);
        device_->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
        device_->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
        device_->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_SELECTARG1);
        device_->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_TEXTURE);
        device_->SetTextureStageState(1, D3DTSS_COLOROP, D3DTOP_DISABLE);
        device_->SetFVF(kPresentFvf);
    }

    void release_scanout_texture() {
        if (scanout_tex_) { scanout_tex_->Release(); scanout_tex_ = nullptr; }
        texture_width_ = texture_height_ = 0;
    }

    static void release_framebuffer(Dx9Framebuffer& fb) {
        if (fb.surface) { fb.surface->Release(); fb.surface = nullptr; }
        if (fb.texture) { fb.texture->Release(); fb.texture = nullptr; }
        fb.initialized = false;
        fb.dirty = false;
    }

    void release_default_pool_resources(bool writeback) {
        if (writeback) writeback_all_framebuffers();
        release_scanout_texture();
        for (auto& kv : framebuffers_) release_framebuffer(kv.second);
        framebuffers_.clear();
    }

    bool reset_device_if_needed() {
        if (!device_) return false;
        const HRESULT coop = device_->TestCooperativeLevel();
        if (coop == D3DERR_DEVICELOST) return false;

        UINT width = backbuffer_width_, height = backbuffer_height_;
        if (!client_size(width, height)) return false;
        const bool resize = width != backbuffer_width_ || height != backbuffer_height_;
        if (coop != D3DERR_DEVICENOTRESET && !resize) return true;

        release_default_pool_resources(coop != D3DERR_DEVICENOTRESET);
        pp_.BackBufferWidth = width;
        pp_.BackBufferHeight = height;
        const HRESULT hr = device_->Reset(&pp_);
        if (FAILED(hr)) return false;
        backbuffer_width_ = width;
        backbuffer_height_ = height;
        configure_fixed_function_state();
        OGRE_MILESTONE("DX9", "device reset: backbuffer %ux%u", width, height);
        return true;
    }

    bool ensure_scanout_texture(int width, int height) {
        if (scanout_tex_ && width == texture_width_ && height == texture_height_) return true;
        release_scanout_texture();
        if (width <= 0 || height <= 0) return false;
        const HRESULT hr = device_->CreateTexture(static_cast<UINT>(width), static_cast<UINT>(height),
                                                  1, D3DUSAGE_DYNAMIC, D3DFMT_A8R8G8B8,
                                                  D3DPOOL_DEFAULT, &scanout_tex_, nullptr);
        if (FAILED(hr)) {
            fprintf(stderr, "[dx9] CreateTexture %dx%d failed (0x%08lX)\n",
                    width, height, static_cast<unsigned long>(hr));
            return false;
        }
        texture_width_ = width;
        texture_height_ = height;
        return true;
    }

    void decode_guest_row(uint32_t address, uint32_t row_bytes, int y, int width,
                          uint8_t siz, uint8_t* dst, int dst_pitch) const {
        if (!rdram_ || y < 0 || width <= 0) return;
        const uint64_t row_address = static_cast<uint64_t>(address) +
                                     static_cast<uint64_t>(y) * row_bytes;
        if (row_address + row_bytes > gbi::kRdramSize) {
            memset(dst, 0, static_cast<size_t>(width) * 4);
            return;
        }
        const uint8_t* src = rdram_ + row_address;
        (void)dst_pitch;
        for (int x = 0; x < width; ++x) {
            uint8_t* px = dst + static_cast<size_t>(x) * 4;
            if (siz == gbi::IM_SIZ_32b) {
                const int off = x * 4;
                px[0] = n64b(src, off + 2);
                px[1] = n64b(src, off + 1);
                px[2] = n64b(src, off + 0);
                px[3] = n64b(src, off + 3);
            } else {
                rgba16_to_bgra8(n64h(src, x * 2), px);
            }
        }
    }

    bool initialize_framebuffer_from_rdram(Dx9Framebuffer& fb, uint32_t address) {
        IDirect3DSurface9* staging = nullptr;
        HRESULT hr = device_->CreateOffscreenPlainSurface(
            static_cast<UINT>(fb.width), static_cast<UINT>(fb.height), D3DFMT_A8R8G8B8,
            D3DPOOL_SYSTEMMEM, &staging, nullptr);
        if (FAILED(hr) || !staging) return false;

        D3DLOCKED_RECT lock{};
        hr = staging->LockRect(&lock, nullptr, 0);
        if (SUCCEEDED(hr)) {
            for (int y = 0; y < fb.height; ++y) {
                auto* dst = static_cast<uint8_t*>(lock.pBits) + static_cast<size_t>(y) * lock.Pitch;
                decode_guest_row(address, fb.row_bytes, y, fb.width, fb.siz, dst, lock.Pitch);
            }
            staging->UnlockRect();
            hr = device_->UpdateSurface(staging, nullptr, fb.surface, nullptr);
        }
        staging->Release();
        fb.initialized = SUCCEEDED(hr);
        return fb.initialized;
    }

    int target_height(const RdpState& st, int requested_bottom) const {
        int height = std::max(1, requested_bottom);
        if (st.scissor_enabled) height = std::max(height, st.scissor_y1);
        const auto* vi = ultramodern::renderer::get_vi_regs();
        if (vi) {
            const ViSize s = vi_framebuffer_size(*vi);
            if (vi_visible(*vi) && s.height > 0) height = std::max(height, s.height);
        }
        if (height < 240 && st.cimg_width == 320) height = 240;
        return std::clamp(height, 1, kMaxFramebufferSide);
    }

    Dx9Framebuffer* ensure_framebuffer(const RdpState& st, int requested_bottom) {
        if (st.cimg_address == 0 || st.cimg_width == 0 ||
            (st.cimg_siz != gbi::IM_SIZ_16b && st.cimg_siz != gbi::IM_SIZ_32b)) {
            return nullptr;
        }
        const int width = std::clamp<int>(st.cimg_width, 1, kMaxFramebufferSide);
        int height = target_height(st, requested_bottom);
        const uint32_t row_bytes = st.cimg_row_bytes ? st.cimg_row_bytes
                                                      : (static_cast<uint32_t>(width) << st.cimg_siz >> 1);
        Dx9Framebuffer& fb = framebuffers_[st.cimg_address];
        if (fb.texture && fb.width == width && fb.siz == st.cimg_siz &&
            fb.row_bytes == row_bytes && fb.height >= height) {
            return &fb;
        }

        if (fb.texture) {
            if (fb.dirty) writeback_framebuffer(st.cimg_address, fb);
            height = std::max(height, fb.height);
            release_framebuffer(fb);
        }
        fb.width = width;
        fb.height = height;
        fb.siz = st.cimg_siz;
        fb.fmt = st.cimg_fmt;
        fb.row_bytes = row_bytes;
        HRESULT hr = device_->CreateTexture(static_cast<UINT>(width), static_cast<UINT>(height), 1,
                                            D3DUSAGE_RENDERTARGET, D3DFMT_A8R8G8B8,
                                            D3DPOOL_DEFAULT, &fb.texture, nullptr);
        if (FAILED(hr) || !fb.texture) {
            fprintf(stderr, "[dx9] render target 0x%06X %dx%d failed (0x%08lX)\n",
                    st.cimg_address, width, height, static_cast<unsigned long>(hr));
            release_framebuffer(fb);
            return nullptr;
        }
        hr = fb.texture->GetSurfaceLevel(0, &fb.surface);
        if (FAILED(hr) || !fb.surface) {
            release_framebuffer(fb);
            return nullptr;
        }
        initialize_framebuffer_from_rdram(fb, st.cimg_address);
        if (framebuffer_log_count_++ < 12) {
            OGRE_MILESTONE("DX9-FB", "target 0x%06X: %dx%d siz=%u fmt=%u pitch=%u",
                           st.cimg_address, width, height, static_cast<unsigned>(st.cimg_siz),
                           static_cast<unsigned>(st.cimg_fmt), row_bytes);
        }
        return &fb;
    }

    void execute_rdp(uint32_t dl_offset) {
        ExecCtx ctx;
        ctx.self = this;
        ctx.state.cimg_address = last_cimg_address_;
        ctx.state.cimg_row_bytes = last_cimg_row_bytes_;
        ctx.state.cimg_width = last_cimg_width_;
        ctx.state.cimg_siz = last_cimg_siz_;
        ctx.state.cimg_fmt = last_cimg_fmt_;

        auto visitor = [](void* user, const gbi::DlCommand& cmd) {
            auto* ctx = static_cast<ExecCtx*>(user);
            ctx->self->exec_rdp_command(*ctx, cmd);
        };
        gbi::walk_dl(rdram_, dl_offset, visitor, &ctx);
    }

    void exec_rdp_command(ExecCtx& ctx, const gbi::DlCommand& c) {
        RdpState& st = ctx.state;
        const uint32_t w0 = c.w0, w1 = c.w1;
        switch (c.op) {
            case gbi::OP_MOVEWORD:
                gbi::set_segment_from_moveword(ctx.segments, w0, w1);
                break;
            case gbi::OP_SETCIMG: {
                st.cimg_fmt = static_cast<uint8_t>(p0(w0, 21, 3));
                st.cimg_siz = static_cast<uint8_t>(p0(w0, 19, 2));
                st.cimg_width = static_cast<uint16_t>(p0(w0, 0, 12) + 1);
                st.cimg_address = w1 & 0x00FFFFFFu;
                st.cimg_row_bytes = st.cimg_address ?
                    (static_cast<uint32_t>(st.cimg_width) << st.cimg_siz >> 1) : 0;
                last_cimg_address_ = st.cimg_address;
                last_cimg_row_bytes_ = st.cimg_row_bytes;
                last_cimg_width_ = st.cimg_width;
                last_cimg_siz_ = st.cimg_siz;
                last_cimg_fmt_ = st.cimg_fmt;
                break;
            }
            case gbi::OP_SETSCISSOR:
                st.scissor_enabled = true;
                st.scissor_x0 = static_cast<int>(p0(w0, 12, 12)) >> 2;
                st.scissor_y0 = static_cast<int>(p0(w0, 0, 12)) >> 2;
                st.scissor_x1 = static_cast<int>(p0(w1, 12, 12)) >> 2;
                st.scissor_y1 = static_cast<int>(p0(w1, 0, 12)) >> 2;
                break;
            case gbi::OP_RDPSETOTHERMODE:
                st.othermode_h = p0(w0, 0, 24);
                st.othermode_l = w1 & 0xFFFFFFu;
                break;
            case gbi::OP_SETOTHERMODE_H: {
                const uint32_t size = p0(w0, 0, 8) + 1;
                const uint32_t off = static_cast<uint32_t>(std::max(
                    0, static_cast<int>(32 - p0(w0, 8, 8) - size)));
                const uint32_t mask = size >= 32 ? 0xFFFFFFFFu : (((1u << size) - 1u) << off);
                st.othermode_h = (st.othermode_h & ~mask) | w1;
                break;
            }
            case gbi::OP_SETOTHERMODE_L: {
                const uint32_t size = p0(w0, 0, 8) + 1;
                const uint32_t off = static_cast<uint32_t>(std::max(
                    0, static_cast<int>(32 - p0(w0, 8, 8) - size)));
                const uint32_t mask = size >= 32 ? 0xFFFFFFFFu : (((1u << size) - 1u) << off);
                st.othermode_l = ((st.othermode_l & ~mask) | w1) & 0xFFFFFFu;
                break;
            }
            case gbi::OP_SETFILLCOLOR:
                st.fill_color = w1;
                break;
            case gbi::OP_FILLRECT: {
                int xl = static_cast<int>(p0(w1, 12, 12)) >> 2;
                int yl = static_cast<int>(p0(w1, 0, 12)) >> 2;
                int xh = static_cast<int>(p0(w0, 12, 12)) >> 2;
                int yh = static_cast<int>(p0(w0, 0, 12)) >> 2;
                const uint32_t cyc = (st.othermode_h >> 20) & 3u;
                if (cyc == kCycCopy || cyc == kCycFill) {
                    xl &= ~3; yl &= ~3; xh |= 3; yh |= 3;
                }
                draw_fill_rect(st, xl, yl, xh, yh);
                break;
            }
            default:
                break;
        }
    }

    void draw_fill_rect(const RdpState& st, int xl, int yl, int xh, int yh) {
        if (xh < xl || yh < yl) return;
        Dx9Framebuffer* fb = ensure_framebuffer(st, yh + 1);
        if (!fb || !fb->surface) return;

        LONG left = std::clamp<LONG>(xl, 0, fb->width);
        LONG top = std::clamp<LONG>(yl, 0, fb->height);
        LONG right = std::clamp<LONG>(xh + 1, 0, fb->width);
        LONG bottom = std::clamp<LONG>(yh + 1, 0, fb->height);
        if (st.scissor_enabled) {
            left = std::max<LONG>(left, st.scissor_x0);
            top = std::max<LONG>(top, st.scissor_y0);
            right = std::min<LONG>(right, st.scissor_x1);
            bottom = std::min<LONG>(bottom, st.scissor_y1);
        }
        if (right <= left || bottom <= top) return;

        IDirect3DSurface9* previous = nullptr;
        if (FAILED(device_->GetRenderTarget(0, &previous))) return;
        if (FAILED(device_->SetRenderTarget(0, fb->surface))) {
            previous->Release();
            return;
        }
        D3DVIEWPORT9 vp{0, 0, static_cast<DWORD>(fb->width), static_cast<DWORD>(fb->height), 0.0f, 1.0f};
        device_->SetViewport(&vp);
        const uint32_t raw = st.fill_color;
        const D3DCOLOR color = D3DCOLOR_ARGB(raw & 0xFFu, (raw >> 24) & 0xFFu,
                                             (raw >> 16) & 0xFFu, (raw >> 8) & 0xFFu);
        D3DRECT rect{left, top, right, bottom};
        const HRESULT hr = device_->Clear(1, &rect, D3DCLEAR_TARGET, color, 1.0f, 0);
        device_->SetRenderTarget(0, previous);
        previous->Release();
        if (SUCCEEDED(hr)) {
            fb->dirty = true;
            fb->last_write_seq = ++framebuffer_write_seq_;
            ++fill_count_;
        }
    }

    Dx9Framebuffer* framebuffer_containing(uint32_t address) {
        Dx9Framebuffer* best = nullptr;
        uint32_t best_seq = 0;
        for (auto& kv : framebuffers_) {
            Dx9Framebuffer& fb = kv.second;
            if (!fb.surface || fb.row_bytes == 0) continue;
            const uint64_t end = static_cast<uint64_t>(kv.first) +
                                 static_cast<uint64_t>(fb.row_bytes) * fb.height;
            if (address >= kv.first && address < end && fb.last_write_seq >= best_seq) {
                best = &fb;
                best_seq = fb.last_write_seq;
            }
        }
        return best;
    }

    uint32_t framebuffer_address(const Dx9Framebuffer* wanted) const {
        for (const auto& kv : framebuffers_) if (&kv.second == wanted) return kv.first;
        return 0;
    }

    bool present_gpu_framebuffer(const ultramodern::renderer::ViRegs& vi, const ViSize& size) {
        const uint32_t address = vi.VI_ORIGIN_REG & 0x00FFFFFFu;
        Dx9Framebuffer* fb = nullptr;
        auto exact = framebuffers_.find(address);
        if (exact != framebuffers_.end() && exact->second.surface) fb = &exact->second;
        if (!fb) fb = framebuffer_containing(address);
        if (!fb || !fb->surface || fb->row_bytes == 0) return false;

        const uint32_t base = framebuffer_address(fb);
        if (address < base) return false;
        const uint32_t diff = address - base;
        const uint32_t bpp = bytes_per_fb_texel(fb->siz);
        const int src_y = static_cast<int>(diff / fb->row_bytes);
        const int src_x = static_cast<int>((diff % fb->row_bytes) / bpp);
        const ViSize visible = visible_framebuffer_size(size);
        RECT src{src_x, src_y,
                 std::min(fb->width, src_x + visible.width),
                 std::min(fb->height, src_y + visible.height)};
        if (src.right <= src.left || src.bottom <= src.top) return false;

        IDirect3DSurface9* back = nullptr;
        if (FAILED(device_->GetBackBuffer(0, 0, D3DBACKBUFFER_TYPE_MONO, &back)) || !back) return false;
        device_->SetRenderTarget(0, back);
        device_->Clear(0, nullptr, D3DCLEAR_TARGET, D3DCOLOR_XRGB(0, 0, 0), 1.0f, 0);
        RECT dst{0, 0, static_cast<LONG>(backbuffer_width_), static_cast<LONG>(backbuffer_height_)};
        const HRESULT hr = device_->StretchRect(fb->surface, &src, back, &dst, D3DTEXF_POINT);
        back->Release();
        if (FAILED(hr)) return false;
        const HRESULT present_hr = device_->Present(nullptr, nullptr, nullptr, nullptr);
        return SUCCEEDED(present_hr) || present_hr == D3DERR_DEVICELOST;
    }

    bool upload_vi(const ultramodern::renderer::ViRegs& vi, const ViSize& size) {
        if (!rdram_ || !device_ || !ensure_scanout_texture(size.width, size.height)) return false;
        const uint32_t type = vi.VI_STATUS_REG & 3u;
        if (type != 2u && type != 3u) return false;
        const uint8_t siz = type == 3u ? gbi::IM_SIZ_32b : gbi::IM_SIZ_16b;
        const uint32_t bpp = bytes_per_fb_texel(siz);
        const uint32_t address = vi.VI_ORIGIN_REG & 0x00FFFFFFu;
        const uint32_t source_width = vi.VI_WIDTH_REG;
        if (address == 0 || source_width == 0) return false;
        const uint32_t source_pitch = source_width * bpp;
        if (static_cast<uint64_t>(address) + static_cast<uint64_t>(source_pitch) * size.height >
            gbi::kRdramSize) return false;

        D3DLOCKED_RECT lock{};
        if (FAILED(scanout_tex_->LockRect(0, &lock, nullptr, D3DLOCK_DISCARD))) return false;
        for (int y = 0; y < size.height; ++y) {
            auto* dst = static_cast<uint8_t*>(lock.pBits) + static_cast<size_t>(y) * lock.Pitch;
            decode_guest_row(address, source_pitch, y, size.width, siz, dst, lock.Pitch);
        }
        scanout_tex_->UnlockRect(0);
        return true;
    }

    bool draw_scanout() {
        if (!device_ || !scanout_tex_) return false;
        IDirect3DSurface9* back = nullptr;
        if (FAILED(device_->GetBackBuffer(0, 0, D3DBACKBUFFER_TYPE_MONO, &back)) || !back) return false;
        device_->SetRenderTarget(0, back);
        back->Release();
        D3DVIEWPORT9 vp{0, 0, backbuffer_width_, backbuffer_height_, 0.0f, 1.0f};
        device_->SetViewport(&vp);
        const float l = -0.5f, t = -0.5f;
        const float r = static_cast<float>(backbuffer_width_) - 0.5f;
        const float b = static_cast<float>(backbuffer_height_) - 0.5f;
        const PresentVertex quad[4] = {
            {l, t, 0, 1, 0, 0}, {r, t, 0, 1, 1, 0},
            {l, b, 0, 1, 0, 1}, {r, b, 0, 1, 1, 1},
        };
        if (FAILED(device_->BeginScene())) return false;
        device_->SetTexture(0, scanout_tex_);
        device_->SetFVF(kPresentFvf);
        const HRESULT draw_hr = device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, quad, sizeof(PresentVertex));
        device_->SetTexture(0, nullptr);
        device_->EndScene();
        if (FAILED(draw_hr)) return false;
        const HRESULT present_hr = device_->Present(nullptr, nullptr, nullptr, nullptr);
        return SUCCEEDED(present_hr) || present_hr == D3DERR_DEVICELOST;
    }

    void present_vi() {
        std::lock_guard<std::mutex> lock(device_mutex_);
        if (!reset_device_if_needed()) return;
        auto* vi = ultramodern::renderer::get_vi_regs();
        if (!vi || !vi_visible(*vi)) return;
        const ViSize size = vi_framebuffer_size(*vi);
        if (size.width <= 0 || size.height <= 0) return;
        if (!present_gpu_framebuffer(*vi, size)) {
            if (!upload_vi(*vi, size)) return;
            draw_scanout();
        }
        const uint64_t key = (static_cast<uint64_t>(size.width) << 32) |
                             static_cast<uint32_t>(size.height);
        if (key != last_vi_size_) {
            last_vi_size_ = key;
            OGRE_MILESTONE("DX9-VI", "scanout %dx%d origin=0x%06X status=0x%08X width=%u",
                           size.width, size.height, vi->VI_ORIGIN_REG & 0x00FFFFFFu,
                           vi->VI_STATUS_REG, vi->VI_WIDTH_REG);
        }
    }

    bool writeback_framebuffer(uint32_t address, Dx9Framebuffer& fb) {
        if (!fb.dirty || !fb.surface || !rdram_ || fb.row_bytes == 0) return true;
        if (static_cast<uint64_t>(address) + static_cast<uint64_t>(fb.row_bytes) * fb.height >
            gbi::kRdramSize) return false;
        IDirect3DSurface9* staging = nullptr;
        HRESULT hr = device_->CreateOffscreenPlainSurface(
            static_cast<UINT>(fb.width), static_cast<UINT>(fb.height), D3DFMT_A8R8G8B8,
            D3DPOOL_SYSTEMMEM, &staging, nullptr);
        if (FAILED(hr) || !staging) return false;
        hr = device_->GetRenderTargetData(fb.surface, staging);
        if (FAILED(hr)) { staging->Release(); return false; }
        D3DLOCKED_RECT lock{};
        hr = staging->LockRect(&lock, nullptr, D3DLOCK_READONLY);
        if (FAILED(hr)) { staging->Release(); return false; }
        const uint32_t bpp = bytes_per_fb_texel(fb.siz);
        for (int y = 0; y < fb.height; ++y) {
            const auto* src = static_cast<const uint8_t*>(lock.pBits) + static_cast<size_t>(y) * lock.Pitch;
            uint8_t* dst = rdram_ + address + static_cast<uint32_t>(y) * fb.row_bytes;
            for (int x = 0; x < fb.width; ++x) {
                const uint8_t* px = src + static_cast<size_t>(x) * 4; // BGRA
                const uint32_t off = static_cast<uint32_t>(x) * bpp;
                if (fb.siz == gbi::IM_SIZ_32b) {
                    dst[(off + 0) ^ 3] = px[2];
                    dst[(off + 1) ^ 3] = px[1];
                    dst[(off + 2) ^ 3] = px[0];
                    dst[(off + 3) ^ 3] = px[3];
                } else {
                    const uint16_t v = static_cast<uint16_t>(
                        ((px[2] >> 3) << 11) | ((px[1] >> 3) << 6) | ((px[0] >> 3) << 1) |
                        ((((px[3] % 8) & 4) != 0) ? 1 : 0));
                    dst[off ^ 2] = static_cast<uint8_t>(v & 0xFF);
                    dst[(off ^ 2) + 1] = static_cast<uint8_t>(v >> 8);
                }
            }
        }
        staging->UnlockRect();
        staging->Release();
        fb.dirty = false;
        ++framebuffer_readbacks_;
        return true;
    }

    void writeback_all_framebuffers() {
        for (auto& kv : framebuffers_) writeback_framebuffer(kv.first, kv.second);
    }

    uint8_t* rdram_ = nullptr;
    HWND hwnd_ = nullptr;
    IDirect3D9* d3d_ = nullptr;
    IDirect3DDevice9* device_ = nullptr;
    IDirect3DTexture9* scanout_tex_ = nullptr;
    D3DPRESENT_PARAMETERS pp_{};
    UINT backbuffer_width_ = 0, backbuffer_height_ = 0;
    int texture_width_ = 0, texture_height_ = 0;
    uint64_t last_vi_size_ = 0;
    uint32_t last_dummy_fb_ = 0;
    bool instant_present_ = false;
    std::mutex device_mutex_;
    std::map<uint32_t, Dx9Framebuffer> framebuffers_;
    uint32_t framebuffer_write_seq_ = 0;
    uint32_t last_cimg_address_ = 0, last_cimg_row_bytes_ = 0;
    uint16_t last_cimg_width_ = 0;
    uint8_t last_cimg_siz_ = 0, last_cimg_fmt_ = 0;
    unsigned framebuffer_log_count_ = 0;
    unsigned framebuffer_readbacks_ = 0;
    unsigned fill_count_ = 0;
    std::atomic<unsigned> display_list_count_{0};
    std::atomic<unsigned> vi_swap_count_{0};
};

DX9Renderer* g_active_renderer = nullptr;

}  // namespace

std::unique_ptr<ultramodern::renderer::RendererContext> create_renderer(
    uint8_t* rdram, ultramodern::renderer::WindowHandle window_handle, bool developer_mode) {
    (void)developer_mode;
    auto renderer = std::make_unique<DX9Renderer>(rdram, window_handle);
    g_active_renderer = renderer.get();
    return renderer;
}

}  // namespace ogre

extern "C" {

void ogre_sync_framebuffers() {
    if (ogre::g_active_renderer) ogre::g_active_renderer->sync_framebuffers();
}

const char* ogre_gfx_stats() {
    std::lock_guard<std::mutex> lock(ogre::g_stats_mutex);
    return ogre::g_stats_snapshot;
}

}  // extern "C"
