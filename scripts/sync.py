#!/usr/bin/env python3
import json, os, urllib.request
from datetime import datetime, timezone

SOURCE = "https://raw.githubusercontent.com/yukidaruma/pokefuta-tracker/main/data/data.json"
CACHE = "data/data-cache.json"
HISTORY = "history.json"

def fetch():
    req = urllib.request.Request(SOURCE, headers={"User-Agent": "poke-lid-github-sync"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def norm(data):
    prefs = {
      1:"北海道",2:"青森県",3:"岩手県",4:"宮城県",5:"秋田県",6:"山形県",7:"福島県",
      8:"茨城県",9:"栃木県",10:"群馬県",11:"埼玉県",12:"千葉県",13:"東京都",14:"神奈川県",
      15:"新潟県",16:"富山県",17:"石川県",18:"福井県",19:"山梨県",20:"長野県",21:"岐阜県",
      22:"静岡県",23:"愛知県",24:"三重県",25:"滋賀県",26:"京都府",27:"大阪府",28:"兵庫県",
      29:"奈良県",30:"和歌山県",31:"鳥取県",32:"島根県",33:"岡山県",34:"広島県",35:"山口県",
      36:"徳島県",37:"香川県",38:"愛媛県",39:"高知県",40:"福岡県",41:"佐賀県",42:"長崎県",
      43:"熊本県",44:"大分県",45:"宮崎県",46:"鹿児島県",47:"沖縄県"}
    out={}
    for x in data.get("list", []):
        p=prefs.get(x.get("pref"), str(x.get("pref","")))
        c=str(x.get("city") or p)
        coords=x.get("coords") or ["",""]
        key=str(x.get("id") or f"{p}|{c}|{coords[0]}|{coords[1]}")
        out[key]={
          "id": key, "prefecture": p, "title": c,
          "lat": str(coords[0]), "lng": str(coords[1])
        }
    return out

def load_json(path, default):
    if not os.path.exists(path): return default
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

latest = fetch()
new = norm(latest)
old = load_json(CACHE, {})

added = [new[k] for k in new.keys()-old.keys()]
removed = [old[k] for k in old.keys()-new.keys()]
changed = [
    new[k] for k in new.keys() & old.keys()
    if (new[k]["lat"],new[k]["lng"],new[k]["title"],new[k]["prefecture"])
       != (old[k]["lat"],old[k]["lng"],old[k]["title"],old[k]["prefecture"])
]

# First run establishes baseline without falsely reporting every existing point as new.
history = load_json(HISTORY, {"history":[], "last_sync":None})
if not os.path.exists(CACHE):
    added = []; removed = []; changed = []

now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
entry = {
  "time": now,
  "total": len(new),
  "added": added,
  "removed": removed,
  "changed": changed
}
if added or removed or changed:
    history["history"] = (history.get("history", []) + [entry])[-100:]
history["last_sync"] = now

with open(CACHE, "w", encoding="utf-8") as f:
    json.dump(new, f, ensure_ascii=False, separators=(",",":"))
with open(HISTORY, "w", encoding="utf-8") as f:
    json.dump(history, f, ensure_ascii=False, indent=2)

# Produce the FavoriteLists/iTools-compatible JSON used by the web page download flow.
favorite={}
for x in new.values():
    favorite.setdefault(x["prefecture"], []).append({
        "lat": x["lat"], "lng": x["lng"], "title": x["title"]
    })
with open("data/poke_lid_2026_favorite.json","w",encoding="utf-8") as f:
    json.dump(favorite,f,ensure_ascii=False,separators=(",",":"))
