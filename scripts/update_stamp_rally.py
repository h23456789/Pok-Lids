import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "scripts" else SCRIPT_DIR
STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
OVERRIDE_FILE = ROOT / "svgstamp_manual_overrides.json"

TIMEOUT = 30
REQUEST_DELAY = 0.35
MAX_DISCOVERY_PAGES = 100
MAX_SITEMAP_URLS = 5000
GEOCODER_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 PokemonJapanCollectionUpdater/6.0",
    "Accept-Language": "zh-TW,zh;q=0.9,ja-JP,ja;q=0.8,en;q=0.7",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

OFFICIAL_DOMAINS = {"pokemongo.com", "www.pokemongo.com"}
DISCOVERY_URLS = [
    "https://pokemongo.com/ja/news",
    "https://pokemongo.com/zh-Hant/news",
    "https://pokemongo.com/en/news",
    "https://pokemongo.com/ja/post/go_stamp_rally",
]
STAMP_KEYWORDS = ["GOスタンプラリー", "GO スタンプラリー", "GO 集章趣", "GO集章趣", "GO Stamp Rally", "Pokemon GO Stamp Rally", "Pokémon GO Stamp Rally"]

EXCLUDE_PATTERNS = [
    r"ポケふた", r"pok[eé] lid", r"pokelid",
    r"ポケモンセンター", r"pokemon center", r"pokemon go lab",
    r"how do .*stamp rall", r"how to .*stamp rall", r"goスタンプラリー.*遊び方",
]

PREF_ALIASES = [
    ("北海道", "北海道"), ("青森", "青森県"), ("岩手", "岩手県"), ("宮城", "宮城県"), ("秋田", "秋田県"),
    ("山形", "山形県"), ("福島", "福島県"), ("茨城", "茨城県"), ("栃木", "栃木県"), ("群馬", "群馬県"),
    ("埼玉", "埼玉県"), ("千葉", "千葉県"), ("東京", "東京都"), ("神奈川", "神奈川県"), ("新潟", "新潟県"),
    ("富山", "富山県"), ("石川", "石川県"), ("福井", "福井県"), ("山梨", "山梨県"), ("長野", "長野県"),
    ("岐阜", "岐阜県"), ("静岡", "静岡県"), ("愛知", "愛知県"), ("三重", "三重県"), ("滋賀", "滋賀県"),
    ("京都", "京都府"), ("大阪", "大阪府"), ("兵庫", "兵庫県"), ("奈良", "奈良県"), ("和歌山", "和歌山県"),
    ("鳥取", "鳥取県"), ("島根", "島根県"), ("岡山", "岡山県"), ("広島", "広島県"), ("山口", "山口県"),
    ("徳島", "徳島県"), ("香川", "香川県"), ("愛媛", "愛媛県"), ("高知", "高知県"), ("福岡", "福岡県"),
    ("佐賀", "佐賀県"), ("長崎", "長崎県"), ("熊本", "熊本県"), ("大分", "大分県"), ("宮崎", "宮崎県"),
    ("鹿児島", "鹿児島県"), ("沖縄", "沖縄県"),
]


def norm(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\u3000", " ")).strip()


def norm_id(v):
    return re.sub(r"[\s\u3000\-‐‑–—_・･.,，。:：/\\()（）「」『』【】\[\]]", "", norm(v).lower())


def sha(*parts):
    return hashlib.sha1("|".join(norm(x) for x in parts).encode("utf-8")).hexdigest()[:12].upper()


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_official(url):
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and (p.hostname or "").lower() in OFFICIAL_DOMAINS
    except Exception:
        return False


def get_html(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        print("HTTP ERROR:", url, e)
        return ""


def canonical_url(url):
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower().removeprefix("www.")
        path = re.sub(r"^/(?:ja|en|zh-hant|zh_hant|ko)(?=/|$)", "", p.path.rstrip("/"), flags=re.I)
        q = re.sub(r"[?&](?:hl|game_client|pgo_client)=[^&]+", "", ("?" + p.query) if p.query else "")
        return host + path + q
    except Exception:
        return norm(url).lower()


def source_rank(url):
    s = url.lower()
    if "/zh-hant/" in s or "/zh_hant/" in s:
        return 0
    if "/ja/" in s or "hl=ja" in s:
        return 1
    if "/en/" in s or "hl=en" in s:
        return 2
    return 3


def extract_dates(text):
    out = []
    patterns = [
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
        r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})",
        r"(\w+\s+\d{1,2},\s+20\d{2})",
    ]
    for pat in patterns[:2]:
        for m in re.finditer(pat, text):
            y, mo, d = m.groups()
            val = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            if val not in out:
                out.append(val)
    return out


def extract_pref(text):
    t = norm(text)
    for a, c in PREF_ALIASES:
        if a in t:
            return c
    return ""


def extract_city(text):
    m = re.search(r"([一-龥ぁ-んァ-ヶー]{1,12}(?:市|区|町|村))", norm(text))
    return m.group(1) if m else ""


def page_title(soup):
    candidates = []
    for tag in soup.find_all(["h1", "h2"]):
        x = norm(tag.get_text(" ", strip=True))
        if x:
            candidates.append(x)
    for attrs in ({"property": "og:title"}, {"name": "twitter:title"}):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            candidates.append(norm(m["content"]))
    if soup.title:
        candidates.append(norm(soup.title.get_text(" ", strip=True)))
    for x in candidates:
        if any(k.lower() in x.lower() for k in STAMP_KEYWORDS):
            return x
    return candidates[0] if candidates else "GO Stamp Rally"


def extract_image(soup, base):
    for attrs in ({"property": "og:image"}, {"name": "twitter:image"}):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            return urljoin(base, m["content"])
    return ""


def is_excluded(title, text, url):
    hay = f"{title} {url} {text[:6000]}"
    return any(re.search(p, hay, re.I) for p in EXCLUDE_PATTERNS)


def has_actual_stamp_signal(soup, text, url):
    title = page_title(soup)
    if is_excluded(title, text, url):
        return False
    path = urlparse(url).path.rstrip("/").lower()
    if path in ("/news", "/ja/news", "/en/news", "/zh-hant/news", "/zh_hant/news"):
        return False
    lower = text.lower()
    direct = any(k.lower() in lower for k in STAMP_KEYWORDS)
    if not direct:
        return False
    # Must describe an actual rally, not merely feature documentation.
    actual_tokens = [
        "スタンプを押", "指定されたポケストップ", "対象のポケストップ", "下記エリア", "以下のような場所",
        "collect stamps", "participating pokéstops", "participating pokestops", "collect up to", "collect five stamps",
        "蒐集圖章", "活動指定的寶可補給站", "集滿", "starting today", "終了期間の制限なく",
    ]
    return any(t.lower() in lower for t in actual_tokens)


def extract_official_stamp_count(text):
    patterns = [
        r"最大\s*([0-9０-９]+)\s*(?:つ|個|枚)の?スタンプ",
        r"スタンプを\s*([0-9０-９]+)\s*(?:つ|個|枚)",
        r"([0-9０-９]+)\s*(?:つ|個|枚)の?スタンプを集",
        r"collect up to\s+(\d+)\s+stamps",
        r"collect\s+(\d+)\s+stamps",
        r"consists of\s+(\d+)\s+stamps",
        r"集滿\s*([0-9０-９]+)\s*枚",
        r"蒐集.*?([0-9０-９]+)\s*枚.*?圖章",
    ]
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            try:
                n = int(m.group(1).translate(trans))
                if 1 <= n <= 100:
                    return n
            except Exception:
                pass
    word_numbers = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    }
    lower = text.lower()
    for word, n in word_numbers.items():
        if re.search(rf"(?:collect up to|collect|consists of)\s+{word}\s+stamps", lower):
            return n
    return 0


def looks_like_venue_list(ul, official_count):
    lis = [norm(li.get_text(" ", strip=True)) for li in ul.find_all("li", recursive=False)]
    lis = [x for x in lis if x and len(x) <= 180]
    if len(lis) < 2 or len(lis) > 40:
        return []
    prev = ul.find_previous(["h2", "h3", "p"])
    context = norm(prev.get_text(" ", strip=True)) if prev else ""
    good_ctx = any(k.lower() in context.lower() for k in [
        "下記エリア", "スタンプ", "location", "explore", "participating", "collect", "地點", "會場", "locations"
    ])
    if good_ctx or (official_count and len(lis) == official_count):
        return lis
    return []


def extract_venues(soup, official_count):
    candidates = []
    for ul in soup.find_all("ul"):
        vals = looks_like_venue_list(ul, official_count)
        if vals:
            candidates.append(vals)
    if not candidates:
        return []
    # Prefer exact count, otherwise list closest to official count, otherwise longest.
    if official_count:
        exact = [x for x in candidates if len(x) == official_count]
        if exact:
            candidates = exact
        else:
            candidates.sort(key=lambda x: abs(len(x) - official_count))
            return candidates[0]
    candidates.sort(key=len, reverse=True)
    return candidates[0]


def geocode(query):
    if not query:
        return None
    try:
        r = SESSION.get(GEOCODER_URL, params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "jp"}, timeout=TIMEOUT,
                        headers={"Referer": "https://h23456789.github.io/Pok-Lids/"})
        r.raise_for_status()
        rows = r.json()
        if rows:
            lat, lng = float(rows[0]["lat"]), float(rows[0]["lon"])
            if 20 <= lat <= 46 and 122 <= lng <= 154:
                return [lat, lng]
    except Exception as e:
        print("GEOCODE ERROR:", query, e)
    return None


def find_override(item, overrides):
    iid, eid = norm(item.get("id")), norm(item.get("eventId"))
    names = {norm_id(item.get(k)) for k in ("venue", "name", "venueZh", "nameZh") if item.get(k)}
    for ov in overrides:
        if iid and norm(ov.get("id")) == iid:
            return ov
    for ov in overrides:
        oeid = norm(ov.get("eventId"))
        if eid and oeid and eid != oeid:
            continue
        onames = set()
        for k in ("venue", "name", "venueZh", "nameZh"):
            if ov.get(k): onames.add(norm_id(ov[k]))
        for k in ("venueAliases", "aliases"):
            for x in ov.get(k, []) if isinstance(ov.get(k, []), list) else []:
                onames.add(norm_id(x))
        if names & onames:
            return ov
    return None


def apply_override(item, ov):
    if not ov:
        return item
    # Manual values always win.
    field_map = {
        "manualEvent": "event", "manualEventZh": "eventZh", "manualName": "name", "manualNameZh": "nameZh",
        "manualVenue": "venue", "manualVenueZh": "venueZh", "manualAddress": "address", "manualPref": "pref",
        "manualCity": "city", "manualStartDate": "startDate", "manualEndDate": "endDate",
        "manualStampCount": "officialStampCount", "manualEventImage": "eventImage",
    }
    for src, dst in field_map.items():
        if src in ov and ov[src] not in (None, ""):
            item[dst] = ov[src]
            item["manualOverride"] = True
    coords = ov.get("manualCoordinates")
    if isinstance(coords, list) and len(coords) >= 2:
        try:
            lat, lng = float(coords[0]), float(coords[1])
            item["coords"] = [lat, lng]; item["lat"] = lat; item["lng"] = lng
            item["coordinatesManual"] = True; item["coordsSource"] = ov.get("coordinatesSource") or "Manual override"
            item["manualOverride"] = True
        except Exception:
            pass
    img = norm(ov.get("manualStampImage"))
    if img:
        item["stampImage"] = img; item["stampImageManual"] = True; item["stampImageSource"] = ov.get("stampImageSource") or "Manual override"
        item["manualOverride"] = True
    return item


def parse_page(url, overrides):
    html = get_html(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    text = norm(soup.get_text(" ", strip=True))
    if not has_actual_stamp_signal(soup, text, url):
        return None
    title = page_title(soup)
    official_count = extract_official_stamp_count(text)
    venues = extract_venues(soup, official_count)
    if not venues:
        print("  SKIP: no concrete venue list ->", title)
        return None

    # Keep Japan-only activities. If no Japanese place signal at all, do not include.
    pref = extract_pref(text)
    if not pref and not any(x in text for x in ["日本", "Japan", "長崎", "吹田", "東京", "大阪", "京都", "札幌", "福岡", "沖縄"]):
        print("  SKIP: non-Japan activity ->", title)
        return None

    dates = extract_dates(text)
    start = dates[0] if dates else ""
    indefinite = bool(re.search(r"終了期間の制限なく|no end date|without an end date", text, re.I))
    end = "" if indefinite else (dates[1] if len(dates) > 1 else "")
    event_id = "STAMP-AUTO-" + sha(canonical_url(url))
    event_img = extract_image(soup, url)
    event = {
        "eventId": event_id,
        "event": title,
        "eventName": title,
        "eventZh": title if "/zh-hant/" in url.lower() or "/zh_hant/" in url.lower() else "",
        "eventNameZh": title if "/zh-hant/" in url.lower() or "/zh_hant/" in url.lower() else "",
        "activity": "GO Stamp Rally",
        "activityZh": "GO 集章趣",
        "startDate": start,
        "endDate": end,
        "officialStampCount": official_count or len(venues),
        "expectedStamps": official_count or len(venues),
        "eventImage": event_img,
        "activityImage": event_img,
        "source": "Pokémon GO Official Website",
        "sourceUrl": url,
        "canonicalPage": canonical_url(url),
        "official": True,
        "discoveryMode": "official-auto",
    }
    points = []
    event_pref = extract_pref(text)
    event_city = extract_city(text)
    for i, venue in enumerate(venues, 1):
        clean_venue = re.sub(r"^[•\-–—\s]+", "", venue).strip()
        point = {
            "id": f"{event_id}-P{i:03d}", "eventId": event_id,
            "event": title, "eventName": title, "eventZh": event["eventZh"], "eventNameZh": event["eventNameZh"],
            "activity": "GO Stamp Rally", "activityZh": "GO 集章趣", "venueType": "go_stamp_point",
            "venue": clean_venue, "name": clean_venue, "pref": extract_pref(clean_venue) or event_pref,
            "city": extract_city(clean_venue) or event_city, "address": "", "coords": [],
            "startDate": start, "endDate": end, "stampImage": "", "activityImage": event_img, "eventImage": event_img,
            "source": "Pokémon GO Official Website", "sourceUrl": url, "official": True, "discoveryMode": "official-auto",
        }
        ov = find_override(point, overrides)
        point = apply_override(point, ov)
        if not point.get("coords"):
            q = ", ".join(x for x in [clean_venue, point.get("city", ""), point.get("pref", ""), "Japan"] if x)
            coords = geocode(q)
            if coords:
                point["coords"] = coords; point["lat"] = coords[0]; point["lng"] = coords[1]
                point["coordsSource"] = "Place-name geocoding (Nominatim)"
            time.sleep(1.05)
        points.append(point)

    # Manual event-level override may target eventId.
    eov = next((x for x in overrides if norm(x.get("eventId")) == event_id and not any(x.get(k) for k in ("venue", "name", "manualCoordinates", "manualStampImage"))), None)
    if eov:
        event = apply_override(event, eov)
    event["pointCount"] = len(points)
    event["dataStatus"] = "complete" if event["pointCount"] == event["officialStampCount"] else "partial"
    return event, points


def discover_sitemaps():
    return ["https://pokemongo.com/sitemap.xml", "https://pokemongo.com/sitemap_index.xml"]


def parse_sitemap(url, visited=None):
    visited = visited or set()
    if url in visited or len(visited) > 30:
        return set()
    visited.add(url)
    xml = get_html(url)
    if not xml:
        return set()
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return set()
    out = set()
    if root.tag.lower().endswith("sitemapindex"):
        for el in root.iter():
            if el.tag.lower().endswith("loc") and el.text and is_official(el.text.strip()):
                out.update(parse_sitemap(el.text.strip(), visited))
                if len(out) >= MAX_SITEMAP_URLS: break
    else:
        for el in root.iter():
            if el.tag.lower().endswith("loc") and el.text and is_official(el.text.strip()):
                out.add(el.text.strip())
                if len(out) >= MAX_SITEMAP_URLS: break
    return out


def discover_urls(old_items):
    candidates = set()
    for item in old_items:
        u = norm(item.get("sourceUrl"))
        if is_official(u): candidates.add(u)
    queue, visited = list(DISCOVERY_URLS), set()
    while queue and len(visited) < MAX_DISCOVERY_PAGES:
        url = queue.pop(0)
        if url in visited or not is_official(url): continue
        visited.add(url)
        html = get_html(url)
        if not html: continue
        soup = BeautifulSoup(html, "html.parser")
        text = norm(soup.get_text(" ", strip=True))
        if has_actual_stamp_signal(soup, text, url): candidates.add(url)
        for a in soup.find_all("a", href=True):
            u = urljoin(url, a["href"]).split("#", 1)[0]
            if not is_official(u): continue
            combined = f"{norm(a.get_text(' ', strip=True))} {u}".lower()
            if any(k.lower() in combined for k in STAMP_KEYWORDS): candidates.add(u)
            path = urlparse(u).path.lower()
            if any(t in path for t in ("/news/", "/post/", "/gofest/", "/gowildarea/")) and u not in visited and u not in queue:
                queue.append(u)
        time.sleep(REQUEST_DELAY)
    for sm in discover_sitemaps():
        for u in parse_sitemap(sm):
            low = u.lower()
            if any(t in low for t in ("stamp", "rally", "gofest", "gowildarea")):
                candidates.add(u)
    # locale dedupe
    best = {}
    for u in candidates:
        k = canonical_url(u)
        if k not in best or source_rank(u) < source_rank(best[k]): best[k] = u
    return sorted(best.values())


def compare(old, new):
    om = {x.get("id"): x for x in old if x.get("id")}
    nm = {x.get("id"): x for x in new if x.get("id")}
    return ([k for k in nm if k not in om], [k for k in om if k not in nm], [k for k in nm if k in om and nm[k] != om[k]])


def main():
    print("=== Pokémon GO actual GO Stamp Rally sync v6 ===")
    old = load_json(STAMP_FILE, {"events": [], "list": []})
    old_items = old.get("list", []) if isinstance(old, dict) else []
    overrides_obj = load_json(OVERRIDE_FILE, {"items": []})
    overrides = overrides_obj.get("items", []) if isinstance(overrides_obj, dict) else []

    urls = discover_urls(old_items)
    print("Candidate official URLs:", len(urls))
    parsed = []
    for url in urls:
        print("CHECK:", url)
        try:
            result = parse_page(url, overrides)
            if result:
                parsed.append(result)
                print("  FOUND actual rally:", result[0].get("event"), "points=", len(result[1]), "official=", result[0].get("officialStampCount"))
        except Exception as e:
            print("  PARSE ERROR:", e)
        time.sleep(REQUEST_DELAY)

    # Event-level locale/source dedupe: same canonical page or same normalized venue set => one event.
    grouped = {}
    for event, points in parsed:
        venue_sig = "|".join(sorted(norm_id(p.get("venue")) for p in points if p.get("venue")))
        key = venue_sig or event.get("canonicalPage") or norm_id(event.get("event"))
        current = grouped.get(key)
        if current is None or source_rank(event.get("sourceUrl", "")) < source_rank(current[0].get("sourceUrl", "")):
            grouped[key] = (event, points)

    events, items = [], []
    for event, points in grouped.values():
        # Re-apply manual overrides after dedupe so manual always wins.
        points = [apply_override(p, find_override(p, overrides)) for p in points]
        event["pointCount"] = len(points)
        event["dataStatus"] = "complete" if event.get("officialStampCount") == len(points) else "partial"
        events.append(event); items.extend(points)

    # Optional manual-only records: only preserved when override explicitly says forceKeep/manualOnly.
    old_by_id = {x.get("id"): x for x in old_items if x.get("id")}
    for ov in overrides:
        if not (ov.get("forceKeep") or ov.get("manualOnly")): continue
        iid = norm(ov.get("id"))
        if iid and iid in old_by_id and not any(x.get("id") == iid for x in items):
            items.append(apply_override(dict(old_by_id[iid]), ov))

    events.sort(key=lambda x: (x.get("startDate") or "9999-99-99", x.get("eventZh") or x.get("event") or ""))
    items.sort(key=lambda x: (x.get("startDate") or "", x.get("eventZh") or x.get("event") or "", x.get("nameZh") or x.get("name") or ""))

    added, removed, changed = compare(old_items, items)
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "version": "6.0", "updated": now, "source": "official",
        "sourceMode": "actual official GO Stamp Rally discovery; official stamp count authoritative; manual overrides highest priority",
        "rule": "Only actual in-game Pokémon GO GO Stamp Rally in Japan. Poké Lid and Pokémon Center rallies are excluded.",
        "events": events, "list": items,
    }
    write_json(STAMP_FILE, data)

    history = load_json(HISTORY_FILE, {"history": []})
    h = history.get("history", []) if isinstance(history, dict) else []
    if added or removed or changed:
        h.insert(0, {"updated": now, "added": added, "removed": removed, "changed": changed})
        h = h[:100]
    write_json(HISTORY_FILE, {"history": h})
    print("DONE events:", len(events), "points:", len(items), "added:", len(added), "removed:", len(removed), "changed:", len(changed))


if __name__ == "__main__":
    main()
