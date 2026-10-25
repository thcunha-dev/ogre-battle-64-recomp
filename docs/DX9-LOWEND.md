# Ogre Battle 64 — Direct3D 9 low-end port

## Scope

This branch has one goal: run the native Ogre Battle 64 recomp port on old/weak
Windows PCs, with a GeForce 410M-class machine as the practical baseline.

The DX9 build must not depend on RT64, D3D12, DXGI or Vulkan at runtime. It is
not a translation project, randomizer, gameplay mod, texture pack or renderer
experiment. Those are deliberately out of scope.

## Compatibility target

- Windows native build.
- Direct3D 9 device creation through `Direct3DCreate9`.
- Conservative D3D9 formats (`A8R8G8B8`, D16 when depth lands, 16-bit guest
  RGBA5551 decode).
- No MSAA requirement.
- Point sampling by default; bilinear only when the N64 RDP state requests it.
- No D3D11/D3D12/DXGI/Vulkan requirement in the DX9 route.
- General RDP programmable path fits Shader Model 3.0.
- Pixel shader is compiled by `fxc` at build/CI time; do not add a runtime
  D3DX/D3DCompiler dependency.
- Primary real-hardware target: NVIDIA GeForce 410M-class hardware.

## Architecture

Do **not** write another N64 graphics interpreter from scratch.

`app/src/web_renderer.cpp` is the validated independent implementation of the
game-facing graphics semantics and remains the behavioural reference for:

- F3DEX2 display-list execution;
- S2DEX2 object/sprite commands;
- RDP OtherMode and combiner decoding;
- blender decoding;
- RGBA/IA/I/CI/YUV texture decode and TLUT handling;
- guest colour-image/framebuffer tracking and readback;
- VI framebuffer sizing/presentation;
- N64ModernRuntime RDRAM byte-order handling.

The DX9 renderer therefore has two layers:

1. **N64/RDP semantics** — API-independent helpers ported from the validated
   WebGL/RT64 behaviour.
2. **D3D9 device/output** — textures, render targets, vertex submission,
   scissor/blend/depth state, Shader Model 3.0 combiner shader and presentation.

The important rule is to port the GPU-facing half, not rediscover F3DEX2/RDP
behaviour through trial and error.

## Current implementation

Branch: `dx9-lowend-410m`.

The active renderer entry is `app/src/dx9_renderer.inl`; a standalone Windows
translation unit now also exists at `app/src/dx9_renderer.cpp`. The milestone
implementation currently reaches Stage 5 and includes:

- Direct3D 9 HAL device creation with software vertex-processing fallback;
- device-loss/window-resize handling;
- VI sizing and presentation for normal and 640-wide modes;
- guest colour-image render targets;
- GPU framebuffer presentation and GPU -> RDRAM writeback;
- FILLRECT, TEXRECT and TEXRECTFLIP;
- bounded reusable texture uploads;
- RGBA16/32, IA, I, CI/TLUT and YUV texture decoding;
- one general `ps_3_0` RDP combiner/blender shader driven by constants;
- F3DEX2 matrix, viewport, VTX, G_TEXTURE, TRI1, TRI2 and QUAD execution;
- S2DEX2 object matrix/sub-matrix, OBJ_RECTANGLE, OBJ_RECTANGLE_R and OBJ_SPRITE;
- copy-cycle fixed-function paths that do not require the pixel shader;
- workload counters and bounded diagnostics.

The F3DEX2 matrix path matches the validated WebGL semantics, including the
microcode's inverted stored PUSH bit and the matrix multiplication order. The
F3DEX2 G_MOVEMEM viewport index is decoded from the low byte, matching RT64.

`app/src/dx9_depth.hpp` now owns the API-independent depth semantics needed for
the next 3D milestone: RDP `Z_CMP`, `Z_UPD`, ZMODE decoding, recognition of the
SETZIMG/SETCIMG depth-clear idiom, and N64 screen-Z (0..1023) to D3D9 depth
(0..1) normalization. D3D9 depth-surface attachment itself is the next graphics
step; it is not claimed complete yet.

## Build path

`dx9/CMakeLists.txt` is the dedicated low-end entry point. It forces RT64 off,
selects the existing DX9 bring-up route and links only the Windows `d3d9`
system library for graphics:

```text
cmake -S dx9 -B build-dx9 -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-dx9 -j
```

The standalone renderer object is also cross-compiled in CI with LLVM-MinGW.
The gate rejects references to D3D12, DXGI factory creation or Vulkan. A second
Windows CI job compiles `dx9_rdp_ps.hlsl` with Microsoft's `fxc` as `ps_3_0`.

A full distributable game build still requires the repository's generated
recompilation units (`RecompiledFuncs`, bank units and RSP recompilation data),
just like the normal project release build. Renderer development does not need
to block on regenerating those files for every patch.

## Next implementation order

1. Attach a conservative D16 depth surface to the Stage 5 3D path and honor
   `Z_CMP`/`Z_UPD`, while preserving device-reset safety.
2. Handle the game's SETZIMG -> SETCIMG(z-address) -> FILLRECT depth-clear idiom.
3. Feed the transformed N64 screen Z into D3D9 XYZRHW vertices instead of the
   current temporary constant Z.
4. Review RDP alpha/depth corner cases and only add commands proven relevant by
   the WebGL reference or captured workload.
5. Flatten the milestone inheritance/includes once the 3D path is stable.
6. Produce one dedicated Windows low-end artifact and perform one meaningful
   real-hardware GeForce 410M validation.

## Test discipline

Use tests as gates, not as exploration:

- compiler and shader checks for every coherent renderer patch set;
- deterministic code/reference comparison before hardware testing;
- one real GeForce 410M test only when the build can answer a meaningful
  compatibility/rendering question.

Do not produce a sequence of user-facing micro-builds to discover individual
opcodes or state bits. The validated WebGL renderer, RT64 definitions and
existing captured DX9 logs are the first references.
