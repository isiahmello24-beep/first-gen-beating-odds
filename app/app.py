"""Streamlit dashboard: which 4-year colleges graduate first-gen students above prediction, and what they spend on.

Run from the project root:  streamlit run app/app.py
Reads data/clean/analysis_scored.parquet, data/clean/bootstrap_ranks.csv and reports/results.json (from src/05-08).
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="First-Gen Completion: Over-performing Colleges", layout="wide", page_icon="🎓")
CORE = {"exp_instruction": "Instruction", "exp_academic_support": "Academic support", "exp_student_services": "Student services", "exp_institutional_support": "Institutional support"}
CARN = "C(carnegie_group, Treatment(reference=\"Master's\"))"
LABELS = {**{f"private:{t}": f"Private × {v}" for t, v in {"pctpell": "Pell share", "adm_rate": "admission rate", "log_ugds": "log(enrollment)", "pptug_ef": "part-time share", "first_gen": "first-gen share", "ug25abv": "share aged 25+", "pct_distance": "share online", "hbcu_flag": "HBCU"}.items()},
          "pctpell": "Pell share", "adm_rate": "Admission rate", "log_ugds": "log(enrollment)", "pptug_ef": "Part-time share", "first_gen": "First-gen share",
          "ug25abv": "Share aged 25+", "pct_distance": "Share exclusively online", "private": "Private nonprofit", "hbcu_flag": "HBCU", f"{CARN}[T.Doctoral]": "Carnegie: Doctoral", f"{CARN}[T.Baccalaureate]": "Carnegie: Baccalaureate"}
TOP, BOT = "#2a9d8f", "#e76f51"


FILES = [ROOT / "data/clean/analysis_scored.parquet", ROOT / "data/clean/bootstrap_ranks.csv", ROOT / "reports/results.json"]


@st.cache_data
def load(_mtimes: tuple):
    """Cached on the files' modification times, so a pipeline rerun always refreshes the dashboard."""
    full = pd.read_parquet(FILES[0]); boot = pd.read_csv(FILES[1]); res = json.loads(FILES[2].read_text())
    return full, boot, res


full, boot, res = load(tuple(f.stat().st_mtime for f in FILES))
df = full[full.in_main == 1].copy()
sf = full[full.in_main == 0].copy()
s5, s6, s7, s8 = res["step5"], res["step6"], res["step7"], res["step8"]
pf, bs, sec = s7["per_fte"], s8["bootstrap"], s8["sector"]

st.title("Which 4-year colleges graduate first-generation students above prediction?")
st.caption("College Scorecard (Oct 2026) + IPEDS FY2018-23 + Opportunity Insights, joined on UNITID. Outcome: first-gen federal-aid students who entered in 2017-18 and completed at the same school within 6 years. "
           "Predictors and spending are measured during the cohort's own years. School-level, correlational. See Methods tab.")
tab_over, tab_rank, tab_spend, tab_school, tab_method = st.tabs(["Overview", "Rankings", "Spending comparison", "School lookup", "Methods & limitations"])

with tab_over:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Schools in model", f"{s5['n']:,}", f"+{s5['n_excluded']} excluded, scored separately")
    c2.metric(f"R² ({s5['main_model']})", f"{s5['r2_main']:.2f}", f"pooled Model A {s5['r2_A']:.2f}")
    c3.metric("Mean first-gen 6-yr completion", f"{s5['outcome_mean']:.1%}")
    c4.metric("Top-decile residual cut", f"+{s6['top_decile_cut_pp']:.1f} pts")
    left, right = st.columns([3, 2])
    with left:
        fig = px.scatter(df, x="predicted", y="firstgen_comp_orig_yr6_rt", color="group", hover_name="instnm",
                         hover_data={"stabbr": True, "control_label": True, "carnegie_group": True, "ugds": ":,", "pctpell": ":.2f", "predicted": ":.3f", "firstgen_comp_orig_yr6_rt": ":.3f", "group": False},
                         color_discrete_map={"top 10%": TOP, "bottom 10%": BOT, "middle": "#8d99ae"}, opacity=.65,
                         labels={"predicted": "Predicted completion (Model A)", "firstgen_comp_orig_yr6_rt": "Actual first-gen completion, 2017-18 cohort"}, title="Actual vs predicted: distance above the line = residual")
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dash", color="black")); fig.update_layout(height=520, legend_title="Residual group")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        terms = [k for k in LABELS if k in s5["coef_A"]]
        co = pd.DataFrame({"term": [LABELS[k] for k in terms], "coef": [s5["coef_A"][k] for k in terms], "se": [s5["se_A"][k] for k in terms]})
        st.caption(f"Coefficients shown are the pooled Model A (one slope per trait). The ranking uses {s5['main_model']}, which lets every slope differ between public and private schools; its coefficients are in reports/05_regression.md.")
        figc = go.Figure(go.Bar(x=co["coef"], y=co["term"], orientation="h", error_x=dict(type="data", array=1.96 * co["se"]), marker_color="#457b9d"))
        figc.update_layout(title="Model A coefficients (±95% CI, HC3)", xaxis_title="Change in completion rate per 1-unit change", height=520, yaxis=dict(autorange="reversed"))
        st.plotly_chart(figc, use_container_width=True)
    st.markdown(f"**Reading the pooled model.** A 10-point higher Pell share (in 2017-18) predicts {abs(s5['coef_A']['pctpell'])*10:.1f} points lower first-gen completion; a 10-point higher admission rate predicts "
                f"{abs(s5['coef_A']['adm_rate'])*10:.1f} points lower; doubling enrollment predicts {s5['coef_A']['log_ugds']*np.log(2)*100:+.1f} points. Spending is not in this model. "
                f"Adding FY2018-23 core spending per student (Model B) lifts R² from {s5['r2_A']:.2f} to {s5['r2_B']:.2f}: a 10% higher budget per student is associated with {s5['pp_per_10pct_spending']:+.2f} points.")

with tab_rank:
    f1, f2, f3, f4, f5 = st.columns(5)
    states = f1.multiselect("State", sorted(df["stabbr"].unique()))
    ctrl = f2.multiselect("Control", ["Public", "Private nonprofit"])
    carn = f3.multiselect("Carnegie group", sorted(df["carnegie_group"].unique()))
    min_ugds = f4.number_input("Min undergraduate enrollment (2017)", 0, int(df["ugds"].max()), 0, step=500)
    pell_rng = f5.slider("Pell share range (2017-18)", 0.0, 1.0, (0.0, 1.0), 0.05)
    d = df.copy()
    if states: d = d[d["stabbr"].isin(states)]
    if ctrl: d = d[d["control_label"].isin(ctrl)]
    if carn: d = d[d["carnegie_group"].isin(carn)]
    d = d[(d["ugds"] >= min_ugds) & (d["pctpell"].between(*pell_rng))].sort_values("residual_eb", ascending=False)
    d = d.merge(boot[["unitid", "p_top_decile", "boot_rank_p2_5", "boot_rank_p97_5"]], on="unitid", how="left")
    st.write(f"{len(d):,} schools match. Rank is by the shrunken residual among all {len(df):,} main-sample schools (raw rank shown for comparison); residuals in percentage points; bootstrap columns from 1,000 resamples.")
    show = d[["rank", "rank_raw", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "adm_rate", "firstgen_yr6_n", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts", "shrink_factor", "residual_eb_pct_pts", "p_top_decile", "boot_rank_p2_5", "boot_rank_p97_5", "exp_core_per_fte"]].rename(columns={
        "rank_raw": "Raw rank", "instnm": "School", "stabbr": "State", "control_label": "Control", "carnegie_group": "Carnegie", "ugds": "Undergrads 2017", "pctpell": "Pell share", "adm_rate": "Admit rate", "firstgen_yr6_n": "First-gen cohort",
        "firstgen_comp_orig_yr6_rt": "Actual", "predicted": "Predicted", "residual_pct_pts": "Raw resid (pts)", "shrink_factor": "Shrink", "residual_eb_pct_pts": "Shrunken resid (pts)", "p_top_decile": "P(top 10%)", "boot_rank_p2_5": "Rank lo", "boot_rank_p97_5": "Rank hi", "exp_core_per_fte": "Core $/FTE FY18-23"})
    st.dataframe(show.style.format({"rank": "{:.0f}", "Raw rank": "{:.0f}", "Pell share": "{:.2f}", "Admit rate": "{:.2f}", "Actual": "{:.3f}", "Predicted": "{:.3f}", "Raw resid (pts)": "{:+.1f}", "Shrink": "{:.2f}", "Shrunken resid (pts)": "{:+.1f}", "P(top 10%)": "{:.2f}", "Rank lo": "{:.0f}", "Rank hi": "{:.0f}",
                                   "Core $/FTE FY18-23": "${:,.0f}", "Undergrads 2017": "{:,.0f}", "First-gen cohort": "{:,.0f}"}), use_container_width=True, height=520, hide_index=True)
    st.caption(f"Shrinkage: each residual is multiplied by τ²/(τ²+σ²) where σ² is the binomial sampling variance of the school's rate given its first-gen cohort. τ = {s6['tau_pp']:.1f} points; median shrink {s6['shrink_median']:.2f}, minimum {s6['shrink_min']:.2f}. {s6['top_decile_left']} schools left the raw top decile after shrinkage, all with cohorts under 100.")
    st.download_button("Download filtered ranking (CSV)", show.to_csv(index=False).encode(), "ranked_schools_filtered.csv", "text/csv")
    with st.expander(f"Excluded schools ({len(sf)}): scored with Model A but not ranked"):
        st.write("Three groups the main model does not describe: Carnegie special-focus and tribal colleges (one structured program); campuses where more than half of Fall 2017 undergraduates were aged 25+ or exclusively online; "
                 "and schools whose Scorecard completion rates are implausible against their IPEDS graduation rate (both first-gen and non-first-gen rates below a quarter of it, e.g. San Jose State at 3.8%). Shown for transparency only.")
        st.dataframe(sf.sort_values(["excluded_reason", "residual"], ascending=[True, False])[["excluded_reason", "instnm", "stabbr", "control_label", "ugds", "ug25abv", "pct_distance", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts"]].rename(columns={
            "excluded_reason": "Why excluded", "instnm": "School", "stabbr": "State", "control_label": "Control", "ugds": "Undergrads", "ug25abv": "Age 25+ share", "pct_distance": "Online share", "pctpell": "Pell", "firstgen_comp_orig_yr6_rt": "Actual", "predicted": "Predicted", "residual_pct_pts": "Residual (pts)"})
                     .style.format({"Pell": "{:.2f}", "Age 25+ share": "{:.2f}", "Online share": "{:.2f}", "Actual": "{:.3f}", "Predicted": "{:.3f}", "Residual (pts)": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True)

with tab_spend:
    scope = st.radio("Comparison", ["All schools (pooled model deciles)", "Public (public-only model deciles)", "Private nonprofit (private-only model deciles)", "Carnegie: Doctoral", "Carnegie: Master's", "Carnegie: Baccalaureate"], horizontal=True)
    if scope.startswith("All"):
        top, bot = df[df.group == "top 10%"], df[df.group == "bottom 10%"]; tab = pf; note = "Deciles of the pooled Model A shrunken residual."
    elif scope.startswith("Carnegie"):
        g = scope.split(": ")[1]; dd = df[df.carnegie_group == g]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = s7["within_carnegie"][g]["per_fte"]
        note = f"Pooled-model deciles restricted to Carnegie {g} schools (top n = {len(top)}, bottom n = {len(bot)})."
    else:
        c = "Public" if scope.startswith("Public") else "Private nonprofit"
        dd = df[df.control_label == c]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = sec[c]["spending"]
        note = f"Medians below come from the {c}-only model's own deciles (n = {sec[c]['n_dec']} per decile); the chart uses pooled-model deciles restricted to {c} schools."
    st.write(f"{note} Dollars are IPEDS expenses per 12-month FTE averaged over FY2018-FY2023.")
    long = pd.DataFrame([{"category": lbl, "group": g, "median $ per FTE": dd_[f"{k}_per_fte"].median()} for k, lbl in CORE.items() for g, dd_ in [("top 10%", top), ("bottom 10%", bot)]])
    a, b = st.columns([3, 2])
    a.plotly_chart(px.bar(long, x="category", y="median $ per FTE", color="group", barmode="group", color_discrete_map={"top 10%": TOP, "bottom 10%": BOT}, title="Median dollars per FTE, FY2018-23 average").update_layout(height=430), use_container_width=True)
    t = pd.DataFrame([{"category": k, "top 10%": v["top10_median_$"], "bottom 10%": v["bottom10_median_$"], "ratio": v["median_ratio"], "Mann-Whitney p": v["mann_whitney_p"]} for k, v in tab.items() if k in list(CORE.values()) + ["Core (4 categories)"]])
    b.dataframe(t.style.format({"top 10%": "${:,.0f}", "bottom 10%": "${:,.0f}", "ratio": "{:.2f}×", "Mann-Whitney p": "{:.3f}"}), hide_index=True, use_container_width=True)
    with st.expander("Timing variants: does the gap depend on which fiscal years or on inflation?"):
        var = pd.DataFrame({"FY2018-23 nominal (main)": {k: v["median_ratio"] for k, v in pf.items()}, "FY2018-19 only": {k: v["median_ratio"] for k, v in s7["per_fte_fy1819"].items()},
                            "FY2018-23 in FY2023 $": {k: v["median_ratio"] for k, v in s7["per_fte_real"].items()}, "FY2023 only (mistimed)": {k: v["median_ratio"] for k, v in s7["per_fte_fy23_only"].items()}})
        st.dataframe(var.loc[list(CORE.values()) + ["Core (4 categories)"]].style.format("{:.2f}×"), use_container_width=True)
        st.caption("Median ratio top 10% / bottom 10%. Constant dollars use BLS CPI-U fiscal-year averages.")
    st.markdown(f"**Lead with the sector.** Public over-performers (public-only model) spent more in all four categories: instruction {sec['Public']['spending']['Instruction']['median_ratio']:.2f}×, academic support {sec['Public']['spending']['Academic support']['median_ratio']:.2f}×, student services {sec['Public']['spending']['Student services']['median_ratio']:.2f}× (p = {sec['Public']['spending']['Student services']['mann_whitney_p']:.3f}). "
                f"Private over-performers differ on instruction ({sec['Private nonprofit']['spending']['Instruction']['median_ratio']:.2f}×) and academic support ({sec['Private nonprofit']['spending']['Academic support']['median_ratio']:.2f}×) but not student services ({sec['Private nonprofit']['spending']['Student services']['median_ratio']:.2f}×). "
                f"Restricted to publics, the pooled-decile gaps are not significant, so the pooled headline is driven by private colleges.")
    st.markdown(f"**Pooled result.** Over-performers' median instruction spending was {pf['Instruction']['median_ratio']:.2f}× the under-performers' (${pf['Instruction']['top10_median_$']:,.0f} vs ${pf['Instruction']['bottom10_median_$']:,.0f}) and academic support {pf['Academic support']['median_ratio']:.2f}×, both p < 0.001. "
                f"Student-services dollars were not different ({pf['Student services']['median_ratio']:.2f}×, p = {pf['Student services']['mann_whitney_p']:.2f}). "
                "Budget shares are not shown as separate findings: they sum to 100%, so a higher instruction share is the same fact as more instruction dollars.")

with tab_school:
    names = (df.sort_values("instnm")["instnm"] + " (" + df.sort_values("instnm")["stabbr"] + ")").reset_index(drop=True)
    default = "California State University-Channel Islands (CA)"
    pick = st.selectbox("Choose a school", names, index=int(names[names == default].index[0]) if (names == default).any() else 0)
    row = df.sort_values("instnm").iloc[names[names == pick].index[0]]
    b_row = boot[boot.unitid == row.unitid].iloc[0]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Actual first-gen 6-yr completion", f"{row.firstgen_comp_orig_yr6_rt:.1%}")
    k2.metric("Predicted (Model A)", f"{row.predicted:.1%}")
    k3.metric("Shrunken residual", f"{row.residual_eb_pct_pts:+.1f} pts", f"raw {row.residual_pct_pts:+.1f}; rank {int(row['rank'])} of {len(df):,} (95% bootstrap: {b_row.boot_rank_p2_5:.0f}-{b_row.boot_rank_p97_5:.0f})")
    k4.metric("P(top 10%) across resamples", f"{b_row.p_top_decile:.0%}")
    st.write(f"{row.control_label} · {row.carnegie_group} · {int(row.ugds):,} undergrads (2017) · Pell share {row.pctpell:.0%} · admit rate {row.adm_rate:.0%} · first-gen share {row.first_gen:.0%} · "
             f"non-first-gen completion {row.not1stgen_comp_orig_yr6_rt:.1%} (gap {row.fg_gap*100:+.1f} pts)"
             + (f" · Opportunity Insights tier: {row.oi_tier_name}, mobility rate {row.oi_mr_kq5_pq1:.2%}" if row.oi_matched and pd.notna(row.oi_mr_kq5_pq1) else ""))
    peers = df[df.control_label == row.control_label]
    comp = pd.DataFrame({"category": list(CORE.values()), "this school": [row[f"{k}_per_fte"] for k in CORE], f"median {row.control_label}": [peers[f"{k}_per_fte"].median() for k in CORE],
                         f"median top 10% {row.control_label}": [peers[peers.group == "top 10%"][f"{k}_per_fte"].median() for k in CORE]})
    st.plotly_chart(px.bar(comp.melt(id_vars="category", var_name="who", value_name="$ per FTE"), x="category", y="$ per FTE", color="who", barmode="group", title="Spending per FTE (FY2018-23 avg) vs peers",
                           color_discrete_sequence=["#1d3557", "#a8dadc", TOP]).update_layout(height=420), use_container_width=True)
    near = df[(df.predicted - row.predicted).abs() < 0.03].sort_values("residual_eb", ascending=False).head(10)
    st.write("Schools with a similar predicted rate (±3 pts), ranked by residual: the most comparable over-performers.")
    st.dataframe(near[["rank", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts"]].rename(columns={"instnm": "School", "stabbr": "State", "control_label": "Control", "carnegie_group": "Carnegie", "ugds": "Undergrads", "pctpell": "Pell", "firstgen_comp_orig_yr6_rt": "Actual", "predicted": "Predicted", "residual_pct_pts": "Residual (pts)"})
                 .style.format({"Pell": "{:.2f}", "Actual": "{:.3f}", "Predicted": "{:.3f}", "Residual (pts)": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True)

with tab_method:
    st.markdown(f"""
**Timing.** The outcome is the NSLDS AY2017-18 entry cohort measured in AY2023-24 (Scorecard data dictionary cohort map). Predictors come from the 2017-18 Scorecard file; spending is the FY2018-FY2023 average per 12-month FTE from IPEDS; Carnegie is the 2018 classification. Control, level and Title IV status come from 2023 IPEDS and are assumed stable.

**Data.** College Scorecard Oct-2026 release (dated file; the undated download URL served a stale 2024 file); IPEDS HD2023, IC2023, F1718-F2223 finance (F1A public / F2 private nonprofit), EFIA2018-2023; Opportunity Insights mobility report cards (context only). Joined on UNITID in DuckDB. 4-year = bachelor's-dominant in both 2017-18 and today and IPEDS level 4+ years. For-profits excluded (non-comparable finance form).

**Sample.** {s5['n']:,} schools (Carnegie doctoral, master's, baccalaureate) after dropping privacy-suppressed outcomes, first-gen cohorts under 50, schools missing an entry-year predictor, and schools with fewer than 3 fiscal years of finance data. Scored but not ranked: {s5['n_special_focus']} special-focus / tribal schools, {s5['n_nontraditional']} campuses with more than 50% of undergraduates aged 25+ or exclusively online, and {s5['n_anomaly']} schools with implausible Scorecard completion rates.

**Models.** Pooled Model A, OLS: first-gen 6-year same-institution completion ~ Pell share + admission rate (open-admission = 1.0) + log enrollment + part-time share + first-gen share + private + HBCU + distance-only + Carnegie group. HC3 robust SEs. R² = {s5['r2_A']:.3f}. Residual = actual − predicted, then shrunk toward zero by τ²/(τ²+σ²) with σ² the binomial variance for the school's first-gen cohort (empirical Bayes; τ = {s6['tau_pp']:.1f} pts, median shrink {s6['shrink_median']:.2f}). The ranking model is {s5['main_model']}: Model A plus private × every trait, adopted because its shrunken ranking overlaps the public-only and private-only rankings' top deciles at {s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} versus {s5['ranking_comparison']['overlap_pool_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_pool_vs_sector_private']:.0%} for the pooled model (R² {s5['r2_main']:.3f}). Spending is left out on purpose so the spending comparison is not circular; Model B adds log core spending per FTE and the undergraduate share of FTE (R² {s5['r2_B']:.3f}).

**Sector slopes.** Joint Wald F test of the private × trait terms: F = {s5['joint_F_interactions']['F']:.2f}, p = {s5['joint_F_interactions']['p']:.1e}. A fractional-logit fit ranks schools the same (Spearman {s8['fractional_logit']['spearman_vs_main']:.3f}). Regressing the shrunken residual on log core spending plus instruction and academic-support shares: shares {'remain' if s7['level_vs_mix']['shares_hold'] else 'do not remain'} significant with the level fixed (p = {s7['level_vs_mix']['p']['instr_share']:.3f} / {s7['level_vs_mix']['p']['acad_share']:.3f}; R² {s7['level_vs_mix']['r2']:.3f}).

**Robustness.** Spending gaps hold with FY2018-19 spending only, in constant FY2023 dollars (BLS CPI-U), within each Carnegie group, and after dropping the {s7['n_cooks_dropped']} Cook's-distance-flagged schools; a Benjamini-Hochberg correction across all {s7['bh']['n_tests']} spending p-values keeps the instruction and academic-support gaps in every comparison and never the student-services gap. VIF: only the share aged 25+ exceeds 5 ({s5['vif']['ug25abv']:.2f}); Pell share and first-gen share correlate at {s5['corr_pell_firstgen']:.2f} with VIFs of {s5['vif']['pctpell']:.2f} and {s5['vif']['first_gen']:.2f}. Bootstrap of 1,000 resamples (shrinkage re-applied each draw): top-decile schools stay top-decile {bs['mean_p_top_among_point_top']:.0%} of the time; two random resamples share {bs['mean_pairwise_top_decile_overlap']:.0%} of their top decile. Separate public and private models rank schools consistently with the pooled model (Spearman {sec['Public']['spearman_vs_pooled']:.2f} / {sec['Private nonprofit']['spearman_vs_pooled']:.2f}). Dropping the largest 5% of schools: Spearman {s8['drop5']['spearman']:.3f} (weak test, kept because the brief asked).

**What changed after review.** The first build used a stale Scorecard file, 2024 traits, FY2023-only spending and no Carnegie control. Only {s6['top20_overlap_vs_v1']} of its top-20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}); the instruction and academic-support spending pattern held.

**Limitations.**
- *School-level data.* We observe institutions, not students. A school can over-perform because of program mix or who it enrolls in ways the predictors do not capture.
- *Correlation only.* Spending differences describe what over-performers look like; they do not show that moving dollars would raise completion.
- *Outcome definition.* Completion at the *same* institution within 6 years for federal-aid students; transfers who finish elsewhere count as non-completers.
- *Suppression bias.* Privacy-suppressed outcomes remove the smallest schools.
- *Budget shares* sum to 100% and are therefore not reported as findings separate from dollar differences.
    """)
