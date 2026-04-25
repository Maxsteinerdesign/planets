bl_info = {
    "name":        "Planets",
    "author":      "Max Steiner",
    "version":     (0, 5, 31),
    "blender":     (5, 0, 0),
    "location":    "View3D > Sidebar > Planets",
    "description": "Planets -- planetary gear development sandbox",
    "category":    "Object",
}

import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Quaternion
from bpy.props import FloatProperty, IntProperty, BoolProperty
from math import gcd

# ============================================================
# Constants
# ============================================================

PREFIX = "PL_"


# ============================================================
# Properties
# ============================================================

class PlanetsProperties(bpy.types.PropertyGroup):
    cone_diameter   : FloatProperty(name="Mouth Diameter",  default=100.0, min=10.0,  max=1000.0,
                                    description="Diameter at the wide/top opening of the cone (mm)")
    cone_height     : FloatProperty(name="Cone Height",     default=100.0, min=5.0,   max=1000.0,
                                    description="Height of the frustum (mouth to truncated bottom)")
    gear_width      : FloatProperty(name="Gear Height",     default=20.0,  min=1.0,   max=200.0,
                                    description="Height (thickness) of the planetary gear disk")
    wall_thickness  : FloatProperty(name="Wall Thickness",  default=3.0,   min=3.0,   max=40.0,
                                    description="Gap from ring gear teeth tips to cone wall (mm)")
    n_planets       : IntProperty  (name="# Planets",       default=3,     min=2,     max=8)
    T_sun           : IntProperty  (name="Sun Teeth",       default=12,    min=6,     max=60)
    T_planet        : IntProperty  (name="Planet Teeth",    default=12,    min=6,     max=60)
    tooth_clearance : FloatProperty(name="Tooth Clearance", default=0.05,  min=0.0,   max=0.30,
                                    step=1,
                                    description="Angular fraction of pitch left as gap between meshing teeth")
    gear_elongation : FloatProperty(name="Gear Elongation", default=0.0,   min=0.0,   max=200.0,
                                    description="Extends each gear outward beyond the gear zone (mm)")
    anim_speed      : FloatProperty(name="Speed (deg/frame)", default=2.0, min=0.1,   max=30.0)


# ============================================================
# Gear profile helpers
# ============================================================

def _spur_pts(T, m, clearance=0.05, addendum=1.0):
    ra    = (T / 2.0 + addendum) * m
    rp    =  T / 2.0            * m
    rf    = max((T / 2.0 - 1.25) * m, rp * 0.4)
    pitch = 2.0 * math.pi / T
    ht    = pitch * (0.5 - clearance)
    fc    = 0.2 * m   # tip chamfer drop — rounds sharp tip corners
    pts   = []
    for i in range(T):
        a = i * pitch
        for da, r in [(-ht*0.90, rf), (-ht*0.55, rp),
                      (-ht*0.22, ra - fc), (-ht*0.10, ra),
                      ( ht*0.10, ra), ( ht*0.22, ra - fc),
                      ( ht*0.55, rp), ( ht*0.90, rf)]:
            pts.append((r * math.cos(a + da), r * math.sin(a + da)))
    return pts


def _ring_inner_pts(T, m, clearance=0.05):
    rp    =  T / 2.0         * m
    ra    = (T / 2.0 - 0.75) * m
    rf    = (T / 2.0 + 1.25) * m
    pitch = 2.0 * math.pi / T
    ht    = pitch * (0.5 - clearance)
    pts   = []
    for i in range(T):
        a = i * pitch
        for da, r in [(-ht*0.90, rf), (-ht*0.55, rp), (-ht*0.22, ra),
                      ( ht*0.22, ra), ( ht*0.55, rp), ( ht*0.90, rf)]:
            pts.append((r * math.cos(a + da), r * math.sin(a + da)))
    return pts


def _rotate_pts(pts, angle):
    c, s = math.cos(angle), math.sin(angle)
    return [(x*c - y*s, x*s + y*c) for x, y in pts]


# ============================================================
# Geometry builders
# ============================================================

def _link(obj):
    if obj.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def _assign_color(obj, rgba):
    mat = bpy.data.materials.new(obj.name + "_Mat")
    mat.use_nodes = False
    mat.diffuse_color = rgba
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def _make_solid_frustum(r_top, r_bottom, height, ext_top=0.0, segments=96):
    full_h = height * 4.0 / 3.0
    r_ext  = r_top * (full_h + ext_top) / full_h   # cone radius at z = +ext_top
    depth  = height + ext_top
    mesh = bpy.data.meshes.new(PREFIX + "BevelGear_Mesh")
    bm   = bmesh.new()
    bmesh.ops.create_cone(bm,
        cap_ends=True, cap_tris=False, segments=segments,
        radius1=r_bottom, radius2=r_ext, depth=depth)
    for v in bm.verts:
        v.co.z -= depth / 2.0 - ext_top  # top at z=+ext_top, bottom at z=-height
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(PREFIX + "BevelGear", mesh)
    _link(obj)
    return obj


def _connect_profiles(name, pts_top, pts_bot, z_top, z_bot):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    bm   = bmesh.new()
    n    = len(pts_top)
    vb   = [bm.verts.new((x, y, z_bot)) for x, y in pts_bot]
    vt   = [bm.verts.new((x, y, z_top)) for x, y in pts_top]
    bm.verts.ensure_lookup_table()
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
    bm.faces.new(vb)
    bm.faces.new(list(reversed(vt)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj)
    return obj


def _make_inner_fill(name, hub_r, hub_top, ring_r_top, ring_r_bot, z_bot,
                     z_top=0.0, segments=64):
    """
    Solid of revolution: profile in r-z plane revolved around Z.
    Profile: (0,z_bot)→(ring_r_bot,z_bot)→(ring_r_top,z_top)→(hub_r,hub_top)→(0,hub_top)
    Used as DIFFERENCE cutter: carves hub+slope cavity from the solid cone.
    Outer wall follows the ra_ring bevel; slope goes outward AND upward from hub to rim.
    """
    bm      = bmesh.new()
    profile = [
        (0.0,        z_bot),
        (ring_r_bot, z_bot),
        (ring_r_top, z_top),
        (hub_r,      hub_top),
        (0.0,        hub_top),
    ]
    rings = []
    for r, z in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))])
        else:
            rings.append([
                bm.verts.new((r * math.cos(2*math.pi*i/segments),
                              r * math.sin(2*math.pi*i/segments), z))
                for i in range(segments)
            ])
    bm.verts.ensure_lookup_table()
    for ri in range(len(rings) - 1):
        r0, r1 = rings[ri], rings[ri + 1]
        # Use profile r values directly (not 3D .co.length which includes z offset)
        p0_r = profile[ri][0]
        p1_r = profile[ri + 1][0]
        if len(r0) == 1:
            # bottom pole fan — reversed winding so normal faces -Z (outward/down)
            for j in range(segments):
                bm.faces.new([r0[0], r1[(j + 1) % segments], r1[j]])
        elif len(r1) == 1:
            # top pole fan — winding so normal faces +Z (outward/up)
            for j in range(segments):
                bm.faces.new([r0[j], r0[(j + 1) % segments], r1[0]])
        elif p1_r >= p0_r:
            # r increases — outward normal faces +R
            for j in range(segments):
                k = (j + 1) % segments
                bm.faces.new([r0[j], r0[k], r1[k], r1[j]])
        else:
            # r decreases — winding depends on z direction so normal is always outward
            p0_z = profile[ri][1]
            p1_z = profile[ri + 1][1]
            if p1_z >= p0_z:
                # r decreases, z increases — slope faces up, normal is +Z
                for j in range(segments):
                    k = (j + 1) % segments
                    bm.faces.new([r0[j], r0[k], r1[k], r1[j]])
            else:
                # r decreases, z decreases — slope faces down, normal is -Z
                for j in range(segments):
                    k = (j + 1) % segments
                    bm.faces.new([r0[j], r1[j], r1[k], r0[k]])
    mesh = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj)
    return obj


def _make_circle_pts(r, segments=64):
    return [(r * math.cos(2*math.pi*i/segments),
             r * math.sin(2*math.pi*i/segments))
            for i in range(segments)]


def _make_bevel_gear(name, pts_top, pts_bot, gw, color, location, pts_ext=None, ext_local=0.0):
    mesh = bpy.data.meshes.new(PREFIX + name + "_Mesh")
    bm   = bmesh.new()
    n    = len(pts_top)
    vb   = [bm.verts.new((x, y, -gw / 2.0)) for x, y in pts_bot]
    vt   = [bm.verts.new((x, y, +gw / 2.0)) for x, y in pts_top]
    bm.verts.ensure_lookup_table()
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
    bm.faces.new(vb)
    if pts_ext is not None and ext_local > 0.0:
        ve = [bm.verts.new((x, y, +gw / 2.0 + ext_local)) for x, y in pts_ext]
        bm.verts.ensure_lookup_table()
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([vt[i], vt[j], ve[j], ve[i]])
        bm.faces.new(list(reversed(ve)))
    else:
        bm.faces.new(list(reversed(vt)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(PREFIX + name, mesh)
    obj.location = location
    _link(obj)
    _assign_color(obj, color)
    return obj


# ============================================================
# Clear / cone radius helpers
# ============================================================

def _clear_pl_objects():
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.name.startswith(PREFIX) and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        if mat.name.startswith(PREFIX) and mat.users == 0:
            bpy.data.materials.remove(mat)


def _cone_r_at(cone_r, cone_h, z):
    full_h = cone_h * 4.0 / 3.0
    return cone_r * (full_h + z) / full_h


# ============================================================
# Tooth alignment
# ============================================================

def _planet_rotation(alpha, T_sun, T_planet, m):
    r_sun   = T_sun    * m / 2.0
    r_planet = T_planet * m / 2.0
    lp      = math.pi  * m
    sun_lin = (alpha % (2.0 * math.pi / T_sun)) * r_sun
    pl_lin  = (lp / 2.0 - sun_lin) % lp
    pl_ang  = pl_lin / r_planet
    return (alpha + math.pi - pl_ang) % (2.0 * math.pi / T_planet)


def _ring_rotation(alpha0, theta_p0, T_planet, T_ring, m):
    r_planet = T_planet * m / 2.0
    lp       = math.pi  * m
    pl_ang   = (alpha0 - theta_p0) % (2.0 * math.pi / T_planet)
    pl_lin   = pl_ang * r_planet
    rg_lin   = (lp / 2.0 - pl_lin) % lp
    rg_ang   = rg_lin / (T_ring * m / 2.0)
    return (alpha0 - rg_ang) % (2.0 * math.pi / T_ring)


# ============================================================
# Operators
# ============================================================

class PLANETS_OT_clear(bpy.types.Operator):
    bl_idname  = "planets.clear"
    bl_label   = "Clear All"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        _clear_pl_objects()
        return {'FINISHED'}


class PLANETS_OT_generate(bpy.types.Operator):
    bl_idname  = "planets.generate"
    bl_label   = "Generate"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Work in millimetres: 1 Blender unit = 1 mm
        context.scene.unit_settings.system       = 'METRIC'
        context.scene.unit_settings.scale_length = 0.001

        props     = context.scene.planets_props
        cone_r    = props.cone_diameter / 2.0
        cone_h    = props.cone_height
        gw        = props.gear_width
        n_pl      = props.n_planets
        T_sun     = props.T_sun
        T_planet  = props.T_planet
        T_ring    = T_sun + 2 * T_planet
        clearance = props.tooth_clearance
        ext       = props.gear_elongation

        r_bottom = cone_r / 4.0
        z_bot    = -gw
        z_disk   = -gw / 2.0

        # Module: ring gear runs parallel to cone wall — same bevel angle, constant gap.
        # m_top sizes ring tips to cone_r - wall at z=0.
        # m_bot sizes ring tips to cone_r*s_bot - wall at z=-gw (same 3mm gap, parallel).
        # All gears (ring, sun, planets) share m_top/m_bot — one bevel angle for all.
        wall   = props.wall_thickness
        full_h = cone_h * 4.0 / 3.0
        s_bot  = (full_h - gw) / full_h
        # Ring: outer surface parallel to cone wall (constant wall gap at top and bottom).
        m            = max(0.001, (cone_r       - wall) / (T_ring / 2.0 + 1.25))
        m_bot        = max(0.001, (cone_r*s_bot - wall) / (T_ring / 2.0 + 1.25))
        dm           = m * (1.0 - s_bot)          # total module drop over gw
        r_sun    = T_sun    * m / 2.0
        r_planet = T_planet * m / 2.0
        orbit_r  = r_sun + r_planet
        # Planet centre sits at z_disk; scale orbit radius to that level on the
        # apex bevel line.  phi = atan2(orbit_r, full_h) — axis points at apex.
        s_disk         = (full_h + z_disk) / full_h
        orbit_r_planet = orbit_r * s_disk
        phi            = math.atan2(orbit_r, full_h)
        beta           = math.atan2(cone_r, full_h)   # cone wall half-angle from Z

        # gear_scale: planet outer top corner (world radius) must fit within ring groove
        # outer boundary (rf = cone_r - wall at that z-level). No correction factor.
        _gs_num = (cone_r * (full_h + z_disk + (gw / 2.0) * math.cos(phi)) / full_h
                   - wall - (gw / 2.0) * math.sin(phi))
        _gs_den = (orbit_r * s_disk
                   + (T_planet / 2.0 + 1.0) * m
                     * (math.cos(phi) + cone_r * math.sin(phi) / full_h))
        gear_scale = min(1.0, _gs_num / _gs_den)

        orbit_r         = orbit_r         * gear_scale
        orbit_r_planet  = orbit_r_planet  * gear_scale

        alphas  = [2.0 * math.pi * i / n_pl for i in range(n_pl)]
        th_pl   = [_planet_rotation(a, T_sun, T_planet, m) for a in alphas]
        th_ring = _ring_rotation(alphas[0], th_pl[0], T_planet, T_ring, m)

        _clear_pl_objects()

        # 1. Solid frustum — extended upward by ext so ring void has material to cut into
        cone_obj = _make_solid_frustum(cone_r, r_bottom, cone_h, ext_top=ext)
        _assign_color(cone_obj, (0.45, 0.45, 0.48, 1.0))

        # hub_r: encloses sun outer tip at full module (relational, no static offset)
        hub_r = (T_sun / 2.0 + 1.0) * m

        # hub_top: slope at angle phi through planet bottom-face center
        z_bot_pl = z_disk - (gw / 2.0) * math.cos(phi)
        r_bot_pl = orbit_r_planet - (gw / 2.0) * math.sin(phi)
        hub_top  = max(z_bot, z_bot_pl + (r_bot_pl - hub_r) * math.tan(phi))

        # Sun: bottom rests on hub flat.
        # Pitch cone half-angle = (2*phi - beta) from Z axis — complement of planet inner angle
        # so that sun and planet pitch cones share a common apex.
        z_disk_sun = hub_top + gw / 2.0
        sun_raise  = (z_disk_sun - z_disk) / gw
        m_top_sun  = max(0.001, gear_scale * (m + dm * sun_raise))
        _sun_bevel = max(0.0, 2.0 * phi - beta)
        m_bot_sun  = max(0.001, m_top_sun - gw * 2.0 * math.tan(_sun_bevel) / T_sun)

        # z_outer and ra_fill are mutually dependent:
        #   slope:  z_outer = hub_top - (ra_fill - hub_r)*tan(phi)
        #   cone:   ra_fill = cone_r*(full_h + z_outer)/full_h - wall
        # Solve simultaneously so slope angle exactly equals phi:
        tan_phi = math.tan(phi)
        z_outer = (hub_top + tan_phi * (wall + hub_r - cone_r)) / (1.0 + tan_phi * cone_r / full_h)
        ra_fill = cone_r * (full_h + z_outer) / full_h - wall
        z_fill_bot  = z_outer - gw
        ra_fill_bot = max(m, cone_r * (full_h + z_fill_bot) / full_h - wall)

        # Planet modules: pitch cone half-angle = (beta - phi) from planet axis,
        # so that the outer pitch surface is parallel to the cone wall.
        m_top_planet = gear_scale * m
        m_bot_planet = max(0.001,
            m_top_planet - gw * 2.0 * math.tan(beta - phi) / T_planet
        )

        # Ring void bottom: deeper of planet tip depth and slope endpoint z_outer
        z_ring_bot    = (z_disk
                         - (gw / 2.0) * math.cos(phi)
                         - (T_planet / 2.0 + 1.0) * m_bot_planet * math.sin(phi))
        ring_void_bot = min(z_ring_bot, z_outer)   # min = more negative = deeper
        m_at_void_bot = max(0.001,
                            (cone_r * (full_h + ring_void_bot) / full_h - wall)
                            / (T_ring / 2.0 + 1.25))

        print(f"Planets v0.5.31 generate: gw={gw} m={m:.3f} gear_scale={gear_scale:.4f} m_top_planet={m_top_planet:.3f} m_bot_planet={m_bot_planet:.3f} T_ring={T_ring}")
        print(f"  phi={math.degrees(phi):.1f}° hub_r={hub_r:.2f} hub_top={hub_top:.2f}")
        print(f"  z_outer={z_outer:.2f} z_ring_bot={z_ring_bot:.2f} ring_void_bot={ring_void_bot:.2f}")
        print(f"  ra_fill={ra_fill:.2f} ra_fill_bot={ra_fill_bot:.2f}")

        # ── Boolean 1: Ring void DIFFERENCE ──
        # Top of void at z = ext (or z≈0 when ext=0); module at top scales with cone.
        # Bottom at ring_void_bot. Outer surface stays cone-parallel throughout.
        m_ring_top  = m * (full_h + ext) / full_h   # module at z=+ext (= m when ext=0)
        ring_top    = _rotate_pts(_ring_inner_pts(T_ring, m_ring_top,   clearance), th_ring)
        ring_bot    = _rotate_pts(_ring_inner_pts(T_ring, m_at_void_bot, clearance), th_ring)
        void_obj    = _connect_profiles("VOID_Ring", ring_top, ring_bot, ext + m * 0.1, ring_void_bot)
        mod           = cone_obj.modifiers.new("RingCut", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object    = void_obj
        mod.solver    = 'EXACT'
        with context.temp_override(active_object=cone_obj):
            bpy.ops.object.modifier_apply(modifier="RingCut")
        bpy.data.objects.remove(void_obj, do_unlink=True)

        # ── Boolean 2: Fill UNION ──
        # Adds hub+slope solid back. Fill bottom is buried in solid cone — no artifact.
        v_before = len(cone_obj.data.vertices)
        fill_obj  = _make_inner_fill("FILL_Base", hub_r, hub_top,
                                     ra_fill, ra_fill_bot,
                                     z_fill_bot, z_top=z_outer)
        mod_fill           = cone_obj.modifiers.new("FillAdd", 'BOOLEAN')
        mod_fill.operation = 'UNION'
        mod_fill.object    = fill_obj
        mod_fill.solver    = 'FLOAT'
        with context.temp_override(active_object=cone_obj):
            bpy.ops.object.modifier_apply(modifier="FillAdd")
        bpy.data.objects.remove(fill_obj, do_unlink=True)
        print(f"  fill UNION: verts {v_before}->{len(cone_obj.data.vertices)}")

        # Extension: world-Z increment ext → correct local-Z per gear axis direction.
        # Planet tilted at phi: ext world-Z = ext/cos(phi) local-Z.
        # Sun vertical: ext world-Z = ext local-Z.
        # Tip profile is cone-scaled at z=+ext so ring and planet stay parallel throughout.
        # (cone-scaled: m_ext = m_top * (full_h + ext) / full_h, same ratio as ring groove)
        if ext > 0.0:
            ext_local_pl  = ext / math.cos(phi)
            ext_local_sun = ext
            cone_scale_ext = (full_h + ext) / full_h
            m_ext_planet   = m_top_planet * cone_scale_ext
            m_ext_sun      = m_top_sun    * cone_scale_ext
        else:
            ext_local_pl = ext_local_sun = 0.0
            m_ext_planet = m_top_planet
            m_ext_sun    = m_top_sun

        # 3. Sun gear — raised by sun_raise*gw; top=m_top_sun, bottom=m_bot_sun.
        pts_ext_sun = _spur_pts(T_sun, m_ext_sun, clearance) if ext > 0.0 else None
        _make_bevel_gear("SunGear",
            _spur_pts(T_sun, m_top_sun, clearance),
            _spur_pts(T_sun, m_bot_sun, clearance),
            gw, (0.9, 0.78, 0.05, 1.0), Vector((0.0, 0.0, z_disk_sun)),
            pts_ext=pts_ext_sun, ext_local=ext_local_sun)

        # 4. Planet gears — placed on apex bevel line at z_disk, tilted so axis
        #    points at cone apex → bevel face is parallel to the ring gear bevel.
        for i in range(n_pl):
            pts_ext_pl = (_rotate_pts(_spur_pts(T_planet, m_ext_planet, clearance), th_pl[i])
                          if ext > 0.0 else None)
            pl_obj = _make_bevel_gear(f"Planet_{i:02d}",
                _rotate_pts(_spur_pts(T_planet, m_top_planet, clearance), th_pl[i]),
                _rotate_pts(_spur_pts(T_planet, m_bot_planet, clearance), th_pl[i]),
                gw, (0.15, 0.55, 0.85, 1.0),
                Vector((orbit_r_planet * math.cos(alphas[i]),
                        orbit_r_planet * math.sin(alphas[i]), z_disk)),
                pts_ext=pts_ext_pl, ext_local=ext_local_pl)
            tilt_axis = Vector((-math.sin(alphas[i]), math.cos(alphas[i]), 0.0))
            rest_q = Quaternion(tilt_axis, +phi)
            pl_obj.rotation_mode = 'QUATERNION'
            pl_obj.rotation_quaternion = rest_q
            pl_obj['rest_q'] = list(rest_q)

        spacing_ok = (T_sun + T_ring) % n_pl == 0
        self.report({'INFO'},
            f"T_ring={T_ring}  m={m:.3f}  wall={wall:.1f}  spacing={'OK' if spacing_ok else 'INVALID'}")
        return {'FINISHED'}


# ============================================================
# Animation helpers
# ============================================================

def _loop_cone_revs(T_sun, T_planet, T_ring):
    # Carrier must complete integer revolutions for seamless loop.
    # Planet tooth alignment is automatically satisfied -- no stricter condition needed.
    return (T_ring + T_sun) // gcd(T_ring, T_sun)


# ============================================================
# Animate operator
# ============================================================

class PLANETS_OT_animate(bpy.types.Operator):
    bl_idname  = "planets.animate"
    bl_label   = "Animate"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props    = context.scene.planets_props
        T_sun    = props.T_sun
        T_planet = props.T_planet
        T_ring   = T_sun + 2 * T_planet
        n_pl     = props.n_planets
        speed    = props.anim_speed

        cone_obj    = bpy.data.objects.get(PREFIX + "BevelGear")
        planet_objs = sorted(
            [o for o in bpy.data.objects if o.name.startswith(PREFIX + "Planet_")],
            key=lambda o: o.name)

        if not cone_obj or not planet_objs:
            self.report({'ERROR'}, "Generate the gear system first.")
            return {'CANCELLED'}

        cone_r     = props.cone_diameter / 2.0
        cone_h     = props.cone_height
        gw         = props.gear_width
        wall       = props.wall_thickness
        clearance  = props.tooth_clearance
        full_h = cone_h * 4.0 / 3.0
        s_bot  = (full_h - gw) / full_h
        m      = max(0.001, (cone_r - wall) / (T_ring / 2.0 + 1.25))
        orbit_r    = (T_sun + T_planet) * m / 2.0
        z_disk     = -gw / 2.0
        s_disk     = (full_h + z_disk) / full_h
        phi        = math.atan2(orbit_r, full_h)
        _gs_num = (cone_r * (full_h + z_disk + (gw / 2.0) * math.cos(phi)) / full_h
                   - wall - (gw / 2.0) * math.sin(phi))
        _gs_den = (orbit_r * s_disk
                   + (T_planet / 2.0 + 1.0) * m
                     * (math.cos(phi) + cone_r * math.sin(phi) / full_h))
        gear_scale = min(1.0, _gs_num / _gs_den)
        orbit_r_planet = orbit_r * s_disk * gear_scale
        alphas     = [2.0 * math.pi * i / n_pl for i in range(n_pl)]

        ratio_carrier  = T_ring / (T_ring + T_sun)
        ratio_pl_world = ratio_carrier * (T_sun + T_planet) / T_planet

        N_cone       = _loop_cone_revs(T_sun, T_planet, T_ring)
        total_frames = int(N_cone * 360.0 / speed)

        all_anim_objs = [cone_obj] + planet_objs

        for obj in all_anim_objs:
            obj.rotation_mode = 'QUATERNION'
            if obj.animation_data and obj.animation_data.action:
                old = obj.animation_data.action
                obj.animation_data.action = None
                if old.users == 0:
                    bpy.data.actions.remove(old)

        context.scene.frame_start = 0
        context.scene.frame_end   = total_frames

        # Step: keep carrier rotation <= 10 deg per keyframe to avoid orbit drift
        carrier_deg_per_frame = speed * ratio_carrier
        step      = max(1, int(10.0 / carrier_deg_per_frame))
        kf_frames = sorted(set(list(range(0, total_frames + 1, step)) + [0, total_frames]))

        prev_cone_q = None
        prev_pl_q   = [None] * len(planet_objs)

        for t in kf_frames:
            frac     = t / total_frames if total_frames > 0 else 0.0
            cone_rad = frac * N_cone * 2.0 * math.pi
            theta_c  = cone_rad * ratio_carrier

            q = Quaternion((0.0, 0.0, 1.0), cone_rad)
            if prev_cone_q is not None and q.dot(prev_cone_q) < 0:
                q.negate()
            prev_cone_q = q.copy()
            cone_obj.rotation_quaternion = q
            cone_obj.keyframe_insert(data_path="rotation_quaternion", frame=t)

            for i, pl_obj in enumerate(planet_objs):
                orbit_angle = alphas[i] + theta_c
                pl_obj.location = Vector((
                    orbit_r_planet * math.cos(orbit_angle),
                    orbit_r_planet * math.sin(orbit_angle),
                    z_disk))
                spin = frac * N_cone * 2.0 * math.pi * ratio_pl_world
                tilt_axis_t = Vector((-math.sin(orbit_angle), math.cos(orbit_angle), 0.0))
                rest_q_t = Quaternion(tilt_axis_t, phi)
                q_pl = rest_q_t @ Quaternion((0.0, 0.0, 1.0), spin)
                if prev_pl_q[i] is not None and q_pl.dot(prev_pl_q[i]) < 0:
                    q_pl.negate()
                prev_pl_q[i] = q_pl.copy()
                pl_obj.rotation_quaternion = q_pl
                pl_obj.keyframe_insert(data_path="location",            frame=t)
                pl_obj.keyframe_insert(data_path="rotation_quaternion", frame=t)

        # LINEAR interpolation + CYCLES repeat
        # Blender 5.0: fcurves live in layered action channelbags
        for obj in all_anim_objs:
            if not (obj.animation_data and obj.animation_data.action):
                continue
            act = obj.animation_data.action
            fcurves = []
            try:
                fcurves = list(act.fcurves)
            except AttributeError:
                for layer in act.layers:
                    for strip in layer.strips:
                        try:
                            for bag in strip.channelbags:
                                fcurves.extend(bag.fcurves)
                        except AttributeError:
                            pass
            for fc in fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
                if not fc.modifiers:
                    mod = fc.modifiers.new(type='CYCLES')
                    mod.mode_before = 'REPEAT'
                    mod.mode_after  = 'REPEAT'
                fc.update()

        context.scene.frame_set(0)
        if not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

        self.report({'INFO'},
            f"Loop: {total_frames} frames  ({N_cone} cone rev, "
            f"{len(kf_frames)} keyframes/object)")
        return {'FINISHED'}


# ============================================================
# UI helpers -- discrete tooth-count selection
# ============================================================

def _valid_T_planet_entries(T_sun, max_T=60):
    entries = []
    for T_pl in range(6, max_T + 1):
        valid_n = [n for n in (3, 4, 5, 6) if (T_sun + T_pl) % n == 0]
        if valid_n:
            entries.append((T_pl, valid_n))
    return entries


def _max_n_planets_physical(T_sun, T_planet, m, clearance_mm=2.0):
    r_planet_outer = (T_planet / 2.0 + 1.0) * m
    orbit_r        = (T_sun + T_planet) / 2.0 * m
    if orbit_r <= r_planet_outer + clearance_mm:
        return 0
    ratio = min((r_planet_outer + clearance_mm) / orbit_r, 1.0 - 1e-12)
    return int(math.pi / math.asin(ratio))


# ============================================================
# Set-value operators (button grids)
# ============================================================

class PLANETS_OT_set_T_planet(bpy.types.Operator):
    bl_idname  = "planets.set_t_planet"
    bl_label   = "Set Planet Teeth"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    value      : IntProperty()
    def execute(self, context):
        context.scene.planets_props.T_planet = self.value
        return {'FINISHED'}


class PLANETS_OT_set_n_planets(bpy.types.Operator):
    bl_idname  = "planets.set_n_planets"
    bl_label   = "Set Planet Count"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    value      : IntProperty()
    def execute(self, context):
        context.scene.planets_props.n_planets = self.value
        return {'FINISHED'}


# ============================================================
# Panel
# ============================================================

class PLANETS_PT_main(bpy.types.Panel):
    bl_label       = "Planets"
    bl_idname      = "PLANETS_PT_main"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "Planets"

    def draw(self, context):
        layout = self.layout
        props  = context.scene.planets_props

        # -- Cone --
        box = layout.box()
        box.label(text="Bevel Gear Cone")
        col = box.column(align=True)
        col.prop(props, "cone_diameter")
        col.prop(props, "cone_height")
        row = box.row()
        row.enabled = False
        row.label(text=f"Bottom Diameter: {props.cone_diameter / 4.0:.1f}mm  (truncated 1/4)")

        # -- Planetary Zone --
        box = layout.box()
        box.label(text="Planetary Zone")
        col = box.column(align=True)
        col.prop(props, "gear_width")
        col.prop(props, "gear_elongation")
        col.prop(props, "wall_thickness")
        row = box.row()
        row.enabled = False
        row.label(text=f"Z: 0.0 -> {-props.gear_width:.1f}  (flush with mouth)")

        # -- Gear Counts --
        T_ring     = props.T_sun + 2 * props.T_planet
        m = max(0.001, (props.cone_diameter / 2.0 - props.wall_thickness) / (T_ring / 2.0 + 1.25))
        max_n      = _max_n_planets_physical(props.T_sun, props.T_planet, m)

        box = layout.box()
        box.label(text="Gear Counts")

        col = box.column(align=True)
        col.prop(props, "T_sun")
        col.prop(props, "tooth_clearance")

        # Planet teeth buttons
        sub = box.box()
        sub.label(text="Planet Teeth  [valid # planets]:")
        entries = _valid_T_planet_entries(props.T_sun)
        grid    = sub.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for T_pl, valid_n in entries:
            label = f"{T_pl}  [{','.join(str(n) for n in valid_n)}]"
            op = grid.operator("planets.set_t_planet", text=label,
                               depress=(props.T_planet == T_pl))
            op.value = T_pl

        # n_planets buttons (spacing + physical fit only)
        sub2 = box.box()
        sub2.label(text="# Planets  (spacing + clearance):")
        valid_n_pl = [n for n in (3, 4, 5, 6)
                      if (props.T_sun + props.T_planet) % n == 0 and n <= max_n]
        row = sub2.row(align=True)
        for n in valid_n_pl:
            op = row.operator("planets.set_n_planets", text=str(n),
                              depress=(props.n_planets == n))
            op.value = n
        if not valid_n_pl:
            err = sub2.row()
            err.alert = True
            err.label(text="No valid count -- adjust teeth or wall thickness")

        row = box.row()
        row.enabled = False
        row.label(text=f"Ring={T_ring}  m={m:.3f}  max_n={max_n}")

        spacing_ok = props.n_planets in valid_n_pl
        row2 = box.row()
        row2.alert = not spacing_ok
        row2.label(text="n_planets: OK" if spacing_ok else
                   f"n_planets={props.n_planets} invalid -- pick a button above")

        # -- Action buttons --
        layout.separator()
        row = layout.row(align=True)
        row.operator("planets.generate", text="Generate")
        row.operator("planets.clear",    text="Clear All")

        # -- Animation --
        layout.separator()
        box = layout.box()
        box.label(text="Animation")
        box.prop(props, "anim_speed")
        try:
            N      = _loop_cone_revs(props.T_sun, props.T_planet, T_ring)
            frames = int(N * 360.0 / props.anim_speed)
            row    = box.row()
            row.enabled = False
            row.label(text=f"Loop: {frames} frames  ({N} cone rev)")
        except Exception:
            pass
        box.operator("planets.animate", text="Animate")


# ============================================================
# Registration
# ============================================================

_classes = [
    PlanetsProperties,
    PLANETS_OT_clear,
    PLANETS_OT_generate,
    PLANETS_OT_animate,
    PLANETS_OT_set_T_planet,
    PLANETS_OT_set_n_planets,
    PLANETS_PT_main,
]

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.planets_props = bpy.props.PointerProperty(type=PlanetsProperties)
    v = bl_info["version"]
    print(f"-- Planets v{v[0]}.{v[1]}.{v[2]} registered --")

def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.planets_props

if __name__ == "__main__":
    register()
