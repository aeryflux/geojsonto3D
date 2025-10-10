import bpy
import json
import math
import bmesh
import sys
import os
from mathutils import Vector
from pathlib import Path

# --- CONFIGURATION (can be overridden by CLI arguments) ----------------------
# Get project root directory (parent of src/)
PROJECT_ROOT = Path(bpy.path.abspath("//")).parent if "//" in bpy.path.abspath("//") else Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RES_DIR = PROJECT_ROOT / "res"

# Ensure res directory exists
RES_DIR.mkdir(exist_ok=True)

# Default values
GEOJSON_COUNTRIES = str(DATA_DIR / "ne_50m_admin_0_countries.geojson")
GEOJSON_PLACES = str(DATA_DIR / "ne_50m_populated_places.json")

RADIUS = 1.0
ICO_SUBDIV = 5
MAX_COUNTRIES = None  # None = process all countries

# Radial extrusion (countries & cities)
EXTRUDE_ABOVE_COUNTRY = 0.05
EXTRUDE_BELOW_COUNTRY = 0.05
EXTRUDE_ABOVE_CITY = EXTRUDE_ABOVE_COUNTRY
EXTRUDE_BELOW_CITY = EXTRUDE_BELOW_COUNTRY

# Borders (placed on top face)
BORDER_WIDTH = 0.0005
BORDER_HEIGHT = 0.0025
BORDER_ZFIGHT_EPS = 0.00005  # Small radial offset to prevent z-fighting

# Cities (if enabled)
SHRINK = 0.4

# Feature toggles
ENABLE_CITIES = False
ENABLE_COUNTRY_BORDERS = True
ENABLE_CITY_BORDERS = False

PARENT_NAME = "Atlas"

# --- Parse CLI arguments (if provided) ---------------------------------------
if "--" in sys.argv:
    args_start = sys.argv.index("--") + 1
    args = sys.argv[args_start:]

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--ico-subdiv" and i + 1 < len(args):
            ICO_SUBDIV = int(args[i + 1])
            i += 2
        elif arg == "--extrude-above" and i + 1 < len(args):
            EXTRUDE_ABOVE_COUNTRY = float(args[i + 1])
            EXTRUDE_ABOVE_CITY = EXTRUDE_ABOVE_COUNTRY
            i += 2
        elif arg == "--extrude-below" and i + 1 < len(args):
            EXTRUDE_BELOW_COUNTRY = float(args[i + 1])
            EXTRUDE_BELOW_CITY = EXTRUDE_BELOW_COUNTRY
            i += 2
        elif arg == "--border-width" and i + 1 < len(args):
            BORDER_WIDTH = float(args[i + 1])
            i += 2
        elif arg == "--border-height" and i + 1 < len(args):
            BORDER_HEIGHT = float(args[i + 1])
            i += 2
        elif arg == "--enable-borders":
            ENABLE_COUNTRY_BORDERS = True
            i += 1
        elif arg == "--disable-borders":
            ENABLE_COUNTRY_BORDERS = False
            i += 1
        elif arg == "--enable-cities":
            ENABLE_CITIES = True
            i += 1
        elif arg == "--disable-cities":
            ENABLE_CITIES = False
            i += 1
        else:
            i += 1

# Output file path in res/ directory
OUT_GLB = str(RES_DIR / f"atlas_ico_subdiv_{ICO_SUBDIV}.glb")


# --- UTILITY FUNCTIONS -------------------------------------------------------
def xyz_to_latlon(v):
    """Convert 3D Cartesian coordinates to latitude/longitude in degrees."""
    r = v.length
    return math.degrees(math.asin(v.z/r)), math.degrees(math.atan2(v.y, v.x))


def point_in_poly(lon, lat, poly):
    """Ray-casting algorithm to test if a point is inside a polygon."""
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i+1) % len(poly)]
        if ((y1 > lat) != (y2 > lat)) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def select_hierarchy(obj):
    """Recursively select an object and all its children."""
    obj.select_set(True)
    for c in obj.children:
        select_hierarchy(c)


def new_mesh_object(name, verts, faces, parent=None, smooth=True):
    """Create a new mesh object from vertices and faces."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    if smooth:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()
    if parent:
        obj.parent = parent
    return obj


def extrude_mesh_radially_bi(obj, depth_above, depth_below):
    """
    Bidirectional radial extrusion.
    Extrudes mesh outward (above) and inward (below) relative to sphere center.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    # Extrude outward (up/above)
    res_up = bmesh.ops.extrude_face_region(bm, geom=bm.faces)
    verts_up = [v for v in res_up["geom"] if isinstance(v, bmesh.types.BMVert)]
    for v in verts_up:
        v.co += v.co.normalized() * depth_above

    # Extrude inward (down/below)
    res_down = bmesh.ops.extrude_face_region(bm, geom=bm.faces)
    verts_down = [v for v in res_down["geom"] if isinstance(v, bmesh.types.BMVert)]
    for v in verts_down:
        v.co -= v.co.normalized() * depth_below

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def create_border_ribbons_from_planar_source_on_top(source_obj, above, name_prefix, parent,
                                                    width=BORDER_WIDTH, height=BORDER_HEIGHT,
                                                    zfight_eps=BORDER_ZFIGHT_EPS):
    """
    Generate 3D border ribbons on top surface only.

    Process:
    - Read boundary edges from source mesh (pre-extrusion surface)
    - Project edges radially to 'above' height (top face)
    - Build ribbon geometry (ring + cap) with radial extrusion for height
    - No border on bottom since we only use original surface
    """
    bm = bmesh.new()
    bm.from_mesh(source_obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Find boundary edges (country contour)
    boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]

    bm_out = bmesh.new()

    for e in boundary_edges:
        v1o = e.verts[0].co.copy()
        v2o = e.verts[1].co.copy()

        # Project vertices to top height = base + above
        v1_top = v1o.normalized() * (v1o.length + above + zfight_eps)
        v2_top = v2o.normalized() * (v2o.length + above + zfight_eps)

        # Edge direction on top surface
        edge_dir = (v2_top - v1_top).normalized()

        # Perpendicular tangent in local tangent plane (via cross product with radial)
        perp1 = v1_top.normalized().cross(edge_dir).normalized()
        perp2 = v2_top.normalized().cross(edge_dir).normalized()

        # Ring quad (annular base)
        v1a = v1_top + perp1 * (width / 2)
        v1b = v1_top - perp1 * (width / 2)
        v2a = v2_top + perp2 * (width / 2)
        v2b = v2_top - perp2 * (width / 2)

        ring = [v1a, v2a, v2b, v1b]

        # Top cap of ribbon: radial extrusion of ring
        top = [p + p.normalized() * height for p in ring]

        verts_all = ring + top
        verts_new = [bm_out.verts.new(co) for co in verts_all]

        # Faces: 4 walls + top cap (bottom left open to remain ribbon-like)
        faces_idx = [
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
            (4, 5, 6, 7),  # top cap
        ]
        for idx in faces_idx:
            try:
                bm_out.faces.new([verts_new[i] for i in idx])
            except ValueError:
                pass

    bm_out.normal_update()
    me = bpy.data.meshes.new(f"{name_prefix}_{source_obj.name}")
    bm_out.to_mesh(me)
    bm_out.free()
    bm.free()

    ob = bpy.data.objects.new(f"{name_prefix}_{source_obj.name}", me)
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.shade_smooth()
    return ob


# --- LOAD GEOJSON DATA -------------------------------------------------------
with open(GEOJSON_COUNTRIES, encoding='utf-8') as f:
    gj = json.load(f)

features = []
for feat in gj.get("features", [])[:MAX_COUNTRIES]:
    name = feat["properties"]["ADMIN"]
    geom = feat.get("geometry", {})
    if not geom:
        continue
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for idx, poly in enumerate(polys):
        rings = []
        for ring in poly:
            pts = [(lon, lat) for lon, lat in ring if isinstance(lon, (int, float))]
            if len(pts) >= 3:
                rings.append(pts)
        if not rings:
            continue
        outer = rings[0]
        bbox = (min(x for x, y in outer), max(x for x, y in outer),
                min(y for x, y in outer), max(y for x, y in outer))
        features.append({"name": f"{name}_{idx}", "rings": rings, "bbox": bbox})

# --- SCENE SETUP -------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
parent = bpy.data.objects.new(PARENT_NAME, None)
bpy.context.collection.objects.link(parent)

bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=ICO_SUBDIV, radius=RADIUS - 1e-4)
core = bpy.context.object
core.name = "GlobeCore"
core.parent = parent
bpy.ops.object.shade_smooth()
mesh_sphere = core.data

# Assign faces to countries
faces_by_country = {feat["name"]: [] for feat in features}
used_faces = set()
for poly in mesh_sphere.polygons:
    cent = sum((mesh_sphere.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
    lat, lon = xyz_to_latlon(cent)
    for feat in features:
        minx, maxx, miny, maxy = feat["bbox"]
        if not (minx <= lon <= maxx and miny <= lat <= maxy):
            continue
        if point_in_poly(lon, lat, feat["rings"][0]):
            faces_by_country[feat["name"]].append(poly.index)
            used_faces.add(poly.index)
            break


def create_surface(name, fids):
    """Create a mesh surface from face indices."""
    cmap, verts, faces = {}, [], []
    for fid in fids:
        poly = mesh_sphere.polygons[fid]
        idxs = []
        for vid in poly.vertices:
            co = mesh_sphere.vertices[vid].co.copy()
            key = (round(co.x, 5), round(co.y, 5), round(co.z, 5))
            if key not in cmap:
                cmap[key] = len(verts)
                verts.append(co)
            idxs.append(cmap[key])
        faces.append(idxs)
    return new_mesh_object(name, verts, faces, parent=parent, smooth=True)


# Ocean (GlobeFill) = all faces not assigned to countries
all_faces = set(range(len(mesh_sphere.polygons)))
ocean = create_surface("GlobeFill", list(all_faces - used_faces))
bpy.data.objects.remove(core, do_unlink=True)

# --- COUNTRIES ---------------------------------------------------------------
country_objs = []
for name, fids in faces_by_country.items():
    if not fids:
        continue

    # 1) Create original surface (source for top borders)
    surf = create_surface(f"country_{name}", fids)

    # 2) Generate borders on top surface (by projecting original surface to +above)
    if ENABLE_COUNTRY_BORDERS:
        create_border_ribbons_from_planar_source_on_top(
            surf, EXTRUDE_ABOVE_COUNTRY, "border", parent,
            width=BORDER_WIDTH, height=BORDER_HEIGHT, zfight_eps=BORDER_ZFIGHT_EPS
        )

    # 3) Extrude country (up + down) without affecting borders
    extrude_mesh_radially_bi(surf, EXTRUDE_ABOVE_COUNTRY, EXTRUDE_BELOW_COUNTRY)

    country_objs.append(surf)

# --- CITIES (OPTIONAL) -------------------------------------------------------
# Same principle if needed: generate city borders at +EXTRUDE_ABOVE_CITY,
# then extrude city tiles. (Disabled by default)

# --- EXPORT ------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
select_hierarchy(parent)
bpy.context.view_layer.objects.active = parent

print(f"Exporting to: {OUT_GLB}")

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    use_selection=True,
    export_apply=True
)

print(f"Export complete: {OUT_GLB}")
