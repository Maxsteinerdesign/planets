bl_info = {
    "name":        "Planets",
    "author":      "Max Steiner",
    "version":     (0, 1, 0),
    "blender":     (5, 0, 0),
    "location":    "View3D > Sidebar > Planets",
    "description": "Planets — planetary gear development sandbox",
    "category":    "Object",
}

import bpy
import bmesh
import math
from mathutils import Vector, Matrix
from bpy.props import FloatProperty, IntProperty, BoolProperty, EnumProperty, StringProperty

# ============================================================
# Constants
# ============================================================

PREFIX       = "PL_"
PLANET_DEPTH = 0.25   # planetary disk sits 1/4 of the way down from the cone top


# ============================================================
# Properties
# ============================================================

class PlanetsProperties(bpy.types.PropertyGroup):
    # Bevel gear cone
    cone_radius: FloatProperty(name="Cone Radius",  default=5.0,  min=1.0,  max=50.0)
    cone_height: FloatProperty(name="Cone Height",  default=8.0,  min=1.0,  max=80.0)
    gear_width:  FloatProperty(name="Gear Width",   default=1.5,  min=0.2,  max=10.0,
                               description="Thickness of the planetary gear disk")

    # Planetary gear counts
    n_planets:   IntProperty (name="# Planets",     default=3,    min=2,    max=8)
    T_sun:       IntProperty (name="Sun Teeth",     default=12,   min=6,    max=60)
    T_planet:    IntProperty (name="Planet Teeth",  default=12,   min=6,    max=60)

    # Computed / display
    show_info:   BoolProperty(name="Show Info",     default=True)


# ============================================================
# Geometry helpers
# ============================================================

def _clear_pl_objects():
    """Remove all PL_ objects from the scene."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            obj.select_set(True)
    bpy.ops.object.delete()


def _link(obj):
    if obj.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def _make_cone(cone_r, cone_h, segments=64):
    """Cone: wide face at Z=0, tip at Z=-cone_h."""
    mesh = bpy.data.meshes.new(PREFIX + "BevelGear_Mesh")
    bm   = bmesh.new()
    bmesh.ops.create_cone(bm,
        cap_ends=True, cap_tris=False,
        segments=segments,
        radius1=cone_r,   # base (Z=0, wide end / gear face)
        radius2=0.01,     # tip  (Z=-cone_h)
        depth=cone_h)
    # bmesh cone is centered; shift so base is at Z=0, tip at Z=-cone_h
    for v in bm.verts:
        v.co.z += cone_h / 2.0
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(PREFIX + "BevelGear", mesh)
    _link(obj)
    # wire display so we can see inside
    obj.display_type = 'WIRE'
    return obj


def _cone_radius_at(cone_r, cone_h, z):
    """Radius of the cone at height z (z=0 → cone_r, z=-cone_h → 0)."""
    t = (cone_h + z) / cone_h   # 1 at top, 0 at tip
    return cone_r * t


def _make_cylinder(radius, depth, location, name, segments=32, wire=False):
    mesh = bpy.data.meshes.new(PREFIX + name + "_Mesh")
    bm   = bmesh.new()
    bmesh.ops.create_cone(bm,
        cap_ends=True, cap_tris=False,
        segments=segments,
        radius1=radius, radius2=radius,
        depth=depth)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(PREFIX + name, mesh)
    obj.location = location
    _link(obj)
    if wire:
        obj.display_type = 'WIRE'
    return obj


def _make_ring_cylinder(r_inner, r_outer, depth, location, name, segments=64):
    """Hollow cylinder (ring gear placeholder)."""
    mesh = bpy.data.meshes.new(PREFIX + name + "_Mesh")
    bm   = bmesh.new()
    # outer wall
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=r_outer, radius2=r_outer, depth=depth)
    # inner cut — subtract inner cylinder
    bm2 = bmesh.new()
    bmesh.ops.create_cone(bm2, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=r_inner, radius2=r_inner, depth=depth + 0.01)
    # For a placeholder, just use solid outer cylinder with wire display
    bm.free(); bm2.free()
    # Simple solid outer for now
    bm3 = bmesh.new()
    bmesh.ops.create_cone(bm3, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=r_outer, radius2=r_outer, depth=depth)
    bm3.to_mesh(mesh)
    bm3.free()
    obj = bpy.data.objects.new(PREFIX + name, mesh)
    obj.location = location
    _link(obj)
    obj.display_type = 'WIRE'
    return obj


def _assign_color(obj, color_rgba):
    mat = bpy.data.materials.new(obj.name + "_Mat")
    mat.use_nodes = False
    mat.diffuse_color = color_rgba
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ============================================================
# Operator — Generate
# ============================================================

class PLANETS_OT_generate(bpy.types.Operator):
    bl_idname  = "planets.generate"
    bl_label   = "Generate"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props   = context.scene.planets_props
        cone_r  = props.cone_radius
        cone_h  = props.cone_height
        gw      = props.gear_width
        n_pl    = props.n_planets
        T_sun   = props.T_sun
        T_planet= props.T_planet
        T_ring  = T_sun + 2 * T_planet

        # ── Planetary disk sits 1/4 of the way down from the top ──
        z_disk  = -(cone_h * PLANET_DEPTH)          # e.g. -2.0 for height=8
        avail_r = _cone_radius_at(cone_r, cone_h, z_disk) * 0.90  # 90% of cone r at that level

        # ── Module: scale so ring gear fits inside available radius ──
        # Ring gear pitch radius = T_ring * m / 2
        # Ring gear outer radius (addendum) ≈ (T_ring/2 + 1) * m
        # We want ring outer ≤ avail_r  →  m ≤ avail_r / (T_ring/2 + 1)
        m = avail_r / (T_ring / 2.0 + 1.0)

        # Pitch radii
        r_sun    = T_sun    * m / 2.0
        r_planet = T_planet * m / 2.0
        r_ring   = T_ring   * m / 2.0    # = r_sun + 2*r_planet

        # Addendum / dedendum
        r_sun_outer  = r_sun    + m
        r_planet_out = r_planet + m
        r_ring_inner = r_ring   - m      # ring gear inner wall (tooth tips reach here)
        r_ring_outer = r_ring   + m      # ring gear outer wall

        # Planet orbit center distance from origin
        orbit_r = r_sun + r_planet

        # ── Clear previous ──
        _clear_pl_objects()

        # ── Cone (bevel gear placeholder) ──
        cone_obj = _make_cone(cone_r, cone_h)
        _assign_color(cone_obj, (0.4, 0.4, 0.45, 1.0))

        # ── Ring gear ──
        ring_loc = Vector((0.0, 0.0, z_disk))
        ring_obj = _make_ring_cylinder(r_ring_inner, r_ring_outer, gw, ring_loc, "RingGear")
        _assign_color(ring_obj, (0.7, 0.3, 0.1, 1.0))   # orange

        # ── Sun gear ──
        sun_loc  = Vector((0.0, 0.0, z_disk))
        sun_obj  = _make_cylinder(r_sun_outer, gw, sun_loc, "SunGear")
        _assign_color(sun_obj, (0.9, 0.8, 0.1, 1.0))    # yellow

        # ── Planet gears ──
        for i in range(n_pl):
            angle = 2.0 * math.pi * i / n_pl
            px    = orbit_r * math.cos(angle)
            py    = orbit_r * math.sin(angle)
            pl_loc= Vector((px, py, z_disk))
            pl_obj= _make_cylinder(r_planet_out, gw, pl_loc, f"Planet_{i:02d}")
            _assign_color(pl_obj, (0.2, 0.6, 0.9, 1.0)) # blue

        # ── Info to console ──
        print(f"\n── Planets: generated planetary layout ──")
        print(f"  Cone:       r={cone_r:.2f}  h={cone_h:.2f}")
        print(f"  Disk at:    Z={z_disk:.2f}  (avail_r={avail_r:.2f})")
        print(f"  Module:     m={m:.4f}")
        print(f"  T_sun/planet/ring: {T_sun}/{T_planet}/{T_ring}")
        print(f"  r_sun={r_sun:.3f}  r_planet={r_planet:.3f}  r_ring={r_ring:.3f}")
        print(f"  Planet orbit: {orbit_r:.3f}")
        print(f"  Ring outer:   {r_ring_outer:.3f}  (avail={avail_r:.2f})")
        print(f"  Planets: {n_pl}  spacing check: {(T_sun+T_ring)} / {n_pl} = {(T_sun+T_ring)/n_pl:.2f} (must be integer)")

        self.report({'INFO'}, f"T_ring={T_ring}  m={m:.4f}  ring_outer={r_ring_outer:.3f}")
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

        # ── Bevel gear cone ──
        box = layout.box()
        box.label(text="Bevel Gear (Placeholder)")
        col = box.column(align=True)
        col.prop(props, "cone_radius")
        col.prop(props, "cone_height")
        col.prop(props, "gear_width")

        # ── Planetary system ──
        box = layout.box()
        box.label(text="Planetary System")
        col = box.column(align=True)
        col.prop(props, "n_planets")
        col.prop(props, "T_sun")
        col.prop(props, "T_planet")
        T_ring = props.T_sun + 2 * props.T_planet
        row = box.row()
        row.enabled = False
        row.label(text=f"Ring Teeth: {T_ring}")

        # Spacing validity check
        spacing_ok = (props.T_sun + T_ring) % props.n_planets == 0
        row2 = box.row()
        row2.alert = not spacing_ok
        row2.label(text="Planet spacing: OK" if spacing_ok else
                   f"Planet spacing: {props.T_sun + T_ring} not divisible by {props.n_planets}")

        layout.separator()
        layout.operator("planets.generate", text="Generate")


# ============================================================
# Registration
# ============================================================

_classes = [
    PlanetsProperties,
    PLANETS_OT_generate,
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
