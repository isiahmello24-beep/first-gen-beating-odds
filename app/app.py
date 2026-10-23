"""Streamlit dashboard: which 4-year colleges graduate first-gen students above prediction, and what they spend on.

Run from the project root:  streamlit run app/app.py
Reads data/clean/analysis_scored.parquet and reports/results.json produced by src/05-08.
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
LABELS = {"pctpell": "Pell share", "adm_rate": "Admission rate", "log_ugds": "log(enrollment)", "pptug_ef": "Part-time share", "first_gen": "First-gen share",
          "private": "Private nonprofit", "hbcu_flag": "HBCU", "distance_only": "Distance-only"}
TOP, BOT = "#2a9d8f", "#e76f51"


@st.cache_data
def load():
    df = pd.read_parquet(ROOT / "data/clean/analysis_scored.parquet")
    res = json.loads((ROOT / "reports/results.json").read_text())
    return df, res


df, res = load()
s5, s6, s7, s8 = res["step5"], res["step6"], res["step7"], res["step8"]

st.title("Which 4-year colleges graduate first-generation students above prediction?")
st.caption("College Scorecard + IPEDS 2023 + Opportunity Insights, joined on UNITID. Outcome: share of first-gen federal-aid students completing at the same school within 6 years. "
           "School-level, correlational. See Methods tab.")

tab_over, tab_rank, tab_spend, tab_school, tab_method = st.tabs(["Overview", "Rankings", "Spending comparison", "School lookup", "Methods & limitations"])

# ------------------------------------------------------------------ Overview
with tab_over:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Schools in model", f"{s5['n']:,}")
    c2.metric("R² (Model A)", f"{s5['r2_A']:.2f}")
    c3.metric("Mean first-gen 6-yr completion", f"{s5['outcome_mean']:.1%}")
    c4.metric("Top-decile residual cut", f"+{s6['top_decile_cut_pp']:.1f} pts")
    left, right = st.columns([3, 2])
    with left:
        fig = px.scatter(df, x="predicted", y="firstgen_comp_orig_yr6_rt", color="group", hover_name="instnm",
                         hover_data={"stabbr": True, "control_label": True, "ugds": ":,", "pctpell": ":.2f", "predicted": ":.3f", "firstgen_comp_orig_yr6_rt": ":.3f", "group": False},
                         color_discrete_map={"top 10%": TOP, "bottom 10%": BOT, "middle": "#8d99ae"}, opacity=.65,
                         labels={"predicted": "Predicted completion (Model A)", "firstgen_comp_orig_yr6_rt": "Actual first-gen completion"}, title="Actual vs predicted: distance above the line = residual")
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dash", color="black"))
        fig.update_layout(height=520, legend_title="Residual group")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        co = pd.DataFrame({"term": [LABELS[k] for k in LABELS], "coef": [s5["coef_A"][k] for k in LABELS], "se": [s5["se_A"][k] for k in LABELS]})
        figc = go.Figure(go.Bar(x=co["coef"], y=co["term"], orientation="h", error_x=dict(type="data", array=1.96 * co["se"]), marker_color="#457b9d"))
        figc.update_layout(title="Model A coefficients (±95% CI, HC3)", xaxis_title="Change in completion rate per 1-unit change", height=520, yaxis=dict(autorange="reversed"))
        st.plotly_chart(figc, use_container_width=True)
    st.markdown(f"**Reading the model.** A 10-point higher Pell share predicts {abs(s5['coef_A']['pctpell'])*10:.1f} points lower first-gen completion; a 10-point higher admission rate predicts "
                f"{abs(s5['coef_A']['adm_rate'])*10:.1f} points lower; doubling enrollment predicts {s5['coef_A']['log_ugds']*np.log(2)*100:+.1f} points. "
                f"Adding spending per student (Model B) lifts R² from {s5['r2_A']:.2f} to {s5['r2_B']:.2f}: a 10% increase in core spending per FTE is associated with {s5['pp_per_10pct_spending']:+.2f} points.")

# ------------------------------------------------------------------ Rankings
with tab_rank:
    f1, f2, f3, f4 = st.columns(4)
    states = f1.multiselect("State", sorted(df["stabbr"].unique()))
    ctrl = f2.multiselect("Control", ["Public", "Private nonprofit"])
    min_ugds = f3.number_input("Min undergraduate enrollment", 0, int(df["ugds"].max()), 1000, step=500)
    pell_rng = f4.slider("Pell share range", 0.0, 1.0, (0.0, 1.0), 0.05)
    d = df.copy()
    if states: d = d[d["stabbr"].isin(states)]
    if ctrl: d = d[d["control_label"].isin(ctrl)]
    d = d[(d["ugds"] >= min_ugds) & (d["pctpell"].between(*pell_rng))]
    d = d.sort_values("residual", ascending=False)
    st.write(f"{len(d):,} schools match. Rank is among all {len(df):,} schools; residual in percentage points.")
    show = d[["rank", "instnm", "stabbr", "control_label", "ugds", "pctpell", "adm_rate", "first_gen", "firstgen_yr6_n", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts", "exp_core_per_fte"]].rename(columns={
        "instnm": "School", "stabbr": "State", "control_label": "Control", "ugds": "Undergrads", "pctpell": "Pell share", "adm_rate": "Admit rate", "first_gen": "First-gen share",
        "firstgen_yr6_n": "First-gen cohort", "firstgen_comp_orig_yr6_rt": "Actual", "predicted": "Predicted", "residual_pct_pts": "Residual (pts)", "exp_core_per_fte": "Core $/FTE"})
    st.dataframe(show.style.format({"Pell share": "{:.2f}", "Admit rate": "{:.2f}", "First-gen share": "{:.2f}", "Actual": "{:.3f}", "Predicted": "{:.3f}", "Residual (pts)": "{:+.1f}", "Core $/FTE": "${:,.0f}", "Undergrads": "{:,.0f}", "First-gen cohort": "{:,.0f}"}),
                 use_container_width=True, height=560, hide_index=True)
    st.download_button("Download filtered ranking (CSV)", show.to_csv(index=False).encode(), "ranked_schools_filtered.csv", "text/csv")
    st.info("Tip: the very top of the unfiltered list is small nursing and health-science colleges, where almost every student is in one structured program. Raise the minimum enrollment to see comprehensive universities.")

# ------------------------------------------------------------------ Spending
with tab_spend:
    scope = st.radio("Compare within", ["All schools", "Public", "Private nonprofit"], horizontal=True)
    top, bot = df[df.group == "top 10%"], df[df.group == "bottom 10%"]
    if scope != "All schools":
        top, bot = top[top.control_label == scope], bot[bot.control_label == scope]
    st.write(f"Top 10% residual schools (n={len(top)}) vs bottom 10% (n={len(bot)}). Fiscal year 2022-23 IPEDS expenses per 12-month FTE.")
    rows = []
    for k, lbl in CORE.items():
        for grp, dd in [("top 10%", top), ("bottom 10%", bot)]:
            rows.append({"category": lbl, "group": grp, "median $ per FTE": dd[f"{k}_per_fte"].median(), "mean share of core": dd[f"{k}_share_core"].mean() * 100})
    long = pd.DataFrame(rows)
    a, b = st.columns(2)
    cmap = {"top 10%": TOP, "bottom 10%": BOT}
    a.plotly_chart(px.bar(long, x="category", y="median $ per FTE", color="group", barmode="group", color_discrete_map=cmap, title="Median dollars per FTE").update_layout(height=430), use_container_width=True)
    b.plotly_chart(px.bar(long, x="category", y="mean share of core", color="group", barmode="group", color_discrete_map=cmap, title="Share of core spending (%)").update_layout(height=430), use_container_width=True)
    piv = long.pivot(index="category", columns="group", values="median $ per FTE")
    piv["ratio top/bottom"] = piv["top 10%"] / piv["bottom 10%"]
    st.dataframe(piv.style.format({"top 10%": "${:,.0f}", "bottom 10%": "${:,.0f}", "ratio top/bottom": "{:.2f}×"}), use_container_width=True)
    p = s7["per_fte"]
    st.markdown(f"**Across all schools**, over-performers' median instruction spending is {p['Instruction']['median_ratio']:.2f}× the under-performers' (${p['Instruction']['top10_median_$']:,.0f} vs ${p['Instruction']['bottom10_median_$']:,.0f}, Mann-Whitney p {p['Instruction']['mann_whitney_p']:.3g}) "
                f"and academic support is {p['Academic support']['median_ratio']:.2f}×. Student services dollars are similar ({p['Student services']['median_ratio']:.2f}×), "
                f"but under-performers devote a larger **share** of core spending to student services ({s7['share_core']['Student services']['bottom10_mean_share']:.1%} vs {s7['share_core']['Student services']['top10_mean_share']:.1%}). "
                f"Robustness (drop largest 5%): instruction ratio {s8['spending_trimmed']['Instruction']['median_ratio']:.2f}×, academic support {s8['spending_trimmed']['Academic support']['median_ratio']:.2f}×.")

# ------------------------------------------------------------------ School lookup
with tab_school:
    names = df.sort_values("instnm")["instnm"] + " (" + df.sort_values("instnm")["stabbr"] + ")"
    pick = st.selectbox("Choose a school", names, index=int(np.where(names.values == "University of Houston-Clear Lake (TX)")[0][0]) if (names == "University of Houston-Clear Lake (TX)").any() else 0)
    row = df.iloc[names.index[names == pick][0]]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Actual first-gen 6-yr completion", f"{row.firstgen_comp_orig_yr6_rt:.1%}")
    k2.metric("Predicted (Model A)", f"{row.predicted:.1%}")
    k3.metric("Residual", f"{row.residual_pct_pts:+.1f} pts", f"rank {int(row['rank'])} of {len(df):,}")
    k4.metric("First-gen cohort", f"{int(row.firstgen_yr6_n):,}")
    st.write(f"{row.control_label} · {int(row.ugds):,} undergrads · Pell share {row.pctpell:.0%} · admit rate {row.adm_rate:.0%} · first-gen share {row.first_gen:.0%} · "
             f"non-first-gen completion {row.not1stgen_comp_orig_yr6_rt:.1%} (gap {row.fg_gap*100:+.1f} pts)"
             + (f" · Opportunity Insights tier: {row.oi_tier_name}, mobility rate {row.oi_mr_kq5_pq1:.2%}" if row.oi_matched and pd.notna(row.oi_mr_kq5_pq1) else ""))
    peers = df[(df.control_label == row.control_label)]
    comp = pd.DataFrame({"category": list(CORE.values()), "this school": [row[f"{k}_per_fte"] for k in CORE], f"median {row.control_label}": [peers[f"{k}_per_fte"].median() for k in CORE],
                         "median top 10%": [df[df.group == "top 10%"][f"{k}_per_fte"].median() for k in CORE]})
    figp = px.bar(comp.melt(id_vars="category", var_name="who", value_name="$ per FTE"), x="category", y="$ per FTE", color="who", barmode="group", title="Spending per FTE vs peers",
                  color_discrete_sequence=["#1d3557", "#a8dadc", TOP])
    st.plotly_chart(figp.update_layout(height=420), use_container_width=True)
    near = df[(df.predicted - row.predicted).abs() < 0.03].sort_values("residual", ascending=False).head(10)
    st.write("Schools with a similar predicted rate (±3 pts), ranked by residual: the most comparable over-performers.")
    st.dataframe(near[["rank", "instnm", "stabbr", "control_label", "ugds", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts"]].rename(columns={"instnm": "School", "stabbr": "State", "control_label": "Control", "ugds": "Undergrads", "pctpell": "Pell", "firstgen_comp_orig_yr6_rt": "Actual", "predicted": "Predicted", "residual_pct_pts": "Residual (pts)"})
                 .style.format({"Pell": "{:.2f}", "Actual": "{:.3f}", "Predicted": "{:.3f}", "Residual (pts)": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ Methods
with tab_method:
    st.markdown(f"""
**Data.** College Scorecard most-recent-cohorts institution file; IPEDS 2023 HD, IC, EFIA and FY2022-23 finance (F1A public / F2 private nonprofit); Opportunity Insights mobility report cards (1980-82 birth cohorts).
Joined on UNITID in DuckDB; Opportunity Insights reached via OPEID. 4-year = Scorecard predominant degree bachelor's and IPEDS level 4+ years. For-profits excluded (non-comparable finance form).

**Sample.** {res['step5']['n']:,} schools after dropping privacy-suppressed outcomes, first-gen cohorts under 50, and schools missing a core predictor.

**Model A.** OLS: first-gen 6-year same-institution completion ~ Pell share + admission rate (open-admission = 1.0) + log enrollment + part-time share + first-gen share + private + HBCU + distance-only. HC3 robust SEs. R² = {s5['r2_A']:.3f}.
Residual = actual − predicted. Spending is left out of Model A on purpose so the spending comparison is not conditioned on it; Model B adds log core spending per FTE (R² {s5['r2_B']:.3f}).

**Robustness.** Dropping the largest 5% of schools ({s8['n_dropped']} schools over {s8['ugds_cut']:,.0f} undergrads): Spearman {s8['spearman']:.3f} between rankings, top-decile overlap {s8['top_decile_overlap']:.0%}, same spending pattern.

**Limitations.**
- *School-level data.* We observe institutions, not students. A school can over-perform because of what it does or because of who it enrolls in ways Pell share and admission rate do not capture (program mix, commuter vs residential, transfer-in students).
- *Correlation only.* Spending differences describe what over-performers look like; they do not show that moving dollars into instruction would raise completion.
- *Timing.* The completion cohort entered roughly 6-8 years before the FY2023 finance data; spending is assumed stable.
- *Outcome definition.* Completion at the *same* institution within 6 years for federal-aid students; transfers who finish elsewhere count as non-completers here.
- *Small specialty colleges* (nursing, health sciences) top the raw ranking because nearly all students are in one structured program. Use the enrollment filter.
- *Suppression bias.* Privacy-suppressed outcomes remove the smallest schools.
    """)
