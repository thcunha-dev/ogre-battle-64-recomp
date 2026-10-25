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
- Conservative D3D9 formats (`A8R8G8B8`, 16-bit guest RGBA5551 decode).
- No MSAA requirement.
- Point sampling by default for the N64 framebuffer.
- No D3D11/D3D12/DXGI requirement in the DX9 route.
- RDP programmable path should fit Shader Model 3.0; avoid heavyweight runtime
  shader compilers and expensive per-draw allocations.
- Primary real-hardware target: NVIDIA GeForce 410M-class hardware.

## Architecture

Do **not** write another N64 graphics interpreter from scratch.

`app/src/web_renderer.cpp` already contains the project's validated independent
implementation of the game-facing graphics semantics:

- F3DEX2 display-list execution;
- S2DEX2 object/sprite commands;
- RDP OtherMode and combiner decoding;
- blender decoding;
- RGBA/IA/I/CI texture decode and TLUT handling;
- guest colour-image/framebuffer tracking;
- VI framebuffer sizing/presentation;
- N64ModernRuntime RDRAM byte-order handling.

The DX9 renderer therefore has two layers:

1. **Shared N64/RDP semantics** — progressively extracted/reused from the WebGL
   renderer without changing their behaviour.
2. **D3D9 device/output** — textures, render targets, vertex submission,
   scissor/blend state, Shader Model 3.0 combiner shader and presentation.

The important rule is to port the GPU-facing half, not rediscover F3DEX2/RDP
behaviour through trial and error.

## Current implementation

Branch: `dx9-lowend-410m`.

Stage 1 is implemented in `app/src/dx9_renderer.inl` and is selected by the
no-RT64 Windows source when `OGRE_USE_DX9=1` is defined. It:

- creates a plain Direct3D 9 HAL device;
- falls back from hardware to software vertex processing when necessary;
- logs VS/PS caps and maximum texture size;
- handles lost/reset devices and client-window resizes;
- derives 320x240 / 640x480 scanout dimensions from the real VI registers using
  the same rule as the WebGL renderer / RT64;
- decodes 16-bit RGBA5551 and 32-bit RGBA framebuffer pixels from the runtime's
  byte-reversed RDRAM representation;
- uploads scanout into one reusable dynamic D3D9 texture;
- presents using the fixed-function pipeline with point filtering;
- keeps the existing graphics-workload analyzer active.

This stage intentionally does **not** fake RDP drawing. Display lists are
observed/analyzed but the guest VI framebuffer is the only image presented.
The next stage attaches the existing WebGL F3DEX2/S2DEX2/RDP executor to D3D9.

## Next implementation order

1. Move the GL-independent types/helpers from `web_renderer.cpp` into a shared
   renderer core: RenderState, Combiner, Blender, texture decoders, VI helpers,
   GBI identification and display-list execution.
2. Preserve the WebGL build against the shared core so semantic regressions are
   caught at extraction time.
3. Add the D3D9 draw-command backend:
   - dynamic vertex ring buffer;
   - reusable D3D9 texture cache;
   - guest colour-image render-target cache;
   - scissor and fixed render states;
   - FILLRECT / TEXRECT / TEXRECTFLIP;
   - F3DEX2 TRI1 / TRI2 / QUAD;
   - S2DEX2 object rectangle/sprite path.
4. Translate the already-working WebGL combiner/blender formula to one small
   Shader Model 3.0 HLSL program driven by constants. Avoid compiling a new
   shader for every combine mode.
5. Implement dirty framebuffer readback for `ogre_sync_framebuffers()` so the
   game's NJPEG/background CPU copies see D3D9-rendered pixels.
6. Make DX9 a first-class CMake renderer option and package a dedicated Windows
   low-end artifact.

## Test discipline

Use tests as gates, not as exploration:

- one compile/CI check after a coherent patch set;
- one deterministic smoke route after the RDP path can draw a real frame;
- one real GeForce 410M test only when the build is technically ready for it.

Do not produce a sequence of user-facing micro-builds to discover individual
opcodes or state bits. The existing WebGL renderer and RT64 behaviour are the
references for those semantics.
