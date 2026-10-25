// Ogre Battle 64 low-end D3D9 RDP pixel shader.
// Target: ps_3_0. One shader covers COPY, 1-cycle and 2-cycle combiner modes.
// The CPU supplies decoded selector integers exactly as web_renderer.cpp does.
// No runtime shader variants are required.

sampler2D Tex0 : register(s0);
sampler2D Tex1 : register(s1);

float4 PrimColor  : register(c0);
float4 EnvColor   : register(c1);
float4 FogColor   : register(c2);
float4 BlendColor : register(c3);
// x=K4, y=K5, z=cycle (0 COPY, 1 one-cycle, 2 two-cycle),
// w=combiner blender cycle count.
float4 Misc       : register(c4);

// Color/alpha selector sets for the two evaluated combiner slots.
int4 ColorSel0 : register(i0); // ca cb cc cd
int4 AlphaSel0 : register(i1); // aa ab ac ad
int4 ColorSel1 : register(i2);
int4 AlphaSel1 : register(i3);
// Blender selectors P M A B.
int4 BlendSel0 : register(i4);
int4 BlendSel1 : register(i5);
// x=forceBlend, y=blendApprox, z=debugMode, w=unused.
int4 Modes     : register(i6);

struct PSInput {
    float2 uv0   : TEXCOORD0;
    float2 uv1   : TEXCOORD1;
    float4 shade : COLOR0;
};

float4 choose_texel(int selector, bool secondCycle, float4 t0, float4 t1) {
    // TEXEL0/TEXEL1 swap in the second RDP cycle.
    bool wants1 = (selector == 2);
    bool use1 = wants1 != secondCycle;
    return use1 ? t1 : t0;
}

float4 color_input(int sel, bool secondCycle, float4 combined,
                   float4 shade, float4 t0, float4 t1) {
    if (sel == 0)  return combined;                                  // COMBINED
    if (sel == 1 || sel == 2) return choose_texel(sel, secondCycle, t0, t1);
    if (sel == 3)  return PrimColor;
    if (sel == 4)  return shade;
    if (sel == 5)  return EnvColor;
    if (sel == 6 || sel == 7) return 0.0.xxxx;                        // key inputs
    if (sel == 8)  return combined.aaaa;
    if (sel == 9)  return choose_texel(1, secondCycle, t0, t1).aaaa;
    if (sel == 10) return choose_texel(2, secondCycle, t0, t1).aaaa;
    if (sel == 11) return PrimColor.aaaa;
    if (sel == 12) return shade.aaaa;
    if (sel == 13) return EnvColor.aaaa;
    if (sel == 14 || sel == 15 || sel == 16) return 0.0.xxxx;        // LOD/noise
    if (sel == 17) return Misc.xxxx;                                  // K4
    if (sel == 18) return Misc.yyyy;                                  // K5
    if (sel == 19) return 1.0.xxxx;                                   // ONE
    return 0.0.xxxx;
}

float alpha_input(int sel, bool secondCycle, float combined,
                  float4 shade, float4 t0, float4 t1) {
    if (sel == 0) return combined;
    if (sel == 1) return choose_texel(1, secondCycle, t0, t1).a;
    if (sel == 2) return choose_texel(2, secondCycle, t0, t1).a;
    if (sel == 3) return PrimColor.a;
    if (sel == 4) return shade.a;
    if (sel == 5) return EnvColor.a;
    if (sel == 8) return 1.0;
    return 0.0;
}

void wrap_input(inout float v, float lo, float hi) {
    float range = hi - lo;
    if (lo >= v) v += range;
    if (v >= hi) v -= range;
}
void wrap_c(inout float v)   { wrap_input(v, -1.0 - 1.0/255.0, 1.0 + 1.0/255.0); }
void wrap_abd(inout float v) { wrap_input(v, -0.5 - 1.0/255.0, 1.5 + 1.0/255.0); }
void wrap_clamp(inout float v) { wrap_abd(v); v = saturate(v); }

float3 blend_pm(int pm, float3 cc) {
    if (pm == 0) return cc;              // combiner / previous blender
    if (pm == 2) return BlendColor.rgb;
    if (pm == 3) return FogColor.rgb;
    return 1.0.xxx;                      // framebuffer colour represented by HW blend
}
float blend_a(int a, float ca, float shadeA) {
    if (a == 0) return ca;
    if (a == 1) return FogColor.a;
    if (a == 2) return shadeA;
    return 0.0;
}
float blend_b(int b, float aMul) {
    if (b == 0) return 1.0 - aMul;
    if (b == 3) return 0.0;
    return 1.0;
}

void blender_cycle(bool forceBlend, bool lastCycle, bool notFirst,
                   float3 combinerRGB, float combinerA, float shadeA,
                   int4 s, inout bool passthroughEnabled,
                   inout int passthroughInput,
                   inout float3 blenderColor, inout float finalAlpha) {
    int P = s.x, M = s.y, A = s.z, B = s.w;
    bool replaceCC = notFirst && !passthroughEnabled;
    if (lastCycle && !forceBlend) {
        if (P == 1) finalAlpha = 0.0;
        else {
            float3 inputColor = replaceCC ? blenderColor : combinerRGB;
            blenderColor = blend_pm(P, inputColor);
            finalAlpha = 1.0;
        }
        return;
    }

    bool anyZero = (A == 3) || (B == 3);
    bool duplicate1ma = (P == M) && (B == 0);
    bool passthrough = anyZero || duplicate1ma;
    bool framebufferColor = (P == 1) || (M == 1);
    if (passthroughEnabled) {
        if (P == 0) { P = passthroughInput; framebufferColor = framebufferColor || P == 1; }
        else if (M == 0) { M = passthroughInput; framebufferColor = framebufferColor || M == 1; }
    }

    if (passthrough) {
        if (!lastCycle) {
            passthroughInput = (A == 3) ? M : P;
            passthroughEnabled = true;
        } else if (framebufferColor) {
            finalAlpha = 0.0;
        } else {
            float3 inputColor = replaceCC ? blenderColor : combinerRGB;
            blenderColor = blend_pm((A == 3) ? M : P, inputColor);
            finalAlpha = 1.0;
        }
    } else if (framebufferColor) {
        float3 inputColor = replaceCC ? blenderColor : combinerRGB;
        if (P == 1) {
            blenderColor = blend_pm(M, inputColor);
            finalAlpha = 1.0 - blend_a(A, combinerA, shadeA);
        } else if (M == 1) {
            blenderColor = blend_pm(P, inputColor);
            finalAlpha = blend_a(A, combinerA, shadeA);
        }
    } else {
        float3 inputColor = replaceCC ? blenderColor : combinerRGB;
        float am = blend_a(A, combinerA, shadeA);
        float bm = blend_b(B, am);
        float3 numerator = blend_pm(P, inputColor) * am + blend_pm(M, inputColor) * bm;
        const float overflow = 1.0 + 8.0/255.0;
        if (P != M) numerator = fmod(numerator, overflow.xxx);
        blenderColor = numerator / max(am + bm, 1.0/255.0);
        finalAlpha = 1.0;
    }
}

float4 run_blender(float4 cc, float shadeA) {
    const int approx = Modes.y;
    if (approx == 1) return float4(cc.rgb, cc.a * cc.a);
    if (approx == 2) return float4(blend_pm(BlendSel0.x, cc.rgb),
                                   blend_a(BlendSel0.z, cc.a, shadeA) *
                                   blend_a(BlendSel1.z, cc.a, shadeA));
    const int cycles = (int)(Misc.w + 0.5);
    if (cycles == 0) return float4(cc.rgb, 1.0);

    float3 bc = 0.0.xxx;
    float fa = 0.0;
    bool pass = false;
    int passInput = 0;
    blender_cycle(Modes.x != 0, cycles == 1, false, cc.rgb, cc.a, shadeA,
                  BlendSel0, pass, passInput, bc, fa);
    if (cycles > 1) {
        blender_cycle(Modes.x != 0, true, true, cc.rgb, cc.a, shadeA,
                      BlendSel1, pass, passInput, bc, fa);
    }
    return float4(bc, fa);
}

float4 main(PSInput input) : COLOR0 {
    // Sample both texture units once; selector logic chooses between values.
    float4 t0 = tex2D(Tex0, input.uv0);
    float4 t1 = tex2D(Tex1, input.uv1);
    if (Modes.z == 1) return float4(t1.rgb, 1.0);
    if (Modes.z == 2) return float4(t0.rgb, 1.0);

    const int cycle = (int)(Misc.z + 0.5);
    if (cycle == 0) return t0; // COPY

    float4 c = 0.0.xxxx;
    c.rgb = (color_input(ColorSel0.x, false, c, input.shade, t0, t1).rgb -
             color_input(ColorSel0.y, false, c, input.shade, t0, t1).rgb) *
             color_input(ColorSel0.z, false, c, input.shade, t0, t1).rgb +
             color_input(ColorSel0.w, false, c, input.shade, t0, t1).rgb;
    c.a = (alpha_input(AlphaSel0.x, false, c.a, input.shade, t0, t1) -
           alpha_input(AlphaSel0.y, false, c.a, input.shade, t0, t1)) *
           alpha_input(AlphaSel0.z, false, c.a, input.shade, t0, t1) +
           alpha_input(AlphaSel0.w, false, c.a, input.shade, t0, t1);

    if (cycle == 2) {
        if (ColorSel1.z == 0) { wrap_c(c.r); wrap_c(c.g); wrap_c(c.b); }
        else { wrap_abd(c.r); wrap_abd(c.g); wrap_abd(c.b); }
        if (AlphaSel1.z == 0) wrap_c(c.a); else wrap_abd(c.a);
        c.rgb = (color_input(ColorSel1.x, true, c, input.shade, t0, t1).rgb -
                 color_input(ColorSel1.y, true, c, input.shade, t0, t1).rgb) *
                 color_input(ColorSel1.z, true, c, input.shade, t0, t1).rgb +
                 color_input(ColorSel1.w, true, c, input.shade, t0, t1).rgb;
        c.a = (alpha_input(AlphaSel1.x, true, c.a, input.shade, t0, t1) -
               alpha_input(AlphaSel1.y, true, c.a, input.shade, t0, t1)) *
               alpha_input(AlphaSel1.z, true, c.a, input.shade, t0, t1) +
               alpha_input(AlphaSel1.w, true, c.a, input.shade, t0, t1);
    }

    wrap_clamp(c.r); wrap_clamp(c.g); wrap_clamp(c.b); wrap_clamp(c.a);
    return run_blender(c, input.shade.a);
}
