import bpy
import json
import math
import bmesh
from mathutils import Vector
from datetime import datetime

# --- PARAMÈTRES --------------------------------------------------------------
GEOJSON_COUNTRIES = bpy.path.abspath("//ne_50m_admin_0_countries.geojson")
GEOJSON_PLACES    = bpy.path.abspath("//ne_50m_populated_places.json")

RADIUS            = 1.0
ICO_SUBDIV        = 5
MAX_COUNTRIES     = None
MAX_CITIES        = None

# Extrusions radiales (haut/bas)
EXTRUDE_ABOVE_COUNTRY = 0.05
EXTRUDE_BELOW_COUNTRY = 0.05
EXTRUDE_ABOVE_CITY    = 0.02
EXTRUDE_BELOW_CITY    = 0.01
CITY_ELEVATION_OFFSET = 0.002

# Bordures (rubans posés sur la face AVANT uniquement)
BORDER_WIDTH      = 0.0006
BORDER_HEIGHT     = 0.0025
BORDER_ZFIGHT_EPS = 0.00008

# “Taille” des villes (réduction de la face support)
SHRINK            = 0.4

# Orientation
INVERT_POLES      = True  # ⇐ active inversion du globe (Antarctique en bas)

# Toggles
ENABLE_COUNTRIES        = True
ENABLE_CITIES           = False
ENABLE_COUNTRY_BORDERS  = False
ENABLE_CITY_BORDERS     = False

PARENT_NAME = "Atlas"
OUT_GLB     = bpy.path.abspath(f"//atlas_ico_subdiv_{ICO_SUBDIV}.glb")
OUT_CFG     = bpy.path.abspath(f"//atlas_ico_subdiv_{ICO_SUBDIV}.config.json")

# --- FONCTIONS UTILES --------------------------------------------------------
def xyz_to_latlon(v):
    r = max(v.length, 1e-12)
    lat = math.degrees(math.asin(v.z / r))
    lon = math.degrees(math.atan2(v.y, v.x))
    return lat, lon

def point_in_poly(lon, lat, poly):
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if ((y1 > lat) != (y2 > lat)) and lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-12) + x1:
            inside = not inside
    return inside

def select_hierarchy(obj):
    obj.select_set(True)
    for c in obj.children:
        select_hierarchy(c)

def new_mesh_object(name, verts, faces, parent=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    if parent:
        obj.parent = parent
    if smooth:
        try:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.shade_smooth()
        except Exception:
            pass
    return obj

def create_surface_from_face_ids(base_mesh, fids, name, parent):
    cmap, verts, faces = {}, [], []
    for fid in fids:
        poly = base_mesh.polygons[fid]
        idxs = []
        for vid in poly.vertices:
            co = base_mesh.vertices[vid].co.copy()
            key = (round(co.x, 6), round(co.y, 6), round(co.z, 6))
            if key not in cmap:
                cmap[key] = len(verts)
                verts.append(co)
            idxs.append(cmap[key])
        if len(idxs) >= 3:
            faces.append(idxs)
    return new_mesh_object(name, verts, faces, parent=parent, smooth=True)

def extrude_mesh_radially_bi(obj, depth_above, depth_below):
    if depth_above == 0 and depth_below == 0:
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    if depth_above > 0:
        res_up = bmesh.ops.extrude_face_region(bm, geom=bm.faces)
        verts_up = [v for v in res_up["geom"] if isinstance(v, bmesh.types.BMVert)]
        for v in verts_up:
            v.co += v.co.normalized() * depth_above

    if depth_below > 0:
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
    bm = bmesh.new()
    bm.from_mesh(source_obj.data)
    bm.edges.ensure_lookup_table()
    boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if not boundary_edges:
        bm.free()
        return None

    bm_out = bmesh.new()
    for e in boundary_edges:
        v1o = e.verts[0].co.copy()
        v2o = e.verts[1].co.copy()
        v1_top = v1o.normalized() * (v1o.length + above + zfight_eps)
        v2_top = v2o.normalized() * (v2o.length + above + zfight_eps)
        edge_dir = (v2_top - v1_top).normalized()
        perp1 = v1_top.normalized().cross(edge_dir).normalized()
        perp2 = v2_top.normalized().cross(edge_dir).normalized()
        v1a = v1_top + perp1 * (width / 2.0)
        v1b = v1_top - perp1 * (width / 2.0)
        v2a = v2_top + perp2 * (width / 2.0)
        v2b = v2_top - perp2 * (width / 2.0)
        ring = [v1a, v2a, v2b, v1b]
        top = [p + p.normalized() * height for p in ring]
        verts_all = ring + top
        verts_new = [bm_out.verts.new(co) for co in verts_all]
        faces_idx = [
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
            (4, 5, 6, 7),
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
    try:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return ob

# --- LECTURE GEOJSON PAYS ----------------------------------------------------
with open(GEOJSON_COUNTRIES, encoding='utf-8') as f:
    gj = json.load(f)

features = []
for feat in gj.get("features", [])[:MAX_COUNTRIES]:
    name = feat["properties"].get("ADMIN") or feat["properties"].get("NAME") or "Unknown"
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
        if rings:
            outer = rings[0]
            bbox = (
                min(x for x, y in outer), max(x for x, y in outer),
                min(y for x, y in outer), max(y for x, y in outer)
            )
            features.append({"name": f"{name}_{idx}", "rings": rings, "bbox": bbox})

# --- LECTURE GEOJSON VILLES --------------------------------------------------
with open(GEOJSON_PLACES, encoding='utf-8') as f:
    gjp = json.load(f)
places = []
for feat in gjp.get('features', [])[:MAX_CITIES or 10**9]:
    props = feat.get('properties', {})
    lat, lon = props.get('LATITUDE'), props.get('LONGITUDE')
    if lat is None or lon is None:
        geom = feat.get("geometry", {})
        if geom and geom.get("type") == "Point":
            lon2, lat2 = geom.get("coordinates", [None, None])
            lon = lon if lon is not None else lon2
            lat = lat if lat is not None else lat2
    if lat is None or lon is None:
        continue
    name = (props.get('NAME_EN') or props.get('NAME') or "City").replace("/", "-")
    places.append({'name': name, 'lat': float(lat), 'lon': float(lon)})

# --- SCÈNE -------------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
parent = bpy.data.objects.new(PARENT_NAME, None)
bpy.context.collection.objects.link(parent)

# --- ICOSPHÈRE ---------------------------------------------------------------
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=ICO_SUBDIV, radius=RADIUS - 1e-4)
core = bpy.context.object
core.name = "GlobeCore"
core.parent = parent
bpy.ops.object.shade_smooth()
mesh_sphere = core.data

# ⇩⇩⇩ INVERSION DU GLOBE (Nord en haut) ⇩⇩⇩
if INVERT_POLES:
    for v in mesh_sphere.vertices:
        v.co.z *= -1
# ⇧⇧⇧ ⇧⇧⇧ ⇧⇧⇧ ⇧⇧⇧ ⇧⇧⇧

# --- ASSIGNATION DES FACES ---------------------------------------------------
faces_by_country = {feat["name"]: [] for feat in features}
used_faces = set()
for poly in mesh_sphere.polygons:
    cent = sum((mesh_sphere.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
    lat, lon = xyz_to_latlon(cent)
    for feat in features:
        minx, maxx, miny, maxy = feat["bbox"]
        if lon < minx or lon > maxx or lat < miny or lat > maxy:
            continue
        if point_in_poly(lon, lat, feat["rings"][0]):
            faces_by_country[feat["name"]].append(poly.index)
            used_faces.add(poly.index)
            break

# --- GLOBEFILL ---------------------------------------------------------------
all_faces = set(range(len(mesh_sphere.polygons)))
ocean = create_surface_from_face_ids(mesh_sphere, list(all_faces - used_faces), "GlobeFill", parent)
bpy.data.objects.remove(core, do_unlink=True)

# --- PAYS & VILLES -----------------------------------------------------------
countries_data, cities_data = [], []

if ENABLE_COUNTRIES:
    for name, fids in faces_by_country.items():
        if not fids:
            continue
        surf = create_surface_from_face_ids(mesh_sphere, fids, f"country_{name}", parent)
        if ENABLE_COUNTRY_BORDERS:
            create_border_ribbons_from_planar_source_on_top(
                surf, EXTRUDE_ABOVE_COUNTRY, "border", parent,
                width=BORDER_WIDTH, height=BORDER_HEIGHT, zfight_eps=BORDER_ZFIGHT_EPS
            )
        extrude_mesh_radially_bi(surf, EXTRUDE_ABOVE_COUNTRY, EXTRUDE_BELOW_COUNTRY)
        countries_data.append({"name": name, "faces": len(fids)})

if ENABLE_CITIES:
    for feat in features:
        name = feat['name']
        fids = faces_by_country.get(name, [])
        if not fids:
            continue
        cands = [p for p in places if point_in_poly(p['lon'], p['lat'], feat['rings'][0])]
        for u in cands:
            closest, dmin = None, float('inf')
            for fid in fids:
                poly = mesh_sphere.polygons[fid]
                cent = sum((mesh_sphere.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
                lat2, lon2 = xyz_to_latlon(cent)
                d = (lat2 - u['lat'])**2 + (lon2 - u['lon'])**2
                if d < dmin:
                    closest, dmin = fid, d
            if closest is None:
                continue
            poly = mesh_sphere.polygons[closest]
            base_verts_top = [mesh_sphere.vertices[v].co.normalized() *
                              (RADIUS + EXTRUDE_ABOVE_COUNTRY + CITY_ELEVATION_OFFSET)
                              for v in poly.vertices]
            cent_top = sum(base_verts_top, Vector()) / len(base_verts_top)
            verts_city = [cent_top + (v - cent_top) * SHRINK for v in base_verts_top]
            mesh_c = bpy.data.meshes.new(f"city_{u['name']}")
            mesh_c.from_pydata(verts_city, [], [list(range(len(verts_city)))])
            mesh_c.update()
            obj_c = bpy.data.objects.new(f"city_{u['name']}", mesh_c)
            bpy.context.collection.objects.link(obj_c)
            obj_c.parent = parent
            if ENABLE_CITY_BORDERS:
                create_border_ribbons_from_planar_source_on_top(
                    obj_c, EXTRUDE_ABOVE_CITY, "border_city", parent,
                    width=BORDER_WIDTH, height=BORDER_HEIGHT, zfight_eps=BORDER_ZFIGHT_EPS
                )
            extrude_mesh_radially_bi(obj_c, EXTRUDE_ABOVE_CITY, EXTRUDE_BELOW_CITY)
            cities_data.append({"name": u['name'], "lat": u['lat'], "lon": u['lon']})

# --- EXPORT ------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
select_hierarchy(parent)
bpy.context.view_layer.objects.active = parent
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB', use_selection=True)

# --- CONFIG JSON -------------------------------------------------------------
cfg = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "ico_subdiv": ICO_SUBDIV,
    "radius": RADIUS,
    "invert_poles": INVERT_POLES,
    "extrusions": {
        "country": {"above": EXTRUDE_ABOVE_COUNTRY, "below": EXTRUDE_BELOW_COUNTRY},
        "city":    {"above": EXTRUDE_ABOVE_CITY,    "below": EXTRUDE_BELOW_CITY}
    },
    "border": {"width": BORDER_WIDTH, "height": BORDER_HEIGHT, "zfight_eps": BORDER_ZFIGHT_EPS},
    "counts": {"countries": len(countries_data), "cities": len(cities_data)},
    "output": {"glb": OUT_GLB, "config": OUT_CFG}
}
with open(OUT_CFG, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)

print(f"[OK] {len(countries_data)} pays et {len(cities_data)} villes exportés.")
print(f"[GLB] → {OUT_GLB}")
print(f"[CFG] → {OUT_CFG}")
