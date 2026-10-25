// Direct3D 9 low-end renderer entry point.
//
// Stage 6 was written against the newer presentation helper names used during
// bring-up. Stage 4 remains the owner of the actual presenter, so keep this
// migration bridge local to the include boundary instead of duplicating that
// code again. The mapping preserves Stage 4's GPU-framebuffer -> RDRAM fallback
// behavior and can disappear when the milestone files are flattened.

static unsigned g_dx9_stage6_present_count = 0;

#define find_present_fb framebuffer_containing
#define upload_rdram_scanout(address, width, height, siz) upload_vi(*regs, raw)
#define draw_present_texture(texture, width, height, visible_width, visible_height) \
    (((texture) == scanout_tex_) \
        ? draw_scanout() \
        : (present_gpu_fb(*regs, raw) || (upload_vi(*regs, raw) && draw_scanout())))
#define present_count_ (::g_dx9_stage6_present_count)

#include "dx9_renderer_stage6.inl"

#undef present_count_
#undef draw_present_texture
#undef upload_rdram_scanout
#undef find_present_fb
