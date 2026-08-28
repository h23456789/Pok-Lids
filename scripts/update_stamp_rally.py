import json
import re
import hashlib
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
        "(compatible; PokemonJapanCollectionUpdater/1.0; "
        "+https://github.com/h23456789/Pok-Lids)"
    )
}


OFFICIAL_SOURCES = [

    # Pokémon Center 官方活動
    "https://shop.pokemon.co.jp/ja/shop/common/events/202606/000336.html",

    # Pokémon 官方網站 sitemap
    "https://www.pokemon.co.jp/sitemap/",

    # Pokémon Center sitemap
    "https://shop.pokemon.co.jp/ja/sitemap/"

]


# =========================================================
# HTTP
# =========================================================

def get_html(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    response.encoding = response.apparent_encoding

    return response.text


# =========================================================
# NORMALIZE
# =========================================================

def normalize_text(value):

    if not value:
        return ""

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# DATE
# =========================================================

JAPANESE_MONTH = {
    "1": "01",
    "2": "02",
    "3": "03",
    "4": "04",
    "5": "05",
    "6": "06",
    "7": "07",
    "8": "08",
    "9": "09",
    "10": "10",
    "11": "11",
    "12": "12"
}


def parse_japanese_date(text):

    if not text:
        return ""


    # 2026年7月1日
    match = re.search(
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
        text
    )

    if match:

        year, month, day = match.groups()

        return (
            f"{year}-"
            f"{JAPANESE_MONTH[month]}-"
            f"{int(day):02d}"
        )


    # 2026/07/01
    match = re.search(
        r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})",
        text
    )

    if match:

        year, month, day = match.groups()

        return (
            f"{year}-"
            f"{int(month):02d}-"
            f"{int(day):02d}"
        )


    return ""


# =========================================================
# ID
# =========================================================

def make_id(event, venue):

    raw = (
        normalize_text(event)
        + "|"
        + normalize_text(venue)
    )

    digest = hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:12]

    return (
        "STAMP-AUTO-"
        + digest.upper()
    )


# =========================================================
# STAMP PAGE PARSER
# =========================================================

def parse_stamp_page(url):

    html = get_html(url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    page_text = normalize_text(
        soup.get_text(" ", strip=True)
    )


    # -----------------------------------------------------
    # 判斷是否為 Stamp Rally
    # -----------------------------------------------------

    keywords = [

        "スタンプラリー",
        "GOスタンプラリー",
        "STAMP RALLY",
        "Stamp Rally",
        "stamp rally"

    ]

    if not any(
        keyword in page_text
        for keyword in keywords
    ):

        return []


    # -----------------------------------------------------
    # Title
    # -----------------------------------------------------

    title = ""

    if soup.title:

        title = normalize_text(
            soup.title.get_text()
        )


    h1 = soup.find("h1")

    if h1:

        h1_text = normalize_text(
            h1.get_text()
        )

        if h1_text:

            title = h1_text


    if not title:

        title = "期間限定 Stamp Rally"


    # -----------------------------------------------------
    # Event
    # -----------------------------------------------------

    event = title


    stamp_match = re.search(
        r"(ポケモン.{0,40}スタンプラリー.{0,40})",
        page_text
    )

    if stamp_match:

        event = normalize_text(
                stamp_match.group(1)
            )


    # -----------------------------------------------------
    # Dates
    # -----------------------------------------------------

    dates = re.findall(

        r"20\d{2}年\d{1,2}月\d{1,2}日",

        page_text

    )


    start_date = ""
    end_date = ""


    if len(dates) >= 1:

        start_date = parse_japanese_date(
                dates[0]
            )


    if len(dates) >= 2:

        end_date = parse_japanese_date(
                dates[1]
            )


    # -----------------------------------------------------
    # Image
    # -----------------------------------------------------

    image_url = ""


    og_image = soup.find(
        "meta",
        attrs={
            "property": "og:image"
        }
    )


    if og_image:

        image_url = urljoin(
                url,
                og_image.get(
                    "content",
                    ""
                )
            )


    if not image_url:

        image = soup.find(
            "img"
        )

        if image:

            image_url = urljoin(
                    url,
                    image.get(
                        "src",
                        ""
                    )
                )


    # -----------------------------------------------------
    # Venue
    # -----------------------------------------------------

    venue = ""


    venue_keywords = [

        "ポケモンセンター",
        "Pokémon Center",
        "Pokémon GO Lab",
        "ポケモンストア"

    ]


    for keyword in venue_keywords:

        if keyword in page_text:

            venue = keyword

            break


    venue_type = ""


    if (
        "ポケモンセンター"
        in page_text
        or
        "Pokémon Center"
        in page_text
    ):

        venue_type = "pokemon_center"


    elif "ポケモンストア" in page_text:

        venue_type = "pokemon_store"


    # -----------------------------------------------------
    # Reward
    # -----------------------------------------------------

    reward = ""


    reward_keywords = [

        "プレゼント内容",
        "プレゼント",
        "認定証",
        "コンプリート"

    ]


    for keyword in reward_keywords:

        position =
            page_text.find(
                keyword
            )


        if position >= 0:

            reward = page_text[
                    position:
                    position + 300
                ]

            break


    # -----------------------------------------------------
    # Record
    # -----------------------------------------------------

    item = {

        "id":
            make_id(
                event,
                venue
            ),

        "event":
            event,

        "eventName":
            event,

        "venueType":
            venue_type,

        "venue":
            venue,

        "pref":
            "",

        "city":
            "",

        "address":
            "",

        "coords":
            [],

        "startDate":
            start_date,

        "endDate":
            end_date,

        "stampImage":
            image_url,

        "reward":
            reward,

        "source":
            "Pokémon Official Website",

        "sourceUrl":
            url,

        "official":
            True

    }


    return [item]


# =========================================================
# URL DISCOVERY
# =========================================================

def discover_urls():

    urls = set()


    for source in OFFICIAL_SOURCES:

        try:

            html = get_html(
                    source
                )

        except Exception as error:

            print(
                "SOURCE ERROR:",
                source,
                error
            )

            continue


        soup = BeautifulSoup(
                html,
                "html.parser"
            )


        for link in soup.find_all(
            "a",
            href=True
        ):

            href = link.get(
                    "href"
                )


            absolute = urljoin(
                    source,
                    href
                )


            text = normalize_text(
                    link.get_text(
                        " ",
                        strip=True
                    )
                )


            combined =
                (
                    text
                    +
                    " "
                    +
                    absolute
                )


            if any(

                keyword in combined

                for keyword in [

                    "スタンプラリー",
                    "Stamp Rally",
                    "stamp rally"

                ]

            ):

                if (
                    absolute.startswith(
                        "https://www.pokemon.co.jp/"
                    )
                    or
                    absolute.startswith(
                        "https://shop.pokemon.co.jp/"
                    )
                ):

                    urls.add(
                        absolute
                    )


    # 已知官方活動頁永遠保留
    urls.add(
        "https://shop.pokemon.co.jp/ja/shop/common/events/202606/000336.html"
    )


    return sorted(
        urls
    )


# =========================================================
# LOAD OLD
# =========================================================

def load_old():

    if not STAMP_FILE.exists():

        return []


    try:

        with open(
            STAMP_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                    file
                )


        return data.get(
            "list",
            []
        )

    except Exception:

        return []


# =========================================================
# MERGE
# =========================================================

def merge_items(old_items, new_items):

    merged = {}

    for item in old_items:

        merged[
            item["id"]
        ] = item


    for item in new_items:

        item_id = item.get(
                "id"
            )

        if not item_id:

            continue


        # 新官方資料優先
        merged[
            item_id
        ] = item


    return list(
        merged.values()
    )


# =========================================================
# HISTORY
# =========================================================

def compare_items(old_items, new_items):

    old_map = {

        item["id"]: item

        for item in old_items

        if item.get("id")

    }


    new_map = {

        item["id"]: item

        for item in new_items

        if item.get("id")

    }


    added = []

    removed = []

    changed = []


    for item_id in new_map:

        if item_id not in old_map:

            added.append(
                item_id
            )

            continue


        if old_map[item_id] != new_map[item_id]:

            changed.append(
                item_id
            )


    for item_id in old_map:

        if item_id not in new_map:

            removed.append(
                item_id
            )


    return (
        added,
        removed,
        changed
    )


# =========================================================
# WRITE
# =========================================================

def write_json(
    path,
    data
):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write(
            "\n"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "========================================"
    )

    print(
        "Pokémon Stamp Rally updater"
    )

    print(
        "========================================"
    )


    old_items = load_old()


    urls = discover_urls()


    print(
        "Discovered URLs:",
        len(urls)
    )


    new_items = []


    for url in urls:

        print(
            "Checking:",
            url
        )


        try:

            items = parse_stamp_page(
                    url
                )

            new_items.extend(
                items
            )

        except Exception as error:

            print(
                "PARSE ERROR:",
                url,
                error
            )


    # -----------------------------------------------------
    # 如果官方網站暫時抓不到，
    # 不覆蓋原有資料
    # -----------------------------------------------------

    if not new_items:

        print(
            "No new official Stamp Rally data."
        )

        print(
            "Keep existing JSON."
        )

        return


    merged = merge_items(
            old_items,
            new_items
        )


    merged.sort(

        key=lambda item:
            (
                item.get(
                    "startDate",
                    ""
                ),
                item.get(
                    "event",
                    ""
                ),
                item.get(
                    "id",
                    ""
                )
            )

    )


    now = datetime.now(
            timezone.utc
        ).astimezone()


    updated = now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )


    output = {

        "version":
            "2.0",

        "updated":
            updated,

        "source":
            "official",

        "list":
            merged

    }


    added, removed, changed =
        compare_items(
            old_items,
            merged
        )


    write_json(
        STAMP_FILE,
        output
    )


    history = {

        "history": []

    }


    if HISTORY_FILE.exists():

        try:

            with open(
                HISTORY_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                history = json.load(
                        file
                    )

        except Exception:

            history = {
                "history":[]
            }


    history.setdefault(
        "history",
        []
    )


    history["history"].insert(

        0,

        {

            "time":
                updated,

            "event":
                "Automatic official Stamp Rally sync",

            "source":
                "Pokémon Official Website",

            "total":
                len(merged),

            "added":
                added,

            "removed":
                removed,

            "changed":
                changed

        }

    )


    history["history"] =
        history[
            "history"
        ][:100]


    write_json(
        HISTORY_FILE,
        history
    )


    print(
        "========================================"
    )

    print(
        "Updated:",
        len(merged)
    )

    print(
        "Added:",
        len(added)
    )

    print(
        "Removed:",
        len(removed)
    )

    print(
        "Changed:",
        len(changed)
    )

    print(
        "========================================"
    )


if __name__ == "__main__":

    main()
