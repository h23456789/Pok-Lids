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
# HTTP
# =========================================================

def fetch_text(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; PokemonCenterSync/1.0)"
            ),
            "Accept-Language": (
                "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7"
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
# Text helpers
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(text),
    ).strip()


# =========================================================
# Stable ID
# =========================================================

def make_id(name, url):
    base = (
        clean_text(name)
        + "|"
        + clean_text(url)
    ).encode("utf-8")

    digest = hashlib.sha1(
        base
    ).hexdigest()[:12]

    return (
        "pokemon-center-"
        + digest
    )


# =========================================================
# Is Pokémon Center
# =========================================================

def is_pokemon_center(name):

    text = clean_text(
        name
    ).lower()

    if "pokemon center" in text:
        return True

    if "pokémon center" in text:
        return True

    if "ポケモンセンター" in text:
        return True

    return False


# =========================================================
# Detect Prefecture
# =========================================================

def detect_prefecture(
    text
):

    text = clean_text(
        text
    )

    # Japanese
    for code, name in PREF.items():

        if name in text:
            return code


    # English fallback
    english = text.lower()


    rules = {

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


    for keyword, code in rules.items():

        if keyword in english:
            return code


    return None


# =========================================================
# JSON-LD
# =========================================================

def extract_jsonld(
    soup
):

    output = []


    scripts = soup.find_all(
        "script",
        type="application/ld+json",
    )


    for script in scripts:

        raw = (
            script.string
            or
            script.get_text()
        )


        if not raw:
            continue


        raw = raw.strip()


        try:

            obj = json.loads(
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
# Shop name
# =========================================================

def extract_shop_name(
    soup
):

    h1 = soup.find(
        "h1"
    )


    if h1:

        value = clean_text(
            h1.get_text(
                " ",
                strip=True,
            )
        )

        if value:
            return value


    title = soup.find(
        "title"
    )


    if title:

        value = clean_text(
            title.get_text(
                " ",
                strip=True,
            )
        )

        if value:
            return value


    return ""


# =========================================================
# Address
# =========================================================

def extract_address(
    soup
):

    # -----------------------------------------------------
    # JSON-LD first
    # -----------------------------------------------------

    jsonld = extract_jsonld(
        soup
    )


    for obj in jsonld:

        if not isinstance(
            obj,
            dict,
        ):
            continue


        address =
            obj.get("address")


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


            result = clean_text(
                " ".join(
                    part
                    for part in parts
                    if part
                )
            )


            if result:
                return result


        elif isinstance(
            address,
            str,
        ):

            result = clean_text(
                address
            )


            if result:
                return result


    # -----------------------------------------------------
    # HTML fallback
    # -----------------------------------------------------

    text = clean_text(
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

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )


        if match:

            value = clean_text(
                match.group(1)
            )


            if value:
                return value


    return ""


# =========================================================
# Image
# =========================================================

def extract_image(
    soup,
    page_url,
):

    # -----------------------------------------------------
    # og:image
    # -----------------------------------------------------

    meta = soup.find(
        "meta",
        attrs={
            "property":
                "og:image"
        },
    )


    if meta:

        image = (
            meta.get(
                "content"
            )
            or
            ""
        ).strip()


        if image:

            return urllib.parse.urljoin(
                page_url,
                image,
            )


    # -----------------------------------------------------
    # JSON-LD fallback
    # -----------------------------------------------------

    jsonld = extract_jsonld(
        soup
    )


    for obj in jsonld:

        if not isinstance(
            obj,
            dict,
        ):
            continue


        image_candidate = obj.get(
            "image",
            "",
        )


        if isinstance(
            image_candidate,
            list,
        ):

            if image_candidate:

                image = str(
                    image_candidate[0]
                ).strip()


                if image:

                    return urllib.parse.urljoin(
                        page_url,
                        image,
                    )


        elif image_candidate:

            image = str(
                image_candidate
            ).strip()


            if image:

                return urllib.parse.urljoin(
                    page_url,
                    image,
                )


    return ""


# =========================================================
# Coordinates
# =========================================================

def parse_google_coordinates(
    raw,
):

    if not raw:
        return None


    decoded = urllib.parse.unquote(
        raw
    )


    # Format:
    # !2d139.7742695 !3d35.6802902

    match = re.search(
        r"!2d(-?\d+(?:\.\d+)?)"
        r".*?"
        r"!3d(-?\d+(?:\.\d+)?)",
        decoded,
    )


    if match:

        try:

            lng = float(
                match.group(1)
            )

            lat = float(
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


    # Format:
    # @35.6802902,139.7742695

    match = re.search(
        r"@(-?\d+(?:\.\d+)?),"
        r"(-?\d+(?:\.\d+)?)",
        decoded,
    )


    if match:

        try:

            lat = float(
                match.group(1)
            )

            lng = float(
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
    soup
):

    # -----------------------------------------------------
    # JSON-LD geo
    # -----------------------------------------------------

    jsonld = extract_jsonld(
        soup
    )


    for obj in jsonld:

        if not isinstance(
            obj,
            dict,
        ):
            continue


        geo = obj.get(
            "geo"
        )


        if not isinstance(
            geo,
            dict,
        ):
            continue


        try:

            lat = float(
                geo.get(
                    "latitude"
                )
            )

            lng = float(
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


    # -----------------------------------------------------
    # Google Maps links
    # -----------------------------------------------------

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = anchor.get(
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
            parse_google_coordinates(
                href
            )


        if coords:
            return coords


    # -----------------------------------------------------
    # iframe
    # -----------------------------------------------------

    for iframe in soup.find_all(
        "iframe",
        src=True,
    ):

        src = iframe.get(
            "src",
            "",
        )


        if (
            "google.com/maps"
            not in src
        ):
            continue


        coords =
            parse_google_coordinates(
                src
            )


        if coords:
            return coords


    # -----------------------------------------------------
    # Raw HTML
    # -----------------------------------------------------

    raw_html = str(
        soup
    )


    coords =
        parse_google_coordinates(
            raw_html
        )


    return coords


# =========================================================
# Discover Shop URLs
# =========================================================

def discover_shop_urls():

    print(
        "======================================"
    )

    print(
        "讀取 Pokémon 官方 Sitemap"
    )

    print(
        SITEMAP_URL
    )

    print(
        "======================================"
    )


    html =
        fetch_text(
            SITEMAP_URL
        )


    soup =
        BeautifulSoup(
            html,
            "html.parser",
        )


    results = []


    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        name = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )


        href = anchor.get(
            "href",
            "",
        )


        if not name or not href:
            continue


        if not is_pokemon_center(
            name
        ):
            continue


        lower = name.lower()


        # Exclude Store
        if (
            "pokemon store"
            in lower
            or
            "pokémon store"
            in lower
            or
            "ストア"
            in name
        ):
            continue


        # Exclude Cafe
        if (
            "pokemon cafe"
            in lower
            or
            "pokémon cafe"
            in lower
            or
            "カフェ"
            in name
        ):
            continue


        full_url =
            urllib.parse.urljoin(
                SITEMAP_URL,
                href,
            )


        if full_url not in results:

            results.append(
                full_url
            )


    print(
        "找到 Center 詳細頁：",
        len(results),
    )


    return results


# =========================================================
# Parse one center
# =========================================================

def parse_shop(
    url
):

    html =
        fetch_text(
            url
        )


    soup =
        BeautifulSoup(
            html,
            "html.parser",
        )


    name =
        extract_shop_name(
            soup
        )


    if not name:
        return None


    if not is_pokemon_center(
        name
    ):
        return None


    address =
        extract_address(
            soup
        )


    image =
        extract_image(
            soup,
            url,
        )


    coords =
        extract_coordinates(
            soup
        )


    combined =
        (
            name
            + " "
            + address
        )


    pref =
        detect_prefecture(
            combined
        )


    item_id =
        make_id(
            name,
            url,
        )


    return {

        "id":
            item_id,

        "type":
            "pokemon_center",

        "pref":
            pref,

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
# Load Existing
# =========================================================

def load_existing():

    if not DATA_FILE.exists():
        return {}


    try:

        raw =
            DATA_FILE.read_text(
                encoding="utf-8"
            )


        data =
            json.loads(
                raw
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


    except Exception as exc:

        print(
            "舊資料讀取失敗：",
            exc
        )

        return {}


# =========================================================
# Load History
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

def summary(
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
            ),

    }


# =========================================================
# MAIN
# =========================================================

def main():

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    old =
        load_existing()


    urls =
        discover_shop_urls()


    if not urls:

        raise RuntimeError(
            "官方 Sitemap 沒找到任何 Pokémon Center 詳細頁。"
        )


    new = {}


    success = 0
    failed = 0


    for index, url in enumerate(
        urls,
        start=1,
    ):

        print("")
        print(
            f"[{index}/{len(urls)}]"
        )
        print(
            "URL:",
            url,
        )


        try:

            item =
                parse_shop(
                    url
                )


            if item is None:

                print(
                    "SKIP: 不是 Pokémon Center"
                )

                continue


            old_item =
                old.get(
                    item["id"]
                )


            # 保留舊資料
            if old_item:

                if not item.get(
                    "coords"
                ):

                    item["coords"] =
                        old_item.get(
                            "coords"
                        )


                if not item.get(
                    "image"
                ):

                    item["image"] =
                        old_item.get(
                            "image",
                            ""
                        )


                if not item.get(
                    "address"
                ):

                    item["address"] =
                        old_item.get(
                            "address",
                            ""
                        )


                if item.get(
                    "pref"
                ) is None:

                    item["pref"] =
                        old_item.get(
                            "pref"
                        )


            new[
                item["id"]
            ] =
                item


            success += 1


            print(
                "OK:",
                item["name"],
            )

            print(
                "pref:",
                item.get("pref")
            )

            print(
                "address:",
                item.get("address")
            )

            print(
                "coords:",
                item.get("coords")
            )


        except Exception as exc:

            failed += 1

            print(
                "FAILED:",
                url
            )

            print(
                repr(exc)
            )


    print("")
    print(
        "======================================"
    )
    print(
        "同步結果"
    )
    print(
        "成功：",
        success
    )
    print(
        "失敗：",
        failed
    )
    print(
        "總數：",
        len(new)
    )
    print(
        "======================================"
    )


    # =====================================================
    # Critical safety check
    # =====================================================

    if len(new) == 0:

        raise RuntimeError(
            "同步結果為 0 筆，"
            "為避免清空現有資料，停止更新。"
        )


    # =====================================================
    # Compare
    # =====================================================

    added_ids =
        set(new) - set(old)


    removed_ids =
        set(old) - set(new)


    common_ids =
        set(new) & set(old)


    changed_ids = []


    compare_fields = [

        "pref",
        "name",
        "address",
        "coords",
        "image"

    ]


    for item_id in common_ids:

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

    now =
        datetime.now(
            timezone.utc
        ).astimezone().isoformat(
            timespec="seconds"
        )


    history =
        load_history()


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
                    summary(
                        new[item_id]
                    )
                    for item_id
                    in sorted(
                        added_ids
                    )
                ],

            "removed":
                [
                    summary(
                        old[item_id]
                    )
                    for item_id
                    in sorted(
                        removed_ids
                    )
                ],

            "changed":
                [
                    summary(
                        new[item_id]
                    )
                    for item_id
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
    # Save JSON
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
        "======================================"
    )


if __name__ == "__main__":
    main()
