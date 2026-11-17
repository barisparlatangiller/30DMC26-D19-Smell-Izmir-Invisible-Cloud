"""
Day 19 film for LinkedIn (1080×1350, ~25 s, top view): 21 July in İzmir, hour by hour. Calm night air slides down to
the gulf, the imbat sets in after noon and pushes the odour cloud from the gulf, the Çiğli wastewater plant and the
Harmandalı landfill into the city; then a close-up of the north shore and the three numbers.

  python pipeline/film.py
Output  build/video/day19_izmir_smell.mp4 · cover.png · still_*.png · outro.png
"""
import json, math, subprocess, time
from pathlib import Path

import numpy as np
import geopandas as gpd
import shapely
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi

B, D, OUT = Path("build"), Path("docs/data"), Path("build/video")
W, H, FPS = 1080, 1350, 24
MAP_Y, MAP_H = 196, 1004
SX, SY, X0, Y1 = 33000, 22800, 491700, 4266300
BG = (18, 26, 42)
INK, INK2, INK3, ACC = (236, 230, 214), (170, 176, 190), (124, 132, 150), (227, 196, 74)
RAMP = [(0, (246, 240, 184)), (0.35, (240, 220, 114)), (0.6, (227, 196, 74)), (0.85, (179, 154, 54)), (1, (127, 109, 42))]
DAY = "07"
ST = json.loads((D / "stats.json").read_text())
SRC = json.loads((D / "sources.json").read_text())
WIND = json.loads((D / "wind" / f"{DAY}.json").read_text())
rng = np.random.default_rng(1907)


def font(size, bold=False):
    f = subprocess.run(["fc-match", "-f", "%{file}", "Inter:bold" if bold else "Inter:medium"], capture_output=True, text=True).stdout.strip()
    return ImageFont.truetype(f, size)


F = {"q": font(58, True), "qs": font(25, True), "mid": font(38, True), "sm": font(28), "lab": font(22, True), "labs": font(19, True), "foot": font(18),
     "clock": font(64, True), "big": font(112, True), "num": font(74, True)}


def ease(u):
    u = min(1, max(0, u)); return u * u * (3 - 2 * u)


def ramp(v):
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,))
    for (a, ca), (b, cb) in zip(RAMP[:-1], RAMP[1:]):
        m = (v >= a) & (v <= b); t = ((v - a) / (b - a))[m][:, None]
        out[m] = np.array(ca) * (1 - t) + np.array(cb) * t
    return out


class View:
    """window in local metres (lx east, ly south) → film pixels"""
    def __init__(self, cx, cy, span):
        self.span, self.px = span, span / W
        self.lx0, self.ly0 = cx - span / 2, cy - MAP_H * self.px / 2

    def xy(self, lx, ly):
        return (np.asarray(lx) - self.lx0) / self.px, (np.asarray(ly) - self.ly0) / self.px

    def lerp(self, o, t):
        v = View(0, 0, self.span + (o.span - self.span) * t)
        cx = (self.lx0 + self.span / 2) * (1 - t) + (o.lx0 + o.span / 2) * t
        cy = (self.ly0 + MAP_H * self.px / 2) * (1 - t) + (o.ly0 + MAP_H * o.px / 2) * t
        return View(cx, cy, v.span)


FULL = View(17600, 11400, 24400)
ZOOM = View(17200, 10600, 12400)
K2 = 2                                                           # base canvas at 2× the full view


def base_canvas():
    """2× base for the FULL window: night basemap × hillshade + trees + buildings"""
    Wb, Hb = W * K2, MAP_H * K2
    pxm = FULL.px / K2
    src = Image.open(D / "base.jpg"); k = src.width / SX
    box = (FULL.lx0 * k, FULL.ly0 * k, (FULL.lx0 + Wb * pxm) * k, (FULL.ly0 + Hb * pxm) * k)
    base = np.asarray(src.resize((Wb, Hb), Image.LANCZOS, box=box)).astype(float)
    terr = Image.open(D / "terr.png"); kt = terr.width / SX
    tbox = (FULL.lx0 * kt, FULL.ly0 * kt, (FULL.lx0 + Wb * pxm) * kt, (FULL.ly0 + Hb * pxm) * kt)
    tr = np.asarray(terr.resize((Wb, Hb), Image.BICUBIC, box=tbox)).astype(float) / 255
    hs, sea = tr[..., 0], tr[..., 2] > 0.5
    gw = np.clip((tr[..., 2] * 255 - 128) / 127, 0, 1) * sea
    mul = np.where(sea, 1.0, 0.55 + 0.68 * hs)
    img = base * mul[..., None]
    img = img * (1 - 0.6 * gw[..., None]) + np.array([64, 69, 41]) * 0.6 * gw[..., None]      # murky water: sewage signal
    im = Image.fromarray(np.clip(img, 0, 255).astype("uint8")); d = ImageDraw.Draw(im, "RGBA")
    # trees: small dots in deep green
    t = np.fromfile(D / "trees.bin", "<u2").reshape(-1, 4).astype(float)
    tx, ty = (t[:, 0] / 2 - FULL.lx0) / pxm, (t[:, 1] / 2 - FULL.ly0) / pxm
    m = (tx > 0) & (tx < Wb) & (ty > 0) & (ty < Hb)
    for x, y, hh in zip(tx[m], ty[m], t[m, 2] / 10):
        r = 0.8 + hh / 20
        d.ellipse([x - r, y - r, x + r, y + r], fill=(40, 82, 56, 170))
    # buildings: footprints in pale sand, with a short shadow to the south-east
    bl = gpd.read_parquet(B / "buildings.parquet")
    bl = bl.cx[X0 + FULL.lx0: X0 + FULL.lx0 + Wb * pxm, Y1 - FULL.ly0 - Hb * pxm: Y1 - FULL.ly0]
    geoms = bl.geometry.values; hgt = bl.h.values
    for gm, hh in zip(geoms, hgt):
        for p in getattr(gm, "geoms", [gm]):
            c = np.asarray(p.exterior.coords)
            px, py = (c[:, 0] - X0 - FULL.lx0) / pxm, (Y1 - c[:, 1] - FULL.ly0) / pxm
            o = min(6, hh / pxm * 0.22)
            d.polygon(list(zip(px + o, py + o)), fill=(8, 12, 22, 120))
            d.polygon(list(zip(px, py)), fill=(214, 204, 184, 235))
    arr = np.asarray(im).astype(float)
    bmask = np.zeros((Hb, Wb), np.uint8)
    return arr, sea


def crop(arr, v):
    """the map window v out of the 2× base"""
    s = v.span / FULL.span
    x0, y0 = (v.lx0 - FULL.lx0) / (FULL.px / K2), (v.ly0 - FULL.ly0) / (FULL.px / K2)
    im = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    return np.asarray(im.resize((W, MAP_H), Image.LANCZOS, box=(x0, y0, x0 + W * K2 * s, y0 + MAP_H * K2 * s))).astype(float)


ODO = [np.asarray(Image.open(B / "odour" / DAY / f"b_{h:02d}.png")).astype(float) / 255 for h in range(24)]
ODO = [o * o for o in ODO]


def odour_field(h, v):
    h0 = int(math.floor(h)) % 24; f = h - math.floor(h)
    o = ODO[h0] * (1 - f) + ODO[(h0 + 1) % 24] * f
    im = Image.fromarray(o.astype("float32"), "F")
    x0, y0 = v.lx0 / 100, v.ly0 / 100
    return np.asarray(im.resize((W, MAP_H), Image.BICUBIC, box=(x0, y0, x0 + v.span / 100, y0 + MAP_H * v.px / 100)))


def fbm_tile(n, seed):
    r = np.random.default_rng(seed); acc = np.zeros((n, n))
    for k, a in ((8, 0.5), (16, 0.28), (32, 0.14), (64, 0.08)):
        g = r.random((k, k)); g = np.tile(g, (3, 3))
        z = ndi.zoom(g, n * 3 / (k * 3), order=3)[n:2 * n, n:2 * n] if False else np.asarray(Image.fromarray(g.astype("float32"), "F").resize((n * 3, n * 3), Image.BICUBIC))[n:2 * n, n:2 * n]
        acc += a * z
    return acc


NOISE = [fbm_tile(1024, 1), fbm_tile(1024, 2)]


def noise(v, t, i, scale, dx, dy):
    """noise in world space (m), scrolled by (dx, dy) m"""
    n = NOISE[i]; N = n.shape[0]
    xs = ((np.arange(W) * v.px + v.lx0 - dx) / scale) % N
    ys = ((np.arange(MAP_H) * v.px + v.ly0 - dy) / scale) % N
    return n[ys.astype(int)[:, None], xs.astype(int)[None, :]]


def wind_at(lx, ly, h):
    nx, ny = WIND["nx"], WIND["ny"]; Hh = WIND["b"]
    fx = np.clip(lx / 500 - 0.5, 0, nx - 1.001); fy = np.clip(ly / 500 - 0.5, 0, ny - 1.001)
    x, y = fx.astype(int), fy.astype(int); u, v = fx - x, fy - y; i = y * nx + x
    h0 = int(math.floor(h)) % 24; h1 = (h0 + 1) % 24; f = h - math.floor(h)
    def bil(a):
        a = np.asarray(a); return a[i] * (1 - u) * (1 - v) + a[i + 1] * u * (1 - v) + a[i + nx] * (1 - u) * v + a[i + nx + 1] * u * v
    return (bil(Hh[h0][0]) * (1 - f) + bil(Hh[h1][0]) * f, bil(Hh[h0][1]) * (1 - f) + bil(Hh[h1][1]) * f)


class Drift:
    NP, TRAIL, TS = 2000, 14, 260.0

    def __init__(self):
        self.sp = [(s["x"] - X0, Y1 - s["y"], s["r"], s["w"]) for s in SRC]
        self.wc = np.cumsum([s[3] for s in self.sp]); self.gulf = np.array(ST["gulfpts"], float)
        self.x = np.zeros(self.NP); self.y = np.zeros(self.NP); self.age = np.zeros(self.NP); self.life = np.ones(self.NP); self.g = np.zeros(self.NP, bool); self.mouth = np.zeros(self.NP, bool)
        self.tr = np.full((self.TRAIL, self.NP, 2), np.nan)
        self.spawn(np.arange(self.NP), warm=0.3); self.age = rng.random(self.NP) * self.life

    def spawn(self, idx, warm=0.3):
        n = len(idx); tot = self.wc[-1] + 3.2 * min(0.3 + warm, 2.3)
        r = rng.random(n) * tot; gl = r > self.wc[-1]
        k = np.searchsorted(self.wc, np.minimum(r, self.wc[-1] - 1e-9))
        a = rng.random(n) * 6.283; dd = np.array([self.sp[j][2] for j in k]) * np.sqrt(rng.random(n))
        self.x[idx] = np.array([self.sp[j][0] for j in k]) + np.cos(a) * dd
        self.y[idx] = np.array([self.sp[j][1] for j in k]) + np.sin(a) * dd
        gi = idx[gl]; gp = self.gulf[rng.integers(0, len(self.gulf), len(gi))]
        self.x[gi] = gp[:, 0] + rng.normal(0, 40, len(gi)); self.y[gi] = gp[:, 1] + rng.normal(0, 40, len(gi))
        self.g[idx] = gl; self.mouth[idx] = np.array([SRC[j]["kind"] == "stream" for j in k]) & ~gl; self.age[idx] = 0; self.life[idx] = 3 + rng.random(n) * 4; self.tr[:, idx] = np.nan

    def step(self, h, dt, warm):
        self.age += dt
        dead = (self.age > self.life) | (self.x < 0) | (self.x > SX) | (self.y < 0) | (self.y > SY)
        if dead.any():
            self.spawn(np.nonzero(dead)[0], warm)
        u, v = wind_at(self.x, self.y, h)
        tb = 0.6 + 0.3 * np.hypot(u, v)
        self.x += (u + rng.normal(0, 0.45, self.NP) * tb) * self.TS * dt
        self.y += (-v + rng.normal(0, 0.45, self.NP) * tb) * self.TS * dt
        self.tr = np.roll(self.tr, 1, axis=0); self.tr[0, :, 0] = self.x; self.tr[0, :, 1] = self.y

    def draw(self, im, v, alpha=1.0):
        d = ImageDraw.Draw(im, "RGBA")
        fade = np.clip(np.minimum(self.age / 0.6, (self.life - self.age) / 1.0), 0, 1) * alpha
        for j in range(self.NP):
            if fade[j] < 0.03:
                continue
            seg = self.tr[:, j]; ok = ~np.isnan(seg[:, 0])
            if ok.sum() < 2:
                continue
            px, py = v.xy(seg[ok, 0], seg[ok, 1]); py = py + MAP_Y
            col = (217, 191, 78) if (self.g[j] or self.mouth[j]) else (246, 236, 158)
            n = len(px)
            for s in range(n - 1):
                a = int(255 * fade[j] * (1 - s / n) * 0.5)
                d.line([(px[s], py[s]), (px[s + 1], py[s + 1])], fill=col + (a,), width=2)


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    fr = OUT / "frames"; fr.mkdir(exist_ok=True)
    for f in fr.glob("*.jpg"):
        f.unlink()
    base2, _ = base_canvas()
    print(f"[{time.time() - t0:.0f} s] base", flush=True)
    sea_full = np.asarray(Image.open(D / "terr.png"))[..., 2] > 127
    LBL = [(n, lx, ly) for n, lx, ly, c in ST["labels"] if c == "big"]
    WLBL = [("INNER GULF", lx, ly) for n, lx, ly, c in ST["labels"] if n == "İç Körfez"]
    SHORT = {"Çiğli Atıksu Arıtma Tesisi": "Çiğli wastewater plant", "Harmandalı Katı Atık Depolama Alanı": "Harmandalı landfill", "Meles Deresi ağzı": "Meles mouth"}
    hb = ST["days"][DAY]["b"]["land_km2_by_hour"]
    drift = Drift()

    def compose(v, h, title, sub, cap=None, od_a=1.0, drift_a=1.0, labels=1.0, clock=True, big=None, overlay=None, t=0.0, base=None):
        img = crop(base2, v) if base is None else base
        o = odour_field(h, v)
        th = WIND["wd"][int(h) % 24] * math.pi / 180; ws = WIND["ws"][int(h) % 24]
        dx, dy = -math.sin(th) * ws * t * 260, math.cos(th) * ws * t * 260         # noise scrolls with the wind (m)
        m1 = noise(v, t, 0, 60, dx, dy); m2 = noise(v, t, 1, 26, dx * 1.6, dy * 1.6)
        dens = np.clip((o - 0.01) / 0.32, 0, 1); dens = dens * dens * (3 - 2 * dens)
        a = np.clip(dens * (0.62 + 1.2 * m1 * m2), 0, 0.9) * od_a
        col = ramp(np.clip(o * 1.15, 0, 1)) * (0.9 + 0.2 * m1[..., None])
        img = img * (1 - a[..., None]) + col * a[..., None]
        im = Image.new("RGB", (W, H), BG); im.paste(Image.fromarray(np.clip(img, 0, 255).astype("uint8")), (0, MAP_Y))
        if drift_a > 0:
            drift.draw(im, v, drift_a)
        d = ImageDraw.Draw(im, "RGBA")
        if labels > 0:
            for n, lx, ly in LBL:
                x, y = v.xy(lx, ly)
                if 30 < x < W - 30 and 30 < y < MAP_H - 30:
                    d.text((x, y + MAP_Y), n.upper(), font=F["labs"], fill=(216, 211, 196, int(230 * labels)), anchor="mm", stroke_width=3, stroke_fill=BG + (int(200 * labels),))
            for n, lx, ly in WLBL:
                x, y = v.xy(lx, ly + 900)
                if 30 < x < W - 30 and 30 < y < MAP_H - 30:
                    d.text((x, y + MAP_Y), n, font=F["lab"], fill=(150, 205, 205, int(230 * labels)), anchor="mm", stroke_width=3, stroke_fill=BG + (int(200 * labels),))
            for s in SRC:
                if s["name"] in SHORT:
                    x, y = v.xy(s["x"] - X0, Y1 - s["y"]); y += MAP_Y
                    if 0 < x < W and MAP_Y < y < MAP_Y + MAP_H:
                        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=ACC + (int(255 * labels),), outline=(255, 245, 200, int(160 * labels)), width=2)
                        tx = x + 14 if x < W - 300 else x - 14
                        d.text((tx, y), SHORT[s["name"]], font=F["lab"], fill=(240, 220, 122, int(255 * labels)), anchor="lm" if x < W - 300 else "rm", stroke_width=3, stroke_fill=BG)
        # header
        d.rectangle([0, 0, W, MAP_Y], fill=BG)
        d.text((48, 36), "#30DAYMAPCHALLENGE · DAY 19 · SMELL · İZMIR", font=F["qs"], fill=ACC)
        d.text((48, 76), title, font=F["q"], fill=INK)
        if sub:
            d.text((48, 146), sub, font=F["sm"], fill=INK2)
        # clock + wind
        if clock:
            hh, mm = int(h) % 24, int((h - int(h)) * 6) * 10
            d.rounded_rectangle([W - 300, MAP_Y + 24, W - 24, MAP_Y + 178], 22, fill=(18, 26, 42, 215))
            d.text((W - 270, MAP_Y + 40), f"{hh:02d}:{mm:02d}", font=F["clock"], fill=INK)
            d.text((W - 270, MAP_Y + 118), f"21 July · {ws:.1f} m/s", font=F["labs"], fill=INK2)
            # wind arrow: where the air goes
            cx, cy = W - 66, MAP_Y + 76; ang = th + math.pi
            ex, ey = cx + math.sin(ang) * 26, cy - math.cos(ang) * 26
            bx, by = cx - math.sin(ang) * 26, cy + math.cos(ang) * 26
            d.line([(bx, by), (ex, ey)], fill=(95, 179, 184), width=5)
            for s in (-0.5, 0.5):
                d.line([(ex, ey), (ex - math.sin(ang + s) * 14, ey + math.cos(ang + s) * 14)], fill=(95, 179, 184), width=5)
            i0 = int(round(h)) % 24
            d.text((W - 270, MAP_Y + 146), f"cloud over {hb[i0]:.0f} km² of land", font=F["labs"], fill=ACC)
        # bottom band
        d.rectangle([0, MAP_Y + MAP_H, W, H], fill=BG)
        if cap:
            d.text((48, MAP_Y + MAP_H + 26), cap[0], font=F["mid"], fill=INK)
            if len(cap) > 1:
                d.text((48, MAP_Y + MAP_H + 76), cap[1], font=F["sm"], fill=INK2)
        d.text((48, H - 30), "Scenario, not a measurement · İZBB gulf data · Open-Meteo · Copernicus DEM · GHSL · © OSM · B. Parlatangiller", font=F["foot"], fill=INK3)
        if big:
            big(d)
        if overlay:
            overlay(d)
        return im

    n = 0
    def save(im):
        nonlocal n
        im.save(fr / f"f{n:04d}.jpg", quality=92); n += 1

    def warm_at(h):
        i = int(h) % 24; return max(0.0, (WIND["T"][i] - 14) / 12)

    for _ in range(int(FPS * 2)):
        drift.step(0.0, 1 / FPS, warm_at(0))
    T = 0.0
    # A · title (00:00)
    NA = int(FPS * 2.4)
    for k in range(NA):
        a = ease(k / (FPS * 1.0)); T += 1 / FPS
        drift.step(0.0, 1 / FPS, warm_at(0))
        im = compose(FULL, 0.0, "Where does İzmir's gulf smell go?", "21 July · a night and a day, hour by hour", cap=("Sewage-fed streams empty into the gulf", "murky water = highest sewage signal (İZBB stations)"), od_a=a, drift_a=a, t=T)
        save(im)
    im.save(OUT / "still_night.png")
    # B · the day, 00 → 24
    NB = int(FPS * 13.0)
    PH = [(0, 7, ("Night: calm air", "slides down the slopes to the gulf")), (7, 12, ("Morning: the wind turns", "the cloud hangs over the shore")),
          (12, 20, ("Afternoon: the imbat", "carries the gulf's smell into Konak, Bayraklı, Bornova")), (20, 24.1, ("Evening: the wind drops", "the cloud settles over the north shore"))]
    for k in range(NB):
        h = 24 * k / NB; T += 1 / FPS
        drift.step(h, 1 / FPS, warm_at(h))
        cap = next(c for a, b, c in PH if a <= h < b)
        im = compose(FULL, h, "Where does İzmir's gulf smell go?", "21 July · hour by hour", cap=cap, t=T)
        save(im)
        if abs(h - 15.5) < 24 / NB / 2:
            im.save(OUT / "still_imbat.png"); cover = im
    # C · close-up of the north shore (16:00 → 17:30)
    NC = int(FPS * 5.0)
    top = ST["top_mahalle"][:3]
    for k in range(NC):
        u = ease(k / (FPS * 2.4)); v = FULL.lerp(ZOOM, u); h = 16 + 1.5 * k / NC; T += 1 / FPS
        drift.step(h, 1 / FPS, warm_at(h))
        def ov(d, u=u, v=v):
            if u < 0.98:
                return
            for m in top:
                x, y = v.xy(m["c"][0], m["c"][1]); y += MAP_Y
                nm = m["n"].replace(" Mahallesi", "")
                d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=INK, outline=BG, width=2)
                if x > W - 330 and y < MAP_Y + 200:
                    y = MAP_Y + 215                                   # keep clear of the clock
                L_ = x < W - 280
                d.text((x + 12 if L_ else x - 12, y - 2), f"{nm}", font=F["lab"], fill=INK, anchor="ld" if L_ else "rd", stroke_width=3, stroke_fill=BG)
                d.text((x + 12 if L_ else x - 12, y + 2), f"{m['h']:.0f} odour hours a day", font=F["labs"], fill=ACC, anchor="la" if L_ else "ra", stroke_width=3, stroke_fill=BG)
        im = compose(v, h, "Where does İzmir's gulf smell go?", "21 July · around the inner gulf", labels=1 - u * 0.4,
                     cap=("The inner gulf's shores smell most often", "Karşıyaka and Konak · average of 12 sample days"), overlay=ov, t=T)
        save(im)
    im.save(OUT / "still_closeup.png")
    hl = ST["headline"]; lin = hl["linger_dense"][DAY]
    # D · outro
    ND = int(FPS * 4.4)
    last = crop(base2, ZOOM)
    for k in range(ND):
        a = ease(k / (FPS * 0.6)); T += 1 / FPS
        drift.step(17.5, 1 / FPS, warm_at(17.5))
        def ov(d):
            if k < 4:
                return
            d.rounded_rectangle([40, MAP_Y + 70, W - 40, MAP_Y + 900], 28, fill=(22, 30, 46, 245))
            d.text((W // 2, MAP_Y + 118), "İzmir · 21 July · modelled odour drift", font=F["sm"], fill=INK2, anchor="ma")
            d.text((W // 2, MAP_Y + 176), f"{hl['bld_4h_07_b']:,}", font=F["big"], fill=ACC, anchor="ma")
            d.text((W // 2, MAP_Y + 318), "buildings sit in the cloud for 4 h or more", font=F["sm"], fill=INK, anchor="ma")
            d.text((W // 2, MAP_Y + 390), f"{hl['gulf_share_07'] * 100:.0f}%", font=F["num"], fill=ACC, anchor="ma")
            d.text((W // 2, MAP_Y + 474), "of the odour over land comes from", font=F["sm"], fill=INK, anchor="ma")
            d.text((W // 2, MAP_Y + 508), "the gulf and its sewage-fed stream mouths", font=F["sm"], fill=INK, anchor="ma")
            d.text((W // 2, MAP_Y + 584), f"{hl['share_any_day'] * 100:.0f}%", font=F["num"], fill=ACC, anchor="ma")
            d.text((W // 2, MAP_Y + 668), "of buildings smell it on at least one", font=F["sm"], fill=INK, anchor="ma")
            d.text((W // 2, MAP_Y + 702), "of 12 sample days", font=F["sm"], fill=INK, anchor="ma")
            d.text((W // 2, MAP_Y + 790), "Any day, any hour, in 3D: barisparlatangiller.github.io", font=F["lab"], fill=INK2, anchor="ma")
            d.text((W // 2, MAP_Y + 830), "A scenario, not a measurement", font=F["lab"], fill=INK3, anchor="ma")
        im = compose(ZOOM, 17.5, "The invisible cloud over İzmir", "the gulf · wind · slopes · 323,318 buildings", labels=0.6 * (1 - a), clock=k < 4, overlay=ov, t=T, drift_a=1 - a * 0.7)
        save(im)
    im.save(OUT / "outro.png")
    cover.save(OUT / "cover.png")
    out = OUT / "day19_izmir_smell.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fr / "f%04d.jpg"), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-profile:v", "main", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    print(f"film: {n} frames, {n / FPS:.1f} s, {out.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # quick look at a few frames
        OUT.mkdir(parents=True, exist_ok=True)
        main.__globals__["FPS"] = 2
    main()
