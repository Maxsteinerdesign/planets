bl_info = {
    "name":        "Planets",
    "author":      "Max Steiner",
    "version":     (0, 4, 0),
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
    cone_radius     : FloatProperty(name="Mouth Radius",    default=50.0,  min=5.0,   max=500.0,
                                    description="Radius at the wide/top opening of the cone")
    cone_height     : FloatProperty(name="Cone Height",     default=100.0, min=5.0,   max=1000.0,
                                    description="Height of the frustum (mouth to truncated bottom)")
    gear_width      : FloatProperty(name="Gear Height",     default=20.0,  min=1.0,   max=200.0,
                                    description="Height (thickness) of the planetary gear disk")
    wall_thickness  : FloatProperty(name="Wall Thickness",  default=3.0,   min=0.5,   max=40.0,
                                    description="Gap from ring gear teeth tips to cone wall (mm)")
    n_planets       : IntProperty  (name="# Planets",       default=3,     min=2,     max=8)
    T_sun           : IntProperty  (name="Sun Teeth",       default=12,    min=6,     max=60)
    T_planet        : IntProperty  (name="Planet Teeth",    default=12,    min=6,     max=60)
    tooth_clearance : FloatProperty(name="Tooth Clearance", default=0.05,  min=0.0,   max=0.30,
                                    step=1,
                                    description="Angular fraction of pitch left as gap between meshing teeth")
    anim_speed      : FloatProperty(name="Speed (deg/frame)", default=2.0, min=0.1,   max=30.0)


# ============================================================
# Gear profile helpers
# ============================================================

def _spur_pts(T, m, clearance=0.05):
    ra    = (T / 2.0 + 1.0) * m
    rp    =  T / 2.0        * m
    rf    = max((T / 2.0 - 1.25) * m, rp * 0.4)
    pitch = 2.0 * math.pi / T
    ht    = pitch * (0.5 - clearance)
    pts   = []
    for i in range(T):
        a = i * pitch
        for da, r in [(-ht*0.90, rf), (-ht*0.55, rp), (-ht*0.22, ra),
                      ( ht*0.22, ra), ( ht*0.55, rp), ( ht*0.90, rf)]:
            pts.append((r * math.cos(a + da), r * math.sin(a + da)))
    return pts


def _ring_inner_pts(T, m, clearance=0.05):
    rp    =  T / 2.0         * m
    ra    = (T / 2.0 - 1.0)  * m
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


def _make_solid_frustum(r_top, r_bottom, height, segments=96):
    mesh = bpy.data.meshes.new(PREFIX + "BevelGear_Mesh")
    bm   = bmesh.new()
    bmesh.ops.create_cone(bm,
        cap_ends=True, cap_tris=False, segments=segments,
        radius1=r_bottom, radius2=r_top, depth=height)
    for v in bm.verts:
        v.co.z -= height / 2.0
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


def _make_bevel_gear(name, pts_top, pts_bot, gw, color, location):
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
    bpy.ops.object.select_all(action='DESELECT')
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            obj.select_set(True)
    bpy.ops.object.delete()
    for m in list(bpy.data.meshes):
        if m.name.startswith(PREFIX) and m.users == 0:
            bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        if m.name.startswith(PREFIX) and m.users == 0:
            bpy.data.materials.remove(m)


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
        props     = context.scene.planets_props
        cone_r    = props.cone_radius
        cone_h    = props.cone_height
        gw        = props.gear_width
        n_pl      = props.n_planets
        T_sun     = props.T_sun
        T_planet  = props.T_planet
        T_ring    = T_sun + 2 * T_planet
        clearance = props.tooth_clearance

        r_bottom = cone_r / 4.0
        z_bot    = -gw
        z_disk   = -gw / 2.0

        # Module: ring outer radius = (T_ring/2 + 1.25)*m, gap = wall_thickness
        min_cone_r = _cone_r_at(cone_r, cone_h, z_bot)
        wall       = props.wall_thickness
        m = max(0.001, (min_cone_r - wall) / (T_ring / 2.0 + 1.25))

        r_sun    = T_sun    * m / 2.0
        r_planet = T_planet * m / 2.0
        orbit_r  = r_sun + r_planet

        full_h       = cone_h * 4.0 / 3.0
        s_bot        = (full_h - gw) / full_h
        m_bot_planet = m * s_bot
        m_bot_sun    = m * (T_sun + T_planet * (1.0 - s_bot)) / T_sun

        alphas  = [2.0 * math.pi * i / n_pl for i in range(n_pl)]
        th_pl   = [_planet_rotation(a, T_sun, T_planet, m) for a in alphas]
        th_ring = _ring_rotation(alphas[0], th_pl[0], T_planet, T_ring, m)

        _clear_pl_objects()

        # 1. Solid frustum
        cone_obj = _make_solid_frustum(cone_r, r_bottom, cone_h)
        _assign_color(cone_obj, (0.45, 0.45, 0.48, 1.0))

        # 2. Boolean-cut ring gear void
        ring_top = _rotate_pts(_ring_inner_pts(T_ring, m,         clearance=0.0), th_ring)
        ring_bot = _rotate_pts(_ring_inner_pts(T_ring, m * s_bot, clearance=0.0), th_ring)
        void_obj = _connect_profiles("VOID_Ring", ring_top, ring_bot, 0.2, z_bot - 0.2)

        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = cone_obj
        cone_obj.select_set(True)
        mod           = cone_obj.modifiers.new("RingCut", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object    = void_obj
        mod.solver    = 'EXACT'
        bpy.ops.object.modifier_apply(modifier="RingCut")
        bpy.data.objects.remove(void_obj, do_unlink=True)

        # 3. Sun gear (opposite bevel: larger at bottom)
        _make_bevel_gear("SunGear",
            _spur_pts(T_sun, m,         clearance),
            _spur_pts(T_sun, m_bot_sun, clearance),
            gw, (0.9, 0.78, 0.05, 1.0), Vector((0.0, 0.0, z_disk)))

        # 4. Planet gears (same bevel as cone: larger at top)
        for i in range(n_pl):
            _make_bevel_gear(f"Planet_{i:02d}",
                _rotate_pts(_spur_pts(T_planet, m,            clearance), th_pl[i]),
                _rotate_pts(_spur_pts(T_planet, m_bot_planet, clearance), th_pl[i]),
                gw, (0.15, 0.55, 0.85, 1.0),
                Vector((orbit_r * math.cos(alphas[i]),
                        orbit_r * math.sin(alphas[i]), z_disk)))

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

        cone_r     = props.cone_radius
        cone_h     = props.cone_height
        gw         = props.gear_width
        min_cone_r = _cone_r_at(cone_r, cone_h, -gw)
        wall       = props.wall_thickness
        m          = max(0.001, (min_cone_r - wall) / (T_ring / 2.0 + 1.25))
        orbit_r    = (T_sun + T_planet) * m / 2.0
        z_disk     = -gw / 2.0
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
                    orbit_r * math.cos(orbit_angle),
                    orbit_r * math.sin(orbit_angle),
                    z_disk))
                spin = frac * N_cone * 2.0 * math.pi * ratio_pl_world
                q_pl = Quaternion((0.0, 0.0, 1.0), spin)
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
        col.prop(props, "cone_radius")
        col.prop(props, "cone_height")
        row = box.row()
        row.enabled = False
        row.label(text=f"Bottom Radius: {props.cone_radius / 4.0:.1f}  (truncated 1/4)")

        # -- Planetary Zone --
        box = layout.box()
        box.label(text="Planetary Zone")
        col = box.column(align=True)
        col.prop(props, "gear_width")
        col.prop(props, "wall_thickness")
        row = box.row()
        row.enabled = False
        row.label(text=f"Z: 0.0 -> {-props.gear_width:.1f}  (flush with mouth)")

        # -- Gear Counts --
        T_ring     = props.T_sun + 2 * props.T_planet
        min_cone_r = _cone_r_at(props.cone_radius, props.cone_height, -props.gear_width)
        m          = max(0.001, (min_cone_r - props.wall_thickness) / (T_ring / 2.0 + 1.25))
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

def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.planets_props

if __name__ == "__main__":
    register()
