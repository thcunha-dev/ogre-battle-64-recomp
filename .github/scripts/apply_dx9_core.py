from pathlib import Path


def replace1(s: str, old: str, new: str, name: str) -> str:
    if new in s:
        return s
    if old not in s:
        raise SystemExit(f"missing anchor: {name}")
    return s.replace(old, new, 1)


p = Path("app/CMakeLists.txt")
s = p.read_text(encoding="utf-8")
s = replace1(
    s,
    'option(OGRE_USE_RT64 "Build with the RT64 renderer (native builds only)" ON)\n',
    'option(OGRE_USE_RT64 "Build with the RT64 renderer (native builds only)" ON)\n'
    'option(OGRE_USE_DX9 "Build with the Direct3D 9 low-end renderer (Windows only)" OFF)\n',
    "DX9 option",
)
s = replace1(
    s,
    "if (EMSCRIPTEN)\n    set(OGRE_USE_RT64 OFF)\nendif()\n",
    "if (EMSCRIPTEN)\n"
    "    set(OGRE_USE_RT64 OFF)\n"
    "    set(OGRE_USE_DX9 OFF)\n"
    "endif()\n\n"
    "if (OGRE_USE_DX9 AND NOT WIN32)\n"
    '    message(FATAL_ERROR "OGRE_USE_DX9 is Windows-only")\n'
    "endif()\n"
    "if (OGRE_USE_DX9 AND OGRE_USE_RT64)\n"
    '    message(FATAL_ERROR "OGRE_USE_DX9 and OGRE_USE_RT64 are mutually exclusive")\n'
    "endif()\n",
    "DX9 guards",
)
s = replace1(
    s,
    "# --- Renderer ----------------------------------------------------------------\n"
    "if (OGRE_USE_RT64)\n",
    "# --- Renderer ----------------------------------------------------------------\n"
    "if (OGRE_USE_DX9)\n"
    "    # Native D3D9 path for old/weak Windows GPUs; RT64 is not compiled.\n"
    "    set(OGRE_RENDERER_SOURCES src/dx9_renderer.cpp)\n"
    "elseif (OGRE_USE_RT64)\n",
    "renderer selector",
)
s = replace1(
    s,
    "if (OGRE_USE_RT64)\n"
    "    target_compile_definitions(ogrebattle64 PRIVATE OGRE_USE_RT64=1)\n"
    "endif()\n\n"
    "if (NOT EMSCRIPTEN)\n",
    "if (OGRE_USE_RT64)\n"
    "    target_compile_definitions(ogrebattle64 PRIVATE OGRE_USE_RT64=1)\n"
    "endif()\n"
    "if (OGRE_USE_DX9)\n"
    "    target_compile_definitions(ogrebattle64 PRIVATE OGRE_USE_DX9=1)\n"
    "    target_link_libraries(ogrebattle64 PRIVATE d3d9)\n"
    "endif()\n\n"
    "if (NOT EMSCRIPTEN)\n",
    "DX9 target contract",
)
p.write_text(s, encoding="utf-8")

p = Path("dx9/CMakeLists.txt")
s = p.read_text(encoding="utf-8")
s = replace1(
    s,
    'set(OGRE_USE_RT64 OFF CACHE BOOL "RT64 is disabled in the Direct3D 9 low-end build" FORCE)\n'
    "add_compile_definitions(OGRE_USE_DX9=1)\n",
    'set(OGRE_USE_RT64 OFF CACHE BOOL "RT64 is disabled in the Direct3D 9 low-end build" FORCE)\n'
    'set(OGRE_USE_DX9 ON CACHE BOOL "Direct3D 9 low-end renderer" FORCE)\n'
    "add_compile_definitions(OGRE_USE_DX9=1)\n",
    "wrapper selector",
)
p.write_text(s, encoding="utf-8")

p = Path("app/src/dx9_geometry.hpp")
s = p.read_text(encoding="utf-8")
if "inline bool modify_vertex(" not in s:
    anchor = "inline void set_viewport(State& st, const uint8_t* rdram, uint32_t address) {"
    pos = s.find(anchor)
    if pos < 0:
        raise SystemExit("missing set_viewport anchor")
    fn = r'''// F3DEX2 G_MODIFYVTX mutates the RSP vertex cache after G_VTX.
// RGBA and ST map directly to fields retained by this geometry core.
// XYSCREEN/ZSCREEN require post-transform cache state and are deliberately
// rejected instead of approximated incorrectly.
inline bool modify_vertex(State& st, int index, uint8_t where, uint32_t value) {
    if (index < 0 || index >= kMaxVertices) return false;
    RawVertex& v = st.vertices[index];
    switch (where) {
        case 0x10: // G_MWO_POINT_RGBA
            v.r = static_cast<uint8_t>(value >> 24);
            v.g = static_cast<uint8_t>(value >> 16);
            v.b = static_cast<uint8_t>(value >> 8);
            v.a = static_cast<uint8_t>(value);
            return true;
        case 0x14: // G_MWO_POINT_ST
            v.s = static_cast<int16_t>(value >> 16);
            v.t = static_cast<int16_t>(value & 0xFFFFu);
            return true;
        default:
            return false;
    }
}

'''
    s = s[:pos] + fn + s[pos:]
p.write_text(s, encoding="utf-8")

p = Path("app/src/dx9_renderer_stage6.inl")
s = p.read_text(encoding="utf-8")
if "case gbi::OP_MODIFYVTX:" not in s:
    anchor = (
        "                case gbi::OP_TRI1:\n"
        "                    draw_triangle_word(st, ctx.geom, c.w0);\n"
        "                    break;\n"
    )
    block = (
        "                case gbi::OP_MODIFYVTX: {\n"
        "                    const uint8_t where = static_cast<uint8_t>((c.w0 >> 16) & 0xFFu);\n"
        "                    const int index = static_cast<int>((c.w0 & 0xFFFFu) >> 1);\n"
        "                    if (dx9geom::modify_vertex(ctx.geom, index, where, c.w1))\n"
        "                        ++modifyvtx_count_;\n"
        "                    else\n"
        "                        ++unsupported_modifyvtx_count_;\n"
        "                    break;\n"
        "                }\n"
    )
    s = replace1(s, anchor, block + anchor, "Stage6 TRI1")
if "unsigned modifyvtx_count_" not in s:
    s = replace1(
        s,
        "    unsigned skipped_triangle_count_ = 0;\n",
        "    unsigned skipped_triangle_count_ = 0;\n"
        "    unsigned modifyvtx_count_ = 0;\n"
        "    unsigned unsupported_modifyvtx_count_ = 0;\n",
        "Stage6 counters",
    )

# Reject triangles the N64 RSP would never rasterize. This runs after the three
# vertices are transformed but before texture upload/RT binding, so it saves the
# most expensive work on old GPUs without changing RDP colour/blender semantics.
if "triangle_trivially_rejected(tv[0]" not in s:
    old = (
        "        if (!tv[0].valid || !tv[1].valid || !tv[2].valid) {\n"
        "            ++skipped_triangle_count_; return;\n"
        "        }\n\n"
        "        const int tile0 = st.tex.active_tile & 7, tile1 = (tile0 + 1) & 7;\n"
    )
    new = (
        "        if (!tv[0].valid || !tv[1].valid || !tv[2].valid) {\n"
        "            ++skipped_triangle_count_; return;\n"
        "        }\n"
        "        if (dx9geom::triangle_trivially_rejected(tv[0], tv[1], tv[2])) {\n"
        "            ++clip_rejected_triangle_count_;\n"
        "            ++skipped_triangle_count_;\n"
        "            return;\n"
        "        }\n"
        "        if (dx9geom::triangle_culled(geom, tv[0], tv[1], tv[2])) {\n"
        "            ++culled_triangle_count_;\n"
        "            ++skipped_triangle_count_;\n"
        "            return;\n"
        "        }\n\n"
        "        const int tile0 = st.tex.active_tile & 7, tile1 = (tile0 + 1) & 7;\n"
    )
    s = replace1(s, old, new, "Stage6 pre-raster culling")

if "unsigned culled_triangle_count_" not in s:
    s = replace1(
        s,
        "    unsigned skipped_triangle_count_ = 0;\n",
        "    unsigned skipped_triangle_count_ = 0;\n"
        "    unsigned culled_triangle_count_ = 0;\n"
        "    unsigned clip_rejected_triangle_count_ = 0;\n",
        "Stage6 cull counters",
    )

# Keep diagnostics useful without turning them into a testing burden.
if "culled=%u clipReject=%u" not in s:
    s = replace1(
        s,
        '                           "stage6 dl=%u fills=%u copyRects=%u shaderRects=%u tris=%u skippedTris=%u s2d=%u skippedS2d=%u zimg=0x%06X zAttach=%u zClear=%u zFallback=%u texUploads=%u",\n'
        "                           frame, fill_count_, copy_texrect_count_, shader_texrect_count_,\n"
        "                           triangle_count_, skipped_triangle_count_, s2dex_rect_count_,\n"
        "                           skipped_s2dex_rect_count_, last_zimg_address_, depth_attach_count_,\n"
        "                           depth_clear_count_, depth_fallback_count_, texture_upload_count_);\n",
        '                           "stage6 dl=%u fills=%u copyRects=%u shaderRects=%u tris=%u skippedTris=%u culled=%u clipReject=%u s2d=%u skippedS2d=%u zimg=0x%06X zAttach=%u zClear=%u zFallback=%u texUploads=%u",\n'
        "                           frame, fill_count_, copy_texrect_count_, shader_texrect_count_,\n"
        "                           triangle_count_, skipped_triangle_count_, culled_triangle_count_,\n"
        "                           clip_rejected_triangle_count_, s2dex_rect_count_,\n"
        "                           skipped_s2dex_rect_count_, last_zimg_address_, depth_attach_count_,\n"
        "                           depth_clear_count_, depth_fallback_count_, texture_upload_count_);\n",
        "Stage6 periodic telemetry",
    )

p.write_text(s, encoding="utf-8")

cm = Path("app/CMakeLists.txt").read_text(encoding="utf-8")
sg = Path("app/src/dx9_renderer_stage6.inl").read_text(encoding="utf-8")
gh = Path("app/src/dx9_geometry.hpp").read_text(encoding="utf-8")
assert "option(OGRE_USE_DX9" in cm
assert "set(OGRE_RENDERER_SOURCES src/dx9_renderer.cpp)" in cm
assert "target_link_libraries(ogrebattle64 PRIVATE d3d9)" in cm
assert "case gbi::OP_MODIFYVTX:" in sg
assert "inline bool modify_vertex(" in gh
assert "triangle_trivially_rejected(tv[0]" in sg
assert "triangle_culled(geom, tv[0]" in sg
assert "kCullFront = 0x00001000u" in gh
