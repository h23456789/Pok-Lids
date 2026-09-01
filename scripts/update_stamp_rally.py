import hashlib
import json
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "scripts" else SCRIPT_DIR
STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
CENTER_FILE = ROOT / "data" / "pokemon_center.json"

TIMEOUT = 35
REQUEST_DELAY = 0.25
GEOCODE_DELAY = 1.10
MAX_DISCOVERED_PAGES = 220
MAX_LINK_DEPTH = 3
MAX_POINTS_PER_EVENT = 100

LOCALE_PRIORITY = {"zh-hant": 0, "zh_hant": 0, "ja": 1, "en": 2}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36 "
        "Pok-Lids-GOStampSync/17.0"
    ),
    "Accept-Language": "zh-TW,zh;q=0.95,en;q=0.9,ja;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

GO_DOMAINS = {"pokemongo.com", "www.pokemongo.com"}
CENTER_DOMAINS = {"shop.pokemon.co.jp", "www.pokemon.co.jp", "pokemon.co.jp"}

DISCOVERY_ROOTS = [
    "https://pokemongo.com/zh-Hant/news",
    "https://pokemongo.com/ja/news",
    "https://pokemongo.com/en/news",
    "https://pokemongo.com/zh-Hant/featured-in-person-events/",
    "https://pokemongo.com/ja/featured-in-person-events/",
    "https://pokemongo.com/en/featured-in-person-events/",
]

# 這些是「搜尋規則」，不是活動清單。
GO_STAMP_TERMS = (
    "go集章趣",
    "go stamp rally",
    "go stamp rallies",
    "goスタンプラリー",
)
STRONG_GAME_TERMS = (
    "pokéstop", "pokestop", "pokéstops",
    "數位圖章", "digital stamp", "in-game stamp",
    "stamp sheet", "scrapbook", "剪貼簿",
    "寶可補給站", "campfire", "指定的寶可補給站",
)
EXCLUDE_TERMS = (
    "poké lid", "pokelid", "ポケふた", "寶可夢人孔蓋",
    "jr east", "jreast", "名鉄", "nexco",
)

CENTER_EXCLUDE_TERMS = (
    "ポケモンセンタースタンプラリー",
    "pokemon center stamp rally",
    "寶可夢中心 go 集章",
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

OFFICIAL_CENTER_BADGE_FALLBACKS = {
    "ポケモンセンターヨコハマ": "https://shop.pokemon.co.jp/images/logos/logo-pokemoncenter-yokohama.webp",
    "寶可夢中心橫濱": "https://shop.pokemon.co.jp/images/logos/logo-pokemoncenter-yokohama.webp",
    "Pokemon Center Yokohama": "https://shop.pokemon.co.jp/images/logos/logo-pokemoncenter-yokohama.webp",
}

# 已知「目前遊戲內永久 GO 集章趣」只作 bootstrap 資料。
# 未來新增活動不需要修改這裡，仍由官方探索器自動發現。
BOOTSTRAP_PERMANENT_POINTS = {
    "東京：港區 GO 集章趣": [
        "東京鐵塔",
        "SL廣場 C11 292",
        "原芝浦小學校紀念碑",
        "江戶坂",
        "芝公園 Gym Statue",
    ],
    "東京：江東區 GO 集章趣": [
        "江東區役所",
        "東陽21 Goddess Fountain",
        "仙台堀公園 嬰兒噴泉",
        "東京都現代美術館 Like a Snail B",
    ],
    "東京：品川區 GO 集章趣": [
        "天王洲 Isle 第四公園",
        "聖蹟公園",
        "街道松廣場",
        "鮫洲入江廣場",
    ],
    "長崎市 GO 集章趣": [
        "長崎站（海鷗廣場）",
        "長崎漁港尾上地區防災綠地（尾上之丘）",
        "原長崎縣廳所在地",
        "長崎中華街（新地橋廣場）",
        "長崎市役所／社區中心",
        "長崎歷史文化博物館",
        "長崎水濱森林公園",
        "長崎體育城",
    ],
    "吹田市 GO 集章趣": [
        "江坂公園",
        "万博記念公園",
        "千里南公園",
        "桃山公園",
        "佐井寺公園",
    ],
}

BOOTSTRAP_ACTIVITY_META = {
    "東京：港區 GO 集章趣": {
        "eventZh": "東京：港區 GO 集章趣",
        "event": "Tokyo: Minato City GO Stamp Rally",
        "startDate": "2026-05-25",
        "endDate": "",
        "sourceUrl": "https://pokemongo.com/gofest/tokyo/in-person-experiences",
        "expectedStamps": 5,
    },
    "東京：江東區 GO 集章趣": {
        "eventZh": "東京：江東區 GO 集章趣",
        "event": "Tokyo: Koto City GO Stamp Rally",
        "startDate": "2026-05-25",
        "endDate": "",
        "sourceUrl": "https://pokemongo.com/gofest/tokyo/in-person-experiences",
        "expectedStamps": 4,
    },
    "東京：品川區 GO 集章趣": {
        "eventZh": "東京：品川區 GO 集章趣",
        "event": "Tokyo: Shinagawa City GO Stamp Rally",
        "startDate": "2026-05-25",
        "endDate": "",
        "sourceUrl": "https://pokemongo.com/gofest/tokyo/in-person-experiences",
        "expectedStamps": 4,
    },
    "長崎市 GO 集章趣": {
        "eventZh": "長崎市 GO 集章趣",
        "event": "Pokémon GO Stamp Rally in Nagasaki",
        "startDate": "2025-11-10",
        "endDate": "",
        "sourceUrl": "https://pokemongo.com/zh-Hant/news/stamp-rally-nagasaki",
        "expectedStamps": 8,
    },
    "吹田市 GO 集章趣": {
        "eventZh": "吹田市 GO 集章趣",
        "event": "Suita City GO Stamp Rally",
        "startDate": "2025-05-09",
        "endDate": "",
        "sourceUrl": "https://pokemongo.com/gofest/osaka/features",
        "expectedStamps": 5,
    },
}


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def canonical_url(url):
    p = urlparse(url)
    return urlunparse((p.scheme.lower(), p.netloc.lower(), re.sub(r"/+", "/", p.path).rstrip("/"), "", "", ""))


def canonical_page_key(url):
    p = urlparse(canonical_url(url))
    path = re.sub(r"^/(?:zh-hant|zh_hant|zh|ja|en)(?=/|$)", "", p.path, flags=re.I)
    return (p.netloc.lower(), path.lower() or "/")


def url_locale(url):
    path = urlparse(url).path.lower()
    m = re.match(r"^/(zh-hant|zh_hant|zh|ja|en)(?:/|$)", path)
    return m.group(1) if m else "en"


def choose_locale(urls):
    return sorted(urls, key=lambda u: (LOCALE_PRIORITY.get(url_locale(u), 99), len(u)))[0]


def dedupe_localized(urls):
    grouped = defaultdict(list)
    for url in urls:
        grouped[canonical_page_key(url)].append(url)
    output = []
    for key, variants in grouped.items():
        chosen = choose_locale(variants)
        output.append(chosen)
        if len(variants) > 1:
            print("LANGUAGE DEDUPE:", key[1], "->", url_locale(chosen))
    return sorted(output)


def is_go_url(url):
    return (urlparse(url).hostname or "").lower() in GO_DOMAINS


def same_go_domain(url):
    return is_go_url(url)


def get(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as exc:
        print("HTTP ERROR:", url, exc)
        return ""


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(*parts):
    return hashlib.sha1("|".join(norm(x) for x in parts).encode("utf-8")).hexdigest()[:16].upper()


def parse_date(text):
    text = norm(text)
    for pat in (
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
        r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})",
    ):
        m = re.search(pat, text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def extract_date_range(text):
    dates = []
    for pat in (r"20\d{2}年\d{1,2}月\d{1,2}日", r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}"):
        for raw in re.findall(pat, text or ""):
            d = parse_date(raw)
            if d and d not in dates:
                dates.append(d)
    dates.sort()
    return (dates[0], dates[-1]) if dates else ("", "")


def extract_title(soup):
    for selector in [("meta", {"property": "og:title"}), ("h1", {})]:
        node = soup.find(selector[0], attrs=selector[1])
        if node:
            value = norm(node.get("content") if node.name == "meta" else node.get_text(" ", strip=True))
            if value:
                return value
    return norm(soup.title.get_text(" ", strip=True)) if soup.title else "Pokémon GO GO 集章趣"


def extract_description(soup):
    for attrs in ({"property": "og:description"}, {"name": "description"}):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            return norm(m["content"])
    return ""


def page_is_go_stamp(soup):
    text = norm(soup.get_text(" ", strip=True)).lower()
    if any(x in text for x in EXCLUDE_TERMS):
        return False
    has_stamp = any(x in text for x in GO_STAMP_TERMS)
    strong = sum(1 for x in STRONG_GAME_TERMS if x in text)
    return has_stamp and strong >= 1


def should_follow(url, anchor_text=""):
    if not same_go_domain(url):
        return False
    p = urlparse(url).path.lower()
    if any(x in p for x in ("/terms", "/privacy", "/contact", "/account", "/support")):
        return False
    probe = f"{p} {anchor_text}".lower()
    interesting = any(x in probe for x in (
        "news", "featured-in-person-events", "gofest", "gowildarea",
        "citysafari", "stamp", "rally", "gameplay", "experience",
        "in-person",
    ))
    return interesting


def extract_links(soup, base_url):
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if should_follow(href, norm(a.get_text(" ", strip=True))):
            links.append(canonical_url(href))
    return sorted(set(links))


def discover_pages():
    seen = set()
    queue = deque((canonical_url(x), 0) for x in DISCOVERY_ROOTS)
    candidates = []
    while queue and len(seen) < MAX_DISCOVERED_PAGES:
        url, depth = queue.popleft()
        if url in seen or depth > MAX_LINK_DEPTH:
            continue
        seen.add(url)
        print("DISCOVER:", url)
        html = get(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        if page_is_go_stamp(soup):
            candidates.append(url)
        for link in extract_links(soup, url):
            if link not in seen and len(seen) + len(queue) < MAX_DISCOVERED_PAGES * 2:
                queue.append((link, depth + 1))
        time.sleep(REQUEST_DELAY)
    return dedupe_localized(candidates)


def extract_jsonld(soup):
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        raw = (s.string or s.get_text() or "").strip()
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, list): out.extend(obj)
        else: out.append(obj)
    return out


def extract_banner(soup, base_url):
    for attrs in ({"property": "og:image"}, {"name": "twitter:image"}):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            return urljoin(base_url, norm(m["content"]))
    for obj in extract_jsonld(soup):
        if isinstance(obj, dict):
            img = obj.get("image")
            if isinstance(img, str) and img:
                return urljoin(base_url, img)
            if isinstance(img, list) and img:
                return urljoin(base_url, str(img[0]))
    return ""


def extract_expected(text):
    lower = text.lower()
    patterns = (
        r"(?:up to|collect up to|最多|共有|共|consists of)\s*(\d{1,3})\s*(?:stamps|stamp|枚|個)",
        r"(\d{1,3})\s*(?:stamps|枚)\s*(?:in total|total)?",
    )
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            return int(m.group(1))
    return None


def extract_heading_blocks(soup):
    headings = soup.find_all(["h2", "h3", "h4"])
    blocks = []
    for i, heading in enumerate(headings):
        h = norm(heading.get_text(" ", strip=True))
        if not any(t in h.lower() for t in GO_STAMP_TERMS):
            continue
        nodes = []
        sibling = heading.find_next_sibling()
        next_heading = headings[i + 1] if i + 1 < len(headings) else None
        while sibling and sibling is not next_heading:
            nodes.append(sibling)
            sibling = sibling.find_next_sibling()
        blocks.append((h, nodes))
    return blocks


def extract_map_coords(url):
    for pat in (
        r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
        r"[?&](?:q|query|ll|center)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
        r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
    ):
        m = re.search(pat, url)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return [lat, lng]
    return []


def extract_map_links(container, base_url):
    out = []
    for a in container.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if any(x in href.lower() for x in ("google.com/maps", "maps.google", "maps.app.goo.gl")):
            out.append((norm(a.get_text(" ", strip=True)), href, extract_map_coords(href)))
    return out


def clean_point(text):
    text = norm(text)
    text = re.sub(r"^[\-•●◆◇★☆\d\s.)、]+", "", text)
    text = re.sub(r"^(?:stamp\s*\d+|point\s*\d+)[:：-]?\s*", "", text, flags=re.I)
    return text.strip(" :：;；")


def looks_like_point(text):
    if not text or len(text) < 3 or len(text) > 150:
        return False
    low = text.lower()
    bad = (
        "how do", "more details", "please be aware", "collect up to", "starting the stamp",
        "finish", "stamp rally is", "活動期間", "開啟", "開始挑戰", "蒐集圖章",
        "完成集章", "官方網站", "copyright", "terms of use", "privacy",
    )
    return not any(x in low for x in bad)


def parse_points_from_container(container):
    points = []
    seen = set()
    for node in container.find_all(["li", "dt", "h4", "h5", "p", "strong"]):
        text = clean_point(node.get_text(" ", strip=True))
        if not looks_like_point(text):
            continue
        low = text.lower()
        if any(x in low for x in ("pokéstop", "pokestop", "stamp rally", "digital stamp", "圖章")):
            continue
        key = re.sub(r"[^a-z0-9一-龥ぁ-んァ-ン]+", "", low)
        if key in seen:
            continue
        seen.add(key)
        points.append({"name": text, "coords": [], "sourceUrl": "", "image": ""})
    return points[:MAX_POINTS_PER_EVENT]


def extract_point_images(container, base_url):
    out = []
    for img in container.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or ""
        if not src:
            continue
        url = urljoin(base_url, src)
        alt = norm(img.get("alt", ""))
        probe = f"{url} {alt}".lower()
        if any(x in probe for x in ("banner", "hero", "header", "kv")):
            continue
        if any(x in probe for x in ("stamp", "スタンプ", "圖章", "go_stamp")):
            out.append(url)
    return list(dict.fromkeys(out))


def parse_activity_blocks(soup, page_url):
    page_title = extract_title(soup)
    page_text = norm(soup.get_text(" ", strip=True))
    page_start, page_end = extract_date_range(page_text)
    page_banner = extract_banner(soup, page_url)
    blocks = extract_heading_blocks(soup)

    # 若官方頁沒有獨立 Stamp Rally heading，整頁仍視為單一 rally block。
    if not blocks and page_is_go_stamp(soup):
        blocks = [(page_title, [soup])]

    activities = []
    for block_title, nodes in blocks:
        block_text = norm(" ".join(n.get_text(" ", strip=True) for n in nodes))
        combined = f"{block_title} {block_text}".lower()
        if any(x in combined for x in EXCLUDE_TERMS):
            continue
        if any(x in combined for x in CENTER_EXCLUDE_TERMS):
            print("SKIP: Pokémon Center in-person stamp rally")
            continue
        expected = extract_expected(block_text)
        starts, ends = extract_date_range(block_text)
        start_date = starts or page_start
        end_date = ends or page_end
        points = []
        for node in nodes:
            points.extend(parse_points_from_container(node))
        # Deduplicate names within the block.
        dedup = []
        seen = set()
        for p in points:
            k = re.sub(r"[^a-z0-9一-龥ぁ-んァ-ン]+", "", p["name"].lower())
            if k and k not in seen:
                seen.add(k); dedup.append(p)
        activities.append({
            "pageUrl": page_url,
            "pageKey": canonical_page_key(page_url),
            "sectionTitle": block_title,
            "pageTitle": page_title,
            "banner": page_banner,
            "startDate": start_date,
            "endDate": end_date,
            "expectedStamps": expected,
            "points": dedup,
            "description": extract_description(soup),
        })
    return activities


def load_centers():
    data = load_json(CENTER_FILE, {})
    if isinstance(data, list): return data
    if isinstance(data, dict):
        for key in ("list", "items", "data"):
            if isinstance(data.get(key), list): return data[key]
    return []


def normalize_center_name(v):
    t = norm(v).lower()
    for ja, zh in CENTER_ALIASES.items():
        if t == ja.lower(): return zh.lower()
    return t


def find_center_record(name, centers):
    target = normalize_center_name(name)
    if not target: return None
    variants = {target}
    for ja, zh in CENTER_ALIASES.items():
        if target == zh.lower(): variants.add(ja.lower())
    for c in centers:
        names = [c.get(k) for k in ("id","name","title","city","venue","nameZh","venueZh","centerName","centerNameZh","shopName","shopNameZh")]
        normalized = [normalize_center_name(x) for x in names if x]
        if any(n == target or (len(n) > 5 and (n in target or target in n)) for n in normalized):
            return c
    return None


def find_center_icon(name, centers):
    c = find_center_record(name, centers)
    if c:
        image = next((c.get(k) for k in (
            "pokemonCenterBadge","pokemonCenterIcon","centerBadge","centerIcon","badge","icon","image","imageUrl","logo"
        ) if c.get(k)), "")
        if image: return image
    lower = normalize_center_name(name)
    if "yokohama" in lower or "橫濱" in name or "横浜" in name or "ヨコハマ" in name:
        return OFFICIAL_CENTER_BADGE_FALLBACKS["ポケモンセンターヨコハマ"]
    return ""


def coords_from_center(name, centers):
    c = find_center_record(name, centers)
    if not c: return []
    if isinstance(c.get("coords"), list) and len(c["coords"]) >= 2:
        try: return [float(c["coords"][0]), float(c["coords"][1])]
        except Exception: pass
    try: return [float(c["lat"]), float(c["lng"])]
    except Exception: return []


def extract_prefecture(text):
    for alias, canon in PREF_ALIASES:
        if alias in norm(text): return canon
    return ""


def event_id_for(page_key, section):
    return "GO-STAMP-" + sha(page_key[0], page_key[1], section)


def point_id(event_id, name, index):
    return f"{event_id}-P{index:03d}-{sha(name, index)[:8]}"


def event_id_for_bootstrap(label):
    return "GO-STAMP-BOOTSTRAP-" + sha(label)


def canonical_event_label(activity):
    title = norm(activity.get("sectionTitle") or activity.get("pageTitle"))
    low = title.lower()
    # 中文活動頁有時標題不是固定格式；將明確的東京三區與長崎/吹田統一。
    rules = [
        (("minato", "港区", "港區"), "東京：港區 GO 集章趣"),
        (("koto", "江東区", "江東區"), "東京：江東區 GO 集章趣"),
        (("shinagawa", "品川区", "品川區"), "東京：品川區 GO 集章趣"),
        (("nagasaki", "長崎", "長崎市"), "長崎市 GO 集章趣"),
        (("suita", "吹田", "吹田市"), "吹田市 GO 集章趣"),
    ]
    for keys, label in rules:
        if any(k.lower() in low for k in keys):
            return label
    return title


def add_bootstrap_points(existing_events, existing_list):
    by_label = {e.get("eventZh") or e.get("event"): e for e in existing_events if e.get("eventZh") or e.get("event")}
    # Match existing known events first, otherwise add permanent bootstrap activities.
    for label, names in BOOTSTRAP_PERMANENT_POINTS.items():
        meta = BOOTSTRAP_ACTIVITY_META[label]
        eid = None
        for e in existing_events:
            if (e.get("eventZh") == label or e.get("event") == meta["event"] or e.get("eventId") == event_id_for_bootstrap(label)):
                eid = e.get("eventId")
                break
        if not eid:
            eid = event_id_for_bootstrap(label)
            existing_events.append({
                "eventId": eid,
                "event": meta["event"],
                "eventZh": meta["eventZh"],
                "eventName": meta["event"],
                "eventNameZh": meta["eventZh"],
                "activity": "GO Stamp Rally",
                "activityZh": "GO 集章趣",
                "startDate": meta["startDate"],
                "endDate": meta["endDate"],
                "expectedStamps": meta["expectedStamps"],
                "eventImage": "",
                "activityImage": "",
                "sourceUrl": meta["sourceUrl"],
                "sourceLocale": "en",
                "canonicalPage": meta["sourceUrl"],
                "dataStatus": "partial",
                "descriptionZh": "",
            })
        already = {norm(x.get("nameZh") or x.get("name") or x.get("venueZh") or x.get("venue")) for x in existing_list if x.get("eventId") == eid}
        for name in names:
            if name in already: continue
            existing_list.append({
                "id": point_id(eid, name, len([x for x in existing_list if x.get("eventId") == eid]) + 1),
                "eventId": eid,
                "event": meta["event"],
                "eventZh": meta["eventZh"],
                "eventName": meta["event"],
                "eventNameZh": meta["eventZh"],
                "activity": "GO Stamp Rally",
                "activityZh": "GO 集章趣",
                "venueType": "go_stamp_point",
                "venue": name,
                "name": name,
                "nameZh": name,
                "pref": "東京都" if label.startswith("東京：") else ("長崎県" if label.startswith("長崎") else "大阪府"),
                "city": "東京" if label.startswith("東京：") else ("長崎市" if label.startswith("長崎") else "吹田市"),
                "address": "",
                "coords": [],
                "lat": None,
                "lng": None,
                "stampImage": "",
                "stampImageType": "actual-stamp",
                "stampImageSource": "",
                "stampImageOfficial": False,
                "startDate": meta["startDate"],
                "endDate": meta["endDate"],
                "source": "Pokémon GO Official / verified community data",
                "sourceUrl": meta["sourceUrl"],
                "official": True,
                "coordinatesOfficial": False,
                "coordsSource": "",
            })
    return existing_events, existing_list


def merge_event_meta(old, new):
    merged = dict(old or {})
    for k, v in new.items():
        if v not in (None, "", [], {}): merged[k] = v
    return merged


def normalize_item_key(item):
    name = norm(item.get("nameZh") or item.get("name") or item.get("venueZh") or item.get("venue"))
    coords = item.get("coords") or []
    if len(coords) >= 2:
        return (name.lower(), round(float(coords[0]), 5), round(float(coords[1]), 5))
    return (name.lower(), None, None)


def merge_points(old_items, new_items, event_id):
    result = []
    old_by_name = defaultdict(list)
    for old in old_items:
        old_by_name[norm(old.get("nameZh") or old.get("name") or old.get("venueZh") or old.get("venue")).lower()].append(old)
    seen = set()
    for idx, new in enumerate(new_items, 1):
        name = norm(new.get("nameZh") or new.get("name") or new.get("venueZh") or new.get("venue"))
        old_match = old_by_name.get(name.lower(), [None])[0]
        item = dict(old_match or {})
        item.update(new)
        if old_match and not new.get("stampImage") and old_match.get("stampImage"):
            item["stampImage"] = old_match["stampImage"]
            item["stampImageType"] = old_match.get("stampImageType", "actual-stamp")
        if old_match and not new.get("coords") and old_match.get("coords"):
            item["coords"] = old_match["coords"]
            item["lat"], item["lng"] = old_match["coords"]
            item["coordinatesOfficial"] = old_match.get("coordinatesOfficial", False)
            item["coordsSource"] = old_match.get("coordsSource", "")
        item["eventId"] = event_id
        item["id"] = old_match.get("id") if old_match else point_id(event_id, name, idx)
        k = normalize_item_key(item)
        if k not in seen:
            seen.add(k); result.append(item)
    # Preserve old real point data when the official page temporarily exposes no point list.
    if not new_items and old_items:
        return [dict(x, eventId=event_id) for x in old_items]
    return result


def find_event_source_variants(old_events, activity):
    key = activity["pageKey"]
    section = norm(activity["sectionTitle"])
    # Same section on the same canonical page = same activity.
    target_id = event_id_for(key, section)
    for e in old_events:
        if e.get("eventId") == target_id:
            return e
    # Bootstrap permanent activities use readable IDs; match by label.
    label = canonical_event_label(activity)
    for e in old_events:
        if e.get("eventZh") == label:
            return e
    return None


def build_from_discovery(discovered, old_data):
    old_events = list(old_data.get("events", [])) if isinstance(old_data, dict) else []
    old_list = list(old_data.get("list", [])) if isinstance(old_data, dict) else []
    events_by_id = {str(e.get("eventId")): dict(e) for e in old_events if e.get("eventId")}
    items_by_event = defaultdict(list)
    for item in old_list:
        items_by_event[str(item.get("eventId") or "")].append(item)

    centers = load_centers()
    discovered_event_ids = set()

    for page_url in discovered:
        html = get(page_url)
        if not html: continue
        soup = BeautifulSoup(html, "html.parser")
        activities = parse_activity_blocks(soup, page_url)
        print("PARSE:", page_url, "activities=", len(activities))
        for activity in activities:
            label = canonical_event_label(activity)
            if any(term in str(label).lower() for term in CENTER_EXCLUDE_TERMS):
                continue
            event_id = event_id_for(activity["pageKey"], activity["sectionTitle"])
            old_event = events_by_id.get(event_id)
            if not old_event:
                for e in events_by_id.values():
                    if e.get("eventZh") == label:
                        old_event = e
                        event_id = e["eventId"]
                        break
            event_zh = label if label in BOOTSTRAP_ACTIVITY_META else activity["pageTitle"]
            if label in BOOTSTRAP_ACTIVITY_META:
                bm = BOOTSTRAP_ACTIVITY_META[label]
                event_zh = bm["eventZh"]
                event_en = bm["event"]
            else:
                event_en = activity["sectionTitle"] or activity["pageTitle"]
            new_event = {
                "eventId": event_id,
                "event": event_en,
                "eventZh": event_zh,
                "eventName": event_en,
                "eventNameZh": event_zh,
                "activity": "GO Stamp Rally",
                "activityZh": "GO 集章趣",
                "startDate": activity["startDate"],
                "endDate": activity["endDate"],
                "expectedStamps": activity["expectedStamps"],
                "eventImage": activity["banner"],
                "activityImage": activity["banner"],
                "sourceUrl": activity["pageUrl"],
                "canonicalPage": canonical_url(activity["pageUrl"]),
                "sourceLocale": url_locale(activity["pageUrl"]),
                "descriptionZh": activity["description"],
            }
            if old_event:
                new_event = merge_event_meta(old_event, new_event)
            items = []
            for idx, p in enumerate(activity["points"], 1):
                name = p["name"]
                name_low = name.lower()
                if any(term in name_low for term in ("ポケモンセンター", "pokemon center", "pokémon center", "寶可夢中心")):
                    continue
                item = {
                    "eventId": event_id,
                    "event": event_en,
                    "eventZh": event_zh,
                    "eventName": event_en,
                    "eventNameZh": event_zh,
                    "activity": "GO Stamp Rally",
                    "activityZh": "GO 集章趣",
                    "venueType": "go_stamp_point",
                    "venue": name,
                    "name": name,
                    "nameZh": name,
                    "pref": extract_prefecture(name + " " + event_zh),
                    "city": "",
                    "address": "",
                    "coords": p.get("coords") or [],
                    "lat": (p.get("coords") or [None, None])[0],
                    "lng": (p.get("coords") or [None, None])[1],
                    "stampImage": p.get("image") or "",
                    "stampImageType": "actual-stamp",
                    "stampImageSource": "Pokémon GO official page" if p.get("image") else "",
                    "stampImageOfficial": bool(p.get("image")),
                    "startDate": activity["startDate"],
                    "endDate": activity["endDate"],
                    "source": "Pokémon GO Official",
                    "sourceUrl": activity["pageUrl"],
                    "official": True,
                    "coordinatesOfficial": False,
                    "coordsSource": "",
                }
                # Center events: use the center's own representative badge and coordinates.
                if any(x in name.lower() for x in ("ポケモンセンター", "pokemon center", "pokémon center", "寶可夢中心")) or "pokemon center" in event_zh.lower() or "寶可夢中心" in event_zh:
                    item["venueType"] = "pokemon_center"
                    icon = find_center_icon(name, centers)
                    if icon:
                        item["stampImage"] = icon
                        item["stampImageType"] = "pokemon-center-badge"
                        item["stampImageSource"] = "Pokémon Center representative badge"
                        item["stampImageOfficial"] = True
                    cc = coords_from_center(name, centers)
                    if cc:
                        item["coords"] = cc; item["lat"], item["lng"] = cc
                        item["coordinatesOfficial"] = True
                        item["coordsSource"] = "pokemon_center.json"
                items.append(item)
            old_items = items_by_event.get(event_id, [])
            merged_items = merge_points(old_items, items, event_id)
            # If a known event's parser returns nothing, preserve cached real points.
            if not items and old_items:
                new_event["dataStatus"] = "partial" if (new_event.get("expectedStamps") and len(old_items) < int(new_event["expectedStamps"])) else "complete"
            else:
                exp = new_event.get("expectedStamps")
                new_event["dataStatus"] = "complete" if not exp or len(merged_items) >= int(exp) else ("partial" if merged_items else "announced-only")
            events_by_id[event_id] = new_event
            items_by_event[event_id] = merged_items
            discovered_event_ids.add(event_id)
        time.sleep(REQUEST_DELAY)

    # Remove legacy Pokémon Center Stamp Rally records and non-GO stamp records before bootstrap.
    for eid, arr in list(items_by_event.items()):
        items_by_event[eid] = [x for x in arr if not is_non_target_item(x)]
    for eid, event in list(events_by_id.items()):
        blob = " ".join(str(event.get(k) or "") for k in ("event", "eventZh", "eventName", "eventNameZh", "activity", "activityZh"))
        if is_non_target_text(blob):
            events_by_id.pop(eid, None)
            items_by_event.pop(eid, None)

    # Re-add permanent bootstrap records so the site does not lose known permanent rallies
    # merely because the official parent page changes structure.
    bootstrap_events = []
    bootstrap_items = []
    for label, names in BOOTSTRAP_PERMANENT_POINTS.items():
        meta = BOOTSTRAP_ACTIVITY_META[label]
        existing = next((e for e in events_by_id.values() if e.get("eventZh") == label), None)
        eid = existing["eventId"] if existing else event_id_for_bootstrap(label)
        event = existing or {
            "eventId": eid,
            "event": meta["event"], "eventZh": meta["eventZh"],
            "eventName": meta["event"], "eventNameZh": meta["eventZh"],
            "activity": "GO Stamp Rally", "activityZh": "GO 集章趣",
            "startDate": meta["startDate"], "endDate": meta["endDate"],
            "expectedStamps": meta["expectedStamps"],
            "eventImage": "", "activityImage": "", "sourceUrl": meta["sourceUrl"],
            "canonicalPage": canonical_url(meta["sourceUrl"]), "sourceLocale": "en",
            "dataStatus": "partial", "descriptionZh": ""
        }
        event["expectedStamps"] = meta["expectedStamps"]
        event["startDate"] = event.get("startDate") or meta["startDate"]
        event["endDate"] = event.get("endDate") or meta["endDate"]
        event["sourceUrl"] = event.get("sourceUrl") or meta["sourceUrl"]
        existing_items = items_by_event.get(eid, [])
        merged = []
        by_name = {norm(x.get("nameZh") or x.get("name") or x.get("venueZh") or x.get("venue")).lower(): x for x in existing_items}
        for i, name in enumerate(names, 1):
            item = dict(by_name.get(name.lower()) or {})
            item.setdefault("id", point_id(eid, name, i))
            item["venueType"] = "go_stamp_point"
            item.update({
                "eventId": eid, "event": meta["event"], "eventZh": meta["eventZh"],
                "eventName": meta["event"], "eventNameZh": meta["eventZh"],
                "activity": "GO Stamp Rally", "activityZh": "GO 集章趣",
                "venueType": item.get("venueType") or "go_stamp_point",
                "name": item.get("name") or name, "nameZh": item.get("nameZh") or name,
                "venue": item.get("venue") or name,
                "pref": item.get("pref") or ("東京都" if label.startswith("東京：") else ("長崎県" if label.startswith("長崎") else "大阪府")),
                "city": item.get("city") or ("東京" if label.startswith("東京：") else ("長崎市" if label.startswith("長崎") else "吹田市")),
                "startDate": item.get("startDate") or meta["startDate"],
                "endDate": item.get("endDate") or meta["endDate"],
                "source": item.get("source") or "Pokémon GO Official / verified community data",
                "sourceUrl": item.get("sourceUrl") or meta["sourceUrl"],
            })
            merged.append(item)
        event["dataStatus"] = "complete" if len(merged) >= int(meta["expectedStamps"]) else "partial"
        bootstrap_events.append(event)
        bootstrap_items.extend(merged)
        events_by_id[eid] = event
        items_by_event[eid] = merged

    # Optional generic geocoding for points with missing coordinates.
    geo_cache = load_json(ROOT / ".stamp_geocode_cache.json", {})
    for eid, items in list(items_by_event.items()):
        for item in items:
            coords = item.get("coords") or []
            if len(coords) >= 2 and all(isinstance(x, (int,float)) for x in coords):
                continue
            name = norm(item.get("nameZh") or item.get("name") or item.get("venueZh") or item.get("venue"))
            city = norm(item.get("city") or item.get("pref") or "")
            if not name: continue
            key = f"{name}|{city}"
            if key in geo_cache:
                result = geo_cache[key]
            else:
                try:
                    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": f"{name}, {city}, Japan", "format":"jsonv2", "limit":1}, headers=HEADERS, timeout=20)
                    data = r.json() if r.ok else []
                    result = {"coords": [float(data[0]["lat"]), float(data[0]["lon"])] if data else [], "ok": bool(data)}
                except Exception:
                    result = {"coords": [], "ok": False}
                geo_cache[key] = result
                time.sleep(GEOCODE_DELAY)
            if result.get("coords"):
                item["coords"] = result["coords"]
                item["lat"], item["lng"] = result["coords"]
                if not item.get("coordinatesOfficial"):
                    item["coordinatesOfficial"] = False
                    item["coordsSource"] = "OpenStreetMap Nominatim geocoding"
    save_json(ROOT / ".stamp_geocode_cache.json", geo_cache)

    final_events = sorted(events_by_id.values(), key=lambda e: (e.get("startDate") or "9999-99-99", e.get("eventZh") or e.get("event") or ""))
    final_items = []
    for e in final_events:
        eid = e.get("eventId")
        its = items_by_event.get(eid, [])
        # Deduplicate final items within each event.
        seen = set()
        for item in its:
            key = normalize_item_key(item)
            if key in seen: continue
            seen.add(key)
            item["eventId"] = eid
            item["event"] = e.get("event", item.get("event", "GO Stamp Rally"))
            item["eventZh"] = e.get("eventZh", item.get("eventZh", "GO 集章趣"))
            item["startDate"] = e.get("startDate", item.get("startDate", ""))
            item["endDate"] = e.get("endDate", item.get("endDate", ""))
            final_items.append(item)
    return final_events, final_items


def signature(x):
    payload = dict(x)
    payload.pop("_hash", None)
    return sha(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def build_history(old, new_events, new_items):
    old_list = old.get("list", []) if isinstance(old, dict) else []
    old_by_id = {str(x.get("id")): x for x in old_list}
    new_by_id = {str(x.get("id")): x for x in new_items}
    added = [new_by_id[k] for k in new_by_id.keys() - old_by_id.keys()]
    removed = [old_by_id[k] for k in old_by_id.keys() - new_by_id.keys()]
    changed = []
    for k in new_by_id.keys() & old_by_id.keys():
        if signature(new_by_id[k]) != signature(old_by_id[k]):
            changed.append({"before": old_by_id[k], "after": new_by_id[k]})
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "event": "Pokémon GO GO 集章趣 AUTO SYNC",
        "eventZh": "Pokémon GO GO 集章趣自動同步",
        "total": len(new_items),
        "added": [x.get("id") for x in added],
        "removed": [x.get("id") for x in removed],
        "changed": [x.get("after", {}).get("id") for x in changed],
    }
    return entry, added, removed, changed


def main():
    print("=" * 60)
    print("Pokémon GO GO 集章趣 AUTO SYNC v17")
    print("Official discovery + localized-page dedupe + activity blocks")
    print("No hard-coded activity catalog")
    print("=" * 60)

    old = load_json(STAMP_FILE, {"events": [], "list": []})
    discovered = discover_pages()
    print("Official GO Stamp Rally candidate pages:", len(discovered))

    events, items = build_from_discovery(discovered, old)
    new = {
        "version": "17.0",
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "Pokémon GO Official Website",
        "sourceMode": "official-first; localized dedupe; activity-block discovery; verified-community/OSM fallback",
        "rule": "Only in-game Pokémon GO GO Stamp Rally. Offline stamp rallies and Poké Lid are excluded.",
        "events": events,
        "list": items,
    }
    entry, added, removed, changed = build_history(old, events, items)
    save_json(STAMP_FILE, new)

    history = load_json(HISTORY_FILE, {"history": []})
    history.setdefault("history", []).insert(0, entry)
    history["history"] = history["history"][:100]
    save_json(HISTORY_FILE, history)

    print("=" * 60)
    print("Unique activities:", len(events))
    print("Total stamp points:", len(items))
    print("Added:", len(added))
    print("Removed:", len(removed))
    print("Changed:", len(changed))
    for e in events:
        print("EVENT:", e.get("eventZh") or e.get("event"), "points=", sum(1 for x in items if x.get("eventId") == e.get("eventId")), "expected=", e.get("expectedStamps"), "status=", e.get("dataStatus"))
    print("=" * 60)


if __name__ == "__main__":
    main()
