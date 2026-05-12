"""
Cross-section diagram of the Planets addon retention geometry.

Recomputes every value with the SAME formulas as variable_gears/planets __init__.py
using the addon's DEFAULT property values, then draws a 2D world r-z view to
verify the sun retention triangle geometry.

Output: G:/My Drive/Claude/planets/cross_section.png
"""
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D

# ─── Default addon property values ────────────────────────────────────────
cone_diameter = 100.0
cone_height   = 100.0
gw            = 20.0
wall          = 3.0
T_sun         = 12
T_planet      = 12
T_ring        = T_sun + 2 * T_planet
clearance     = 0.05
tolerance     = 0.15
ext           = 0.0

# ─── Mirror the addon's generate() math ───────────────────────────────────
cone_r = cone_diameter / 2.0
cone_h = cone_height
z_bot  = -gw
z_disk = -gw / 2.0
full_h = cone_h * 4.0 / 3.0
s_bot  = (full_h - gw) / full_h
m      = max(0.001, (cone_r       - wall) / (T_ring / 2.0 + 1.25))
m_bot  = max(0.001, (cone_r*s_bot - wall) / (T_ring / 2.0 + 1.25))
dm     = m * (1.0 - s_bot)

r_sun    = T_sun    * m / 2.0
r_planet = T_planet * m / 2.0
orbit_r  = r_sun + r_planet
s_disk         = (full_h + z_disk) / full_h
orbit_r_planet = orbit_r * s_disk
phi  = math.atan2(orbit_r, full_h)
beta = math.atan2(cone_r, full_h)
sin_phi = math.sin(phi); cos_phi = math.cos(phi); tan_phi = math.tan(phi)

_gs_num = (cone_r * (full_h + z_disk + (gw / 2.0) * math.cos(phi)) / full_h
           - wall - (gw / 2.0) * math.sin(phi))
_gs_den = (orbit_r * s_disk
           + (T_planet / 2.0 + 1.0) * m
             * (math.cos(phi) + cone_r * math.sin(phi) / full_h))
gear_scale = min(1.0, _gs_num / _gs_den)

orbit_r        = orbit_r        * gear_scale
orbit_r_planet = orbit_r_planet * gear_scale

hub_r    = (T_sun / 2.0 + 1.0) * m
z_bot_pl = z_disk - (gw / 2.0) * math.cos(phi)
r_bot_pl = orbit_r_planet - (gw / 2.0) * math.sin(phi)
hub_top  = max(z_bot, z_bot_pl + (r_bot_pl - hub_r) * math.tan(phi))

z_disk_sun = hub_top + gw / 2.0
sun_raise  = (z_disk_sun - z_disk) / gw
m_top_sun  = max(0.001, gear_scale * (m + dm * sun_raise))
_sun_bevel = max(0.0, 2.0 * phi - beta)
m_bot_sun  = max(0.001, m_top_sun - gw * 2.0 * math.tan(_sun_bevel) / T_sun)

m_top_planet = gear_scale * m
m_bot_planet = max(0.001, m_top_planet - gw * 2.0 * math.tan(beta - phi) / T_planet)

ext_local_pl = 0.0
m_ext_planet = m_top_planet
ra_ext_planet = (T_planet / 2.0 + 1.0) * m_ext_planet
rf_ext_planet = (T_planet / 2.0 - 1.25) * m_ext_planet

# Retention geometry
ext_local_top = gw / 2.0 + ext / math.cos(phi)
center_r_ext  = orbit_r_planet + ext_local_top * math.sin(phi)
center_z_ext  = z_disk + ext_local_top * math.cos(phi)
ra0   = (T_ring / 2.0 - 0.75) * m
k_lip = ra0 * tan_phi / full_h
z_A   = (center_z_ext + center_r_ext * tan_phi - k_lip * full_h) / (1.0 + k_lip)
ra_r  = ra0 * (full_h + z_A) / full_h
m_at_zA = m * (full_h + z_A) / full_h
rf_r    = (T_ring / 2.0 + 1.25) * m_at_zA

dr_1  = (rf_r - ra_r) + tolerance
d_1   = dr_1 / math.cos(phi)
A_lip = (ra_r,                      z_A)
B_lip = (ra_r + d_1*math.cos(phi),  z_A - d_1*math.sin(phi))
C_lip = (B_lip[0] - d_1*math.sin(beta), B_lip[1] - d_1*math.cos(beta))

l3_dr  = A_lip[0] - C_lip[0]
l3_dz  = A_lip[1] - C_lip[1]
l3_len = math.sqrt(l3_dr**2 + l3_dz**2)
nt_r   = -l3_dz / l3_len
nt_z   =  l3_dr / l3_len
A_tol  = (A_lip[0] + nt_r * tolerance, A_lip[1] + nt_z * tolerance)
C_tol  = (C_lip[0] + nt_r * tolerance, C_lip[1] + nt_z * tolerance)

def w2l(rw, zw):
    dr = rw - orbit_r_planet;  dz = zw - z_disk
    return (dr * cos_phi - dz * sin_phi, dr * sin_phi + dz * cos_phi)

def l2w(lr, lz):
    return (orbit_r_planet + lr * cos_phi + lz * sin_phi,
            z_disk          - lr * sin_phi + lz * cos_phi)

_cone_scale_ch = 1.0
lr_outer    = (T_planet / 2.0 + 2.0) * m_top_planet * _cone_scale_ch
local_A_tol = w2l(*A_tol)
local_C_tol = w2l(*C_tol)
lz_top      = local_A_tol[1] + m_top_planet
t_ext       = (lz_top - local_C_tol[1]) / (local_A_tol[1] - local_C_tol[1])
r_A_ext     = local_C_tol[0] + t_ext * (local_A_tol[0] - local_C_tol[0])

# After-chamfer top corner on the SUN-FACING side
local_tip_z = gw / 2.0 + ext_local_pl
frac        = (local_tip_z - local_C_tol[1]) / (lz_top - local_C_tol[1])
r_boundary  = local_C_tol[0] + frac * (r_A_ext - local_C_tol[0])
z_planet_max     = z_disk + r_boundary * sin_phi + local_tip_z * cos_phi
r_chamfer_at_max = orbit_r_planet - r_boundary * cos_phi + local_tip_z * sin_phi

# Sun extension/retention values
ext_local_sun   = max(0.0, z_planet_max - (z_disk_sun + gw / 2.0))
m_ext_sun       = m_top_sun * (full_h + ext_local_sun) / full_h if ext_local_sun > 0.0 else m_top_sun
m_ext_sun_uncapped = m_ext_sun
m_ext_sun_capped   = min(m_ext_sun, (r_chamfer_at_max - tolerance) / (T_sun / 2.0 + 1.0))

ra_sun_ext_uncapped = (T_sun / 2.0 + 1.0) * m_ext_sun_uncapped
rf_sun_ext_uncapped = (T_sun / 2.0 - 1.25) * m_ext_sun_uncapped
ra_sun_ext_capped   = (T_sun / 2.0 + 1.0) * m_ext_sun_capped
rf_sun_ext_capped   = (T_sun / 2.0 - 1.25) * m_ext_sun_capped

# Sun bevel cone apex (Line 2 slope reference)
z_apex_sun = (z_disk_sun + gw / 2.0
              - gw * m_top_sun / max(m_top_sun - m_bot_sun, 1e-9))
slope_r2   = ra_sun_ext_capped / (z_planet_max - z_apex_sun)

# Slope_line3 — TWO formulas
# (a) BUGGY (v0.5.92): uses delta_lr signed → describes RING-facing chamfer
delta_lr   = r_A_ext - local_C_tol[0]   # < 0
delta_lz   = lz_top  - local_C_tol[1]   # > 0
slope_line3_BUG = ((delta_lr * cos_phi + delta_lz * sin_phi)
                   / (delta_lz * cos_phi - delta_lr * sin_phi))

# (b) PROPOSED FIX: sun-facing chamfer direction (flip sign of delta_lr)
slope_line3_FIX = ((-delta_lr * cos_phi + delta_lz * sin_phi)
                   / (delta_lz * cos_phi + delta_lr * sin_phi))

# Triangle C points for both formulas, using capped ra_sun_ext
def compute_C(slope_l3):
    dz_C = (ra_sun_ext_capped - rf_sun_ext_capped) / (slope_l3 - slope_r2)
    z_C  = z_planet_max - dz_C
    r_C  = ra_sun_ext_capped - slope_l3 * dz_C
    return (r_C, z_C, dz_C)

r_C_bug, z_C_bug, dz_C_bug = compute_C(slope_line3_BUG)
r_C_fix, z_C_fix, dz_C_fix = compute_C(slope_line3_FIX)

# ─── Geometry for drawing ─────────────────────────────────────────────────
# Sun outline in world r-z (top: ra_sun at z_planet_max, root rf at z_disk_sun-gw/2 etc.)
# We approximate the sun's outer profile as a trapezoid from its bevel cone.
sun_top_r    = ra_sun_ext_capped
sun_top_z    = z_planet_max
sun_body_top_z = z_disk_sun + gw/2.0
sun_body_bot_z = z_disk_sun - gw/2.0
sun_top_face_r = (T_sun/2.0 + 1.0) * m_top_sun
sun_bot_face_r = (T_sun/2.0 + 1.0) * m_bot_sun

sun_outline = [
    (0,                sun_body_bot_z),
    (sun_bot_face_r,   sun_body_bot_z),
    (sun_top_face_r,   sun_body_top_z),
    (sun_top_r,        sun_top_z),
    (0,                sun_top_z),
    (0,                sun_body_bot_z),
]

# Planet outline in world r-z (rectangle in local r-z, tilted at phi).
# Local box: r in [-ra_planet, +ra_planet], z in [-gw/2, +gw/2+ext_local_pl]
ra_planet = (T_planet / 2.0 + 1.0) * m_top_planet
rf_planet = (T_planet / 2.0 - 1.25) * m_top_planet
planet_box_local = [
    (-ra_planet, -gw/2.0),
    ( ra_planet, -gw/2.0),
    ( ra_planet,  gw/2.0 + ext_local_pl),
    (-ra_planet,  gw/2.0 + ext_local_pl),
]
planet_box_world = [l2w(lr, lz) for lr, lz in planet_box_local]

# Chamfer cutter rectangle (local) — corners at lr ∈ [r_A_ext or local_C_tol[0], lr_outer]
# We need both sides of the revolved cutter — at positive local r (ring-side)
# AND negative local r (sun-side).
chamfer_local = [
    (r_A_ext,         lz_top),
    (lr_outer,        lz_top),
    (lr_outer,        local_C_tol[1]),
    (local_C_tol[0],  local_C_tol[1]),
]
chamfer_world_ringside = [l2w(lr, lz) for lr, lz in chamfer_local]
chamfer_world_sunside  = [l2w(-lr, lz) for lr, lz in chamfer_local]

# Sun-facing chamfer FACE in world (the line from local (-r_A_ext, lz_top) to (-local_C_tol[0], local_C_tol[1]))
# Restricted to the visible portion within the planet body (lz_top is above tip face).
# Top of exposed face: at local_tip_z, lr = -r_boundary
top_chamfer_face_world = l2w(-r_boundary, local_tip_z)   # = (r_chamfer_at_max, z_planet_max)
bot_chamfer_face_world = l2w(-local_C_tol[0], local_C_tol[1])

# Ring-facing chamfer face top corner (for symmetry/reference)
top_chamfer_face_ring_world = l2w(r_boundary, local_tip_z)
bot_chamfer_face_ring_world = l2w(local_C_tol[0], local_C_tol[1])

# Triangle A-B-C points (using capped ra_sun_ext)
A_pt = (ra_sun_ext_capped, z_planet_max)
B_pt = (rf_sun_ext_capped, z_planet_max)
C_pt_bug = (r_C_bug, z_C_bug)
C_pt_fix = (r_C_fix, z_C_fix)

# ─── Plot ────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 10))

# Sun
sun_xs = [p[0] for p in sun_outline]
sun_zs = [p[1] for p in sun_outline]
ax.fill(sun_xs, sun_zs, color='#fdd835', alpha=0.4, label='Sun')
ax.plot(sun_xs, sun_zs, color='#c9a000', linewidth=1.5)

# Planet body (tilted box)
pl_xs = [p[0] for p in planet_box_world] + [planet_box_world[0][0]]
pl_zs = [p[1] for p in planet_box_world] + [planet_box_world[0][1]]
ax.fill(pl_xs, pl_zs, color='#42a5f5', alpha=0.35, label='Planet (tilted at phi)')
ax.plot(pl_xs, pl_zs, color='#1565c0', linewidth=1.2)

# Chamfer cutter outline — ring side
ch_r_xs = [p[0] for p in chamfer_world_ringside] + [chamfer_world_ringside[0][0]]
ch_r_zs = [p[1] for p in chamfer_world_ringside] + [chamfer_world_ringside[0][1]]
ax.plot(ch_r_xs, ch_r_zs, color='#ef6c00', linewidth=1, linestyle='--',
        label='Chamfer cutter (revolved, ring-side)')

# Chamfer cutter outline — sun side
ch_s_xs = [p[0] for p in chamfer_world_sunside] + [chamfer_world_sunside[0][0]]
ch_s_zs = [p[1] for p in chamfer_world_sunside] + [chamfer_world_sunside[0][1]]
ax.plot(ch_s_xs, ch_s_zs, color='#d32f2f', linewidth=1, linestyle='--',
        label='Chamfer cutter (revolved, sun-side)')

# Exposed sun-facing chamfer face (the one Line 3 should be parallel to)
ax.plot([bot_chamfer_face_world[0], top_chamfer_face_world[0]],
        [bot_chamfer_face_world[1], top_chamfer_face_world[1]],
        color='#d32f2f', linewidth=3.5,
        label='SUN-FACING chamfer face (slope ≈ +%.3f)' %
              ((top_chamfer_face_world[0] - bot_chamfer_face_world[0]) /
               (top_chamfer_face_world[1] - bot_chamfer_face_world[1])))

# Exposed ring-facing chamfer face
ax.plot([bot_chamfer_face_ring_world[0], top_chamfer_face_ring_world[0]],
        [bot_chamfer_face_ring_world[1], top_chamfer_face_ring_world[1]],
        color='#ef6c00', linewidth=3.5,
        label='RING-FACING chamfer face (slope ≈ %.3f)' %
              ((top_chamfer_face_ring_world[0] - bot_chamfer_face_ring_world[0]) /
               (top_chamfer_face_ring_world[1] - bot_chamfer_face_ring_world[1])))

# Mark r_chamfer_at_max, z_planet_max
ax.plot(r_chamfer_at_max, z_planet_max, marker='o', color='#d32f2f', markersize=8)
ax.annotate(f'  r_chamfer_at_max\n  ({r_chamfer_at_max:.2f}, {z_planet_max:.2f})',
            (r_chamfer_at_max, z_planet_max), fontsize=8, va='bottom')

# A and B
ax.plot(*A_pt, marker='s', color='black', markersize=9)
ax.annotate(f' A=(ra_sun_ext, z_planet_max)\n   =({A_pt[0]:.2f}, {A_pt[1]:.2f})',
            A_pt, fontsize=9, va='bottom', ha='left', color='black')
ax.plot(*B_pt, marker='s', color='black', markersize=9)
ax.annotate(f' B=(rf_sun_ext, z_planet_max)\n   =({B_pt[0]:.2f}, {B_pt[1]:.2f})',
            B_pt, fontsize=9, va='top', ha='right', color='black')

# Line 1: A → B
ax.plot([A_pt[0], B_pt[0]], [A_pt[1], B_pt[1]],
        color='black', linewidth=2, label='Line 1 (A→B)')

# Line 3 (BUGGY formula)
ax.plot([A_pt[0], C_pt_bug[0]], [A_pt[1], C_pt_bug[1]],
        color='magenta', linewidth=2, linestyle=':',
        label=f'Line 3 BUGGY (slope={slope_line3_BUG:+.3f}) → C above (DOME)')
ax.plot(*C_pt_bug, marker='x', color='magenta', markersize=12, markeredgewidth=3)
ax.annotate(f'  C (buggy)\n  ({C_pt_bug[0]:.2f}, {C_pt_bug[1]:.2f})',
            C_pt_bug, fontsize=8, color='magenta')

# Line 3 (PROPOSED FIX)
ax.plot([A_pt[0], C_pt_fix[0]], [A_pt[1], C_pt_fix[1]],
        color='green', linewidth=2.5,
        label=f'Line 3 PROPOSED (slope={slope_line3_FIX:+.3f}) → C inward-below')
# Line 2 from B to C_fix
ax.plot([B_pt[0], C_pt_fix[0]], [B_pt[1], C_pt_fix[1]],
        color='green', linewidth=1.5, linestyle='-.',
        label=f'Line 2 (B→C, slope_r2={slope_r2:+.3f})')
ax.plot(*C_pt_fix, marker='*', color='green', markersize=18)
ax.annotate(f'  C (proposed)\n  ({C_pt_fix[0]:.2f}, {C_pt_fix[1]:.2f})',
            C_pt_fix, fontsize=8, color='green', va='top')

# Axes & labels
ax.axhline(z_planet_max, color='gray', linewidth=0.5, linestyle=':')
ax.axvline(0, color='black', linewidth=0.5)
ax.set_xlabel('world r')
ax.set_ylabel('world z')
ax.set_title(f'Planets retention cross-section (default props, phi={math.degrees(phi):.2f}°)\n'
             f'sun-facing chamfer goes outer-high → inner-low; Line 3 parallel to it goes A inward-downward')
ax.set_aspect('equal')
ax.grid(True, alpha=0.3)
ax.legend(loc='lower right', fontsize=8)

# Information box
info_text = (
    f"DEFAULTS: cone_r={cone_r}, cone_h={cone_h}, gw={gw}, T_sun={T_sun}, T_planet={T_planet}, T_ring={T_ring}\n"
    f"phi = {math.degrees(phi):.2f}°, beta = {math.degrees(beta):.2f}°, gear_scale = {gear_scale:.4f}\n"
    f"\n"
    f"r_A_ext = {r_A_ext:.3f}  local_C_tol = ({local_C_tol[0]:.3f}, {local_C_tol[1]:.3f})  lz_top = {lz_top:.3f}\n"
    f"delta_lr = {delta_lr:+.3f}  delta_lz = {delta_lz:+.3f}\n"
    f"\n"
    f"z_planet_max = {z_planet_max:.3f}     r_chamfer_at_max = {r_chamfer_at_max:.3f}\n"
    f"ra_sun_ext (uncapped) = {ra_sun_ext_uncapped:.3f}  → exceeds r_chamfer_at_max!\n"
    f"ra_sun_ext (capped)   = {ra_sun_ext_capped:.3f}\n"
    f"rf_sun_ext (capped)   = {rf_sun_ext_capped:.3f}\n"
    f"\n"
    f"slope_line3 BUGGY    = {slope_line3_BUG:+.3f} (ring-facing chamfer direction)\n"
    f"slope_line3 PROPOSED = {slope_line3_FIX:+.3f} (sun-facing chamfer direction)\n"
    f"slope_r2             = {slope_r2:+.3f}\n"
    f"\n"
    f"BUGGY:    C = ({C_pt_bug[0]:.3f}, {C_pt_bug[1]:.3f})  dz_C = {dz_C_bug:+.3f}  → z_C > z_planet_max = DOME\n"
    f"PROPOSED: C = ({C_pt_fix[0]:.3f}, {C_pt_fix[1]:.3f})  dz_C = {dz_C_fix:+.3f}  → z_C < z_planet_max ✓"
)
plt.figtext(0.02, 0.02, info_text, fontsize=8, family='monospace',
            bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray'))

plt.subplots_adjust(bottom=0.32)
plt.savefig(r'G:/My Drive/Claude/planets/cross_section.png', dpi=120, bbox_inches='tight')
print("Wrote cross_section.png")
