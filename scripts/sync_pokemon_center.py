#!/usr/bin/env python3

import json
import re
import time
import hashlib
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

from bs4 import BeautifulSoup


OFFICIAL_URL = (
    "https://www.pokemon.co.jp/shop/"
)

DATA_FILE = Path(
    "data/pokemon_center.json"
)

HISTORY_FILE = Path(
    "center_history.json"
)

PREF_NAMES = {
    1: "北海道",
    2: "青森県",
    3: "岩手県",
    4: "宮城県",
    5: "秋田県",
    6: "山形県",
    7: "福島県",
    8: "茨城県",
    9: "栃木県",
    10: "群馬県",
    11: "埼玉県",
    12: "千葉県",
    13: "東京都",
    14: "神奈川県",
    15: "新潟県",
    16: "富山県",
    17: "石川県",
    18: "福井県",
    19: "山梨県",
    20: "長野県",
    21: "岐阜県",
    22: "静岡県",
    23: "愛知県",
    24: "三重県",
    25: "滋賀県",
    26: "京都府",
    27: "大阪府",
    28: "兵庫県",
    29: "奈良県",
    30: "和歌山県",
    31: "鳥取県",
    32: "島根県",
    33: "岡山県",
    34: "広島県",
    35: "山口県",
    36: "徳島県",
    37: "香川県",
    38: "愛媛県",
    39: "高知県",
    40: "福岡県",
    41: "佐賀県",
    42: "長崎県",
    43: "熊本県",
    44: "大分県",
    45: "宮崎県",
    46: "鹿児島県",
    47: "沖縄県",
}

PREF_BY_TEXT = {
    name: code
    for code, name in PREF_NAMES.items()
}


REGION_TO_CODES = {
    "北海道・東北": [1, 2, 3, 4, 5, 6, 7],
    "関東": [8, 9, 10, 11, 12, 13, 14],
    "中部・北陸": [
        15, 16, 17, 18, 19,
        20, 21, 22, 23
    ],
    "関西": [
        24, 25, 26, 27, 28, 29, 30
    ],
    "中国・四国": [
        31, 32, 33, 34, 35,
        36, 37, 38, 39
    ],
    "九州・沖縄": [
        40, 41, 42, 43, 44,
        45, 46, 47
    ],
}


def fetch_text(url, timeout=30):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Pok-Lids-Pokemon-Center-Sync/1.0 "
                "(GitHub Actions)"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace"
        )


def normalize_space(text):

    return re.sub(
        r"\s+",
        " ",
        unescape(text or "")
    ).strip()


def make_id(url, name, address):

    if url:

        path = (
            urllib.parse.urlparse(url)
            .path
            .strip("/")
        )

        if path:
            slug = re.sub(
                r"[^a-zA-Z0-9]+",
                "-",
                path
            ).strip("-").lower()

            if slug:
                return (
                    "pokemon-center-" +
                    slug
                )

    raw = (
        name +
        "|" +
        address
    ).encode(
        "utf-8"
    )

    digest = hashlib.sha1(
        raw
    ).hexdigest()[:12]

    return (
        "pokemon-center-" +
        digest
    )


def extract_pref(
    address,
    name,
    region
):

    address =
        normalize_space(address)

    name =
        normalize_space(name)

    for code, pref in PREF_NAMES.items():

        if pref in address:

            return code

    special_rules = [

        ("札幌", 1),
        ("仙台", 4),
        ("盛岡", 3),
        ("秋田", 5),
        ("山形", 6),
        ("福島市", 7),

        ("水戸", 8),
        ("宇都宮", 9),
        ("前橋", 10),
        ("さいたま", 11),
        ("千葉市", 12),
        ("船橋", 12),
        ("日本橋", 13),
        ("渋谷", 13),
        ("池袋", 13),
        ("押上", 13),
        ("横浜", 14),

        ("新潟", 15),
        ("富山", 16),
        ("金沢", 17),
        ("福井", 18),
        ("甲府", 19),
        ("長野", 20),
        ("岐阜", 21),
        ("静岡", 22),
        ("名古屋", 23),

        ("津市", 24),
        ("大津", 25),
        ("京都", 26),
        ("大阪", 27),
        ("神戸", 28),
        ("奈良", 29),
        ("和歌山", 30),

        ("鳥取", 31),
        ("松江", 32),
        ("岡山", 33),
        ("広島", 34),
        ("山口", 35),

        ("徳島", 36),
        ("高松", 37),
        ("松山", 38),
        ("高知", 39),

        ("福岡", 40),
        ("佐賀", 41),
        ("長崎", 42),
        ("熊本", 43),
        ("大分", 44),
        ("宮崎", 45),
        ("鹿児島", 46),
        ("沖縄", 47),
        ("北中城", 47),
    ]

    combined = (
        name +
        " " +
        address
    )

    for keyword, code in special_rules:

        if keyword in combined:

            return code

    codes = REGION_TO_CODES.get(
        region,
        []
    )

    if len(codes) == 1:

        return codes[0]

    return None


def extract_address(text):

    text =
        normalize_space(text)

    patterns = [

        r"所在地(.+?)(?:詳細はこちら|$)",

        r"Address(.+?)(?:Learn More|$)",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            return normalize_space(
                match.group(1)
            )

    return ""


def extract_image(detail_url):

    if not detail_url:

        return ""

    try:

        html =
            fetch_text(
                detail_url
            )

        soup =
            BeautifulSoup(
                html,
                "html.parser"
            )

        meta =
            soup.find(
                "meta",
                attrs={
                    "property":
                        "og:image"
                }
            )

        if meta:

            image =
                meta.get("content")

            if image:

                return image.strip()

    except Exception as exc:

        print(
            "詳細頁圖片取得失敗:",
            detail_url,
            exc
        )

    return ""


def geocode(
    address
):

    if not address:

        return None

    query =
        address

    url = (
        "https://nominatim.openstreetmap.org/search"
        "?format=jsonv2"
        "&limit=1"
        "&countrycodes=jp"
        "&q="
        +
        urllib.parse.quote(
            query
        )
    )

    try:

        request =
            urllib.request.Request(

                url,

                headers={
                    "User-Agent":
                        "Pok-Lids-Pokemon-Center-Sync/1.0 "
                        "(GitHub Actions)"
                }

            )


        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            rows =
                json.load(
                    response
                )


        if rows:

            return [
                float(rows[0]["lat"]),
                float(rows[0]["lon"])
            ]

    except Exception as exc:

        print(
            "Geocoding failed:",
            address,
            exc
        )

    return None


def load_existing():

    if not DATA_FILE.exists():

        return {}

    try:

        data =
            json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

        return {
            str(item["id"]):
                item
            for item
            in data.get(
                "list",
                []
            )
            if item.get("id")
        }

    except Exception:

        return {}


def load_history():

    if not HISTORY_FILE.exists():

        return {
            "last_sync": None,
            "history": []
        }

    try:

        return json.loads(
            HISTORY_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return {
            "last_sync": None,
            "history": []
        }


def get_anchor_region(
    anchor
):

    current = anchor

    for _ in range(6):

        if not current:
            break

        text =
            normalize_space(
                current.get_text(
                    " ",
                    strip=True
                )
            )

        for region in REGION_TO_CODES:

            if region in text:

                return region

        current =
            current.parent

    return ""


def is_center_name(
    name
):

    normalized =
        name.lower()

    if "ポケモンセンター" in name:

        return True

    if "pokemon center" in normalized:

        return True

    return False


def scrape_official():

    html =
        fetch_text(
            OFFICIAL_URL
        )

    soup =
        BeautifulSoup(
            html,
            "html.parser"
        )

    results = {}
    current_region = ""

    for heading in soup.find_all(
        ["h2", "h3"]
    ):

        heading_text =
            normalize_space(
                heading.get_text(
                    " ",
                    strip=True
                )
            )

        for region in REGION_TO_CODES:

            if region in heading_text:

                current_region =
                    region

                break

    for anchor in soup.find_all(
        "a"
    ):

        href =
            anchor.get(
                "href",
                ""
            )

        if "shop.pokemon.co.jp" not in href:

            continue

        if href.startswith("/"):

            href =
                urllib.parse.urljoin(
                    OFFICIAL_URL,
                    href
                )

        name =
            normalize_space(
                anchor.get_text(
                    " ",
                    strip=True
                )
            )

        if not name:

            continue

        if not is_center_name(
            name
        ):

            continue

        if "ストア" in name:
            continue

        if "カフェ" in name:
            continue

        if "cafe" in name.lower():
            continue

        parent =
            anchor.parent

        block_text =
            normalize_space(
                parent.get_text(
                    " ",
                    strip=True
                )
            )

        if len(block_text) < len(name):

            block_text =
                normalize_space(
                    anchor.parent.parent
                    .get_text(
                        " ",
                        strip=True
                    )
                )

        address =
            extract_address(
                block_text
            )

        if not address:

            address =
                block_text

        region =
            get_anchor_region(
                anchor
            ) or current_region

        pref =
            extract_pref(
                address,
                name,
                region
            )

        detail_url =
            href

        item_id =
            make_id(
                detail_url,
                name,
                address
            )

        results[item_id] = {

            "id":
                item_id,

            "type":
                "pokemon_center",

            "pref":
                pref,

            "region":
                region,

            "name":
                name,

            "city":
                "",

            "address":
                address,

            "coords":
                None,

            "image":
                "",

            "source":
                OFFICIAL_URL,

            "official_url":
                detail_url

        }

    return list(
        results.values()
    )


def main():

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    old_map =
        load_existing()


    scraped =
        scrape_official()


    print(
        "官方頁面抓到：",
        len(scraped),
        "筆"
    )


    new_map = {}


    for item in scraped:

        item_id =
            item["id"]


        old =
            old_map.get(
                item_id
            )


        if old:

            item["coords"] =
                old.get(
                    "coords"
                )

            item["image"] =
                old.get(
                    "image",
                    ""
                )


        if not item.get(
            "image"
        ):

            item["image"] =
                extract_image(
                    item["official_url"]
                )


        address_changed = (

            not old

            or

            old.get(
                "address"
            ) !=
            item.get(
                "address"
            )

        )


        if (
            not item.get("coords")
            or
            address_changed
        ):

            print(
                "Geocoding:",
                item["name"]
            )


            coords =
                geocode(
                    item["address"]
                )


            if coords:

                item["coords"] =
                    coords


            # Nominatim 公開服務的保守使用頻率
            time.sleep(
                1.1
            )


        new_map[item_id] =
            item


    added_ids =
        set(new_map) -
        set(old_map)

    removed_ids =
        set(old_map) -
        set(new_map)

    changed_ids = set()


    for item_id in (
        set(new_map) &
        set(old_map)
    ):

        old =
            old_map[item_id]

        new =
            new_map[item_id]

        compare_fields = [

            "pref",
            "region",
            "name",
            "address",
            "coords",
            "image"

        ]

        if any(

            old.get(field)
            !=
            new.get(field)

            for field
            in compare_fields

        ):

            changed_ids.add(
                item_id
            )


    def simplify(item):

        return {

            "id":
                item.get(
                    "id",
                    ""
                ),

            "prefecture":
                item.get(
                    "pref",
                    ""
                ),

            "title":
                item.get(
                    "name",
                    ""
                ),

            "lat":
                (
                    item.get(
                        "coords"
                    )[0]
                    if item.get(
                        "coords"
                    )
                    else ""
                ),

            "lng":
                (
                    item.get(
                        "coords"
                    )[1]
                    if item.get(
                        "coords"
                    )
                    else ""
                ),

            "address":
                item.get(
                    "address",
                    ""
                )

        }


    added = [

        simplify(
            new_map[item_id]
        )

        for item_id
        in sorted(
            added_ids
        )

    ]


    removed = [

        simplify(
            old_map[item_id]
        )

        for item_id
        in sorted(
            removed_ids
        )

    ]


    changed = [

        simplify(
            new_map[item_id]
        )

        for item_id
        in sorted(
            changed_ids
        )

    ]


    now =
        datetime.now(
            timezone.utc
        ).astimezone().isoformat(
            timespec="seconds"
        )


    history =
        load_history()


    has_change = (

        bool(added)
        or
        bool(removed)
        or
        bool(changed)

    )


    if has_change:

        history.setdefault(
            "history",
            []
        )

        history["history"].append({

            "time":
                now,

            "type":
                "center",

            "total":
                len(new_map),

            "added":
                added,

            "removed":
                removed,

            "changed":
                changed

        })

        history["history"] =
            history["history"][
                -200:
            ]


    history["last_sync"] =
        now

    history["total"] =
        len(new_map)


    ordered =
        sorted(

            new_map.values(),

            key=lambda x: (

                x.get(
                    "pref"
                )
                or
                999,

                x.get(
                    "name",
                    ""
                )

            )

        )


    DATA_FILE.write_text(

        json.dumps(

            {
                "list":
                    ordered
            },

            ensure_ascii=False,

            indent=2

        ),

        encoding="utf-8"

    )


    HISTORY_FILE.write_text(

        json.dumps(

            history,

            ensure_ascii=False,

            indent=2

        ),

        encoding="utf-8"

    )


    print(
        "Pokémon Center 更新完成"
    )

    print(
        "目前：",
        len(ordered),
        "筆"
    )

    print(
        "新增：",
        len(added)
    )

    print(
        "移除：",
        len(removed)
    )

    print(
        "修改：",
        len(changed)
    )


if __name__ == "__main__":

    import urllib.parse

    main()
