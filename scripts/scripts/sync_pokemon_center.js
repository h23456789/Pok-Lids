const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const SITEMAP_URL =
  "https://shop.pokemon.co.jp/en/sitemap/";

const DATA_FILE =
  path.join(
    process.cwd(),
    "data",
    "pokemon_center.json"
  );

const HISTORY_FILE =
  path.join(
    process.cwd(),
    "center_history.json"
  );


const PREF = {

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
  47: "沖縄県"

};


const EN_PREF = {

  hokkaido: 1,
  aomori: 2,
  iwate: 3,
  miyagi: 4,
  akita: 5,
  yamagata: 6,
  fukushima: 7,

  ibaraki: 8,
  tochigi: 9,
  gunma: 10,
  saitama: 11,
  chiba: 12,
  tokyo: 13,
  kanagawa: 14,

  niigata: 15,
  toyama: 16,
  ishikawa: 17,
  fukui: 18,
  yamanashi: 19,
  nagano: 20,
  gifu: 21,
  shizuoka: 22,
  aichi: 23,

  mie: 24,
  shiga: 25,
  kyoto: 26,
  osaka: 27,
  hyogo: 28,
  nara: 29,
  wakayama: 30,

  tottori: 31,
  shimane: 32,
  okayama: 33,
  hiroshima: 34,
  yamaguchi: 35,

  tokushima: 36,
  kagawa: 37,
  ehime: 38,
  kochi: 39,

  fukuoka: 40,
  saga: 41,
  nagasaki: 42,
  kumamoto: 43,
  oita: 44,
  miyazaki: 45,
  kagoshima: 46,
  okinawa: 47

};


const CITY_RULES = [

  ["札幌", 1],
  ["仙台", 4],
  ["盛岡", 3],
  ["秋田", 5],
  ["山形", 6],
  ["福島", 7],

  ["水戸", 8],
  ["宇都宮", 9],
  ["前橋", 10],
  ["さいたま", 11],
  ["千葉", 12],
  ["東京", 13],
  ["日本橋", 13],
  ["渋谷", 13],
  ["池袋", 13],
  ["押上", 13],
  ["横浜", 14],

  ["新潟", 15],
  ["富山", 16],
  ["金沢", 17],
  ["福井", 18],
  ["甲府", 19],
  ["長野", 20],
  ["岐阜", 21],
  ["静岡", 22],
  ["名古屋", 23],

  ["津", 24],
  ["大津", 25],
  ["京都", 26],
  ["大阪", 27],
  ["神戸", 28],
  ["奈良", 29],
  ["和歌山", 30],

  ["鳥取", 31],
  ["松江", 32],
  ["岡山", 33],
  ["広島", 34],
  ["山口", 35],

  ["徳島", 36],
  ["高松", 37],
  ["松山", 38],
  ["高知", 39],

  ["福岡", 40],
  ["佐賀", 41],
  ["長崎", 42],
  ["熊本", 43],
  ["大分", 44],
  ["宮崎", 45],
  ["鹿児島", 46],
  ["沖縄", 47]

];


function clean(text) {

  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();

}


async function fetchText(url) {

  const response =
    await fetch(
      url,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 PokemonCenterSync/1.0",
          "Accept-Language":
            "ja-JP,ja;q=0.9,en;q=0.8"
        }
      }
    );


  if (!response.ok) {

    throw new Error(
      `HTTP ${response.status}: ${url}`
    );

  }


  return await response.text();

}


function makeId(
  name,
  url
) {

  const raw =
    `${name}|${url}`;

  const hash =
    crypto
      .createHash("sha1")
      .update(raw, "utf8")
      .digest("hex")
      .slice(0, 12);


  return (
    "pokemon-center-" +
    hash
  );

}


function isCenter(
  name
) {

  const text =
    clean(name).toLowerCase();


  return (
    text.includes("pokemon center") ||
    text.includes("pokémon center") ||
    name.includes("ポケモンセンター")
  );

}


function isExcluded(
  name
) {

  const text =
    clean(name).toLowerCase();


  if (
    text.includes("pokemon store") ||
    text.includes("pokémon store") ||
    text.includes("pokemon cafe") ||
    text.includes("pokémon cafe") ||
    text.includes("store") ||
    text.includes("cafe")
  ) {

    return true;

  }


  if (
    name.includes("ストア") ||
    name.includes("カフェ")
  ) {

    return true;

  }


  return false;

}


function detectPrefecture(
  text
) {

  const value =
    clean(text);


  for (
    const [
      code,
      name
    ]
    of Object.entries(PREF)
  ) {

    if (
      value.includes(name)
    ) {

      return Number(code);

    }

  }


  const lower =
    value.toLowerCase();


  for (
    const [
      keyword,
      code
    ]
    of Object.entries(EN_PREF)
  ) {

    if (
      lower.includes(keyword)
    ) {

      return code;

    }

  }


  for (
    const [
      keyword,
      code
    ]
    of CITY_RULES
  ) {

    if (
      value.includes(keyword)
    ) {

      return code;

    }

  }


  return null;

}


function extractJsonLd(
  html
) {

  const result = [];


  const regex =
    /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;


  let match;


  while (
    (match = regex.exec(html))
    !== null
  ) {

    const raw =
      match[1].trim();


    if (!raw) {

      continue;

    }


    try {

      const obj =
        JSON.parse(raw);


      if (
        Array.isArray(obj)
      ) {

        result.push(...obj);

      } else {

        result.push(obj);

      }

    } catch {
      // Ignore malformed JSON-LD
    }

  }


  return result;

}


function stripTags(
  html
) {

  return clean(
    html
      .replace(
        /<script[\s\S]*?<\/script>/gi,
        " "
      )
      .replace(
        /<style[\s\S]*?<\/style>/gi,
        " "
      )
      .replace(
        /<[^>]+>/g,
        " "
      )
  );

}


function decodeHtml(
  text
) {

  return clean(
    text
      .replace(
        /&amp;/g,
        "&"
      )
      .replace(
        /&quot;/g,
        '"'
      )
      .replace(
        /&#39;/g,
        "'"
      )
      .replace(
        /&lt;/g,
        "<"
      )
      .replace(
        /&gt;/g,
        ">"
      )
  );

}


function extractName(
  html
) {

  const h1 =
    html.match(
      /<h1[^>]*>([\s\S]*?)<\/h1>/i
    );


  if (h1) {

    const name =
      decodeHtml(
        stripTags(
          h1[1]
        )
      );


    if (name) {

      return name;

    }

  }


  const title =
    html.match(
      /<title[^>]*>([\s\S]*?)<\/title>/i
    );


  if (title) {

    const name =
      decodeHtml(
        stripTags(
          title[1]
        )
      );


    if (name) {

      return name;

    }

  }


  return "";

}


function extractAddress(
  html
) {

  const jsonld =
    extractJsonLd(
      html
    );


  for (
    const obj
    of jsonld
  ) {

    if (
      !obj ||
      typeof obj !== "object"
    ) {

      continue;

    }


    const address =
      obj.address;


    if (
      address &&
      typeof address === "object"
    ) {

      const parts = [

        address.postalCode || "",
        address.addressRegion || "",
        address.addressLocality || "",
        address.streetAddress || ""

      ];


      const value =
        clean(
          parts
            .filter(Boolean)
            .join(" ")
        );


      if (value) {

        return value;

      }

    }


    if (
      typeof address === "string" &&
      clean(address)
    ) {

      return clean(
        address
      );

    }

  }


  const text =
    stripTags(
      html
    );


  const patterns = [

    /Location\s+(.{5,400}?)(?:Google Maps|Opening Hours|Business Hours|Directions)/i,

    /所在地\s+(.{5,400}?)(?:Google Maps|営業時間|アクセス)/i

  ];


  for (
    const pattern
    of patterns
  ) {

    const match =
      text.match(
        pattern
      );


    if (match) {

      const address =
        clean(
          match[1]
        );


      if (address) {

        return address;

      }

    }

  }


  return "";

}


function extractImage(
  html,
  pageUrl
) {

  const og =
    html.match(
      /<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["'][^>]*>/i
    );


  if (og && og[1]) {

    return new URL(
      og[1],
      pageUrl
    ).href;

  }


  const jsonld =
    extractJsonLd(
      html
    );


  for (
    const obj
    of jsonld
  ) {

    if (
      !obj ||
      typeof obj !== "object"
    ) {

      continue;

    }


    let image =
      obj.image;


    if (
      Array.isArray(image)
    ) {

      image =
        image[0];

    }


    if (image) {

      return new URL(
        String(image),
        pageUrl
      ).href;

    }

  }


  return "";

}


function parseGoogleCoords(
  text
) {

  if (!text) {

    return null;

  }


  const decoded =
    decodeURIComponent(
      text
        .replace(
          /&amp;/g,
          "&"
        )
    );


  let match =
    decoded.match(
      /!2d(-?\d+(?:\.\d+)?).*?!3d(-?\d+(?:\.\d+)?)/s
    );


  if (match) {

    const lng =
      Number(
        match[1]
      );


    const lat =
      Number(
        match[2]
      );


    if (
      Number.isFinite(lat) &&
      Number.isFinite(lng) &&
      lat >= 20 &&
      lat <= 50 &&
      lng >= 120 &&
      lng <= 150
    ) {

      return [
        lat,
        lng
      ];

    }

  }


  match =
    decoded.match(
      /@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/
    );


  if (match) {

    const lat =
      Number(
        match[1]
      );


    const lng =
      Number(
        match[2]
      );


    if (
      Number.isFinite(lat) &&
      Number.isFinite(lng) &&
      lat >= 20 &&
      lat <= 50 &&
      lng >= 120 &&
      lng <= 150
    ) {

      return [
        lat,
        lng
      ];

    }

  }


  return null;

}


function extractCoordinates(
  html
) {

  const jsonld =
    extractJsonLd(
      html
    );


  for (
    const obj
    of jsonld
  ) {

    if (
      !obj ||
      typeof obj !== "object"
    ) {

      continue;

    }


    if (
      obj.geo &&
      typeof obj.geo === "object"
    ) {

      const lat =
        Number(
          obj.geo.latitude
        );


      const lng =
        Number(
          obj.geo.longitude
        );


      if (
        Number.isFinite(lat) &&
        Number.isFinite(lng) &&
        lat >= 20 &&
        lat <= 50 &&
        lng >= 120 &&
        lng <= 150
      ) {

        return [
          lat,
          lng
        ];

      }

    }

  }


  const googleRegex =
    /https?:\/\/[^"'<> ]*(?:google\.com\/maps|google\.co\.jp\/maps)[^"'<> ]*/gi;


  const links =
    html.match(
      googleRegex
    ) || [];


  for (
    const link
    of links
  ) {

    const coords =
      parseGoogleCoords(
        link
      );


    if (coords) {

      return coords;

    }

  }


  return null;

}


function discover() {

  return fetchText(
    SITEMAP_URL
  )
    .then(
      html => {

        const regex =
          /<a[^>]+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;


        const results = [];
        const seen = new Set();


        let match;


        while (
          (match = regex.exec(html))
          !== null
        ) {

          const href =
            new URL(
              match[1],
              SITEMAP_URL
            ).href;


          const name =
            decodeHtml(
              stripTags(
                match[2]
              )
            );


          if (
            !isCenter(name)
          ) {

            continue;

          }


          if (
            isExcluded(name)
          ) {

            continue;

          }


          if (
            !href.includes(
              "/en/shop/"
            )
          ) {

            continue;

          }


          if (
            name.toUpperCase()
              .includes("TAIPEI")
            ||
            name.toUpperCase()
              .includes("SINGAPORE")
          ) {

            continue;

          }


          if (
            seen.has(href)
          ) {

            continue;

          }


          seen.add(
            href
          );


          results.push({
            name,
            url: href
          });

        }


        return results;

      }
    );

}


function loadExisting() {

  if (
    !fs.existsSync(
      DATA_FILE
    )
  ) {

    return {};

  }


  try {

    const data =
      JSON.parse(
        fs.readFileSync(
          DATA_FILE,
          "utf8"
        )
      );


    return Object.fromEntries(

      (data.list || [])
        .filter(
          item =>
            item &&
            item.id
        )
        .map(
          item => [
            String(item.id),
            item
          ]
        )

    );

  } catch {

    return {};

  }

}


function loadHistory() {

  if (
    !fs.existsSync(
      HISTORY_FILE
    )
  ) {

    return {
      last_sync: null,
      total: 0,
      history: []
    };

  }


  try {

    return JSON.parse(
      fs.readFileSync(
        HISTORY_FILE,
        "utf8"
      )
    );

  } catch {

    return {
      last_sync: null,
      total: 0,
      history: []
    };

  }

}


function summary(
  item
) {

  const coords =
    item.coords;


  return {

    id:
      item.id || "",

    prefecture:
      item.pref ?? null,

    title:
      item.name || "",

    lat:
      Array.isArray(coords)
      ? coords[0]
      : "",

    lng:
      Array.isArray(coords)
      ? coords[1]
      : "",

    address:
      item.address || ""

  };

}


async function main() {

  console.log(
    "======================================"
  );

  console.log(
    "Pokémon Center 同步開始"
  );

  console.log(
    SITEMAP_URL
  );

  console.log(
    "======================================"
  );


  const old =
    loadExisting();


  const shops =
    await discover();


  console.log(
    "找到 Center 詳細頁：",
    shops.length
  );


  if (
    shops.length === 0
  ) {

    throw new Error(
      "官方 Sitemap 找不到 Pokémon Center"
    );

  }


  const newData = {};


  let success = 0;
  let failed = 0;


  for (
    let i = 0;
    i < shops.length;
    i++
  ) {

    const shop =
      shops[i];


    try {

      const html =
        await fetchText(
          shop.url
        );


      const name =
        extractName(
          html
        ) ||
        shop.name;


      if (
        !isCenter(name)
        ||
        isExcluded(name)
      ) {

        continue;

      }


      const address =
        extractAddress(
          html
        );


      const image =
        extractImage(
          html,
          shop.url
        );


      const coords =
        extractCoordinates(
          html
        );


      const pref =
        detectPrefecture(
          name +
          " " +
          address
        );


      const id =
        makeId(
          name,
          shop.url
        );


      const oldItem =
        old[id];


      const item = {

        id,

        type:
          "pokemon_center",

        pref:
          pref !== null
          ? pref
          : (
              oldItem
              ? oldItem.pref
              : null
            ),

        region:
          oldItem
          ? oldItem.region || ""
          : "",

        name,

        city:
          "",

        address:
          address ||
          (
            oldItem
            ? oldItem.address || ""
            : ""
          ),

        coords:
          coords ||
          (
            oldItem
            ? oldItem.coords || null
            : null
          ),

        image:
          image ||
          (
            oldItem
            ? oldItem.image || ""
            : ""
          ),

        official_url:
          shop.url,

        source:
          SITEMAP_URL

      };


      newData[id] =
        item;


      success++;


      console.log(
        `[${i + 1}/${shops.length}] OK`,
        name,
        "| pref:",
        item.pref,
        "| coords:",
        JSON.stringify(
          item.coords
        )
      );


    } catch (
      error
    ) {

      failed++;


      console.log(
        `[${i + 1}/${shops.length}] FAILED`,
        shop.url
      );


      console.log(
        error.message
      );

    }

  }


  console.log("");
  console.log(
    "成功：",
    success
  );
  console.log(
    "失敗：",
    failed
  );
  console.log(
    "最終資料：",
    Object.keys(newData).length
  );


  if (
    Object.keys(newData).length === 0
  ) {

    throw new Error(
      "同步結果為 0 筆，拒絕覆蓋資料"
    );

  }


  const addedIds =
    Object.keys(newData)
      .filter(
        id =>
          !old[id]
      );


  const removedIds =
    Object.keys(old)
      .filter(
        id =>
          !newData[id]
      );


  const changedIds = [];


  for (
    const id
    of Object.keys(newData)
  ) {

    if (
      !old[id]
    ) {

      continue;

    }


    const fields = [
      "pref",
      "name",
      "address",
      "coords",
      "image"
    ];


    const changed =
      fields.some(
        field =>
          JSON.stringify(
            old[id][field]
          )
          !==
          JSON.stringify(
            newData[id][field]
          )
      );


    if (changed) {

      changedIds.push(
        id
      );

    }

  }


  const history =
    loadHistory();


  const now =
    new Date()
      .toISOString();


  if (
    addedIds.length ||
    removedIds.length ||
    changedIds.length
  ) {

    history.history =
      history.history || [];


    history.history.push({

      time:
        now,

      type:
        "center",

      total:
        Object.keys(newData).length,

      added:
        addedIds.map(
          id =>
            summary(
              newData[id]
            )
        ),

      removed:
        removedIds.map(
          id =>
            summary(
              old[id]
            )
        ),

      changed:
        changedIds.map(
          id =>
            summary(
              newData[id]
            )
        )

    });


    history.history =
      history.history.slice(
        -200
      );

  }


  history.last_sync =
    now;


  history.total =
    Object.keys(newData).length;


  const ordered =
    Object.values(
      newData
    ).sort(
      (a,b) =>
        (
          (a.pref ?? 999)
          -
          (b.pref ?? 999)
        )
        ||
        a.name.localeCompare(
          b.name
        )
    );


  fs.mkdirSync(
    path.dirname(DATA_FILE),
    {
      recursive: true
    }
  );


  fs.writeFileSync(

    DATA_FILE,

    JSON.stringify(
      {
        list:
          ordered
      },
      null,
      2
    ),

    "utf8"

  );


  fs.writeFileSync(

    HISTORY_FILE,

    JSON.stringify(
      history,
      null,
      2
    ),

    "utf8"

  );


  console.log("");
  console.log(
    "======================================"
  );

  console.log(
    "Pokémon Center Sync 完成"
  );

  console.log(
    "總數：",
    ordered.length
  );

  console.log(
    "新增：",
    addedIds.length
  );

  console.log(
    "移除：",
    removedIds.length
  );

  console.log(
    "修改：",
    changedIds.length
  );

  console.log(
    "======================================"
  );

}


main()
  .catch(
    error => {

      console.error("");
      console.error(
        "❌ Pokémon Center Sync 失敗"
      );

      console.error(
        error.stack ||
        error.message
      );

      process.exit(
        1
      );

    }
  );
