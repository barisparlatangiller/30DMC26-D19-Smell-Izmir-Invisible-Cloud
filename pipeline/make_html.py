"""docs/index.html (EN) and docs/tr.html (TR) from one template. python pipeline/make_html.py"""
import json
from pathlib import Path

V = "9"
ST = json.loads(Path("docs/data/stats.json").read_text())
H = ST["headline"]
lin = ST["headline"]["linger_dense"]["07"]
GS = H["gulf_share_07"]; GMIN, GMAX = H["gulf_share_min"], H["gulf_share_max"]
pct = lambda x: f"{x * 100:.0f}%"
N4 = H["bld_4h_07_b"]

S = {
 "en": dict(
  title="İzmir's invisible cloud",
  desc="Hour by hour: where the smell of İzmir's inner gulf, wastewater plant and landfill drifts with the imbat sea breeze. A 3D odour-drift scenario over terrain, 323,000 buildings and 233,000 trees.",
  ogt="The invisible cloud over İzmir", ogd="Where does the smell go? A 3D odour-drift scenario for İzmir: wind, slopes, buildings and trees, hour by hour on 12 days of the year.",
  canvas="3D map of İzmir with a modelled odour cloud drifting over the city", load="Reading the wind…",
  eyebrow="#30DayMapChallenge · Day 19 · Smell · İzmir", h1="The invisible cloud over İzmir",
  lede="Sewage-fed streams and canals empty into the shallow <b>inner gulf</b>. On a hot July afternoon the <b>imbat</b>, the sea breeze from the north-west, picks up the smell of the water, the stream mouths, a <b>wastewater plant</b> and a <b>landfill</b> and pushes it into the city. Where does it go, hour by hour?",
  s1="buildings inside the cloud for 4 h or more on 21 July", s2="of the odour over land comes from the gulf and its stream mouths (21 July)",
  s3="of buildings get at least one odour hour on one of the 12 sample days",
  scen="Scenario · not a measurement", day="Day", hour="Hour", play="Play", pause="Pause", wb="With buildings", wo="Bare terrain",
  wbh="Buildings slow the wind near the ground, so the cloud lingers longer in dense blocks: LINGER more odour there on 21 July.",
  layers="Layers", lOd="Odour cloud", lOdE="modelled odour index", lPa="Drift", lPaE="where the air carries it", lBd="Buildings", lBdE="323,318 · height from OSM / GHSL",
  lTr="Trees", lTrE="233,045 · OSM trees, rows and woods", lSl="Slope", lSlE="steeper = lighter", lSo="Sources", lSoE="candidate odour sources",
  relief="Relief", cloud="Cloud", views="Views", vAll="Whole gulf", vCigli="Çiğli", vKonak="Konak", vBornova="Bornova",
  srcT="Sources &amp; strength · this day", srcH="Pale bar: share of the odour each type puts into the air (model weights). Strong bar and %: share of the odour that reaches land. The gulf water releases a lot, but much of it stays over the sea; the stream mouths sit on the shore.",
  chart="Land under the cloud, km² · by hour", dist="Districts · odour hours per day", disth="Average of the 12 sample days, per building, with buildings. Share = buildings with 4 h or more on an average day.", rank="Neighbourhoods that smell most often", rankh="Average odour hours per day, 12 sample days, with buildings. Click to fly there.",
  howto="How to read this map",
  h_1="The <b>haze</b> is the modelled odour cloud near the ground. Its <b>colour shows where it comes from</b>: yellow from the gulf water, orange from the stream and canal mouths, sage from the wastewater plant, mauve from the landfill. Thicker and brighter means stronger.",
  h_2="<b>Symbols</b> mark the sources; a bigger symbol is a stronger source. Small wave symbols are the 11 gulf monitoring stations (hover for the sewage value). <b>Moving streaks</b> show where the air carries the smell this hour, in the same colours. <b>Murky olive water</b> marks where the sewage signal is highest.",
  h_3="Pick a <b>day</b> and an <b>hour</b>. In summer the imbat blows from the north-west in the afternoon; at night the wind drops and the air slides down the slopes to the gulf.",
  h_4="<b>Click</b> anywhere: odour now, odour hours that day, wind and the neighbourhood.",
  method="Method, data &amp; limits",
  m_wind="<b>Wind.</b> Hourly 10 m wind, temperature and humidity for the 21st of every month, Nov 2025 – Oct 2026 (Open-Meteo, one point in the gulf). On the map the wind slows and turns where it would have to climb a steep slope, speeds up over open ridges and the sea, and drains down the slopes on calm nights.",
  m_bld="<b>Buildings.</b> 323,318 OSM footprints. Heights from OSM tags where mapped (282), otherwise from GHSL GHS-BUILT-H 2018 (100 m). In the “with buildings” scenario dense, tall blocks slow the wind near the ground to 40–70% of the open value.",
  m_src="<b>The gulf.</b> The water near the shore releases odour in proportion to the sewage signal measured by İzmir Metropolitan Municipality at 11 gulf stations (median faecal coliform and E. coli, 2012–2026, about 340 samples per station). The signal is spread over the water by distance and fades 1–2 km offshore; it is highest off Meles, Bayraklı, Karşıyaka pier and Konak. A warmer sea makes it stronger: hourly sea surface temperature from Open-Meteo Marine, from about 0.3× at 14 °C in winter to 1.7× at 25 °C in July. <b>Other sources</b>, relative weights, not emissions: stream and canal mouths that carry sewage overflow (Meles 1.0, six others 0.5–0.8), Çiğli wastewater plant (0.8), Harmandalı landfill (0.8), Karşıyaka transfer station (0.3).",
  m_mod="<b>Model.</b> Particles are released every hour, carried by the wind in 1-minute steps with turbulent spread, and fade over about an hour. The odour index is the particle density per 100 m cell, scaled 0–1 over all days. “Odour hour” = index ≥ 0.15.",
  limits="Limits",
  l_1="This is a <b>scenario</b>: a way to see how wind, slopes and buildings move air. It is not an odour measurement, an H₂S map or a forecast. There are no public emission rates for these sources, so all sources use relative weights.",
  l_2="One wind point for the whole area, a simple terrain rule instead of a flow model (no CFD), building heights partly estimated. The gulf's smell depends on water temperature, oxygen and algae, which are only proxied here by the sea surface temperature of one model cell. Coliform counts show sewage in the water, not the smell itself: they are used only to say where along the shore the water is dirtiest.",
  l_3="Terrain: Copernicus DEM GLO-30. Trees are OSM trees, tree rows and points placed in mapped woods and orchards.",
  sources="Sources",
  r_1="Wind &amp; weather: <a href=\"https://open-meteo.com/\">Open-Meteo</a> historical API, 38.49 N 27.11 E (CC BY 4.0).",
  r_2="Terrain: Copernicus DEM GLO-30, © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA.",
  r_3="Building height: Pesaresi, M., Politis, P. (2023). GHS-BUILT-H R2023A, European Commission JRC.",
  r_4="Buildings, trees, streams, roads, neighbourhoods: © OpenStreetMap contributors, ODbL.",
  r_7="Sea surface temperature: <a href=\"https://open-meteo.com/en/docs/marine-weather-api\">Open-Meteo Marine</a>, hourly (CC BY 4.0).",
  r_6="District boundaries: geoBoundaries ADM2 Türkiye (Runfola et al. 2020), from OpenStreetMap, ODbL.",
  r_5="Gulf water quality (faecal coliform, E. coli, 11 stations, 2012–2026): İzmir Büyükşehir Belediyesi Açık Veri Portalı.",
  foot="Barış Parlatangiller · <a href=\"https://barisparlatangiller.github.io/\">all 30 maps</a> · <a href=\"https://github.com/barisparlatangiller/30DMC26-D19-Smell-Izmir-Invisible-Cloud\">code &amp; method</a> · built with AI assistance (Claude, Anthropic)",
  other="tr.html", otherL="TR", otherT="Türkçe",
 ),
 "tr": dict(
  title="İzmir'in görünmez bulutu",
  desc="Saat saat: İzmir iç körfezinin, atıksu arıtmanın ve çöplüğün kokusu imbatla nereye gidiyor? Arazi, 323.000 bina ve 233.000 ağaç üzerinde 3B koku yayılım senaryosu.",
  ogt="İzmir'in üzerindeki görünmez bulut", ogd="Koku nereye gidiyor? İzmir için 3B koku yayılım senaryosu: rüzgâr, eğim, binalar ve ağaçlar, yılın 12 gününde saat saat.",
  canvas="İzmir'in 3B haritası; modellenmiş koku bulutu kentin üzerinde sürükleniyor", load="Rüzgâr okunuyor…",
  eyebrow="#30DayMapChallenge · Gün 19 · Koku · İzmir", h1="İzmir'in üzerindeki görünmez bulut",
  lede="Kanalizasyon karışan dereler ve kanallar sığ <b>iç körfeze</b> dökülüyor. Sıcak bir temmuz öğleden sonrası kuzeybatıdan esen <b>imbat</b>, suyun, dere ağızlarının, bir <b>atıksu arıtma tesisinin</b> ve bir <b>çöplüğün</b> kokusunu alıp kente taşıyor. Koku saat saat nereye gidiyor?",
  s1="bina 21 Temmuz'da 4 saat veya daha uzun süre bulutun içinde", s2="karadaki kokunun körfezden ve dere ağızlarından geliyor (21 Temmuz)",
  s3="binalar, 12 örnek günün en az birinde en az bir saat koku alıyor",
  scen="Senaryo · ölçüm değil", day="Gün", hour="Saat", play="Oynat", pause="Durdur", wb="Binalarla", wo="Çıplak arazi",
  wbh="Binalar zemine yakın rüzgârı yavaşlatır; bulut yoğun yapı adalarında daha uzun kalır: 21 Temmuz'da orada LINGER daha fazla koku.",
  layers="Katmanlar", lOd="Koku bulutu", lOdE="modellenmiş koku indeksi", lPa="Sürüklenme", lPaE="havanın kokuyu taşıdığı yön", lBd="Binalar", lBdE="323.318 · yükseklik OSM / GHSL",
  lTr="Ağaçlar", lTrE="233.045 · OSM ağaçları, ağaç sıraları ve korular", lSl="Eğim", lSlE="dik = açık renk", lSo="Kaynaklar", lSoE="olası koku kaynakları",
  relief="Rölyef", cloud="Bulut", views="Görünümler", vAll="Tüm körfez", vCigli="Çiğli", vKonak="Konak", vBornova="Bornova",
  srcT="Kaynaklar ve güçleri · bu gün", srcH="Soluk çubuk: her türün havaya verdiği koku payı (model ağırlıkları). Koyu çubuk ve %: karaya ulaşan kokunun payı. Körfez suyu çok koku verir ama bunun büyük kısmı denizin üzerinde kalır; dere ağızları ise tam kıyıdadır.",
  chart="Bulutun altındaki kara, km² · saat saat", dist="İlçeler · günde koku saati", disth="12 örnek günün ortalaması, bina başına, binalarla. Oran = ortalama bir günde 4 saat veya daha fazla koku alan binalar.", rank="En sık koku alan mahalleler", rankh="12 örnek günde günlük ortalama koku saati, binalarla. Tıklayınca oraya gider.",
  howto="Harita nasıl okunur",
  h_1="<b>Pus</b>, zemine yakın modellenmiş koku bulutu. <b>Rengi kokunun nereden geldiğini gösterir</b>: sarı körfez suyundan, turuncu dere ve kanal ağızlarından, adaçayı yeşili atıksu arıtmadan, mor çöplükten. Daha kalın ve parlak = daha güçlü.",
  h_2="<b>Semboller</b> kaynakları gösterir; büyük sembol güçlü kaynaktır. Küçük dalga sembolleri 11 körfez ölçüm istasyonudur (üzerine gelince kanalizasyon değeri). <b>Hareketli izler</b> havanın kokuyu bu saatte nereye taşıdığını aynı renklerle gösterir. <b>Bulanık zeytin rengi su</b> kanalizasyon izinin en yüksek olduğu yerlerdir.",
  h_3="Bir <b>gün</b> ve <b>saat</b> seçin. Yazın imbat öğleden sonra kuzeybatıdan eser; gece rüzgâr düşer ve hava yamaçlardan körfeze doğru süzülür.",
  h_4="Herhangi bir yere <b>tıklayın</b>: şu anki koku, o gün kaç saat koku, rüzgâr ve mahalle.",
  method="Yöntem, veri ve sınırlar",
  m_wind="<b>Rüzgâr.</b> Kasım 2025 – Ekim 2026 arasında her ayın 21'i için saatlik 10 m rüzgâr, sıcaklık ve nem (Open-Meteo, körfezde tek nokta). Haritada rüzgâr dik bir yamaca tırmanması gereken yerde yavaşlar ve yön değiştirir, açık sırtlarda ve denizde hızlanır, sakin gecelerde yamaçlardan aşağı süzülür.",
  m_bld="<b>Binalar.</b> 323.318 OSM bina izi. Yükseklik OSM etiketinden (282 bina), yoksa GHSL GHS-BUILT-H 2018'den (100 m). “Binalarla” senaryosunda yoğun ve yüksek yapı adaları zemine yakın rüzgârı açık alana göre %40–70'e düşürür.",
  m_src="<b>Körfez.</b> Kıyıya yakın su, İzmir Büyükşehir Belediyesi'nin 11 körfez istasyonunda ölçtüğü kanalizasyon izine göre koku verir (fekal koliform ve E. coli medyanı, 2012–2026, istasyon başına yaklaşık 340 örnek). Bu iz mesafeye göre suya dağıtılır ve kıyıdan 1–2 km açıkta söner; en yüksek değerler Meles, Bayraklı, Karşıyaka iskelesi ve Konak açıklarında. Deniz ısındıkça etki artar: Open-Meteo Marine saatlik deniz yüzeyi sıcaklığı; kışın 14 °C'de yaklaşık 0,3×, temmuzda 25 °C'de 1,7×. <b>Diğer kaynaklar</b>, göreli ağırlık, emisyon değil: kanalizasyon taşkını taşıyan dere ve kanal ağızları (Meles 1,0, altı dere daha 0,5–0,8), Çiğli Atıksu Arıtma (0,8), Harmandalı Katı Atık (0,8), Karşıyaka transfer istasyonu (0,3).",
  m_mod="<b>Model.</b> Her saat parçacıklar salınır, rüzgârla 1 dakikalık adımlarla ve türbülanslı yayılımla taşınır, yaklaşık bir saatte söner. Koku indeksi 100 m hücre başına parçacık yoğunluğudur, tüm günler için 0–1 ölçeklenmiştir. “Koku saati” = indeks ≥ 0,15.",
  limits="Sınırlar",
  l_1="Bu bir <b>senaryo</b>: rüzgârın, eğimin ve binaların havayı nasıl taşıdığını görmenin bir yolu. Koku ölçümü, H₂S haritası ya da tahmin değildir. Bu kaynaklar için kamuya açık emisyon verisi olmadığından tüm kaynaklar göreli ağırlıkla modellenmiştir.",
  l_2="Tüm alan için tek rüzgâr noktası, akış modeli yerine basit bir arazi kuralı (CFD yok), bina yükseklikleri kısmen tahmini. Körfezin kokusu su sıcaklığına, oksijene ve alglere bağlıdır; burada yalnızca tek bir model hücresinin deniz yüzeyi sıcaklığıyla temsil ediliyor. Koliform sayıları kokuyu değil, sudaki kanalizasyonu gösterir: burada yalnızca kıyının neresinde suyun en kirli olduğunu belirlemek için kullanıldı.",
  l_3="Arazi: Copernicus DEM GLO-30. Ağaçlar OSM ağaçları, ağaç sıraları ve haritalanmış koru ve bahçelere yerleştirilen noktalardır.",
  sources="Kaynaklar",
  r_1="Rüzgâr ve hava: <a href=\"https://open-meteo.com/\">Open-Meteo</a> geçmiş veri API'si, 38,49 K 27,11 D (CC BY 4.0).",
  r_2="Arazi: Copernicus DEM GLO-30, © DLR e.V. 2010–2014 ve © Airbus Defence and Space GmbH 2014–2018, Avrupa Birliği ve ESA tarafından COPERNICUS kapsamında sağlanmıştır.",
  r_3="Bina yüksekliği: Pesaresi, M., Politis, P. (2023). GHS-BUILT-H R2023A, Avrupa Komisyonu JRC.",
  r_4="Binalar, ağaçlar, dereler, yollar, mahalleler: © OpenStreetMap katkıcıları, ODbL.",
  r_7="Deniz yüzeyi sıcaklığı: <a href=\"https://open-meteo.com/en/docs/marine-weather-api\">Open-Meteo Marine</a>, saatlik (CC BY 4.0).",
  r_6="İlçe sınırları: geoBoundaries ADM2 Türkiye (Runfola vd. 2020), OpenStreetMap kaynaklı, ODbL.",
  r_5="Körfez su kalitesi (fekal koliform, E. coli, 11 istasyon, 2012–2026): İzmir Büyükşehir Belediyesi Açık Veri Portalı.",
  foot="Barış Parlatangiller · <a href=\"https://barisparlatangiller.github.io/\">30 haritanın tümü</a> · <a href=\"https://github.com/barisparlatangiller/30DMC26-D19-Smell-Izmir-Invisible-Cloud\">kod ve yöntem</a> · yapay zekâ desteğiyle hazırlandı (Claude, Anthropic)",
  other="index.html", otherL="EN", otherT="English",
 )}

def num(x, lang):
    s = f"{x:,}"
    return s.replace(",", ".") if lang == "tr" else s

for lang, t in S.items():
    s1 = num(N4, lang)
    s2 = pct(GS) if lang == "en" else "%" + f"{GS * 100:.0f}"
    s3 = pct(H["share_any_day"]) if lang == "en" else "%" + f"{H['share_any_day'] * 100:.0f}"
    t = dict(t); t["wbh"] = t["wbh"].replace("LINGER", f"+{(lin - 1) * 100:.0f}%" if lang == "en" else f"+%{(lin - 1) * 100:.0f}")
    html = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t['title']}</title>
<meta name="description" content="{t['desc']}">
<meta property="og:title" content="{t['ogt']}">
<meta property="og:description" content="{t['ogd']}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css?v={V}">
<script type="importmap">{{"imports":{{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}}}</script>
</head>
<body>
<div class="app">
  <main class="mapwrap">
    <canvas id="c" aria-label="{t['canvas']}"></canvas>
    <div id="labels" aria-hidden="true"></div>
    <div class="card legend-card" id="legend"></div>
    <div class="card mapbar">
      <button class="pill" data-v="all">{t['vAll']}</button>
      <button class="pill" data-v="cigli">{t['vCigli']}</button>
      <button class="pill" data-v="konak">{t['vKonak']}</button>
      <button class="pill" data-v="bornova">{t['vBornova']}</button>
      <a class="pill lang" href="{t['other']}" title="{t['otherT']}">{t['otherL']}</a>
    </div>
    <div class="card timebar" id="timebar">
      <button class="play" id="bPlay" aria-label="{t['play']}">▶</button>
      <div class="tb-main">
        <div class="tb-top"><b class="mono" id="tClock">15:00</b><span id="tWind"></span><span class="tb-tag">{t['scen']}</span></div>
        <input type="range" id="rHour" min="0" max="23.99" step="0.01" value="15" aria-label="{t['hour']}">
        <div class="days" id="days" role="tablist" aria-label="{t['day']}"></div>
      </div>
    </div>
    <div id="load" class="loading">{t['load']}</div>
  </main>

  <aside class="panel card" id="panel">
    <header class="head">
      <p class="eyebrow">{t['eyebrow']}</p>
      <h1>{t['h1']}</h1>
      <p class="lede">{t['lede']}</p>
    </header>
    <div class="stats">
      <div class="st"><b class="mono">{s1}</b><span>{t['s1']}</span></div>
      <div class="st"><b class="mono">{s2}</b><span>{t['s2']}</span></div>
      <div class="st"><b class="mono">{s3}</b><span>{t['s3']}</span></div>
    </div>

    <section class="block" id="detail" hidden></section>

    <section class="block">
      <div class="seg seg2" id="scenSeg"><button data-s="b" class="on">{t['wb']}</button><button data-s="o">{t['wo']}</button></div>
      <p class="hint">{t['wbh']}</p>
    </section>

    <section class="block">
      <h2 class="label">{t['srcT']}</h2>
      <ul class="srcs" id="srcs"></ul>
      <p class="hint">{t['srcH']}</p>
    </section>

    <section class="block">
      <h2 class="label">{t['chart']}</h2>
      <canvas id="chart" width="640" height="150"></canvas>
    </section>

    <section class="block">
      <h2 class="label">{t['layers']}</h2>
      <div class="toggles">
        <label><input type="checkbox" id="tOd" checked><span>{t['lOd']}</span><em>{t['lOdE']}</em></label>
        <label><input type="checkbox" id="tPa" checked><span>{t['lPa']}</span><em>{t['lPaE']}</em></label>
        <label><input type="checkbox" id="tBd" checked><span>{t['lBd']}</span><em>{t['lBdE']}</em></label>
        <label><input type="checkbox" id="tTr" checked><span>{t['lTr']}</span><em>{t['lTrE']}</em></label>
        <label><input type="checkbox" id="tSl"><span>{t['lSl']}</span><em>{t['lSlE']}</em></label>
        <label><input type="checkbox" id="tSo" checked><span>{t['lSo']}</span><em>{t['lSoE']}</em></label>
      </div>
      <div class="sl"><span>{t['cloud']}</span><input type="range" id="rOp" min="0.2" max="1" step="0.01" value="0.85"><b class="mono" id="opO">85%</b></div>
      <div class="sl"><span>{t['relief']}</span><input type="range" id="rEx" min="1" max="3" step="0.1" value="1.6"><b class="mono" id="exv">1.6×</b></div>
    </section>

    <section class="block">
      <h2 class="label">{t['dist']}</h2>
      <ul class="rank" id="dist"></ul>
      <p class="hint">{t['disth']}</p>
    </section>

    <section class="block">
      <h2 class="label">{t['rank']}</h2>
      <ul class="rank" id="rank"></ul>
      <p class="hint">{t['rankh']}</p>
    </section>

    <details class="howto" open>
      <summary>{t['howto']}</summary>
      <ol><li>{t['h_1']}</li><li>{t['h_2']}</li><li>{t['h_3']}</li><li>{t['h_4']}</li></ol>
    </details>
    <details class="howto">
      <summary>{t['method']}</summary>
      <p>{t['m_wind']}</p><p>{t['m_bld']}</p><p>{t['m_src']}</p><p>{t['m_mod']}</p>
    </details>
    <details class="howto">
      <summary>{t['limits']}</summary>
      <p>{t['l_1']}</p><p>{t['l_2']}</p><p>{t['l_3']}</p>
    </details>
    <details class="howto">
      <summary>{t['sources']}</summary>
      <ol class="refs"><li>{t['r_1']}</li><li>{t['r_2']}</li><li>{t['r_3']}</li><li>{t['r_4']}</li><li>{t['r_5']}</li><li>{t['r_6']}</li><li>{t['r_7']}</li></ol>
    </details>
    <footer class="foot"><p>{t['foot']}</p></footer>
  </aside>
</div>
<div id="film" hidden><div id="fq"></div><div id="fc"></div><div id="fa"></div><div id="fs"></div><div id="fclock"></div></div>
<script type="module" src="app.js?v={V}"></script>
</body>
</html>
"""
    Path("docs/" + ("index.html" if lang == "en" else "tr.html")).write_text(html)
print("ok")
