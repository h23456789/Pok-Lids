import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
STAMP_FILE = ROOT / "svgstamp_rally.json"
HISTORY_FILE = ROOT / "svgstamp_history.json"
GEOCODE_CACHE_FILE = ROOT / "stamp_geocode_cache.json"

TIMEOUT = 30
REQUEST_DELAY = 0.25
GEOCODE_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 PokémonJapanCollection/6.0 (+https://github.com/h23456789/Pok-Lids)",
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# 官方／主辦單位網站，不再只限 Pokémon Center。
OFFICIAL_DOMAINS = {
    "pokemon.co.jp", "www.pokemon.co.jp", "shop.pokemon.co.jp",
    "pokemongolive.com", "www.pokemongolive.com",
    "jreast.co.jp", "www.jreast.co.jp", "media.jreast.co.jp",
    "meitetsu.co.jp", "www.meitetsu.co.jp",
    "c-nexco.co.jp", "sapa.c-nexco.co.jp",
    "nexco-all-stamprally.jp", "www.nexco-all-stamprally.jp",
    "aeonmall.com", "online-event.aeonmall.com",
}

DISCOVERY_URLS = [
    "https://www.pokemon.co.jp/info/",
    "https://shop.pokemon.co.jp/ja/shop/common/events/",
    "https://pokemongolive.com/ja/news/",
    "https://www.jreast.co.jp/tokyo/jre_pokemonrally2026/",
    "https://media.jreast.co.jp/articles/6624",
    "https://www.meitetsu.co.jp/pr/pokemon2026/",
    "https://sapa.c-nexco.co.jp/topics?id=5212",
    "https://nexco-all-stamprally.jp/pokemon/",
    "https://online-event.aeonmall.com/pokemon/digital_stamp_rally_guide/",
]

KEYWORDS = [
    "スタンプラリー", "GOスタンプラリー", "デジタルスタンプラリー",
    "ポケふたスタンプラリー", "ビンゴラリー", "STAMP RALLY",
    "Stamp Rally", "stamp rally", "Bingo Rally", "スタンプを集め",
]

PREFS = [
    ("北海道", "北海道"), ("青森県", "青森県"), ("青森", "青森県"),
    ("岩手県", "岩手県"), ("岩手", "岩手県"), ("宮城県", "宮城県"), ("宮城", "宮城県"),
    ("秋田県", "秋田県"), ("秋田", "秋田県"), ("山形県", "山形県"), ("山形", "山形県"),
    ("福島県", "福島県"), ("福島", "福島県"), ("茨城県", "茨城県"), ("茨城", "茨城県"),
    ("栃木県", "栃木県"), ("栃木", "栃木県"), ("群馬県", "群馬県"), ("群馬", "群馬県"),
    ("埼玉県", "埼玉県"), ("埼玉", "埼玉県"), ("千葉県", "千葉県"), ("千葉", "千葉県"),
    ("東京都", "東京都"), ("東京", "東京都"), ("神奈川県", "神奈川県"), ("神奈川", "神奈川県"),
    ("新潟県", "新潟県"), ("新潟", "新潟県"), ("富山県", "富山県"), ("富山", "富山県"),
    ("石川県", "石川県"), ("石川", "石川県"), ("福井県", "福井県"), ("福井", "福井県"),
    ("山梨県", "山梨県"), ("山梨", "山梨県"), ("長野県", "長野県"), ("長野", "長野県"),
    ("岐阜県", "岐阜県"), ("岐阜", "岐阜県"), ("静岡県", "静岡県"), ("静岡", "静岡県"),
    ("愛知県", "愛知県"), ("愛知", "愛知県"), ("三重県", "三重県"), ("三重", "三重県"),
    ("滋賀県", "滋賀県"), ("滋賀", "滋賀県"), ("京都府", "京都府"), ("京都", "京都府"),
    ("大阪府", "大阪府"), ("大阪", "大阪府"), ("兵庫県", "兵庫県"), ("兵庫", "兵庫県"),
    ("奈良県", "奈良県"), ("奈良", "奈良県"), ("和歌山県", "和歌山県"), ("和歌山", "和歌山県"),
    ("鳥取県", "鳥取県"), ("鳥取", "鳥取県"), ("島根県", "島根県"), ("島根", "島根県"),
    ("岡山県", "岡山県"), ("岡山", "岡山県"), ("広島県", "広島県"), ("広島", "広島県"),
    ("山口県", "山口県"), ("山口", "山口県"), ("徳島県", "徳島県"), ("徳島", "徳島県"),
    ("香川県", "香川県"), ("香川", "香川県"), ("愛媛県", "愛媛県"), ("愛媛", "愛媛県"),
    ("高知県", "高知県"), ("高知", "高知県"), ("福岡県", "福岡県"), ("福岡", "福岡県"),
    ("佐賀県", "佐賀県"), ("佐賀", "佐賀県"), ("長崎県", "長崎県"), ("長崎", "長崎県"),
    ("熊本県", "熊本県"), ("熊本", "熊本県"), ("大分県", "大分県"), ("大分", "大分県"),
    ("宮崎県", "宮崎県"), ("宮崎", "宮崎県"), ("鹿児島県", "鹿児島県"), ("鹿児島", "鹿児島県"),
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

TRANSLATION_CACHE = {}
FALLBACK_ZH = {
    "ポケモンセンタースタンプラリー2026": "寶可夢中心集章拉力賽 2026",
    "Pokémon Center Stamp Rally 2026": "寶可夢中心集章拉力賽 2026",
    "GOスタンプラリー": "GO 集章拉力賽",
    "デジタルスタンプラリー": "數位集章拉力賽",
    "ポケふたスタンプラリー": "寶可夢井蓋集章拉力賽",
    "ポケモンビンゴラリー": "寶可夢賓果集章拉力賽",
    "ビンゴラリー": "賓果集章拉力賽",
    "スタンプラリー": "集章拉力賽",
    "ポケモンセンター": "寶可夢中心",
    "Pokémon GO Lab.": "Pokémon GO Lab.",
    "ポケモン": "寶可夢",
    "駅": "站",
}


def norm(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\u3000", " ")).strip()


def official(url):
    try:
        return (urlparse(url).hostname or "").lower() in OFFICIAL_DOMAINS
    except Exception:
        return False


def get(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        print("HTTP ERROR", url, e)
        return ""


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(*parts):
    return hashlib.sha1("|".join(norm(x) for x in parts).encode()).hexdigest()[:12].upper()


def parse_date(s):
    s = norm(s)
    m = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def dates(text):
    out = []
    for p in (r"20\d{2}年\d{1,2}月\d{1,2}日", r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}"):
        for x in re.findall(p, text):
            d = parse_date(x)
            if d and d not in out:
                out.append(d)
    return sorted(out)


def translate(text):
    text = norm(text)
    if not text:
        return ""
    if text in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[text]
    if text in FALLBACK_ZH:
        TRANSLATION_CACHE[text] = FALLBACK_ZH[text]
        return FALLBACK_ZH[text]
    # Google Translate 公開翻譯端點；失敗就以詞彙替換保底。
    try:
        u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=ja&tl=zh-TW&dt=t&q=" + quote(text)
        r = requests.get(u, timeout=15, headers=HEADERS)
        parts = r.json()[0]
        zh = "".join(p[0] for p in parts if p and p[0]).strip()
        if zh:
            TRANSLATION_CACHE[text] = zh
            return zh
    except Exception:
        pass
    result = text
    for ja, zh in sorted(FALLBACK_ZH.items(), key=lambda x: len(x[0]), reverse=True):
        result = result.replace(ja, zh)
    TRANSLATION_CACHE[text] = result
    return result


def extract_image(soup, base):
    # 優先找真正與 stamp / rally 有關的官方圖片，而不是網站 banner。
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        alt = norm(img.get("alt", ""))
        probe = (src + " " + alt).lower()
        if any(k in probe for k in ("stamp", "rally", "スタンプ", "stamp-rally", "pokemonrally")):
            return urljoin(base, src)
    for attrs in ({"property":"og:image"},{"name":"twitter:image"}):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            return urljoin(base, m["content"])
    return ""


def extract_google_coords(url):
    # Google Maps query / @lat,lng / ll=lat,lng / q=lat,lng
    for pat in [r"@(-?\d+\.\d+),(-?\d+\.\d+)", r"(?:ll|q)=(-?\d+\.\d+),(-?\d+\.\d+)"]:
        m = re.search(pat, url)
        if m:
            return [float(m.group(1)), float(m.group(2))]
    return []


def extract_map_links(soup, base):
    out = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])
        if "google.com/maps" in href or "maps.google" in href or "maps.app.goo.gl" in href:
            c = extract_google_coords(href)
            out.append((norm(a.get_text(" ", strip=True)), href, c))
    return out


def geocode(query, cache):
    query = norm(query)
    if not query:
        return []
    if query in cache:
        return cache[query]
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query + ", Japan", "format":"json", "limit":1, "countrycodes":"jp"},
            headers={"User-Agent":"PokemonJapanCollection/6.0"},
            timeout=20,
        )
        data = r.json()
        if data:
            coords = [float(data[0]["lat"]), float(data[0]["lon"])]
            cache[query] = coords
            time.sleep(GEOCODE_DELAY)
            return coords
    except Exception as e:
        print("GEOCODE ERROR", query, e)
    cache[query] = []
    time.sleep(GEOCODE_DELAY)
    return []


def pref_from(text):
    text = norm(text)
    for a, b in PREFS:
        if a in text:
            return b
    return ""


def city_from(text):
    m = re.search(r"([一-龥ぁ-んァ-ヶー]{2,12}市)", text)
    return m.group(1) if m else ""


def event_title(soup, text):
    for tag in soup.find_all(["h1","h2"]):
        x = norm(tag.get_text(" ", strip=True))
        if x and any(k.lower() in x.lower() for k in KEYWORDS):
            return x
    m = re.search(r"[^。]{0,80}(?:スタンプラリー|ビンゴラリー)[^。]{0,100}", text)
    if m:
        return norm(m.group(0))
    if soup.title:
        return norm(soup.title.get_text(" ", strip=True))
    return "期間限定 Pokémon Stamp Rally"


def activity(text):
    if "ポケふたスタンプラリー" in text: return "ポケふたスタンプラリー"
    if "GOスタンプラリー" in text: return "GOスタンプラリー"
    if "デジタルスタンプラリー" in text: return "デジタルスタンプラリー"
    if "ビンゴラリー" in text: return "ポケモンビンゴラリー"
    return "スタンプラリー"


def reward(text):
    for k in ["プレゼント内容","参加特典","達成賞","コンプリート特典","賞品","景品"]:
        p = text.find(k)
        if p >= 0:
            return norm(text[p:p+700])
    return ""


def point_candidates(soup, source_url, event_text):
    results = []
    seen = set()
    # 優先使用明確的地圖連結。
    for label, href, coords in extract_map_links(soup, source_url):
        name = label or "地圖上的集章點"
        key = norm(name)
        if key and key not in seen:
            seen.add(key)
            results.append((name, href, coords))
    # 常見交通／SA・PA／Pokemon Center 名稱。
    for a in soup.find_all("a", href=True):
        name = norm(a.get_text(" ", strip=True))
        if not name or len(name) > 80:
            continue
        if not any(t in name for t in ["ポケモンセンター","駅","SA","PA","サービスエリア","パーキングエリア","ラリースポット"]):
            continue
        href = urljoin(source_url, a["href"])
        if not official(href) and "google" not in href:
            continue
        key = name
        if key not in seen:
            seen.add(key)
            results.append((name, href, extract_google_coords(href)))
    # 只有活動級頁面、沒有明確連結時，找列舉文字。
    if not results:
        for m in re.findall(r"(?:ポケモンセンター[^、。\s]{0,30}|[^、。\s]{1,30}(?:駅|SA|PA))", event_text):
            name = norm(m)
            if name and name not in seen:
                seen.add(name)
                results.append((name, source_url, []))
    return results


def parse_event_page(url, old_items, geocache):
    html = get(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    text = norm(soup.get_text(" ", strip=True))
    if not any(k.lower() in text.lower() for k in KEYWORDS):
        return []
    ds = dates(text)
    if not ds:
        return []
    # 過期活動保留在 history 但不再當成目前活動；網站資料仍可查。
    event = event_title(soup, text)
    aid = "STAMP-AUTO-" + sha(event, url)
    img = extract_image(soup, url)
    act = activity(text)
    rw = reward(text)
    points = point_candidates(soup, url, text)
    if not points:
        points = [(event, url, extract_google_coords(url))]
    out = []
    for idx, (name, point_url, coords) in enumerate(points, 1):
        hint = CENTER_HINTS.get(name, ("", ""))
        pref = hint[0] or pref_from(name + " " + text)
        city = hint[1] or city_from(name)
        address = ""
        # 地址由連結頁或附近文字補強；沒有就以地點名稱 geocode。
        if not coords:
            coords = geocode(name if name != event else pref + " " + city, geocache)
        zh_name = translate(name)
        item = {
            "id": "STAMP-AUTO-" + sha(aid, name),
            "eventId": aid,
            "event": event,
            "eventZh": translate(event),
            "eventName": translate(event),
            "eventNameZh": translate(event),
            "activity": act,
            "activityZh": translate(act),
            "venueType": "pokemon_center" if "ポケモンセンター" in name else ("station" if "駅" in name else "stamp_point"),
            "venue": name,
            "venueZh": zh_name,
            "name": name,
            "nameZh": zh_name,
            "pref": pref,
            "city": city,
            "address": address,
            "addressZh": translate(address) if address else "",
            "coords": coords,
            "lat": coords[0] if len(coords)==2 else None,
            "lng": coords[1] if len(coords)==2 else None,
            "startDate": ds[0],
            "endDate": ds[-1] if len(ds)>1 else ds[0],
            "stampImage": img,
            "pointImage": img,
            "reward": rw,
            "rewardZh": translate(rw),
            "source": urlparse(url).netloc,
            "sourceUrl": url,
            "venueSourceUrl": point_url,
            "official": True,
            "coordinatesOfficial": bool(coords),
            "coordsSource": "官方 Google Maps" if coords and "google" in point_url else ("OpenStreetMap Nominatim" if coords else ""),
            "sequence": idx,
        }
        out.append(item)
    return out


def existing_by_id(old):
    return {x.get("id"): x for x in old if x.get("id")}


def merge(old, fresh):
    m = existing_by_id(old)
    for x in fresh:
        m[x["id"]] = x
    return list(m.values())


def history_detail(x):
    return {k:x.get(k) for k in ["id","event","eventZh","venue","venueZh","pref","city","coords","startDate","endDate","sourceUrl"]}


def main():
    print("=== Pokémon Japan Collection Stamp Rally Updater 6.0 ===")
    data = load(STAMP_FILE, {"version":"6.0","list":[]})
    old = data.get("list", [])
    cache = load(GEOCODE_CACHE_FILE, {})
    fresh = []
    checked = set()
    for url in DISCOVERY_URLS:
        if url in checked:
            continue
        checked.add(url)
        print("CHECK", url)
        items = parse_event_page(url, old, cache)
        if items:
            print("  FOUND", len(items), "points")
            fresh.extend(items)
        time.sleep(REQUEST_DELAY)

    # 既有官方活動頁也要重新抓，確保座標／翻譯／圖片會補齊。
    for x in old:
        u = x.get("sourceUrl", "")
        if official(u) and u not in checked:
            checked.add(u)
            items = parse_event_page(u, old, cache)
            if items:
                fresh.extend(items)
            time.sleep(REQUEST_DELAY)

    # 去重：同活動同地點只留一筆。
    unique = {}
    for x in fresh:
        key = (x.get("eventId"), x.get("venue"), x.get("sourceUrl"))
        unique[key] = x
    fresh = list(unique.values())

    if not fresh:
        print("No new official data; existing data kept.")
        save(GEOCODE_CACHE_FILE, cache)
        return

    merged = merge(old, fresh)
    merged.sort(key=lambda x:(x.get("startDate",""), x.get("eventZh",x.get("event","")), x.get("sequence",0), x.get("venueZh",x.get("venue",""))))
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    old_map = existing_by_id(old)
    new_map = existing_by_id(merged)
    added = [k for k in new_map if k not in old_map]
    changed = [k for k in new_map if k in old_map and old_map[k] != new_map[k]]

    save(STAMP_FILE, {
        "version":"6.0",
        "updated":now,
        "source":"official / partner official sources",
        "groupBy":"event",
        "list":merged,
    })
    save(GEOCODE_CACHE_FILE, cache)

    hist = load(HISTORY_FILE, {"history":[]})
    if added or changed:
        hist.setdefault("history", []).insert(0, {
            "time":now,
            "type":"stamp",
            "event":"Automatic Stamp Rally sync",
            "source":"Official Pokémon / JR East / Meitetsu / NEXCO / Pokémon GO sources",
            "total":len(merged),
            "added":added,
            "changed":changed,
            "addedItems":[history_detail(new_map[k]) for k in added],
            "changedItems":[history_detail(new_map[k]) for k in changed],
        })
    hist["history"] = hist.get("history",[])[:100]
    save(HISTORY_FILE, hist)
    print("TOTAL", len(merged), "ADDED", len(added), "CHANGED", len(changed))

if __name__ == "__main__":
    main()
