#!/usr/bin/env python3

import json
import re
import hashlib
import urllib.request
import urllib.parse

from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup


# =========================================================
# Settings
# =========================================================

SITEMAP_URL = (
    "https://shop.pokemon.co.jp/en/sitemap/"
)

DATA_FILE = Path(
    "data/pokemon_center.json"
)

HISTORY_FILE = Path(
    "center_history.json"
)


# =========================================================
# Prefecture
# =========================================================

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


# =========================================================
# Region
# =========================================================

REGIONS = {

    "北海道・東北": [1, 2, 3, 4, 5, 6, 7],

    "関東": [
        8, 9, 10, 11,
        12, 13, 14
    ],

    "中部・北陸": [
        15, 16, 17, 18,
        19, 20, 21, 22,
        23
    ],

    "関西": [
        24, 25, 26, 27,
        28, 29, 30
    ],

    "中国・四国": [
        31, 32, 33, 34,
        35, 36, 37, 38,
        39
    ],

    "九州・沖縄": [
        40, 41, 42, 43,
        44, 45, 46, 47
    ],
}


# =========================================================
# HTTP
# =========================================================

def fetch_text(url):

    request = urllib.request.Request(

        url,

        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "(compatible; Pok-Lids-Center-Sync/1.0)",
            "Accept-Language":
                "en-US,en;q=0.9"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=40
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace"
        )


# =========================================================
# Normalize
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# Region Detection
# =========================================================

def get_region_from_heading(
    heading
):

    text =
        clean_text(
            heading.get_text(
                " ",
                strip=True
            )
        )

    for region in REGIONS:

        if region.lower() in text.lower():

            return region

    return None


# =========================================================
# Prefecture Detection
# =========================================================

def detect_prefecture(
    address,
    name
):

    text = (
        clean_text(address)
        + " "
        + clean_text(name)
    )

    # 直接比對日本都道府縣名稱
    for code, pref in PREF_NAMES.items():

        if pref in text:

            return code

    # English fallback
    english = text.lower()

    rules = [

        ("hokkaido", 1),

        ("aomori", 2),
        ("iwate", 3),
        ("miyagi", 4),
        ("akita", 5),
        ("yamagata", 6),
        ("fukushima", 7),

        ("ibaraki", 8),
        ("tochigi", 9),
        ("gunma", 10),
        ("saitama", 11),
        ("chiba", 12),
        ("tokyo", 13),
        ("kanagawa", 14),

        ("niigata", 15),
        ("toyama", 16),
        ("ishikawa", 17),
        ("fukui", 18),
        ("yamanashi", 19),
        ("nagano", 20),
        ("gifu", 21),
        ("shizuoka", 22),
        ("aichi", 23),

        ("mie", 24),
        ("shiga", 25),
        ("kyoto", 26),
        ("osaka", 27),
        ("hyogo", 28),
        ("nara", 29),
        ("wakayama", 30),

        ("tottori", 31),
        ("shimane", 32),
        ("okayama", 33),
        ("hiroshima", 34),
        ("yamaguchi", 35),

        ("tokushima", 36),
        ("kagawa", 37),
        ("ehime", 38),
        ("kochi", 39),

        ("fukuoka", 40),
        ("saga", 41),
        ("nagasaki", 42),
        ("kumamoto", 43),
        ("oita", 44),
        ("miyazaki", 45),
        ("kagoshima", 46),
        ("okinawa", 47),

    ]

    for keyword, code in rules:

        if keyword in english:

            return code

    return None


# =========================================================
# Extract JSON-LD
# =========================================================

def extract_json_ld(
    soup
):

    output = []

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        raw =
            script.string or \
            script.get_text()

        if not raw:
            continue

        try:

            data =
                json.loads(raw)

            if isinstance(
                data,
                list
            ):

                output.extend(
                    data
                )

            else:

                output.append(
                    data
                )

        except Exception:

            continue

    return output


# =========================================================
# Extract Address
# =========================================================

def extract_address(
    soup
):

    # -----------------------------------------------------
    # 1. JSON-LD
    # -----------------------------------------------------

    json_ld =
        extract_json_ld(
            soup
        )

    for obj in json_ld:

        address =
            obj.get(
                "address"
            ) \
            if isinstance(
                obj,
                dict
            ) \
            else None

        if isinstance(
            address,
            dict
        ):

            parts = [

                address.get(
                    "postalCode",
                    ""
                ),

                address.get(
                    "streetAddress",
                    ""
                ),

                address.get(
                    "addressLocality",
                    ""
                ),

                address.get(
                    "addressRegion",
                    ""
                )

            ]

            result =
                clean_text(
                    " ".join(
                        p
                        for p
                        in parts
                        if p
                    )
                )

            if result:

                return result

        elif isinstance(
            address,
            str
        ):

            result =
                clean_text(
                    address
                )

            if result:

                return result

    # -----------------------------------------------------
    # 2. Shop Information text
    # -----------------------------------------------------

    text =
        clean_text(
            soup.get_text(
                " ",
                strip=True
            )
        )

    patterns = [

        r"Location\s+(.+?)"
        r"\s+\d{3}-\d{4}",

        r"Location\s+(.+?)"
        r"\s+Google Maps",

        r"所在地\s+(.+?)"
        r"\s+Google Maps",

    ]

    for pattern in patterns:

        match =
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            )

        if match:

            result =
                clean_text(
                    match.group(1)
                )

            if result:

                return result

    return ""


# =========================================================
# Extract Image
# =========================================================

def extract_image(
    soup
):

    meta =
        soup.find(
            "meta",
            attrs={
                "property":
                    "og:image"
            }
        )

    if meta:

        url =
            meta.get(
                "content"
            )

        if url:

            return urllib.parse.urljoin(
                SITEMAP_URL,
                url.strip()
            )

    return ""


# =========================================================
# Extract Google Maps Coordinates
# =========================================================

def extract_google_coords(
    soup
):

    # -----------------------------------------------------
    # Look for Google Maps links
    # -----------------------------------------------------

    for a in soup.find_all(
        "a",
        href=True
    ):

        href =
            a.get(
                "href",
                ""
            )

        if (
            "google.com/maps" not in
            href
            and
            "google.co.jp/maps" not in
            href
        ):

            continue

        coords =
            parse_google_url(
                href
            )

        if coords:

            return coords


    # -----------------------------------------------------
    # Look for iframe src
    # -----------------------------------------------------

    for iframe in soup.find_all(
        "iframe",
        src=True
    ):

        src =
            iframe.get(
                "src",
                ""
            )

        if "google.com/maps" not in src:

            continue

        coords =
            parse_google_url(
                src
            )

        if coords:

            return coords


    # -----------------------------------------------------
    # Search raw HTML
    # -----------------------------------------------------

    html =
        str(soup)


    coords =
        parse_google_url(
            html
        )


    return coords


# =========================================================
# Parse Google Map Embed URL
# =========================================================

def parse_google_url(
    text
):

    if not text:

        return None

    decoded =
        urllib.parse.unquote(
            text
        )


    # Google embed often has:
    #
    # !2d139.7742695
    # !3d35.6802902

    lng_match =
        re.search(
            r"!2d(-?\d+\.\d+)",
            decoded
        )


    lat_match =
        re.search(
            r"!3d(-?\d+\.\d+)",
            decoded
        )


    if (
        lat_match and
        lng_match
    ):

        try:

            lat =
                float(
                    lat_match.group(1)
                )

            lng =
                float(
                    lng_match.group(1)
                )

            if (
                20 <= lat <= 50
                and
                120 <= lng <= 150
            ):

                return [
                    lat,
                    lng
                ]

        except ValueError:

            pass


    # Another common format:
    #
    # @35.6802902,139.7742695

    match =
        re.search(
            r"@(-?\d+\.\d+),(-?\d+\.\d+)",
            decoded
        )


    if match:

        try:

            lat =
                float(
                    match.group(1)
                )

            lng =
                float(
                    match.group(2)
                )

            if (
                20 <= lat <= 50
                and
                120 <= lng <= 150
            ):

                return [
                    lat,
                    lng
                ]

        except ValueError:

            pass


    return None


# =========================================================
# Extract Shop Name
# =========================================================

def extract_shop_name(
    soup
):

    h1 =
        soup.find(
            "h1"
        )

    if h1:

        text =
            clean_text(
                h1.get_text(
                    " ",
                    strip=True
                )
            )

        if text:

            return text

    title =
        soup.title

    if title:

        return clean_text(
            title.get_text(
                " ",
                strip=True
            )
        )

    return ""


# =========================================================
# Is Pokémon Center
# =========================================================

def is_pokemon_center(
    name
):

    name_lower =
        name.lower()

    return (

        "pokémon center"
        in
        name_lower

        or

        "pokemon center"
        in
        name_lower

        or

        "ポケモンセンター"
        in
        name

    )


# =========================================================
# Stable ID
# =========================================================

def make_id(
    url,
    name
):

    parsed =
        urllib.parse.urlparse(
            url
        )

    path =
        parsed.path.strip(
            "/"
        )

    if path:

        slug =
            re.sub(
                r"[^a-zA-Z0-9]+",
                "-",
                path
            ) \
            .strip(
                "-"
            ) \
            .lower()

        if slug:

            return (
                "pokemon-center-" +
                slug
            )

    raw =
        (
            name +
            "|" +
            url
        ).encode(
            "utf-8"
        )

    digest =
        hashlib.sha1(
            raw
        ).hexdigest()[:12]

    return (
        "pokemon-center-" +
        digest
    )


# =========================================================
# Discover Shops From Sitemap
# =========================================================

def discover_shops():

    print(
        "讀取官方 Sitemap..."
    )


    html =
        fetch_text(
            SITEMAP_URL
        )


    soup =
        BeautifulSoup(
            html,
            "html.parser"
        )


    shops = []

    current_region =
        None


    # sitemap has h3 region headings
    for element in soup.find_all(
        ["h3", "a"]
    ):

        if element.name == "h3":

            region =
                get_region_from_heading(
                    element
                )

            if region:

                current_region =
                    region

            continue


        name =
            clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )


        href =
            element.get(
                "href",
                ""
            )


        if not name or not href:

            continue


        if not is_pokemon_center(
            name
        ):

            continue


        # Exclude Store / Cafe explicitly

        name_lower =
            name.lower()


        if (
            "store"
            in
            name_lower
            or
            "cafe"
            in
            name_lower
            or
            "ストア"
            in
            name
            or
            "カフェ"
            in
            name
        ):

            continue


        href =
            urllib.parse.urljoin(
                SITEMAP_URL,
                href
            )


        # International should not enter
        # Japan collection

        if (
            "taipei"
            in
            name_lower
            or
            "singapore"
            in
            name_lower
        ):

            continue


        item = {

            "name":
                name,

            "url":
                href,

            "region":
                current_region

        }


        # Avoid duplicates

        if not any(

            s["url"] ==
            item["url"]

            for s in shops

        ):

            shops.append(
                item
            )


    print(
        "找到 Pokémon Center：",
        len(shops)
    )


    return shops


# =========================================================
# Parse Detail Page
# =========================================================

def parse_shop(
    shop
):

    url =
        shop["url"]

    print(
        "讀取：",
        shop["name"]
    )


    html =
        fetch_text(
            url
        )


    soup =
        BeautifulSoup(
            html,
            "html.parser"
        )


    name =
        extract_shop_name(
            soup
        ) or shop["name"]


    address =
        extract_address(
            soup
        )


    image =
        extract_image(
            soup
        )


    coords =
        extract_google_coords(
            soup
        )


    pref =
        detect_prefecture(
            address,
            name
        )


    item_id =
        make_id(
            url,
            name
        )


    return {

        "id":
            item_id,

        "type":
            "pokemon_center",

        "pref":
            pref,

        "region":
            shop.get(
                "region"
            ),

        "name":
            name,

        "city":
            "",

        "address":
            address,

        "coords":
            coords,

        "image":
            image,

        "official_url":
            url,

        "source":
            "https://shop.pokemon.co.jp/en/sitemap/"

    }


# =========================================================
# Existing Data
# =========================================================

def load_existing():

    if not DATA_FILE.exists():

        return {}


    try:

        json_data =
            json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )


        items =
            json_data.get(
                "list",
                []
            )


        return {

            str(
                item["id"]
            ):
                item

            for item
            in items

            if item.get(
                "id"
            )

        }

    except Exception:

        return {}


# =========================================================
# Existing History
# =========================================================

def load_history():

    if not HISTORY_FILE.exists():

        return {

            "last_sync":
                None,

            "total":
                0,

            "history":
                []

        }


    try:

        return json.loads(
            HISTORY_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return {

            "last_sync":
                None,

            "total":
                0,

            "history":
                []

        }


# =========================================================
# Summary
# =========================================================

def simplify(
    item
):

    coords =
        item.get(
            "coords"
        )


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
                coords[0]
                if
                isinstance(
                    coords,
                    list
                )
                and
                len(coords) >= 2
                else
                ""
            ),

        "lng":
            (
                coords[1]
                if
                isinstance(
                    coords,
                    list
                )
                and
                len(coords) >= 2
                else
                ""
            ),

        "address":
            item.get(
                "address",
                ""
            )

    }


# =========================================================
# MAIN
# =========================================================

def main():

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    old_map =
        load_existing()


    shops =
        discover_shops()


    if not shops:

        raise RuntimeError(
            "官方 Sitemap 沒有找到 Pokémon Center。"
        )


    new_map = {}


    for shop in shops:

        item =
            parse_shop(
                shop
            )


        old =
            old_map.get(
                item["id"]
            )


        # Preserve old data when
        # official page temporarily misses it.

        if old:

            if not item.get(
                "coords"
            ):

                item["coords"] =
                    old.get(
                        "coords"
                    )


            if not item.get(
                "image"
            ):

                item["image"] =
                    old.get(
                        "image",
                        ""
                    )


            if not item.get(
                "address"
            ):

                item["address"] =
                    old.get(
                        "address",
                        ""
                    )


            if not item.get(
                "pref"
            ):

                item["pref"] =
                    old.get(
                        "pref"
                    )


        new_map[
            item["id"]
        ] = item


    # =====================================================
    # Compare
    # =====================================================

    added_ids =
        set(
            new_map
        ) - set(
            old_map
        )


    removed_ids =
        set(
            old_map
        ) - set(
            new_map
        )


    common_ids =
        set(
            new_map
        ) & set(
            old_map
        )


    changed_ids = []


    fields = [

        "pref",
        "region",
        "name",
        "address",
        "coords",
        "image"

    ]


    for item_id in common_ids:

        old =
            old_map[
                item_id
            ]

        new =
            new_map[
                item_id
            ]


        changed = False


        for field in fields:

            if (
                old.get(field)
                !=
                new.get(field)
            ):

                changed = True

                break


        if changed:

            changed_ids.append(
                item_id
            )


    added = [

        simplify(
            new_map[x]
        )

        for x
        in sorted(
            added_ids
        )

    ]


    removed = [

        simplify(
            old_map[x]
        )

        for x
        in sorted(
            removed_ids
        )

    ]


    changed = [

        simplify(
            new_map[x]
        )

        for x
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


    # =====================================================
    # Save Data
    # =====================================================

    ordered =
        sorted(

            new_map.values(),

            key=lambda item: (

                item.get(
                    "pref"
                )
                if
                item.get(
                    "pref"
                )
                is not None

                else
                999,

                item.get(
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


    # =====================================================
    # Output
    # =====================================================

    print("")
    print("======================================")
    print(" Pokémon Center Sync 完成")
    print("======================================")
    print(
        "目前：",
        len(ordered)
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
    print("======================================")


if __name__ == "__main__":

    main()
