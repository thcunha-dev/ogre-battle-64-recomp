// Ogre Battle 64 Direct3D 9 low-end renderer - Stage 5.
//
// Reuses the validated Stage 4 device/framebuffer/texture/combiner implementation
// and adds the F3DEX2 geometry path plus the S2DEX2 object/sprite path used by
// Ogre Battle 64's NJPEG/background display lists. The N64 semantics mirror the
// validated WebGL renderer; only the GPU-facing draw code is Direct3D 9.

// Pre-include everything Stage 4 includes before the narrow access macro below,
// so `private -> protected` only affects the Stage 4 renderer class itself and
// never standard/runtime headers.
#include "renderer.hpp"
#include "dx9_texture.hpp"
#include "dx9_rdp_state.hpp"
#include "dx9_shader.hpp"
#include "dx9_geometry.hpp"
#include "dx9_s2dex.hpp"
#include "gbi.hpp"
#include "milestones.hpp"
#include "ultramodern/renderer_context.hpp"
#include "ultramodern/ultramodern.hpp"

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

// Compile Stage 4 as a reusable base in this same translation unit. Names that
// would otherwise export the active renderer are renamed; Stage 5 supplies the
// public factory/hooks at the end of this file.
#define final
#define private protected
#define DX9Renderer DX9RendererStage4
#define g_active_renderer g_active_renderer_stage4
#define create_renderer create_renderer_stage4
#define ogre_sync_framebuffers ogre_sync_framebuffers_stage4
#define ogre_gfx_stats ogre_gfx_stats_stage4
#include "dx9_renderer_stage4.inl"
#undef ogre_gfx_stats
#undef ogre_sync_framebuffers
#undef create_renderer
#undef g_active_renderer
#undef DX9Renderer
#undef private
#undef final

namespace ogre {
namespace {

class DX9Renderer final : public DX9RendererStage4 {
  public:
    DX9Renderer(uint8_t* rdram, ultramodern::renderer::WindowHandle window_handle)
        : DX9RendererStage4(rdram, window_handle) {
        if (valid()) {
            OGRE_MILESTONE("RENDERER", "DX9 stage5 F3DEX2 + S2DEX2 geometry layer enabled");
        }
    }

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
                execute_stage5(dl, ucode == 0x000A5110u);
            }
        }
        if (frame <= 8 || (frame % 300) == 0) {
            OGRE_MILESTONE("DX9-DL",
                           "stage5 dl=%u fills=%u copyRects=%u shaderRects=%u tris=%u skippedTris=%u s2d=%u skippedS2d=%u texUploads=%u",
                           frame, fill_count_, copy_texrect_count_, shader_texrect_count_,
                           triangle_count_, skipped_triangle_count_, s2dex_rect_count_,
                           skipped_s2dex_rect_count_, texture_upload_count_);
        }
        if (instant_present_) present_vi();
    }

    void shutdown() override {
        sync_framebuffers();
        std::lock_guard<std::mutex> stats_lock(g_stats_mutex);
        refresh_stats_snapshot();
        OGRE_MILESTONE("RENDERER",
                       "DX9 stage5 shutdown: DL=%u VI=%u rects=%u/%u tris=%u skippedTris=%u s2d=%u skippedS2d=%u",
                       display_list_count_.load(), vi_swap_count_.load(), copy_texrect_count_,
                       shader_texrect_count_, triangle_count_, skipped_triangle_count_,
                       s2dex_rect_count_, skipped_s2dex_rect_count_);
        OGRE_MILESTONE("GFX-WORKLOAD", "%s", g_stats_snapshot);
    }

  protected:
    struct Stage5Ctx {
        DX9Renderer* self = nullptr;
        ExecCtx base{};
        dx9geom::State geom{};
        dx9s2d::ObjMtx obj_mtx{};
    };

    void execute_stage5(uint32_t dl, bool s2dex) {
        Stage5Ctx ctx{};
        ctx.self = this;
        ctx.base.self = this;
        ctx.base.s2dex = s2dex;
        ctx.base.state.cimg_address = last_cimg_address_;
        ctx.base.state.cimg_row_bytes = last_cimg_row_bytes_;
        ctx.base.state.cimg_width = last_cimg_width_;
        ctx.base.state.cimg_siz = last_cimg_siz_;
        ctx.base.state.cimg_fmt = last_cimg_fmt_;
        ctx.base.state.combiner.decode(0, 0);

        auto visitor = [](void* user, const gbi::DlCommand& cmd) {
            auto* c = static_cast<Stage5Ctx*>(user);
            c->self->exec_stage5_command(*c, cmd);
        };
        gbi::walk_dl(rdram_, dl, visitor, &ctx);
    }

    void exec_stage5_command(Stage5Ctx& ctx, const gbi::DlCommand& c) {
        // S2DEX2 collides with F3DEX2 at 0x01/0x02/0xDA/0xDC/0xE4. Handle
        // those commands first and do not let Stage 4 reinterpret them.
        if (ctx.base.s2dex) {
            switch (c.op) {
                case dx9s2d::OBJ_MOVEMEM: {
                    const uint32_t addr = gbi::resolve_address(ctx.base.segments, c.w1);
                    dx9s2d::set_obj_matrix(rdram_, addr, c.w0 & 0xFFFFu, ctx.obj_mtx);
                    return;
                }
                case dx9s2d::OBJ_RECTANGLE_R:
                case dx9s2d::OBJ_RECTANGLE: {
                    const uint32_t addr = gbi::resolve_address(ctx.base.segments, c.w1);
                    draw_s2dex_object(ctx.base.state, ctx.obj_mtx, addr, false);
                    return;
                }
                case dx9s2d::OBJ_SPRITE: {
                    const uint32_t addr = gbi::resolve_address(ctx.base.segments, c.w1);
                    draw_s2dex_object(ctx.base.state, ctx.obj_mtx, addr, true);
                    return;
                }
                case dx9s2d::RDPHALF_0:
                    // Same deliberate boundary as the validated WebGL path:
                    // OB64's NJPEG lists use the object commands above. The
                    // S2DEX2 RDPHALF_0 texrect encoding is not needed there and
                    // must not be mistaken for F3DEX2 G_TEXRECT.
                    if (!s2dex_half0_logged_) {
                        s2dex_half0_logged_ = true;
                        OGRE_MILESTONE("DX9-S2D", "S2DEX2 RDPHALF_0 seen and ignored (object path remains active)");
                    }
                    return;
                default:
                    break;
            }
        } else {
            switch (c.op) {
                case gbi::OP_MOVEMEM: {
                    const uint8_t idx = static_cast<uint8_t>((c.w0 >> 16) & 0xFFu);
                    if (idx == gbi::MV_VIEWPORT) {
                        const uint32_t addr = gbi::resolve_address(ctx.base.segments, c.w1);
                        dx9geom::set_viewport(ctx.geom, rdram_, addr);
                    }
                    break;
                }
                case gbi::OP_MTX: {
                    dx9geom::Mat4 mat{};
                    const uint32_t addr = gbi::resolve_address(ctx.base.segments, c.w1);
                    if (dx9geom::read_matrix(rdram_, addr, mat)) {
                        // F3DEX2 stores the PUSH bit inverted in the command;
                        // dx9geom::apply_matrix mirrors the validated WebGL
                        // matrix semantics including that flag convention.
                        dx9geom::apply_matrix(ctx.geom, mat, c.w0 & 0xFFu);
                    }
                    break;
                }
                case gbi::OP_POPMTX: {
                    const uint32_t count = std::max(1u, c.w1 >> 6);
                    dx9geom::pop_modelview(ctx.geom, count);
                    break;
                }
                case gbi::OP_GEOMETRYMODE: {
                    const uint32_t off = p0(c.w0, 0, 24);
                    const uint32_t on = c.w1;
                    ctx.geom.geometry_mode = (ctx.geom.geometry_mode & ~off) | on;
                    break;
                }
                case gbi::OP_TEXTURE:
                    dx9geom::set_texture(ctx.geom, c.w0, c.w1);
                    break;
                case gbi::OP_VTX: {
                    const int n = static_cast<int>(p0(c.w0, 12, 8));
                    const int end = static_cast<int>(p0(c.w0, 1, 7));
                    const int start = end - n;
                    const uint32_t addr = gbi::resolve_address(ctx.base.segments, c.w1);
                    dx9geom::load_vertices(ctx.geom, rdram_, addr, start, n);
                    break;
                }
                case gbi::OP_TRI1:
                    draw_triangle_word(ctx.base.state, ctx.geom, c.w0);
                    break;
                case gbi::OP_TRI2:
                case gbi::OP_QUAD:
                    draw_triangle_word(ctx.base.state, ctx.geom, c.w0);
                    draw_triangle_word(ctx.base.state, ctx.geom, c.w1);
                    break;
                default:
                    break;
            }
        }

        // Stage 4 remains the single owner of RDP state, texture loads,
        // framebuffers, fills and normal F3DEX2 TEXRECT/combiner execution.
        exec_command(ctx.base, c);
    }

    bool begin_rdp_target(RdpState& st, int bottom, Dx9Framebuffer*& fb,
                          IDirect3DSurface9*& old) {
        fb = ensure_fb(st, bottom);
        if (!fb || !fb->surface) return false;
        old = nullptr;
        if (FAILED(device_->GetRenderTarget(0, &old))) return false;
        if (FAILED(device_->SetRenderTarget(0, fb->surface))) {
            old->Release();
            old = nullptr;
            return false;
        }
        D3DVIEWPORT9 vp{0, 0, static_cast<DWORD>(fb->width), static_cast<DWORD>(fb->height), 0.0f, 1.0f};
        device_->SetViewport(&vp);
        if (st.scissor_enabled) {
            RECT sc{std::clamp(st.scissor_x0, 0, fb->width), std::clamp(st.scissor_y0, 0, fb->height),
                    std::clamp(st.scissor_x1, 0, fb->width), std::clamp(st.scissor_y1, 0, fb->height)};
            device_->SetScissorRect(&sc);
            device_->SetRenderState(D3DRS_SCISSORTESTENABLE, TRUE);
        } else {
            device_->SetRenderState(D3DRS_SCISSORTESTENABLE, FALSE);
        }
        return true;
    }

    void end_rdp_target(IDirect3DSurface9* old) {
        device_->SetPixelShader(nullptr);
        device_->SetTexture(0, nullptr);
        device_->SetTexture(1, nullptr);
        device_->SetRenderState(D3DRS_SCISSORTESTENABLE, FALSE);
        if (old) {
            device_->SetRenderTarget(0, old);
            old->Release();
        }
    }

    bool bind_rdp_program(RdpState& st, uint32_t cyc, int tile0,
                          TileGpu* tg0, TileGpu* tg1) {
        const bool bilerp = ((st.othermode_h >> 12) & 3u) != 0u;
        const int tile1 = (tile0 + 1) & 7;
        set_sampler(0, st.tex.tiles[tile0 & 7], bilerp);
        set_sampler(1, st.tex.tiles[tile1], bilerp);
        device_->SetTexture(0, tg0 ? tg0->texture : white_tex_);
        device_->SetTexture(1, tg1 ? tg1->texture : white_tex_);

        if (cyc == dx9rdp::kCycCopy) {
            device_->SetPixelShader(nullptr);
            device_->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
            return true;
        }
        if ((cyc != dx9rdp::kCyc1 && cyc != dx9rdp::kCyc2) ||
            !rdp_shader_ || !st.combiner.valid) {
            return false;
        }
        st.blender.decode(st.othermode_l, st.othermode_h);
        dx9shader::Constants constants;
        constants.build(st.combiner, st.blender, st.prim, st.env, st.fog, st.blend,
                        static_cast<float>(st.tex.convert_k[4] & 0x1FF) / 255.0f,
                        static_cast<float>(st.tex.convert_k[5] & 0x1FF) / 255.0f, cyc);
        device_->SetPixelShader(rdp_shader_);
        dx9shader::upload_constants(device_, constants);
        dx9shader::apply_framebuffer_blend(device_, st.blender);
        return true;
    }

    void draw_s2dex_object(RdpState& st, const dx9s2d::ObjMtx& matrix,
                           uint32_t sprite_addr, bool full_matrix) {
        dx9s2d::ObjSprite sprite{};
        if (!dx9s2d::decode_obj_sprite(rdram_, sprite_addr, sprite)) {
            ++skipped_s2dex_rect_count_;
            return;
        }
        const dx9s2d::ObjectRect rect = dx9s2d::compute_object_rect(sprite, matrix, full_matrix);
        if (!(rect.x1 > rect.x0) || !(rect.y1 > rect.y0) ||
            rect.imageW <= 0.0f || rect.imageH <= 0.0f) {
            ++skipped_s2dex_rect_count_;
            return;
        }

        // Match WebGL draw_obj_rect exactly: S2DEX2 programs render tile 0 from
        // the object's own texture descriptor, then consumes the block loaded by
        // the preceding LOADTILE/LOADBLOCK into TMEM.
        constexpr int tile0 = 0;
        constexpr int tile1 = 1;
        dx9tex::TileState& t = st.tex.tiles[tile0];
        t.fmt = sprite.imageFmt;
        t.siz = sprite.imageSiz;
        t.line = sprite.imageStride;
        t.tmem = sprite.imageAdrs;
        t.palette = sprite.imagePal;
        t.cms = t.cmt = 0;
        t.masks = t.maskt = 0;
        t.shifts = t.shiftt = 0;
        t.uls = t.ult = 0;
        t.lrs = static_cast<uint16_t>(std::max<int32_t>((static_cast<int32_t>(sprite.imageW) >> 3) - 4, 0));
        t.lrt = static_cast<uint16_t>(std::max<int32_t>((static_cast<int32_t>(sprite.imageH) >> 3) - 4, 0));
        if (st.tex.pending_load.valid) {
            dx9tex::set_tile_image(st.tex, tile0, st.tex.pending_load.address,
                                   st.tex.pending_load.stride, st.tex.pending_load.generation);
            st.tex.pending_load.valid = false;
        }

        const int saved_tile = st.tex.active_tile;
        st.tex.active_tile = tile0;
        const bool have0 = ensure_tile(st, tile0);
        const bool have1 = ensure_tile(st, tile1);
        TileGpu* tg0 = have0 ? &tile_gpu_[tile0] : nullptr;
        TileGpu* tg1 = have1 ? &tile_gpu_[tile1] : nullptr;
        if (!tg0) {
            st.tex.active_tile = saved_tile;
            ++skipped_s2dex_rect_count_;
            return;
        }

        const uint32_t cyc = (st.othermode_h >> 20) & 3u;
        if (cyc != dx9rdp::kCycCopy && cyc != dx9rdp::kCyc1 && cyc != dx9rdp::kCyc2) {
            st.tex.active_tile = saved_tile;
            ++skipped_s2dex_rect_count_;
            return;
        }

        Dx9Framebuffer* fb = nullptr;
        IDirect3DSurface9* old = nullptr;
        const int bottom = static_cast<int>(std::ceil(std::max(rect.y0, rect.y1)));
        if (!begin_rdp_target(st, bottom, fb, old)) {
            st.tex.active_tile = saved_tile;
            ++skipped_s2dex_rect_count_;
            return;
        }
        if (!bind_rdp_program(st, cyc, tile0, tg0, tg1)) {
            end_rdp_target(old);
            st.tex.active_tile = saved_tile;
            ++skipped_s2dex_rect_count_;
            return;
        }

        const float px[4][2] = {
            {rect.x0 - 0.5f, rect.y0 - 0.5f},
            {rect.x1 - 0.5f, rect.y0 - 0.5f},
            {rect.x0 - 0.5f, rect.y1 - 0.5f},
            {rect.x1 - 0.5f, rect.y1 - 0.5f}
        };
        const float raw_uv[4][2] = {
            {rect.u0, rect.v0}, {rect.u1, rect.v0},
            {rect.u0, rect.v1}, {rect.u1, rect.v1}
        };

        HRESULT hr = E_FAIL;
        if (SUCCEEDED(device_->BeginScene())) {
            if (cyc == dx9rdp::kCycCopy) {
                device_->SetFVF(kCopyFvf);
                CopyVertex q[4]{};
                for (int i = 0; i < 4; ++i) {
                    float u = 0.0f, v = 0.0f;
                    normalized_uv(tg0, raw_uv[i][0], raw_uv[i][1], u, v);
                    q[i] = {px[i][0], px[i][1], 0.0f, 1.0f, u, v};
                }
                hr = device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, q, sizeof(CopyVertex));
            } else {
                device_->SetFVF(kRdpFvf);
                RdpVertex q[4]{};
                for (int i = 0; i < 4; ++i) {
                    float u0 = 0.0f, v0 = 0.0f, u1 = 0.0f, v1 = 0.0f;
                    normalized_uv(tg0, raw_uv[i][0], raw_uv[i][1], u0, v0);
                    normalized_uv(tg1, raw_uv[i][0], raw_uv[i][1], u1, v1);
                    q[i] = {px[i][0], px[i][1], 0.0f, 1.0f, 0xFFFFFFFFu,
                            u0, v0, u1, v1};
                }
                hr = device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, q, sizeof(RdpVertex));
            }
            device_->EndScene();
        }
        end_rdp_target(old);
        st.tex.active_tile = saved_tile;

        if (SUCCEEDED(hr)) {
            fb->dirty = true;
            fb->last_write_seq = ++framebuffer_write_seq_;
            ++s2dex_rect_count_;
            if (s2dex_log_count_ < 4) {
                ++s2dex_log_count_;
                OGRE_MILESTONE("DX9-S2D",
                               "object fmt=%u siz=%u img=%.0fx%.0f rect=(%.1f,%.1f)-(%.1f,%.1f) cycle=%u",
                               static_cast<unsigned>(sprite.imageFmt), static_cast<unsigned>(sprite.imageSiz),
                               rect.imageW, rect.imageH, rect.x0, rect.y0, rect.x1, rect.y1,
                               static_cast<unsigned>(cyc));
            }
        } else {
            ++skipped_s2dex_rect_count_;
        }
    }

    void draw_triangle_word(RdpState& st, const dx9geom::State& geom, uint32_t word) {
        const int i0 = static_cast<int>(p0(word, 17, 7));
        const int i1 = static_cast<int>(p0(word, 9, 7));
        const int i2 = static_cast<int>(p0(word, 1, 7));
        draw_triangle(st, geom, i0, i1, i2);
    }

    void draw_triangle(RdpState& st, const dx9geom::State& geom, int i0, int i1, int i2) {
        const uint32_t cyc = (st.othermode_h >> 20) & 3u;
        if ((cyc != dx9rdp::kCyc1 && cyc != dx9rdp::kCyc2 && cyc != dx9rdp::kCycCopy) ||
            (cyc != dx9rdp::kCycCopy && (!rdp_shader_ || !st.combiner.valid))) {
            ++skipped_triangle_count_;
            return;
        }

        Dx9Framebuffer* fb = ensure_fb(st, st.scissor_enabled ? st.scissor_y1 : 240);
        if (!fb || !fb->surface) {
            ++skipped_triangle_count_;
            return;
        }

        const dx9geom::TransformedVertex tv[3] = {
            dx9geom::transform_vertex(geom, i0, fb->width, fb->height),
            dx9geom::transform_vertex(geom, i1, fb->width, fb->height),
            dx9geom::transform_vertex(geom, i2, fb->width, fb->height)
        };
        if (!tv[0].valid || !tv[1].valid || !tv[2].valid) {
            ++skipped_triangle_count_;
            return;
        }

        const int tile0 = st.tex.active_tile & 7;
        const int tile1 = (tile0 + 1) & 7;
        const bool have0 = geom.texture_on && ensure_tile(st, tile0);
        const bool have1 = geom.texture_on && ensure_tile(st, tile1);
        TileGpu* tg0 = have0 ? &tile_gpu_[tile0] : nullptr;
        TileGpu* tg1 = have1 ? &tile_gpu_[tile1] : nullptr;
        if (cyc == dx9rdp::kCycCopy && !tg0) {
            ++skipped_triangle_count_;
            return;
        }

        IDirect3DSurface9* old = nullptr;
        Dx9Framebuffer* target = nullptr;
        if (!begin_rdp_target(st, fb->height, target, old)) {
            ++skipped_triangle_count_;
            return;
        }
        if (!bind_rdp_program(st, cyc, tile0, tg0, tg1)) {
            end_rdp_target(old);
            ++skipped_triangle_count_;
            return;
        }

        if (cyc == dx9rdp::kCycCopy) {
            // Geometry in COPY cycle is unusual for OB64, but keep a correct
            // fixed-function path rather than requiring ps_3_0 unnecessarily.
            device_->SetFVF(kCopyFvf);
            CopyVertex out[3]{};
            for (int i = 0; i < 3; ++i) {
                float u = 0.0f, v = 0.0f;
                normalized_uv(tg0, tv[i].s, tv[i].t, u, v);
                out[i] = {tv[i].x - 0.5f, tv[i].y - 0.5f, 0.0f, tv[i].rhw, u, v};
            }
            HRESULT hr = E_FAIL;
            if (SUCCEEDED(device_->BeginScene())) {
                hr = device_->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 1, out, sizeof(CopyVertex));
                device_->EndScene();
            }
            end_rdp_target(old);
            if (SUCCEEDED(hr)) {
                target->dirty = true;
                target->last_write_seq = ++framebuffer_write_seq_;
                ++triangle_count_;
            } else {
                ++skipped_triangle_count_;
            }
            return;
        }

        device_->SetFVF(kRdpFvf);
        RdpVertex out[3]{};
        for (int i = 0; i < 3; ++i) {
            float u0 = 0.0f, v0 = 0.0f, u1 = 0.0f, v1 = 0.0f;
            normalized_uv(tg0, tv[i].s, tv[i].t, u0, v0);
            normalized_uv(tg1, tv[i].s, tv[i].t, u1, v1);
            out[i] = {
                tv[i].x - 0.5f,
                tv[i].y - 0.5f,
                0.0f,
                tv[i].rhw,
                dx9geom::shade_argb(tv[i]),
                u0, v0, u1, v1
            };
        }

        HRESULT hr = E_FAIL;
        if (SUCCEEDED(device_->BeginScene())) {
            hr = device_->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 1, out, sizeof(RdpVertex));
            device_->EndScene();
        }
        end_rdp_target(old);

        if (SUCCEEDED(hr)) {
            target->dirty = true;
            target->last_write_seq = ++framebuffer_write_seq_;
            ++triangle_count_;
        } else {
            ++skipped_triangle_count_;
        }
    }

    unsigned triangle_count_ = 0;
    unsigned skipped_triangle_count_ = 0;
    unsigned s2dex_rect_count_ = 0;
    unsigned skipped_s2dex_rect_count_ = 0;
    unsigned s2dex_log_count_ = 0;
    bool s2dex_half0_logged_ = false;
};

DX9Renderer* g_active_renderer = nullptr;
} // namespace

std::unique_ptr<ultramodern::renderer::RendererContext> create_renderer(
    uint8_t* rdram, ultramodern::renderer::WindowHandle window_handle, bool developer_mode) {
    (void)developer_mode;
    auto renderer = std::make_unique<DX9Renderer>(rdram, window_handle);
    g_active_renderer = renderer.get();
    return renderer;
}
} // namespace ogre

extern "C" {
void ogre_sync_framebuffers() {
    if (ogre::g_active_renderer) ogre::g_active_renderer->sync_framebuffers();
}
const char* ogre_gfx_stats() {
    std::lock_guard<std::mutex> lock(ogre::g_stats_mutex);
    return ogre::g_stats_snapshot;
}
}
