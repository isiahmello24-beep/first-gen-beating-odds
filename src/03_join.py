"""Step 3: join Scorecard + IPEDS + Opportunity Insights in DuckDB on UNITID.

Restricts to 4-year schools and reports how many schools drop at every stage and why.
Output: data/clean/joined.parquet (+ .csv) and reports/03_join_report.md.

Every stage is one SQL statement so the funnel can be re-run and audited.
"""
from pathlib import Path
import duckdb
import columns as C

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
REPORT = ROOT / "reports" / "03_join_report.md"

SC_CSV = RAW / "scorecard/Most-Recent-Cohorts-Institution/Most-Recent-Cohorts-Institution.csv"
HD_CSV = RAW / "ipeds/HD2023/HD2023.csv"
IC_CSV = RAW / "ipeds/IC2023/IC2023_RV.csv"       # _RV = revised release, preferred when present
F1A_CSV = RAW / "ipeds/F2223_F1A/f2223_f1a.csv"
F2_CSV = RAW / "ipeds/F2223_F2/f2223_f2.csv"
EFIA_CSV = RAW / "ipeds/EFIA2023/EFIA2023_RV.csv"
OI2_CSV = RAW / "opportunity_insights/mrc_table2.csv"
OI11_CSV = RAW / "opportunity_insights/mrc_table11.csv"

NUMERIC_SC = [c for c in C.SCORECARD if c not in ("UNITID", "OPEID6", "INSTNM", "STABBR")]


def sc_num(col: str) -> str:
    """Scorecard numeric columns arrive as text with 'NULL' / 'PrivacySuppressed'. TRY_CAST turns both into NULL."""
    return f"TRY_CAST(NULLIF(NULLIF({col}, 'NULL'), 'PrivacySuppressed') AS DOUBLE) AS {col.lower()}"


def main() -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    funnel: list[tuple[str, int, str]] = []  # (stage, schools remaining, why rows dropped)

    def stage(name: str, sql: str, why: str) -> None:
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {sql}")
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        funnel.append((name, n, why))
        print(f"{name:18s} {n:6,d}  {why}")

    # ---------------------------------------------------------------- Scorecard
    sc_cols = ",\n  ".join(
        ["UNITID::INTEGER AS unitid", "OPEID6 AS opeid6", "INSTNM AS instnm", "STABBR AS stabbr"]
        + [sc_num(c) for c in NUMERIC_SC]
        + ["FIRSTGEN_COMP_ORIG_YR6_RT = 'PrivacySuppressed' AS outcome_suppressed",
           "FIRSTGEN_COMP_ORIG_YR6_RT = 'NULL' AS outcome_null"]
    )
    stage("sc_all", f"SELECT {sc_cols} FROM read_csv('{SC_CSV}', all_varchar=true, header=true)",
          "All campuses in the Scorecard institution file.")
    stage("sc_4yr", "SELECT * FROM sc_all WHERE preddeg = 3",
          "Keep schools whose predominant award is a bachelor's degree (PREDDEG = 3).")
    stage("sc_oper", "SELECT * FROM sc_4yr WHERE curroper = 1",
          "Drop campuses flagged not currently operating (CURROPER = 0).")

    # -------------------------------------------------------------------- IPEDS HD
    hd_cols = ", ".join(f"{c}::INTEGER AS hd_{c.lower()}" if c not in ("INSTNM",) else f"{c} AS hd_instnm" for c in C.IPEDS_HD)
    con.execute(f"CREATE OR REPLACE TABLE hd AS SELECT {hd_cols} FROM read_csv('{HD_CSV}', all_varchar=true, header=true, nullstr=['.', ''])")
    stage("j_hd", "SELECT s.*, h.* EXCLUDE (hd_unitid) FROM sc_oper s JOIN hd h ON s.unitid = h.hd_unitid",
          "Inner join IPEDS HD2023 on UNITID. Drops Scorecard campuses with no 2023 IPEDS record (closed/merged/not in IPEDS universe).")
    stage("j_hd_4yr", "SELECT * FROM j_hd WHERE hd_iclevel = 1 AND hd_cyactive = 1 AND hd_pset4flg = 1",
          "Keep IPEDS level '4 or more years' (ICLEVEL = 1), active in 2023, Title IV eligible.")
    stage("j_nonprofit", "SELECT * FROM j_hd_4yr WHERE hd_control IN (1, 2)",
          "Drop private for-profit schools (CONTROL = 3): their finance form F3 collapses the spending categories we compare.")

    # ------------------------------------------------------------ IPEDS finance
    pub = ", ".join(f"TRY_CAST({p} AS DOUBLE) AS {k}" for k, (p, _, _) in C.SPENDING_CATEGORIES.items())
    prv = ", ".join(f"TRY_CAST({q} AS DOUBLE) AS {k}" for k, (_, q, _) in C.SPENDING_CATEGORIES.items())
    con.execute(f"""CREATE OR REPLACE TABLE fin AS
        SELECT UNITID::INTEGER AS fin_unitid, 'GASB (public)' AS finance_form, {pub}
          FROM read_csv('{F1A_CSV}', all_varchar=true, header=true, nullstr=['.', ''])
        UNION ALL
        SELECT UNITID::INTEGER, 'FASB (private nonprofit)', {prv}
          FROM read_csv('{F2_CSV}', all_varchar=true, header=true, nullstr=['.', ''])""")
    dup = con.execute("SELECT count(*) - count(DISTINCT fin_unitid) FROM fin").fetchone()[0]
    assert dup == 0, f"{dup} UNITIDs appear in both finance files"
    stage("j_fin", "SELECT j.*, f.* EXCLUDE (fin_unitid) FROM j_nonprofit j JOIN fin f ON j.unitid = f.fin_unitid",
          "Inner join IPEDS finance (F1A for public, F2 for private). Drops campuses whose finances are reported by a parent "
          "institution (IPEDS parent/child reporting) or that filed no finance survey.")

    # ------------------------------------------------------------------ IPEDS FTE
    con.execute(f"""CREATE OR REPLACE TABLE efia AS
        SELECT UNITID::INTEGER AS efia_unitid, TRY_CAST(FTEUG AS DOUBLE) AS fteug, TRY_CAST(FTEGD AS DOUBLE) AS ftegd,
               TRY_CAST(FTEDPP AS DOUBLE) AS ftedpp
          FROM read_csv('{EFIA_CSV}', all_varchar=true, header=true, nullstr=['.', ''])""")
    stage("j_fte", "SELECT j.*, e.* EXCLUDE (efia_unitid) FROM j_fin j JOIN efia e ON j.unitid = e.efia_unitid",
          "Inner join IPEDS EFIA2023 (12-month FTE). Drops schools with no 12-month enrollment record (needed as the per-student denominator).")

    # --------------------------------------------------------- IPEDS IC (left)
    con.execute(f"""CREATE OR REPLACE TABLE ic AS
        SELECT UNITID::INTEGER AS ic_unitid, TRY_CAST(OPENADMP AS INTEGER) AS openadmp
          FROM read_csv('{IC_CSV}', all_varchar=true, header=true, nullstr=['.', ''])""")
    stage("j_ic", "SELECT j.*, i.openadmp FROM j_fte j LEFT JOIN ic i ON j.unitid = i.ic_unitid",
          "LEFT join IPEDS IC2023 admissions policy. No rows drop; unmatched schools get NULL openadmp.")
    n_ic_missing = con.execute("SELECT count(*) FROM j_ic WHERE openadmp IS NULL").fetchone()[0]

    # ------------------------------------------------ Opportunity Insights (left)
    con.execute(f"""CREATE OR REPLACE TABLE oi AS
        WITH xw AS (
            SELECT DISTINCT TRY_CAST(super_opeid AS INTEGER) AS super_opeid, TRY_CAST(opeid AS INTEGER) AS opeid
              FROM read_csv('{OI11_CSV}', all_varchar=true, header=true)
             WHERE TRY_CAST(super_opeid AS INTEGER) > 0),
        t2 AS (
            SELECT TRY_CAST(super_opeid AS INTEGER) AS super_opeid, name AS oi_name,
                   TRY_CAST(tier AS INTEGER) AS oi_tier, tier_name AS oi_tier_name,
                   TRY_CAST(count AS DOUBLE) AS oi_count, TRY_CAST(par_median AS DOUBLE) AS oi_par_median,
                   TRY_CAST(par_q1 AS DOUBLE) AS oi_par_q1, TRY_CAST(par_rank AS DOUBLE) AS oi_par_rank,
                   TRY_CAST(k_rank AS DOUBLE) AS oi_k_rank, TRY_CAST(k_median AS DOUBLE) AS oi_k_median,
                   TRY_CAST(mr_kq5_pq1 AS DOUBLE) AS oi_mr_kq5_pq1
              FROM read_csv('{OI2_CSV}', all_varchar=true, header=true))
        SELECT xw.opeid, t2.* FROM xw JOIN t2 USING (super_opeid)""")
    # one OPEID must map to one super_opeid; if not, keep the first deterministically and record it
    oi_dup = con.execute("SELECT count(*) - count(DISTINCT opeid) FROM oi").fetchone()[0]
    con.execute("CREATE OR REPLACE TABLE oi1 AS SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY opeid ORDER BY super_opeid) rn FROM oi) WHERE rn = 1")
    stage("joined", """SELECT j.*, o.* EXCLUDE (opeid, rn), (o.opeid IS NOT NULL) AS oi_matched
                       FROM j_ic j LEFT JOIN oi1 o ON TRY_CAST(j.opeid6 AS INTEGER) = o.opeid""",
          "LEFT join Opportunity Insights via OPEID6 → mrc_table11 → super_opeid. No rows drop; unmatched schools get NULL OI fields.")
    n_oi = con.execute("SELECT count(*) FILTER (WHERE oi_matched) FROM joined").fetchone()[0]
    n_total = funnel[-1][1]
    assert con.execute("SELECT count(*) - count(DISTINCT unitid) FROM joined").fetchone()[0] == 0, "UNITID not unique after join"

    # ------------------------------------------------------------------- outputs
    con.execute(f"COPY joined TO '{CLEAN/'joined.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY joined TO '{CLEAN/'joined.csv'}' (HEADER, DELIMITER ',')")

    # why did finance drop so many? break down by control
    fin_loss = con.execute("""
        SELECT hd_control, count(*) AS before_fin,
               count(*) FILTER (WHERE unitid IN (SELECT fin_unitid FROM fin)) AS matched_fin
          FROM j_nonprofit GROUP BY 1 ORDER BY 1""").df()
    lost_examples = con.execute("""
        SELECT instnm, stabbr, ugds FROM j_nonprofit WHERE unitid NOT IN (SELECT fin_unitid FROM fin)
        ORDER BY ugds DESC NULLS LAST LIMIT 12""").df()

    lines = ["# Join report (Step 3)\n", "Generated by `src/03_join.py`. Join key: `UNITID`. Opportunity Insights reached via OPEID6 → super_opeid.\n",
             "\n## Funnel\n", "| Stage | Schools remaining | Dropped | Why |", "|---|---:|---:|---|"]
    prev = None
    for name, n, why in funnel:
        d = "" if prev is None else f"{prev - n:,}"
        lines.append(f"| `{name}` | {n:,} | {d} | {why} |")
        prev = n
    lines += ["\n## Left-join coverage (no rows dropped)\n",
              f"- IPEDS IC2023 admissions policy matched: {n_total - n_ic_missing:,} of {n_total:,} ({n_ic_missing} missing OPENADMP).",
              f"- Opportunity Insights matched: {n_oi:,} of {n_total:,} ({n_oi/n_total:.1%}). OI covers 1980-82 birth cohorts at schools with enough students, so small and newer schools are absent.",
              f"- OPEIDs mapped to more than one super_opeid in mrc_table11 (first kept): {oi_dup}.",
              "\n## Finance join loss by control (1 = public, 2 = private nonprofit)\n", fin_loss.to_markdown(index=False),
              "\nMost finance losses are IPEDS parent/child reporters: branch campuses whose budget is reported under the parent UNITID. "
              "Largest campuses lost at the finance join:\n", lost_examples.to_markdown(index=False),
              f"\n## Output\n\n- `data/clean/joined.parquet`: {n_total:,} rows, {len(con.execute('DESCRIBE joined').fetchall())} columns, one row per UNITID.\n"]
    REPORT.write_text("\n".join(lines))
    print(f"\nwrote {REPORT.relative_to(ROOT)} and data/clean/joined.parquet ({n_total:,} rows)")


if __name__ == "__main__":
    main()
