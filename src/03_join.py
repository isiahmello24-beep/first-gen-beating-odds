"""Step 3: join Scorecard + IPEDS + Opportunity Insights in DuckDB on UNITID (cohort-aligned version).

Timing design (see reports/02 and decisions.md):
  * Outcome  : FIRSTGEN_COMP_ORIG_YR6_RT from the Oct-2026 Scorecard file = NSLDS AY2017-18 entry cohort, measured AY2023-24.
  * Predictors: from MERGED2017_18_PP.csv (Fall 2017 / AY2017-18), the cohort's entry year.
  * Spending : IPEDS finance FY2018..FY2023 (every fiscal year the cohort was enrolled) per 12-month FTE
               of the same year, averaged across reported years. FY2023-only values kept as *_fy23.
  * Carnegie : C18BASIC from HD2023 (classification in force at entry).
Restricts to 4-year schools and reports how many schools drop at every stage and why.
Output: data/clean/joined.parquet (+ .csv), data/clean/finance_by_year.parquet, reports/03_join_report.md.
"""
import json
from pathlib import Path
import duckdb
import columns as C

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
REPORT = ROOT / "reports" / "03_join_report.md"
RESULTS = ROOT / "reports" / "results.json"

SC_CSV = RAW / "scorecard/Most-Recent-Cohorts-Institution_10152026/Most-Recent-Cohorts-Institution.csv"
SC_ENTRY_CSV = RAW / "scorecard/College_Scorecard_Raw_Data_10152026/MERGED2017_18_PP.csv"
HD_CSV = RAW / "ipeds/HD2023/HD2023.csv"
IC_CSV = RAW / "ipeds/IC2023/IC2023_RV.csv"
EFDIST_CSV = RAW / "ipeds/EF2017A_DIST/ef2017a_dist_rv.csv"
OI2_CSV = RAW / "opportunity_insights/mrc_table2.csv"
OI11_CSV = RAW / "opportunity_insights/mrc_table11.csv"
CPI_CSV = RAW / "cpi/CPIAUCSL.csv"
# fiscal year -> (public file, private file, FTE file); revised (_rv) files preferred where NCES published one
FIN_YEARS = {
    2018: ("F1718_F1A/f1718_f1a_rv.csv", "F1718_F2/f1718_f2_rv.csv", "EFIA2018/efia2018_rv.csv"),
    2019: ("F1819_F1A/f1819_f1a_rv.csv", "F1819_F2/f1819_f2_rv.csv", "EFIA2019/efia2019_rv.csv"),
    2020: ("F1920_F1A/f1920_f1a_rv.csv", "F1920_F2/f1920_f2_rv.csv", "EFIA2020/efia2020_rv.csv"),
    2021: ("F2021_F1A/f2021_f1a_rv.csv", "F2021_F2/f2021_f2_rv.csv", "EFIA2021/efia2021_rv.csv"),
    2022: ("F2122_F1A/f2122_f1a_rv.csv", "F2122_F2/f2122_f2_rv.csv", "EFIA2022/efia2022_rv.csv"),
    2023: ("F2223_F1A/f2223_f1a.csv", "F2223_F2/f2223_f2.csv", "EFIA2023/EFIA2023_RV.csv"),
}
IPEDS_OPTS = "all_varchar=true, header=true, nullstr=['.', ''], sample_size=-1"
SC_OPTS = "all_varchar=true, header=true, sample_size=-1"
MISSING = "('NULL', 'NA', '')"            # Scorecard "not available" markers (old and new releases)
SUPPRESSED = "('PrivacySuppressed', 'PS')"  # Scorecard small-cell suppression markers
NUMERIC_SC = [c for c in C.SCORECARD if c not in ("UNITID", "OPEID6", "INSTNM", "STABBR")]


def sc_num(col: str, alias: str | None = None) -> str:
    alias = alias or col.lower()
    return f"TRY_CAST(CASE WHEN {col} IN {MISSING} OR {col} IN {SUPPRESSED} THEN NULL ELSE {col} END AS DOUBLE) AS {alias}"


def main() -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    funnel: list[tuple[str, int, str]] = []

    def stage(name: str, sql: str, why: str) -> None:
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {sql}")
        n, n_distinct = con.execute(f"SELECT count(*), count(DISTINCT unitid) FROM {name}").fetchone()
        assert n == n_distinct, f"{name}: {n - n_distinct} duplicate UNITIDs"   # grain check at every stage, not only at the end
        funnel.append((name, n, why))
        print(f"{name:18s} {n:6,d}  {why}")

    # ------------------------------------------------- Scorecard, most recent (outcome)
    sc_cols = ",\n  ".join(
        ["UNITID::INTEGER AS unitid", "OPEID6 AS opeid6", "INSTNM AS instnm", "STABBR AS stabbr"]
        + [sc_num(c) for c in NUMERIC_SC]
        + [f"FIRSTGEN_COMP_ORIG_YR6_RT IN {SUPPRESSED} AS outcome_suppressed",
           f"FIRSTGEN_COMP_ORIG_YR6_RT IN {MISSING} AS outcome_null"])
    stage("sc_all", f"SELECT {sc_cols} FROM read_csv('{SC_CSV}', {SC_OPTS})",
          "All campuses in the October 2026 Scorecard institution file.")
    stage("sc_4yr", "SELECT * FROM sc_all WHERE preddeg = 3",
          "Keep schools whose predominant award is a bachelor's degree today (PREDDEG = 3).")
    stage("sc_oper", "SELECT * FROM sc_4yr WHERE curroper = 1",
          "Drop campuses flagged not currently operating (CURROPER = 0).")

    # ------------------------------------------------- Scorecard, entry year 2017-18 (predictors)
    e_cols = ", ".join(["UNITID::INTEGER AS e_unitid"] + [sc_num(c, f"e_{c.lower()}") for c in C.SCORECARD_ENTRY if c != "UNITID"])
    con.execute(f"CREATE OR REPLACE TABLE sc_entry AS SELECT {e_cols} FROM read_csv('{SC_ENTRY_CSV}', {SC_OPTS})")
    stage("j_entry", "SELECT s.*, e.* EXCLUDE (e_unitid) FROM sc_oper s JOIN sc_entry e ON s.unitid = e.e_unitid",
          "Inner join the 2017-18 Scorecard file (cohort entry year). Drops campuses that did not exist or were not reported in 2017-18.")
    stage("j_entry_4yr", "SELECT * FROM j_entry WHERE e_preddeg = 3",
          "Keep schools that were ALSO bachelor's-dominant in 2017-18, when the cohort entered.")

    # ------------------------------------------------------------------ IPEDS HD
    hd_cols = ", ".join(f"{c}::INTEGER AS hd_{c.lower()}" if c != "INSTNM" else "INSTNM AS hd_instnm" for c in C.IPEDS_HD)
    con.execute(f"CREATE OR REPLACE TABLE hd AS SELECT {hd_cols} FROM read_csv('{HD_CSV}', {IPEDS_OPTS})")
    stage("j_hd", "SELECT s.*, h.* EXCLUDE (hd_unitid) FROM j_entry_4yr s JOIN hd h ON s.unitid = h.hd_unitid",
          "Inner join IPEDS HD2023 on UNITID. Drops campuses with no 2023 IPEDS record (closed/merged/not in IPEDS universe).")
    stage("j_hd_4yr", "SELECT * FROM j_hd WHERE hd_iclevel = 1 AND hd_cyactive = 1 AND hd_pset4flg = 1",
          "Keep IPEDS level '4 or more years' (ICLEVEL = 1), active in 2023, Title IV eligible.")
    stage("j_nonprofit", "SELECT * FROM j_hd_4yr WHERE hd_control IN (1, 2)",
          "Drop private for-profit schools (CONTROL = 3): their finance form F3 collapses the spending categories we compare.")
    stage("j_carnegie", "SELECT * FROM j_nonprofit WHERE hd_c18basic > 0",
          "Drop schools outside the Carnegie 2018 universe (C18BASIC = -2: not accredited or non-degree-granting).")

    # ------------------------------------------------ IPEDS finance + FTE, FY2018..FY2023
    pub = ", ".join(f"TRY_CAST({p} AS DOUBLE) AS {k}" for k, (p, _, _) in C.SPENDING_CATEGORIES.items())
    prv = ", ".join(f"TRY_CAST({q} AS DOUBLE) AS {k}" for k, (_, q, _) in C.SPENDING_CATEGORIES.items())
    parts = []
    for fy, (f1a, f2, efia) in FIN_YEARS.items():
        parts.append(f"""
            SELECT {fy} AS fy, UNITID::INTEGER AS unitid, 'GASB (public)' AS finance_form, {pub} FROM read_csv('{RAW/'ipeds'/f1a}', {IPEDS_OPTS})
            UNION ALL
            SELECT {fy}, UNITID::INTEGER, 'FASB (private nonprofit)', {prv} FROM read_csv('{RAW/'ipeds'/f2}', {IPEDS_OPTS})""")
    con.execute("CREATE OR REPLACE TABLE fin_raw AS " + " UNION ALL ".join(parts))
    parts = [f"""SELECT {fy} AS fy, UNITID::INTEGER AS unitid, TRY_CAST(FTEUG AS DOUBLE) AS fteug, TRY_CAST(FTEGD AS DOUBLE) AS ftegd,
                        TRY_CAST(FTEDPP AS DOUBLE) AS ftedpp FROM read_csv('{RAW/'ipeds'/efia}', {IPEDS_OPTS})""" for fy, (_, _, efia) in FIN_YEARS.items()]
    con.execute("CREATE OR REPLACE TABLE efia_raw AS " + " UNION ALL ".join(parts))
    dup = con.execute("SELECT count(*) - count(DISTINCT (fy, unitid)) FROM fin_raw").fetchone()[0]
    assert dup == 0, f"{dup} (fy, UNITID) pairs appear in both finance files"
    cats = list(C.SPENDING_CATEGORIES)
    # row accounting for the school-year filter below: how many (school, fiscal year) rows each condition removes
    fin_acct = con.execute("""
        WITH e AS (SELECT fy, unitid, COALESCE(fteug,0)+COALESCE(ftegd,0)+COALESCE(ftedpp,0) AS fte_total FROM efia_raw),
             x AS (SELECT f.fy, f.unitid, f.exp_total, f.exp_instruction, e.fte_total FROM fin_raw f LEFT JOIN e USING (fy, unitid))
        SELECT count(*) AS finance_rows,
               count(*) FILTER (WHERE fte_total IS NULL) AS no_fte_record,
               count(*) FILTER (WHERE fte_total IS NOT NULL AND NOT fte_total > 0) AS fte_zero,
               count(*) FILTER (WHERE fte_total > 0 AND NOT exp_total > 0) AS total_expense_missing_or_zero,
               count(*) FILTER (WHERE fte_total > 0 AND exp_total > 0 AND NOT exp_instruction > 0) AS instruction_missing_or_zero,
               count(*) FILTER (WHERE fte_total > 0 AND exp_total > 0 AND exp_instruction > 0) AS kept FROM x""").df().iloc[0].to_dict()
    per_fte = ", ".join(f"f.{k} / e.fte_total AS {k}_per_fte" for k in cats)
    con.execute(f"""CREATE OR REPLACE TABLE fin_year AS
        SELECT f.fy, f.unitid, f.finance_form, {', '.join('f.'+k for k in cats)},
               e.fteug, e.ftegd, e.ftedpp, e.fte_total, {per_fte}
          FROM fin_raw f
          JOIN (SELECT fy, unitid, fteug, ftegd, ftedpp, COALESCE(fteug,0)+COALESCE(ftegd,0)+COALESCE(ftedpp,0) AS fte_total FROM efia_raw) e
            USING (fy, unitid)
         WHERE e.fte_total > 0 AND f.exp_total > 0 AND f.exp_instruction > 0""")
    # CPI-U fiscal-year averages (FY y = July y-1 .. June y); deflator to FY2023 dollars
    con.execute(f"""CREATE OR REPLACE TABLE cpi_fy AS
        SELECT CASE WHEN month(observation_date) >= 7 THEN year(observation_date) + 1 ELSE year(observation_date) END AS fy, avg(CPIAUCSL) AS cpi
          FROM read_csv('{CPI_CSV}', header=true, columns={{'observation_date': 'DATE', 'CPIAUCSL': 'DOUBLE'}}) GROUP BY 1""")
    con.execute("CREATE OR REPLACE TABLE cpi_fy AS SELECT fy, cpi, (SELECT cpi FROM cpi_fy WHERE fy = 2023) / cpi AS deflator_to_fy23 FROM cpi_fy")
    cpi_tab = con.execute("SELECT * FROM cpi_fy WHERE fy BETWEEN 2018 AND 2023 ORDER BY fy").df()
    con.execute("CREATE OR REPLACE TABLE fin_year AS SELECT f.*, c.deflator_to_fy23 FROM fin_year f JOIN cpi_fy c USING (fy)")
    con.execute(f"COPY fin_year TO '{CLEAN/'finance_by_year.parquet'}' (FORMAT PARQUET)")
    avg_cols = ", ".join(f"avg({k}_per_fte) AS {k}_per_fte" for k in cats)          # window average FY2018-23, nominal
    fy23_cols = ", ".join(f"max(CASE WHEN fy = 2023 THEN {k}_per_fte END) AS {k}_per_fte_fy23" for k in cats)
    fy1819_cols = ", ".join(f"avg(CASE WHEN fy IN (2018, 2019) THEN {k}_per_fte END) AS {k}_per_fte_fy1819" for k in cats)
    real_cols = ", ".join(f"avg({k}_per_fte * deflator_to_fy23) AS {k}_per_fte_real" for k in cats)
    con.execute(f"""CREATE OR REPLACE TABLE fin_window AS
        SELECT unitid, count(*) AS n_fin_years, min(fy) AS first_fin_fy, max(fy) AS last_fin_fy,
               count(*) FILTER (WHERE fy IN (2018, 2019)) AS n_fin_years_1819,
               max(finance_form) AS finance_form, avg(fte_total) AS fte_total, avg(fteug) AS fteug,
               avg(COALESCE(fteug, 0)) / avg(fte_total) AS ug_share_fte,
               {avg_cols}, {fy23_cols}, {fy1819_cols}, {real_cols}
          FROM fin_year GROUP BY unitid""")
    stage("j_fin", "SELECT j.*, f.* EXCLUDE (unitid) FROM j_carnegie j JOIN fin_window f ON j.unitid = f.unitid",
          "Inner join IPEDS finance + 12-month FTE for at least one fiscal year in FY2018-FY2023. Drops campuses whose finances are "
          "reported by a parent institution (IPEDS parent/child reporting) or that never filed a finance survey.")

    # --------------------------------------------------------- IPEDS IC (left)
    con.execute(f"CREATE OR REPLACE TABLE ic AS SELECT UNITID::INTEGER AS ic_unitid, TRY_CAST(OPENADMP AS INTEGER) AS openadmp FROM read_csv('{IC_CSV}', {IPEDS_OPTS})")
    stage("j_ic", "SELECT j.*, i.openadmp FROM j_fin j LEFT JOIN ic i ON j.unitid = i.ic_unitid",
          "LEFT join IPEDS IC2023 admissions policy. No rows drop; unmatched schools get NULL openadmp.")
    n_ic_missing = con.execute("SELECT count(*) FROM j_ic WHERE openadmp IS NULL").fetchone()[0]

    # ------------------------------------------- IPEDS Fall 2017 distance education (left)
    con.execute(f"""CREATE OR REPLACE TABLE efdist AS
        SELECT UNITID::INTEGER AS d_unitid, TRY_CAST(EFDETOT AS DOUBLE) AS ug_total_f17, TRY_CAST(EFDEEXC AS DOUBLE) AS ug_distance_exc_f17,
               -- IPEDS leaves EFDEEXC blank with imputation flag 'A' (not applicable) when a school offers no distance education: that is zero, not missing
               COALESCE(TRY_CAST(EFDEEXC AS DOUBLE), 0) / NULLIF(TRY_CAST(EFDETOT AS DOUBLE), 0) AS pct_distance
          FROM read_csv('{EFDIST_CSV}', {IPEDS_OPTS}) WHERE trim(EFDELEV) = '2'""")
    stage("j_dist", "SELECT j.*, d.* EXCLUDE (d_unitid) FROM j_ic j LEFT JOIN efdist d ON j.unitid = d.d_unitid",
          "LEFT join IPEDS EF2017A_DIST (share of undergraduates exclusively online, Fall 2017). No rows drop; unmatched get NULL.")
    n_dist_missing = con.execute("SELECT count(*) FROM j_dist WHERE pct_distance IS NULL").fetchone()[0]

    # ----------------------------------- OPEID6 reporting groups (left): the Scorecard reports NSLDS outcomes per 6-digit OPEID
    # Branch campuses that share an OPEID6 carry one pooled completion rate and cohort size. Each campus's share of the group's
    # Fall 2017 undergraduates says how much of that pooled rate is its own; Step 4 sets aside campuses below OPEID_SHARE_CUT.
    con.execute(f"""CREATE OR REPLACE TABLE opeid_grp AS
        WITH m AS (SELECT UNITID::INTEGER AS unitid, lpad(OPEID6, 6, '0') AS opeid6,
                          TRY_CAST(CASE WHEN UGDS IN {MISSING} OR UGDS IN {SUPPRESSED} THEN NULL ELSE UGDS END AS DOUBLE) AS ugds_now,
                          CASE WHEN FIRSTGEN_COMP_ORIG_YR6_RT IN {MISSING} OR FIRSTGEN_COMP_ORIG_YR6_RT IN {SUPPRESSED} THEN NULL ELSE FIRSTGEN_COMP_ORIG_YR6_RT END AS rate
                     FROM read_csv('{SC_CSV}', {SC_OPTS})),
             e AS (SELECT UNITID::INTEGER AS unitid, TRY_CAST(CASE WHEN UGDS IN {MISSING} OR UGDS IN {SUPPRESSED} THEN NULL ELSE UGDS END AS DOUBLE) AS ugds17
                     FROM read_csv('{SC_ENTRY_CSV}', {SC_OPTS})),
             u AS (SELECT m.unitid, m.opeid6, m.rate, COALESCE(e.ugds17, m.ugds_now, 0) AS u FROM m LEFT JOIN e USING (unitid))
        SELECT unitid, opeid6, rate, count(*) OVER (PARTITION BY opeid6) AS opeid6_members,
               COALESCE(u / NULLIF(sum(u) OVER (PARTITION BY opeid6), 0), 1.0) AS opeid6_share FROM u""")
    opeid_check = con.execute("""SELECT count(*) AS groups_with_2plus_rates, count(*) FILTER (WHERE n_rates = 1) AS groups_with_one_identical_rate
                                 FROM (SELECT opeid6, count(DISTINCT rate) AS n_rates, count(rate) AS n_campuses FROM opeid_grp WHERE rate IS NOT NULL GROUP BY 1)
                                 WHERE n_campuses > 1""").df().iloc[0].to_dict()
    stage("j_opeid", "SELECT j.*, g.opeid6_members, g.opeid6_share FROM j_dist j LEFT JOIN opeid_grp g USING (unitid)",
          "LEFT join OPEID6 reporting-group size and this campus's share of the group's Fall 2017 undergraduates (all Scorecard campuses). No rows drop.")
    n_shared = con.execute("SELECT count(*) FROM j_opeid WHERE opeid6_members > 1").fetchone()[0]

    # ------------------------------------------------ Opportunity Insights (left)
    con.execute(f"""CREATE OR REPLACE TABLE oi AS
        WITH xw AS (SELECT DISTINCT TRY_CAST(super_opeid AS INTEGER) AS super_opeid, TRY_CAST(opeid AS INTEGER) AS opeid
                      FROM read_csv('{OI11_CSV}', all_varchar=true, header=true) WHERE TRY_CAST(super_opeid AS INTEGER) > 0),
        t2 AS (SELECT TRY_CAST(super_opeid AS INTEGER) AS super_opeid, name AS oi_name, TRY_CAST(tier AS INTEGER) AS oi_tier, tier_name AS oi_tier_name,
                      TRY_CAST(count AS DOUBLE) AS oi_count, TRY_CAST(par_median AS DOUBLE) AS oi_par_median, TRY_CAST(par_q1 AS DOUBLE) AS oi_par_q1,
                      TRY_CAST(par_rank AS DOUBLE) AS oi_par_rank, TRY_CAST(k_rank AS DOUBLE) AS oi_k_rank, TRY_CAST(k_median AS DOUBLE) AS oi_k_median,
                      TRY_CAST(mr_kq5_pq1 AS DOUBLE) AS oi_mr_kq5_pq1 FROM read_csv('{OI2_CSV}', all_varchar=true, header=true))
        SELECT xw.opeid, t2.* FROM xw JOIN t2 USING (super_opeid)""")
    oi_dup = con.execute("SELECT count(*) - count(DISTINCT opeid) FROM oi").fetchone()[0]
    con.execute("CREATE OR REPLACE TABLE oi1 AS SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY opeid ORDER BY super_opeid) rn FROM oi) WHERE rn = 1")
    stage("joined", """SELECT j.*, o.* EXCLUDE (opeid, rn), (o.opeid IS NOT NULL) AS oi_matched
                       FROM j_opeid j LEFT JOIN oi1 o ON TRY_CAST(j.opeid6 AS INTEGER) = o.opeid""",
          "LEFT join Opportunity Insights via OPEID6 → mrc_table11 → super_opeid. No rows drop; unmatched schools get NULL OI fields.")
    n_oi = con.execute("SELECT count(*) FILTER (WHERE oi_matched) FROM joined").fetchone()[0]
    n_total = funnel[-1][1]
    assert con.execute("SELECT count(*) - count(DISTINCT unitid) FROM joined").fetchone()[0] == 0, "UNITID not unique after join"

    con.execute(f"COPY joined TO '{CLEAN/'joined.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY joined TO '{CLEAN/'joined.csv'}' (HEADER, DELIMITER ',')")

    fin_loss = con.execute("""SELECT hd_control, count(*) AS before_fin, count(*) FILTER (WHERE unitid IN (SELECT unitid FROM fin_window)) AS matched_fin
                              FROM j_carnegie GROUP BY 1 ORDER BY 1""").df()
    lost_examples = con.execute("""SELECT instnm, stabbr, ugds FROM j_carnegie WHERE unitid NOT IN (SELECT unitid FROM fin_window)
                                   ORDER BY ugds DESC NULLS LAST LIMIT 10""").df()
    years_hist = con.execute("SELECT n_fin_years, count(*) AS schools FROM joined GROUP BY 1 ORDER BY 1").df()

    lines = ["# Join report (Step 3)\n", "Generated by `src/03_join.py`. Join key: `UNITID`. Opportunity Insights reached via OPEID6 → super_opeid.\n",
             "\n## Timing alignment\n",
             "| Element | Source | Period |", "|---|---|---|",
             "| Outcome `FIRSTGEN_COMP_ORIG_YR6_RT` | Scorecard Oct-2026 file | NSLDS AY2017-18 entry cohort, measured AY2023-24 (data dictionary cohort map) |",
             "| Predictors (Pell share, admission rate, enrollment, part-time share, first-gen share) | Scorecard MERGED2017_18_PP.csv | Fall 2017 / AY2017-18, the cohort's entry year |",
             "| Spending per FTE | IPEDS F1718..F2223 + EFIA2018..2023 | Each fiscal year FY2018-FY2023 the cohort was enrolled, averaged per school |",
             "| Carnegie classification | IPEDS HD2023 `C18BASIC` | 2018 classification, in force at entry |",
             "| Control, level, Title IV status, open admission | IPEDS HD2023 / IC2023 | 2023 (structural, assumed stable) |",
             "\n## Funnel\n", "| Stage | Schools remaining | Dropped | Why |", "|---|---:|---:|---|"]
    prev = None
    for name, n, why in funnel:
        lines.append(f"| `{name}` | {n:,} | {'' if prev is None else f'{prev - n:,}'} | {why} |"); prev = n
    lines += ["\n## Left-join coverage (no rows dropped)\n",
              f"- IPEDS IC2023 admissions policy matched: {n_total - n_ic_missing:,} of {n_total:,} ({n_ic_missing} missing OPENADMP).",
              f"- IPEDS EF2017A_DIST (exclusively-online share, Fall 2017) matched: {n_total - n_dist_missing:,} of {n_total:,} ({n_dist_missing} missing).",
              f"- Opportunity Insights matched: {n_oi:,} of {n_total:,} ({n_oi/n_total:.1%}). OI covers 1980-82 birth cohorts at schools with enough students, so small and newer schools are absent.",
              f"- OPEIDs mapped to more than one super_opeid in mrc_table11 (first kept): {oi_dup}.",
              f"\n## OPEID6 reporting groups\n\nThe Scorecard reports NSLDS-based outcomes per 6-digit OPEID. In the full file, {opeid_check['groups_with_2plus_rates']:,} OPEID6 groups have two or more campuses with a published first-gen completion rate, "
              f"and {opeid_check['groups_with_one_identical_rate']:,} of them carry one identical rate across every campus. {n_shared:,} of the {n_total:,} joined schools sit in a multi-campus group; "
              "Step 4 sets aside the ones whose own undergraduates are under 90% of the group, because their outcome is mostly another campus's.\n",
              "\n## Finance school-year rows (FY2018-FY2023, before averaging)\n", "| Condition | School-years |", "|---|---:|",
              *[f"| {k.replace('_', ' ')} | {int(v):,} |" for k, v in fin_acct.items()],
              "\n## CPI-U fiscal-year averages used to deflate spending to FY2023 dollars (BLS via FRED, series CPIAUCSL)\n", cpi_tab.round(3).to_markdown(index=False),
              "\n\n## Fiscal years of finance data per school (FY2018-FY2023)\n", years_hist.to_markdown(index=False),
              "\n\nStep 4 requires at least 3 of the 6 fiscal years.\n",
              "\n## Finance join loss by control (1 = public, 2 = private nonprofit)\n", fin_loss.to_markdown(index=False),
              "\nMost finance losses are IPEDS parent/child reporters: branch campuses whose budget is reported under the parent UNITID. Largest campuses lost at the finance join:\n",
              lost_examples.to_markdown(index=False),
              f"\n## Output\n\n- `data/clean/joined.parquet`: {n_total:,} rows, {len(con.execute('DESCRIBE joined').fetchall())} columns, one row per UNITID.\n- `data/clean/finance_by_year.parquet`: one row per school × fiscal year.\n"]
    REPORT.write_text("\n".join(lines))
    raw_mb = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file() and "_stale" not in f.parts) / 1e6
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    results["step1"] = {"raw_total_mb": round(raw_mb)}
    results["step3"] = {"funnel": [{"stage": nm, "schools": n, "why": why} for nm, n, why in funnel], "n_joined": n_total,
                        "finance_school_years": {k: int(v) for k, v in fin_acct.items()}, "n_fin_years": {int(r.n_fin_years): int(r.schools) for r in years_hist.itertuples()},
                        "opeid6": {k: int(v) for k, v in opeid_check.items()} | {"joined_schools_in_multi_campus_groups": int(n_shared)},
                        "left_joins": {"ic_missing": int(n_ic_missing), "efdist_missing": int(n_dist_missing), "oi_matched": int(n_oi), "oi_duplicate_opeids": int(oi_dup)}}
    RESULTS.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {REPORT.relative_to(ROOT)} and data/clean/joined.parquet ({n_total:,} rows); {n_shared} schools in shared-OPEID groups; finance school-years {fin_acct}")


if __name__ == "__main__":
    main()
