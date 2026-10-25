#pragma once

// D3D9 ownership/state for the N64 depth image.
// Kept separate from the RDP semantic decoder so device-loss lifetime and the
// old-GPU D16 fallback are explicit and easy to audit.

#include <algorithm>
#include <cstdint>
#include <cstring>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <d3d9.h>

#include "dx9_depth.hpp"

namespace ogre::dx9depth {

class Surface {
  public:
    Surface() = default;
    ~Surface() { release(); }
    Surface(const Surface&) = delete;
    Surface& operator=(const Surface&) = delete;

    void release() {
        if (surface_) {
            surface_->Release();
            surface_ = nullptr;
        }
        address_ = 0;
        width_ = height_ = 0;
        initialized_ = false;
    }

    bool valid_for(uint32_t address, int width, int height) const {
        return surface_ && address_ == address && width_ == width && height_ == height;
    }

    bool ensure(IDirect3DDevice9* device, uint32_t address, int width, int height) {
        if (!device || !address || width <= 0 || height <= 0) return false;
        if (valid_for(address, width, height)) return true;
        release();

        IDirect3DSurface9* created = nullptr;
        const HRESULT hr = device->CreateDepthStencilSurface(
            static_cast<UINT>(width), static_cast<UINT>(height), D3DFMT_D16,
            D3DMULTISAMPLE_NONE, 0, TRUE, &created, nullptr);
        if (FAILED(hr) || !created) return false;

        surface_ = created;
        address_ = address;
        width_ = width;
        height_ = height;
        initialized_ = false;
        return true;
    }

    bool attach(IDirect3DDevice9* device, uint32_t address, int width, int height,
                const Mode& mode, IDirect3DSurface9*& old_depth) {
        old_depth = nullptr;
        if (!device || !mode.enabled()) return false;
        if (!ensure(device, address, width, height)) return false;

        // No auto-depth surface is requested by the DX9 device, so failure here
        // normally just means there was no old surface. Keep a COM reference
        // only when GetDepthStencilSurface succeeds.
        device->GetDepthStencilSurface(&old_depth);
        if (FAILED(device->SetDepthStencilSurface(surface_))) {
            if (old_depth) {
                old_depth->Release();
                old_depth = nullptr;
            }
            return false;
        }

        if (!initialized_) {
            if (FAILED(device->Clear(0, nullptr, D3DCLEAR_ZBUFFER, 0, 1.0f, 0))) {
                device->SetDepthStencilSurface(old_depth);
                if (old_depth) {
                    old_depth->Release();
                    old_depth = nullptr;
                }
                return false;
            }
            initialized_ = true;
        }

        device->SetRenderState(D3DRS_ZENABLE, TRUE);
        device->SetRenderState(D3DRS_ZWRITEENABLE, mode.update ? TRUE : FALSE);
        device->SetRenderState(D3DRS_ZFUNC, mode.compare ? D3DCMP_LESSEQUAL : D3DCMP_ALWAYS);

        // N64 decal mode biases coplanar decals toward the camera. A tiny D3D9
        // depth bias is a conservative approximation and is disabled for every
        // other Z mode.
        float bias = mode.decal() ? -1.0e-4f : 0.0f;
        DWORD bias_bits = 0;
        static_assert(sizeof(bias_bits) == sizeof(bias));
        std::memcpy(&bias_bits, &bias, sizeof(bias_bits));
        device->SetRenderState(D3DRS_DEPTHBIAS, bias_bits);
        return true;
    }

    void detach(IDirect3DDevice9* device, IDirect3DSurface9* old_depth) {
        if (!device) return;
        device->SetRenderState(D3DRS_ZENABLE, FALSE);
        device->SetRenderState(D3DRS_ZWRITEENABLE, FALSE);
        device->SetRenderState(D3DRS_ZFUNC, D3DCMP_LESSEQUAL);
        DWORD zero = 0;
        device->SetRenderState(D3DRS_DEPTHBIAS, zero);
        device->SetDepthStencilSurface(old_depth);
        if (old_depth) old_depth->Release();
    }

    bool clear_rect(IDirect3DDevice9* device, IDirect3DSurface9* color_target,
                    uint32_t address, int width, int height,
                    LONG left, LONG top, LONG right, LONG bottom) {
        if (!device || !color_target) return false;
        if (!ensure(device, address, width, height)) return false;
        left = std::clamp<LONG>(left, 0, width);
        top = std::clamp<LONG>(top, 0, height);
        right = std::clamp<LONG>(right, 0, width);
        bottom = std::clamp<LONG>(bottom, 0, height);
        if (right <= left || bottom <= top) return true;

        IDirect3DSurface9* old_rt = nullptr;
        IDirect3DSurface9* old_depth = nullptr;
        if (FAILED(device->GetRenderTarget(0, &old_rt)) || !old_rt) return false;
        device->GetDepthStencilSurface(&old_depth);

        bool ok = SUCCEEDED(device->SetRenderTarget(0, color_target));
        if (ok) ok = SUCCEEDED(device->SetDepthStencilSurface(surface_));
        if (ok) {
            D3DVIEWPORT9 vp{0, 0, static_cast<DWORD>(width), static_cast<DWORD>(height), 0.0f, 1.0f};
            device->SetViewport(&vp);
            D3DRECT rect{left, top, right, bottom};
            ok = SUCCEEDED(device->Clear(1, &rect, D3DCLEAR_ZBUFFER, 0, 1.0f, 0));
            if (ok) initialized_ = true;
        }

        device->SetDepthStencilSurface(old_depth);
        device->SetRenderTarget(0, old_rt);
        if (old_depth) old_depth->Release();
        old_rt->Release();
        return ok;
    }

    uint32_t address() const { return address_; }
    int width() const { return width_; }
    int height() const { return height_; }

  private:
    IDirect3DSurface9* surface_ = nullptr;
    uint32_t address_ = 0;
    int width_ = 0;
    int height_ = 0;
    bool initialized_ = false;
};

} // namespace ogre::dx9depth
