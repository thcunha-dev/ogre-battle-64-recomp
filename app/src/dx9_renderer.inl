// Ogre Battle 64: Person of Lordly Caliber - Direct3D 9 low-end renderer.
//
// Stage 1 of the native DX9 backend. This deliberately avoids RT64, D3D12,
// Vulkan, DXGI and D3DCompiler. It creates a plain Direct3D 9 device, decodes
// the N64 VI framebuffer from RDRAM, uploads it to one dynamic A8R8G8B8 texture
// and presents it with the fixed-function pipeline. The next stage ports the
// already validated F3DEX2/S2DEX2/RDP executor from web_renderer.cpp onto this
// device; keeping the VI path independent gives us a small, deterministic
// bring-up target for GeForce 410M-class hardware.
//
// This file is included by null_renderer.cpp when OGRE_USE_DX9 is defined. It
// stays an .inl until the CMake renderer selector is switched to a first-class
// OGRE_USE_DX9 option; that keeps this first commit isolated from the normal
// RT64 and null builds.

#include "renderer.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
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

// Same VI sizing rule used by the WebGL renderer, itself ported from RT64's
// VI::fbSize. OB64 resolves to 320x240 in the normal mode and 640x480 on the
// high-resolution world-map mode.
inline bool vi_visible(const ultramodern::renderer::ViRegs& r) {
    return ((r.VI_STATUS_REG & 3u) != 0u) && (((r.VI_H_START_REG >> 16) & 0x3FFu) > 0u);
}

inline ViSize vi_framebuffer_size(const ultramodern::renderer::ViRegs& r) {
    ViSize out;
    const uint32_t width = r.VI_WIDTH_REG;
    if (width == 0) {
        return out;
    }

    const uint32_t x_scale = r.VI_X_SCALE_REG & 0xFFFu;
    const uint32_t y_scale = r.VI_Y_SCALE_REG & 0xFFFu;
    if (x_scale == 0 || y_scale == 0) {
        return out;
    }

    const uint32_t h_word = r.VI_H_START_REG;
    const uint32_t v_word = r.VI_V_START_REG;
    const uint32_t h_start = (h_word >> 16) & 0x3FFu;
    const uint32_t h_end = h_word & 0x3FFu;
    const uint32_t v_start = (v_word >> 16) & 0x3FFu;
    const uint32_t v_end = v_word & 0x3FFu;
    if (h_end <= h_start || v_end <= v_start) {
        return out;
    }

    const float x_scale_f = 1024.0f / static_cast<float>(x_scale);
    const float y_scale_f = 1024.0f / static_cast<float>(y_scale);

    int size_x = static_cast<int>(width);
    if ((r.VI_STATUS_REG & 0x40u) != 0) {
        const float estimated = static_cast<float>(h_end - h_start) / x_scale_f;
        if (estimated < (static_cast<float>(width) / 1.875f)) {
            size_x = static_cast<int>(width) / 2;
        }
    }

    const float scale_ratio = static_cast<float>(size_x) / static_cast<float>(width);
    if (scale_ratio <= 0.0f) {
        return out;
    }
    const float rows = static_cast<float>(v_end - v_start) /
                       (2.0f * y_scale_f * scale_ratio);
    int size_y = static_cast<int>(std::lround(rows));
    if (size_x <= 0 || size_y <= 0) {
        return out;
    }
    size_y += 2;
    size_y = static_cast<int>(std::lround(static_cast<float>(size_y) / 4.0f)) * 4;

    // Guard the D3D allocation as well as the guest-memory read. OB64 only uses
    // 320x240 and 640x480 here, so anything much larger is a bad VI state.
    if (size_x > 2048 || size_y > 2048) {
        return {};
    }

    out.width = size_x;
    out.height = size_y;
    return out;
}

inline uint16_t rd16(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 0) | (p[1] << 8));
}

// N64ModernRuntime stores each guest 32-bit word byte-reversed in host RDRAM.
inline uint16_t n64h(const uint8_t* p, int off) {
    return rd16(p + (off ^ 2));
}
inline uint8_t n64b(const uint8_t* p, int off) {
    return p[off ^ 3];
}

inline void rgba16_to_bgra8(uint16_t v, uint8_t* out) {
    const uint32_t r = (v >> 11) & 0x1F;
    const uint32_t g = (v >> 6) & 0x1F;
    const uint32_t b = (v >> 1) & 0x1F;
    // D3DFMT_A8R8G8B8 is BGRA in little-endian memory.
    out[0] = static_cast<uint8_t>((b << 3) | (b >> 2));
    out[1] = static_cast<uint8_t>((g << 3) | (g >> 2));
    out[2] = static_cast<uint8_t>((r << 3) | (r >> 2));
    out[3] = 0xFF;
}

struct PresentVertex {
    float x, y, z, rhw;
    float u, v;
};
constexpr DWORD kPresentFvf = D3DFVF_XYZRHW | D3DFVF_TEX1;

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
            fprintf(stderr,
                    "[dx9] caps: VS=%u.%u PS=%u.%u maxTexture=%ux%u HW-T&L=%d\n",
                    D3DSHADER_VERSION_MAJOR(caps.VertexShaderVersion),
                    D3DSHADER_VERSION_MINOR(caps.VertexShaderVersion),
                    D3DSHADER_VERSION_MAJOR(caps.PixelShaderVersion),
                    D3DSHADER_VERSION_MINOR(caps.PixelShaderVersion),
                    caps.MaxTextureWidth, caps.MaxTextureHeight,
                    (caps.DevCaps & D3DDEVCAPS_HWTRANSFORMANDLIGHT) ? 1 : 0);
        }

        if (!create_device()) {
            return;
        }

        configure_fixed_function_state();
        OGRE_MILESTONE("RENDERER", "Direct3D 9 low-end renderer initialized");
        fprintf(stderr, "[dx9] renderer initialized: pure D3D9, no RT64/DXGI/D3D12/Vulkan\n");
        fflush(stderr);
    }

    ~DX9Renderer() override {
        release_texture();
        if (device_ != nullptr) {
            device_->Release();
            device_ = nullptr;
        }
        if (d3d_ != nullptr) {
            d3d_->Release();
            d3d_ = nullptr;
        }
    }

    bool valid() override {
        return device_ != nullptr;
    }

    bool update_config(const ultramodern::renderer::GraphicsConfig& old_config,
                       const ultramodern::renderer::GraphicsConfig& new_config) override {
        // The first low-end path intentionally keeps presentation windowed at the
        // D3D device level. SDL can still resize/borderless the HWND and the
        // backbuffer is reset to follow its client size in update_screen().
        return old_config != new_config;
    }

    void enable_instant_present() override {
        instant_present_ = true;
    }

    void send_dl(const OSTask* task) override {
        const unsigned frame = ++display_list_count_;
        if (rdram_ != nullptr) {
            const uint32_t dl_offset = task->t.data_ptr & 0x3FFFFFFu;
            std::lock_guard<std::mutex> lock(g_stats_mutex);
            gbi::analyze_dl(rdram_, dl_offset, task->t.data_size, g_workload);
            refresh_stats_snapshot();
        }

        if (frame <= 4 || (frame % 300) == 0) {
            OGRE_MILESTONE("DX9-DL",
                           "display list %u queued for DX9 RDP stage (ucode=0x%08X data=0x%08X size=0x%X)",
                           frame, static_cast<unsigned>(task->t.ucode),
                           static_cast<unsigned>(task->t.data_ptr),
                           static_cast<unsigned>(task->t.data_size));
        }

        // Stage 1 deliberately presents the guest VI buffer only. The F3DEX2 /
        // S2DEX2 executor is ported next; do not invent partial RDP behaviour in
        // this bring-up path. If a task updates RDRAM itself (notably NJPEG), an
        // instant-present diagnostic can still show it immediately.
        if (instant_present_) {
            present_vi();
        }
    }

    void send_dummy_workload(uint32_t fb_address) override {
        last_dummy_fb_ = fb_address & 0x00FFFFFFu;
    }

    void update_screen() override {
        ++vi_swap_count_;
        present_vi();
    }

    void shutdown() override {
        std::lock_guard<std::mutex> lock(g_stats_mutex);
        refresh_stats_snapshot();
        OGRE_MILESTONE("RENDERER", "DX9 renderer shut down (%u DLs, %u VI swaps)",
                       display_list_count_.load(), vi_swap_count_.load());
        OGRE_MILESTONE("GFX-WORKLOAD", "%s", g_stats_snapshot);
    }

    uint32_t get_display_framerate() const override {
        return 60;
    }

    float get_resolution_scale() const override {
        return 1.0f;
    }

  private:
    bool client_size(UINT& width, UINT& height) const {
        RECT r{};
        if (hwnd_ == nullptr || !GetClientRect(hwnd_, &r)) {
            return false;
        }
        const LONG w = r.right - r.left;
        const LONG h = r.bottom - r.top;
        if (w <= 0 || h <= 0) {
            return false;
        }
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

        const DWORD common = D3DCREATE_FPU_PRESERVE;
        HRESULT hr = d3d_->CreateDevice(D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd_,
                                        common | D3DCREATE_HARDWARE_VERTEXPROCESSING,
                                        &pp_, &device_);
        if (FAILED(hr)) {
            fprintf(stderr, "[dx9] hardware vertex processing failed (0x%08lX); trying software VP\n",
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
        if (device_ == nullptr) {
            return;
        }
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

    void release_texture() {
        if (scanout_tex_ != nullptr) {
            scanout_tex_->Release();
            scanout_tex_ = nullptr;
        }
        texture_width_ = 0;
        texture_height_ = 0;
    }

    bool reset_device_if_needed() {
        if (device_ == nullptr) {
            return false;
        }

        const HRESULT coop = device_->TestCooperativeLevel();
        if (coop == D3DERR_DEVICELOST) {
            return false;
        }

        UINT width = backbuffer_width_;
        UINT height = backbuffer_height_;
        if (!client_size(width, height)) {
            return false;
        }
        const bool resize = (width != backbuffer_width_ || height != backbuffer_height_);
        if (coop != D3DERR_DEVICENOTRESET && !resize) {
            return true;
        }

        release_texture();
        pp_.BackBufferWidth = width;
        pp_.BackBufferHeight = height;
        const HRESULT hr = device_->Reset(&pp_);
        if (FAILED(hr)) {
            return false;
        }
        backbuffer_width_ = width;
        backbuffer_height_ = height;
        configure_fixed_function_state();
        OGRE_MILESTONE("DX9", "device reset: backbuffer %ux%u", width, height);
        return true;
    }

    bool ensure_texture(int width, int height) {
        if (scanout_tex_ != nullptr && width == texture_width_ && height == texture_height_) {
            return true;
        }
        release_texture();
        if (width <= 0 || height <= 0) {
            return false;
        }
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

    bool upload_vi(const ultramodern::renderer::ViRegs& vi, const ViSize& size) {
        if (rdram_ == nullptr || device_ == nullptr || !ensure_texture(size.width, size.height)) {
            return false;
        }

        const uint32_t type = vi.VI_STATUS_REG & 3u;
        const uint32_t bytes_per_pixel = (type == 3u) ? 4u : 2u;
        if (type != 2u && type != 3u) {
            return false;
        }

        const uint32_t address = vi.VI_ORIGIN_REG & 0x00FFFFFFu;
        const uint32_t source_width = vi.VI_WIDTH_REG;
        if (address == 0 || source_width == 0) {
            return false;
        }
        const uint64_t source_pitch = static_cast<uint64_t>(source_width) * bytes_per_pixel;
        const uint64_t end = static_cast<uint64_t>(address) +
                             source_pitch * static_cast<uint64_t>(size.height);
        if (end > gbi::kRdramSize) {
            if (bad_range_logs_++ < 4) {
                fprintf(stderr,
                        "[dx9] VI framebuffer outside RDRAM: addr=0x%06X pitch=%llu h=%d end=0x%llX\n",
                        address, static_cast<unsigned long long>(source_pitch), size.height,
                        static_cast<unsigned long long>(end));
            }
            return false;
        }

        D3DLOCKED_RECT lock{};
        const HRESULT hr = scanout_tex_->LockRect(0, &lock, nullptr, D3DLOCK_DISCARD);
        if (FAILED(hr)) {
            return false;
        }

        for (int y = 0; y < size.height; ++y) {
            const uint8_t* src = rdram_ + address + static_cast<uint64_t>(y) * source_pitch;
            uint8_t* dst = static_cast<uint8_t*>(lock.pBits) + static_cast<size_t>(y) * lock.Pitch;
            for (int x = 0; x < size.width; ++x) {
                uint8_t* px = dst + static_cast<size_t>(x) * 4;
                if (type == 3u) {
                    const int off = x * 4;
                    const uint8_t r = n64b(src, off + 0);
                    const uint8_t g = n64b(src, off + 1);
                    const uint8_t b = n64b(src, off + 2);
                    px[0] = b;
                    px[1] = g;
                    px[2] = r;
                    px[3] = 0xFF;
                } else {
                    rgba16_to_bgra8(n64h(src, x * 2), px);
                }
            }
        }

        scanout_tex_->UnlockRect(0);
        return true;
    }

    bool draw_scanout() {
        if (device_ == nullptr || scanout_tex_ == nullptr) {
            return false;
        }

        const float left = -0.5f;
        const float top = -0.5f;
        const float right = static_cast<float>(backbuffer_width_) - 0.5f;
        const float bottom = static_cast<float>(backbuffer_height_) - 0.5f;
        const PresentVertex quad[4] = {
            {left,  top,    0.0f, 1.0f, 0.0f, 0.0f},
            {right, top,    0.0f, 1.0f, 1.0f, 0.0f},
            {left,  bottom, 0.0f, 1.0f, 0.0f, 1.0f},
            {right, bottom, 0.0f, 1.0f, 1.0f, 1.0f},
        };

        if (FAILED(device_->BeginScene())) {
            return false;
        }
        device_->SetTexture(0, scanout_tex_);
        device_->SetFVF(kPresentFvf);
        const HRESULT draw_hr = device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2,
                                                          quad, sizeof(PresentVertex));
        device_->SetTexture(0, nullptr);
        device_->EndScene();
        if (FAILED(draw_hr)) {
            return false;
        }

        const HRESULT present_hr = device_->Present(nullptr, nullptr, nullptr, nullptr);
        return SUCCEEDED(present_hr) || present_hr == D3DERR_DEVICELOST;
    }

    void present_vi() {
        if (!reset_device_if_needed()) {
            return;
        }
        ultramodern::renderer::ViRegs* vi = ultramodern::renderer::get_vi_regs();
        if (vi == nullptr || !vi_visible(*vi)) {
            return;
        }
        const ViSize size = vi_framebuffer_size(*vi);
        if (size.width <= 0 || size.height <= 0) {
            return;
        }
        if (!upload_vi(*vi, size)) {
            return;
        }
        draw_scanout();

        const uint64_t key = (static_cast<uint64_t>(size.width) << 32) |
                             static_cast<uint32_t>(size.height);
        if (key != last_vi_size_) {
            last_vi_size_ = key;
            OGRE_MILESTONE("DX9-VI", "scanout %dx%d origin=0x%06X status=0x%08X width=%u",
                           size.width, size.height, vi->VI_ORIGIN_REG & 0x00FFFFFFu,
                           vi->VI_STATUS_REG, vi->VI_WIDTH_REG);
        }
    }

    uint8_t* rdram_ = nullptr;
    HWND hwnd_ = nullptr;
    IDirect3D9* d3d_ = nullptr;
    IDirect3DDevice9* device_ = nullptr;
    IDirect3DTexture9* scanout_tex_ = nullptr;
    D3DPRESENT_PARAMETERS pp_{};
    UINT backbuffer_width_ = 0;
    UINT backbuffer_height_ = 0;
    int texture_width_ = 0;
    int texture_height_ = 0;
    uint64_t last_vi_size_ = 0;
    uint32_t last_dummy_fb_ = 0;
    unsigned bad_range_logs_ = 0;
    bool instant_present_ = false;
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

// Stage 1 does not render RDP colour images yet, so there is no GPU target to
// copy back. Once the web executor is attached to D3D9, this hook will read back
// only dirty guest framebuffer rows, matching web_renderer.cpp.
void ogre_sync_framebuffers() {
}

const char* ogre_gfx_stats() {
    std::lock_guard<std::mutex> lock(ogre::g_stats_mutex);
    return ogre::g_stats_snapshot;
}

}  // extern "C"
