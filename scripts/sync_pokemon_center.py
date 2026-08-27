#!/usr/bin/env python3

import json
import re
import hashlib
import urllib.request
import urllib.parse

from pathlib import Path
from datetime import datetime, timezone

from bs4 import BeautifulSoup


SITEMAP_URL = "https://shop.pokemon.co.jp/en/sitemap/"

DATA_FILE = Path("data/pokemon_center.json")
HISTORY_FILE = Path("center_history.json")


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


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; PokLidsBot/1.0)"
            ),
            "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"
        }
    )

    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode(
            "utf-8",
            errors="replace"
        )


def clean(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def make_id(name, url):
    base = (
        clean(name) +
        "|" +
        clean(url)
    ).encode("utf-8")

    return (
        "pokemon-center-" +
        hashlib.sha1(base)
        .hexdigest()[:12]
    )


def is_center_name(text):

    text = clean(text).lower()

    return (
        "pokemon center" in text
        or
        "pokémon center" in text
        or
        "ポケモンセンター" in text
    )


def extract_prefecture(
    text
):

    text = clean(text)

    for code, name in PREF.items():
        if name in text:
            return code

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


def extract_jsonld(
    soup
):

    output = []

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            obj = json.loads(raw)

            if isinstance(obj, list):
                output.extend(obj)
            else:
                output.append(obj)

        except Exception:
            pass

    return output


def parse_shop(
    url,
    fallback_name=""
):

    html = fetch(url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    title = ""

    h1 = soup.find("h1")

    if h1:
        title = clean(
            h1.get_text(
                " ",
                strip=True
            )
        )

    if not title:
        title_tag = soup.find("title")

        if title_tag:
            title = clean(
                title_tag.get_text(
                    " ",
                    strip=True
                )
            )

    if not title:
        title = fallback_name


    if not is_center_name(title):
        return None


    # -----------------------------------------------------
    # JSON-LD
    # -----------------------------------------------------

    jsonld = extract_jsonld(soup)

    address = ""
    image = ""
    lat = None
    lng = None

    for obj in jsonld:

        if not isinstance(obj, dict):
            continue

        obj_address = obj.get(
            "address"
        )

        if isinstance(
            obj_address,
            dict
        ):

            parts = [

                obj_address.get(
                    "postalCode",
                    ""
                ),

                obj_address.get(
                    "addressRegion",
                    ""
                ),

                obj_address.get(
                    "addressLocality",
                    ""
                ),

                obj_address.get(
                    "streetAddress",
                    ""
                ),

            ]

            candidate = clean(
                " ".join(
                    x
                    for x in parts
                    if x
                )
            )

            if candidate:
                address = candidate

        elif isinstance(
            obj_address,
            str
        ):

            if obj_address:
                address = clean(
                    obj_address
                )


        if not image:

            image_candidate =
                obj.get("image", "")

            if isinstance(
                image_candidate,
                list
            ):

                if image_candidate:
                    image = str(
                        image_candidate[0]
                    )

            elif image_candidate:

                image = str(
                    image_candidate
                )


        geo = obj.get(
            "geo"
        )

        if isinstance(
            geo,
            dict
        ):

            try:
                if geo.get(
                    "latitude"
                ) is not None:

                    lat = float(
                        geo["latitude"]
                    )

                if geo.get(
                    "longitude"
                ) is not None:

                    lng = float(
                        geo["longitude"]
                    )

            except Exception:
                pass


    # -----------------------------------------------------
    # Meta image fallback
    # -----------------------------------------------------

    if not image:

        meta = soup.find(
            "meta",
            attrs={
                "property":
                    "og:image"
            }
        )

        if meta:
            image = (
                meta.get(
                    "content"
                )
                or
                ""
            ).strip()


    # -----------------------------------------------------
    # Page text fallback for address
    # -----------------------------------------------------

    page_text = clean(
        soup.get_text(
            " ",
            strip=True
        )
    )


    if not address:

        patterns = [

            r"Location\s+(.{5,300}?)(?:Google Maps|Opening Hours|Business Hours)",

            r"所在地\s+(.{5,300}?)(?:Google Maps|営業時間|アクセス)",

        ]

        for pattern in patterns:

            m = re.search(
                pattern,
                page_text,
                re.IGNORECASE
            )

            if m:
                address = clean(
                    m.group(1)
                )
                break


    # -----------------------------------------------------
    # Google Maps coordinates
    # -----------------------------------------------------

    if lat is None or lng is None:

        google_links = []

        for a in soup.find_all(
            "a",
            href=True
        ):

            href = a["href"]

            if (
                "google.com/maps"
                in href
                or
                "google.co.jp/maps"
                in href
            ):

                google_links.append(
                    href
                )


        for iframe in soup.find_all(
            "iframe",
            src=True
        ):

            src = iframe["src"]

            if "google.com/maps" in src:

                google_links.append(
                    src
                )


        for raw_url in google_links:

            decoded = urllib.parse.unquote(
                raw_url
            )

            m = re.search(
                r"!2d(-?\d+(?:\.\d+)?)"
                r".*?"
                r"!3d(-?\d+(?:\.\d+)?)",
                decoded
            )

            if not m:

                m = re.search(
                    r"@(-?\d+(?:\.\d+)?),"
                    r"(-?\d+(?:\.\d+)?)",
                    decoded
                )

            if m:

                try:

                    lng = float(
                        m.group(1)
                    )

                    lat = float(
                        m.group(2)
                    )

                    break

                except Exception:

                    pass


    combined = (
        title +
        " " +
        address
    )


    pref = extract_prefecture(
        combined
    )


    coords = None

    if (
        lat is not None
        and
        lng is not None
        and
        20 <= lat <= 50
        and
        120 <= lng <= 150
    ):

        coords = [
            lat,
            lng
        ]


    return {

        "id":
            make_id(
                title,
                url
            ),

        "type":
            "pokemon_center",

        "pref":
            pref,

        "name":
            title,

        "city":
            "",

        "address":
            address,

        "coords":
            coords,

        "image":
            urllib.parse.urljoin(
                url,
                image
            )
            if image
            else
            "",

        "official_url":
            url,

        "source":
            "Pokemon Official Shop"

    }


def discover_urls():

    print(
        "讀取官方 Sitemap..."
    )

    html =
        fetch(
            SITEMAP_URL
        )

    soup =
        BeautifulSoup(
            html,
            "html.parser"
        )

    urls = []

    for a in soup.find_all(
        "a",
        href=True
    ):

        href =
            a["href"]

        text =
            clean(
                a.get_text(
                    " ",
                    strip=True
                )
            )

        full =
            urllib.parse.urljoin(
                SITEMAP_URL,
                href
            )


        if "shop.pokemon.co.jp" not in full:
            continue


        # 不抓 Store
        if (
            "store"
            in
            text.lower()
            or
            "ストア"
            in
            text
        ):
            continue


        # 不抓 Cafe
        if (
            "cafe"
            in
            text.lower()
            or
            "カフェ"
            in
            text
        ):
            continue


        if full not in urls:

            urls.append(
                full
            )


    print(
        "找到詳細頁：",
        len(urls)
    )


    return urls


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
            str(x["id"]): x
            for x
            in data.get(
                "list",
                []
            )
            if x.get("id")
        }

    except Exception:

        return {}


def load_history():

    if not HISTORY_FILE.exists():

        return {
            "last_sync": None,
            "total": 0,
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
            "total": 0,
            "history": []
        }


def main():

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    old =
        load_existing()


    urls =
        discover_urls()


    if not urls:

        raise RuntimeError(
            "找不到任何官方詳細頁，停止更新。"
        )


    new = {}


    success = 0
    failed = 0


    for url in urls:

        try:

            item =
                parse_shop(
                    url
                )


            if item is None:

                continue


            success += 1


            # 保留舊資料
            old_item =
                old.get(
                    item["id"]
                )


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


            print(
                "OK:",
                item["name"]
            )

        except Exception as exc:

            failed += 1

            print(
                "FAILED:",
                url,
                exc
            )


    print("")
    print(
        "成功取得 Center：",
        success
    )

    print(
        "失敗：",
        failed
    )


    # =====================================================
    # CRITICAL SAFETY CHECK
    # =====================================================

    if len(new) == 0:

        raise RuntimeError(
            "同步結果為 0 筆，"
            "拒絕覆蓋 pokemon_center.json。"
        )


    now =
        datetime.now(
            timezone.utc
        ).astimezone().isoformat(
            timespec="seconds"
        )


    added_ids =
        set(new) -
        set(old)


    removed_ids =
        set(old) -
        set(new)


    common =
        set(new) &
        set(old)


    changed_ids = []


    for item_id in common:

        a = old[item_id]
        b = new[item_id]

        fields = [
            "pref",
            "name",
            "address",
            "coords",
            "image"
        ]

        for field in fields:

            if (
                a.get(field)
                !=
                b.get(field)
            ):

                changed_ids.append(
                    item_id
                )

                break


    def summary(item):

        coords =
            item.get(
                "coords"
            )


        return {

            "id":
                item.get(
                    "id"
                ),

            "prefecture":
                item.get(
                    "pref"
                ),

            "title":
                item.get(
                    "name"
                ),

            "lat":
                (
                    coords[0]
                    if
                    coords
                    else
                    ""
                ),

            "lng":
                (
                    coords[1]
                    if
                    coords
                    else
                    ""
                ),

            "address":
                item.get(
                    "address",
                    ""
                )

        }


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
                    summary(new[x])
                    for x in sorted(
                        added_ids
                    )
                ],

            "removed":
                [
                    summary(old[x])
                    for x in sorted(
                        removed_ids
                    )
                ],

            "changed":
                [
                    summary(new[x])
                    for x in sorted(
                        changed_ids
                    )
                ]

        })


        history["history"] =
            history["history"][
                -200:
            ]


    history["last_sync"] =
        now


    history["total"] =
        len(new)


    ordered =
        sorted(

            new.values(),

            key=lambda x: (

                x.get(
                    "pref"
                )
                if x.get(
                    "pref"
                ) is not None
                else
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


    print("")
    print(
        "================================"
    )
    print(
        " Pokémon Center Sync OK"
    )
    print(
        "總數：",
        len(ordered)
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
        "================================"
    )


if __name__ == "__main__":
    main()
