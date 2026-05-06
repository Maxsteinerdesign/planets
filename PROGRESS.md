# Planets Addon — Session Progress Notes

> Update this file at the END of every working session, and COMMIT it along with the code.
> This is the persistent context that survives session compaction and new conversations.

---

## Current State (v0.5.83)

**What works:**
- All gear generation, ring, planet, sun
- Ring lip retention (Boolean UNION on cone_obj): ring inner lip hooks over planet outer chamfer
- Ring trim (Boolean DIFFERENCE): cleans up cone mouth at phi slope
- Planet chamfer cutter (per-planet DIFFERENCE): creates bevel on planet outer face for ring lip
- m_ext_sun_teeth cap: prevents sun extension teeth from penetrating planet chamfer
- Sun lip retention (Boolean UNION on sun_obj): hooks over planet chamfer from inside

**Sun lip approach (v0.5.83 = restored from v0.5.60):**
- Uses `_connect_profiles` with TWO TOOTH PROFILES, not `_make_revolution_solid`
- This is critical: a revolution solid fills sun tooth gaps → intersections with planet teeth
- Profile A at z_planet_max: module = ra_sun_top / (T_sun/2+1), clamped ≤ r_chamfer_at_max
- Profile C above z_planet_max: module = ra_C_sun / (T_sun/2+1), follows chamfer slope
- Slope direction (slope_r, slope_z) is derived from the planet chamfer cutter geometry

**Key variables computed before sun lip block:**
- `r_chamfer_at_max`: world r of planet inner chamfer boundary at z_planet_max
- `z_planet_max`: highest world z on planet's sun-facing chamfer
- `m_ext_sun`: sun module at z_planet_max (cone-scaled)
- `r_A_ext`, `local_C_tol`, `lz_top`: from planet chamfer cutter precomputation
- `cos_phi`, `sin_phi`: from line ~579

---

## What Was "Just About Right" (v0.5.60)

v0.5.60 had the sun lip working with SLIGHT overlaps remaining. The sun lip code used
`_connect_profiles` with tooth profiles — same as v0.5.83. The slight overlaps at v0.5.60
were in 3 areas:
1. Ring-planet tooth interference (small number of faces — ring groove clearance issue)
2. Sun-planet tooth interference (sun extension teeth penetrating planet body)
3. Sun lip slight overlap (lip slightly too large)

**What BROKE it:** v0.5.70 replaced the correct `_connect_profiles` approach with a simple
revolution-solid cone, then v0.5.77+ tried to fix this with new geometry that kept getting worse.

**m_ext_sun_teeth cap** (added in v0.5.77, kept in v0.5.83):
Caps sun extension tooth addendum so (T_sun/2+1)*m_ext_sun_teeth ≤ r_chamfer_at_max - tolerance.
This was a genuine fix for sun-planet tooth interference. Keep this.

---

## Session History

| Version | What changed | Outcome |
|---------|-------------|---------|
| v0.5.33 | Last git commit before long session | — |
| v0.5.52 | (session work) | — |
| v0.5.60 | Sun lip with _connect_profiles + tooth profiles | Nearly correct, slight overlap |
| v0.5.70 | WRONG: replaced with revolution-solid cone | Regression |
| v0.5.75 | Attempt to fix, incomplete | Worse |
| v0.5.76 | More changes | — |
| v0.5.77 | Added m_ext_sun_teeth cap + new r_chamfer_at_max/z_planet_max | Large intersections (953/617/170 faces) |
| v0.5.78–82 | Multiple failed sun lip geometry attempts | — |
| v0.5.83 | Restored v0.5.60 sun lip code, kept m_ext_sun_teeth cap | Back to near-correct |

---

## Things That Must NOT Be Changed

- `_shared_edge_pitch_radii` approach
- Planet chamfer cutter approach (transform world→local, chamfer_local profile)
- Ring lip triangle (A_lip, B_lip, C_lip) geometry
- m_ext_sun_teeth cap formula
- `_connect_profiles` for sun lip (NOT _make_revolution_solid)

---

## Next Steps

1. Test v0.5.83 in Blender — check intersection face counts
2. If small overlaps remain from ring-planet tooth interference: adjust ring groove clearance
3. If sun lip slight overlap remains: adjust the `tolerance` multiplier in lip clamping
4. DO NOT change the sun lip approach — only adjust clamping parameters

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
