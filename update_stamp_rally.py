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

ROOT = Path(__file__).resolve().parent
STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
CENTER_FILE = ROOT / "data" / "pokemon_center.json"

TIMEOUT = 35
REQUEST_DELAY = 0.25
GEOCODE_DELAY = 1.10
GEOCODER_EMAIL = ""  # Optional: set to a contact email in CI if desired.
GEOCODER_USER_AGENT = "Pok-Lids-GOStampSync/22.0 (+https://github.com/h23456789/Pok-Lids)"
MAX_DISCOVERED_PAGES = 220
MAX_LINK_DEPTH = 3
MAX_POINTS_PER_EVENT = 100

LOCALE_PRIORITY = {"zh-hant": 0, "zh_hant": 0, "ja": 1, "en": 2}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36 "
        "Pok-Lids-GOStampSync/20.0"
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



# 已由玩家/攻略網站公開並可交叉驗證的「實際 GO 集章趣」座標。
# 這不是活動清單，而是點位座標快取；未來新增點仍會走官方座標／地名地理編碼流程。
# 東京 2026 GO Fest 三區座標來源：Margxt / Reddit 玩家座標整理。
VERIFIED_STAMP_COORDS = {
    # Tokyo / Minato
    "東京鐵塔": [35.6586, 139.7454],
    "SL廣場 C11 292": [35.6671448, 139.7574141],
    "SL広場 C11 292号": [35.6671448, 139.7574141],
    "原芝浦小學校紀念碑": [35.665661, 139.7461202],
    "港區立鞆絵小学校校舎跡": [35.665661, 139.7461202],
    "江戶坂": [35.6669716, 139.7454765],
    "江戸見坂": [35.6669716, 139.7454765],
    "芝公園 Gym Statue": [35.6560133, 139.7490935],
    "芝公園 Gym Statue(▶︎Googleマップ)": [35.6560133, 139.7490935],

    # Tokyo / Koto
    "江東區役所": [35.6730499, 139.8164348],
    "江東区役所": [35.6730499, 139.8164348],
    "東陽21 Goddess Fountain": [35.6748, 139.81523],
    "イースト21 女神の噴水": [35.6748, 139.81523],
    "仙台堀公園 嬰兒噴泉": [35.676180, 139.812740],
    "仙台堀川公園 赤ちゃん噴水池": [35.676180, 139.812740],
    "東京都現代美術館 Like a Snail B": [35.6796307, 139.8074057],
    "東京都現代美術館 かたつむりのようにB": [35.6796307, 139.8074057],

    # Tokyo / Shinagawa
    "天王洲 Isle 第四公園": [35.623578, 139.748265],
    "天王洲アイル第4公園": [35.623578, 139.748265],
    "聖蹟公園": [35.619162, 139.74419],
    "街道松廣場": [35.615484, 139.744176],
    "街道松の広場": [35.615484, 139.744176],
    "鮫洲入江廣場": [35.603301, 139.743942],
    "鮫洲入江広場": [35.603301, 139.743942],
}

OFFICIAL_CENTER_BADGE_FALLBACKS = {
    "ポケモンセンターヨコハマ": "https://shop.pokemon.co.jp/images/logos/logo-pokemoncenter-yokohama.webp",
    "寶可夢中心橫濱": "https://shop.pokemon.co.jp/images/logos/logo-pokemoncenter-yokohama.webp",
    "Pokemon Center Yokohama": "https://shop.pokemon.co.jp/images/logos/logo-pokemoncenter-yokohama.webp",
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
    explicit = any(x in text for x in GO_STAMP_TERMS) or "in-game stamp rally" in text
    if not explicit:
        return False
    rally_signal = any(x in text for x in (
        "collect stamps", "collect up to", "stamp sheet", "stamp card",
        "stamp icon", "digital stamp", "數位圖章", "蒐集圖章", "開始挑戰",
        "完成本次的", "go集章趣", "goスタンプラリー"
    ))
    game_signal = any(x in text for x in STRONG_GAME_TERMS)
    return rally_signal and game_signal


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
    points=[]; seen=set()
    def add_point(name, coords=None, image="", source_url="", address=""):
        name=clean_point(name)
        if not looks_like_point(name): return
        low=name.lower()
        if any(x in low for x in ("pokéstop","pokestop","stamp rally","digital stamp","圖章","集章趣","collect stamps","how do","more details")): return
        key=re.sub(r"[^a-z0-9一-龥ぁ-んァ-ン]+","",low)
        if not key or key in seen: return
        seen.add(key); points.append({"name":name,"coords":coords or [],"sourceUrl":source_url,"image":image,"address":norm(address)})
    for node in container.find_all(["li","dt"]):
        text=norm(node.get_text(" ",strip=True))
        if not text: continue
        maps=extract_map_links(node,"https://pokemongo.com/")
        coords=maps[0][2] if maps and maps[0][2] else []
        source_url=maps[0][1] if maps else ""
        add_point(text,coords,"",source_url, extract_location_context(text))

    # Some official pages render location cards as div/p elements rather than list items.
    for node in container.find_all(["p","div"]):
        text=norm(node.get_text(" ",strip=True))
        if not text or len(text) > 100: continue
        if len(node.find_all(recursive=False)) > 12: continue
        low=text.lower()
        if any(token in low for token in ("stamp rally","collect stamps","開始挑戰","蒐集圖章","please be aware","more details","how do")): continue
        maps=extract_map_links(node,"https://pokemongo.com/")
        if maps:
            coords=maps[0][2] or []
            source_url=maps[0][1]
            add_point(text,coords,"",source_url, extract_location_context(text))
    for a in container.find_all("a",href=True):
        href=urljoin("https://pokemongo.com/",a["href"])
        if not any(x in href.lower() for x in ("google.com/maps","maps.google","maps.app.goo.gl")): continue
        coords=extract_map_coords(href); label=norm(a.get_text(" ",strip=True))
        if not label or label.lower() in {"google maps","map","地圖","view map"}:
            prev=a.find_previous(["li","dt","p","strong","h4","h5"]); label=norm(prev.get_text(" ",strip=True)) if prev else ""
        add_point(label,coords,"",href)
    for script in container.find_all("script"):
        raw=script.string or script.get_text() or ""
        pattern=re.compile(r"[\"'](?:name|title|label)[\"']?\s*[:=]\s*[\"']([^\"']{3,120})[\"'][^{}]{0,500}?(-?\d{1,3}\.\d+)\s*[,/]\s*(-?\d{1,3}\.\d+)",re.I)
        for m in pattern.finditer(raw):
            name,lat,lng=m.group(1),float(m.group(2)),float(m.group(3))
            if -90<=lat<=90 and -180<=lng<=180: add_point(name,[lat,lng])
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
        expected = extract_expected(block_text)
        starts, ends = extract_date_range(block_text)
        start_date = starts or page_start
        end_date = ends or page_end
        points = []
        for node in nodes:
            points.extend(parse_points_from_container(node))
        # If the official page exposes actual stamp images, pair them with point order.
        stamp_images = extract_point_images(soup, page_url)
        for idx, point in enumerate(points):
            if not point.get("image") and idx < len(stamp_images):
                point["image"] = stamp_images[idx]
                point["imageSource"] = "Pokémon GO official page"
        # If a published place has no map coordinates, resolve its name to a Japan coordinate.
        context = f"{block_title} {page_title}"
        points = enrich_points_with_coordinates(points, context)
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


def _looks_like_center_badge(url: str) -> bool:
    u = str(url or "").lower()
    if not u or u.endswith((".svg", ".json")):
        return False
    if any(token in u for token in ("mv/", "/mv", "mainvisual", "hero", "banner", "news", "event", "ogp")):
        return False
    return any(token in u for token in ("logo", "badge", "mark", "symbol", "emblem", "shop-logo", "shop_logo"))

def discover_center_badge_from_official(name, centers):
    # Prefer a badge/logo already stored in pokemon_center.json.
    c = find_center_record(name, centers)
    if c:
        for key in ("pokemonCenterBadge","pokemonCenterIcon","centerBadge","centerIcon","badge","logo"):
            value = c.get(key)
            if value and _looks_like_center_badge(value):
                return value
    # Known official Yokohama logo asset.
    lower = normalize_center_name(name)
    if "yokohama" in lower or "橫濱" in name or "横浜" in name or "ヨコハマ" in name:
        return OFFICIAL_CENTER_BADGE_FALLBACKS["ポケモンセンターヨコハマ"]
    # Discover from the official store page.
    official_url = c.get("official_url") if c else ""
    if official_url:
        html = get(official_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            candidates = []
            for tag in soup.find_all("img"):
                for attr in ("src", "data-src", "data-lazy-src", "srcset"):
                    raw = tag.get(attr)
                    if not raw:
                        continue
                    values = str(raw).split(",") if attr == "srcset" else [raw]
                    for value in values:
                        value = value.strip().split(" ")[0]
                        full = urljoin(official_url, value)
                        if _looks_like_center_badge(full):
                            candidates.append(full)
            for tag in soup.find_all(["meta","link"]):
                raw = tag.get("content") or tag.get("href") or ""
                full = urljoin(official_url, str(raw))
                if _looks_like_center_badge(full):
                    candidates.append(full)
            # Prefer URLs whose filename is explicitly logo/mark/badge.
            for candidate in candidates:
                if any(k in candidate.lower() for k in ("logo", "badge", "mark", "emblem")):
                    return candidate
            if candidates:
                return candidates[0]
    return ""

def find_center_icon(name, centers):
    return discover_center_badge_from_official(name, centers)


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



def extract_location_context(text):
    """Return useful location fragments from activity text for geocoding."""
    text = norm(text)
    # Japanese addresses / postal codes
    postal = re.search(r"〒?\s*\d{3}-\d{4}[^。\n]{0,80}", text)
    if postal:
        return norm(postal.group(0))
    return ""


def geocode_place(query):
    """Geocode a place name in Japan using public Nominatim.

    This is intentionally a fallback only. Official coordinates / map links always win.
    """
    query = norm(query)
    if not query:
        return None
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 3,
        "countrycodes": "jp",
        "accept-language": "ja,en",
    }
    headers = {
        "User-Agent": GEOCODER_USER_AGENT,
    }
    if GEOCODER_EMAIL:
        params["email"] = GEOCODER_EMAIL
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers=headers,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list):
            return None
        for row in rows:
            lat = float(row.get("lat"))
            lng = float(row.get("lon"))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {
                    "coords": [lat, lng],
                    "displayName": norm(row.get("display_name", "")),
                    "osmType": row.get("type", ""),
                }
    except Exception as exc:
        print("GEOCODE ERROR:", query, exc)
    return None


def build_geocode_queries(point_name, context, address=""):
    """Generate conservative Japanese place-name queries from most specific to broad."""
    queries = []
    for value in (
        f"{point_name}, {address}, Japan",
        f"{point_name}, {context}, Japan",
        f"{point_name}, Japan",
    ):
        value = re.sub(r"\s+,", ",", norm(value))
        value = re.sub(r",\s*,", ",", value)
        if value and value not in queries:
            queries.append(value)
    return queries


def enrich_points_with_coordinates(points, context):
    """Fill missing coordinates from published place names; never overwrite official coords."""
    enriched = []
    for point in points:
        p = dict(point)
        if not p.get("coords"):
            address = p.get("address", "")
            found = None
            used_query = ""
            for query in build_geocode_queries(p.get("name", ""), context, address):
                found = geocode_place(query)
                time.sleep(GEOCODE_DELAY)
                if found:
                    used_query = query
                    break
            if found:
                p["coords"] = found["coords"]
                p["coordsSource"] = "Nominatim geocoding from published place name"
                p["coordinatesOfficial"] = False
                p["coordinatesConfidence"] = "medium"
                p["geocodeQuery"] = used_query
                p["geocodeDisplayName"] = found["displayName"]
                print("GEOCODED:", p.get("name"), "->", p["coords"])
            else:
                p["coordsSource"] = p.get("coordsSource", "")
                p["coordinatesOfficial"] = bool(p.get("coords"))
        enriched.append(p)
    return enriched


def merge_location_data(point, node):
    """Keep human-readable address from map-link/list context without inventing it."""
    merged = dict(point)
    for key in ("address", "location", "venue"):
        if not merged.get(key) and node.get(key):
            merged[key] = node[key]
    return merged



def verified_coords_for_name(name):
    """Return a known verified community coordinate for a published stamp point name."""
    target = norm(name).lower()
    if not target:
        return None
    # Exact match first.
    for key, coords in VERIFIED_STAMP_COORDS.items():
        if norm(key).lower() == target:
            return list(coords)
    # Conservative fuzzy match, useful for Japanese/Chinese punctuation variations.
    compact = re.sub(r"[\s・･,，.。()（）]+", "", target)
    for key, coords in VERIFIED_STAMP_COORDS.items():
        k = re.sub(r"[\s・･,，.。()（）]+", "", norm(key).lower())
        if compact == k or (len(k) >= 5 and (k in compact or compact in k)):
            return list(coords)
    return None


def enrich_known_points(points, context=""):
    """Fill missing coordinates for existing points: verified cache, then geocoding by place name."""
    enriched=[]
    for p in points:
        q=dict(p)
        coords=q.get("coords") or []
        valid=False
        if len(coords)>=2:
            try:
                lat=float(coords[0]); lng=float(coords[1])
                valid=(-90<=lat<=90 and -180<=lng<=180)
            except Exception:
                valid=False
        if not valid:
            known=verified_coords_for_name(q.get("name", ""))
            if known:
                q["coords"]=known
                q["coordinatesOfficial"]=False
                q["coordinatesConfidence"]="high"
                q["coordsSource"]="Verified community coordinate reference"
                q["coordinatesSourceUrl"]="https://www.margxt.fr/evenement-chasse-aux-tampons-a-minato-tokyo-japon-dans-pokemon-go/"
                valid=True
        if not valid:
            name=norm(q.get("name"))
            address=norm(q.get("address"))
            queries=build_geocode_queries(name, context, address)
            for query in queries:
                found=geocode_place(query)
                if found:
                    q["coords"]=found["coords"]
                    q["lat"],q["lng"]=found["coords"]
                    q["coordinatesOfficial"]=False
                    q["coordinatesConfidence"]="medium"
                    q["coordsSource"]="Nominatim geocoding from published place name"
                    q["geocodeQuery"]=query
                    q["geocodeDisplayName"]=found.get("displayName","")
                    valid=True
                    break
                time.sleep(GEOCODE_DELAY)
        if valid and len(q.get("coords") or [])>=2:
            q["lat"],q["lng"]=q["coords"][:2]
        enriched.append(q)
    return enriched


def event_status(start_date, end_date):
    """Return a snapshot status for JSON/history; frontend recalculates this live."""
    try:
        today = datetime.now(timezone.utc).date()
    except Exception:
        today = datetime.utcnow().date()
    start = None
    end = None
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    if start and today < start:
        return "upcoming"
    if end and today > end:
        return "ended"
    return "active"


def event_id_for(page_key, section):
    return "GO-STAMP-" + sha(page_key[0], page_key[1], section)


def point_id(event_id, name, index):
    return f"{event_id}-P{index:03d}-{sha(name, index)[:8]}"


def canonical_event_label(activity):
    title=norm(activity.get("sectionTitle") or activity.get("pageTitle"))
    if title.lower() in {"go stamp rally","go集章趣","goスタンプラリー"}:
        title=norm(activity.get("pageTitle") or title)
    return title or "GO 集章趣"


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
    result=[]
    old_by_name=defaultdict(list)
    for old in old_items:
        name=norm(old.get("nameZh") or old.get("name") or old.get("venueZh") or old.get("venue")).lower()
        old_by_name[name].append(old)
    seen=set()
    for idx,new in enumerate(new_items,1):
        name=norm(new.get("nameZh") or new.get("name") or new.get("venueZh") or new.get("venue"))
        old_match=old_by_name.get(name.lower(),[None])[0]
        item=dict(old_match or {})
        item.update(new)
        if old_match and not new.get("stampImage") and old_match.get("stampImage") and item.get("venueType") != "pokemon_center":
            item["stampImage"]=old_match["stampImage"]
            item["stampImageType"]=old_match.get("stampImageType","actual-stamp")
            item["stampImageSource"]=old_match.get("stampImageSource","")
            item["stampImageOfficial"]=old_match.get("stampImageOfficial",False)
        if old_match and not new.get("centerBadgeImage") and old_match.get("centerBadgeImage"):
            item["centerBadgeImage"]=old_match["centerBadgeImage"]
            item["centerBadgeType"]=old_match.get("centerBadgeType","pokemon-center-badge")
            item["centerBadgeSource"]=old_match.get("centerBadgeSource","")
            item["centerBadgeOfficial"]=old_match.get("centerBadgeOfficial",False)
        if old_match and not new.get("coords") and old_match.get("coords"):
            item["coords"]=old_match["coords"]
            item["lat"],item["lng"]=old_match["coords"]
            item["coordinatesOfficial"]=old_match.get("coordinatesOfficial",False)
            item["coordsSource"]=old_match.get("coordsSource","")
        item["eventId"]=event_id
        item["id"]=old_match.get("id") if old_match else point_id(event_id,name,idx)
        k=normalize_item_key(item)
        if k not in seen:
            seen.add(k); result.append(item)
    # Preserve only previously verified cache points if the official page temporarily
    # exposes no point list. Placeholder/empty points are intentionally discarded.
    if not new_items and old_items:
        verified=[]
        for x in old_items:
            coords=x.get("coords") or []
            has_coords=len(coords)>=2
            has_image=bool(x.get("stampImage"))
            if has_coords or has_image:
                verified.append(dict(x,eventId=event_id))
        return verified
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
    old_events=list(old_data.get("events",[])) if isinstance(old_data,dict) else []
    old_list=list(old_data.get("list",[])) if isinstance(old_data,dict) else []
    old_by_event={str(e.get("eventId")):dict(e) for e in old_events if e.get("eventId")}
    old_items_by_event=defaultdict(list)
    for item in old_list:
        if item.get("eventId"): old_items_by_event[str(item["eventId"])].append(dict(item))
    centers=load_centers(); events_by_id={}; items_by_event=defaultdict(list)
    for page_url in discovered:
        html=get(page_url)
        if not html: continue
        soup=BeautifulSoup(html,"html.parser")
        activities=parse_activity_blocks(soup,page_url)
        print("PARSE:",page_url,"activities=",len(activities))
        for activity in activities:
            section_key=norm(activity.get("sectionTitle") or activity.get("pageTitle") or "GO Stamp Rally")
            event_id=event_id_for(activity["pageKey"],section_key)
            old_event=old_by_event.get(event_id)
            event_zh=canonical_event_label(activity)
            event_en=activity.get("sectionTitle") or activity.get("pageTitle") or "GO Stamp Rally"
            event={"eventId":event_id,"event":event_en,"eventZh":event_zh,"eventName":event_en,"eventNameZh":event_zh,
                   "activity":"GO Stamp Rally","activityZh":"GO 集章趣","startDate":activity.get("startDate") or "","endDate":activity.get("endDate") or "",
                   "expectedStamps":activity.get("expectedStamps"),"eventImage":activity.get("banner") or "","activityImage":activity.get("banner") or "",
                   "sourceUrl":activity.get("pageUrl") or page_url,"canonicalPage":canonical_url(activity.get("pageUrl") or page_url),
                   "sourceLocale":url_locale(activity.get("pageUrl") or page_url),"descriptionZh":activity.get("description") or "","status":event_status(activity.get("startDate") or "", activity.get("endDate") or "")}
            if old_event:
                event=merge_event_meta(old_event,event)
                if activity.get("banner"): event["eventImage"]=event["activityImage"]=activity["banner"]
                if activity.get("pageUrl"): event["sourceUrl"]=activity["pageUrl"]; event["sourceLocale"]=url_locale(activity["pageUrl"])
            event["status"]=event_status(event.get("startDate") or "", event.get("endDate") or "")
            new_items=[]
            for idx,point in enumerate(activity.get("points",[]),1):
                name=norm(point.get("name"));
                if not name: continue
                coords=point.get("coords") or []
                item={"id":point_id(event_id,name,idx),"eventId":event_id,"event":event_en,"eventZh":event_zh,"eventName":event_en,"eventNameZh":event_zh,
                      "activity":"GO Stamp Rally","activityZh":"GO 集章趣","venueType":"go_stamp_point","venue":name,"name":name,"nameZh":name,
                      "pref":extract_prefecture(name+" "+event_zh),"city":"","address":point.get("address") or "","coords":coords,
                      "lat":coords[0] if len(coords)>=2 else None,"lng":coords[1] if len(coords)>=2 else None,
                      "stampImage":point.get("image") or "","stampImageType":"actual-stamp" if point.get("image") else "",
                      "stampImageSource":point.get("imageSource") or ("Pokémon GO official page" if point.get("image") else ""),"stampImageOfficial":bool(point.get("image")),
                      "startDate":event["startDate"],"endDate":event["endDate"],"source":"Pokémon GO Official","sourceUrl":point.get("sourceUrl") or event["sourceUrl"],
                      "official":True,"coordinatesOfficial":bool(point.get("coordinatesOfficial") or len(coords)>=2),
                      "coordinatesConfidence":point.get("coordinatesConfidence", "high" if len(coords)>=2 and point.get("coordinatesOfficial") else ("medium" if len(coords)>=2 else "low")),
                      "coordsSource":point.get("coordsSource") or ("official map link" if len(coords)>=2 else "")
                  }
                low=name.lower()
                if any(x in low for x in ("ポケモンセンター","pokemon center","pokémon center","寶可夢中心")):
                    item["venueType"]="pokemon_center"; icon=find_center_icon(name,centers)
                    if icon:
                        item["centerBadgeImage"]=icon
                        item["centerBadgeType"]="pokemon-center-badge"
                        item["centerBadgeSource"]="Pokémon Center official store page / pokemon_center.json"
                        item["centerBadgeOfficial"]=True
                        # Legacy compatibility: keep stampImage empty for Center because this is a site display badge, not a GO stamp.
                    cc=coords_from_center(name,centers)
                    if cc: item["coords"]=cc; item["lat"],item["lng"]=cc; item["coordinatesOfficial"]=True; item["coordsSource"]="pokemon_center.json"
                new_items.append(item)
            merged=merge_points(old_items_by_event.get(event_id,[]),new_items,event_id)
            events_by_id[event_id]=event; items_by_event[event_id]=merged
            exp=event.get("expectedStamps"); event["dataStatus"]="complete" if exp and len(merged)>=int(exp) else ("partial" if merged else "announced-only")
    # Preserve previously known activities when an official page is temporarily unavailable.
    # Their status is recomputed from dates; this prevents a transient 429/5xx from deleting history.
    for eid, old_event in old_by_event.items():
        if eid not in events_by_id:
            preserved = dict(old_event)
            preserved["status"] = event_status(preserved.get("startDate") or "", preserved.get("endDate") or "")
            events_by_id[eid] = preserved
            items_by_event[eid] = [dict(x) for x in old_items_by_event.get(eid, [])]

    final_events=sorted(events_by_id.values(),key=lambda e:(e.get("startDate") or "9999-99-99",e.get("eventZh") or e.get("event") or ""))
    final_items=[]
    for event in final_events:
        eid=event["eventId"]; seen=set()
        raw_items=items_by_event.get(eid,[])
        context=f"{event.get('eventZh') or event.get('event') or ''} {event.get('canonicalPage') or event.get('sourceUrl') or ''}"
        raw_items=enrich_known_points(raw_items, context)
        for item in raw_items:
            key=normalize_item_key(item)
            if key in seen: continue
            seen.add(key); item["eventId"]=eid; item["event"]=event.get("event",item.get("event","GO Stamp Rally")); item["eventZh"]=event.get("eventZh",item.get("eventZh","GO 集章趣")); item["startDate"]=event.get("startDate",item.get("startDate","")); item["endDate"]=event.get("endDate",item.get("endDate","")); final_items.append(item)
        exp=event.get("expectedStamps")
        event["pointCount"]=sum(1 for x in final_items if x.get("eventId")==eid)
        event["dataStatus"]="complete" if exp and event["pointCount"]>=int(exp) else ("partial" if event["pointCount"] else "announced-only")
    return final_events,final_items

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
    print("Pokémon GO GO 集章趣 AUTO SYNC v22")
    print("Official discovery + locale dedupe + activity blocks + no fabricated points")
    print("No hard-coded activity catalog")
    print("=" * 60)

    old = load_json(STAMP_FILE, {"events": [], "list": []})
    discovered = discover_pages()
    print("Official GO Stamp Rally candidate pages (after locale dedupe):", len(discovered))

    events, items = build_from_discovery(discovered, old)
    new = {
        "version": "22.0",
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "Pokémon GO Official Website",
        "sourceMode": "official-first; localized dedupe; activity-block discovery; official map coords first; place-name geocoding fallback; no fabricated points",
        "rule": "Only in-game Pokémon GO GO Stamp Rally. Offline stamp rallies, ordinary PokéStops, and Poké Lid are excluded. Published place names may be geocoded when official coordinates are not embedded.",
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
