#!/usr/bin/env python3

import hashlib
import json
import re
import urllib.parse
import urllib.request

from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup


# =========================================================
# Settings
# =========================================================

SITEMAP_URL = "https://shop.pokemon.co.jp/en/sitemap/"

DATA_FILE = Path(
    "data/pokemon_center.json"
)

HISTORY_FILE = Path(
    "center_history.json"
)


# =========================================================
# Prefecture
# =========================================================

PREF = {
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
# English Prefecture
# =========================================================

EN_PREF = {
    "hokkaido": 1,
    "aomori": 2,
    "iwate": 3,
    "miyagi": 4,
    "akita": 5,
    "yamagata": 6,
    "fukushima": 7,
    "ibaraki": 8,
    "tochigi": 9,
    "gunma": 10,
    "saitama": 11,
    "chiba": 12,
    "tokyo": 13,
    "kanagawa": 14,
    "niigata": 15,
    "toyama": 16,
    "ishikawa": 17,
    "fukui": 18,
    "yamanashi": 19,
    "nagano": 20,
    "gifu": 21,
    "shizuoka": 22,
    "aichi": 23,
    "mie": 24,
    "shiga": 25,
    "kyoto": 26,
    "osaka": 27,
    "hyogo": 28,
    "nara": 29,
    "wakayama": 30,
    "tottori": 31,
    "shimane": 32,
    "okayama": 33,
    "hiroshima": 34,
    "yamaguchi": 35,
    "tokushima": 36,
    "kagawa": 37,
    "ehime": 38,
    "kochi": 39,
    "fukuoka": 40,
    "saga": 41,
    "nagasaki": 42,
    "kumamoto": 43,
    "oita": 44,
    "miyazaki": 45,
    "kagoshima": 46,
    "okinawa": 47,
}


# =========================================================
# HTTP
# =========================================================

def fetch_text(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; PokLidsCenterSync/1.0)"
            ),
            "Accept-Language": (
                "en-US,en;q=0.9,"
                "ja;q=0.8"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=40,
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace",
        )


# =========================================================
# Text
# =========================================================

def clean(text):

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(text),
    ).strip()


# =========================================================
# Is Center
# =========================================================

def is_pokemon_center(name):

    text = clean(
        name
    ).lower()


    return (

        "pokemon center" in text
        or
        "pokémon center" in text
        or
        "ポケモンセンター" in name

    )


# =========================================================
# Exclude Store / Cafe
# =========================================================

def is_excluded(name):

    text = clean(
        name
    ).lower()


    excluded = [

        "pokemon store",
        "pokémon store",
        "pokemon cafe",
        "pokémon cafe",
        "pikachu sweets",
        "store",
        "cafe",

    ]


    for word in excluded:

        if word in text:

            return True


    if "ストア" in name:
        return True


    if "カフェ" in name:
        return True


    return False


# =========================================================
# ID
# =========================================================

def make_id(
    name,
    url,
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
                path,
            ).strip(
                "-"
            ).lower()


        if slug:

            return (
                "pokemon-center-"
                + slug
            )


    raw = (
        clean(name)
        + "|"
        + clean(url)
    ).encode(
        "utf-8"
    )


    return (
        "pokemon-center-"
        +
        hashlib.sha1(
            raw
        ).hexdigest()[:12]
    )


# =========================================================
# Prefecture Detection
# =========================================================

def detect_prefecture(
    text,
):

    text =
        clean(text)


    # Japanese
    for code, name in PREF.items():

        if name in text:

            return code


    # English
    lower =
        text.lower()


    for keyword, code in EN_PREF.items():

        if keyword in lower:

            return code


    # City fallback
    city_rules = [

        ("札幌", 1),
        ("仙台", 4),
        ("盛岡", 3),
        ("秋田", 5),
        ("山形", 6),

        ("福島", 7),

        ("水戸", 8),
        ("宇都宮", 9),
        ("前橋", 10),
        ("さいたま", 11),
        ("千葉", 12),

        ("東京", 13),
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
    ]


    for keyword, code in city_rules:

        if keyword in text:

            return code


    return None


# =========================================================
# JSON-LD
# =========================================================

def extract_jsonld(
    soup,
):

    output = []


    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):

        raw =
            script.string or \
            script.get_text()


        raw =
            raw.strip()


        if not raw:

            continue


        try:

            obj =
                json.loads(
                    raw
                )

        except Exception:

            continue


        if isinstance(
            obj,
            list,
        ):

            output.extend(
                obj
            )

        else:

            output.append(
                obj
            )


    return output


# =========================================================
# Name
# =========================================================

def extract_name(
    soup,
):

    h1 =
        soup.find(
            "h1"
        )


    if h1:

        value =
            clean(
                h1.get_text(
                    " ",
                    strip=True
                )
            )


        if value:

            return value


    title =
        soup.find(
            "title"
        )


    if title:

        value =
            clean(
                title.get_text(
                    " ",
                    strip=True
                )
            )


        if value:

            return value


    return ""


# =========================================================
# Address
# =========================================================

def extract_address(
    soup,
):

    jsonld =
        extract_jsonld(
            soup
        )


    for obj in jsonld:

        if not isinstance(
            obj,
            dict,
        ):

            continue


        address =
            obj.get(
                "address"
            )


        if isinstance(
            address,
            dict,
        ):

            parts = [

                address.get(
                    "postalCode",
                    "",
                ),

                address.get(
                    "addressRegion",
                    "",
                ),

                address.get(
                    "addressLocality",
                    "",
                ),

                address.get(
                    "streetAddress",
                    "",
                ),

            ]


            result =
                clean(
                    " ".join(
                        part
                        for part
                        in parts
                        if part
                    )
                )


            if result:

                return result


        elif isinstance(
            address,
            str,
        ):

            result =
                clean(
                    address
                )


            if result:

                return result


    text =
        clean(
            soup.get_text(
                " ",
                strip=True,
            )
        )


    patterns = [

        r"Location\s+(.{5,350}?)"
        r"(?:Google Maps|Opening Hours|Business Hours)",

        r"所在地\s+(.{5,350}?)"
        r"(?:Google Maps|営業時間|アクセス)",

    ]


    for pattern in patterns:

        match =
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )


        if match:

            result =
                clean(
                    match.group(1)
                )


            if result:

                return result


    return ""


# =========================================================
# Image
# =========================================================

def extract_image(
    soup,
    page_url,
):

    meta =
        soup.find(
            "meta",
            attrs={
                "property":
                    "og:image"
            },
        )


    if meta:

        image =
            clean(
                meta.get(
                    "content",
                    "",
                )
            )


        if image:

            return urllib.parse.urljoin(
                page_url,
                image,
            )


    for obj in extract_jsonld(
        soup
    ):

        if not isinstance(
            obj,
            dict,
        ):

            continue


        image =
            obj.get(
                "image",
                "",
            )


        if isinstance(
            image,
            list,
        ):

            image =
                image[0] \
                if image \
                else ""


        if image:

            return urllib.parse.urljoin(
                page_url,
                str(image).strip(),
            )


    return ""


# =========================================================
# Google Coordinates
# =========================================================

def parse_google_coords(
    text,
):

    if not text:

        return None


    decoded =
        urllib.parse.unquote(
            text
        )


    # !2d longitude + !3d latitude

    match =
        re.search(
            r"!2d(-?\d+(?:\.\d+)?).*?"
            r"!3d(-?\d+(?:\.\d+)?)",
            decoded,
        )


    if match:

        try:

            lng =
                float(
                    match.group(1)
                )

            lat =
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
                    lng,
                ]

        except ValueError:

            pass


    # @latitude,longitude

    match =
        re.search(
            r"@(-?\d+(?:\.\d+)?),"
            r"(-?\d+(?:\.\d+)?)",
            decoded,
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
                    lng,
                ]

        except ValueError:

            pass


    return None


def extract_coordinates(
    soup,
):

    # JSON-LD
    for obj in extract_jsonld(
        soup
    ):

        if not isinstance(
            obj,
            dict,
        ):

            continue


        geo =
            obj.get(
                "geo"
            )


        if isinstance(
            geo,
            dict,
        ):

            try:

                lat =
                    float(
                        geo.get(
                            "latitude"
                        )
                    )

                lng =
                    float(
                        geo.get(
                            "longitude"
                        )
                    )


                if (
                    20 <= lat <= 50
                    and
                    120 <= lng <= 150
                ):

                    return [
                        lat,
                        lng,
                    ]

            except (
                TypeError,
                ValueError,
            ):

                pass


    # Google links
    for a in soup.find_all(
        "a",
        href=True,
    ):

        href =
            a.get(
                "href",
                "",
            )


        if (
            "google.com/maps"
            not in href
            and
            "google.co.jp/maps"
            not in href
        ):

            continue


        coords =
            parse_google_coords(
                href
            )


        if coords:

            return coords


    # iframe
    for iframe in soup.find_all(
        "iframe",
        src=True,
    ):

        src =
            iframe.get(
                "src",
                "",
            )


        if (
            "google.com/maps"
            not in src
        ):

            continue


        coords =
            parse_google_coords(
                src
            )


        if coords:

            return coords


    # Raw HTML
    return parse_google_coords(
        str(soup)
    )


# =========================================================
# Find Region
# =========================================================

def find_region(
    anchor,
):

    node =
        anchor


    for _ in range(8):

        if not node:

            break


        text =
            clean(
                node.get_text(
                    " ",
                    strip=True,
                )
            )


        lower =
            text.lower()


        if (
            "hokkaido" in lower
            and
            "tohoku" in lower
        ):

            return "北海道・東北"


        if "kanto" in lower:

            return "關東"


        if (
            "chubu" in lower
            and
            "hokuriku" in lower
        ):

            return "中部・北陸"


        if "kansai" in lower:

            return "關西"


        if (
            "chugoku" in lower
            and
            "shikoku" in lower
        ):

            return "中國・四國"


        if (
            "kyushu" in lower
            and
            "okinawa" in lower
        ):

            return "九州・沖繩"


        node =
            node.parent


    return ""


# =========================================================
# Discover
# =========================================================

def discover():

    html =
        fetch_text(
            SITEMAP_URL
        )


    soup =
        BeautifulSoup(
            html,
            "html.parser",
        )


    shops = []
    seen = set()


    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        name =
            clean(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            )


        href =
            urllib.parse.urljoin(
                SITEMAP_URL,
                anchor["href"],
            )


        if not is_pokemon_center(
            name
        ):

            continue


        if is_excluded(
            name
        ):

            continue


        if (
            "/en/shop/"
            not in href
        ):

            continue


        # Exclude international centers
        upper =
            name.upper()


        if (
            "TAIPEI" in upper
            or
            "SINGAPORE" in upper
        ):

            continue


        if href in seen:

            continue


        seen.add(
            href
        )


        shops.append({

            "name":
                name,

            "url":
                href,

            "region":
                find_region(
                    anchor
                ),

        })


    return shops


# =========================================================
# Existing
# =========================================================

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

            if item.get(
                "id"
            )

        }

    except Exception:

        return {}


# =========================================================
# History
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

def summarize(
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
                "pref"
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
            ),

    }


# =========================================================
# MAIN
# =========================================================

def main():

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    old =
        load_existing()


    shops =
        discover()


    print(
        "======================================"
    )

    print(
        "官方 Pokémon Center Sitemap"
    )

    print(
        "找到店舖頁：",
        len(shops)
    )

    print(
        "======================================"
    )


    if not shops:

        raise RuntimeError(
            "沒有找到任何 Pokémon Center。"
        )


    new = {}
    failed = 0


    for index, shop in enumerate(
        shops,
        1,
    ):

        url =
            shop["url"]


        try:

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
                extract_name(
                    soup
                )


            if not name:

                name =
                    shop["name"]


            if not is_pokemon_center(
                name
            ):

                print(
                    "SKIP:",
                    shop["name"]
                )

                continue


            if is_excluded(
                name
            ):

                print(
                    "SKIP EXCLUDED:",
                    name
                )

                continue


            address =
                extract_address(
                    soup
                )


            image =
                extract_image(
                    soup,
                    url
                )


            coords =
                extract_coordinates(
                    soup
                )


            pref =
                detect_prefecture(
                    name
                    + " "
                    + address
            )


            item_id =
                make_id(
                    name,
                    url
                )


            old_item =
                old.get(
                    item_id
                )


            # Preserve old values
            # when the official page
            # temporarily omits something.

            if old_item:

                if not coords:

                    coords =
                        old_item.get(
                            "coords"
                        )


                if not image:

                    image =
                        old_item.get(
                            "image",
                            ""
                        )


                if not address:

                    address =
                        old_item.get(
                            "address",
                            ""
                        )


                if pref is None:

                    pref =
                        old_item.get(
                            "pref"
                        )


            item = {

                "id":
                    item_id,

                "type":
                    "pokemon_center",

                "pref":
                    pref,

                "region":
                    shop.get(
                        "region",
                        ""
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
                    SITEMAP_URL,

            }


            new[item_id] =
                item


            print(
                f"[{index}/{len(shops)}] "
                f"OK: {name}"
            )


            print(
                "   pref:",
                pref,
            )


            print(
                "   coords:",
                coords,
            )


        except Exception as exc:

            failed += 1


            print(
                f"[{index}/{len(shops)}] "
                f"FAILED: {url}"
            )


            print(
                "   ",
                repr(exc)
            )


    print("")
    print(
        "成功：",
        len(new)
    )

    print(
        "失敗：",
        failed
    )


    # =====================================================
    # Safety
    # =====================================================

    if not new:

        raise RuntimeError(
            "同步結果為 0 筆，"
            "拒絕覆蓋現有資料。"
        )


    # =====================================================
    # Compare
    # =====================================================

    added_ids =
        set(new) - set(old)


    removed_ids =
        set(old) - set(new)


    changed_ids =
        []


    compare_fields = [

        "pref",
        "region",
        "name",
        "address",
        "coords",
        "image",

    ]


    for item_id in (
        set(new) & set(old)
    ):

        before =
            old[item_id]


        after =
            new[item_id]


        for field in compare_fields:

            if (
                before.get(field)
                !=
                after.get(field)
            ):

                changed_ids.append(
                    item_id
                )

                break


    # =====================================================
    # History
    # =====================================================

    history =
        load_history()


    now =
        datetime.now(
            timezone.utc
        ).astimezone().isoformat(
            timespec="seconds"
        )


    if (
        added_ids
        or
        removed_ids
        or
        changed_ids
    ):

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
                len(new),

            "added":
                [
                    summarize(
                        new[x]
                    )
                    for x
                    in sorted(
                        added_ids
                    )
                ],

            "removed":
                [
                    summarize(
                        old[x]
                    )
                    for x
                    in sorted(
                        removed_ids
                    )
                ],

            "changed":
                [
                    summarize(
                        new[x]
                    )
                    for x
                    in sorted(
                        changed_ids
                    )
                ],

        })


        history["history"] =
            history["history"][
                -200:
            ]


    history["last_sync"] =
        now


    history["total"] =
        len(new)


    # =====================================================
    # Save
    # =====================================================

    ordered =
        sorted(

            new.values(),

            key=lambda item: (

                (
                    item.get(
                        "pref"
                    )
                    if
                    item.get(
                        "pref"
                    ) is not None
                    else
                    999
                ),

                item.get(
                    "name",
                    ""
                ),

            )

        )


    DATA_FILE.write_text(

        json.dumps(

            {
                "list":
                    ordered
            },

            ensure_ascii=False,

            indent=2,

        ),

        encoding="utf-8",

    )


    HISTORY_FILE.write_text(

        json.dumps(

            history,

            ensure_ascii=False,

            indent=2,

        ),

        encoding="utf-8",

    )


    print("")
    print(
        "======================================"
    )
    print(
        " Pokémon Center Sync 完成"
    )
    print(
        "目前：",
        len(ordered),
        "筆"
    )
    print(
        "新增：",
        len(added_ids)
    )
    print(
        "移除：",
        len(removed_ids)
    )
    print(
        "修改：",
        len(changed_ids)
    )
    print(
        "失敗：",
        failed
    )
    print(
        "======================================"
    )


if __name__ == "__main__":

    main()
