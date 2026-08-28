import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# =========================================================
# CONFIG
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"

TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; PokemonJapanCollectionUpdater/2.0; "
        "+https://github.com/h23456789/Pok-Lids)"
    )
}


# =========================================================
# OFFICIAL SOURCES
# =========================================================

SEED_URLS = [
    "https://shop.pokemon.co.jp/ja/shop/common/events/202606/000336.html"
]


OFFICIAL_INDEXES = [
    "https://shop.pokemon.co.jp/ja/sitemap/",
    "https://www.pokemon.co.jp/sitemap/"
]


STAMP_KEYWORDS = (
    "スタンプラリー",
    "GOスタンプラリー",
    "STAMP RALLY",
    "Stamp Rally",
    "stamp rally"
)


# =========================================================
# PREFECTURE
# =========================================================

PREF_ALIAS = {
    "北海道": "北海道",
    "青森": "青森県",
    "青森県": "青森県",
    "岩手": "岩手県",
    "岩手県": "岩手県",
    "宮城": "宮城県",
    "宮城県": "宮城県",
    "秋田": "秋田県",
    "秋田県": "秋田県",
    "山形": "山形県",
    "山形県": "山形県",
    "福島": "福島県",
    "福島県": "福島県",
    "茨城": "茨城県",
    "茨城県": "茨城県",
    "栃木": "栃木県",
    "栃木県": "栃木県",
    "群馬": "群馬県",
    "群馬県": "群馬県",
    "埼玉": "埼玉県",
    "埼玉県": "埼玉県",
    "千葉": "千葉県",
    "千葉県": "千葉県",
    "東京": "東京都",
    "東京都": "東京都",
    "神奈川": "神奈川県",
    "神奈川県": "神奈川県",
    "新潟": "新潟県",
    "新潟県": "新潟県",
    "富山": "富山県",
    "富山県": "富山県",
    "石川": "石川県",
    "石川県": "石川県",
    "福井": "福井県",
    "福井県": "福井県",
    "山梨": "山梨県",
    "山梨県": "山梨県",
    "長野": "長野県",
    "長野県": "長野県",
    "岐阜": "岐阜県",
    "岐阜県": "岐阜県",
    "静岡": "静岡県",
    "静岡県": "静岡県",
    "愛知": "愛知県",
    "愛知県": "愛知県",
    "三重": "三重県",
    "三重県": "三重県",
    "滋賀": "滋賀県",
    "滋賀県": "滋賀県",
    "京都": "京都府",
    "京都府": "京都府",
    "大阪": "大阪府",
    "大阪府": "大阪府",
    "兵庫": "兵庫県",
    "兵庫県": "兵庫県",
    "奈良": "奈良県",
    "奈良県": "奈良県",
    "和歌山": "和歌山県",
    "和歌山県": "和歌山県",
    "鳥取": "鳥取県",
    "鳥取県": "鳥取県",
    "島根": "島根県",
    "島根県": "島根県",
    "岡山": "岡山県",
    "岡山県": "岡山県",
    "広島": "広島県",
    "広島県": "広島県",
    "山口": "山口県",
    "山口県": "山口県",
    "徳島": "徳島県",
    "徳島県": "徳島県",
    "香川": "香川県",
    "香川県": "香川県",
    "愛媛": "愛媛県",
    "愛媛県": "愛媛県",
    "高知": "高知県",
    "高知県": "高知県",
    "福岡": "福岡県",
    "福岡県": "福岡県",
    "佐賀": "佐賀県",
    "佐賀県": "佐賀県",
    "長崎": "長崎県",
    "長崎県": "長崎県",
    "熊本": "熊本県",
    "熊本県": "熊本県",
    "大分": "大分県",
    "大分県": "大分県",
    "宮崎": "宮崎県",
    "宮崎県": "宮崎県",
    "鹿児島": "鹿児島県",
    "鹿児島県": "鹿児島県",
    "沖縄": "沖縄県",
    "沖縄県": "沖縄県"
}


# =========================================================
# KNOWN OFFICIAL CENTERS
# =========================================================

KNOWN_CENTERS = [
    ("ポケモンセンターサッポロ", "北海道", "札幌市"),
    ("ポケモンセンタートウホク", "宮城県", "仙台市"),
    ("ポケモンセンタートウキョーDX", "東京都", "中央区"),
    ("ポケモンセンターメガトウキョー", "東京都", "豊島区"),
    ("ポケモンセンターシブヤ", "東京都", "渋谷区"),
    ("ポケモンセンタースカイツリータウン", "東京都", "墨田区"),
    ("ポケモンセンタートウキョーベイ", "千葉県", "船橋市"),
    ("ポケモンセンターヨコハマ", "神奈川県", "横浜市"),
    ("ポケモンセンターナゴヤ", "愛知県", "名古屋市"),
    ("ポケモンセンターカナザワ", "石川県", "金沢市"),
    ("ポケモンセンターキョウト", "京都府", "京都市"),
    ("ポケモンセンターオーサカDX", "大阪府", "大阪市"),
    ("ポケモンセンターオーサカ", "大阪府", "大阪市"),
    ("ポケモンセンターヒロシマ", "広島県", "広島市"),
    ("ポケモンセンターカガワ", "香川県", "高松市"),
    ("ポケモンセンターフクオカ", "福岡県", "福岡市"),
    ("ポケモンセンターオキナワ", "沖縄県", "沖縄市")
]


# =========================================================
# TEXT
# =========================================================

def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


# =========================================================
# HTTP
# =========================================================

def get_html(url):
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


# =========================================================
# DATE
# ==========================================================

def parse_date(text):
    if not text:
        return ""

    patterns = [
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
        r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"

    return ""


def extract_dates(text):
    dates = []
    for match in re.finditer(r"20\d{2}年\d{1,2}月\d{1,2}日", text or ""):
        value = parse_date(match.group(0))
        if value and value not in dates:
            dates.append(value)
    return dates


# =========================================================
# ID
# =========================================================

def make_event_id(url, event):
    raw = f"{url}|{event}"
    return "STAMP-AUTO-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def make_item_id(event_id, venue):
    raw = f"{event_id}|{venue}"
    return event_id + "-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8].upper()


# =========================================================
# PAGE INFO
# =========================================================

def get_title(soup):
    h1 = soup.find("h1")
    if h1:
        text = normalize_text(h1.get_text(" ", strip=True))
        if text:
            return text

    if soup.title:
        return normalize_text(soup.title.get_text(" ", strip=True))

    return "期間限定 Stamp Rally"


def get_image(soup, base_url):
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return urljoin(base_url, og["content"])

    image = soup.find("img", src=True)
    if image:
        return urljoin(base_url, image["src"])

    return ""


# =========================================================
# DISCOVERY
# ==========================================================

def discover_event_urls():
    urls = set(SEED_URLS)

    for source in OFFICIAL_INDEXES:
        try:
            html = get_html(source)
            soup = BeautifulSoup(html, "html.parser")
        except Exception as error:
            print("INDEX ERROR:", source, error)
            continue

        for link in soup.find_all("a", href=True):
            href = urljoin(source, link["href"])
            text = normalize_text(link.get_text(" ", strip=True))
            combined = text + " " + href

            if not any(keyword in combined for keyword in STAMP_KEYWORDS):
                continue

            if href.startswith("https://shop.pokemon.co.jp/") or href.startswith("https://www.pokemon.co.jp/"):
                urls.add(href.split("#", 1)[0])

    return sorted(urls)


# =========================================================
# VENUE DISCOVERY
# ==========================================================

def extract_venues(soup, base_url, page_text):
    venues = []
    seen = set()

    for link in soup.find_all("a", href=True):
        name = normalize_text(link.get_text(" ", strip=True))

        if not name:
            continue
        if "ポケモンセンター" not in name:
            continue
        if "サテライト" in name or "出張所" in name:
            continue
        if name in seen:
            continue

        venues.append({
            "name": name,
            "url": urljoin(base_url, link["href"])
        })
        seen.add(name)

    if "Pokémon GO Lab." in page_text or "Pokémon GO Lab" in page_text:
        if "Pokémon GO Lab." not in seen:
            venues.append({
                "name": "Pokémon GO Lab.",
                "url": base_url
            })

    return venues


# =========================================================
# KNOWN LOCATION
# ==========================================================

def parse_location_from_name(name):
    for center, pref, city in KNOWN_CENTERS:
        if center == name:
            return pref, city
    return "", ""


# =========================================================
# STORE ADDRESS
# ==========================================================

def parse_address_from_store(url):
    if not url:
        return ""

    try:
        html = get_html(url)
        soup = BeautifulSoup(html, "html.parser")
        text = normalize_text(soup.get_text(" ", strip=True))
        match = re.search(r"〒\s*\d{3}-?\d{4}\s*([^|｜]{5,120})", text)
        if match:
            return normalize_text(match.group(1))
    except Exception as error:
        print("STORE ERROR:", url, error)

    return ""


# =========================================================
# PARSE STAMP PAGE
# ==========================================================

def parse_stamp_page(url):
    html = get_html(url)
    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_text(soup.get_text(" ", strip=True))

    if not any(keyword in page_text for keyword in STAMP_KEYWORDS):
        return []

    title = get_title(soup)
    event = title
    match = re.search(r"(ポケモン.{0,80}?スタンプラリー.{0,80})", page_text)
    if match:
        event = normalize_text(match.group(1))

    dates = extract_dates(page_text)
    start_date = dates[0] if dates else ""
    end_date = dates[1] if len(dates) > 1 else ""

    event_id = make_event_id(url, event)
    image_url = get_image(soup, url)

    reward = ""
    for keyword in ("プレゼント内容", "認定証", "コンプリート"):
        position = page_text.find(keyword)
        if position >= 0:
            reward = page_text[position:position + 300]
            break

    venues = extract_venues(soup, url, page_text)

    # 目前 Pokémon Center 官方 2026 頁面：
    # 17 家 Pokémon Center + Pokémon GO Lab.
    # 如果官方網站改版導致店舖連結抓不到，使用官方店舖名單作為保底。
    if len(venues) < 2 and "ポケモンセンター" in page_text:
        venues = [
            {
                "name": name,
                "url": url
            }
            for name, _, _ in KNOWN_CENTERS
        ]

        if "Pokémon GO Lab." in page_text:
            venues.append({
                "name": "Pokémon GO Lab.",
                "url": url
            })

    items = []

    for venue in venues:
        name = venue["name"]
        pref, city = parse_location_from_name(name)
        address = parse_address_from_store(venue.get("url", ""))

        if not pref and address:
            for alias, canonical in PREF_ALIAS.items():
                if alias in address:
                    pref = canonical
                    break

        venue_type = "pokemon_go_lab" if "GO Lab" in name else "pokemon_center"

        items.append({
            "id": make_item_id(event_id, name),
            "eventId": event_id,
            "event": event,
            "eventName": event,
            "activity": "Pokémon GO GOスタンプラリー",
            "venueType": venue_type,
            "venue": name,
            "name": name,
            "pref": pref,
            "city": city,
            "address": address,
            "coords": [],
            "startDate": start_date,
            "endDate": end_date,
            "stampImage": image_url,
            "reward": reward,
            "source": "Pokémon Center Official Website",
            "sourceUrl": url,
            "venueSourceUrl": venue.get("url", ""),
            "official": True
        })

    # 官方頁如果完全沒有列出地點，還是保留一筆活動資料，避免活動因網站改版而整個消失。
    if not items:
        items.append({
            "id": make_item_id(event_id, event),
            "eventId": event_id,
            "event": event,
            "eventName": event,
            "activity": "Stamp Rally",
            "venueType": "event",
            "venue": "官方活動頁",
            "name": event,
            "pref": "",
            "city": "",
            "address": "",
            "coords": [],
            "startDate": start_date,
            "endDate": end_date,
            "stampImage": image_url,
            "reward": reward,
            "source": "Pokémon Official Website",
            "sourceUrl": url,
            "official": True
        })

    return items


# =========================================================
# JSON
# ==========================================================

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


# =========================================================
# MERGE
# ==========================================================

def merge_items(old_items, new_items):
    merged = {item.get("id"): item for item in old_items if item.get("id")}
    for item in new_items:
        if item.get("id"):
            merged[item["id"]] = item
    return list(merged.values())


# =========================================================
# HISTORY COMPARE
# ==========================================================

def compare_items(old_items, new_items):
    old_map = {item.get("id"): item for item in old_items if item.get("id")}
    new_map = {item.get("id"): item for item in new_items if item.get("id")}

    added = [key for key in new_map if key not in old_map]
    removed = [key for key in old_map if key not in new_map]
    changed = [key for key in new_map if key in old_map and old_map[key] != new_map[key]]

    return added, removed, changed


# =========================================================
# MAIN
# ==========================================================

def main():
    print("========================================")
    print("Pokémon Stamp Rally updater 2.0")
    print("Official source only")
    print("========================================")

    old_data = load_json(STAMP_FILE, {"list": []})
    old_items = old_data.get("list", [])

    urls = discover_event_urls()
    print("Discovered official URLs:", len(urls))

    new_items = []
    successful_pages = 0

    for url in urls:
        print("Checking:", url)
        try:
            parsed = parse_stamp_page(url)
            if parsed:
                successful_pages += 1
                new_items.extend(parsed)
                print("  ->", len(parsed), "items")
        except Exception as error:
            print("PARSE ERROR:", url, error)

    if not new_items:
        print("No official Stamp Rally data found.")
        print("Existing JSON is kept.")
        return

    merged = merge_items(old_items, new_items)
    merged.sort(key=lambda item: (
        item.get("startDate", ""),
        item.get("event", ""),
        item.get("name", ""),
        item.get("id", "")
    ))

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    output = {
        "version": "3.0",
        "updated": now,
        "source": "official",
        "list": merged
    }

    added, removed, changed = compare_items(old_items, merged)
    write_json(STAMP_FILE, output)

    history_data = load_json(HISTORY_FILE, {"history": []})
    history = history_data.get("history", [])

    history.insert(0, {
        "time": now,
        "type": "stamp",
        "event": "Automatic official Stamp Rally sync",
        "source": "Pokémon Center Official Website",
        "pages": successful_pages,
        "total": len(merged),
        "added": added,
        "removed": removed,
        "changed": changed
    })

    history_data["history"] = history[:100]
    write_json(HISTORY_FILE, history_data)

    print("========================================")
    print("Updated:", len(merged))
    print("Added:", len(added))
    print("Removed:", len(removed))
    print("Changed:", len(changed))
    print("========================================")


if __name__ == "__main__":
    main()
