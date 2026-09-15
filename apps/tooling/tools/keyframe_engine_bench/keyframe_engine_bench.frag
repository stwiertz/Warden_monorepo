// Tool 12 mega-shader (Story 12.1, AC4/AC6/AC7).
//
// ONE draw per keyframe. Fragment i evaluates rule i and writes one 0/1.
// NO combination logic here -- scoring and phase resolution are CPU-side (AC4),
// and `weight` / `weight_override` never reach the GPU.
//
// ===========================================================================
// AC6 -- ES-3.0-COMPATIBLE SUBSET FROM LINE ONE. This body is authored ONCE;
// only the `#version` line is swapped (see shader.py::build_source), and both
// dialects are gated on glslangValidator. Binding rules observed here, each of
// which silently passes on desktop and fails on Adreno:
//   * no implicit int->float ANYWHERE (`float x = 1;` compiles on 330 core and
//     ERRORS on 300 es -- the #1 silent killer). Every literal is explicit.
//   * `precision highp float/int/sampler2D` are mandatory: the ES fragment
//     language has NO default float precision, and sampler2D defaults to LOWP
//     -- which would shred both the RGBA32F rule bounds and the 8-bit frame.
//   * `out vec4`, never gl_FragColor. `texture()`/`texelFetch()`, never
//     texture2D(). No `layout(location=)` on uniforms (banned in both).
//   * integer `%` and `/` are UNDEFINED for negative operands in ES 3.00, so
//     hue wrap uses float `mod()` (floored, like Python's `%`).
// Desktop drivers run a permissive front-end -- `#version 300 es` compiling
// locally proves NOTHING about Adreno, and ModernGL cannot create a real GLES
// context (moderngl#507). The validator is the gate, not the driver.
// ===========================================================================

precision highp float;
precision highp int;
precision highp sampler2D;

// The keyframe. Channel order is EXACTLY as uploaded by shader.py: OpenCV's
// native BGR memory order, so .r == blue, .g == green, .b == red. This is not
// a swizzle to undo -- hsv_cv() takes (b, g, r) positionally, mirroring
// OpenCV's own `int b = src[bidx], g = src[1], r = src[bidx^2]` for bidx=0.
uniform sampler2D uFrame;
// Rules LUT, 150x3 RGBA32F. Texturing a 32F format is fine in ES 3.0 core;
// only *rendering* to one is not.
uniform sampler2D uRules;

out vec4 fragColor;

// Loop cap. ES 3.00 needs a constant bound, and an unbounded loop over a
// malformed rect would hang the GPU. Shipped rects are 1-25 px (mode 2x2), so
// this is ~164x headroom.
//
// MUST match MAX_RECT_TEXELS in lut.py. Above the cap the loop truncates while
// `ratio` below still divides by the FULL area, so an oversized rect would
// silently under-fire (capped at MAX_RECT_TEXELS/area) instead of failing --
// a parity break that presents as a wrong number, not an error. `pack_rules`
// rejects any rect above the cap CPU-side, which is what makes the truncation
// unreachable rather than merely unlikely. Raise both together or neither.
const int MAX_RECT_TEXELS = 4096;

const int MODE_WRAP = 1;
const int MODE_FULL_CIRCLE = 2;

// OpenCV's RGB2HSV_b, ported EXACTLY (integer arithmetic, hsv_shift = 12).
//
// This is a deliberate deviation from the story's Dev Notes, which suggest Sam
// Hocevar's branchless float rgb2hsv. A float conversion cannot guarantee
// parity: cv2's H/S/V are INTEGERS produced by fixed-point math with rounding,
// and the CPU reference tests `cv2.inRange` against integer bounds inclusively,
// so a float hue landing at 19.9997 instead of 20 flips a tight rule. This
// integer port was brute-forced against cv2.cvtColor(BGR2HSV) over all 2^24 RGB
// inputs: 0 mismatches on H, S and V. (That sweep also confirms max H == 179 --
// 180 is an unattainable wrapping endpoint, which is why the /180 mapping is
// correct and /179 would impose a 1.005x hue stretch.)
//
// Fits comfortably in 32-bit: max |diff * sdiv| = 255 * 1044480 = 2.66e8 and
// max |h * hdiv| = 1275 * 122880 = 1.57e8, both well inside int32.
ivec3 hsv_cv(int b, int g, int r) {
    int v = max(max(b, g), r);
    int vmin = min(min(b, g), r);
    int diff = v - vmin;

    int vr = (v == r) ? -1 : 0;
    int vg = (v == g) ? -1 : 0;

    // OpenCV precomputes these as tables via a FLOAT divide + round:
    //   sdiv_table[i]     = round((255 << 12) / i)
    //   hdiv_table180[i]  = round((180 << 12) / (6 * i))
    // Recomputed per-texel here. Neither expression can land on an exact .5 tie
    // for i in [1,255] (a tie needs i divisible by 2^13 / 2^14 respectively), so
    // round-half-to-even vs round-half-away is unobservable and floor(x + 0.5)
    // is exact -- the float error is ~1/32 while the nearest tie is >= 1/510 away.
    int sdiv = (v > 0) ? int(floor(float(255 * 4096) / float(v) + 0.5)) : 0;
    int hdiv = (diff > 0)
        ? int(floor(float(180 * 4096) / (6.0 * float(diff)) + 0.5))
        : 0;

    int s = (diff * sdiv + 2048) >> 12;

    int h = (vr & (g - b))
          + ((~vr) & ((vg & (b - r + 2 * diff)) + ((~vg) & (r - g + 4 * diff))));
    // ES 3.00 sign-extends on >> for signed ints, matching C++'s arithmetic shift.
    h = (h * hdiv + 2048) >> 12;
    h = h + ((h < 0) ? 180 : 0);

    return ivec3(h, s, v);
}

void main() {
    int i = int(gl_FragCoord.x);

    vec4 t0 = texelFetch(uRules, ivec2(i, 0), 0);
    vec4 t1 = texelFetch(uRules, ivec2(i, 1), 0);
    vec4 t2 = texelFetch(uRules, ivec2(i, 2), 0);

    int rx = int(t0.x);
    int ry = int(t0.y);
    int rw = int(t0.z);
    int rh = int(t0.w);

    int h_lo = int(t1.x);
    int h_hi = int(t1.y);
    int s_lo = int(t1.z);
    int s_hi = int(t1.w);

    int v_lo = int(t2.x);
    int v_hi = int(t2.y);
    float min_ratio = t2.z;
    int mode = int(t2.w);

    // Rects are pre-clamped CPU-side, so area is already the CORRECT denominator
    // -- it matches band_inrange_ratio's clamped mask.size, not the declared w*h.
    int area = rw * rh;

    // Hue sub-interval bounds for the wrap branch: [wlo, 179] u [0, whi].
    // Float mod() is floored (mod(-6.0, 180.0) == 174.0), matching Python's `%`,
    // so this reconstructs cv2's `h_lo % 180` / `h_hi % 180` exactly. Integer
    // `%` is undefined for negative operands in ES 3.00 and must not be used.
    int wlo = int(mod(float(h_lo), 180.0));
    int whi = int(mod(float(h_hi), 180.0));

    int count = 0;
    int n = min(area, MAX_RECT_TEXELS);
    for (int k = 0; k < MAX_RECT_TEXELS; ++k) {
        if (k >= n) {
            break;
        }
        // rw > 0 whenever area > 0, so these stay positive-operand divisions.
        int dy = k / rw;
        int dx = k - dy * rw;

        vec3 texel = texelFetch(uFrame, ivec2(rx + dx, ry + dy), 0).rgb;
        // Exact uint8 recovery from an 8-bit normalized texture: v/255.0 is
        // representable and round-trips under round().
        // px.x/y/z are BGR-ordered (see uFrame above) -- NOT r/g/b. Indexed
        // positionally rather than via .rgb swizzles so the channel meaning
        // cannot be misread at the call site.
        ivec3 px = ivec3(floor(texel * 255.0 + 0.5));
        ivec3 hsv = hsv_cv(px.x, px.y, px.z);

        bool hue_ok;
        if (mode == MODE_FULL_CIRCLE) {
            // Tolerance covers the whole circle -- hue is not tested; s/v still
            // constrain. (68 of the 134 shipped rules take this branch.)
            hue_ok = true;
        } else if (mode == MODE_WRAP) {
            hue_ok = (hsv.x >= wlo) || (hsv.x <= whi);
        } else {
            hue_ok = (hsv.x >= h_lo) && (hsv.x <= h_hi);
        }

        // cv2.inRange is INCLUSIVE on both bounds.
        bool in_band = hue_ok
            && (hsv.y >= s_lo) && (hsv.y <= s_hi)
            && (hsv.z >= v_lo) && (hsv.z <= v_hi);

        if (in_band) {
            count = count + 1;
        }
    }

    float ratio = (area > 0) ? (float(count) / float(area)) : 0.0;
    // step(edge, x) == (x >= edge) -- matching zone_fires_on_frame's
    // `ratio >= min_ratio` (>=, not >). A 0-area rect yields ratio 0.0 and is
    // fed through the same test rather than special-cased, so it agrees with
    // band_inrange_ratio's `region.size == 0 -> 0.0` on every min_ratio.
    float fired = step(min_ratio, ratio);
    fragColor = vec4(fired, fired, fired, 1.0);
}
