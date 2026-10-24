"""Step 1: download the three raw datasets into data/raw and inventory them.

Sources
  College Scorecard  - most recent institution-level file, October 15, 2026 release (outcome: NSLDS AY2017-18
                       cohort measured in AY2023-24) plus MERGED2017_18_PP.csv for entry-year predictors
  IPEDS              - HD2023 / IC2023 (characteristics, admissions policy); finance F1718..F2223 (public F1A / private F2)
                       and EFIA2018..EFIA2023 (12-month FTE) covering the cohort's six fiscal years FY2018-FY2023
  BLS CPI-U (via FRED) - monthly price index, to deflate spending to FY2023 dollars
  Opportunity Insights - mrc_table2 (mobility report card, preferred estimates),
                         mrc_table11 (super_opeid -> OPEID crosswalk)

Re-running skips files that already exist. Prints row counts and columns for each
table and writes the full inventory to reports/01_raw_inventory.md.
"""
from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "reports" / "01_raw_inventory.md"

FILES = {
    "scorecard": [
        # NOTE: the undated .../Most-Recent-Cohorts-Institution.zip URL served a stale August 2024 file in Oct 2026.
        # Always use the dated file that matches the data dictionary release (here: October 15, 2026).
        ("https://ed-public-download.scorecard.network/downloads/Most-Recent-Cohorts-Institution_10152026.zip",
         "Most-Recent-Cohorts-Institution_10152026.zip"),
        ("https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx", "CollegeScorecardDataDictionary.xlsx"),
        # Full raw archive (~560 MB). Only MERGED2017_18_PP.csv is extracted: the entry year of the outcome cohort.
        ("https://ed-public-download.scorecard.network/downloads/College_Scorecard_Raw_Data_10152026.zip",
         "College_Scorecard_Raw_Data_10152026.zip"),
    ],
    "ipeds": [
        ("https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip", "HD2023.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/HD2023_Dict.zip", "HD2023_Dict.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1718_F1A.zip", "F1718_F1A.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1718_F1A_Dict.zip", "F1718_F1A_Dict.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1718_F2.zip", "F1718_F2.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1718_F2_Dict.zip", "F1718_F2_Dict.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1819_F1A.zip", "F1819_F1A.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1819_F2.zip", "F1819_F2.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1920_F1A.zip", "F1920_F1A.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F1920_F2.zip", "F1920_F2.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2021_F1A.zip", "F2021_F1A.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2021_F2.zip", "F2021_F2.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2122_F1A.zip", "F2122_F1A.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2122_F2.zip", "F2122_F2.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2018.zip", "EFIA2018.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2018_Dict.zip", "EFIA2018_Dict.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2019.zip", "EFIA2019.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2020.zip", "EFIA2020.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2021.zip", "EFIA2021.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2022.zip", "EFIA2022.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A.zip", "F2223_F1A.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A_Dict.zip", "F2223_F1A_Dict.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2223_F2.zip", "F2223_F2.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/F2223_F2_Dict.zip", "F2223_F2_Dict.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/IC2023.zip", "IC2023.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/IC2023_Dict.zip", "IC2023_Dict.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2023.zip", "EFIA2023.zip"),
        ("https://nces.ed.gov/ipeds/datacenter/data/EFIA2023_Dict.zip", "EFIA2023_Dict.zip"),
    ],
    "cpi": [
        # BLS CPI-U, all items, seasonally adjusted, monthly, via FRED. Used to express FY2018-FY2023 spending in FY2023 dollars.
        ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL", "CPIAUCSL.csv"),
    ],
    "opportunity_insights": [
        ("https://opportunityinsights.org/wp-content/uploads/2018/04/mrc_table2.csv", "mrc_table2.csv"),
        ("https://opportunityinsights.org/wp-content/uploads/2018/04/mrc_table11.csv", "mrc_table11.csv"),
    ],
}

HEADERS = {"User-Agent": "Mozilla/5.0 (portfolio research download)"}
# FRED stalls on browser-style user agents from scripted clients but answers a plain one at once.
HEADERS_BY_HOST = {"fred.stlouisfed.org": {"User-Agent": "curl/8.4.0"}}


def download(url: str, dest: Path, retries: int = 3) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  exists   {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
        return
    for attempt in range(1, retries + 1):
        try:
            host = url.split("/")[2]
            with requests.get(url, headers=HEADERS_BY_HOST.get(host, HEADERS), stream=True, timeout=120) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
            print(f"  fetched  {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
            return
        except Exception as e:  # noqa: BLE001
            print(f"  retry {attempt}/{retries} for {dest.name}: {e}")
            time.sleep(3 * attempt)
    sys.exit(f"FAILED to download {url}. Stopping, as instructed.")


RAW_ARCHIVE_KEEP = ["MERGED2017_18_PP.csv"]   # entry year of the FIRSTGEN_COMP_ORIG_YR6_RT cohort (AY2017-18)


def unzip(path: Path) -> list[Path]:
    out_dir = path.with_suffix("")
    out_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(path) as z:
        if path.name.startswith("College_Scorecard_Raw_Data"):
            names = [n for n in z.namelist() if Path(n).name in RAW_ARCHIVE_KEEP]
            for n in names:
                target = out_dir / Path(n).name
                if not target.exists():
                    with z.open(n) as src, open(target, "wb") as dst:
                        dst.write(src.read())
            return [out_dir / Path(n).name for n in names]
        z.extractall(out_dir)
        names = z.namelist()
    return [out_dir / n for n in names]


def inventory_csv(path: Path, con: duckdb.DuckDBPyConnection) -> tuple[int, list[str]]:
    rel = con.read_csv(str(path), all_varchar=True, header=True, ignore_errors=False, sample_size=-1)
    cols = rel.columns
    n = con.execute(f"SELECT count(*) FROM read_csv('{path}', all_varchar=true, header=true, sample_size=-1)").fetchone()[0]
    return n, cols


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    lines = ["# Raw data inventory (Step 1)\n", f"Generated by `src/01_download.py`.\n"]
    csvs: list[Path] = []
    for source, items in FILES.items():
        print(f"\n[{source}]")
        sdir = RAW / source
        sdir.mkdir(exist_ok=True)
        for url, fname in items:
            dest = sdir / fname
            download(url, dest)
            if fname.endswith(".zip"):
                extracted = unzip(dest)
                csvs += [p for p in extracted if p.suffix.lower() == ".csv"]
            elif fname.endswith(".csv"):
                csvs.append(dest)

    print("\n=== Row counts and columns ===")
    for p in sorted(csvs):
        # IPEDS zips sometimes ship a revised "_rv" copy alongside the original; inventory both.
        if "__MACOSX" in p.parts:
            continue
        n, cols = inventory_csv(p, con)
        rel = p.relative_to(ROOT)
        print(f"\n{rel}\n  rows: {n:,}   columns: {len(cols)}")
        preview = cols if len(cols) <= 60 else cols[:40] + ["..."] + cols[-5:]
        print("  " + ", ".join(preview))
        lines.append(f"\n## {rel}\n\n- rows: {n:,}\n- columns: {len(cols)}\n\n```\n" + "\n".join(cols) + "\n```\n")

    REPORT.write_text("".join(lines))
    print(f"\nFull inventory written to {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
