"""Build a JSON geo lookup for Flemish municipalities from municipalities.csv."""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "docs" / "municipalities.csv"
OUTPUT = ROOT / "frontend" / "public" / "geo" / "vlaanderen-gemeenten.json"


def main() -> None:
    groups: dict[str, dict] = defaultdict(lambda: {"lats": [], "lons": [], "name": ""})

    with INPUT.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["reg_name_nl"] != "Vlaams Gewest":
                continue
            nis = row["niscode"]
            g = groups[nis]
            g["lats"].append(float(row["latitude"]))
            g["lons"].append(float(row["longitude"]))
            if not g["name"]:
                g["name"] = row["mun_name_nl"]

    result = []
    for nis in sorted(groups):
        g = groups[nis]
        lat = sum(g["lats"]) / len(g["lats"])
        lon = sum(g["lons"]) / len(g["lons"])
        result.append({
            "nis": nis,
            "gemeente": g["name"],
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(result)} municipalities to {OUTPUT}")


if __name__ == "__main__":
    main()
