"""
Day 19 · Smell · Izmir — terrain, sea, buildings, trees, streams and odour sources for the 3D scene and the model.

Inputs (input/, from the author's folder): Copernicus GLO-30 DSM tiles N38E026 + N38E027, OSM extract (BBBike
GeoPackage, 26.908,38.342 – 27.281,38.544, 17 Nov 2026).

Grid: EPSG:32635 (UTM 35N), 30 m model grid; outputs in build/ (numpy) and docs/data/ (web).
  python pipeline/prep.py
"""
import json, math
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
import rasterio
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from rasterio import features
from scipy import ndimage as ndi
from pyproj import Transformer

IN, B, W = Path("input"), Path("build"), Path("docs/data")
CRS = 32635
RES = 30.0
LL = (26.908, 38.342, 27.281, 38.544)
TR = Transformer.from_crs(4326, CRS, always_xy=True)
x0, y0 = TR.transform(LL[0], LL[1]); x1, y1 = TR.transform(LL[2], LL[3])
X0 = math.floor(min(x0, TR.transform(LL[0], LL[3])[0]) / 300) * 300
X1 = math.ceil(max(x1, TR.transform(LL[2], LL[1])[0]) / 300) * 300
Y0 = math.floor(min(y0, TR.transform(LL[2], LL[1])[1]) / 300) * 300
Y1 = math.ceil(max(y1, TR.transform(LL[0], LL[3])[1]) / 300) * 300
NX, NY = int((X1 - X0) / RES), int((Y1 - Y0) / RES)
T30 = from_origin(X0, Y1, RES, RES)
GPKG = str(IN / "osm.gpkg")


def read(layer, cols, where=None):
    import pyogrio
    df = pyogrio.read_dataframe(GPKG, layer=layer, columns=cols, where=where)
    return df.to_crs(CRS)


def tag(s, k):
    if not isinstance(s, str):
        return None
    i = s.find(f'"{k}"=>"')
    if i < 0:
        return None
    j = i + len(k) + 6
    return s[j:s.find('"', j)]


def main():
    B.mkdir(exist_ok=True); W.mkdir(parents=True, exist_ok=True)
    print(f"grid {NX}×{NY} at {RES:.0f} m, X {X0}–{X1}, Y {Y0}–{Y1}")
    # ---- DSM → 30 m UTM
    srcs = [rasterio.open(IN / f) for f in ("dsm_e026.tif", "dsm_e027.tif")]
    mos, mtr = merge(srcs)
    dsm = np.zeros((NY, NX), "float32")
    reproject(mos[0], dsm, src_transform=mtr, src_crs=4326, dst_transform=T30, dst_crs=CRS, resampling=Resampling.bilinear)
    # ---- sea: low and connected to the open gulf in the west
    low = dsm <= 1.2
    lab, n = ndi.label(low)
    seed = lab[NY // 2, 5] if low[NY // 2, 5] else np.bincount(lab[:, :20].ravel()).argmax()
    sizes = np.bincount(lab.ravel())
    sea = np.isin(lab, [k for k in range(1, n + 1) if sizes[k] > 20000])
    sea = ndi.binary_opening(sea, iterations=1)
    # ---- bare ground from the DSM: morphological opening removes buildings / trees (~ 150 m), then smooth
    g = np.where(sea, 0, dsm)
    ground = ndi.grey_opening(g, size=(5, 5))
    ground = ndi.gaussian_filter(ground, 1.2)
    ground = np.minimum(ground, dsm)
    ground[sea] = 0
    objh = np.clip(dsm - ground, 0, 120)
    # slope and hillshade
    gy, gx = np.gradient(ground, RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    az, alt = math.radians(315), math.radians(42)
    asp = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(np.radians(slope)) + np.cos(alt) * np.sin(np.radians(slope)) * np.cos(az - asp)
    print(f"sea {sea.mean():.1%}, ground max {ground.max():.0f} m, slope p95 {np.percentile(slope[~sea], 95):.0f}°")

    # ---- buildings
    bl = read("multipolygons", ["osm_id", "osm_way_id", "building", "name", "other_tags"], where="building IS NOT NULL")
    bl = bl[bl.geometry.notna()].explode(index_parts=False).reset_index(drop=True)
    bl["area"] = bl.geometry.area
    bl = bl[bl.area >= 12].reset_index(drop=True)
    lv = pd.to_numeric(bl.other_tags.map(lambda s: tag(s, "building:levels")), errors="coerce")
    hh = pd.to_numeric(bl.other_tags.map(lambda s: (tag(s, "height") or "").replace("m", "").strip() or None), errors="coerce")
    c = bl.geometry.representative_point()
    col = ((c.x - X0) / RES).astype(int).clip(0, NX - 1); row = ((Y1 - c.y) / RES).astype(int).clip(0, NY - 1)
    # DSM-based estimate: 75th percentile of object height in the 3×3 cells around the building
    oh_max = ndi.percentile_filter(objh, 75, size=3)
    est = oh_max[row.values, col.values]
    h = np.where(hh.notna(), hh, np.where(lv.notna(), lv * 3.1 + 1.0, np.nan))
    src = np.where(hh.notna(), "height", np.where(lv.notna(), "levels", "dsm"))
    est = np.clip(est, 3.5, 75)
    small = bl.area < 60
    h = np.where(np.isnan(h), np.where(small, np.minimum(est, 6), est), h)
    bl["h"] = np.clip(h, 2.5, 220).round(1); bl["hsrc"] = src
    bl["z"] = ground[row.values, col.values]
    print(f"buildings {len(bl):,}; height from tag {int((src == 'height').sum())}, levels {int((src == 'levels').sum())}, DSM estimate {int((src == 'dsm').sum()):,}; median {np.median(bl.h):.1f} m")
    # oriented boxes for instancing: centre, length, width, angle, height
    mrr = shapely.oriented_envelope(bl.geometry.values)
    co = shapely.get_coordinates(mrr).reshape(len(bl), -1, 2)[:, :4]
    e1 = co[:, 1] - co[:, 0]; e2 = co[:, 2] - co[:, 1]
    L1 = np.hypot(*e1.T); L2 = np.hypot(*e2.T)
    ang = np.arctan2(e1[:, 1], e1[:, 0])
    k = np.sqrt(bl.area.values / np.maximum(L1 * L2, 1))          # keep the footprint area
    cx_, cy_ = co.mean(axis=1).T
    inst = np.c_[cx_ - X0, Y1 - cy_, L1 * k, L2 * k, ang, bl.h.values, bl.z.values].astype("float32")
    inst.tofile(W / "buildings.f32")
    np.save(B / "bld_inst.npy", inst)
    # building raster for the model (fraction built, mean height) and the basemap
    bf = features.rasterize(zip(bl.geometry.values, np.ones(len(bl))), out_shape=(NY * 3, NX * 3), transform=from_origin(X0, Y1, 10, 10), dtype="uint8")
    frac = bf.reshape(NY, 3, NX, 3).mean(axis=(1, 3))
    hras = features.rasterize(zip(bl.geometry.values, bl.h.values), out_shape=(NY, NX), transform=T30, dtype="float32")
    hmean = ndi.uniform_filter(hras * (frac > 0), 5) / np.maximum(ndi.uniform_filter((frac > 0).astype(float), 5), 1e-3)
    np.savez_compressed(B / "terrain.npz", dsm=dsm, ground=ground, sea=sea, slope=slope, hs=hs, frac=frac, hmean=hmean, objh=objh,
                        X0=X0, Y1=Y1, RES=RES)
    bl[["h", "hsrc", "z", "geometry"]].to_parquet(B / "buildings.parquet")

    # ---- trees: single trees, tree rows, woods / forests / orchards / parks
    pts = read("points", ["other_tags"], where="other_tags LIKE '%\"natural\"=>\"tree\"%'")
    T_single = np.c_[pts.geometry.x, pts.geometry.y]
    ln = read("lines", ["other_tags"], where="other_tags LIKE '%tree_row%'")
    rows = []
    for gm in ln.geometry:
        L = gm.length
        for d in np.arange(0, L, 9):
            p = gm.interpolate(d); rows.append((p.x, p.y))
    T_rows = np.array(rows) if rows else np.zeros((0, 2))
    mp = read("multipolygons", ["landuse", "natural", "leisure"], where="landuse IN ('forest','orchard') OR natural IN ('wood','scrub') OR leisure IN ('park')")
    rng = np.random.default_rng(19)
    fpts = []
    for gm, lu, na, le in zip(mp.geometry, mp.landuse, mp.natural, mp.leisure):
        sp = 26 if (lu == "forest" or na == "wood") else 34 if lu == "orchard" else 30 if le == "park" else 48
        x0b, y0b, x1b, y1b = gm.bounds
        n = int(gm.area / (sp * sp))
        if n < 1:
            continue
        n = min(n, 60000)
        cand = np.c_[rng.uniform(x0b, x1b, n * 3), rng.uniform(y0b, y1b, n * 3)]
        ins = shapely.contains_xy(gm, cand[:, 0], cand[:, 1])
        fpts.append(cand[ins][:n])
    T_area = np.vstack(fpts) if fpts else np.zeros((0, 2))
    allT = np.vstack([T_single, T_rows, T_area])
    kind = np.r_[np.zeros(len(T_single)), np.ones(len(T_rows)), np.full(len(T_area), 2)]
    tc = ((allT[:, 0] - X0) / RES).astype(int).clip(0, NX - 1); tr_ = ((Y1 - allT[:, 1]) / RES).astype(int).clip(0, NY - 1)
    keep = ~sea[tr_, tc]
    allT, kind, tc, tr_ = allT[keep], kind[keep], tc[keep], tr_[keep]
    th = np.clip(objh[tr_, tc] * 0.8, 5, 16) * rng.uniform(0.75, 1.15, len(allT))
    th = np.where(kind == 0, np.clip(th, 6, 12), th)
    tz = ground[tr_, tc]
    tarr = np.c_[allT[:, 0] - X0, Y1 - allT[:, 1], th, tz, kind].astype("float32")
    tarr.tofile(W / "trees.f32"); np.save(B / "trees.npy", tarr)
    print(f"trees: {len(T_single):,} single, {len(T_rows):,} in rows, {len(T_area):,} in woods / orchards / parks")

    # ---- streams, roads, admin
    lines = read("lines", ["name", "highway", "waterway", "railway"])
    streams = lines[lines.waterway.isin(["river", "stream", "canal", "drain", "ditch"])]
    roads = lines[lines.highway.notna()]
    mah = read("multipolygons", ["name", "admin_level", "boundary"], where="boundary='administrative' AND admin_level IN ('6','8')")
    mah[mah.admin_level == "8"][["name", "geometry"]].to_parquet(B / "mahalle.parquet")
    mah[mah.admin_level == "6"][["name", "geometry"]].to_parquet(B / "districts.parquet")
    streams.to_parquet(B / "streams.parquet"); roads[["highway", "geometry"]].to_parquet(B / "roads.parquet")
    green = read("multipolygons", ["landuse", "natural", "leisure"], where="landuse IN ('forest','orchard','grass','meadow','farmland','cemetery') OR natural IN ('wood','scrub','grassland','heath') OR leisure IN ('park','garden')")
    green.to_parquet(B / "green.parquet")
    indus = read("multipolygons", ["landuse"], where="landuse IN ('industrial','landfill','port','railway')")
    indus.to_parquet(B / "industry.parquet")

    # ---- odour sources (scenario, relative weights)
    def mouth(name):
        s = streams[streams.name == name]
        if not len(s):
            return None
        best = None
        for gm in s.geometry:
            for p in (gm.coords[0], gm.coords[-1]):
                c_ = int((p[0] - X0) / RES); r_ = int((Y1 - p[1]) / RES)
                if 0 <= c_ < NX and 0 <= r_ < NY:
                    d = ndi.distance_transform_edt(~sea)[r_, c_] if best is None else None
                    dd = ground[r_, c_]
                    if best is None or dd < best[0]:
                        best = (dd, p)
        return best[1] if best else None
    S = []
    def add(name, kind, lon=None, lat=None, xy=None, w=1.0, r=150, note=""):
        if xy is None:
            xy = TR.transform(lon, lat)
        S.append({"name": name, "kind": kind, "x": float(xy[0]), "y": float(xy[1]), "w": w, "r": r, "note": note})
    add("Çiğli Atıksu Arıtma Tesisi", "wastewater", 27.0055, 38.4780, w=1.0, r=320, note="aeration basins mapped in OSM (landuse=basin)")
    add("Harmandalı Katı Atık Depolama Alanı", "landfill", 27.0655, 38.5335, w=1.0, r=380, note="OSM: Harmandalı Çöplüğü, landuse=landfill; biogas plant next to it")
    add("Karşıyaka Katı Atık Transfer İstasyonu", "transfer", 27.1182, 38.4962, w=0.3, r=80, note="OSM landuse=landfill")
    for nm, w in (("Meles Deresi", 0.6), ("Bornova Çayı", 0.4), ("Manda Çayı", 0.5), ("Büyük Çiğli Deresi", 0.4), ("Küçük Çiğli Deresi", 0.3), ("Gökdere", 0.3), ("Peynircioğlu Deresi", 0.4)):
        m = mouth(nm)
        if m is not None:
            add(f"{nm} ağzı", "stream", xy=m, w=w, r=120, note="stream mouth into the inner gulf (OSM)")
    # inner-gulf shallow sea: cells of sea east of 27.06° within 1.2 km of the shore
    xg = X0 + (np.arange(NX) + 0.5) * RES
    lon_e = TR.transform(27.06, 38.44)[0]
    dist_shore = ndi.distance_transform_edt(sea) * RES
    inner = sea & (xg[None, :] > lon_e) & (dist_shore < 1200)
    np.save(B / "inner_gulf.npy", inner)
    (W / "sources.json").write_text(json.dumps(S, ensure_ascii=False, indent=1))
    print("sources:", [s["name"] for s in S], f"+ inner gulf shallows {inner.sum() * RES * RES / 1e6:.1f} km²")
    meta = {"X0": X0, "Y1": Y1, "NX": NX, "NY": NY, "RES": RES, "crs": "EPSG:32635", "ll": LL,
            "buildings": int(len(bl)), "hsrc": {k: int(v) for k, v in pd.Series(src).value_counts().items()},
            "trees": {"single": int(len(T_single)), "rows": int(len(T_rows)), "areas": int(len(T_area)), "total": int(len(tarr))}}
    (B / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
