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

# =========================================================
# PATHS
# =========================================================
ROOT = Path(__file__).resolve().parent
STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
OVERRIDE_FILE = ROOT / "svgstamp_manual_overrides.json"

# =========================================================
# CONFIG
# =========================================================
TIMEOUT = 30
REQUEST_DELAY = 0.35
MAX_DISCOVERY_PAGES = 80
MAX_SITEMAP_URLS = 4000
GEOCODER_URL = "https://nominatim.openstreetmap.org/search"

# =========================================================
# HTTP
# =========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36 "
        "PokemonJapanCollectionUpdater/5.0"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,ja-JP,ja;q=0.8,en;q=0.7",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# =========================================================
# OFFICIAL DOMAINS
# =========================================================
OFFICIAL_DOMAINS = {
    "pokemongo.com",
    "www.pokemongo.com",
}

# =========================================================
# DISCOVERY
# =========================================================
DISCOVERY_URLS = [
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
    "デジタルスタンプラリー",
    "GO 集章趣",
    "GO集章趣",
    "STAMP RALLY",
    "Stamp Rally",
    "stamp rally",
]

# =========================================================
# EXCLUDE TEACHING / FAQ
# =========================================================
INSTRUCTIONAL_STAMP_PATTERNS = [
    r"我該怎麼進行.*(?:GO)?\s*集章趣",
    r"我怎麼(?:進行|參加|玩).*集章趣",
    r"GO\s*集章趣.*(?:玩法|教學|說明|怎麼玩)",
    r"如何.*(?:GO)?\s*集章趣",
    r"怎麼.*(?:GO)?\s*集章趣",
    r"how to (?:participate|play|do).*stamp rally",
    r"how (?:do|to).*stamp rally",
    r"stamp rally.*(?:how to|guide|how it works|instructions)",
    r"(?:ご利用方法|遊び方|参加方法|楽しみ方).*スタンプラリー",
    r"スタンプラリー.*(?:ご利用方法|遊び方|参加方法|楽しみ方)",
    r"(?:faq|frequently asked questions).*stamp rally",
]


def normalize_text(value):
    if value is None:
        return ""
    value = str(value).replace("\u3000", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_identity(value):
    value = normalize_text(value).lower()
    return re.sub(r"[\s\u3000\-‐-–—_・･.,，。:：/\\()（）「」『』【】]", "", value)


def is_instructional_stamp_text(value):
    text = normalize_text(value)
    if not text:
        return False
    return any(re.search(pattern, text, re.I) for pattern in INSTRUCTIONAL_STAMP_PATTERNS)


# =========================================================
# CANONICAL URL
# =========================================================
def canonical_source_url(url):
    raw = normalize_text(url)
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        path = parsed.path.rstrip("/")
        path = re.sub(r"^/(?:en|ja|zh-hant|zh_hant)(?=/|$)", "", path, flags=re.I)
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host + path
    except Exception:
        return raw.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")


def preferred_source_rank(url):
    path = normalize_text(url).lower()
    if "/zh-hant/" in path or "/zh_hant/" in path:
        return 0
    if "/ja/" in path:
        return 1
    if "/en/" in path:
        return 2
    return 3


# =========================================================
# HTTP HELPERS
# =========================================================
def is_official_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        return host in OFFICIAL_DOMAINS
    except Exception:
        return False


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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_hash(*parts):
    raw = "|".join(normalize_text(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


# =========================================================
# DATE
# =========================================================
def parse_date(value):
    if not value:
        return ""
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
    values = []
    for pattern in (r"20\d{2}年\d{1,2}月\d{1,2}日", r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}"):
        for raw in re.findall(pattern, text or ""):
            date = parse_date(raw)
            if date and date not in values:
                values.append(date)
    return sorted(values)


# =========================================================
# EVENT EXTRACTION
# =========================================================
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
        text = normalize_text(soup.title.get_text(" ", strip=True))
        if text:
            candidates.append(text)

    for text in candidates:
        if any(kw in text.lower() for kw in ("スタンプラリー", "stamp rally", "集章趣")):
            return text

    match = re.search(r".{0,80}(?:GO\s*)?スタンプラリー.{0,120}", page_text or "")
    if match:
        return normalize_text(match.group(0))

    return candidates[0] if candidates else "GO 集章趣"


def extract_image(soup, base_url):
    for attrs in ({"property": "og:image"}, {"name": "twitter:image"}):
        meta = soup.find("meta", attrs=attrs)
        if meta:
            value = normalize_text(meta.get("content", ""))
            if value:
                return urljoin(base_url, value)
    return ""


def extract_reward(page_text):
    for keyword in ("プレゼント内容", "プレゼント条件", "認定証", "コンプリート", "景品", "賞品"):
        pos = page_text.find(keyword)
        if pos >= 0:
            return normalize_text(page_text[pos:pos + 500])
    return ""


def extract_activity(page_text):
    if "GOスタンプラリー" in page_text or "GO 集章趣" in page_text or "GO集章趣" in page_text:
        return "GO Stamp Rally"
    return "GO Stamp Rally"


def extract_prefecture(text):
    text = normalize_text(text)
    aliases = [
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
    for alias, canonical in aliases:
        if alias in text:
            return canonical
    return ""


# =========================================================
# MANUAL OVERRIDES
# =========================================================
def load_manual_overrides():
    data = load_json(OVERRIDE_FILE, {"items": []})
    if not isinstance(data, dict):
        return []
    items = data.get("items", [])
    return items if isinstance(items, list) else []


def find_manual_override(item, overrides):
    item_id = normalize_text(item.get("id", ""))
    event_id = normalize_text(item.get("eventId", ""))
    names = [item.get("venue"), item.get("name"), item.get("venueZh"), item.get("nameZh")]
    normalized_names = {normalize_identity(x) for x in names if x}

    if item_id:
        for override in overrides:
            if normalize_text(override.get("id", "")) == item_id:
                return override

    for override in overrides:
        override_event = normalize_text(override.get("eventId", ""))
        if event_id and override_event and event_id != override_event:
            continue

        override_names = []
        for field in ("venue", "name", "venueZh", "nameZh"):
            value = override.get(field)
            if value:
                override_names.append(normalize_identity(value))

        for field in ("venueAliases", "aliases"):
            values = override.get(field, [])
            if isinstance(values, list):
                for value in values:
                    if value:
                        override_names.append(normalize_identity(value))

        if normalized_names & set(override_names):
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
                item["coords"] = [lat, lng]
                item["lat"] = lat
                item["lng"] = lng
                item["coordinatesManual"] = True
                item["coordsSource"] = override.get("coordinatesSource") or "Manual override"
            except (TypeError, ValueError):
                pass

        image = normalize_text(override.get("manualStampImage", ""))
        if image:
            item["stampImage"] = image
            item["stampImageManual"] = True
            item["stampImageSource"] = override.get("stampImageSource") or "Manual override"

        badge = normalize_text(override.get("manualCenterBadge", ""))
        if badge:
            item["centerBadgeImage"] = badge
            item["centerBadgeManual"] = True
    return items


# =========================================================
# EVENT SIGNAL
# =========================================================
def has_strong_stamp_event_signal(soup, page_text, url):
    if is_excluded_go_stamp_text(page_text) or is_excluded_go_stamp_text(url):
        return False

    title_candidates = []
    for tag in soup.find_all(["h1", "h2"]):
        text = normalize_text(tag.get_text(" ", strip=True))
        if text:
            title_candidates.append(text)

    if soup.title:
        title_candidates.append(normalize_text(soup.title.get_text(" ", strip=True)))

    for attrs in ({"property": "og:title"}, {"name": "twitter:title"}):
        meta = soup.find("meta", attrs=attrs)
        if meta:
            title_candidates.append(normalize_text(meta.get("content", "")))

    if any(is_instructional_stamp_text(value) for value in title_candidates if value):
        return False

    path = urlparse(url).path.lower().rstrip("/")
    listing_paths = {
        "/news", "/ja/news", "/en/news", "/zh-hant/news", "/zh_hant/news",
        "/event", "/events", "/info", "/featured-in-person-events",
        "/ja/featured-in-person-events", "/en/featured-in-person-events",
        "/zh-hant/featured-in-person-events", "/zh_hant/featured-in-person-events",
    }
    if path in listing_paths:
        return False

    lower_body = page_text.lower()
    stamp_signal = any(
        token in lower_body
        for token in ("go stamp rally", "goスタンプラリー", "go 集章趣", "go集章趣", "pokemon go stamp rally", "pokémon go stamp rally")
    )
    if not stamp_signal:
        return False

    title_has_stamp = any(
        ("stamp rally" in value.lower()) or "スタンプラリー" in value or "集章趣" in value
        for value in title_candidates
    )

    has_date = bool(extract_dates(page_text))
    location_signal = any(
        token.lower() in lower_body
        for token in ("city safari", "go wild area", "go fest", "pokemon center", "ポケモンセンター", "nagasaki", "東京", "大阪", "cross-region", "asia-pacific", "stamp point", "collect stamps")
    )

    return sum([bool(title_has_stamp), bool(has_date), bool(location_signal)]) >= 2



# =========================================================
# GLOBAL GO STAMP RALLY FILTER / EVENT FAMILY
# =========================================================
def is_excluded_go_stamp_text(value):
    text = normalize_text(value).lower()
    if not text:
        return False

    # Poké Lid is a different collection in this project.
    if any(token in text for token in ("poké lid", "poke lid", "pokelid", "ポケふた")):
        return True

    # Pokémon Center / GO Lab on-site rally is intentionally excluded.
    if any(token in text for token in (
        "pokemon center", "pokémon center", "ポケモンセンター",
        "pokemon go lab", "pokémon go lab"
    )):
        return True

    return False


def event_family_key(event="", source_url="", page_text=""):
    """
    Return one logical activity key across languages and regional detail pages.

    Important:
    PokéXciting! APAC cross-region GO Stamp Rally is ONE activity.
    Taipei / Kuala Lumpur / Singapore / Manila / Bangkok points all belong
    under the same event instead of becoming separate event cards.
    """
    combined = " ".join([
        normalize_text(event),
        normalize_text(source_url),
        normalize_text(page_text),
    ]).lower()

    if "pokexciting" in combined or "pokéxciting" in combined:
        if any(token in combined for token in (
            "stamp rally", "go集章趣", "go 集章趣", "goスタンプラリー",
            "cross-region", "asia-pacific", "apac"
        )):
            return "family:pokexciting-apac-go-stamp-rally"

    canonical = canonical_source_url(source_url)
    if canonical:
        return "source:" + canonical

    return "event:" + normalize_identity(event)


def event_id_for_family(event="", source_url="", page_text=""):
    family = event_family_key(event, source_url, page_text)
    if family == "family:pokexciting-apac-go-stamp-rally":
        return "STAMP-EVENT-POKEXCITING-APAC"
    return "STAMP-AUTO-" + make_hash(family)

# =========================================================
# EVENT ID
# =========================================================
def get_event_id(event, source_url, old_items, page_text=""):
    family = event_family_key(event, source_url, page_text)

    # Reuse an existing ID from any page already belonging to the same family.
    for item in old_items:
        old_family = event_family_key(
            item.get("event") or item.get("eventName") or "",
            item.get("sourceUrl", ""),
            ""
        )
        if old_family == family:
            event_id = item.get("eventId") or ""
            if event_id:
                return event_id

    return event_id_for_family(event, source_url, page_text)


def get_item_id(event_id, venue):
    return "STAMP-POINT-" + make_hash(normalize_identity(event_id), normalize_identity(venue))


def get_existing_item_id(event_id, venue, old_items, source_url=""):
    event_key = normalize_identity(event_id)
    venue_key = normalize_identity(venue)
    source_key = canonical_source_url(source_url)

    for item in old_items:
        if normalize_identity(item.get("eventId")) == event_key and normalize_identity(item.get("venue") or item.get("name")) == venue_key:
            return item.get("id", "")

    if source_key and venue_key:
        for item in old_items:
            old_source = canonical_source_url(item.get("sourceUrl", ""))
            old_venue = normalize_identity(item.get("venue") or item.get("name"))
            if old_source == source_key and old_venue == venue_key:
                return item.get("id", "")
    return ""


# =========================================================
# SITEMAP
# =========================================================
def discover_sitemaps():
    sitemaps = set()
    text = get_html("https://pokemongo.com/robots.txt")
    for match in re.findall(r"(?im)^\s*Sitemap:\s*(\S+)\s*$", text):
        if is_official_url(match):
            sitemaps.add(match)

    sitemaps.update({
        "https://pokemongo.com/sitemap.xml",
        "https://pokemongo.com/sitemap_index.xml",
    })
    return sorted(sitemaps)


def parse_sitemap(url, visited=None, url_limit=MAX_SITEMAP_URLS):
    if visited is None:
        visited = set()
    if url in visited:
        return set()
    visited.add(url)

    if len(visited) > 25:
        return set()

    html = get_html(url)
    if not html:
        return set()

    try:
        root = ET.fromstring(html)
    except ET.ParseError:
        return set()

    found = set()
    root_tag = root.tag.lower()

    if root_tag.endswith("sitemapindex"):
        for child in root.iter():
            if not child.tag.lower().endswith("loc") or not child.text:
                continue
            child_url = child.text.strip()
            if not is_official_url(child_url):
                continue
            found.update(parse_sitemap(child_url, visited, url_limit))
            if len(found) >= url_limit:
                break
    elif root_tag.endswith("urlset"):
        for child in root.iter():
            if not child.tag.lower().endswith("loc") or not child.text:
                continue
            child_url = child.text.strip()
            if is_official_url(child_url):
                found.add(child_url)
                if len(found) >= url_limit:
                    break
    return found


# =========================================================
# DISCOVERY
# =========================================================
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
        page_text = normalize_text(soup.get_text(" ", strip=True))

        if has_strong_stamp_event_signal(soup, page_text, url):
            candidates.add(url)

        for link in soup.find_all("a", href=True):
            absolute = urljoin(url, link["href"])
            absolute = absolute.split("#", 1)[0]
            if not is_official_url(absolute):
                continue

            text = normalize_text(link.get_text(" ", strip=True))
            combined = f"{text} {absolute}"

            if any(keyword.lower() in combined.lower() for keyword in STAMP_KEYWORDS):
                candidates.add(absolute)

            path = urlparse(absolute).path.lower()
            if any(token in path for token in (
                "/info/", "/event/", "/events/", "/campaign/", "/common/events/",
                "/featured-in-person-events/", "/gofest/", "/gowildarea/", "/news/",
            )):
                if absolute not in visited and absolute not in queue:
                    queue.append(absolute)

        time.sleep(REQUEST_DELAY)

    for sitemap in discover_sitemaps():
        urls = parse_sitemap(sitemap)
        for url in urls:
            lower = url.lower()
            if any(token in lower for token in (
                "event", "events", "campaign", "info", "stamp", "rally", "gofest", "gowildarea", "citysafari", "featured-in-person-events"
            )):
                candidates.add(url)

    deduped = {}
    for candidate in candidates:
        key = canonical_source_url(candidate)
        current = deduped.get(key)
        if current is None or preferred_source_rank(candidate) < preferred_source_rank(current):
            deduped[key] = candidate

    return sorted(deduped.values())


# =========================================================
# CENTER
# =========================================================
CENTER_HINTS = {
    "ポケモンセンターサッポロ": ("北海道", "札幌市"),
    "ポケモンセンタートウホク": ("宮城県", "仙台市"),
    "ポケモンセンタートウキョーDX": ("東京都", "中央区"),
    "ポケモンセンターメガトウキョー": ("東京都", "豊島区"),
    "ポケモンセンターシブヤ": ("東京都", "渋谷区"),
    "ポケモンセンタースカイツリータウン": ("東京都", "墨田区"),
    "ポケモンセンタートウキョーベイ": ("千葉県", "船橋市"),
    "ポケモンセンターヨコハマ": ("神奈川県", "横浜市"),
    "ポケモンセンターナゴヤ": ("愛知県", "名古屋市"),
    "ポケモンセンターカナザワ": ("石川県", "金沢市"),
    "ポケモンセンターキョウト": ("京都府", "京都市"),
    "ポケモンセンターオーサカDX": ("大阪府", "大阪市"),
    "ポケモンセンターオーサカ": ("大阪府", "大阪市"),
    "ポケモンセンターヒロシマ": ("広島県", "広島市"),
    "ポケモンセンターカガワ": ("香川県", "高松市"),
    "ポケモンセンターフクオカ": ("福岡県", "福岡市"),
    "ポケモンセンターオキナワ": ("沖縄県", "沖縄市"),
    "Pokémon GO Lab.": ("東京都", "豊島区"),
}


def extract_center_links(soup, base_url):
    results = []
    seen = set()

    for link in soup.find_all("a", href=True):
        name = normalize_text(link.get_text(" ", strip=True))
        if not name:
            continue
        if "ポケモンセンター" not in name:
            continue
        if any(bad in name for bad in ("サテライト", "出張所", "ポケモンカフェ")):
            continue

        key = normalize_identity(name)
        if key in seen:
            continue

        results.append({
            "name": name,
            "url": urljoin(base_url, link["href"]),
        })
        seen.add(key)
    return results


def enrich_location(item, venue_url):
    html = get_html(venue_url)
    if not html:
        return item

    soup = BeautifulSoup(html, "html.parser")
    text = normalize_text(soup.get_text(" ", strip=True))
    address = ""

    patterns = (
        r"〒\s*\d{3}-?\d{4}\s*([^|｜]{5,180})",
        r"住所\s*[:：]?\s*([^|｜]{5,180})",
    )

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            address = normalize_text(match.group(1))
            break

    item["address"] = address
    if not item.get("pref"):
        item["pref"] = extract_prefecture(address)

    known = CENTER_HINTS.get(item.get("venue") or item.get("name", ""))
    if known:
        known_pref, known_city = known
        if not item.get("pref"):
            item["pref"] = known_pref
        if not item.get("city"):
            item["city"] = known_city

    item["venueSourceUrl"] = venue_url
    return item


# =========================================================
# GENERAL GEOCODING
# =========================================================
def geocode_place(query):
    if not query:
        return None
    try:
        response = SESSION.get(
            GEOCODER_URL,
            params={"q": query, "format": "jsonv2", "limit": 1},
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


def enrich_point_coordinates(item):
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
    pref = normalize_text(item.get("pref") or item.get("prefZh") or "")
    event = normalize_text(item.get("event") or item.get("eventName") or "")

    country = normalize_text(item.get("country") or item.get("countryZh") or "")

    queries = []
    if venue and city and country:
        queries.append(f"{venue}, {city}, {country}")
    if venue and city and pref:
        queries.append(f"{venue}, {city}, {pref}")
    if venue and city:
        queries.append(f"{venue}, {city}")
    if venue and pref:
        queries.append(f"{venue}, {pref}")
    if event and venue:
        queries.append(f"{venue}, {event}")
    if venue:
        queries.append(venue)

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


# =========================================================
# STAMP PAGE
# =========================================================
def parse_stamp_page(url, old_items):
    html = get_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_text(soup.get_text(" ", strip=True))

    if not has_strong_stamp_event_signal(soup, page_text, url):
        print("  SKIP: non-event / instructional page")
        return []

    event = extract_event_name(soup, page_text)
    if is_instructional_stamp_text(event):
        print("  SKIP: instructional title ->", event)
        return []

    event_id = get_event_id(event, url, old_items, page_text)
    dates = extract_dates(page_text)
    start_date = dates[0] if dates else ""
    end_date = dates[1] if len(dates) >= 2 else ""
    activity_image = extract_image(soup, url)
    reward = extract_reward(page_text)
    activity = extract_activity(page_text)
    centers = extract_center_links(soup, url)
    items = []

    # -----------------------------------------------------
    # Pokémon Center
    # -----------------------------------------------------
    if centers:
        seen = set()
        for center in centers:
            venue = center["name"]
            venue_key = normalize_identity(venue)
            if venue_key in seen:
                continue
            seen.add(venue_key)

            known = CENTER_HINTS.get(venue, ("", ""))
            venue_type = "pokemon_go_lab" if "GO Lab" in venue else "pokemon_center"
            existing_id = get_existing_item_id(event_id, venue, old_items, url)

            item = {
                "id": existing_id or get_item_id(event_id, venue),
                "eventId": event_id,
                "event": event,
                "eventName": event,
                "eventZh": event if ("/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()) else "",
                "eventNameZh": event if ("/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()) else "",
                "activity": activity,
                "activityZh": "GO 集章趣" if ("/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()) else "",
                "venueType": venue_type,
                "venue": venue,
                "name": venue,
                "pref": known[0],
                "city": known[1],
                "address": "",
                "coords": [],
                "startDate": start_date,
                "endDate": end_date,
                "stampImage": "",
                "activityImage": activity_image,
                "eventImage": activity_image,
                "reward": reward,
                "source": "Pokémon GO Official Website",
                "sourceUrl": url,
                "venueSourceUrl": center.get("url", ""),
                "official": True,
            }

            venue_url = center.get("url", "")
            if is_official_url(venue_url):
                item = enrich_location(item, venue_url)
                time.sleep(REQUEST_DELAY)

            items.append(item)

    # -----------------------------------------------------
    # General GO Stamp Rally
    # -----------------------------------------------------
    else:
        venue = ""
        venue_type = "event"

        if "Pokémon GO Lab" in page_text:
            venue = "Pokémon GO Lab."
            venue_type = "pokemon_go_lab"
        elif "ポケモンセンター" in page_text:
            venue = "全国のポケモンセンター"
            venue_type = "pokemon_center"

        existing_id = get_existing_item_id(event_id, venue or event, old_items, url)
        items.append({
            "id": existing_id or get_item_id(event_id, venue or event),
            "eventId": event_id,
            "event": event,
            "eventName": event,
            "eventZh": event if ("/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()) else "",
            "eventNameZh": event if ("/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()) else "",
            "activity": activity,
            "activityZh": "GO 集章趣" if ("/zh-hant/" in url.lower() or "/zh_hant/" in url.lower()) else "",
            "venueType": venue_type,
            "venue": venue,
            "name": venue or event,
            "pref": extract_prefecture(page_text),
            "city": "",
            "address": "",
            "coords": [],
            "startDate": start_date,
            "endDate": end_date,
            "stampImage": "",
            "activityImage": activity_image,
            "eventImage": activity_image,
            "reward": reward,
            "source": "Pokémon GO Official Website",
            "sourceUrl": url,
            "official": True,
        })
    return items


# =========================================================
# INVALID OLD ITEMS
# =========================================================
def is_invalid_existing_stamp_item(item):
    values = [
        item.get("event", ""),
        item.get("eventName", ""),
        item.get("eventZh", ""),
        item.get("eventNameZh", ""),
        item.get("name", ""),
        item.get("venue", ""),
    ]

    if any(is_instructional_stamp_text(value) for value in values if value):
        return True
    if any(is_excluded_go_stamp_text(value) for value in values if value):
        return True

    source = normalize_text(item.get("sourceUrl", ""))
    if source and not is_official_url(source):
        return True

    # PokéXciting general celebration/city announcement is not itself a
    # Stamp Rally record. Keep only pages/items with a direct Stamp Rally signal.
    combined = " ".join(normalize_text(v) for v in values if v) + " " + source
    lower = combined.lower()
    if ("pokexciting" in lower or "pokéxciting" in lower):
        if not any(token in lower for token in (
            "stamp-rally", "stamp rally", "go集章趣", "go 集章趣", "goスタンプラリー"
        )):
            return True

    return False


# =========================================================
# MERGE
# =========================================================
def merge_items(old_items, fresh_items):
    def activity_key(item):
        return event_family_key(
            item.get("event") or item.get("eventName") or "",
            item.get("sourceUrl", ""),
            ""
        )

    def point_key(item):
        return (activity_key(item), normalize_identity(item.get("venue") or item.get("name") or ""))

    def source_rank(item):
        return preferred_source_rank(item.get("sourceUrl", ""))

    # -----------------------------------------------------
    # 舊資料清理 + 語言合併
    # -----------------------------------------------------
    old_by_key = {}
    for item in old_items:
        if not item.get("id"):
            continue
        if is_invalid_existing_stamp_item(item):
            continue

        key = point_key(item)
        current = old_by_key.get(key)
        if current is None:
            old_by_key[key] = item
            continue

        preferred = item if source_rank(item) < source_rank(current) else current
        other = current if preferred is item else item

        for field in ("eventZh", "eventNameZh", "activityZh", "nameZh", "venueZh", "cityZh", "addressZh", "activityImage", "eventImage", "rewardZh", "centerBadgeImage", "stampImage", "coords", "lat", "lng", "address"):
            if not preferred.get(field) and other.get(field):
                preferred[field] = other[field]
        old_by_key[key] = preferred

    # -----------------------------------------------------
    # 新資料語言合併
    # -----------------------------------------------------
    fresh_by_key = {}
    for item in fresh_items:
        if not item.get("id"):
            continue

        key = point_key(item)
        current = fresh_by_key.get(key)
        if current is None:
            fresh_by_key[key] = item
            continue

        preferred = item if source_rank(item) < source_rank(current) else current
        other = current if preferred is item else item

        for field in ("eventZh", "eventNameZh", "activityZh", "nameZh", "venueZh", "cityZh", "addressZh", "activityImage", "eventImage", "rewardZh", "centerBadgeImage", "stampImage"):
            if not preferred.get(field) and other.get(field):
                preferred[field] = other[field]
        fresh_by_key[key] = preferred

    # -----------------------------------------------------
    # 保留穩定 ID
    # -----------------------------------------------------
    merged = {}
    for key, item in fresh_by_key.items():
        old = old_by_key.get(key)
        if old and old.get("id"):
            item["id"] = old["id"]
        merged[item["id"]] = item

    # -----------------------------------------------------
    # 沒重新抓到的舊活動保留
    # -----------------------------------------------------
    fresh_keys = set(fresh_by_key)
    for key, item in old_by_key.items():
        if key not in fresh_keys and item.get("id"):
            merged[item["id"]] = item

    # -----------------------------------------------------
    # 同一跨地區活動統一 eventId
    # -----------------------------------------------------
    family_event_ids = {}
    for item in merged.values():
        family = activity_key(item)
        family_event_ids.setdefault(
            family,
            event_id_for_family(
                item.get("event") or item.get("eventName") or "",
                item.get("sourceUrl", ""),
                ""
            )
        )
    for item in merged.values():
        item["eventId"] = family_event_ids[activity_key(item)]

    # -----------------------------------------------------
    # 如果已有具體地點資料，移除同活動的 generic placeholder
    # -----------------------------------------------------
    concrete_activity_keys = {activity_key(item) for item in fresh_by_key.values() if item.get("pref")}
    for item_id, item in list(merged.items()):
        if activity_key(item) in concrete_activity_keys and not item.get("pref"):
            del merged[item_id]

    return list(merged.values())


# =========================================================
# EVENTS METADATA
# =========================================================
def build_events_metadata(old_events, merged):
    grouped = {}

    # -----------------------------------------------------
    # 先把舊 events 依 canonical URL 合併
    # -----------------------------------------------------
    for event in (old_events or []):
        event_probe = {
            "event": event.get("event") or event.get("eventName") or "",
            "eventName": event.get("eventName") or event.get("event") or "",
            "eventZh": event.get("eventZh") or "",
            "eventNameZh": event.get("eventNameZh") or "",
            "name": "",
            "venue": "",
            "sourceUrl": event.get("sourceUrl") or "",
        }
        if is_invalid_existing_stamp_item(event_probe):
            continue

        source = normalize_text(event.get("sourceUrl", ""))
        key = event_family_key(
            event.get("event") or event.get("eventName") or "",
            source,
            ""
        )
        if not key:
            continue

        current = grouped.get(key)
        if current is None:
            grouped[key] = dict(event)
            continue

        current_rank = preferred_source_rank(current.get("sourceUrl", ""))
        incoming_rank = preferred_source_rank(source)
        preferred = event if incoming_rank < current_rank else current
        other = current if preferred is event else event

        for field in ("event", "eventName", "eventZh", "eventNameZh", "activity", "activityZh", "descriptionZh", "activityImage", "eventImage", "reward", "rewardZh", "source", "sourceUrl"):
            if not preferred.get(field) and other.get(field):
                preferred[field] = other[field]
        grouped[key] = preferred

    # -----------------------------------------------------
    # 由 merged points 再次建立 event metadata
    # -----------------------------------------------------
    for item in merged:
        source = normalize_text(item.get("sourceUrl", ""))
        key = event_family_key(
            item.get("event") or item.get("eventName") or "",
            source,
            ""
        )
        if not key:
            continue

        current = grouped.get(key)
        if current is None:
            current = {
                "eventId": item.get("eventId") or "STAMP-AUTO-" + make_hash(key),
                "event": item.get("event") or item.get("eventName") or "GO 集章趣",
                "eventName": item.get("eventName") or item.get("event") or "GO 集章趣",
                "eventZh": item.get("eventZh") or item.get("eventNameZh") or item.get("event") or "GO 集章趣",
                "eventNameZh": item.get("eventNameZh") or item.get("eventZh") or item.get("event") or "GO 集章趣",
                "activity": item.get("activity") or "GO Stamp Rally",
                "activityZh": item.get("activityZh") or "GO 集章趣",
                "sourceUrl": source,
                "activityImage": item.get("activityImage") or item.get("eventImage") or "",
                "eventImage": item.get("eventImage") or item.get("activityImage") or "",
                "startDate": item.get("startDate") or "",
                "endDate": item.get("endDate") or "",
                "expectedStamps": None,
            }
            grouped[key] = current
        else:
            current["eventId"] = current.get("eventId") or item.get("eventId") or "STAMP-AUTO-" + make_hash(key)
            for field in ("eventZh", "eventNameZh", "activityZh", "descriptionZh", "activityImage", "eventImage", "rewardZh"):
                if not current.get(field) and item.get(field):
                    current[field] = item[field]
            if item.get("startDate") and (not current.get("startDate") or item["startDate"] < current["startDate"]):
                current["startDate"] = item["startDate"]
            if item.get("endDate") and (not current.get("endDate") or item["endDate"] > current["endDate"]):
                current["endDate"] = item["endDate"]

    # -----------------------------------------------------
    # point count
    # -----------------------------------------------------
    result = []
    for key, event in grouped.items():
        seen = set()
        point_count = 0
        for item in merged:
            source = normalize_text(item.get("sourceUrl", ""))
            item_key = event_family_key(
                item.get("event") or item.get("eventName") or "",
                source,
                ""
            )
            if item_key != key:
                continue

            venue_key = normalize_identity(item.get("venue") or item.get("name") or "")
            if not venue_key or venue_key in seen:
                continue

            seen.add(venue_key)
            point_count += 1

        event["pointCount"] = point_count
        if not event.get("expectedStamps") and point_count:
            event["expectedStamps"] = point_count
        result.append(event)

    return sorted(result, key=lambda row: (row.get("startDate") or "9999", row.get("eventZh") or row.get("event") or ""))


# =========================================================
# HISTORY
# =========================================================
def compare_items(old_items, new_items):
    old_map = {item.get("id"): item for item in old_items if item.get("id")}
    new_map = {item.get("id"): item for item in new_items if item.get("id")}
    added = [item_id for item_id in new_map if item_id not in old_map]
    changed = [item_id for item_id in new_map if item_id in old_map and old_map[item_id] != new_map[item_id]]
    removed = []
    return added, removed, changed


def history_detail(item):
    return {
        "id": item.get("id", ""),
        "event": item.get("event", ""),
        "eventZh": item.get("eventZh", ""),
        "name": item.get("name", ""),
        "venue": item.get("venue", ""),
        "pref": item.get("pref", ""),
        "city": item.get("city", ""),
        "startDate": item.get("startDate", ""),
        "endDate": item.get("endDate", ""),
        "sourceUrl": item.get("sourceUrl", ""),
    }


# =========================================================
# MAIN
# =========================================================
def main():
    print("========================================")
    print("Pokémon GO GO Stamp Rally AUTO SYNC")
    print("Official discovery + locale dedupe")
    print("Manual override protected")
    print("========================================")

    old_data = load_json(STAMP_FILE, {"version": "6.0", "events": [], "list": []})
    old_items = old_data.get("list", [])
    old_events = old_data.get("events", [])
    if not isinstance(old_items, list):
        old_items = []
    if not isinstance(old_events, list):
        old_events = []

    manual_overrides = load_manual_overrides()
    old_items = apply_manual_overrides(old_items, manual_overrides)

    print("Existing records:", len(old_items))
    print("Existing events:", len(old_events))
    print("Manual overrides:", len(manual_overrides))

    urls = discover_urls(old_items)
    print("Discovered official candidate URLs:", len(urls))

    fresh_items = []
    for url in urls:
        print("CHECK:", url)
        try:
            items = parse_stamp_page(url, old_items)
            if items:
                print("  FOUND:", len(items), "records")
                fresh_items.extend(items)
        except Exception as error:
            print("  PARSE ERROR:", error)
        time.sleep(REQUEST_DELAY)

    # -----------------------------------------------------
    # Fresh 去重
    # -----------------------------------------------------
    unique = {}
    def fresh_point_key(item):
        source = normalize_text(item.get("sourceUrl", ""))
        activity = event_family_key(
            item.get("event") or item.get("eventName") or "",
            source,
            ""
        )
        venue = normalize_identity(item.get("venue") or item.get("name") or "")
        return (activity, venue)

    for item in fresh_items:
        key = fresh_point_key(item)
        current = unique.get(key)
        if current is None:
            unique[key] = item
            continue

        current_rank = preferred_source_rank(current.get("sourceUrl", ""))
        incoming_rank = preferred_source_rank(item.get("sourceUrl", ""))
        preferred = item if incoming_rank < current_rank else current
        other = current if preferred is item else item

        for field in ("eventZh", "eventNameZh", "activityZh", "nameZh", "venueZh", "cityZh", "addressZh", "activityImage", "eventImage", "rewardZh"):
            if not preferred.get(field) and other.get(field):
                preferred[field] = other[field]
        unique[key] = preferred

    fresh_items = list(unique.values())
    fresh_items = apply_manual_overrides(fresh_items, manual_overrides)
    print("Fresh official records:", len(fresh_items))

    # -----------------------------------------------------
    # 沒有新資料也要保持既有資料
    # -----------------------------------------------------
    if not fresh_items:
        print("No fresh official Stamp Rally records.")
        rebuilt = merge_items(old_items, [])
        rebuilt = apply_manual_overrides(rebuilt, manual_overrides)
        events_metadata = build_events_metadata(old_events, rebuilt)

        if rebuilt != old_items or events_metadata != old_events:
            now = datetime.now(timezone.utc).astimezone()
            updated = now.strftime("%Y-%m-%d %H:%M:%S")
            write_json(STAMP_FILE, {
                "version": "6.0",
                "updated": updated,
                "source": "official",
                "sourceMode": "global official Pokémon GO discovery; cross-region event merge; locale dedupe; manual overrides protected",
                "events": events_metadata,
                "list": rebuilt,
            })
            print("Existing data normalized.")
        else:
            print("Existing JSON kept unchanged.")
        return

    # -----------------------------------------------------
    # Merge
    # -----------------------------------------------------
    merged = merge_items(old_items, fresh_items)

    # -----------------------------------------------------
    # 地名座標 fallback
    # -----------------------------------------------------
    for item in merged:
        override = find_manual_override(item, manual_overrides)
        if override:
            continue

        coords = item.get("coords")
        valid = False
        if isinstance(coords, list) and len(coords) >= 2:
            try:
                lat, lng = float(coords[0]), float(coords[1])
                valid = abs(lat) <= 90 and abs(lng) <= 180
            except (TypeError, ValueError):
                valid = False

        if valid:
            continue
        enrich_point_coordinates(item)
        time.sleep(REQUEST_DELAY)

    merged = apply_manual_overrides(merged, manual_overrides)
    merged.sort(key=lambda item: (item.get("startDate", ""), item.get("event", ""), item.get("pref", ""), item.get("name", ""), item.get("id", "")))

    added, removed, changed = compare_items(old_items, merged)
    now = datetime.now(timezone.utc).astimezone()
    updated = now.strftime("%Y-%m-%d %H:%M:%S")
    events_metadata = build_events_metadata(old_events, merged)

    # -----------------------------------------------------
    # Write
    # -----------------------------------------------------
    write_json(STAMP_FILE, {
        "version": "6.0",
        "updated": updated,
        "source": "official",
        "sourceMode": "global official Pokémon GO discovery; cross-region event merge; locale dedupe; official coordinates first; manual overrides protected; global place-name geocoding fallback",
        "rule": "Global in-game Pokémon GO GO Stamp Rally only. Cross-region rallies are one event containing all regional stamp points. Offline stamp rallies, Pokémon Center on-site rallies and Poké Lid are excluded.",
        "events": events_metadata,
        "list": merged,
    })

    # -----------------------------------------------------
    # History
    # -----------------------------------------------------
    history = load_json(HISTORY_FILE, {"history": []})
    history_list = history.get("history", [])
    merged_map = {item.get("id"): item for item in merged if item.get("id")}

    if added or changed or removed:
        history_list.insert(0, {
            "time": updated,
            "type": "stamp",
            "event": "Automatic official GO Stamp Rally sync",
            "eventZh": "自動同步 Pokémon GO 官方 GO 集章趣",
            "source": "Pokémon GO Official Website",
            "total": len(merged),
            "added": added,
            "removed": removed,
            "changed": changed,
            "addedItems": [history_detail(merged_map[item_id]) for item_id in added if item_id in merged_map],
            "changedItems": [history_detail(merged_map[item_id]) for item_id in changed if item_id in merged_map],
        })
    history["history"] = history_list[:100]
    write_json(HISTORY_FILE, history)

    print("========================================")
    print("Total records:", len(merged))
    print("Total events:", len(events_metadata))
    print("Added:", len(added))
    print("Changed:", len(changed))
    print("Removed:", len(removed))
    print("========================================")


if __name__ == "__main__":
    main()
