import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

=========================================================

PATH

=========================================================

ROOT = Path(file).resolve().parent.parent

STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
OVERRIDE_FILE = ROOT / "svgstamp_manual_overrides.json"

=========================================================

CONFIG

=========================================================

TIMEOUT = 30
REQUEST_DELAY = 0.35

MAX_DISCOVERY_PAGES = 80
GEOCODER_URL = "https://nominatim.openstreetmap.org/search"

=========================================================

HTTP

=========================================================

HEADERS = {
"User-Agent": (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 (KHTML, like Gecko) "
"Chrome/151.0 Safari/537.36 "
"PokemonJapanCollectionUpdater/7.0"
),
"Accept-Language": "zh-TW,zh;q=0.9,ja-JP,ja;q=0.8,en;q=0.7",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

=========================================================

OFFICIAL DOMAINS

=========================================================

OFFICIAL_DOMAINS = {
"pokemon.co.jp",
"www.pokemon.co.jp",
"shop.pokemon.co.jp",
"pokemongo.com",
"www.pokemongo.com",
}

=========================================================

DISCOVERY

=========================================================

DISCOVERY_URLS = [
"https://www.pokemon.co.jp/",
"https://www.pokemon.co.jp/info/",
"https://www.pokemon.co.jp/event/",
"https://shop.pokemon.co.jp/ja/",
"https://shop.pokemon.co.jp/ja/shop/common/events/",
"https://pokemongo.com/zh-Hant/news",
"https://pokemongo.com/en/news",
"https://pokemongo.com/ja/news",
"https://pokemongo.com/zh-Hant/featured-in-person-events",
"https://pokemongo.com/en/featured-in-person-events",
"https://pokemongo.com/ja/featured-in-person-events",
]

STAMP_KEYWORDS = [
"スタンプラリー",
"GOスタンプラリー",
"GO 集章趣",
"GO集章趣",
"STAMP RALLY",
"Stamp Rally",
"stamp rally",
]

INSTRUCTIONAL_PATTERNS = [
r"我該怎麼進行.*集章趣",
r"我怎麼(?:進行|參加|玩).*集章趣",
r"如何.*集章趣",
r"怎麼.*集章趣",
r"how to .*stamp rally",
r"how .*stamp rally",
r"stamp rally.*how to",
r"(?:ご利用方法|遊び方|参加方法|楽しみ方).スタンプラリー",
r"スタンプラリー.(?:ご利用方法|遊び方|参加方法|楽しみ方)",
]

=========================================================

TEXT

=========================================================

def normalize_text(value):
if value is None:
return ""
return re.sub(r"\s+", " ", str(value).replace("\u3000", " ")).strip()

def normalize_identity(value):
return re.sub(
r"[\s\u3000-‐-–—_・･.,，。:：/\()（）「」『』【】]",
"",
normalize_text(value).lower()
)

def clean_event_title(value):
value = normalize_text(value)
value = re.sub(r"\s*[—-|]\sPok[eé]mon GO\s$", "", value, flags=re.I)
return value.strip()

def make_hash(*parts):
raw = "|".join(normalize_text(part) for part in parts)
return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()

=========================================================

URL

=========================================================

def is_official_url(url):
try:
parsed = urlparse(url)
if parsed.scheme not in ("http", "https"):
return False
return (parsed.hostname or "").lower() in OFFICIAL_DOMAINS
except Exception:
return False

def canonical_source_url(url):
raw = normalize_text(url)
if not raw:
return ""
try:
parsed = urlparse(raw)
path = parsed.path.rstrip("/")
path = re.sub(r"^/(?|ja|zh-hant|zh_hant)(?=/|$)", "", path, flags=re.I)
host = (parsed.hostname or "").lower()
if host.startswith("www."):
host = host[4:]
return host + path
except Exception:
return raw.lower()

def source_locale_rank(url):
value = normalize_text(url).lower()
if "/zh-hant/" in value or "/zh_hant/" in value:
return 0
if "/ja/" in value:
return 1
if "/en/" in value:
return 2
return 3

=========================================================

ACTIVITY KEY

=========================================================

def canonical_activity_key(item):
source = canonical_source_url(item.get("sourceUrl", "") or item.get("canonicalPage", ""))
if source:
return "source:" + source

title = clean_event_title(
    item.get("eventZh")
    or item.get("eventNameZh")
    or item.get("event")
    or item.get("eventName")
    or ""
)

# PokéXciting 特別處理。
# 不管 eventId / locale，都視為同一活動。
if "pokéxciting" in title.lower() or "pokexciting" in normalize_identity(title):
    return "title:pokexciting-2026"

if title:
    return "title:" + normalize_identity(title)

if item.get("eventId"):
    return "eventid:" + normalize_text(item["eventId"])

if item.get("id"):
    return "id:" + normalize_text(item["id"])

return "unknown"

=========================================================

HTTP / JSON

=========================================================

def get_html(url):
try:
response = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
response.raise_for_status()
response.encoding = response.apparent_encoding or "utf-8"
return response.text
except Exception as error:
print("HTTP ERROR:", url, error)
return ""

def load_json(path, default):
if not path.exists():
return default
try:
return json.loads(path.read_text(encoding="utf-8"))
except Exception:
return default

def write_json(path, data):
path.write_text(
json.dumps(data, ensure_ascii=False, indent=2) + "\n",
encoding="utf-8"
)

=========================================================

DATE

=========================================================

def parse_date(value):
value = normalize_text(value)

match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", value)
if match:
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"

match = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", value)
if match:
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"

return ""

def extract_dates(text):
found = []
patterns = [
r"20\d{2}年\d{1,2}月\d{1,2}日",
r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}",
]
for pattern in patterns:
for raw in re.findall(pattern, text or ""):
value = parse_date(raw)
if value and value not in found:
found.append(value)
return sorted(found)

=========================================================

EVENT EXTRACTION

=========================================================

def extract_event_name(soup, page_text):
candidates = []

for tag in soup.find_all("h1"):
    text = normalize_text(tag.get_text(" ", strip=True))
    if text:
        candidates.append(text)

for attrs in ({"property": "og:title"}, {"name": "twitter:title"}):
    meta = soup.find("meta", attrs=attrs)
    if meta:
        text = normalize_text(meta.get("content", ""))
        if text:
            candidates.append(text)

if soup.title:
    candidates.append(normalize_text(soup.title.get_text(" ", strip=True)))

for text in candidates:
    if ("スタンプラリー" in text or "stamp rally" in text.lower() or "集章趣" in text):
        return text

return candidates[0] if candidates else "GO 集章趣"

def extract_image(soup, base_url):
for attrs in ({"property": "og"}, {"name": "twitter"}):
meta = soup.find("meta", attrs=attrs)
if meta:
value = normalize_text(meta.get("content", ""))
if value:
return urljoin(base_url, value)
return ""

def is_instructional(text):
normalized = normalize_text(text)
return any(re.search(pattern, normalized, re.I) for pattern in INSTRUCTIONAL_PATTERNS)

def is_real_stamp_page(soup, page_text, url):
event_name = extract_event_name(soup, page_text)
if is_instructional(event_name):
return False

lower = (page_text or "").lower()
return (
    "stamp rally" in lower
    or "スタンプラリー" in page_text
    or "go 集章趣" in lower
    or "go集章趣" in lower
)

=========================================================

PREFECTURE

=========================================================

PREF_ALIASES = [
("北海道", "北海道"),
("青森県", "青森県"), ("青森", "青森県"),
("岩手県", "岩手県"), ("岩手", "岩手県"),
("宮城県", "宮城県"), ("宮城", "宮城県"),
("秋田県", "秋田県"), ("秋田", "秋田県"),
("山形県", "山形県"), ("山形", "山形県"),
("福島県", "福島県"), ("福島", "福島県"),
("茨城県", "茨城県"), ("茨城", "茨城県"),
("栃木県", "栃木県"), ("栃木", "栃木県"),
("群馬県", "群馬県"), ("群馬", "群馬県"),
("埼玉県", "埼玉県"), ("埼玉", "埼玉県"),
("千葉県", "千葉県"), ("千葉", "千葉県"),
("東京都", "東京都"), ("東京", "東京都"),
("神奈川県", "神奈川県"), ("神奈川", "神奈川県"),
("新潟県", "新潟県"), ("新潟", "新潟県"),
("富山県", "富山県"), ("富山", "富山県"),
("石川県", "石川県"), ("石川", "石川県"),
("福井県", "福井県"), ("福井", "福井県"),
("山梨県", "山梨県"), ("山梨", "山梨県"),
("長野県", "長野県"), ("長野", "長野県"),
("岐阜県", "岐阜県"), ("岐阜", "岐阜県"),
("静岡県", "静岡県"), ("静岡", "静岡県"),
("愛知県", "愛知県"), ("愛知", "愛知県"),
("三重県", "三重県"), ("三重", "三重県"),
("滋賀県", "滋賀県"), ("滋賀", "滋賀県"),
("京都府", "京都府"), ("京都", "京都府"),
("大阪府", "大阪府"), ("大阪", "大阪府"),
("兵庫県", "兵庫県"), ("兵庫", "兵庫県"),
("奈良県", "奈良県"), ("奈良", "奈良県"),
("和歌山県", "和歌山県"), ("和歌山", "和歌山県"),
("鳥取県", "鳥取県"), ("鳥取", "鳥取県"),
("島根県", "島根県"), ("島根", "島根県"),
("岡山県", "岡山県"), ("岡山", "岡山県"),
("広島県", "広島県"), ("広島", "広島県"),
("山口県", "山口県"), ("山口", "山口県"),
("徳島県", "徳島県"), ("徳島", "徳島県"),
("香川県", "香川県"), ("香川", "香川県"),
("愛媛県", "愛媛県"), ("愛媛", "愛媛県"),
("高知県", "高知県"), ("高知", "高知県"),
("福岡県", "福岡県"), ("福岡", "福岡県"),
("佐賀県", "佐賀県"), ("佐賀", "佐賀県"),
("長崎県", "長崎県"), ("長崎", "長崎県"),
("熊本県", "熊本県"), ("熊本", "熊本県"),
("大分県", "大分県"), ("大分", "大分県"),
("宮崎県", "宮崎県"), ("宮崎", "宮崎県"),
("鹿児島県", "鹿児島県"), ("鹿児島", "鹿児島県"),
("沖縄県", "沖縄県"), ("沖縄", "沖縄県"),
]

def extract_prefecture(text):
normalized = normalize_text(text)
for alias, canonical in PREF_ALIASES:
if alias in normalized:
return canonical
return ""

=========================================================

EVENT / POINT ID

=========================================================

def get_event_id(event, source_url, old_items):
canonical = canonical_source_url(source_url)

for item in old_items:
    old_source = canonical_source_url(item.get("sourceUrl", ""))
    if canonical and canonical == old_source:
        existing = item.get("eventId") or item.get("id") or ""
        if existing:
            return existing

return "STAMP-AUTO-" + make_hash(canonical or event)

def get_point_id(event_id, venue):
return "STAMP-POINT-" + make_hash(normalize_identity(event_id), normalize_identity(venue))

=========================================================

MANUAL OVERRIDE

=========================================================

def load_manual_overrides():
data = load_json(OVERRIDE_FILE, {"items": []})
if not isinstance(data, dict):
return []
items = data.get("items", [])
return items if isinstance(items, list) else []

def find_manual_override(item, overrides):
item_id = normalize_text(item.get("id", ""))

if item_id:
    for override in overrides:
        if normalize_text(override.get("id", "")) == item_id:
            return override

event_id = normalize_text(item.get("eventId", ""))
names = {
    normalize_identity(value) for value in (
        item.get("venue"), item.get("name"), item.get("venueZh"), item.get("nameZh")
    ) if value
}

for override in overrides:
    override_event = normalize_text(override.get("eventId", ""))
    if event_id and override_event and event_id != override_event:
        continue

    override_names = {
        normalize_identity(value) for value in (
            override.get("venue"), override.get("name"), override.get("venueZh"), override.get("nameZh")
        ) if value
    }

    if names & override_names:
        return override

return None

def apply_manual_overrides(items, overrides):
for item in items:
override = find_manual_override(item, overrides)
if not override:
continue

    coordinates = override.get("manualCoordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        try:
            lat = float(coordinates[0])
            lng = float(coordinates[1])

            if abs(lat) <= 90 and abs(lng) <= 180:
                item["coords"] = [lat, lng]
                item["lat"] = lat
                item["lng"] = lng
                item["coordinatesManual"] = True
                item["coordinatesSource"] = override.get("coordinatesSource") or "Manual override"
        except (TypeError, ValueError):
            pass

    if override.get("manualStampImage"):
        item["stampImage"] = override["manualStampImage"]
        item["stampImageManual"] = True

    if override.get("manualCenterBadge"):
        item["centerBadgeImage"] = override["manualCenterBadge"]

    if override.get("manualTitle"):
        item["nameZh"] = override["manualTitle"]
        item["venueZh"] = override["manualTitle"]

    if override.get("nameZh"):
        item["nameZh"] = override["nameZh"]

    if override.get("venueZh"):
        item["venueZh"] = override["venueZh"]

return items

=========================================================

STAMP PAGE

=========================================================

def parse_stamp_page(url, old_items):
html = get_html(url)
if not html:
return []

soup = BeautifulSoup(html, "html.parser")
page_text = normalize_text(soup.get_text(" ", strip=True))

if not is_real_stamp_page(soup, page_text, url):
    return []

event = extract_event_name(soup, page_text)
dates = extract_dates(page_text)
start_date = dates[0] if dates else ""
end_date = dates[1] if len(dates) >= 2 else ""
image = extract_image(soup, url)
event_id = get_event_id(event, url, old_items)

items = []
centers = []

for link in soup.find_all("a", href=True):
    text = normalize_text(link.get_text(" ", strip=True))
    if "ポケモンセンター" not in text:
        continue

    if any(bad in text for bad in ("サテライト", "出張所", "カフェ")):
        continue

    centers.append({
        "name": text,
        "url": urljoin(url, link["href"])
    })

seen = set()
for center in centers:
    venue = center["name"]
    key = normalize_identity(venue)
    
    if key in seen:
        continue
    seen.add(key)

    lower_venue = venue.lower()
    venue_type = "pokemon_go_lab" if ("go lab" in lower_venue or "pokemon go lab" in lower_venue) else "pokemon_center"
    is_zh = "/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()

    item = {
        "id": get_point_id(event_id, venue),
        "eventId": event_id,
        "event": event,
        "eventName": event,
        "eventZh": event if is_zh else "",
        "eventNameZh": event if is_zh else "",
        "activity": "GO Stamp Rally",
        "activityZh": "GO 集章趣",
        "venueType": venue_type,
        "venue": venue,
        "name": venue,
        "pref": extract_prefecture(page_text),
        "city": "",
        "address": "",
        "coords": [],
        "startDate": start_date,
        "endDate": end_date,
        "stampImage": "",
        "activityImage": image,
        "eventImage": image,
        "source": "Pokémon GO Official Website",
        "sourceUrl": url,
        "venueSourceUrl": center["url"],
        "official": True
    }
    items.append(item)

if not items:
    is_zh = "/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()
    items.append({
        "id": get_point_id(event_id, event),
        "eventId": event_id,
        "event": event,
        "eventName": event,
        "eventZh": event if is_zh else "",
        "eventNameZh": event if is_zh else "",
        "activity": "GO Stamp Rally",
        "activityZh": "GO 集章趣",
        "venueType": "event",
        "venue": "",
        "name": event,
        "pref": extract_prefecture(page_text),
        "city": "",
        "address": "",
        "coords": [],
        "startDate": start_date,
        "endDate": end_date,
        "stampImage": "",
        "activityImage": image,
        "eventImage": image,
        "source": "Pokémon GO Official Website",
        "sourceUrl": url,
        "official": True
    })

return items

=========================================================

DISCOVERY

=========================================================

def discover_urls(old_items):
candidates = set()

for item in old_items:
    source = normalize_text(item.get("sourceUrl", ""))
    if is_official_url(source):
        candidates.add(source)

queue = list(DISCOVERY_URLS)
visited = set()

while queue and len(visited) < MAX_DISCOVERY_PAGES:
    url = queue.pop(0)

    if url in visited or not is_official_url(url):
        continue

    visited.add(url)
    html = get_html(url)
    if not html:
        continue

    soup = BeautifulSoup(html, "html.parser")
    text = normalize_text(soup.get_text(" ", strip=True))

    if is_real_stamp_page(soup, text, url):
        candidates.add(url)

    for link in soup.find_all("a", href=True):
        absolute = urljoin(url, link["href"]).split("#", 1)[0]
        if not is_official_url(absolute):
            continue

        link_text = normalize_text(link.get_text(" ", strip=True))
        combined = f"{link_text} {absolute}".lower()

        if any(keyword.lower() in combined for keyword in STAMP_KEYWORDS):
            candidates.add(absolute)

        path = urlparse(absolute).path.lower()
        if any(token in path for token in (
            "/news/", "/event/", "/events/", "/featured-in-person-events/", "/gofest/", "/gowildarea/"
        )):
            if absolute not in visited and absolute not in queue:
                queue.append(absolute)

    time.sleep(REQUEST_DELAY)

# sitemap
for sitemap in discover_sitemaps():
    sitemap_html = get_html(sitemap)
    if not sitemap_html:
        continue

    for url in re.findall(r"<loc>\s*(.*?)\s*</loc>", sitemap_html, re.I):
        if not is_official_url(url):
            continue

        lower = url.lower()
        if any(token in lower for token in (
            "stamp", "rally", "event", "citysafari", "gofest", "featured-in-person-events"
        )):
            candidates.add(url)

# canonical locale dedupe
deduped = {}
for candidate in candidates:
    key = canonical_source_url(candidate)
    if not key:
        continue

    current = deduped.get(key)
    if current is None or source_locale_rank(candidate) < source_locale_rank(current):
        deduped[key] = candidate

return sorted(deduped.values())

def discover_sitemaps():
result = set()
for robots in (
"https://www.pokemon.co.jp/robots.txt",
"https://shop.pokemon.co.jp/robots.txt",
"https://pokemongo.com/robots.txt",
):
text = get_html(robots)
for match in re.findall(r"(?im)^\sSitemap:\s(\S+)\s*$", text):
if is_official_url(match):
result.add(match)

result.update({
    "https://www.pokemon.co.jp/sitemap.xml",
    "https://shop.pokemon.co.jp/sitemap.xml",
    "https://shop.pokemon.co.jp/sitemap_index.xml",
    "https://pokemongo.com/sitemap.xml",
    "https://pokemongo.com/sitemap_index.xml",
})

return sorted(result)

=========================================================

GEOCODING

=========================================================

def geocode_place(query):
if not query:
return None

try:
    response = SESSION.get(
        GEOCODER_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "jp"
        },
        timeout=TIMEOUT,
        headers={"Referer": "https://h23456789.github.io/Pok-Lids/"}
    )
    response.raise_for_status()
    rows = response.json()

    if rows:
        return [float(rows[0]["lat"]), float(rows[0]["lon"])]

except Exception as error:
    print("GEOCODE ERROR:", query, error)

return None

def enrich_coordinates(item):
if item.get("coordinatesManual"):
return item

coords = item.get("coords")
if isinstance(coords, list) and len(coords) >= 2:
    try:
        lat = float(coords[0])
        lng = float(coords[1])
        if abs(lat) <= 90 and abs(lng) <= 180:
            return item
    except (TypeError, ValueError):
        pass

venue = normalize_text(item.get("venue") or item.get("name") or "")
city = normalize_text(item.get("city") or item.get("cityZh") or "")
pref = normalize_text(item.get("pref") or "")

queries = []
if venue and city and pref:
    queries.append(f"{venue}, {city}, {pref}, Japan")
if venue and city:
    queries.append(f"{venue}, {city}, Japan")
if venue and pref:
    queries.append(f"{venue}, {pref}, Japan")
if venue:
    queries.append(f"{venue}, Japan")

seen = set()
for query in queries:
    if query in seen:
        continue
    seen.add(query)

    coords = geocode_place(query)
    if coords:
        item["coords"] = coords
        item["lat"] = coords[0]
        item["lng"] = coords[1]
        item["coordsSource"] = "Place-name geocoding (Nominatim)"
        item["coordinatesConfidence"] = "medium"
        return item

    time.sleep(1.1)

return item

=========================================================

MERGE

=========================================================

def point_key(item):
return (
canonical_activity_key(item),
normalize_identity(item.get("venue") or item.get("name") or "")
)

def merge_items(old_items, fresh_items):
result = {}

# 先處理舊資料
for item in old_items:
    if not item.get("id"):
        continue

    if is_instructional(item.get("event", "")):
        continue

    key = point_key(item)
    if key not in result:
        result[key] = item
        continue

    current = result[key]
    preferred = item if source_locale_rank(item.get("sourceUrl", "")) < source_locale_rank(current.get("sourceUrl", "")) else current
    other = current if preferred is item else item

    for field in (
        "eventZh", "eventNameZh", "activityZh", "nameZh", "venueZh",
        "cityZh", "addressZh", "activityImage", "eventImage", "rewardZh",
        "stampImage", "centerBadgeImage", "coords", "lat", "lng", "address"
    ):
        if not preferred.get(field) and other.get(field):
            preferred[field] = other[field]

    result[key] = preferred

# 再處理新資料
for item in fresh_items:
    if not item.get("id"):
        continue

    key = point_key(item)
    if key not in result:
        result[key] = item
        continue

    current = result[key]

    # 舊資料 ID 一定保留
    if current.get("id"):
        item["id"] = current["id"]

    preferred = item if source_locale_rank(item.get("sourceUrl", "")) < source_locale_rank(current.get("sourceUrl", "")) else current
    other = current if preferred is item else item

    for field in (
        "eventZh", "eventNameZh", "activityZh", "nameZh", "venueZh",
        "cityZh", "addressZh", "activityImage", "eventImage", "rewardZh",
        "stampImage", "centerBadgeImage", "coords", "lat", "lng", "address"
    ):
        if not item.get(field) and current.get(field):
            item[field] = current[field]

    result[key] = item

return list(result.values())

def build_event_metadata(items, old_events=None):
if old_events is None:
old_events = []

grouped = {}

for item in items:
    key = canonical_activity_key(item)
    if not key:
        continue

    event = grouped.get(key)
    if event is None:
        grouped[key] = {
            "eventId": item.get("eventId") or ("STAMP-AUTO-" + make_hash(key)),
            "event": item.get("event") or item.get("eventName") or "GO 集章趣",
            "eventName": item.get("eventName") or item.get("event") or "GO 集章趣",
            "eventZh": item.get("eventZh") or item.get("eventNameZh") or item.get("event") or "GO 集章趣",
            "eventNameZh": item.get("eventNameZh") or item.get("eventZh") or item.get("event") or "GO 集章趣",
            "activity": "GO Stamp Rally",
            "activityZh": "GO 集章趣",
            "startDate": "",
            "endDate": "",
            "pointCount": 0,
            "activityImage": item.get("activityImage") or item.get("eventImage") or "",
            "eventImage": item.get("eventImage") or item.get("activityImage") or "",
            "sourceUrl": item.get("sourceUrl") or ""
        }
        event = grouped[key]

    event["pointCount"] += 1

    if item.get("startDate") and (not event["startDate"] or item["startDate"] < event["startDate"]):
        event["startDate"] = item["startDate"]

    if item.get("endDate") and (not event["endDate"] or item["endDate"] > event["endDate"]):
        event["endDate"] = item["endDate"]

    for field in ("eventZh", "eventNameZh", "activityImage", "eventImage"):
        if not event.get(field) and item.get(field):
            event[field] = item[field]

# old events 補充，但 canonical 相同不新增第二筆
for old in old_events:
    source = old.get("sourceUrl", "")
    key = canonical_source_url(source) if source else normalize_identity(old.get("eventId") or "")
    
    if not key or key in grouped:
        continue
    grouped[key] = old

return sorted(
    grouped.values(),
    key=lambda x: (
        x.get("startDate") or "9999",
        x.get("eventZh") or x.get("event") or ""
    )
)

=========================================================

HISTORY

=========================================================

def history_detail(item):
return {
"id": item.get("id", ""),
"event": item.get("event", ""),
"eventZh": item.get("eventZh", ""),
"name": item.get("name", ""),
"venue": item.get("venue", ""),
"startDate": item.get("startDate", ""),
"endDate": item.get("endDate", ""),
"sourceUrl": item.get("sourceUrl", ""),
}

def compare_items(old_items, new_items):
old_map = {item.get("id"): item for item in old_items if item.get("id")}
new_map = {item.get("id"): item for item in new_items if item.get("id")}

added = [key for key in new_map if key not in old_map]
removed = [key for key in old_map if key not in new_map]
changed = [
    key for key in new_map
    if key in old_map and old_map[key] != new_map[key]
]

return added, removed, changed

=========================================================

MAIN

=========================================================

def main():
print("========================================")
print("Pokémon GO GO Stamp Rally Sync 7.0")
print("Canonical activity dedupe")
print("PokéXciting unified")
print("Manual override protected")
print("========================================")

old_data = load_json(
    STAMP_FILE,
    {
        "version": "7.0",
        "events": [],
        "list": []
    }
)

old_items = old_data.get("list", [])
if not isinstance(old_items, list):
    old_items = []

old_events = old_data.get("events", [])
if not isinstance(old_events, list):
    old_events = []

overrides = load_manual_overrides()
old_items = apply_manual_overrides(old_items, overrides)
urls = discover_urls(old_items)

print("Candidates:", len(urls))

fresh = []
for url in urls:
    print("CHECK:", url)
    try:
        rows = parse_stamp_page(url, old_items)
        if rows:
            print("  FOUND:", len(rows))
            fresh.extend(rows)
    except Exception as error:
        print("  PARSE ERROR:", error)
    time.sleep(REQUEST_DELAY)

merged = merge_items(old_items, fresh)

# 官方座標缺失時再補地理編碼。
# 人工 override 跳過。
for item in merged:
    override = find_manual_override(item, overrides)
    if override:
        continue
    enrich_coordinates(item)
    time.sleep(REQUEST_DELAY)

merged = apply_manual_overrides(merged, overrides)

merged.sort(
    key=lambda x: (
        x.get("startDate", ""),
        x.get("event", ""),
        x.get("pref", ""),
        x.get("name", ""),
        x.get("id", "")
    )
)

events = build_event_metadata(merged, old_events)
added, removed, changed = compare_items(old_items, merged)

now = datetime.now(timezone.utc).astimezone()
updated = now.strftime("%Y-%m-%d %H:%M:%S")

write_json(
    STAMP_FILE,
    {
        "version": "7.0",
        "updated": updated,
        "source": "official",
        "sourceMode": (
            "official GO discovery; canonical activity dedupe; "
            "PokéXciting unified; manual overrides protected; "
            "place-name geocoding fallback"
        ),
        "rule": (
            "Only in-game Pokémon GO GO Stamp Rally. "
            "Offline stamp rallies, ordinary PokéStops and Poké Lid are excluded."
        ),
        "events": events,
        "list": merged
    }
)

# =====================================================
# HISTORY
# =====================================================
history = load_json(HISTORY_FILE, {"history": []})
history_rows = history.get("history", [])
if not isinstance(history_rows, list):
    history_rows = []

merged_map = {item.get("id"): item for item in merged if item.get("id")}

if added or removed or changed:
    history_rows.insert(
        0,
        {
            "time": updated,
            "type": "stamp",
            "event": "Automatic official GO Stamp Rally sync",
            "eventZh": "自動同步 Pokémon GO 官方 GO 集章趣",
            "source": "Pokémon GO Official Website",
            "total": len(merged),
            "added": added,
            "removed": removed,
            "changed": changed,
            "addedItems": [
                history_detail(merged_map[key])
                for key in added if key in merged_map
            ],
            "removedItems": [
                {"id": key} for key in removed
            ],
            "changedItems": [
                history_detail(merged_map[key])
                for key in changed if key in merged_map
            ]
        }
    )

history_rows = history_rows[:100]
write_json(HISTORY_FILE, {"history": history_rows})

print("========================================")
print("Records:", len(merged))
print("Events:", len(events))
print("Added:", len(added))
print("Removed:", len(removed))
print("Changed:", len(changed))
print("========================================")

if name == "main":
main()
