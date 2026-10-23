"""Step 2: render the column selection in src/columns.py to reports/02_column_selection.md."""
from pathlib import Path
import columns as C

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "02_column_selection.md"


def table(title, note, d):
    rows = "\n".join(f"| `{k}` | {v} |" for k, v in d.items())
    return f"\n## {title}\n\n{note}\n\n| Column | Plain description |\n|---|---|\n{rows}\n"


def main():
    parts = ["# Column selection (Step 2)\n\nGenerated from `src/columns.py`. Role tags: **OUTCOME**, **PELL SHARE**, **SELECTIVITY**, **SIZE**, **SPENDING**.\n"]
    parts.append(table("College Scorecard (Most-Recent-Cohorts-Institution.csv)",
                       "One row per campus. `NULL` = not available; `PrivacySuppressed` = cell too small to publish.", C.SCORECARD))
    parts.append(table("IPEDS HD2023 (institutional characteristics)", "One row per institution.", C.IPEDS_HD))
    parts.append(table("IPEDS IC2023 (admissions policy)", "One row per institution.", C.IPEDS_IC))
    sp = {f"{k}  ←  {pub} / {priv}": desc for k, (pub, priv, desc) in C.SPENDING_CATEGORIES.items()}
    parts.append(table("IPEDS finance F2223_F1A (public, GASB) and F2223_F2 (private nonprofit, FASB)",
                       "Fiscal year 2022-23, whole dollars. Shown as `harmonized name ← public code / private code`. "
                       "For-profit schools file a third form (F3) whose categories are collapsed and not comparable, so they are excluded.", sp))
    parts.append(table("IPEDS EFIA2023 (12-month FTE enrollment)",
                       "**SPENDING per student** = each expense category ÷ (FTEUG + FTEGD + FTEDPP).", C.IPEDS_EFIA))
    parts.append(table("Opportunity Insights mrc_table2 (Mobility Report Cards)",
                       "1980-82 birth cohorts (students entering college roughly 1999-2004). Keyed on `super_opeid`.", C.OI_TABLE2))
    parts.append(table("Opportunity Insights mrc_table11 (crosswalk)", "Maps `super_opeid` → OPEID → Scorecard `OPEID6` → `UNITID`.", C.OI_TABLE11))
    OUT.write_text("".join(parts))
    print("".join(parts))


if __name__ == "__main__":
    main()
