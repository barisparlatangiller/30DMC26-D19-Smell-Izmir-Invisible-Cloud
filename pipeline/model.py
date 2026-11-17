"""
Day 19 · Smell · Izmir — a representative odour-drift scenario (not a measurement, no emission data, no CFD).

Wind: Open-Meteo hourly 10 m wind at 38.49 N 27.11 E (the 21st of every month, Nov 2025 – Oct 2026), shaped by
  · terrain: air slows and turns where it would have to climb a steep slope, speeds up over open ridges;
  · buildings (scenario "with buildings"): dense, tall blocks slow the wind near the ground (built fraction × height);
  · calm nights (< 1.5 m/s): air drains down the slopes towards the gulf (as the cold air in Day 15).
Sources (relative weights, documented candidates): Çiğli wastewater plant, Harmandalı landfill, Karşıyaka transfer
  station, stream mouths into the inner gulf, and the shallow inner gulf itself, stronger in warm water (warm air proxy).
Particles are released every hour, carried by the hourly wind (60 s steps) with turbulent spread, and fade over 3 h.
Odour index = weighted particle density per 100 m cell and hour, scaled 0–1 over all days and both scenarios.

  python pipeline/model.py
Output build/odour/MM/{b,o}_HH.png (b = with buildings, o = without) · docs/data/wind/MM.json · build/film_tracks.npz ·
       docs/data/stats.json
"""
import json, math, time
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from PIL import Image
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates
from rasterio import features
from rasterio.transform import from_origin

B, W = Path("build"), Path("docs/data")
G = 100.0                                    # model / odour grid (m)
DT = 60.0                                    # s
LIFE = 2.5 * 3600.0
REL = 260                                    # particles per hour for a weight-1 source
rng = np.random.default_rng(1919)


def coarse(a, f, how="mean"):
    h, w = a.shape[0] // f * f, a.shape[1] // f * f
    a = a[:h, :w].reshape(h // f, f, w // f, f)
    return a.mean(axis=(1, 3)) if how == "mean" else a.max(axis=(1, 3))


def main():
    t0 = time.time()
    T = np.load(B / "terrain.npz")
    X0, Y1 = float(T["X0"]), float(T["Y1"])
    ground, sea, frac, hmean = T["ground"], T["sea"], T["frac"], T["hmean"]
    # 30 m → 100 m (factor 10/3: resample with zoom)
    z = 30 / G
    gnd = ndi.zoom(ground, z, order=1); seaG = ndi.zoom(sea.astype(float), z, order=1) > 0.5
    fr = ndi.zoom(frac, z, order=1); hm = ndi.zoom(np.nan_to_num(hmean), z, order=1)
    NY, NX = gnd.shape
    gs = ndi.gaussian_filter(gnd, 3)
    gy, gx = np.gradient(gs, G)
    gy = -gy                                                     # rows run north → south
    sl = np.hypot(gx, gy); ux, uy = gx / np.maximum(sl, 1e-6), gy / np.maximum(sl, 1e-6)
    rel = gnd - ndi.gaussian_filter(gnd, 15)
    f_terrain = np.clip(1 + rel / 250, 0.6, 1.5) * np.where(seaG, 1.15, 1.0)
    f_bld = np.clip(1 - 1.3 * fr * np.clip(hm / 15, 0, 1.5), 0.35, 1.0)     # pedestrian-level wind in dense blocks ≈ 0.4–0.7 of open
    inner = ndi.zoom(np.load(B / "inner_gulf.npy").astype(float), z, order=0) > 0.5
    S = json.loads((W / "sources.json").read_text())
    wind = pd.read_csv("data/wind_21st_hourly.csv")
    wind.columns = ["t", "ws10", "wd10", "ws100", "wd100", "tc", "RH"]
    wind["t"] = pd.to_datetime(wind.t)
    days = sorted(set(wind.t.dt.strftime("%m")), key=lambda m: (int(m) < 11, int(m)))

    def field(ws, wd, T_, bld):
        """hourly wind field (m/s, east / north components) on the 100 m grid"""
        th = math.radians(wd)
        u0, v0 = -ws * math.sin(th), -ws * math.cos(th)
        u = np.full((NY, NX), u0); v = np.full((NY, NX), v0)
        up = np.maximum(u * ux + v * uy, 0) * np.clip(sl / 0.10, 0, 1)     # part that would climb a steep slope
        u, v = u - 0.85 * up * ux, v - 0.85 * up * uy
        k = f_terrain * (f_bld if bld else 1.0)
        u, v = u * k, v * k
        if ws < 1.5:                                             # calm night: drainage down the slopes
            d = (1.5 - ws) / 1.5 * 0.7 * np.clip(sl / 0.05, 0, 1)
            u, v = u - d * ux, v - d * uy
        return ndi.gaussian_filter(u, 1.5), ndi.gaussian_filter(v, 1.5)

    # source release points (100 m grid coordinates: col, row)
    def src_points(s, n):
        r = s["r"] / G
        cx, cy = (s["x"] - X0) / G, (Y1 - s["y"]) / G
        a = rng.uniform(0, 2 * np.pi, n); rr = r * np.sqrt(rng.uniform(0, 1, n))
        return np.c_[cx + rr * np.cos(a), cy + rr * np.sin(a)]
    inner_rc = np.argwhere(inner)

    allc, stats = {}, {"days": {}}
    tracks = None
    for scen in ("b", "o"):
        for mm in days:
            dw = wind[wind.t.dt.strftime("%m") == mm].reset_index(drop=True)
            P = np.zeros((0, 2)); A = np.zeros(0); M = np.zeros(0)
            conc = np.zeros((24, NY, NX), "float32")
            film = scen == "b" and mm == "07"
            fx = []
            fields = [field(r.ws10, r.wd10, r.tc, scen == "b") for r in dw.itertuples()]
            # spin-up: the day's own last 3 hours stand in for the previous evening (no accumulation)
            for k, hr in enumerate([21, 22, 23] + list(range(24))):
                rec = k >= 3
                r = dw.iloc[hr]; u, v = fields[hr]
                warm = max(0.0, (r.tc - 14) / 12)
                newp, neww = [], []
                for s in S:
                    n = int(round(REL * s["w"]))
                    newp.append(src_points(s, n)); neww.append(np.full(n, 1.0))
                ng = int(REL * 0.9 * warm)
                if ng:
                    kk = inner_rc[rng.integers(0, len(inner_rc), ng)]
                    newp.append(np.c_[kk[:, 1] + rng.uniform(0, 1, ng), kk[:, 0] + rng.uniform(0, 1, ng)]); neww.append(np.full(ng, 0.8))
                newp = np.vstack(newp); neww = np.concatenate(neww)
                P = np.vstack([P, newp]); A = np.r_[A, -rng.uniform(0, 3600, len(newp))]; M = np.r_[M, neww]
                for st in range(int(3600 / DT)):
                    act = A >= 0
                    if act.any():
                        c, rr_ = P[act, 0], P[act, 1]
                        uu = map_coordinates(u, [rr_, c], order=1, mode="nearest"); vv = map_coordinates(v, [rr_, c], order=1, mode="nearest")
                        sig = (0.30 * np.hypot(uu, vv) + 0.20) * DT / G
                        P[act, 0] = c + uu * DT / G + rng.normal(0, sig)
                        P[act, 1] = rr_ - vv * DT / G + rng.normal(0, sig)
                    A += DT
                    alive = (A < LIFE) & (P[:, 0] > -5) & (P[:, 0] < NX + 5) & (P[:, 1] > -5) & (P[:, 1] < NY + 5)
                    P, A, M = P[alive], A[alive], M[alive]
                    if rec and st % 5 == 4:
                        act = A >= 0
                        cc = P[act, 0].astype(int); rr2 = P[act, 1].astype(int)
                        ok = (cc >= 0) & (cc < NX) & (rr2 >= 0) & (rr2 < NY)
                        wgt = M[act][ok] * np.exp(-A[act][ok] / (0.9 * 3600))
                        np.add.at(conc[hr], (rr2[ok], cc[ok]), wgt)
                        if film and st % 10 == 9:
                            fx.append(np.c_[P[act, 0], P[act, 1], M[act] * np.exp(-A[act] / (0.9 * 3600))].astype("float32"))
            conc = np.stack([ndi.gaussian_filter(c, 1.6) for c in conc])
            allc[(scen, mm)] = conc
            if film:
                tracks = fx
            print(f"[{time.time() - t0:5.0f} s] {scen} {mm}: max {conc.max():.1f}, particles alive {len(P):,}", flush=True)
    # common scale
    ref = np.percentile(np.concatenate([c[c > 0].ravel() for c in allc.values()]), 99.5)
    (W / "odour").mkdir(exist_ok=True); (B / "odour").mkdir(exist_ok=True)
    landG = ~seaG
    lvl = 0.15                                                     # "noticeable" threshold of the index
    for (scen, mm), conc in allc.items():
        idx = np.clip(conc / ref, 0, 1)
        d = W / "odour" / mm; d.mkdir(exist_ok=True); db = B / "odour" / mm; db.mkdir(exist_ok=True)
        for hr in range(24):                                         # hourly frames (build/), atlas for the web in build_web.py
            Image.fromarray((np.sqrt(idx[hr]) * 255).astype("uint8")).save(db / f"{scen}_{hr:02d}.png")
        hours = (idx >= lvl).sum(axis=0)
        np.save(B / f"hours_{scen}_{mm}.npy", hours)
        Image.fromarray(np.clip(hours * 10, 0, 255).astype("uint8")).save(d / f"{scen}_hours.png", optimize=True)
        e = stats["days"].setdefault(mm, {})
        e[scen] = {"km2_1h": round(float(((hours >= 1) & landG).sum() * G * G / 1e6), 2),
                   "km2_4h": round(float(((hours >= 4) & landG).sum() * G * G / 1e6), 2),
                   "km2_8h": round(float(((hours >= 8) & landG).sum() * G * G / 1e6), 2),
                   "land_km2_by_hour": [round(float(((idx[h] >= lvl) & landG).sum() * G * G / 1e6), 2) for h in range(24)]}
    # winds for the web: 500 m grid per hour, both scenarios
    (W / "wind").mkdir(exist_ok=True)
    for mm in days:
        dw = wind[wind.t.dt.strftime("%m") == mm].reset_index(drop=True)
        out = {"t": dw.t.dt.strftime("%H:%M").tolist(), "ws": dw.ws10.round(1).tolist(), "wd": dw.wd10.round(0).tolist(), "T": dw["tc"].round(1).tolist(),
               "RH": dw.RH.round(0).tolist(), "nx": NX // 5, "ny": NY // 5, "b": [], "o": []}
        for r in dw.itertuples():
            for scen in ("b", "o"):
                u, v = field(r.ws10, r.wd10, r.tc, scen == "b")
                out[scen].append([np.round(coarse(u, 5), 1).ravel().tolist(), np.round(coarse(v, 5), 1).ravel().tolist()])
        (W / "wind" / f"{mm}.json").write_text(json.dumps(out, separators=(",", ":")))
    stats["grid"] = {"X0": X0, "Y1": Y1, "G": G, "NX": NX, "NY": NY, "threshold": lvl}
    stats["days_order"] = days
    stats["sources"] = S
    # buildings affected (21 July, ≥ 4 h)
    bi = np.load(B / "bld_inst.npy")
    bc, br = (bi[:, 0] / G).astype(int).clip(0, NX - 1), (bi[:, 1] / G).astype(int).clip(0, NY - 1)
    for scen in ("b", "o"):
        hrs = np.load(B / f"hours_{scen}_07.npy")
        stats[f"bld_4h_{scen}_07"] = int((hrs[br, bc] >= 4).sum())
    (W / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    if tracks:
        np.savez_compressed(B / "film_tracks.npz", *tracks)
        print("film frames:", len(tracks))
    print(json.dumps({m: stats["days"][m] for m in ("07", "01")}, indent=0)[:1500])


def hr_real(hr, fx):
    return True


if __name__ == "__main__":
    main()
