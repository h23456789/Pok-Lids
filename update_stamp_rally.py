import hashlib
import json
import re
import time
import html as html_lib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
CENTER_FILE = ROOT / "data" / "pokemon_center.json"

TIMEOUT = 30
REQUEST_DELAY = 0.30
GEOCODE_DELAY = 1.10
MAX_NEWS_PAGES = 12
MAX_DISCOVERED_PAGES = 180
MAX_POINTS_PER_EVENT = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36 "
        "PokemonJapanCollection-GOStampSync/12.0"
    ),
    "Accept-Language": "zh-TW,zh;q=0.95,en;q=0.8,ja;q=0.7",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# 只允許 Pokémon GO 官方網域作為「活動發現來源」。
GO_DOMAINS = {
    "pokemongo.com",
    "www.pokemongo.com",
}

# Pokémon Center 官方頁只作為「Pokémon Center 圖示 / 店舖座標」的補充來源，
# 活動本身仍必須先由 Pokémon GO 官方文章發現。
CENTER_DOMAINS = {
    "shop.pokemon.co.jp",
    "www.pokemon.co.jp",
    "pokemon.co.jp",
}

DISCOVERY_ROOTS = [
    "https://pokemongo.com/zh-Hant/news",
    "https://pokemongo.com/en/news",
    "https://pokemongo.com/ja/news",
    "https://pokemongo.com/zh-Hant/featured-in-person-events/",
    "https://pokemongo.com/en/featured-in-person-events/",
    "https://pokemongo.com/ja/featured-in-person-events/",
]

# 只拿「Pokémon GO 遊戲內 GO 集章趣」，不是一般線下 Stamp Rally。
GO_STAMP_TERMS = (
    "go集章趣",
    "go stamp rally",
    "go stamp rallies",
    "goスタンプラリー",
    "stamp rally",
    "stamp rallies",
)

GAMEPLAY_TERMS = (
    "pokémon go",
    "pokemon go",
    "寶可補給站",
    "pokéstop",
    "pokestop",
    "pokéstops",
    "digital stamp",
    "數位圖章",
    "遊戲內圖章",
    "stamp sheet",
    "剪貼簿",
    "campfire",
)

EXCLUDE_TERMS = (
    "poké lid",
    "pokelid",
    "ポケふた",
    "寶可夢人孔蓋",
    "jr east",
    "jreast",
    "名鉄",
    "nexco",
)

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

# 舊資料／官方 Center 資料中常見的中日名稱，僅用於匹配既有 Center 圖示與座標。
CENTER_ALIASES = {
    "ポケモンセンターサッポロ": "寶可夢中心札幌",
    "ポケモンセンタートウホク": "寶可夢中心東北",
    "ポケモンセンタートウキョーDX": "寶可夢中心東京DX",
    "ポケモンセンターメガトウキョー": "寶可夢中心Mega東京",
    "ポケモンセンターシブヤ": "寶可夢中心澀谷",
    "ポケモンセンタースカイツリータウン": "寶可夢中心晴空塔",
    "ポケモンセンタートウキョーベイ": "寶可夢中心東京灣",
    "ポケモンセンターヨコハマ": "寶可夢中心橫濱",
    "ポケモンセンターナゴヤ": "寶可夢中心名古屋",
    "ポケモンセンターカナザワ": "寶可夢中心金澤",
    "ポケモンセンターキョウト": "寶可夢中心京都",
    "ポケモンセンターオーサカDX": "寶可夢中心大阪DX",
    "ポケモンセンターオーサカ": "寶可夢中心大阪",
    "ポケモンセンターヒロシマ": "寶可夢中心廣島",
    "ポケモンセンターカガワ": "寶可夢中心香川",
    "ポケモンセンターフクオカ": "寶可夢中心福岡",
    "ポケモンセンターオキナワ": "寶可夢中心沖繩",
    "Pokémon GO Lab.": "Pokémon GO Lab.",
}


def norm(value):
    value = html_lib.unescape(str(value or ""))
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def is_go_url(url):
    try:
        return (urlparse(url).hostname or "").lower() in GO_DOMAINS
    except Exception:
        return False


def is_center_url(url):
    try:
        return (urlparse(url).hostname or "").lower() in CENTER_DOMAINS
    except Exception:
        return False


def canonical_url(url):
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def get(url):
    try:
        response = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text
    except Exception as exc:
        print("HTTP ERROR:", url, exc)
        return ""


def load_json(path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha(*parts):
    raw = "|".join(norm(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16].upper()


def parse_date(value):
    value = norm(value)
    patterns = [
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
        r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})",
        r"(20\d{2})年(\d{1,2})月",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return f"{groups[0]}-{int(groups[1]):02d}-{int(groups[2]):02d}"
    return ""


def extract_dates(text):
    values = []
    for pattern in (
        r"20\d{2}年\d{1,2}月\d{1,2}日",
        r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}",
    ):
        for raw in re.findall(pattern, text or ""):
            value = parse_date(raw)
            if value and value not in values:
                values.append(value)
    return sorted(values)


def localize_url(url, locale="zh-Hant"):
    parsed = urlparse(url)
    path = parsed.path
    path = re.sub(r"^/(?:en|ja|zh-Hant|zh_Hant|zh)/", f"/{locale}/", path)
    path = re.sub(r"^/(?:en|ja|zh-Hant|zh_Hant|zh)$", f"/{locale}/", path)
    if not path.startswith(f"/{locale}/") and parsed.netloc.endswith("pokemongo.com"):
        if path.startswith("/news/"):
            path = f"/{locale}" + path
        elif path.startswith("/featured-in-person-events/"):
            path = f"/{locale}" + path
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def page_is_go_stamp(text):
    lower = norm(text).lower()
    # Pokémon GO 官方頁本身已經是可信來源，因此只要求「集章」語彙 +
    # 明確的遊戲內情境（PokéStop / digital stamp / stamp sheet / in-game 等）。
    has_stamp = any(term.lower() in lower for term in GO_STAMP_TERMS)
    has_gameplay = any(term.lower() in lower for term in GAMEPLAY_TERMS)
    if not has_stamp or not has_gameplay:
        return False

    # 嚴格排除已由 Lid 系統處理的ポケふた。
    if any(term.lower() in lower for term in EXCLUDE_TERMS[:3]):
        return False

    # 一般「Stamp Rally」若沒有明確的 PokéStop / digital / in-game 語境，排除。
    strong_go_context = any(term in lower for term in (
        "go stamp rally", "goスタンプラリー", "go集章趣",
        "pokéstop", "pokestop", "digital stamp", "in-game stamp",
        "stamp sheet", "stamp rally is activated", "spin their photo discs",
        "遊戲內圖章", "數位圖章", "指定的寶可補給站", "寶可補給站"
    ))
    return strong_go_context


def extract_title(soup):
    h1 = soup.find("h1")
    if h1:
        title = norm(h1.get_text(" ", strip=True))
        if title:
            return title
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        return norm(meta["content"])
    if soup.title:
        return norm(soup.title.get_text(" ", strip=True))
    return "Pokémon GO GO 集章趣"


def extract_description(soup):
    for attrs in (
        {"property": "og:description"},
        {"name": "description"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            return norm(meta["content"])
    return ""


def find_go_stamp_sections(soup):
    """Return section containers beginning at headings that mention GO Stamp Rally."""
    sections = []
    headings = soup.find_all(["h2", "h3", "h4"])
    for index, heading in enumerate(headings):
        title = norm(heading.get_text(" ", strip=True)).lower()
        if not any(term.lower() in title for term in GO_STAMP_TERMS):
            continue
        nodes = []
        current = heading.find_next_sibling()
        next_heading = headings[index + 1] if index + 1 < len(headings) else None
        while current and current is not next_heading:
            nodes.append(current)
            current = current.find_next_sibling()
        sections.append((heading, nodes))
    return sections


def extract_stamp_image_candidates(soup, base_url, section_nodes):
    candidates = []
    pools = [section_nodes, list(soup.find_all("img"))]
    for pool in pools:
        for node in pool:
            imgs = [node] if getattr(node, "name", None) == "img" else node.find_all("img") if hasattr(node, "find_all") else []
            for img in imgs:
                src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or ""
                if not src:
                    continue
                absolute = urljoin(base_url, src)
                alt = norm(img.get("alt", ""))
                probe = f"{absolute} {alt}".lower()
                score = 0
                if any(x in probe for x in ("stamp", "rally", "stamp-rally", "スタンプ", "go_stamp")):
                    score += 10
                if any(x in probe for x in ("banner", "header", "kv", "hero")):
                    score -= 4
                candidates.append((score, absolute))
        if candidates:
            break
    candidates.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    result = []
    for score, url in candidates:
        if url in seen:
            continue
        seen.add(url)
        result.append({"url": url, "score": score})
    return result


def extract_activity_image(soup, base_url, section_nodes=None):
    """Prefer the official article hero/OG image for the activity banner."""
    for attrs in (
        {"property": "og:image"},
        {"name": "twitter:image"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            return urljoin(base_url, norm(meta.get("content")))

    # Fallback: first reasonably large image from the section/page.
    pools = []
    if section_nodes:
        pools.extend(section_nodes)
    pools.extend(soup.find_all("img"))
    for node in pools:
        img = node if getattr(node, "name", None) == "img" else None
        if img is None and hasattr(node, "find"):
            img = node.find("img")
        if not img:
            continue
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if not src:
            continue
        return urljoin(base_url, src)
    return ""


def find_point_specific_image(soup, base_url, point_name, section_nodes):
    """Find an official image explicitly associated with one named point.

    Never returns the article hero/banner merely because it is on the same page.
    """
    target = norm(point_name).lower()
    if not target:
        return ""

    candidates = []
    nodes = []
    nodes.extend(section_nodes or [])
    nodes.extend(soup.find_all(["figure", "li", "p", "a"]))

    seen_nodes = set()
    for node in nodes:
        ident = id(node)
        if ident in seen_nodes:
            continue
        seen_nodes.add(ident)
        text = norm(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else ""
        if not text:
            continue
        low = text.lower()
        if target not in low and low not in target:
            continue
        for img in node.find_all("img") if hasattr(node, "find_all") else []:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            if not src:
                continue
            absolute = urljoin(base_url, src)
            alt = norm(img.get("alt", ""))
            probe = f"{text} {alt} {absolute}".lower()
            if any(bad in probe for bad in ("banner", "hero", "header", "kv")):
                continue
            score = 0
            if target in probe:
                score += 20
            if "stamp" in probe or "スタンプ" in probe or "圖章" in probe:
                score += 10
            candidates.append((score, absolute))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates and candidates[0][0] >= 20 else ""

def extract_jsonld_objects(soup):
    objects = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, list):
            objects.extend(payload)
        elif isinstance(payload, dict):
            objects.append(payload)
    return objects


def geo_from_jsonld(soup):
    for obj in extract_jsonld_objects(soup):
        candidates = obj.get("location", []) if isinstance(obj, dict) else []
        if not candidates:
            candidates = [obj]
        if not isinstance(candidates, list):
            candidates = [candidates]
        for loc in candidates:
            if not isinstance(loc, dict):
                continue
            geo = loc.get("geo")
            if isinstance(geo, dict):
                try:
                    lat = float(geo.get("latitude"))
                    lng = float(geo.get("longitude"))
                    if -90 <= lat <= 90 and -180 <= lng <= 180:
                        return [lat, lng]
                except Exception:
                    pass
    return []


def coords_from_url(url):
    patterns = [
        r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
        r"(?:q|query|ll|center)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
        r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return [lat, lng]
    return []


def extract_map_links(soup, base_url):
    out = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"])
        lower = href.lower()
        if "google.com/maps" in lower or "maps.google" in lower or "maps.app.goo.gl" in lower:
            out.append({
                "text": norm(anchor.get_text(" ", strip=True)),
                "url": href,
                "coords": coords_from_url(href),
            })
    return out


def extract_coords_from_text(text):
    for pattern in (
        r"(-?\d{1,3}\.\d{4,})\s*[,、]\s*(-?\d{1,3}\.\d{4,})",
        r"緯度[^0-9-]*(-?\d{1,3}\.\d+).*?經度[^0-9-]*(-?\d{1,3}\.\d+)",
        r"latitude[^0-9-]*(-?\d{1,3}\.\d+).*?longitude[^0-9-]*(-?\d{1,3}\.\d+)",
    ):
        match = re.search(pattern, text or "", re.I | re.S)
        if match:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return [lat, lng]
    return []


def extract_location_country(text):
    lower = norm(text).lower()
    countries = [
        ("taiwan", "Taiwan"), ("台灣", "Taiwan"), ("台北", "Taiwan"),
        ("malaysia", "Malaysia"), ("馬來西亞", "Malaysia"), ("kuala lumpur", "Malaysia"),
        ("singapore", "Singapore"), ("新加坡", "Singapore"),
        ("philippines", "Philippines"), ("菲律賓", "Philippines"), ("manila", "Philippines"),
        ("thailand", "Thailand"), ("泰國", "Thailand"), ("bangkok", "Thailand"),
        ("brazil", "Brazil"), ("巴西", "Brazil"), ("rio de janeiro", "Brazil"),
        ("germany", "Germany"), ("德國", "Germany"), ("munich", "Germany"),
        ("portugal", "Portugal"), ("葡萄牙", "Portugal"), ("lisbon", "Portugal"),
        ("australia", "Australia"), ("澳洲", "Australia"), ("brisbane", "Australia"),
        ("japan", "Japan"), ("日本", "Japan"),
    ]
    for key, country in countries:
        if key in lower:
            return country
    return ""


def geocode(query, country, cache):
    query = norm(query)
    if not query:
        return [], False
    key = f"{country}|{query}"
    if key in cache:
        value = cache[key]
        return value.get("coords", []), bool(value.get("ok"))

    try:
        full_query = f"{query}, {country}" if country else query
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": full_query,
                "format": "jsonv2",
                "limit": 1,
            },
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        if data:
            coords = [float(data[0]["lat"]), float(data[0]["lon"])]
            cache[key] = {"coords": coords, "ok": True}
            time.sleep(GEOCODE_DELAY)
            return coords, True
    except Exception as exc:
        print("GEOCODE ERROR:", query, exc)

    cache[key] = {"coords": [], "ok": False}
    time.sleep(GEOCODE_DELAY)
    return [], False


def center_records():
    data = load_json(CENTER_FILE, {})
    if isinstance(data, dict):
        if isinstance(data.get("list"), list):
            return data["list"]
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("data"), list):
            return data["data"]
        return []
    if isinstance(data, list):
        return data
    return []


def normalize_center_name(value):
    text = norm(value).lower()
    for ja, zh in CENTER_ALIASES.items():
        if text == ja.lower():
            return zh.lower()
    return text


def find_center_record(name, records):
    target = normalize_center_name(name)
    if not target:
        return None
    for item in records:
        candidates = [
            item.get("id"), item.get("name"), item.get("title"), item.get("city"),
            item.get("venue"), item.get("nameZh"), item.get("centerKey"), item.get("image"),
        ]
        for candidate in candidates:
            c = normalize_center_name(candidate)
            if not c:
                continue
            if c == target or c in target or target in c:
                return item
    return None


def find_center_icon(item, records):
    center = find_center_record(item.get("venue") or item.get("name") or item.get("nameZh"), records)
    if not center:
        return ""
    return (
        center.get("pokemonCenterIcon")
        or center.get("centerIcon")
        or center.get("icon")
        or center.get("image")
        or ""
    )


def find_center_coords(item, records):
    center = find_center_record(item.get("venue") or item.get("name") or item.get("nameZh"), records)
    if not center:
        return []
    coords = center.get("coords")
    if isinstance(coords, list) and len(coords) >= 2:
        try:
            return [float(coords[0]), float(coords[1])]
        except Exception:
            pass
    try:
        lat = float(center.get("lat"))
        lng = float(center.get("lng"))
        return [lat, lng]
    except Exception:
        return []


def extract_prefecture(text):
    text = norm(text)
    for alias, canonical in PREF_ALIASES:
        if alias in text:
            return canonical
    return ""


def event_identity(title, url):
    return "GO-STAMP-" + sha(title, canonical_url(url))


def point_identity(event_id, name, index):
    return f"{event_id}-P{index:03d}-{sha(name, index)[:8]}"


def clean_point_text(text):
    text = norm(text)
    text = re.sub(r"^[-•●◆◇★☆\s]+", "", text)
    text = re.sub(r"^\d+[.)、]\s*", "", text)
    return text.strip("：:;； ")


def parse_point_candidates(section_nodes):
    candidates = []
    seen = set()

    for node in section_nodes:
        # 先處理明確的 <li>
        for li in node.find_all("li"):
            text = clean_point_text(li.get_text(" ", strip=True))
            if text:
                key = text.lower()
                if key not in seen:
                    seen.add(key)
                    candidates.append(text)

        # 有些官方頁用段落/strong 列出地點。
        for p in node.find_all(["p", "strong", "h4"]):
            text = clean_point_text(p.get_text(" ", strip=True))
            if not text or len(text) < 3 or len(text) > 180:
                continue
            if any(x in text.lower() for x in (
                "how do", "starting the stamp", "collecting stamps", "finishing a stamp",
                "more details", "please be aware", "開始挑戰", "蒐集圖章", "完成集章",
                "遊玩", "敬請參閱",
            )):
                continue
            key = text.lower()
            if key not in seen:
                seen.add(key)
                candidates.append(text)

    # 過濾明顯是敘述句而非地點。
    filtered = []
    for text in candidates:
        low = text.lower()
        if any(term in low for term in ("2026年", "september", "august", "start the stamp rally", "the way you")):
            # 含日期的條目仍可能是地點，保留短而像地點的條目。
            if len(text) > 120:
                continue
        if len(text) > 180:
            continue
        filtered.append(text)
    return filtered[:MAX_POINTS_PER_EVENT]


def infer_event_name(title, url):
    title = norm(title)
    # 用官方文章標題作主名稱；若是 City Safari，補上城市。
    if title:
        return title
    path = urlparse(url).path
    return path.rstrip("/").split("/")[-1] or "Pokémon GO GO 集章趣"


def extract_center_event_links(soup, base_url):
    links=[]
    seen=set()
    for a in soup.find_all("a", href=True):
        href=urljoin(base_url,a["href"])
        if not is_center_url(href):
            continue
        text=norm(a.get_text(" ",strip=True))
        probe=(text+" "+href).lower()
        if not any(k in probe for k in ("pokemoncenter","ポケモンセンター","stamp","スタンプ","/shop/")):
            continue
        c=canonical_url(href)
        if c in seen:
            continue
        seen.add(c)
        links.append(c)
    return links

def extract_address(soup):
    text=norm(soup.get_text(" ",strip=True))
    for pattern in (r"〒\s*\d{3}-?\d{4}\s*([^|｜]{5,180})",r"住所\s*[:：]?\s*([^|｜]{5,180})",r"Address\s*[:：]?\s*([^|｜]{5,180})"):
        m=re.search(pattern,text,re.I)
        if m:
            return norm(m.group(1))
    return ""

def extract_center_points_from_official_page(go_url, go_soup, event_id, event_title, event_title_zh, start_date, end_date, old_items=None):
    points = []
    seen = set()
    centers = center_records()
    old_items = old_items or []
    # 只要舊資料同一活動、同一店舖，就沿用舊 ID，避免使用者已獲得狀態因同步而消失。
    def legacy_match(name):
        for old in old_items:
            if norm(old.get("event", "")) == norm(event_title) and norm(old.get("name", old.get("venue", ""))) == norm(name):
                return old
        return None
    old_event_ids = [o.get("eventId") for o in old_items if norm(o.get("event", "")) == norm(event_title) and o.get("eventId")]
    if old_event_ids:
        event_id = old_event_ids[0]
    center_pages = extract_center_event_links(go_soup, go_url)

    # 先從官方活動頁連結取得中心名單。
    discovered_names = []
    for center_page in center_pages:
        html = get(center_page)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        page_text = norm(soup.get_text(" ", strip=True))
        if "スタンプラリー" not in page_text and "stamp rally" not in page_text.lower():
            continue
        for a in soup.find_all("a", href=True):
            name = norm(a.get_text(" ", strip=True))
            if not name:
                continue
            if "ポケモンセンター" in name or "Pokemon Center" in name or "Pokémon Center" in name or "Pokémon GO Lab." in name or "GO Lab" in name:
                if any(bad in name for bad in ("ポケモンカフェ", "ポケモンストア", "サテライト", "出張所")):
                    continue
                discovered_names.append((name, urljoin(center_page, a["href"])))
        # 有些店舖會在頁面文字而非連結中出現；以既有官方 Center 資料作名稱對照。
        lower_page = page_text.lower()
        for center in centers:
            name = norm(center.get("name") or center.get("title") or center.get("venue") or "")
            if not name or "ポケモンセンター" not in name:
                continue
            if name.lower() in lower_page:
                discovered_names.append((name, center_page))
        time.sleep(REQUEST_DELAY)

    # 建立去重後的中心名稱。
    for name, href in discovered_names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        legacy = legacy_match(name)
        item = {
            "id": legacy.get("id") if legacy else point_identity(event_id, name, len(points) + 1),
            "eventId": event_id,
            "event": event_title,
            "eventZh": event_title_zh,
            "eventName": event_title,
            "eventNameZh": event_title_zh,
            "activity": "GO Stamp Rally",
            "activityZh": "GO 集章趣",
            "venueType": "pokemon_go_lab" if "GO Lab" in name else "pokemon_center",
            "venue": name,
            "venueZh": CENTER_ALIASES.get(name, name),
            "name": name,
            "nameZh": CENTER_ALIASES.get(name, name),
            "country": "Japan",
            "pref": "",
            "city": "",
            "address": "",
            "coords": [],
            "lat": None,
            "lng": None,
            "stampImage": "",
            "stampImageOfficial": False,
            "stampImageSource": "",
            "startDate": start_date,
            "endDate": end_date,
            "reward": "",
            "rewardZh": "",
            "source": "Pokémon GO Official Website / Pokémon Center Official Website",
            "sourceUrl": go_url,
            "venueSourceUrl": href,
            "official": True,
            "coordinatesOfficial": False,
            "coordsSource": "",
        }

        center = find_center_record(name, centers)
        if center:
            coords = center.get("coords")
            if isinstance(coords, list) and len(coords) >= 2:
                try:
                    coords = [float(coords[0]), float(coords[1])]
                except Exception:
                    coords = []
            else:
                try:
                    coords = [float(center.get("lat")), float(center.get("lng"))]
                except Exception:
                    coords = []
            if coords:
                item["coords"] = coords
                item["lat"], item["lng"] = coords
                item["coordinatesOfficial"] = True
                item["coordsSource"] = "既有 Pokémon Center 官方資料"
            # 注意：GO 集章趣內頁必須使用「實際遊戲圖章」，
            # 不把 Pokémon Center Logo / 店舖圖示當成 Stamp。
            item["pref"] = center.get("pref", "") or center.get("prefecture", "")
            item["city"] = center.get("city", "")
            item["address"] = center.get("address", "")
        else:
            venue_html = get(href) if is_center_url(href) else ""
            if venue_html:
                venue_soup = BeautifulSoup(venue_html, "html.parser")
                item["address"] = extract_address(venue_soup)
                for ml in extract_map_links(venue_soup, href):
                    if ml.get("coords"):
                        item["coords"] = ml["coords"]
                        item["lat"], item["lng"] = ml["coords"]
                        item["coordinatesOfficial"] = True
                        item["coordsSource"] = "Pokémon Center 官方頁面的 Google Maps"
                        break
                if not item["coords"]:
                    geo = geo_from_jsonld(venue_soup)
                    if geo:
                        item["coords"] = geo
                        item["lat"], item["lng"] = geo
                        item["coordinatesOfficial"] = True
                        item["coordsSource"] = "Pokémon Center 官方頁面的結構化資料"
        if not item["pref"]:
            item["pref"] = extract_prefecture(item["address"])
        points.append(item)

    return points


def extract_rally_name(text, fallback_title):
    text = norm(text)

    # 官方繁中／日文頁常把活動名稱放在「」或『』內。
    patterns = [
        r"「([^」]{0,140}(?:GO集章趣|GOスタンプラリー|スタンプラリー)[^」]{0,80})」",
        r"『([^』]{0,140}(?:GO集章趣|GOスタンプラリー|スタンプラリー)[^』]{0,80})』",
        r"“([^”]{0,140}(?:GO集章趣|GO Stamp Rally|Stamp Rally)[^”]{0,80})”",
        r"\"([^\"]{0,140}(?:GO集章趣|GO Stamp Rally|Stamp Rally)[^\"]{0,80})\"",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            candidate = norm(match.group(1))
            if len(candidate) >= 4:
                if candidate.strip() in {"GO集章趣", "GOスタンプラリー", "GO Stamp Rally", "a GO Stamp Rally"} or candidate.lower() in {"a go stamp rally"}:
                    return norm(fallback_title) + "｜GO 集章趣"
                return candidate

    # 無書名號時，從包含 GO Stamp Rally 的短句取名稱。
    patterns = [
        r"([A-Z][A-Za-z0-9!&'’().:：・/\- ]{0,140}(?:GO )?Stamp Rally)",
        r"([A-Z][A-Za-z0-9!&'’().:：・/\- ]{0,140}Stamp Rallies)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            candidate = norm(match.group(1))
            candidate = re.sub(r"^(?:Enjoy|Take part in|Join|The)\s+", "", candidate, flags=re.I)
            if len(candidate) >= 4:
                if candidate.strip().lower() in {"a go stamp rally", "go stamp rally", "stamp rally"}:
                    return norm(fallback_title) + "｜GO 集章趣"
                return candidate

    # 中文頁只有「GO集章趣」而沒有完整名稱時，取前後文短句。
    for term in ("GO集章趣", "GO Stamp Rally", "GOスタンプラリー"):
        pos = text.lower().find(term.lower())
        if pos >= 0:
            left = max(0, pos - 70)
            right = min(len(text), pos + len(term) + 90)
            snippet = norm(text[left:right])
            if snippet:
                # 優先從最後一個句號/驚嘆號後開始。
                parts = re.split(r"[。.!！?？]", snippet)
                candidate = norm(parts[-1])
                if len(candidate) >= 4:
                    return candidate

    return norm(fallback_title) or "Pokémon GO GO 集章趣"

def zh_event_name(original_name, localized_name):
    """Prefer official Traditional-Chinese localized text.
    No activity names are hard-coded here.
    """
    original_name = norm(original_name)
    localized_name = norm(localized_name)
    if localized_name and localized_name not in {"GO集章趣", "GOスタンプラリー", "GO Stamp Rally", "a GO Stamp Rally"}:
        return localized_name
    if original_name and original_name not in {"GO集章趣", "GOスタンプラリー", "GO Stamp Rally"}:
        return original_name + "｜GO 集章趣"
    return "GO 集章趣"

def extract_event_payload(url, soup, localized_soup=None, old_items=None):
    source_soup = localized_soup or soup
    text = norm(source_soup.get_text(" ", strip=True))
    original_text = norm(soup.get_text(" ", strip=True))
    title_zh = extract_title(source_soup)
    title_original = extract_title(soup)
    description_zh = extract_description(source_soup)

    sections = find_go_stamp_sections(source_soup)
    if not sections:
        sections = find_go_stamp_sections(soup)

    # 每個文章通常是一個活動；若一篇文章含多個 GO 集章趣標題，才拆成多個子活動。
    section_payloads = []
    for idx, (heading, nodes) in enumerate(sections, start=1):
        heading_text = norm(heading.get_text(" ", strip=True))
        points = parse_point_candidates(nodes)
        images = extract_stamp_image_candidates(source_soup, url, nodes)
        section_text = norm(" ".join(n.get_text(" ", strip=True) for n in nodes))
        section_dates = extract_dates(heading_text + " " + section_text)
        section_payloads.append({
            "heading": heading_text,
            "nodes": nodes,
            "points": points,
            "images": images,
            "text": section_text,
            "dates": section_dates,
            "index": idx,
        })

    if not section_payloads:
        section_payloads = [{
            "heading": title_zh,
            "nodes": [],
            "points": [],
            "images": extract_stamp_image_candidates(source_soup, url, []),
            "text": text,
            "dates": extract_dates(text),
            "index": 1,
        }]

    # 若只有一個小節，活動名稱沿用文章 H1；多個則使用小節標題。
    outputs = []
    for payload in section_payloads:
        section_text = payload.get("text", "")
        rally_name_zh = extract_rally_name(section_text, title_zh)
        rally_name_original = extract_rally_name(original_text, title_original)

        # 多個 GO 集章趣同頁時，以每個 GO 集章趣 section 分開；單一活動則使用該活動名稱。
        event_title_zh = zh_event_name(rally_name_original, rally_name_zh)
        if len(section_payloads) > 1 and payload["heading"]:
            heading_zh = norm(payload["heading"])
            if "集章" in heading_zh or "Stamp Rally" in heading_zh or "スタンプラリー" in heading_zh:
                event_title_zh = heading_zh
        event_title_original = rally_name_original
        event_id = event_identity(event_title_original + "|" + payload["heading"], url)
        all_dates = payload["dates"] or extract_dates(original_text)
        start_date = all_dates[0] if all_dates else ""
        end_date = all_dates[-1] if len(all_dates) >= 2 else ""

        # 找活動頁上的地點資訊；先從段落中的文字/連結取得。
        points = []
        point_names = payload["points"]
        map_links = extract_map_links(source_soup, url)
        event_country = extract_location_country(text + " " + original_text)
        activity_image = extract_activity_image(source_soup, url, payload.get("nodes") or [])

        # If the official section explicitly contains Pokémon Center locations,
        # enrich them from the existing official Center dataset. The activity
        # itself is still discovered dynamically from Pokémon GO.
        has_center_points = any(
            "ポケモンセンター" in p or "pokemon center" in p.lower() or "Pokémon Center" in p
            for p in point_names
        )
        if has_center_points:
            center_points = extract_center_points_from_official_page(
                url, soup, event_id, event_title_original, event_title_zh,
                start_date, end_date, old_items
            )
            if center_points:
                points.extend(center_points)
                point_names = [
                    p for p in point_names
                    if not ("ポケモンセンター" in p or "pokemon center" in p.lower() or "Pokémon Center" in p)
                ]

        for position, point_name in enumerate(point_names, start=len(points) + 1):
            point = {
                "id": point_identity(event_id, point_name, position),
                "eventId": event_id,
                "event": event_title_original,
                "eventZh": event_title_zh,
                "name": point_name,
                "nameZh": point_name,
                "venue": point_name,
                "venueZh": point_name,
                "country": event_country,
                "pref": extract_prefecture(point_name),
                "city": "",
                "address": "",
                "coords": [],
                "lat": None,
                "lng": None,
                "stampImage": "",
                "stampImageOfficial": False,
                "stampImageSource": "",
                "startDate": start_date,
                "endDate": end_date,
                "source": "Pokémon GO Official Website",
                "sourceUrl": url,
                "official": True,
                "coordinatesOfficial": False,
                "coordsSource": "",
                "expectedStamps": None,
                "descriptionZh": description_zh,
            }

            # 1) 若是 Pokémon Center，直接匹配既有 Center 圖示 / 座標。
            if "ポケモンセンター" in point_name or "Pokémon Center" in point_name or "pokemon center" in point_name.lower():
                centers = center_records()
                center_coords = find_center_coords(point, centers)
                if center_coords:
                    point["coords"] = center_coords
                    point["lat"], point["lng"] = center_coords
                    point["coordinatesOfficial"] = True
                    point["coordsSource"] = "Pokémon Center 官方資料"

            # 2) 嘗試附近文字鏈結的 Google Maps 座標。
            if not point["coords"]:
                for link in map_links:
                    label = link["text"].lower()
                    if label and (label in point_name.lower() or point_name.lower() in label):
                        if link["coords"]:
                            point["coords"] = link["coords"]
                            point["lat"], point["lng"] = link["coords"]
                            point["coordinatesOfficial"] = True
                            point["coordsSource"] = "Pokémon GO 官方頁面的 Google Maps"
                            break

            # 3) 活動頁 JSON-LD 的地理資訊。
            if not point["coords"]:
                geo = geo_from_jsonld(source_soup)
                if geo:
                    point["coords"] = geo
                    point["lat"], point["lng"] = geo
                    point["coordinatesOfficial"] = True
                    point["coordsSource"] = "Pokémon GO 官方頁面的結構化資料"

            # 3b) 解析官方頁面內嵌腳本中的常見 lat/lng 欄位。
            if not point["coords"]:
                embedded = " ".join(
                    (script.string or script.get_text() or "")
                    for script in source_soup.find_all("script")
                )
                point_geo = extract_coords_from_text(embedded)
                if point_geo:
                    point["coords"] = point_geo
                    point["lat"], point["lng"] = point_geo
                    point["coordinatesOfficial"] = True
                    point["coordsSource"] = "Pokémon GO 官方頁面內嵌資料"

            # 4) 只在官方沒有公開座標時，以公開地理編碼作為 fallback；不冒充官方。
            if not point["coords"]:
                query = point_name
                coords, ok = geocode(query, event_country or "", GEOCODE_CACHE)
                if coords:
                    point["coords"] = coords
                    point["lat"], point["lng"] = coords
                    point["coordinatesOfficial"] = False
                    point["coordsSource"] = "OpenStreetMap Nominatim（地理編碼 fallback）"

            # 5) 圖章圖片：只接受「與此集章點有明確關聯」的官方圖片。
            # 活動 Banner 絕不直接當成單一 Stamp。
            point_specific_image = find_point_specific_image(
                source_soup, url, point_name, payload.get("nodes") or []
            )
            if point_specific_image:
                point["stampImage"] = point_specific_image
                point["stampImageOfficial"] = True
                point["stampImageSource"] = "Pokémon GO 官方頁面：集章點對應圖片"

            points.append(point)

        # 如果官方只公布了活動總枚數而未公開點名，仍保留活動本身。
        expected = None
        expected_match = re.search(
            r"(?:collect|collect up to|蒐集|收集|集滿)\s*(?:up to\s*)?(\d+)\s*(?:stamps?|枚|個|個圖章|枚圖章)",
            text,
            re.I,
        )
        if expected_match:
            expected = int(expected_match.group(1))
        if expected is None:
            expected_match = re.search(r"(\d+)枚(?:の)?(?:スタンプ|圖章)", original_text)
            if expected_match:
                expected = int(expected_match.group(1))

        if expected and points:
            for point in points:
                point["expectedStamps"] = expected

        outputs.append({
            "eventId": event_id,
            "event": event_title_original,
            "eventZh": event_title_zh,
            "eventName": title_original,
            "eventNameZh": title_zh,
            "activity": "GO Stamp Rally",
            "activityZh": "GO 集章趣",
            "startDate": start_date,
            "endDate": end_date,
            "expectedStamps": expected,
            "descriptionZh": description_zh,
            "source": "Pokémon GO Official Website",
            "sourceUrl": url,
            "official": True,
            "points": points,
            "activityImage": activity_image,
        })

    return outputs


def is_candidate_go_path(url):
    path=urlparse(url).path.lower()
    return any(token in path for token in (
        "/news/",
        "/featured-in-person-events/",
        "/gofest/",
        "/citysafari/",
        "/events/",
        "/event/",
        "/post/",
    ))


def discover_links(root_url, max_pages=220):
    queue=[root_url]
    visited=set()
    results=set()
    pages=0
    while queue and pages < max_pages:
        url=canonical_url(queue.pop(0))
        if url in visited or not is_go_url(url):
            continue
        visited.add(url)
        html=get(url)
        pages += 1
        if not html:
            continue
        soup=BeautifulSoup(html,"html.parser")
        text=norm(soup.get_text(" ",strip=True))
        if page_is_go_stamp(text):
            results.add(url)
        for anchor in soup.find_all("a",href=True):
            absolute=canonical_url(urljoin(url,anchor["href"]))
            if not is_go_url(absolute) or absolute in visited:
                continue
            if is_candidate_go_path(absolute):
                if absolute not in queue:
                    queue.append(absolute)
        time.sleep(REQUEST_DELAY)
    return sorted(results)


def discover_official_stamp_pages():
    """Discover GO Stamp Rally pages from Pokémon GO itself.

    There is intentionally no fixed activity list. We crawl the official News /
    event navigation and keep only pages whose content describes an in-game GO
    Stamp Rally.
    """
    candidates=set()
    roots=list(DISCOVERY_ROOTS)

    # Crawl each official root and collect pagination links instead of assuming
    # a single query-string format for the news archive.
    for root in list(DISCOVERY_ROOTS):
        html=get(root)
        if not html:
            continue
        soup=BeautifulSoup(html,"html.parser")
        for anchor in soup.find_all("a",href=True):
            href=canonical_url(urljoin(root,anchor["href"]))
            if not is_go_url(href):
                continue
            path=urlparse(href).path.lower()
            if "/news" in path or is_candidate_go_path(href):
                roots.append(href)
        time.sleep(REQUEST_DELAY)

    # Deduplicate roots while keeping stable order.
    seen_roots=[]
    seen=set()
    for root in roots:
        root=canonical_url(root)
        if root not in seen:
            seen.add(root)
            seen_roots.append(root)

    for root in seen_roots:
        print("DISCOVER:",root)
        found=discover_links(root,max_pages=180 if "/news" in root else 100)
        candidates.update(found)

    return sorted(candidates)


def localized_soup(url, fallback_soup):
    localized = localize_url(url, "zh-Hant")
    if canonical_url(localized) == canonical_url(url):
        return fallback_soup
    html = get(localized)
    if not html:
        return fallback_soup
    soup = BeautifulSoup(html, "html.parser")
    text = norm(soup.get_text(" ", strip=True))
    if page_is_go_stamp(text):
        return soup
    return fallback_soup


def flatten_events(events):
    items = []
    seen = set()
    for event in events:
        for point in event.get("points", []):
            point_id = point.get("id")
            if not point_id or point_id in seen:
                continue
            seen.add(point_id)
            items.append(point)
    return items


def legacy_is_allowed(item):
    """保留既有合法 GO 集章趣快取，不保留先前誤加入的線下活動。"""
    text = norm(" ".join(
        str(item.get(k, ""))
        for k in ("event", "eventName", "activity", "eventZh", "activityZh")
    )).lower()
    source = norm(item.get("sourceUrl", ""))
    is_go_source = is_go_url(source)
    has_go_term = any(term.lower() in text for term in GO_STAMP_TERMS)
    has_gameplay = any(term.lower() in text for term in GAMEPLAY_TERMS)
    excluded = any(term.lower() in text for term in EXCLUDE_TERMS)
    if excluded:
        return False
    # 既有資料若是由 Pokémon Center 官方頁補充而來，仍必須有 GO 集章趣語境。
    return (is_go_source or is_center_url(source)) and (has_go_term or has_gameplay)


def merge_preserving(old_items, fresh_items):
    merged = {}

    # 先保留既有真正 GO 集章趣快取，避免一次網路故障讓既有資料消失。
    for item in old_items:
        if item.get("id") and legacy_is_allowed(item):
            merged[item["id"]] = item

    # 新鮮官方資料覆蓋舊資料。
    for item in fresh_items:
        if item.get("id"):
            merged[item["id"]] = item

    # 同一 eventId + point name 去重，優先新資料。
    dedup = {}
    for item in merged.values():
        key = (
            norm(item.get("eventId", "")),
            norm(item.get("name", "")),
            norm(item.get("venue", "")),
        )
        if not key[0]:
            key = (norm(item.get("id", "")), "", "")
        dedup[key] = item

    result = list(dedup.values())
    result.sort(key=lambda x: (
        x.get("startDate", "9999-99-99"),
        x.get("eventZh", x.get("event", "")),
        x.get("nameZh", x.get("name", "")),
        x.get("id", ""),
    ))
    return result


def compare(old_items, new_items):
    old_map = {item.get("id"): item for item in old_items if item.get("id")}
    new_map = {item.get("id"): item for item in new_items if item.get("id")}

    added = [key for key in new_map if key not in old_map]
    removed = [key for key in old_map if key not in new_map]
    changed = [key for key in new_map if key in old_map and old_map[key] != new_map[key]]
    return added, removed, changed


def history_detail(item):
    return {
        "id": item.get("id", ""),
        "event": item.get("event", ""),
        "eventZh": item.get("eventZh", ""),
        "name": item.get("name", ""),
        "nameZh": item.get("nameZh", ""),
        "lat": item.get("lat"),
        "lng": item.get("lng"),
        "startDate": item.get("startDate", ""),
        "endDate": item.get("endDate", ""),
        "sourceUrl": item.get("sourceUrl", ""),
    }


def cleanup_empty_duplicate_events(items):
    # 若同一活動已經有實際 point，就移除舊的空 placeholder。
    groups = {}
    for item in items:
        groups.setdefault(item.get("eventId"), []).append(item)
    out = []
    for event_id, group in groups.items():
        has_real_points = any(norm(x.get("name", "")) for x in group)
        if has_real_points:
            out.extend(group)
        else:
            out.extend(group[:1])
    return out


def main():
    print("=" * 60)
    print("Pokémon GO GO 集章趣 AUTO SYNC")
    print("Official Pokémon GO discovery mode")
    print("No hard-coded activity list")
    print("=" * 60)

    global GEOCODE_CACHE
    GEOCODE_CACHE = {}
    old_data = load_json(STAMP_FILE, {"list": []})
    old_items = old_data.get("list", []) if isinstance(old_data, dict) else []

    official_pages = discover_official_stamp_pages()
    print("Official GO Stamp Rally pages:", len(official_pages))

    fresh_events = []
    fresh_items = []

    for url in official_pages:
        print("PARSE:", url)
        html = get(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        text = norm(soup.get_text(" ", strip=True))
        if not page_is_go_stamp(text):
            continue
        zh_soup = localized_soup(url, soup)
        try:
            event_payloads = extract_event_payload(url, soup, zh_soup, old_items)
            for event in event_payloads:
                # 嚴格排除 Poké Lid。
                event_text = norm(
                    " ".join([
                        event.get("event", ""),
                        event.get("eventZh", ""),
                        event.get("activity", ""),
                        event.get("activityZh", ""),
                    ])
                ).lower()
                if any(term.lower() in event_text for term in EXCLUDE_TERMS):
                    print("  EXCLUDED:", event.get("eventZh"))
                    continue
                fresh_events.append(event)
                fresh_items.extend(event.get("points", []))
                print("  FOUND:", event.get("eventZh"), "points=", len(event.get("points", [])))
        except Exception as exc:
            print("  PARSE ERROR:", exc)
        time.sleep(REQUEST_DELAY)

    # 去重
    unique_items = {}
    for item in fresh_items:
        if item.get("id"):
            unique_items[item["id"]] = item
    fresh_items = list(unique_items.values())

    if not fresh_items:
        print("No fresh official GO Stamp Rally data found.")
        print("Existing official cache kept unchanged.")
        return

    merged = merge_preserving(old_items, fresh_items)
    merged = cleanup_empty_duplicate_events(merged)
    merged = [item for item in merged if legacy_is_allowed(item) or item in fresh_items]

    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    added, removed, changed = compare(old_items, merged)

    old_event_meta = {}
    if isinstance(old_data, dict):
        for event in old_data.get("events", []) or []:
            if event.get("eventId"):
                old_event_meta[event["eventId"]] = event
    for event in fresh_events:
        old_event_meta[event["eventId"]] = {
            "eventId": event.get("eventId"),
            "event": event.get("event", ""),
            "eventZh": event.get("eventZh", ""),
            "eventName": event.get("eventName", ""),
            "eventNameZh": event.get("eventNameZh", ""),
            "activity": "GO Stamp Rally",
            "activityZh": "GO 集章趣",
            "startDate": event.get("startDate", ""),
            "endDate": event.get("endDate", ""),
            "expectedStamps": event.get("expectedStamps"),
            "descriptionZh": event.get("descriptionZh", ""),
            "source": "Pokémon GO Official Website",
            "sourceUrl": event.get("sourceUrl", ""),
            "official": True,
            "activityImage": event.get("activityImage", ""),
        }
    event_meta = list(old_event_meta.values())
    point_count = {}
    for item in merged:
        eid = item.get("eventId")
        if eid: point_count[eid] = point_count.get(eid, 0) + 1
    for event in event_meta:
        event["pointCount"] = point_count.get(event.get("eventId"), 0)
    event_meta.sort(key=lambda x: (x.get("startDate", "9999-99-99"), x.get("eventZh", "")))

    save_json(
        STAMP_FILE,
        {
            "version": "12.0",
            "updated": timestamp,
            "source": "Pokémon GO Official Website",
            "sourceMode": "automatic-discovery",
            "rule": "Pokémon GO GO 集章趣 only; Poké Lid and offline stamp rallies excluded",
            "events": event_meta,
            "list": merged,
        },
    )

    history = load_json(HISTORY_FILE, {"history": []})
    history_list = history.get("history", []) if isinstance(history, dict) else []
    merged_map = {item.get("id"): item for item in merged if item.get("id")}

    if added or removed or changed:
        history_list.insert(0, {
            "time": timestamp,
            "type": "stamp",
            "event": "Automatic Pokémon GO GO 集章趣 sync",
            "eventZh": "自動同步 Pokémon GO GO 集章趣",
            "source": "Pokémon GO Official Website",
            "total": len(merged),
            "added": added,
            "removed": removed,
            "changed": changed,
            "addedItems": [history_detail(merged_map[x]) for x in added if x in merged_map],
            "changedItems": [history_detail(merged_map[x]) for x in changed if x in merged_map],
            "removedItems": [history_detail({"id": x}) for x in removed],
        })

    save_json(HISTORY_FILE, {"history": history_list[:100]})

    print("=" * 60)
    print("Total records:", len(merged))
    print("Added:", len(added))
    print("Removed:", len(removed))
    print("Changed:", len(changed))
    print("=" * 60)


if __name__ == "__main__":
    main()
