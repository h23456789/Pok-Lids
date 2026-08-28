import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]

STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"

TIMEOUT = 30
REQUEST_DELAY = 0.4
MAX_DISCOVERED_URLS = 300

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; PokemonJapanCollectionUpdater/3.0; "
        "+https://github.com/h23456789/Pok-Lids)"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


OFFICIAL_DOMAINS = {
    "pokemon.co.jp",
    "www.pokemon.co.jp",
    "shop.pokemon.co.jp"
}


DISCOVERY_URLS = [
    "https://www.pokemon.co.jp/",
    "https://www.pokemon.co.jp/sitemap/",
    "https://www.pokemon.co.jp/info/",
    "https://www.pokemon.co.jp/event/",
    "https://shop.pokemon.co.jp/ja/",
    "https://shop.pokemon.co.jp/ja/sitemap/",
    "https://shop.pokemon.co.jp/ja/shop/common/events/"
]


STAMP_KEYWORDS = [
    "スタンプラリー",
    "GOスタンプラリー",
    "デジタルスタンプラリー",
    "STAMP RALLY",
    "Stamp Rally",
    "stamp rally"
]


PREF_ALIASES = {
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


CENTER_TO_LOCATION = {
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
    "Pokémon GO Lab.": ("東京都", "豊島区")
}


def normalize_text(value):
    if value is None:
        return ""
    value = str(value)
    value = value.replace("\u3000", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


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
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text
    except Exception as error:
        print("HTTP ERROR:", url, error)
        return ""


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
    dates = []
    patterns = [
        r"20\d{2}年\d{1,2}月\d{1,2}日",
        r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}"
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, text or ""):
            parsed = parse_date(raw)
            if parsed and parsed not in dates:
                dates.append(parsed)
    return sorted(dates)


def make_hash(*parts):
    raw = "|".join(normalize_text(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def get_event_id(event, source_url, old_items):
    for item in old_items:
        if normalize_text(item.get("event")) == normalize_text(event):
            old_url = normalize_text(item.get("sourceUrl", ""))
            if old_url.rstrip("/") == source_url.rstrip("/"):
                return item.get("eventId") or item.get("id")
    return "STAMP-AUTO-" + make_hash(event, source_url)


def get_item_id(event_id, venue):
    return f"{event_id}-{make_hash(venue)[:8]}"


def extract_event_name(soup, page_text):
    candidates = []
    for tag in soup.find_all("h1"):
        value = normalize_text(tag.get_text(" ", strip=True))
        if value:
            candidates.append(value)

    for attrs in [{"property": "og:title"}, {"name": "twitter:title"}]:
        meta = soup.find("meta", attrs=attrs)
        if meta:
            value = normalize_text(meta.get("content", ""))
            if value:
                candidates.append(value)

    if soup.title:
        value = normalize_text(soup.title.get_text(" ", strip=True))
        if value:
            candidates.append(value)

    for value in candidates:
        if "スタンプラリー" in value or "Stamp Rally" in value:
            return value

    match = re.search(r".{0,80}スタンプラリー.{0,120}", page_text or "")
    if match:
        return normalize_text(match.group(0))

    if candidates:
        return candidates[0]

    return "期間限定 Stamp Rally"


def extract_image(soup, base_url):
    for attrs in [{"property": "og:image"}, {"name": "twitter:image"}]:
        meta = soup.find("meta", attrs=attrs)
        if meta:
            source = normalize_text(meta.get("content", ""))
            if source:
                return urljoin(base_url, source)

    for image in soup.find_all("img"):
        source = image.get("src") or image.get("data-src") or image.get("data-lazy-src")
        if not source:
            continue
        absolute = urljoin(base_url, source)
        lower = absolute.lower()
        if any(keyword in lower for keyword in ("stamp", "rally", "スタンプ")):
            return absolute

    return ""


def extract_reward(page_text):
    for keyword in ("プレゼント内容", "プレゼント条件", "認定証", "コンプリート"):
        position = page_text.find(keyword)
        if position >= 0:
            return normalize_text(page_text[position : position + 450])
    return ""


def extract_activity(page_text):
    if "GOスタンプラリー" in page_text:
        return "Pokémon GO GOスタンプラリー"
    if "デジタルスタンプラリー" in page_text:
        return "デジタルスタンプラリー"
    return "Stamp Rally"


def extract_center_links(soup, base_url):
    results = []
    seen = set()
    for link in soup.find_all("a", href=True):
        name = normalize_text(link.get_text(" ", strip=True))
        if not name:
            continue
        if "ポケモンセンター" not in name:
            continue
        if "サテライト" in name or "出張所" in name or "カフェ" in name:
            continue
        if name in seen:
            continue

        results.append({
            "name": name,
            "url": urljoin(base_url, link["href"])
        })
        seen.add(name)
    return results


def get_official_center_list():
    urls = ["https://shop.pokemon.co.jp/ja/sitemap/"]
    centers = []
    seen = set()

    for url in urls:
        html = get_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for item in extract_center_links(soup, url):
            name = item["name"]
            if name in seen:
                continue
            centers.append(item)
            seen.add(name)
        time.sleep(REQUEST_DELAY)

    return centers


def extract_prefecture(text):
    text = normalize_text(text)
    for alias, canonical in PREF_ALIASES.items():
        if alias in text:
            return canonical
    return ""


def enrich_center(item, center_url):
    html = get_html(center_url)
    if not html:
        return item
    
    soup = BeautifulSoup(html, "html.parser")
    text = normalize_text(soup.get_text(" ", strip=True))
    address = ""
    patterns = [
        r"〒\s*\d{3}-?\d{4}\s*([^|｜]{5,150})",
        r"住所\s*[:：]?\s*([^|｜]{5,150})"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            address = normalize_text(match.group(1))
            break

    pref = item.get("pref", "")
    city = item.get("city", "")

    if not pref:
        pref = extract_prefecture(address)

    known = CENTER_TO_LOCATION.get(item.get("name", ""))
    if known:
        known_pref, known_city = known
        if not pref:
            pref = known_pref
        if not city:
            city = known_city

    item["address"] = address
    item["pref"] = pref
    item["city"] = city
    item["venueSourceUrl"] = center_url
    return item


def parse_stamp_page(url, old_items, center_list):
    html = get_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_text(soup.get_text(" ", strip=True))

    if not any(keyword.lower() in page_text.lower() for keyword in STAMP_KEYWORDS):
        return []

    event = extract_event_name(soup, page_text)
    event_id = get_event_id(event, url, old_items)
    dates = extract_dates(page_text)
    start_date = dates[0] if dates else ""
    end_date = dates[1] if len(dates) >= 2 else ""
    event_image = extract_image(soup, url)
    reward = extract_reward(page_text)
    activity = extract_activity(page_text)
    centers = extract_center_links(soup, url)

    if len(centers) < 2 and "ポケモンセンター" in page_text:
        centers = center_list

    items = []

    if centers:
        seen = set()
        for center in centers:
            name = center["name"]
            if name in seen:
                continue
            seen.add(name)

            pref, city = CENTER_TO_LOCATION.get(name, ("", ""))
            venue_type = "pokemon_go_lab" if "GO Lab" in name else "pokemon_center"

            item = {
                "id": get_item_id(event_id, name),
                "eventId": event_id,
                "event": event,
                "eventName": event,
                "activity": activity,
                "venueType": venue_type,
                "venue": name,
                "name": name,
                "pref": pref,
                "city": city,
                "address": "",
                "coords": [],
                "startDate": start_date,
                "endDate": end_date,
                "stampImage": event_image,
                "reward": reward,
                "source": (
                    "Pokémon Center Official Website"
                    if "shop.pokemon.co.jp" in url
                    else "Pokémon Official Website"
                ),
                "sourceUrl": url,
                "venueSourceUrl": center.get("url", ""),
                "official": True
            }

            venue_url = center.get("url", "")
            if venue_url and is_official_url(venue_url):
                item = enrich_center(item, venue_url)
                time.sleep(REQUEST_DELAY)

            items.append(item)
    else:
        venue = ""
        venue_type = "event"

        if "Pokémon GO Lab" in page_text:
            venue = "Pokémon GO Lab."
            venue_type = "pokemon_go_lab"
        elif "ポケモンセンター" in page_text:
            venue = "全国のポケモンセンター"
            venue_type = "pokemon_center"

        items.append({
            "id": get_item_id(event_id, venue or event),
            "eventId": event_id,
            "event": event,
            "eventName": event,
            "activity": activity,
            "venueType": venue_type,
            "venue": venue,
            "name": venue or event,
            "pref": "",
            "city": "",
            "address": "",
            "coords": [],
            "startDate": start_date,
            "endDate": end_date,
            "stampImage": event_image,
            "reward": reward,
            "source": (
                "Pokémon Center Official Website"
                if "shop.pokemon.co.jp" in url
                else "Pokémon Official Website"
            ),
            "sourceUrl": url,
            "official": True
        })

    return items


def discover_urls():
    discovered = set()
    queue = list(DISCOVERY_URLS)
    scanned = set()

    while queue and len(scanned) < MAX_DISCOVERED_URLS:
        url = queue.pop(0)
        if url in scanned or not is_official_url(url):
            continue

        scanned.add(url)
        print("DISCOVER:", url)

        html = get_html(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = urljoin(url, link["href"])
            href = href.split("#", 1)[0]

            if not is_official_url(href):
                continue

            text = normalize_text(link.get_text(" ", strip=True))
            combined = f"{text} {href}"

            if any(keyword.lower() in combined.lower() for keyword in STAMP_KEYWORDS):
                discovered.add(href)

            path = urlparse(href).path.lower()
            if any(token in path for token in ("/info/", "/event/", "/events/", "/campaign/", "/common/events/")):
                if href not in scanned and href not in queue:
                    queue.append(href)

        time.sleep(REQUEST_DELAY)

    return sorted(discovered)


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


def merge_items(old_items, fresh_items):
    merged = {item.get("id"): item for item in old_items if item.get("id")}
    concrete_event_ids = {
        item.get("eventId") for item in fresh_items
        if item.get("eventId") and item.get("pref")
    }

    for item_id, item in list(merged.items()):
        if item.get("eventId") in concrete_event_ids and not item.get("pref"):
            del merged[item_id]

    for item in fresh_items:
        if item.get("id"):
            merged[item["id"]] = item

    return list(merged.values())


def compare_items(old_items, new_items):
    old_map = {item.get("id"): item for item in old_items if item.get("id")}
    new_map = {item.get("id"): item for item in new_items if item.get("id")}
    
    added = [item_id for item_id in new_map if item_id not in old_map]
    changed = [
        item_id for item_id in new_map 
        if item_id in old_map and old_map[item_id] != new_map[item_id]
    ]
    removed = [] 
    
    return added, removed, changed


def history_detail(item):
    return {
        "id": item.get("id", ""),
        "event": item.get("event", ""),
        "name": item.get("name", ""),
        "pref": item.get("pref", ""),
        "startDate": item.get("startDate", ""),
        "endDate": item.get("endDate", ""),
        "sourceUrl": item.get("sourceUrl", "")
    }


def main():
    print("========================================")
    print("Pokémon Stamp Rally AUTO UPDATER")
    print("Official-source discovery mode")
    print("========================================")

    old_data = load_json(STAMP_FILE, {"list": []})
    old_items = old_data.get("list", [])
    print("Existing:", len(old_items))

    center_list = get_official_center_list()
    print("Official center candidates:", len(center_list))

    urls = discover_urls()
    print("Discovered official URLs:", len(urls))

    fresh_items = []

    for url in urls:
        print("CHECK:", url)
        try:
            items = parse_stamp_page(url, old_items, center_list)
            if items:
                print("  FOUND:", len(items))
                fresh_items.extend(items)
        except Exception as error:
            print("  ERROR:", error)
        time.sleep(REQUEST_DELAY)

    unique = {}
    for item in fresh_items:
        if item.get("id"):
            unique[item["id"]] = item
            
    fresh_items = list(unique.values())

    if not fresh_items:
        print("No official Stamp Rally found.")
        print("Existing data kept.")
        return

    merged = merge_items(old_items, fresh_items)
    merged.sort(key=lambda item: (
        item.get("startDate", ""),
        item.get("event", ""),
        item.get("pref", ""),
        item.get("name", "")
    ))

    added, removed, changed = compare_items(old_items, merged)
    now = datetime.now(timezone.utc).astimezone()
    updated = now.strftime("%Y-%m-%d %H:%M:%S")

    output = {
        "version": "3.0",
        "updated": updated,
        "source": "official",
        "list": merged
    }

    write_json(STAMP_FILE, output)

    history = load_json(HISTORY_FILE, {"history": []})
    history_list = history.get("history", [])
    new_map = {item.get("id"): item for item in merged if item.get("id")}

    history_list.insert(0, {
        "time": updated,
        "type": "stamp",
        "event": "Automatic official Stamp Rally sync",
        "source": "Pokémon Official Website / Pokémon Center Official Website",
        "total": len(merged),
        "added": added,
        "removed": removed,
        "changed": changed,
        "addedItems": [
            history_detail(new_map[item_id]) for item_id in added if item_id in new_map
        ],
        "changedItems": [
            history_detail(new_map[item_id]) for item_id in changed if item_id in new_map
        ]
    })

    history["history"] = history_list[:100]
    write_json(HISTORY_FILE, history)

    print("========================================")
    print("Total:", len(merged))
    print("Added:", len(added))
    print("Changed:", len(changed))
    print("Removed:", len(removed))
    print("========================================")


if __name__ == "__main__":
    main()
