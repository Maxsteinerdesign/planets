# Planets Addon — Session Progress Notes

> Update this file at the END of every working session, and COMMIT it along with the code.
> This is the persistent context that survives session compaction and new conversations.

---

## ⭐ MILESTONE — v0.5.93 (2026-05-12)

**Sun retention ring geometry confirmed correct.** Visual verification in Blender by Max:
"It finally looks like it did before, when we just needed to make some small adjustments."

This commit is the known-good baseline. If future changes break retention, revert to the
`v0.5.93-milestone` tag.

---

## Current State (v0.5.93)

**What works:**
- All gear generation, ring, planet, sun
- Ring lip retention (Boolean UNION on cone_obj): ring inner lip hooks over planet outer chamfer
- Ring trim (Boolean DIFFERENCE): cleans up cone mouth at phi slope
- Planet chamfer cutter (per-planet DIFFERENCE): creates bevel on planet outer face for ring lip
- `m_ext_sun_teeth` cap: prevents sun extension teeth from penetrating planet chamfer
- Sun retention ring (Boolean UNION on sun_obj): triangle A-B-C revolved around sun Z, hooks
  over planet chamfer from inside

**Sun retention ring approach (v0.5.93):**
- Triangle A-B-C revolved around sun's Z-axis (`_make_revolution_solid`), UNION into sun gear
- `A = (ra_sun_ext, z_planet_max)` — sun tip circle, top of sun extension
- `B = (rf_sun_ext, z_planet_max)` — sun root circle, same height (Line 1: A→B horizontal)
- Line 2: from B downward, parallel to sun bevel cone surface (slope_r2 > 0)
- Line 3: from A downward AND INWARD, parallel to planet chamfer (SUN-FACING side)
- C = intersection of Line 2 and Line 3

**The slope_line3 fix (root cause of all earlier dome/no-overhang attempts):**
- Chamfer cutter is revolved around planet's LOCAL Z axis → cross-section has TWO mirror
  copies of the cutter: one at `+local_r` (ring-facing side) and one at `−local_r` (sun-facing)
- Sun retention engages the SUN-FACING mirror — opposite sign of `delta_lr`
- v0.5.92 formula tracked the RING-facing slope (negative) → dome
- v0.5.93 formula flips sign of `delta_lr`:
  ```
  slope_line3 = (-delta_lr * cos_phi + delta_lz * sin_phi) /
                 (delta_lz * cos_phi + delta_lr * sin_phi)
  ```
- For default props (phi ≈ 12.4°): slope_line3 = +1.346 (was −0.544 in v0.5.92) ✓

**m_ext_sun_teeth cap (in v0.5.93):**
- Without cap, default `ra_sun_ext = 17.25` > `r_chamfer_at_max = 17.02` (sun tip pokes
  past chamfer)
- Cap: `m_ext_sun_teeth = min(m_ext_sun, (r_chamfer_at_max − tolerance) / (T_sun/2 + 1))`
- Applied only when `retention` is True

**Key variables:**
- `l3_dr = A_lip[0] - C_lip[0]` (< 0 for typical geometry: ring lip Line 3 goes inward as z increases)
- `l3_dz = A_lip[1] - C_lip[1]` (> 0 always: A_lip above C_lip)
- `r_chamfer_at_max`: world-r of planet's SUN-FACING chamfer boundary at z_planet_max
- `z_planet_max`: world-z of the sun-facing chamfer top corner
- `delta_lr = r_A_ext - local_C_tol[0]` (< 0 in planet local r)
- `delta_lz = lz_top - local_C_tol[1]` (> 0 in planet local z)

---

## Diagnostic Tool — cross_section.py

`cross_section.py` recomputes all geometry from the addon's default property values and
renders a 2D world r-z cross-section (`cross_section.png`). Shows:
- Sun outline, planet outline (tilted at phi)
- Both ring-facing and sun-facing chamfer cutter mirrors
- Chamfer FACE on both sides with measured slope
- Sun retention triangle A-B-C with BOTH the v0.5.92 buggy slope and the v0.5.93 correct slope

Use this whenever you change the slope_line3 formula — confirms direction before touching the
addon and reloading Blender.

---

## Session History

| Version | What changed | Outcome |
|---------|-------------|---------|
| v0.5.33 | Last git commit before long session | — |
| v0.5.52 | (session work) | — |
| v0.5.60 | Sun lip with _connect_profiles + tooth profiles (slope_r < 0) | No visible overhang |
| v0.5.70 | WRONG: replaced with revolution-solid cone | Regression |
| v0.5.75 | Attempt to fix, incomplete | Worse |
| v0.5.76 | More changes | — |
| v0.5.77 | Added m_ext_sun_teeth cap + new r_chamfer_at_max/z_planet_max | Large intersections |
| v0.5.78–82 | Multiple failed sun lip geometry attempts | — |
| v0.5.82 | Correct geometry but revolution solid | Shape OK, gap fill bad |
| v0.5.83 | Restored v0.5.60 code (slope_r < 0) | Still no overhang |
| v0.5.84 | v0.5.82 geometry + tooth profiles (_connect_profiles) | Untested at the time |
| v0.5.91 | Triangle A-B-C revival, slope = tan_phi | Wrong angle |
| v0.5.92 | Triangle A-B-C, slope from local→world transform | DOME (used ring-side slope) |
| **v0.5.93** | **Flip sign of delta_lr → sun-side slope; add m_ext_sun_teeth cap** | **✓ CORRECT (milestone)** |

---

## Things That Must NOT Be Changed

- `_shared_edge_pitch_radii` approach
- Planet chamfer cutter approach (transform world→local, chamfer_local profile)
- Ring lip triangle (A_lip, B_lip, C_lip) geometry
- m_ext_sun_teeth cap formula (`min(m_ext_sun, (r_chamfer_at_max - tolerance) / (T_sun/2 + 1))`)
- **slope_line3 must use SUN-FACING chamfer direction (negated delta_lr)**
- Triangle A-B-C revolved around sun Z via `_make_revolution_solid`
- `r_chamfer_at_max = orbit_r_planet - r_boundary * cos_phi + local_tip_z * sin_phi`
  (the minus sign is correct — it's the −local_r mirror, sun-facing side)

---

## Next Steps

1. Visual confirmation in Blender ✓ (Max: "looks like it did before")
2. Small adjustments expected — slope_line3 formula and cap are correct, but parameters
   (tolerance, sun module headroom) may benefit from tuning
3. Keep `cross_section.py` updated if any retention math changes

---

## How to Not Lose Progress

**Before ending a session:**
1. `git commit` in `G:\My Drive\Claude\planets\` with a descriptive message
2. Update this PROGRESS.md with current state
3. Note any open issues and what was tried

**At the start of a new session:**
1. Read this PROGRESS.md first
2. Check `git log --oneline` to confirm version
3. Do NOT make structural changes without re-reading this file

**To recover the v0.5.93 milestone if something breaks:**
```
git checkout v0.5.93-milestone -- __init__.py
```
