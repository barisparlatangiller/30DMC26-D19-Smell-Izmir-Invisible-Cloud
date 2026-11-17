"""
Web assets for Day 19 (three.js page) from build/ (prep.py) and the model output (model.py).

  docs/data/dem.png        ground height, 30 m, 16 bit in R,G: (z + 20) × 50
  docs/data/terr.png       R hillshade · G slope (0–45°) · B sea
  docs/data/base.jpg       night basemap 4096 px (sea, green, industry, roads, streams, contours, mahalle lines)
  docs/data/odour/MM/{b,o}.png   24-hour atlas (6 × 4 tiles of 330 × 228), sqrt-scaled odour index
  docs/data/mah.png        mahalle id per 100 m cell (R,G) · docs/data/mah.json names, district, stats
  docs/data/bld.bin        buildings, uint16 × 6: cx·2, cy·2, L·10, W·10, angle·10000/π, h·10 ; z: dem
  docs/data/trees.bin      uint16 × 4: x·2, y·2, h·10, kind
"""
import json, math
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi
from shapely.geometry import box
from skimage import measure
from rasterio import features
from rasterio.transform import from_origin

B, W = Path("build"), Path("docs/data")
T = np.load(B / "terrain.npz")
X0, Y1, RES = float(T["X0"]), float(T["Y1"]), float(T["RES"])
NY, NX = T["ground"].shape
SX, SY = NX * RES, NY * RES                       # 33000 × 22800 m
ST = json.loads((W / "stats.json").read_text())
G = ST["grid"]


def png16(a, path, off, sc):
    v = np.clip(np.round((a + off) * sc), 0, 65535).astype(np.uint16)
    rgb = np.dstack([(v >> 8).astype(np.uint8), (v & 255).astype(np.uint8), np.zeros_like(v, np.uint8)])
    Image.fromarray(rgb).save(path, optimize=True)


def terrain():
    g = T["ground"].copy()
    sea = T["sea"]
    g[sea] = np.minimum(g[sea], -1.0) - (2.0 * ndi.distance_transform_edt(sea).clip(0, 6) / 6)[sea]  # gentle shelf under the sea surface
    png16(g, W / "dem.png", 20, 50)
    sl = np.clip(T["slope"] / 45 * 255, 0, 255).astype(np.uint8)
    hs = np.clip(T["hs"] * 255, 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack([hs, sl, (sea * 255).astype(np.uint8)])).save(W / "terr.png", optimize=True)
    return g


def basemap(g):
    PX = 4096
    k = PX / SX
    PY = int(round(SY * k))
    sea = T["sea"]
    gs = ndi.gaussian_filter(np.where(sea, 0, T["ground"]), 1.0)
    # land: night blue, slightly lighter uphill
    up = np.clip(gs / 600, 0, 1)
    land = np.dstack([27 + 13 * up, 35 + 14 * up, 54 + 14 * up])
    d = ndi.distance_transform_edt(sea) * RES
    shelf = np.clip(d / 1500, 0, 1)[..., None]
    seac = np.array([22, 74, 84]) * (1 - shelf) + np.array([12, 46, 58]) * shelf       # deep petrol-teal, lighter shallows
    rgb = np.where(sea[..., None], seac, land).astype(np.uint8)
    img = Image.fromarray(rgb).resize((PX, PY), Image.BICUBIC)
    tr = lambda x, y: ((x - X0) * k, (Y1 - y) * k)

    def poly(geoms, fill, outline=None, layer=None):
        dr = ImageDraw.Draw(layer or img, "RGBA")
        for geom in geoms:
            for p in getattr(geom, "geoms", [geom]):
                if p.is_empty or p.geom_type != "Polygon":
                    continue
                dr.polygon([tr(*c) for c in p.exterior.coords], fill=fill, outline=outline)
                for h in p.interiors:
                    dr.polygon([tr(*c) for c in h.coords], fill=None)

    def lines(geoms, fill, width):
        dr = ImageDraw.Draw(img, "RGBA")
        for geom in geoms:
            for l in getattr(geom, "geoms", [geom]):
                if l.geom_type == "Polygon":
                    l = l.exterior
                if l.is_empty or l.geom_type not in ("LineString", "LinearRing"):
                    continue
                dr.line([tr(*c) for c in l.coords], fill=fill, width=width, joint="curve")

    green = gpd.read_parquet(B / "green.parquet")
    ind = gpd.read_parquet(B / "industry.parquet")
    poly(ind.geometry, (70, 60, 66, 150))
    poly(green.geometry, (34, 62, 48, 190))
    # contours from the 30 m ground (smoothed): 10 m thin, 50 m bold
    gc = ndi.gaussian_filter(np.where(sea, -5, T["ground"]), 1.4)
    dr = ImageDraw.Draw(img, "RGBA")
    for lev in range(10, 1060, 10):
        bold = lev % 50 == 0
        for c in measure.find_contours(gc, lev):
            if len(c) < 6:
                continue
            pts = [((x + 0.5) * RES * k, (y + 0.5) * RES * k) for y, x in c]
            dr.line(pts, fill=(140, 150, 178, 70 if bold else 32), width=2 if bold else 1)
    mah = gpd.read_parquet(B / "mahalle.parquet")
    lines(mah.geometry.boundary, (150, 160, 190, 46), 1)
    roads = gpd.read_parquet(B / "roads.parquet")
    order = {"motorway": 0, "trunk": 0, "primary": 1, "secondary": 1, "tertiary": 2}
    roads["o"] = roads.highway.map(order).fillna(3)
    for o, col, wd in ((3, (92, 104, 136, 85), 1), (2, (112, 124, 156, 130), 2), (1, (136, 146, 176, 160), 2), (0, (166, 172, 196, 180), 3)):
        lines(roads[roads.o == o].geometry, col, wd)
    st = gpd.read_parquet(B / "streams.parquet")
    lines(st.geometry, (70, 150, 160, 200), 2)
    # coast line
    cs = measure.find_contours(ndi.gaussian_filter(sea.astype(float), 0.8), 0.5)
    for c in cs:
        if len(c) > 10:
            dr.line([((x + 0.5) * RES * k, (y + 0.5) * RES * k) for y, x in c], fill=(120, 180, 186, 150), width=2)
    img.save(W / "base.jpg", quality=88, optimize=True, progressive=True)
    print("base", img.size)


def odour_atlas():
    for mm in ST["days_order"]:
        d = W / "odour" / mm
        for sc in ("b", "o"):
            tiles = [np.asarray(Image.open(d / f"{sc}_{h:02d}.png")) for h in range(24)]
            th, tw = tiles[0].shape
            at = np.zeros((th * 4, tw * 6), np.uint8)
            for h, t in enumerate(tiles):
                at[(h // 6) * th:(h // 6 + 1) * th, (h % 6) * tw:(h % 6 + 1) * tw] = t
            Image.fromarray(at).save(d / f"{sc}.png", optimize=True)
    print("atlas", tw, th)


def instances():
    b = np.load(B / "bld_inst.npy")      # cx-X0, Y1-cy, L, W, angle, h, z
    q = np.c_[b[:, 0] * 2, b[:, 1] * 2, np.clip(b[:, 2], 0, 6553) * 10, np.clip(b[:, 3], 0, 6553) * 10,
              (np.mod(b[:, 4], np.pi)) / np.pi * 10000, np.clip(b[:, 5], 0, 6553) * 10]
    np.clip(np.round(q), 0, 65535).astype("<u2").tofile(W / "bld.bin")
    t = np.load(B / "trees.npy")         # x-X0, Y1-y, h, z, kind
    q = np.c_[t[:, 0] * 2, t[:, 1] * 2, t[:, 2] * 10, t[:, 4]]
    np.clip(np.round(q), 0, 65535).astype("<u2").tofile(W / "trees.bin")
    for f in ("buildings.f32", "trees.f32"):
        (W / f).unlink(missing_ok=True)
    print("buildings", len(b), "trees", len(t))
    return b


def mahalle(b):
    mah = gpd.read_parquet(B / "mahalle.parquet").reset_index(drop=True)
    dpath = Path("data/izmir_districts.geojson")
    if dpath.exists():
        dis = gpd.read_file(dpath)
        dis = dis[dis.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(32635)[["name", "geometry"]]
        rp = mah.copy(); rp["geometry"] = mah.representative_point()
        j = gpd.sjoin(rp, dis.rename(columns={"name": "dist"}), how="left", predicate="within")
        mah["dist"] = j.groupby(level=0).dist.first().reindex(mah.index).fillna("")
    else:
        mah["dist"] = ""
    clip = box(X0, Y1 - SY, X0 + SX, Y1)
    mah = mah[mah.intersects(clip)].reset_index(drop=True)
    tf = from_origin(X0, Y1, G["G"], G["G"])
    ras = features.rasterize(((geom, i + 1) for i, geom in enumerate(mah.geometry)), out_shape=(G["NY"], G["NX"]), transform=tf, dtype="uint16")
    Image.fromarray(np.dstack([(ras >> 8).astype(np.uint8), (ras & 255).astype(np.uint8), np.zeros_like(ras, np.uint8)])).save(W / "mah.png")
    # buildings per mahalle; odour hours per building, per day (with buildings)
    bc = (b[:, 0] / G["G"]).astype(int).clip(0, G["NX"] - 1); br = (b[:, 1] / G["G"]).astype(int).clip(0, G["NY"] - 1)
    mid = ras[br, bc]
    days = ST["days_order"]
    H = np.stack([np.load(B / f"hours_b_{m}.npy")[br, bc] for m in days])          # days × buildings
    Ho = np.stack([np.load(B / f"hours_o_{m}.npy")[br, bc] for m in days])
    mean_h = H.mean(axis=0)
    out = []
    df = pd.DataFrame({"m": mid, "h": mean_h, "h07": H[days.index("07")], "x4": (H >= 4).mean(axis=0)})
    agg = df[df.m > 0].groupby("m").agg(n=("h", "size"), h=("h", "mean"), h07=("h07", "mean"), x4=("x4", "mean"))
    for i, r in mah.iterrows():
        a = agg.loc[i + 1] if (i + 1) in agg.index else None
        c = r.geometry.representative_point()
        out.append({"n": r["name"], "d": r["dist"], "c": [round(c.x - X0), round(Y1 - c.y)], "b": int(a.n) if a is not None else 0,
                    "h": round(float(a.h), 2) if a is not None else 0, "h07": round(float(a.h07), 1) if a is not None else 0,
                    "x4": round(float(a.x4), 3) if a is not None else 0})
    (W / "mah.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    # district summary (12 days, with buildings)
    dd = pd.DataFrame({"d": [out[m - 1]["d"] if m > 0 else "" for m in mid], "h": mean_h, "x4": (H >= 4).mean(axis=0)})
    dist = dd[dd.d != ""].groupby("d").agg(n=("h", "size"), h=("h", "mean"), x4=("x4", "mean")).sort_values("h", ascending=False)
    ST["districts"] = [{"d": k, "b": int(v.n), "h": round(float(v.h), 2), "x4": round(float(v.x4), 3)} for k, v in dist.iterrows() if v.n > 2000]
    # headline numbers
    ST["headline"] = {
        "buildings": int(len(b)),
        "bld_any_day_1h": int((H >= 1).any(axis=0).sum()),
        "bld_mean_h": round(float(mean_h.mean()), 2),
        "bld_4h_07_b": int((H[days.index("07")] >= 4).sum()),
        "bld_4h_07_o": int((Ho[days.index("07")] >= 4).sum()),
        "share_any_day": round(float((H >= 1).any(axis=0).mean()), 3),
        "linger_dense": linger(),
    }
    top = sorted([o for o in out if o["b"] >= 150], key=lambda o: -o["h"])[:10]
    ST["top_mahalle"] = top
    print("districts", ST["districts"][:4]); print("top", top[:3]); print(ST["headline"])


def linger():
    """odour summed over the day inside dense blocks (built fraction > 0.3): with / without buildings"""
    fr = ndi.zoom(T["frac"], RES / G["G"], order=1)[:G["NY"], :G["NX"]] > 0.3
    out = {}
    for mm in ST["days_order"]:
        a = [sum((np.asarray(Image.open(W / "odour" / mm / f"{sc}_{h:02d}.png")).astype(float) / 255) ** 2 for h in range(24)) for sc in ("b", "o")]
        out[mm] = round(float(a[0][fr].sum() / max(a[1][fr].sum(), 1e-9)), 3)
    return out


def extras():
    from pyproj import Transformer
    tf = Transformer.from_crs(4326, 32635, always_xy=True)
    inner = np.load(B / "inner_gulf.npy")
    rr, cc = np.nonzero(inner)
    rng = np.random.default_rng(19)
    k = rng.choice(len(rr), 500, replace=False)
    ST["gulfpts"] = [[round((cc[i] + rng.random()) * RES), round((rr[i] + rng.random()) * RES)] for i in k]   # x-X0, Y1-y
    L = [("Karşıyaka", 27.112, 38.462, "big"), ("Bayraklı", 27.168, 38.462, "big"), ("Bornova", 27.222, 38.468, "big"), ("Konak", 27.138, 38.414, "big"),
         ("Karabağlar", 27.118, 38.382, "big"), ("Buca", 27.178, 38.386, "big"), ("Balçova", 27.048, 38.392, "big"), ("Narlıdere", 26.995, 38.398, "big"),
         ("Çiğli", 27.062, 38.497, "big"), ("Gaziemir", 27.148, 38.350, "big"), ("İzmir Körfezi", 27.035, 38.438, "water"), ("İç Körfez", 27.115, 38.440, "water")]
    ST["labels"] = []
    for n, lon, lat, c in L:
        x, y = tf.transform(lon, lat)
        ST["labels"].append([n, round(x - X0), round(Y1 - y), c])


def wind_rose():
    w = pd.read_csv("data/wind_year_hourly.csv", skiprows=3)
    w.columns = [c.strip() for c in w.columns]
    ws = w.iloc[:, 1].astype(float); wd = w.iloc[:, 2].astype(float)
    sec = ((wd + 11.25) % 360 // 22.5).astype(int)
    rose = [round(float(((sec == i) & (ws >= 0.5)).mean()), 4) for i in range(16)]
    ST["rose"] = {"freq": rose, "calm": round(float((ws < 0.5).mean()), 4), "n": int(len(w)), "cols": list(w.columns[:3])}
    print("rose", ST["rose"])


if __name__ == "__main__":
    g = terrain()
    basemap(g)
    odour_atlas()
    b = instances()
    mahalle(b)
    wind_rose()
    extras()
    (W / "stats.json").write_text(json.dumps(ST, ensure_ascii=False, indent=1))
