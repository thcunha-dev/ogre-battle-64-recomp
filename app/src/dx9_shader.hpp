#pragma once

// Direct3D 9 runtime bridge for the precompiled Ogre Battle 64 RDP ps_3_0.
// There is intentionally no D3DX/D3DCompiler dependency: the build produces
// dx9_rdp_ps.cso with fxc and the game loads those bytes directly.

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <vector>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <d3d9.h>

#include "dx9_rdp_state.hpp"

namespace ogre::dx9shader {

constexpr wchar_t kShaderFilename[] = L"dx9_rdp_ps.cso";
constexpr uint32_t kPs30VersionToken = 0xFFFF0300u;
constexpr UINT kConstantRegisters = 12;

inline bool executable_directory(wchar_t* out, size_t count) {
    if (!out || count < 4) return false;
    const DWORD n = GetModuleFileNameW(nullptr, out, static_cast<DWORD>(count));
    if (n == 0 || n >= count) return false;
    for (DWORD i = n; i > 0; --i) {
        if (out[i - 1] == L'\\' || out[i - 1] == L'/') {
            out[i] = L'\0';
            return true;
        }
    }
    out[0] = L'.'; out[1] = L'\\'; out[2] = L'\0';
    return true;
}

inline bool shader_path(wchar_t* out, size_t count) {
    if (!executable_directory(out, count)) return false;
    const size_t used = wcslen(out);
    const size_t name_len = wcslen(kShaderFilename);
    if (used + name_len + 1 > count) return false;
    memcpy(out + used, kShaderFilename, (name_len + 1) * sizeof(wchar_t));
    return true;
}

inline bool read_shader_bytecode(std::vector<uint8_t>& bytes) {
    wchar_t path[MAX_PATH]{};
    if (!shader_path(path, MAX_PATH)) {
        fprintf(stderr, "[dx9] could not construct ps_3_0 shader path\n");
        return false;
    }
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "[dx9] missing dx9_rdp_ps.cso beside executable (Win32 error %lu)\n",
                static_cast<unsigned long>(GetLastError()));
        return false;
    }
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(file, &size) || size.QuadPart < 8 || size.QuadPart > 65536 ||
        (size.QuadPart & 3) != 0) {
        fprintf(stderr, "[dx9] invalid ps_3_0 bytecode size\n");
        CloseHandle(file);
        return false;
    }
    bytes.resize(static_cast<size_t>(size.QuadPart));
    DWORD got = 0;
    const BOOL ok = ReadFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &got, nullptr);
    CloseHandle(file);
    if (!ok || got != bytes.size()) {
        fprintf(stderr, "[dx9] failed reading complete ps_3_0 bytecode\n");
        bytes.clear();
        return false;
    }
    uint32_t version = 0;
    memcpy(&version, bytes.data(), sizeof(version));
    if (version != kPs30VersionToken) {
        fprintf(stderr, "[dx9] dx9_rdp_ps.cso has shader token 0x%08X, expected ps_3_0\n",
                version);
        bytes.clear();
        return false;
    }
    return true;
}

inline IDirect3DPixelShader9* create_rdp_pixel_shader(IDirect3DDevice9* device) {
    if (!device) return nullptr;
    std::vector<uint8_t> bytes;
    if (!read_shader_bytecode(bytes)) return nullptr;
    IDirect3DPixelShader9* shader = nullptr;
    const HRESULT hr = device->CreatePixelShader(
        reinterpret_cast<const DWORD*>(bytes.data()), &shader);
    if (FAILED(hr) || !shader) {
        fprintf(stderr, "[dx9] CreatePixelShader(ps_3_0) failed (0x%08lX)\n",
                static_cast<unsigned long>(hr));
        return nullptr;
    }
    fprintf(stderr, "[dx9] RDP ps_3_0 loaded (%zu bytes, no runtime compiler)\n", bytes.size());
    return shader;
}

struct Constants {
    // c0..c11, exactly matching dx9_rdp_ps.hlsl.
    float c[kConstantRegisters][4]{};

    void set_color(UINT reg, const float v[4]) {
        if (reg >= kConstantRegisters) return;
        for (int i = 0; i < 4; ++i) c[reg][i] = v[i];
    }

    static void set4(float dst[4], float a, float b, float cc, float d) {
        dst[0] = a; dst[1] = b; dst[2] = cc; dst[3] = d;
    }

    void build(const dx9rdp::Combiner& combiner, const dx9rdp::Blender& blender,
               const float prim[4], const float env[4], const float fog[4],
               const float blend[4], float k4, float k5, uint32_t cycle_type,
               int debug_mode = 0) {
        set_color(0, prim);
        set_color(1, env);
        set_color(2, fog);
        set_color(3, blend);

        const float shader_cycle = cycle_type == dx9rdp::kCycCopy ? 0.0f
                                 : cycle_type == dx9rdp::kCyc2 ? 2.0f : 1.0f;
        set4(c[4], k4, k5, shader_cycle, static_cast<float>(blender.blend_cycles));

        // RDP 1-cycle ignores mux 0 and evaluates mux 1. For 2-cycle, c5/c6
        // carry mux 0 and c7/c8 carry mux 1. Mapping it here keeps the shader
        // small and makes 1-cycle use the same first evaluation path.
        const int first = (cycle_type == dx9rdp::kCyc1) ? 1 : 0;
        set4(c[5], static_cast<float>(combiner.ca[first]), static_cast<float>(combiner.cb[first]),
                   static_cast<float>(combiner.cc[first]), static_cast<float>(combiner.cd[first]));
        set4(c[6], static_cast<float>(combiner.aa[first]), static_cast<float>(combiner.ab[first]),
                   static_cast<float>(combiner.ac[first]), static_cast<float>(combiner.ad[first]));
        set4(c[7], static_cast<float>(combiner.ca[1]), static_cast<float>(combiner.cb[1]),
                   static_cast<float>(combiner.cc[1]), static_cast<float>(combiner.cd[1]));
        set4(c[8], static_cast<float>(combiner.aa[1]), static_cast<float>(combiner.ab[1]),
                   static_cast<float>(combiner.ac[1]), static_cast<float>(combiner.ad[1]));
        set4(c[9], static_cast<float>(blender.p[0]), static_cast<float>(blender.m[0]),
                   static_cast<float>(blender.a[0]), static_cast<float>(blender.b[0]));
        set4(c[10], static_cast<float>(blender.p[1]), static_cast<float>(blender.m[1]),
                    static_cast<float>(blender.a[1]), static_cast<float>(blender.b[1]));
        set4(c[11], blender.force_blend ? 1.0f : 0.0f,
                    static_cast<float>(blender.approx), static_cast<float>(debug_mode), 0.0f);
    }
};

inline bool upload_constants(IDirect3DDevice9* device, const Constants& constants) {
    if (!device) return false;
    return SUCCEEDED(device->SetPixelShaderConstantF(
        0, &constants.c[0][0], kConstantRegisters));
}

inline void apply_framebuffer_blend(IDirect3DDevice9* device,
                                    const dx9rdp::Blender& blender) {
    if (!device) return;
    if (blender.alpha_blend) {
        device->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
        device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
        device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
        device->SetRenderState(D3DRS_BLENDOP, D3DBLENDOP_ADD);
    } else {
        device->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
    }
}

} // namespace ogre::dx9shader
