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
    # ---- the gulf itself: sewage signal from İZBB gulf monitoring (faecal coliform / E. coli, 11 stations, 2012–2026)
    from pyproj import Transformer
    tf = Transformer.from_crs(4326, 32635, always_xy=True)
    ms = pd.read_csv("data/izbb_korfez_olcum.csv", sep=";")
    ms = ms[ms.OLCUM_TIPI.isin(["FEKAL KOLİFORM", "ESCHERICHIA COLI"])]
    ms["v"] = pd.to_numeric(ms.OLCUM_DEGERI.astype(str).str.replace(",", ".").str.extract(r"([0-9.]+)")[0], errors="coerce")
    ms = ms.dropna(subset=["v"])
    ms["lg"] = np.log10(ms.v.clip(lower=1))
    sta = pd.read_csv("data/korfez_istasyonlari.csv", encoding="utf-8-sig")
    med = ms.groupby("ISTASYON_NUMARASI").lg.median()
    sta = sta[sta.ISTASYON_NUMARASI.isin(med.index)].copy()
    sta["lg"] = sta.ISTASYON_NUMARASI.map(med); sta["n"] = sta.ISTASYON_NUMARASI.map(ms.groupby("ISTASYON_NUMARASI").size())
    sta["x"], sta["y"] = tf.transform(sta.BOYLAM.values, sta.ENLEM.values)
    lo, hi = sta.lg.min(), sta.lg.max()
    sta["idx"] = 0.15 + 0.85 * (sta.lg - lo) / max(hi - lo, 1e-6)
    print(sta[["ISTASYON_ADI", "n", "lg", "idx"]].to_string())
    cy_, cx_ = np.mgrid[0:NY, 0:NX]
    Xc, Yc = X0 + (cx_ + 0.5) * G, Y1 - (cy_ + 0.5) * G
    wsum = np.zeros((NY, NX)); vsum = np.zeros((NY, NX))
    for r in sta.itertuples():
        w = 1 / np.maximum(np.hypot(Xc - r.x, Yc - r.y), 300) ** 2; wsum += w; vsum += w * r.idx
    idw = vsum / wsum
    dshore = ndi.distance_transform_edt(seaG) * G
    lon_ok = Xc > tf.transform(27.0, 38.42)[0]
    gulf_w = np.where(seaG & lon_ok, idw * np.exp(-dshore / 1400), 0)           # polluted water near the shore smells most
    gulf_w[gulf_w < 0.02] = 0
    np.save(B / "gulf_w.npy", gulf_w.astype("float32"))
    gulf_rc = np.argwhere(gulf_w > 0); gulf_p = gulf_w[gulf_w > 0] / gulf_w.sum()
    # weights: stream / canal mouths carry sewage overflow into the gulf → stronger; plant and landfill second
    WOVR = {"wastewater": 0.8, "landfill": 0.8, "transfer": 0.3}
    for s_ in S:
        s_.setdefault("w0", s_["w"])                               # prep.py weight, kept so reruns do not compound
        if s_["kind"] in WOVR:
            s_["w"] = WOVR[s_["kind"]]
        elif "Meles" in s_["name"]:
            s_["w"] = 1.0
        else:
            s_["w"] = round(min(0.9, s_["w0"] * 1.6), 2)
    GULF_K = [k for k, s_ in enumerate(S) if s_["kind"] not in WOVR]       # gulf-side sources (mouths)
    stations = [{"n": r.ISTASYON_ADI, "x": round(r.x - X0), "y": round(Y1 - r.y), "lg": round(float(r.lg), 2), "n_obs": int(r.n)} for r in sta.itertuples()]

    allc, gshare, stats = {}, {}, {"days": {}}
    tracks = None
    for scen in ("b", "o"):
        for mm in days:
            dw = wind[wind.t.dt.strftime("%m") == mm].reset_index(drop=True)
            P = np.zeros((0, 2)); A = np.zeros(0); M = np.zeros(0); C = np.zeros(0, bool)
            conc = np.zeros((24, NY, NX), "float32"); concg = np.zeros((24, NY, NX), "float32")
            film = scen == "b" and mm == "07"
            fx = []
            fields = [field(r.ws10, r.wd10, r.tc, scen == "b") for r in dw.itertuples()]
            # spin-up: the day's own last 3 hours stand in for the previous evening (no accumulation)
            for k, hr in enumerate([21, 22, 23] + list(range(24))):
                rec = k >= 3
                r = dw.iloc[hr]; u, v = fields[hr]
                warm = max(0.0, (r.tc - 14) / 12)
                newp, neww, newc = [], [], []
                for k_, s in enumerate(S):
                    n = int(round(REL * s["w"] * (0.6 + 0.4 * min(warm, 1.5) if k_ in GULF_K else 1.0)))
                    newp.append(src_points(s, n)); neww.append(np.full(n, 1.0)); newc.append(np.full(n, k_ in GULF_K))
                ng = int(REL * 3.2 * min(0.3 + warm, 2.3))                  # warm, still water smells more (air temperature as proxy)
                if ng:
                    kk = gulf_rc[rng.choice(len(gulf_rc), ng, p=gulf_p)]
                    newp.append(np.c_[kk[:, 1] + rng.uniform(0, 1, ng), kk[:, 0] + rng.uniform(0, 1, ng)]); neww.append(np.full(ng, 0.8)); newc.append(np.ones(ng, bool))
                newp = np.vstack(newp); neww = np.concatenate(neww); newc = np.concatenate(newc)
                P = np.vstack([P, newp]); A = np.r_[A, -rng.uniform(0, 3600, len(newp))]; M = np.r_[M, neww]; C = np.r_[C, newc]
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
                    P, A, M, C = P[alive], A[alive], M[alive], C[alive]
                    if rec and st % 5 == 4:
                        act = A >= 0
                        cc = P[act, 0].astype(int); rr2 = P[act, 1].astype(int)
                        ok = (cc >= 0) & (cc < NX) & (rr2 >= 0) & (rr2 < NY)
                        wgt = M[act][ok] * np.exp(-A[act][ok] / (0.9 * 3600))
                        np.add.at(conc[hr], (rr2[ok], cc[ok]), wgt)
                        g_ = C[act][ok]; np.add.at(concg[hr], (rr2[ok][g_], cc[ok][g_]), wgt[g_])
                        if film and st % 10 == 9:
                            fx.append(np.c_[P[act, 0], P[act, 1], M[act] * np.exp(-A[act] / (0.9 * 3600))].astype("float32"))
            conc = np.stack([ndi.gaussian_filter(c, 1.6) for c in conc])
            concg = np.stack([ndi.gaussian_filter(c, 1.6) for c in concg])
            allc[(scen, mm)] = conc
            gshare[(scen, mm)] = concg / np.maximum(conc, 1e-9)
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
        sh = gshare[(scen, mm)]; on = (idx >= lvl) & landG[None]
        Image.fromarray((np.clip(sh, 0, 1) * 255).astype("uint8").reshape(24 * NY, NX)).save(db / f"{scen}_gulfshare.png")
        e = stats["days"].setdefault(mm, {})
        e[scen] = {"km2_1h": round(float(((hours >= 1) & landG).sum() * G * G / 1e6), 2),
                   "km2_4h": round(float(((hours >= 4) & landG).sum() * G * G / 1e6), 2),
                   "km2_8h": round(float(((hours >= 8) & landG).sum() * G * G / 1e6), 2),
                   "gulf_share_land": round(float((sh * idx * on).sum() / max((idx * on).sum(), 1e-9)), 3),
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
    stats["stations"] = stations
    (W / "sources.json").write_text(json.dumps(S, ensure_ascii=False, indent=1))
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
