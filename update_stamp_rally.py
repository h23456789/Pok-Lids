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

ROOT = Path(__file__).resolve().parent
STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
OVERRIDE_FILE = ROOT / "svgstamp_manual_overrides.json"

TIMEOUT = 30
REQUEST_DELAY = 0.35
MAX_DISCOVERY_PAGES = 80
MAX_SITEMAP_URLS = 4000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36 "
        "PokemonJapanCollectionUpdater/4.0"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

OFFICIAL_DOMAINS = {
    "pokemon.co.jp",
    "www.pokemon.co.jp",
    "shop.pokemon.co.jp",
    "pokemongo.com",
    "www.pokemongo.com",
}

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
    "デジタルスタンプラリー",
    "STAMP RALLY",
    "Stamp Rally",
    "stamp rally",
]


INSTRUCTIONAL_STAMP_PATTERNS = [
    r"我該怎麼進行.*(?:GO)?\s*集章趣",
    r"我怎麼(?:進行|參加|玩).*集章趣",
    r"GO\s*集章趣.*(?:玩法|教學|說明|怎麼玩)",
    r"how to (?:participate|play|do).*stamp rally",
    r"how (?:do|to).*stamp rally",
    r"stamp rally.*(?:how to|guide|how it works|instructions)",
    r"(?:ご利用方法|遊び方|参加方法|楽しみ方).*スタンプラリー",
    r"スタンプラリー.*(?:ご利用方法|遊び方|参加方法|楽しみ方)",
    r"(?:faq|frequently asked questions).*stamp rally",
]


def is_instructional_stamp_text(value):
    text = normalize_text(value).lower()
    if not text:
        return False
    return any(re.search(pattern, text, re.I) for pattern in INSTRUCTIONAL_STAMP_PATTERNS)


def has_strong_stamp_event_signal(soup, page_text, url):
    """判斷頁面是否真的在介紹一個 GO 集章趣活動，而不是單純提到集章趣。"""
    candidates = []
    for tag in soup.find_all(["h1", "h2"]):
        text = normalize_text(tag.get_text(" ", strip=True))
        if text:
            candidates.append(text)

    for attrs in ({"property": "og:title"}, {"name": "twitter:title"}):
        meta = soup.find("meta", attrs=attrs)
        if meta:
            text = normalize_text(meta.get("content", ""))
            if text:
                candidates.append(text)

    title_text = normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    if title_text:
        candidates.append(title_text)

    # 明確是教學/FAQ 頁，直接排除。
    if any(is_instructional_stamp_text(x) for x in candidates):
        return False

    # URL 本身若明顯是教學說明頁，也不建立活動。
    path = urlparse(url).path.lower()
    if any(token in path for token in ("how-to", "howto", "guide", "faq", "instructions")):
        # 仍允許 URL 看起來是活動頁且標題明確是實際活動名稱。
        if not any("stamp rally" in x.lower() or "スタンプラリー" in x for x in candidates):
            return False

    # 官方首頁／新聞列表／活動索引本身不是單一活動，不能因為
    # 頁面內含教學或活動摘要就被當成一個活動。
    path_clean = path.rstrip("/")
    listing_paths = {"/news", "/ja/news", "/event", "/events", "/info", "/ja/event", "/ja/events", "/ja/info"}
    if path_clean in listing_paths:
        return False

    # 至少要有明確活動性訊號。優先看標題，其次看常見活動詞。
    title_has_stamp = any(
        ("スタンプラリー" in x) or ("stamp rally" in x.lower())
        for x in candidates
    )
    activity_words = (
        "開催", "開催期間", "イベント", "event period", "期間",
        "city safari", "go wild area", "go fest", "community day",
        "pokemon center", "ポケモンセンター", "pokemon go", "pokémon go"
    )
    body_has_activity = any(word.lower() in page_text.lower() for word in activity_words)

    return title_has_stamp or body_has_activity and any(
        ("スタンプラリー" in page_text) or ("stamp rally" in page_text.lower())
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


def normalize_text(value):
    if value is None:
        return ""
    value = str(value).replace("\u3000", " ")
    return re.sub(r"\s+", " ", value).strip()


def is_official_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        return (parsed.hostname or "").lower() in OFFICIAL_DOMAINS
    except Exception:
        return False


def get_html(url):
    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
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
        encoding="utf-8",
    )


def make_hash(*parts):
    raw = "|".join(normalize_text(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def parse_date(value):
    if not value:
        return ""

    match = re.search(
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
        value,
    )
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    match = re.search(
        r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})",
        value,
    )
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    return ""


def extract_dates(text):
    values = []

    for pattern in (
        r"20\d{2}年\d{1,2}月\d{1,2}日",
        r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}",
    ):
        for raw in re.findall(pattern, text or ""):
            date = parse_date(raw)
            if date and date not in values:
                values.append(date)

    return sorted(values)


def extract_event_name(soup, page_text):
    candidates = []

    for tag in soup.find_all("h1"):
        text = normalize_text(tag.get_text(" ", strip=True))
        if text:
            candidates.append(text)

    for attrs in (
        {"property": "og:title"},
        {"name": "twitter:title"},
    ):
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
        if "スタンプラリー" in text or "Stamp Rally" in text:
            return text

    match = re.search(
        r".{0,80}スタンプラリー.{0,120}",
        page_text or "",
    )
    if match:
        return normalize_text(match.group(0))

    return candidates[0] if candidates else "期間限定 Stamp Rally"


def extract_image(soup, base_url):
    for attrs in (
        {"property": "og:image"},
        {"name": "twitter:image"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta:
            value = normalize_text(meta.get("content", ""))
            if value:
                return urljoin(base_url, value)

    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
        )
        if not src:
            continue
        absolute = urljoin(base_url, src)
        lower = absolute.lower()
        if any(token in lower for token in ("stamp", "rally", "スタンプ")):
            return absolute

    return ""


def extract_reward(page_text):
    for keyword in (
        "プレゼント内容",
        "プレゼント条件",
        "認定証",
        "コンプリート",
        "景品",
        "賞品",
    ):
        pos = page_text.find(keyword)
        if pos >= 0:
            return normalize_text(page_text[pos:pos + 500])
    return ""


def extract_activity(page_text):
    if "GOスタンプラリー" in page_text:
        return "Pokémon GO GOスタンプラリー"
    if "デジタルスタンプラリー" in page_text:
        return "デジタルスタンプラリー"
    return "Stamp Rally"


def extract_prefecture(text):
    text = normalize_text(text)
    for alias, canonical in PREF_ALIASES:
        if alias in text:
            return canonical
    return ""


def get_event_id(event, source_url, old_items):
    for item in old_items:
        if normalize_text(item.get("event")) != normalize_text(event):
            continue
        old_url = normalize_text(item.get("sourceUrl", ""))
        if old_url.rstrip("/") == source_url.rstrip("/"):
            return item.get("eventId") or item.get("id") or ""

    return "STAMP-AUTO-" + make_hash(event, source_url)


def normalize_identity(value):
    value = normalize_text(value).lower()
    value = re.sub(r"[\s\u3000\-‐‑–—_・･.,，。:：/\\()（）「」『』【】]", "", value)
    return value


def get_item_id(event_id, venue):
    """
    產生可重現的 Stamp ID。
    同一個 event + venue 永遠得到相同 ID，避免每次 Actions 更新後
    localStorage 的已獲得狀態因 ID 改變而看起來歸零。
    """
    raw_event = normalize_identity(event_id)
    raw_venue = normalize_identity(venue)
    return "STAMP-POINT-" + make_hash(raw_event, raw_venue)


def get_existing_item_id(event_id, venue, old_items, source_url=""):
    event_key = normalize_identity(event_id)
    venue_key = normalize_identity(venue)
    source_key = normalize_text(source_url).rstrip("/").lower()

    # ① 完全相同 eventId + venue：保留舊 ID。
    for item in old_items:
        if (
            normalize_identity(item.get("eventId")) == event_key
            and normalize_identity(item.get("venue") or item.get("name"))
            == venue_key
        ):
            return item.get("id", "")

    # ② event 名稱曾被官方改名，但官方來源 URL 沒變：
    #    仍視為同一個集章點，繼續沿用舊 ID。
    if source_key and venue_key:
        for item in old_items:
            old_source = normalize_text(item.get("sourceUrl", "")).rstrip("/").lower()
            old_venue = normalize_identity(item.get("venue") or item.get("name"))
            if old_source == source_key and old_venue == venue_key:
                return item.get("id", "")

    return ""


def discover_sitemaps():
    sitemaps = set()

    for root in (
        "https://www.pokemon.co.jp/robots.txt",
        "https://shop.pokemon.co.jp/robots.txt",
    ):
        text = get_html(root)
        for match in re.findall(
            r"(?im)^\s*Sitemap:\s*(\S+)\s*$",
            text,
        ):
            if is_official_url(match):
                sitemaps.add(match)

    # Pokémon 官方 robots.txt 明確提供此 sitemap。
    sitemaps.add(
        "https://www.pokemon.co.jp/sitemap.xml"
    )

    # Pokémon Center 若提供 XML sitemap，以下常見入口可直接嘗試；
    # 找不到就略過，不會影響既有資料。
    sitemaps.update({
        "https://shop.pokemon.co.jp/sitemap.xml",
        "https://shop.pokemon.co.jp/sitemap_index.xml",
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
    tag = root.tag.lower()

    if tag.endswith("sitemapindex"):
        for child in root.iter():
            if not child.tag.lower().endswith("loc") or not child.text:
                continue
            child_url = child.text.strip()
            if not is_official_url(child_url):
                continue
            found.update(
                parse_sitemap(
                    child_url,
                    visited,
                    url_limit=url_limit,
                )
            )
            if len(found) >= url_limit:
                break

    elif tag.endswith("urlset"):
        for child in root.iter():
            if not child.tag.lower().endswith("loc") or not child.text:
                continue
            child_url = child.text.strip()
            if is_official_url(child_url):
                found.add(child_url)
                if len(found) >= url_limit:
                    break

    return found


def discover_urls(old_items):
    candidates = set()

    # 既有資料的官方來源也作為更新入口。
    # 這不是寫死活動網址；只會更新已存在的官方來源。
    for item in old_items:
        source_url = normalize_text(item.get("sourceUrl", ""))
        if is_official_url(source_url):
            candidates.add(source_url)

    # HTML 官方入口。
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

        page_text = normalize_text(
            soup.get_text(" ", strip=True)
        )

        # 這個頁面本身若已經是 Stamp Rally 頁，就保留。
        if any(
            keyword.lower() in page_text.lower()
            for keyword in STAMP_KEYWORDS
        ):
            candidates.add(url)

        for link in soup.find_all("a", href=True):
            absolute = urljoin(url, link["href"])
            absolute = absolute.split("#", 1)[0]

            if not is_official_url(absolute):
                continue

            text = normalize_text(
                link.get_text(" ", strip=True)
            )
            combined = f"{text} {absolute}"

            if any(
                keyword.lower() in combined.lower()
                for keyword in STAMP_KEYWORDS
            ):
                candidates.add(absolute)

            path = urlparse(absolute).path.lower()
            if any(
                token in path
                for token in (
                    "/info/",
                    "/event/",
                    "/events/",
                    "/campaign/",
                    "/common/events/",
                )
            ):
                if absolute not in visited and absolute not in queue:
                    queue.append(absolute)

        time.sleep(REQUEST_DELAY)

    # XML sitemap 作為第二層發現機制。
    for sitemap in discover_sitemaps():
        urls = parse_sitemap(sitemap)
        for url in urls:
            lower = url.lower()
            if any(
                token in lower
                for token in (
                    "event",
                    "events",
                    "campaign",
                    "info",
                    "stamp",
                    "rally",
                )
            ):
                candidates.add(url)

    return sorted(candidates)


def extract_center_links(soup, base_url):
    results = []
    seen = set()

    for link in soup.find_all("a", href=True):
        name = normalize_text(
            link.get_text(" ", strip=True)
        )
        if not name:
            continue

        if "ポケモンセンター" not in name:
            continue

        if any(
            bad in name
            for bad in (
                "サテライト",
                "出張所",
                "ポケモンカフェ",
            )
        ):
            continue

        if name in seen:
            continue

        results.append({
            "name": name,
            "url": urljoin(base_url, link["href"]),
        })
        seen.add(name)

    if (
        "Pokémon GO Lab." in soup.get_text(" ", strip=True)
        or "Pokémon GO Lab" in soup.get_text(" ", strip=True)
    ):
        if "Pokémon GO Lab." not in seen:
            results.append({
                "name": "Pokémon GO Lab.",
                "url": base_url,
            })

    return results


def enrich_location(item, venue_url):
    html = get_html(venue_url)
    if not html:
        return item

    soup = BeautifulSoup(html, "html.parser")
    text = normalize_text(
        soup.get_text(" ", strip=True)
    )

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

    known = CENTER_HINTS.get(
        item.get("venue") or item.get("name", "")
    )

    if known:
        known_pref, known_city = known
        if not item.get("pref"):
            item["pref"] = known_pref
        if not item.get("city"):
            item["city"] = known_city

    item["venueSourceUrl"] = venue_url

    return item


def parse_stamp_page(url, old_items):
    html = get_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_text(
        soup.get_text(" ", strip=True)
    )

    if not any(
        keyword.lower() in page_text.lower()
        for keyword in STAMP_KEYWORDS
    ):
        return []

    # 只建立真正的 GO 集章趣活動；教學／FAQ 等說明頁不進 JSON。
    if not has_strong_stamp_event_signal(soup, page_text, url):
        print("  SKIP: instructional/non-event Stamp Rally page")
        return []

    event = extract_event_name(
        soup,
        page_text
    )

    # 再做一次活動名稱層級的保險判斷。
    if is_instructional_stamp_text(event):
        print("  SKIP: instructional Stamp Rally title ->", event)
        return []

    event_id = get_event_id(
        event,
        url,
        old_items
    )

    dates = extract_dates(page_text)
    start_date = dates[0] if dates else ""
    end_date = dates[1] if len(dates) >= 2 else ""

    image_url = extract_image(
        soup,
        url
    )

    reward = extract_reward(
        page_text
    )

    activity = extract_activity(
        page_text
    )

    centers = extract_center_links(
        soup,
        url
    )

    items = []

    # 只將真正出現在活動頁的 Pokémon Center 當成活動地點。
    # 不把 Pokémon Store / Cafe / Satellite 混進來。
    if centers:

        seen = set()

        for center in centers:
            venue = center["name"]

            if venue in seen:
                continue

            seen.add(venue)

            known = CENTER_HINTS.get(
                venue,
                ("", "")
            )

            venue_type = (
                "pokemon_go_lab"
                if "GO Lab" in venue
                else "pokemon_center"
            )

            existing_id = get_existing_item_id(
                event_id,
                venue,
                old_items,
                url
            )

            item = {
                "id": existing_id or get_item_id(event_id, venue),
                "eventId": event_id,
                "event": event,
                "eventName": event,
                "activity": activity,
                "venueType": venue_type,
                "venue": venue,
                "name": venue,
                "pref": known[0],
                "city": known[1],
                "address": "",
                "coords": [],
                "startDate": start_date,
                "endDate": end_date,
                "stampImage": image_url,
                "reward": reward,
                "source": (
                    "Pokémon Center Official Website"
                    if "shop.pokemon.co.jp" in url
                    else "Pokémon Official Website"
                ),
                "sourceUrl": url,
                "venueSourceUrl": center.get("url", ""),
                "official": True,
            }

            venue_url = center.get("url", "")
            if is_official_url(venue_url):
                item = enrich_location(
                    item,
                    venue_url
                )
                time.sleep(REQUEST_DELAY)

            items.append(item)

    else:
        # 一般 Stamp Rally 如果沒有逐點列出地點，
        # 仍然保留一筆活動資料；前端會以活動 → 收集點顯示。
        venue = ""
        venue_type = "event"

        if "Pokémon GO Lab" in page_text:
            venue = "Pokémon GO Lab."
            venue_type = "pokemon_go_lab"
        elif "ポケモンセンター" in page_text:
            venue = "全国のポケモンセンター"
            venue_type = "pokemon_center"

        existing_id = get_existing_item_id(
            event_id,
            venue or event,
            old_items,
            url
        )

        items.append({
            "id": existing_id or get_item_id(event_id, venue or event),
            "eventId": event_id,
            "event": event,
            "eventName": event,
            "activity": activity,
            "venueType": venue_type,
            "venue": venue,
            "name": venue or event,
            "pref": extract_prefecture(page_text),
            "city": "",
            "address": "",
            "coords": [],
            "startDate": start_date,
            "endDate": end_date,
            "stampImage": image_url,
            "reward": reward,
            "source": (
                "Pokémon Center Official Website"
                if "shop.pokemon.co.jp" in url
                else "Pokémon Official Website"
            ),
            "sourceUrl": url,
            "official": True,
        })

    return items


def is_invalid_existing_stamp_item(item):
    """移除之前版本誤收進 JSON 的教學／FAQ／索引項目。"""
    values = [
        item.get("event", ""),
        item.get("eventName", ""),
        item.get("name", ""),
        item.get("venue", ""),
    ]
    return any(is_instructional_stamp_text(value) for value in values if value)


def merge_items(old_items, fresh_items):
    merged = {
        item.get("id"): item
        for item in old_items
        if item.get("id") and not is_invalid_existing_stamp_item(item)
    }

    # 若某活動已有新的「有縣市地點」資料，
    # 刪掉舊的「全國一筆」殘留記錄。
    concrete_event_ids = {
        item.get("eventId")
        for item in fresh_items
        if item.get("eventId") and item.get("pref")
    }

    for item_id, item in list(merged.items()):
        if (
            item.get("eventId") in concrete_event_ids
            and not item.get("pref")
        ):
            del merged[item_id]

    for item in fresh_items:
        if item.get("id"):
            merged[item["id"]] = item

    return list(merged.values())


def compare_items(old_items, new_items):
    old_map = {
        item.get("id"): item
        for item in old_items
        if item.get("id")
    }

    new_map = {
        item.get("id"): item
        for item in new_items
        if item.get("id")
    }

    added = [
        item_id
        for item_id in new_map
        if item_id not in old_map
    ]

    changed = [
        item_id
        for item_id in new_map
        if item_id in old_map and old_map[item_id] != new_map[item_id]
    ]

    # 不因一次爬蟲失敗就刪除既有資料。
    removed = []

    return added, removed, changed



def build_events_metadata(old_events, merged):
    old_map = {}
    for event in old_events or []:
        key = normalize_text(event.get("eventId") or event.get("id") or event.get("event"))
        if key:
            old_map[key] = dict(event)

    grouped = {}
    for item in merged:
        event_id = normalize_text(
            item.get("eventId") or item.get("event") or item.get("eventName")
        )
        if not event_id:
            continue
        event = grouped.setdefault(event_id, dict(old_map.get(event_id, {})))
        event["eventId"] = event_id
        event["event"] = item.get("event") or event.get("event") or item.get("eventName") or "GO 集章趣"
        event["eventName"] = item.get("eventName") or event.get("eventName") or event["event"]
        for field in (
            "eventZh", "eventNameZh", "activity", "activityZh",
            "descriptionZh", "activityImage", "eventImage",
            "reward", "rewardZh", "source", "sourceUrl"
        ):
            if item.get(field):
                event[field] = item[field]
        if item.get("startDate") and (not event.get("startDate") or item["startDate"] < event["startDate"]):
            event["startDate"] = item["startDate"]
        if item.get("endDate") and (not event.get("endDate") or item["endDate"] > event["endDate"]):
            event["endDate"] = item["endDate"]

        points = [
            x for x in merged
            if normalize_text(x.get("eventId") or x.get("event") or x.get("eventName")) == event_id
        ]
        points = [
            x for x in points
            if normalize_text(x.get("venue") or x.get("name"))
            and normalize_text(x.get("venue") or x.get("name")) != normalize_text(event.get("event"))
        ]
        event["pointCount"] = len(points)
        if not event.get("expectedStamps") and points:
            event["expectedStamps"] = len(points)

    return sorted(
        grouped.values(),
        key=lambda x: ((x.get("startDate") or "9999"), (x.get("eventZh") or x.get("event") or ""))
    )


def history_detail(item):
    return {
        "id": item.get("id", ""),
        "event": item.get("event", ""),
        "name": item.get("name", ""),
        "venue": item.get("venue", ""),
        "pref": item.get("pref", ""),
        "city": item.get("city", ""),
        "startDate": item.get("startDate", ""),
        "endDate": item.get("endDate", ""),
        "sourceUrl": item.get("sourceUrl", ""),
    }


def main():
    print("========================================")
    print("Pokémon Stamp Rally AUTO UPDATER")
    print("Official-source discovery mode")
    print("========================================")

    old_data = load_json(
        STAMP_FILE,
        {
            "list": []
        }
    )

    old_items = old_data.get(
        "list",
        []
    )
    old_events = old_data.get("events", []) if isinstance(old_data, dict) else []

    manual_overrides = load_manual_overrides()
    old_items = apply_manual_overrides(
        old_items,
        manual_overrides
    )

    print(
        "Existing records:",
        len(old_items)
    )
    print(
        "Manual overrides:",
        len(manual_overrides)
    )

    urls = discover_urls(
        old_items
    )

    print(
        "Discovered official candidate URLs:",
        len(urls)
    )

    fresh_items = []

    for url in urls:
        print(
            "CHECK:",
            url
        )

        try:
            items = parse_stamp_page(
                url,
                old_items
            )

            if items:
                print(
                    "  FOUND:",
                    len(items),
                    "records"
                )
                fresh_items.extend(items)

        except Exception as error:
            print(
                "  PARSE ERROR:",
                error
            )

        time.sleep(
            REQUEST_DELAY
        )

    # 去重
    unique = {}
    for item in fresh_items:
        if item.get("id"):
            unique[item["id"]] = item

    fresh_items = list(
        unique.values()
    )

    fresh_items = apply_manual_overrides(
        fresh_items,
        manual_overrides
    )

    print(
        "Fresh official records:",
        len(fresh_items)
    )

    # =====================================================
    # 安全機制
    # =====================================================
    # 如果這次完全抓不到，就什麼都不改。
    if not fresh_items:
        print(
            "No official Stamp Rally found."
        )
        print(
            "Existing JSON kept unchanged."
        )
        return

    merged = merge_items(
        old_items,
        fresh_items
    )

    merged = apply_manual_overrides(
        merged,
        manual_overrides
    )

    merged.sort(
        key=lambda item: (
            item.get("startDate", ""),
            item.get("event", ""),
            item.get("pref", ""),
            item.get("name", ""),
            item.get("id", ""),
        )
    )

    added, removed, changed = compare_items(
        old_items,
        merged
    )

    now = datetime.now(
        timezone.utc
    ).astimezone()

    updated = now.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    write_json(
        STAMP_FILE,
        {
            "version": "5.0",
            "updated": updated,
            "source": "official",
            "sourceMode": "official GO discovery + locale dedupe + manual overrides protected",
            "events": build_events_metadata(old_events, merged),
            "list": merged,
        }
    )

    history = load_json(
        HISTORY_FILE,
        {
            "history": []
        }
    )

    history_list = history.get(
        "history",
        []
    )

    merged_map = {
        item.get("id"): item
        for item in merged
        if item.get("id")
    }

    if added or changed or removed:
        history_list.insert(
            0,
            {
                "time": updated,
                "type": "stamp",
                "event": "Automatic official Stamp Rally sync",
                "source": (
                    "Pokémon Official Website / "
                    "Pokémon Center Official Website"
                ),
                "total": len(merged),
                "added": added,
                "removed": removed,
                "changed": changed,
                "addedItems": [
                    history_detail(merged_map[item_id])
                    for item_id in added
                    if item_id in merged_map
                ],
                "changedItems": [
                    history_detail(merged_map[item_id])
                    for item_id in changed
                    if item_id in merged_map
                ],
            }
        )

    history["history"] = history_list[:100]

    write_json(
        HISTORY_FILE,
        history
    )

    print("========================================")
    print("Total records:", len(merged))
    print("Added:", len(added))
    print("Changed:", len(changed))
    print("Removed:", len(removed))
    print("========================================")


if __name__ == "__main__":
    main()
