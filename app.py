#!/usr/bin/env python3
"""Panel de Walter - solo biblioteca estandar de Python 3."""
import json, re, urllib.parse, ssl, time, html, threading, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from email.utils import parsedate_to_datetime

import os
PORT = int(os.environ.get("PORT", 8000))
UA = {"User-Agent": "Mozilla/5.0 (WalterDashboard; contacto local)", "Accept": "*/*"}
CTX = ssl.create_default_context()
GN = "https://news.google.com/rss/search?q={}&hl={}"

NEWS = {  # cada fuente: lista de URLs de respaldo
 "Fox News": ["https://moxie.foxnews.com/google-publisher/latest.xml"],
 "CNN": ["http://rss.cnn.com/rss/money_latest.rss", GN.format("site:cnn.com", "en-US&gl=US&ceid=US:en")],
 "ABC News": ["https://feeds.abcnews.com/abcnews/moneyheadlines", "https://abcnews.go.com/abcnews/topstories"],
 "Univision": [GN.format("site:univision.com", "es-419&gl=US&ceid=US:es-419")],
}
ECUADOR = {
 "Google Noticias: Guayaquil": [GN.format("Guayaquil", "es-419&gl=EC&ceid=EC:es-419")],
 "El Universo": ["https://www.eluniverso.com/arc/outboundfeeds/rss/?outputType=xml"],
 "Primicias": ["https://www.primicias.ec/feed/", GN.format("site:primicias.ec+Guayaquil", "es-419&gl=EC&ceid=EC:es-419")],
}
ECON_KW = ["econom", "market", "mercado", "stock", "bolsa", "dow", "nasdaq", "s&p", "inflation", "inflaci",
 "fed", "reserva federal", "interest rate", "tasa", "oil", "petróleo", "petroleo", "jobs", "empleo", "desempleo",
 "unemployment", "gdp", "pib", "tariff", "arancel", "recession", "recesi", "dollar", "dólar", "price", "precio",
 "bank", "banco", "trade", "comercio", "wall street", "crypto", "bitcoin", "gas", "gasolina", "debt", "deuda"]
# Reglas de alertas: agrega nuevas lineas (nombre, [palabras clave], nivel)
ALERT_RULES = [
 ("Reserva Federal / tasas", ["fed ", "federal reserve", "reserva federal", "interest rate", "tasas de interés", "powell"], "alta"),
 ("Inflación", ["inflation", "inflación", "cpi", "consumer price"], "alta"),
 ("Petróleo / energía", ["oil", "petróleo", "opec", "opep", "crude", "gasolina", "gas prices"], "media"),
 ("Empleo", ["jobs report", "unemployment", "desempleo", "payroll", "layoffs", "despidos", "empleo"], "media"),
 ("Mercados", ["stock market", "dow", "nasdaq", "s&p 500", "wall street", "bolsa", "sell-off"], "media"),
 ("Recesión / aranceles", ["recession", "recesión", "tariff", "arancel", "trade war"], "alta"),
]

def fetch(url, t=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=t, context=CTX) as r:
        return r.read()

def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()

def parse_feed(data, source):
    root = ET.fromstring(data); out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        g = lambda n: next((c for c in it if c.tag.split("}")[-1] == n), None)
        t, l, d = g("title"), g("link"), next((x for x in (g("pubDate"), g("updated"), g("published")) if x is not None), None)
        link = (l.text or l.get("href", "")) if l is not None else ""
        ts = 0
        if d is not None and d.text:
            try: ts = parsedate_to_datetime(d.text).timestamp()
            except Exception:
                try: from datetime import datetime; ts = datetime.fromisoformat(d.text.replace("Z", "+00:00")).timestamp()
                except Exception: pass
        out.append({"title": clean(t.text if t is not None else ""), "link": (link or "").strip(), "source": source, "ts": ts})
    return out

def get_feed(source, urls):
    err = None
    for u in urls:
        try:
            items = parse_feed(fetch(u), source)
            if items: return items, None
        except Exception as e: err = str(e)
    return [], f"{source}: {err or 'sin datos'}"

def econ_score(title):
    t = title.lower(); return sum(1 for k in ECON_KW if k in t)

def feeds_section(srcs, prioritize=False, per=8):
    items, errs = [], []
    key = (lambda i: (-min(i["econ"], 3), -i["ts"])) if prioritize else (lambda i: -i["ts"])
    with ThreadPoolExecutor(6) as ex:
        for res, err in ex.map(lambda kv: get_feed(*kv), srcs.items()):
            for i in res: i["econ"] = econ_score(i["title"])
            res.sort(key=key)
            items += res[:per]  # mismo numero por fuente
            if err: errs.append(err)
    items.sort(key=key)
    return {"items": items, "errors": errs}

def jget(url):
    return json.loads(fetch(url))

def airport():
    out = {"faa": None, "weather": None, "alerts": [], "errors": [],
           "links": {"Estado de vuelos FLL (oficial)": "https://www.fll.net/flight-status",
                     "Broward - vuelos": "https://www.broward.org/Airport/FlightInfo/Pages/default.aspx",
                     "FlightAware FLL": "https://www.flightaware.com/live/airport/KFLL"}}
    try:
        x = ET.fromstring(fetch("https://nasstatus.faa.gov/api/airport-status-information"))
        txt = ET.tostring(x, encoding="unicode")
        hits = [clean(ET.tostring(e, encoding="unicode")) for e in x.iter() if "FLL" in "".join(e.itertext()) and len(list(e)) and e.tag in ("Delay", "Ground_Stop", "Program", "Airport", "Ground_Delay")]
        out["faa"] = {"fll_afectado": "FLL" in txt, "detalle": hits[:5],
                      "updated": (x.findtext("Update_Time") or "")}
    except Exception as e: out["errors"].append(f"FAA: {e}")
    try:
        p = jget("https://api.weather.gov/points/26.07,-80.15")["properties"]
        per = jget(p["forecast"])["properties"]["periods"][:4]
        hr = jget(p["forecastHourly"])["properties"]["periods"][:12]
        out["weather"] = {"periods": [{"name": q["name"], "temp": f'{q["temperature"]}°{q["temperatureUnit"]}', "text": q["detailedForecast"]} for q in per],
            "hourly": [{"time": q["startTime"][11:16], "temp": q["temperature"], "rain": (q.get("probabilityOfPrecipitation") or {}).get("value"), "short": q["shortForecast"]} for q in hr]}
    except Exception as e: out["errors"].append(f"Clima NWS: {e}")
    try:
        a = jget("https://api.weather.gov/alerts/active?point=26.07,-80.15")["features"]
        out["alerts"] = [{"event": f["properties"]["event"], "headline": f["properties"]["headline"]} for f in a]
    except Exception as e: out["errors"].append(f"Alertas NWS: {e}")
    return out


SOFLA = {"Broward", "Miami-Dade", "Palm Beach", "Monroe", "Collier", "Martin", "St. Lucie"}
ROUTES = [("I-95", ["i-95"]), ("I-595", ["i-595"]), ("Florida Turnpike", ["turnpike", "sr-91", "sr 91", "sr-821"]),
          ("US-1", ["us-1", "us 1", "federal hwy"]), ("I-75", ["i-75", "alligator alley"])]

def traffic():
    out = {"by_route": {}, "other": [], "total_sofla": 0, "errors": [],
           "links": {"Mapa en vivo FL511": "https://fl511.com/map",
                     "Google Maps tráfico (Fort Lauderdale)": "https://www.google.com/maps/@26.12,-80.17,11z/data=!5m1!1e1",
                     "Waze mapa en vivo": "https://www.waze.com/live-map/directions?latlng=26.12%2C-80.17"}}
    rows = []
    try:
        start = 0
        while start < 1000:
            q = urllib.parse.quote(json.dumps({"columns": [], "start": start, "length": 100}))
            d = jget("https://fl511.com/List/GetData/traffic?query=" + q)
            rows += d.get("data", []); start += 100
            if start >= d.get("recordsTotal", 0): break
    except Exception as e: out["errors"].append(f"FL511: {e}")
    for r in rows:
        if r.get("county") not in SOFLA: continue
        out["total_sofla"] += 1
        it = {"type": r.get("type"), "road": r.get("roadwayName"), "dir": r.get("direction"), "county": r.get("county"),
              "desc": clean(r.get("description", "")).split("Comments:")[0][:220], "closure": r.get("isFullClosure"),
              "updated": r.get("lastUpdated"), "severity": r.get("severity")}
        txt = (str(r.get("roadwayName")) + " " + str(r.get("locationDescription")) + " " + it["desc"]).lower()
        for name, kws in ROUTES:
            if any(k in txt for k in kws):
                out["by_route"].setdefault(name, []).append(it); break
        else: out["other"].append(it)
    out["routes"] = [n for n, _ in ROUTES]
    return out

def fa_board(h, board):
    i = h.find(board + "-board")
    if i < 0: return []
    t = h[i:h.find("</table>", i)]; res = []
    for r in re.findall(r"<tr class=\"smallrow.*?</tr>", t, re.S):
        c = [html.unescape(re.sub(r"<[^>]+>|\s+", " ", x)).strip() for x in re.findall(r"<td.*?</td>", r, re.S)]
        if len(c) >= 6: res.append({"flight": c[0], "type": c[1], "place": c[2], "dep": c[3], "arr": c[5]})
    return res

def opensky():
    import math
    try:
        d = jget("https://opensky-network.org/api/states/all?lamin=25.85&lomin=-80.45&lamax=26.30&lomax=-79.85")
        st = d.get("states") or []
        air = [x for x in st if not x[8]]
        def km(x): return math.hypot((x[6] - 26.07) * 111, (x[5] + 80.15) * 111 * math.cos(math.radians(26.07)))
        landing = [x for x in air if x[5] and x[6] and km(x) < 25 and 30 < (x[7] or 99999) < 3000 and (x[11] or 0) < 0]
        return {"ok": True, "total_area": len(st), "airborne": len(air), "landing": len(landing),
                "landing_list": [(x[1] or x[0]).strip() + f" {int(x[7])} m" for x in landing][:10], "time": d.get("time")}
    except Exception as e:
        return {"ok": False, "error": f"OpenSky no respondió: {e}"}

def flights():
    out = {"arrivals": [], "departures": [], "enroute": [], "scheduled": [], "errors": [], "source": "FlightAware (página pública KFLL)", "live": opensky()}
    try:
        h = fetch("https://www.flightaware.com/live/airport/KFLL").decode("utf-8", "replace")
        for b in ("arrivals", "departures", "enroute", "scheduled"): out[b] = fa_board(h, b)[:15]
        if not any(out[b] for b in ("arrivals", "departures")): out["errors"].append("FlightAware: no se pudo leer la tabla")
    except Exception as e: out["errors"].append(f"FlightAware: {e}")
    return out

def cruises():
    out = {"today": [], "upcoming": [], "error": None, "source": "CruiseMapper (calendario programado)"}
    try:
        from datetime import datetime, timedelta
        h = fetch("https://www.cruisemapper.com/ports/fort-lauderdale-port-44").decode("utf-8", "replace")
        i = h.find("portItemSchedule"); t = h[i:h.find("</table>", i)]
        today = datetime.now().date()
        for r in re.findall(r"<tr.*?</tr>", t, re.S):
            c = [html.unescape(re.sub(r"<[^>]+>|\s+", " ", x)).strip() for x in re.findall(r"<td.*?</td>", r, re.S)]
            if len(c) < 4: continue
            try: d = datetime.strptime(" ".join(c[0].split()[:3]), "%d %B, %Y").date()
            except Exception: continue
            fix = lambda v: v if re.fullmatch(r"\d\d:\d\d", v) else "—"
            it = {"date": d.isoformat(), "ship": c[1], "arr": fix(c[2]), "dep": fix(c[3])}
            if d == today: out["today"].append(it)
            elif today < d <= today + timedelta(days=7): out["upcoming"].append(it)
    except Exception as e: out["error"] = f"CruiseMapper: {e}"
    return out

def maritime():
    out = {"forecast": "", "alerts": [], "news": [], "errors": [],
           "links": {"Mapa AIS - MarineTraffic (Port Everglades)": "https://www.marinetraffic.com/en/ais/home/centerx:-80.12/centery:26.09/zoom:13",
                     "Mapa AIS - VesselFinder": "https://www.vesselfinder.com/?p=USPEF001",
                     "Calendario de cruceros Port Everglades": "https://www.porteverglades.net/cruise/cruise-schedule/",
                     "CruiseMapper - Port Everglades": "https://www.cruisemapper.com/ports/fort-lauderdale-port-everglades-port-75"}}
    try:
        t = fetch("https://tgftp.nws.noaa.gov/data/forecasts/marine/coastal/am/amz651.txt").decode("utf-8", "replace")
        out["forecast"] = t.split("$$")[0].strip()[-2500:]
    except Exception as e: out["errors"].append(f"Pronóstico marino: {e}")
    try:
        a = jget("https://api.weather.gov/alerts/active?zone=AMZ651")["features"]
        out["alerts"] = [{"event": f["properties"]["event"], "headline": f["properties"]["headline"]} for f in a]
    except Exception as e: out["errors"].append(f"Alertas marinas: {e}")
    r, err = get_feed("Noticias Port Everglades", [GN.format("%22Port+Everglades%22", "en-US&gl=US&ceid=US:en")])
    r.sort(key=lambda i: -i["ts"]); out["news"] = r[:8]
    if err: out["errors"].append(err)
    out["cruises"] = cruises()
    if out["cruises"]["error"]: out["errors"].append(out["cruises"]["error"])
    out["ais"] = ("Conteo de barcos en vivo: no disponible. Probamos fuentes AIS públicas (VesselFinder, MyShipTracking, AISHub) "
                  "y todas requieren clave o bloquean el acceso automático. Usa el mapa AIS en vivo (enlace).")
    return out

def events():
    out = {"items": [], "errors": [], "links": {"Visit Lauderdale - eventos": "https://www.visitlauderdale.com/events/",
           "Ciudad de Fort Lauderdale - eventos": "https://www.fortlauderdale.gov/government/departments-a-h/parks-recreation/special-events",
           "Eventbrite Fort Lauderdale": "https://www.eventbrite.com/d/fl--fort-lauderdale/events/"}}
    try:
        h = fetch("https://www.eventbrite.com/d/fl--fort-lauderdale/events/").decode("utf-8", "replace")
        for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try: d = json.loads(blk)
            except Exception: continue
            lst = d.get("itemListElement", []) if isinstance(d, dict) else []
            for e in lst:
                it = e.get("item", e)
                if it.get("name"):
                    out["items"].append({"title": clean(it["name"]), "link": it.get("url", ""), "date": (it.get("startDate") or "")[:16].replace("T", " "),
                        "place": ((it.get("location") or {}).get("name") or ""), "source": "Eventbrite"})
    except Exception as e: out["errors"].append(f"Eventbrite: {e}")
    if len(out["items"]) < 5:
        r, err = get_feed("Google Noticias", [GN.format("Fort+Lauderdale+events+this+week", "en-US&gl=US&ceid=US:en")])
        r.sort(key=lambda i: -i["ts"]); out["items"] += r[:10]
        if err: out["errors"].append(err)
    out["items"].sort(key=lambda i: i.get("date") or "9")
    return out

def alerts(all_items):
    res = []
    for name, kws, lvl in ALERT_RULES:
        m = [i for i in all_items if any(k in (" " + i["title"].lower() + " ") for k in kws)]
        m.sort(key=lambda i: -i["ts"])
        if m: res.append({"rule": name, "level": lvl, "count": len(m), "items": m[:4]})
    return {"rules": [r[0] for r in ALERT_RULES], "matches": res}


INTL = {"Casa Blanca": "%22White+House%22", "Donald Trump": "Donald+Trump", "Europa": "Europa+noticias",
        "China": "China", "Japón": "Jap%C3%B3n", "Asia": "Asia+noticias", "Rusia": "Rusia"}

def intl():
    def one(kv):
        name, q = kv
        r, err = get_feed(name, [GN.format(q + "+when:2d", "es-419&gl=US&ceid=US:es-419")])
        return name, r[:6], err   # Google ordena por relevancia = historias clave
    out = {"topics": {}, "errors": []}
    with ThreadPoolExecutor(7) as ex:
        for name, r, err in ex.map(one, INTL.items()):
            out["topics"][name] = r
            if err: out["errors"].append(err)
    out["order"] = list(INTL)
    return out

def national():
    r, err = get_feed("Google Noticias EE.UU.", ["https://news.google.com/rss/headlines/section/topic/NATION?hl=es-419&gl=US&ceid=US:es-419",
                                                 GN.format("Estados+Unidos+noticias+when:1d", "es-419&gl=US&ceid=US:es-419")])
    return {"items": r[:15], "errors": [err] if err else []}

def noticias():
    out = {"florida": [], "top": [], "errors": []}
    r, e = get_feed("Google Noticias: Florida", [GN.format("Florida+when:1d", "es-419&gl=US&ceid=US:es-419")])
    out["florida"] = r[:10]; e and out["errors"].append(e)
    r, e = get_feed("Google Noticias: principales", ["https://news.google.com/rss?hl=es-419&gl=US&ceid=US:es-419"])
    out["top"] = r[:10]; e and out["errors"].append(e)
    return out

def eventbrite(url, src):
    h = fetch(url).decode("utf-8", "replace"); res = []
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try: d = json.loads(blk)
        except Exception: continue
        for e in (d.get("itemListElement", []) if isinstance(d, dict) else []):
            it = e.get("item", e)
            if it.get("name"):
                loc = it.get("location") or {}; addr = loc.get("address") or {}
                res.append({"title": clean(it["name"]), "link": it.get("url", ""), "date": (it.get("startDate") or "")[:16].replace("T", " "),
                            "place": (loc.get("name") or "") + (", " + addr.get("addressLocality") if isinstance(addr, dict) and addr.get("addressLocality") else ""), "source": src})
    return res

def fl_events():
    out = {"items": [], "errors": [], "links": {"Visit Florida - eventos": "https://www.visitflorida.com/events/",
           "Eventbrite Florida": "https://www.eventbrite.com/d/fl/events/"}}
    for city in ("miami", "orlando", "tampa", "west-palm-beach"):
        try: out["items"] += eventbrite(f"https://www.eventbrite.com/d/fl--{city}/events/", "Eventbrite " + city.replace("-", " ").title())[:6]
        except Exception as e: out["errors"].append(f"Eventbrite {city}: {e}")
    out["items"].sort(key=lambda i: i.get("date") or "9")
    return out

BREAK_KW = ["breaking", "última hora", "ultima hora", "urgente", "just in", "developing", "en vivo", "live:"]
def safety_alerts(world_items):
    out = {"nws": [], "breaking": [], "errors": []}
    try:
        seen = set()
        for z in ("FLC011", "FLC086", "FLC099"):  # Broward, Miami-Dade, Palm Beach
            for f in jget(f"https://api.weather.gov/alerts/active?zone={z}")["features"]:
                p = f["properties"]
                if p["id"] in seen: continue
                seen.add(p["id"])
                out["nws"].append({"event": p["event"], "headline": p["headline"], "severity": p["severity"], "area": p["areaDesc"][:120]})
    except Exception as e: out["errors"].append(f"Alertas NWS: {e}")
    b = [i for i in world_items if any(k in i["title"].lower() for k in BREAK_KW)]
    r, err = get_feed("Google Noticias (destacadas)", ["https://news.google.com/rss?hl=es-419&gl=US&ceid=US:es-419"])
    if err: out["errors"].append(err)
    out["breaking"] = b[:5] + r[:8]
    return out

MSG_FILE = __file__.replace("app.py", "mensajes.json"); MSG_LOCK = threading.Lock()
def load_msgs():
    try:
        with open(MSG_FILE, encoding="utf-8") as f: return json.load(f)
    except Exception: return []
def save_msgs(m):
    with open(MSG_FILE, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=1)

CITIES = [("Fort Lauderdale", "KFLL"), ("Miami", "KMIA"), ("Orlando", "KMCO"), ("Tampa", "KTPA"), ("Jacksonville", "KJAX"), ("Key West", "KEYW")]
def city_wx(c):
    name, st = c
    try:
        p = jget(f"https://api.weather.gov/stations/{st}/observations/latest")["properties"]
        t = (p.get("temperature") or {}).get("value"); h = (p.get("relativeHumidity") or {}).get("value")
        return {"city": name, "desc": p.get("textDescription"), "temp_c": None if t is None else round(t),
                "temp_f": None if t is None else round(t * 9 / 5 + 32), "humidity": None if h is None else round(h)}
    except Exception as e:
        return {"city": name, "error": str(e)}
def cities():
    with ThreadPoolExecutor(6) as ex: return {"items": list(ex.map(city_wx, CITIES))}

CACHE = {"t": 0, "data": None}; LOCK = threading.Lock()
def build(force=False):
    with LOCK:
        if not force and CACHE["data"] and time.time() - CACHE["t"] < 300: return CACHE["data"]
        with ThreadPoolExecutor(12) as ex:
            fw = ex.submit(feeds_section, NEWS, True); fe = ex.submit(feeds_section, ECUADOR, False, 6)
            fa = ex.submit(airport); fm = ex.submit(maritime); fv = ex.submit(events); ft = ex.submit(traffic); ff = ex.submit(flights); fi = ex.submit(intl); fn = ex.submit(national); fl = ex.submit(fl_events); fno = ex.submit(noticias); fc = ex.submit(cities)
            def safe(f, d):
                try: return f.result()
                except Exception as e: return {**d, "errors": [str(e)]}
            world = safe(fw, {"items": []}); ec = safe(fe, {"items": []})
            data = {"generated": time.strftime("%Y-%m-%d %H:%M %Z"), "world": world, "airport": safe(fa, {}),
                    "maritime": safe(fm, {}), "events": safe(fv, {"items": []}), "traffic": safe(ft, {}), "flights": safe(ff, {}), "intl": safe(fi, {"topics": {}, "order": []}), "national": safe(fn, {"items": []}), "fl_events": safe(fl, {"items": []}), "cities": safe(fc, {"items": []}), "noticias": safe(fno, {"florida": [], "top": []}), "ecuador": ec}
        try: data["safety"] = safety_alerts(world.get("items", []))
        except Exception as e: data["safety"] = {"nws": [], "breaking": [], "errors": [str(e)]}
        data["alerts"] = alerts(world.get("items", []) + ec.get("items", []))
        CACHE.update(t=time.time(), data=data); return data

PAGE = open(__file__.replace("app.py", "index.html"), encoding="utf-8").read()

class H(BaseHTTPRequestHandler):
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        if self.path != "/api/messages": return self.send_error(404)
        try:
            n = int(self.headers.get("Content-Length", 0)); txt = str(json.loads(self.rfile.read(min(n, 5000)) or b"{}").get("text", "")).strip()[:500]
        except Exception: return self.send_json({"error": "datos inválidos"}, 400)
        if not txt: return self.send_json({"error": "mensaje vacío"}, 400)
        with MSG_LOCK:
            m = load_msgs(); m.insert(0, {"id": str(int(time.time() * 1000)), "text": txt, "time": time.strftime("%Y-%m-%d %H:%M")}); save_msgs(m)
        self.send_json(m)
    def do_DELETE(self):
        if not self.path.startswith("/api/messages/"): return self.send_error(404)
        mid = self.path.rsplit("/", 1)[-1]
        with MSG_LOCK:
            m = [x for x in load_msgs() if x["id"] != mid]; save_msgs(m)
        self.send_json(m)
    def do_GET(self):
        if self.path == "/api/messages": return self.send_json(load_msgs())
        if self.path.startswith("/api/data"):
            body = json.dumps(build("refresh" in self.path), ensure_ascii=False).encode(); ct = "application/json; charset=utf-8"
        elif self.path in ("/", "/index.html"):
            body = PAGE.encode(); ct = "text/html; charset=utf-8"
        else:
            self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    print(f"Panel de Walter en http://localhost:{PORT}  (Ctrl+C para salir)")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
