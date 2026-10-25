"""Streamlit dashboard: which 4-year colleges graduate first-gen students above prediction, and what they spent on.

Run from the project root:  streamlit run app/app.py
Reads data/clean/analysis_scored.parquet, data/clean/bootstrap_ranks.csv and reports/results.json (from src/05-08).
Visual style: dark analytics panels (uppercase panel headers, neon cyan bars, pink lines, colored KPI tiles).
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="First-Gen Completion: Over-performing Colleges", layout="wide", page_icon="🎓")

# ------------------------------------------------------------------ palette (reference look: cyan bars, pink lines)
CYAN, PINK, PURPLE, LIME, AMBER, MUTED = "#38bdf8", "#f9a8c9", "#c084fc", "#bef264", "#fbbf24", "#6b7280"
INK, INK2, GRID, SURFACE = "#e6e9ef", "#9aa3b2", "rgba(255,255,255,0.08)", "#14171c"
CORE = {"exp_instruction": "Instruction", "exp_academic_support": "Academic support", "exp_student_services": "Student services", "exp_institutional_support": "Institutional support"}
CARN = "C(carnegie_group, Treatment(reference=\"Master's\"))"
LABELS = {**{f"private:{t}": f"Private × {v}" for t, v in {"pctpell": "Pell share", "adm_rate": "admission rate", "log_ugds": "log(enrollment)", "pptug_ef": "part-time share", "first_gen": "first-gen share", "ug25abv": "share aged 25+", "pct_distance": "share online", "hbcu_flag": "HBCU"}.items()},
          "pctpell": "Pell share", "adm_rate": "Admission rate", "log_ugds": "log(enrollment)", "pptug_ef": "Part-time share", "first_gen": "First-gen share",
          "ug25abv": "Share aged 25+", "pct_distance": "Share exclusively online", "private": "Private nonprofit", "hbcu_flag": "HBCU", f"{CARN}[T.Doctoral]": "Carnegie: Doctoral", f"{CARN}[T.Baccalaureate]": "Carnegie: Baccalaureate"}

st.markdown(f"""
<style>
  .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }}
  h1 {{ font-weight: 800; letter-spacing: .02em; text-transform: uppercase; font-size: 1.45rem !important; color: {INK}; margin-bottom: .2rem; }}
  h1 span.dim {{ color: {INK2}; font-weight: 600; }}
  .panel-head {{ display:flex; justify-content:space-between; align-items:center; background:#1b1f26; border:1px solid #262b33; border-bottom:none;
                 padding:.45rem .8rem; border-radius:8px 8px 0 0; margin-top:.6rem; }}
  .panel-head .t {{ font-size:.72rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; color:{INK}; }}
  .panel-head .o {{ font-size:.66rem; letter-spacing:.12em; text-transform:uppercase; color:{INK2}; }}
  .panel-body {{ background:{SURFACE}; border:1px solid #262b33; border-top:none; border-radius:0 0 8px 8px; padding:.4rem .6rem .2rem .6rem; }}
  .kpi {{ padding:.2rem .2rem .6rem .2rem; }}
  .kpi .l {{ font-size:.8rem; letter-spacing:.04em; padding-bottom:.25rem; border-bottom:2px solid; margin-bottom:.35rem; }}
  .kpi .v {{ font-size:2.1rem; font-weight:800; line-height:1.05; }}
  .kpi .s {{ font-size:.72rem; color:{INK2}; margin-top:.25rem; }}
  div[data-testid="stTabs"] button {{ text-transform:uppercase; letter-spacing:.08em; font-size:.75rem; font-weight:700; }}
  div[data-testid="stDataFrame"] {{ border:1px solid #262b33; border-radius:8px; }}
  .stCaption, .stMarkdown small {{ color:{INK2}; }}
</style>""", unsafe_allow_html=True)


def panel_head(title: str, right: str = "⚙ OPTIONS"):
    st.markdown(f'<div class="panel-head"><span class="t">{title}</span><span class="o">{right}</span></div>', unsafe_allow_html=True)


def kpi(col, label, value, sub, color):
    col.markdown(f'<div class="kpi"><div class="l" style="color:{color};border-color:{color}">{label}</div><div class="v" style="color:{color}">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def dark(fig, height=360, legend=True):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=INK2, size=12), height=height,
                      margin=dict(l=10, r=10, t=36, b=10), title=None,
                      legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(color=INK2, size=11), bgcolor="rgba(0,0,0,0)") if legend else dict(),
                      showlegend=legend, hoverlabel=dict(bgcolor="#f3f4f6", font_color="#111827", bordercolor="#f3f4f6"))
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=INK2), title_font=dict(color=INK2, size=11))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=INK2), title_font=dict(color=INK2, size=11))
    return fig


def shrink(resid, pred, n):
    pred = pred.clip(0.05, 0.95); sigma2 = pred * (1 - pred) / n
    tau2 = max(float(resid.var() - sigma2.mean()), 1e-6)
    return resid * tau2 / (tau2 + sigma2)


def decile_groups(d, resid_col):
    dec = pd.qcut(d[resid_col], 10, labels=range(1, 11)).astype(int)
    return d[dec == 10], d[dec == 1]


def compare_table(top, bot):
    rows = []
    for k, lbl in list(CORE.items()) + [("exp_core", "Core (4 categories)")]:
        a, b = top[f"{k}_per_fte"], bot[f"{k}_per_fte"]
        rows.append({"category": lbl, "top 10%": a.median(), "bottom 10%": b.median(), "ratio": a.median() / b.median(), "Mann-Whitney p": stats.mannwhitneyu(a, b, alternative="two-sided").pvalue})
    return pd.DataFrame(rows)


def spend_bar(top, bot, height=340):
    cats = list(CORE.values())
    fig = go.Figure()
    fig.add_bar(name="Top 10%", x=cats, y=[top[f"{k}_per_fte"].median() for k in CORE], marker_color=CYAN, marker_line_width=0, text=[f"${top[f'{k}_per_fte'].median():,.0f}" for k in CORE], textposition="outside", textfont=dict(color=INK2, size=10))
    fig.add_bar(name="Bottom 10%", x=cats, y=[bot[f"{k}_per_fte"].median() for k in CORE], marker_color=PINK, marker_line_width=0, text=[f"${bot[f'{k}_per_fte'].median():,.0f}" for k in CORE], textposition="outside", textfont=dict(color=INK2, size=10))
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, yaxis_title="Median $ per FTE, FY2018-23")
    return dark(fig, height)


FILES = [ROOT / "data/clean/analysis_scored.parquet", ROOT / "data/clean/bootstrap_ranks.csv", ROOT / "reports/results.json"]


@st.cache_data
def load(_mtimes: tuple):
    full = pd.read_parquet(FILES[0]); boot = pd.read_csv(FILES[1]); res = json.loads(FILES[2].read_text())
    return full, boot, res


full, boot, res = load(tuple(f.stat().st_mtime for f in FILES))
df = full[full.in_main == 1].copy(); sf = full[full.in_main == 0].copy()
s5, s6, s7, s8 = res["step5"], res["step6"], res["step7"], res["step8"]
pf, bs, sec, lm = s7["per_fte"], s8["bootstrap"], s8["sector"], s7["level_vs_mix"]
pp_double = lm["coef"]["log_core_per_fte"] * np.log(2) * 100

st.markdown('<h1>First-gen completion: <span class="dim">colleges that beat prediction, 2017-18 cohort</span> ▾</h1>', unsafe_allow_html=True)
st.caption("College Scorecard (Oct 2026) · IPEDS FY2018-23 · Opportunity Insights · joined on UNITID. Outcome: first-gen federal-aid students who entered in 2017-18 and completed at the same school within 6 years. "
           "Predictors and spending are measured during the cohort's own years. School-level, correlational. See Methods.")
tab_over, tab_rank, tab_spend, tab_school, tab_method = st.tabs(["Overview", "Rankings", "Spending comparison", "School lookup", "Methods & limitations"])

# ------------------------------------------------------------------ Overview
with tab_over:
    k1, k2, k3, k4, k5 = st.columns(5)
    kpi(k1, "Schools in model", f"{s5['n']:,}", f"+{s5['n_excluded']} excluded, scored separately", CYAN)
    kpi(k2, f"R² · {s5['main_model']}", f"{s5['r2_main']:.2f}", f"pooled Model A {s5['r2_A']:.2f}", PURPLE)
    kpi(k3, "Mean first-gen 6-yr completion", f"{s5['outcome_mean']:.1%}", f"SD {s5['outcome_sd']:.1%}", PINK)
    kpi(k4, "Top-decile cut", f"+{s6['top_decile_cut_pp']:.1f} pts", f"{s6['top_decile_n']} schools, shrunken residual", LIME)
    kpi(k5, "Spending explains", f"{lm['r2']*100:.1f}%", "of over-performance · R² of residual on level + mix (reports/07 §7b)", AMBER)

    a, b = st.columns(2)
    with a:
        panel_head("Actual vs predicted · distance above the line = residual")
        with st.container():
            fig = go.Figure()
            for g, c, nm in [("middle", MUTED, "middle 80%"), ("bottom 10%", PINK, "bottom 10%"), ("top 10%", CYAN, "top 10%")]:
                d = df[df.group == g]
                fig.add_scatter(x=d.predicted, y=d.firstgen_comp_orig_yr6_rt, mode="markers", name=nm, marker=dict(color=c, size=6, opacity=.75 if g != "middle" else .45, line=dict(width=0)),
                                customdata=np.stack([d.instnm, d.stabbr, d.control_label, d.carnegie_group, d.ugds, d.pctpell], axis=1),
                                hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>%{customdata[2]} · %{customdata[3]}<br>undergrads %{customdata[4]:,} · Pell %{customdata[5]:.0%}<br>predicted %{x:.1%} · actual %{y:.1%}<extra></extra>")
            fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=PINK, dash="dash", width=1.5), name="actual = predicted", hoverinfo="skip")
            fig.update_layout(xaxis_title="Predicted completion", yaxis_title="Actual first-gen completion", xaxis=dict(range=[0.05, 1], tickformat=".0%"), yaxis=dict(range=[0, 1], tickformat=".0%"))
            st.plotly_chart(dark(fig, 400), use_container_width=True)
    with b:
        panel_head("Residual distribution · shrunken, percentage points")
        with st.container():
            r = df.residual_eb_pct_pts
            fig = go.Figure(go.Histogram(x=r, nbinsx=45, marker_color=CYAN, marker_line=dict(color="#0b0d10", width=1), name="schools", hovertemplate="residual %{x} pts: %{y} schools<extra></extra>"))
            for v, lab, c in [(s6["top_decile_cut_pp"], f"top-decile cut +{s6['top_decile_cut_pp']:.1f}", LIME), (s6["bottom_decile_cut_pp"], f"bottom-decile cut {s6['bottom_decile_cut_pp']:+.1f}", PINK)]:
                fig.add_vline(x=v, line=dict(color=c, dash="dash", width=1.5), annotation_text=lab, annotation_position="top", annotation_font=dict(color=c, size=10))
            fig.update_layout(xaxis_title="Actual − predicted (pts)", yaxis_title="Schools", bargap=0.08)
            st.plotly_chart(dark(fig, 400, legend=False), use_container_width=True)

    c, d_ = st.columns(2)
    with c:
        panel_head("Pooled model coefficients · ±95% CI, HC3", "one slope per trait")
        terms = [k for k in LABELS if k in s5["coef_A"]]
        co = pd.DataFrame({"term": [LABELS[k] for k in terms], "coef": [s5["coef_A"][k] for k in terms], "se": [s5["se_A"][k] for k in terms]})
        fig = go.Figure(go.Bar(x=co.coef, y=co.term, orientation="h", marker_color=[CYAN if v > 0 else PINK for v in co.coef], marker_line_width=0,
                               error_x=dict(type="data", array=1.96 * co.se, color=INK2, thickness=1.2), hovertemplate="%{y}: %{x:+.3f}<extra></extra>"))
        fig.update_layout(xaxis_title="Change in completion rate per 1-unit change", yaxis=dict(autorange="reversed"), bargap=0.35)
        st.plotly_chart(dark(fig, 400, legend=False), use_container_width=True)
        st.caption(f"The ranking uses {s5['main_model']}, which lets every slope differ between public and private schools; its coefficients are in reports/05_regression.md.")
    with d_:
        panel_head("Spending · top vs bottom decile", "median $ per FTE")
        st.plotly_chart(spend_bar(df[df.group == "top 10%"], df[df.group == "bottom 10%"], 400), use_container_width=True)
        st.caption(f"Spending level and mix together explain {lm['r2']*100:.1f}% of the residual: one SD more academic-support share ≈ {lm['pp_per_sd_acad_share']:+.1f} pts, one SD more instruction share ≈ {lm['pp_per_sd_instr_share']:+.1f}, doubling core spending ≈ {pp_double:+.0f}, against a top-decile cut of +{s6['top_decile_cut_pp']:.1f}. Most over-performance sits outside budget data: use the Rankings tab to find peers.")

# ------------------------------------------------------------------ Rankings
with tab_rank:
    panel_head("Ranked schools · shrunken residual of the main model", f"{len(df):,} schools")
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
    st.caption(f"{len(d):,} schools match. Rank is by the shrunken residual among all {len(df):,} main-sample schools (raw rank shown for comparison); residuals in percentage points; bootstrap columns from 1,000 resamples.")
    show = d[["rank", "rank_raw", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "adm_rate", "firstgen_yr6_n", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts", "shrink_factor", "residual_eb_pct_pts", "p_top_decile", "boot_rank_p2_5", "boot_rank_p97_5", "exp_core_per_fte"]].rename(columns={
        "rank_raw": "Raw rank", "instnm": "School", "stabbr": "State", "control_label": "Control", "carnegie_group": "Carnegie", "ugds": "Undergrads 2017", "pctpell": "Pell share", "adm_rate": "Admit rate", "firstgen_yr6_n": "First-gen cohort",
        "firstgen_comp_orig_yr6_rt": "Actual", "predicted": "Predicted", "residual_pct_pts": "Raw resid (pts)", "shrink_factor": "Shrink", "residual_eb_pct_pts": "Shrunken resid (pts)", "p_top_decile": "P(top 10%)", "boot_rank_p2_5": "Rank lo", "boot_rank_p97_5": "Rank hi", "exp_core_per_fte": "Core $/FTE FY18-23"})
    st.dataframe(show.style.format({"rank": "{:.0f}", "Raw rank": "{:.0f}", "Pell share": "{:.2f}", "Admit rate": "{:.2f}", "Actual": "{:.3f}", "Predicted": "{:.3f}", "Raw resid (pts)": "{:+.1f}", "Shrink": "{:.2f}", "Shrunken resid (pts)": "{:+.1f}", "P(top 10%)": "{:.2f}", "Rank lo": "{:.0f}", "Rank hi": "{:.0f}",
                                   "Core $/FTE FY18-23": "${:,.0f}", "Undergrads 2017": "{:,.0f}", "First-gen cohort": "{:,.0f}"}), use_container_width=True, height=520, hide_index=True)
    st.download_button("Download filtered ranking (CSV)", show.to_csv(index=False).encode(), "ranked_schools_filtered.csv", "text/csv")
    st.caption(f"Shrinkage: each residual is multiplied by τ²/(τ²+σ²) where σ² is the binomial sampling variance of the school's rate given its first-gen cohort. τ = {s6['tau_pp']:.1f} points; median shrink {s6['shrink_median']:.2f}, minimum {s6['shrink_min']:.2f}. {s6['top_decile_left']} schools left the raw top decile after shrinkage, all with cohorts under 100.")
    with st.expander(f"Excluded schools ({len(sf)}): scored with the main model but not ranked"):
        st.write("Three groups the main model does not describe: Carnegie special-focus and tribal colleges (one structured program); campuses where more than half of Fall 2017 undergraduates were aged 25+ or exclusively online; "
                 "and schools whose Scorecard completion rates are implausible against their IPEDS graduation rate (both first-gen and non-first-gen rates below a quarter of it, e.g. San Jose State at 3.8%). Shown for transparency only.")
        st.dataframe(sf.sort_values(["excluded_reason", "residual"], ascending=[True, False])[["excluded_reason", "instnm", "stabbr", "control_label", "ugds", "ug25abv", "pct_distance", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts"]].rename(columns={
            "excluded_reason": "Why excluded", "instnm": "School", "stabbr": "State", "control_label": "Control", "ugds": "Undergrads", "ug25abv": "Age 25+ share", "pct_distance": "Online share", "pctpell": "Pell", "firstgen_comp_orig_yr6_rt": "Actual", "predicted": "Predicted", "residual_pct_pts": "Residual (pts)"})
                     .style.format({"Pell": "{:.2f}", "Age 25+ share": "{:.2f}", "Online share": "{:.2f}", "Actual": "{:.3f}", "Predicted": "{:.3f}", "Residual (pts)": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ Spending
with tab_spend:
    panel_head("Spending comparison · top 10% vs bottom 10% by residual", "IPEDS $ per FTE, FY2018-23")
    scope = st.radio("Comparison", [f"Main ranking: {s5['main_model']} deciles (default, matches the README)", "Pooled Model A deciles (single slope per trait)", "Public (public-only model deciles)", "Private nonprofit (private-only model deciles)", "Carnegie: Doctoral", "Carnegie: Master's", "Carnegie: Baccalaureate"], horizontal=True)
    if scope.startswith("Main"):
        top, bot = df[df.group == "top 10%"], df[df.group == "bottom 10%"]; tab = pf; note = f"Top and bottom deciles of the shrunken residual from the main model ({s5['main_model']}): the ranking shown on the Rankings tab and in the README."
    elif scope.startswith("Pooled"):
        dp = df.assign(resid_pooled_eb=shrink(df["residual_pooled"], df["predicted_pooled"], df["firstgen_yr6_n"]))
        top, bot = decile_groups(dp, "resid_pooled_eb"); tab = None
        note = "Deciles of the shrunken residual from the pooled Model A (one slope per trait, computed here). Kept for comparison; the interaction model is the main ranking."
    elif scope.startswith("Carnegie"):
        g = scope.split(": ")[1]; dd = df[df.carnegie_group == g]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = s7["within_carnegie"][g]["per_fte"]
        note = f"Main-ranking deciles restricted to Carnegie {g} schools (top n = {len(top)}, bottom n = {len(bot)})."
    else:
        c = "Public" if scope.startswith("Public") else "Private nonprofit"
        dd = df[df.control_label == c]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = sec[c]["spending"]
        note = f"Medians in the table come from the {c}-only model's own deciles (n = {sec[c]['n_dec']} per decile); the chart uses main-ranking deciles restricted to {c} schools."
    st.caption(note)
    a, b = st.columns([3, 2])
    a.plotly_chart(spend_bar(top, bot, 420), use_container_width=True)
    t = compare_table(top, bot) if tab is None else pd.DataFrame([{"category": k, "top 10%": v["top10_median_$"], "bottom 10%": v["bottom10_median_$"], "ratio": v["median_ratio"], "Mann-Whitney p": v["mann_whitney_p"]} for k, v in tab.items() if k in list(CORE.values()) + ["Core (4 categories)"]])
    b.dataframe(t.style.format({"top 10%": "${:,.0f}", "bottom 10%": "${:,.0f}", "ratio": "{:.2f}×", "Mann-Whitney p": "{:.3f}"}), hide_index=True, use_container_width=True)
    with st.expander("Timing variants: does the gap depend on which fiscal years or on inflation?"):
        var = pd.DataFrame({"FY2018-23 nominal (main)": {k: v["median_ratio"] for k, v in pf.items()}, "FY2018-19 only": {k: v["median_ratio"] for k, v in s7["per_fte_fy1819"].items()},
                            "FY2018-23 in FY2023 $": {k: v["median_ratio"] for k, v in s7["per_fte_real"].items()}, "FY2023 only (mistimed)": {k: v["median_ratio"] for k, v in s7["per_fte_fy23_only"].items()}})
        st.dataframe(var.loc[list(CORE.values()) + ["Core (4 categories)"]].style.format("{:.2f}×"), use_container_width=True)
        st.caption("Median ratio top 10% / bottom 10%. Constant dollars use BLS CPI-U fiscal-year averages.")
    st.markdown(f"**Lead with the sector.** Public over-performers (public-only model) spent more in all four categories: instruction {sec['Public']['spending']['Instruction']['median_ratio']:.2f}×, academic support {sec['Public']['spending']['Academic support']['median_ratio']:.2f}×, student services {sec['Public']['spending']['Student services']['median_ratio']:.2f}× (p = {sec['Public']['spending']['Student services']['mann_whitney_p']:.3f}). "
                f"Private over-performers differ on instruction ({sec['Private nonprofit']['spending']['Instruction']['median_ratio']:.2f}×) and academic support ({sec['Private nonprofit']['spending']['Academic support']['median_ratio']:.2f}×) but not student services ({sec['Private nonprofit']['spending']['Student services']['median_ratio']:.2f}×). "
                f"After a Benjamini-Hochberg correction across all {s7['bh']['n_tests']} spending tests, the instruction and academic-support gaps survive in every comparison and the student-services gap in none. "
                "Budget shares are not shown as separate findings: they sum to 100%, so a higher instruction share is the same fact as more instruction dollars.")

# ------------------------------------------------------------------ School lookup
with tab_school:
    panel_head("School lookup", "pick a school")
    names = (df.sort_values("instnm")["instnm"] + " (" + df.sort_values("instnm")["stabbr"] + ")").reset_index(drop=True)
    default = "California State University-Channel Islands (CA)"
    pick = st.selectbox("Choose a school", names, index=int(names[names == default].index[0]) if (names == default).any() else 0)
    row = df.sort_values("instnm").iloc[names[names == pick].index[0]]
    b_row = boot[boot.unitid == row.unitid].iloc[0]
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Actual first-gen 6-yr completion", f"{row.firstgen_comp_orig_yr6_rt:.1%}", f"cohort {int(row.firstgen_yr6_n):,}", CYAN)
    kpi(k2, "Predicted (main model)", f"{row.predicted:.1%}", f"{row.control_label} · {row.carnegie_group}", PURPLE)
    kpi(k3, "Shrunken residual", f"{row.residual_eb_pct_pts:+.1f} pts", f"raw {row.residual_pct_pts:+.1f} · rank {int(row['rank'])} of {len(df):,} (95% bootstrap {b_row.boot_rank_p2_5:.0f}-{b_row.boot_rank_p97_5:.0f})", PINK if row.residual_eb < 0 else LIME)
    kpi(k4, "P(top 10%) across resamples", f"{b_row.p_top_decile:.0%}", "1,000 bootstrap resamples", AMBER)
    st.caption(f"{int(row.ugds):,} undergrads (2017) · Pell share {row.pctpell:.0%} · admit rate {row.adm_rate:.0%} · first-gen share {row.first_gen:.0%} · non-first-gen completion {row.not1stgen_comp_orig_yr6_rt:.1%} (gap {row.fg_gap*100:+.1f} pts)"
               + (f" · Opportunity Insights tier: {row.oi_tier_name}, mobility rate {row.oi_mr_kq5_pq1:.2%}" if row.oi_matched and pd.notna(row.oi_mr_kq5_pq1) else ""))
    a, b = st.columns([3, 2])
    with a:
        panel_head("Spending per FTE vs peers", "FY2018-23 average")
        peers = df[df.control_label == row.control_label]
        cats = list(CORE.values())
        fig = go.Figure()
        fig.add_bar(name="this school", x=cats, y=[row[f"{k}_per_fte"] for k in CORE], marker_color=CYAN, marker_line_width=0)
        fig.add_bar(name=f"median {row.control_label}", x=cats, y=[peers[f"{k}_per_fte"].median() for k in CORE], marker_color=MUTED, marker_line_width=0)
        fig.add_bar(name=f"median top 10% {row.control_label}", x=cats, y=[peers[peers.group == "top 10%"][f"{k}_per_fte"].median() for k in CORE], marker_color=LIME, marker_line_width=0)
        fig.update_layout(barmode="group", bargap=0.35, yaxis_title="$ per FTE")
        st.plotly_chart(dark(fig, 400), use_container_width=True)
    with b:
        panel_head("Comparable over-performers", "predicted within ±3 pts")
        near = df[(df.predicted - row.predicted).abs() < 0.03].sort_values("residual_eb", ascending=False).head(10)
        st.dataframe(near[["rank", "instnm", "stabbr", "control_label", "ugds", "pctpell", "firstgen_comp_orig_yr6_rt", "residual_eb_pct_pts"]].rename(columns={"instnm": "School", "stabbr": "State", "control_label": "Control", "ugds": "Undergrads", "pctpell": "Pell", "firstgen_comp_orig_yr6_rt": "Actual", "residual_eb_pct_pts": "Residual (pts)"})
                     .style.format({"rank": "{:.0f}", "Pell": "{:.2f}", "Actual": "{:.3f}", "Residual (pts)": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True, height=400)

# ------------------------------------------------------------------ Methods
with tab_method:
    panel_head("Methods & limitations", "")
    st.markdown(f"""
**Timing.** The outcome is the NSLDS AY2017-18 entry cohort measured in AY2023-24 (Scorecard data dictionary cohort map). Predictors come from the 2017-18 Scorecard file; spending is the FY2018-FY2023 average per 12-month FTE from IPEDS; Carnegie is the 2018 classification. Control, level and Title IV status come from 2023 IPEDS and are assumed stable.

**Data.** College Scorecard Oct-2026 release (dated file; the undated download URL served a stale 2024 file); IPEDS HD2023, IC2023, F1718-F2223 finance (F1A public / F2 private nonprofit), EFIA2018-2023; Opportunity Insights mobility report cards (context only). Joined on UNITID in DuckDB. 4-year = bachelor's-dominant in both 2017-18 and today and IPEDS level 4+ years. For-profits excluded (non-comparable finance form).

**Sample.** {s5['n']:,} schools (Carnegie doctoral, master's, baccalaureate) after dropping privacy-suppressed outcomes, first-gen cohorts under 50, schools missing an entry-year predictor, and schools with fewer than 3 fiscal years of finance data. Scored but not ranked: {s5['n_special_focus']} special-focus / tribal schools, {s5['n_nontraditional']} campuses with more than 50% of undergraduates aged 25+ or exclusively online, and {s5['n_anomaly']} schools with implausible Scorecard completion rates.

**Models.** Pooled Model A, OLS: first-gen 6-year same-institution completion ~ Pell share + admission rate (open-admission = 1.0) + log enrollment + part-time share + first-gen share + share of undergraduates aged 25+ + share exclusively online (all Fall 2017) + private + HBCU + Carnegie group. HC3 robust SEs. R² = {s5['r2_A']:.3f}. Residual = actual − predicted, then shrunk toward zero by τ²/(τ²+σ²) with σ² the binomial variance for the school's first-gen cohort (empirical Bayes; τ = {s6['tau_pp']:.1f} pts, median shrink {s6['shrink_median']:.2f}). The ranking model is {s5['main_model']}: Model A plus private × every trait, adopted because its shrunken ranking overlaps the public-only and private-only rankings' top deciles at {s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} versus {s5['ranking_comparison']['overlap_pool_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_pool_vs_sector_private']:.0%} for the pooled model (R² {s5['r2_main']:.3f}). Spending is left out on purpose so the spending comparison is not circular; Model B adds log core spending per FTE and the undergraduate share of FTE (R² {s5['r2_B']:.3f}).

**Sector slopes.** Joint Wald F test of the private × trait terms: F = {s5['joint_F_interactions']['F']:.2f}, p {'< 0.001' if s5['joint_F_interactions']['p'] < 0.001 else f"= {s5['joint_F_interactions']['p']:.3f}"}. A fractional-logit fit ranks schools the same (Spearman {s8['fractional_logit']['spearman_vs_main']:.3f}). Regressing the shrunken residual on log core spending plus instruction and academic-support shares: shares {'remain' if lm['shares_hold'] else 'do not remain'} significant with the level fixed (p = {lm['p']['instr_share']:.3f} / {lm['p']['acad_share']:.3f}; R² {lm['r2']:.3f}).

**Robustness.** Spending gaps hold with FY2018-19 spending only, in constant FY2023 dollars (BLS CPI-U), within each Carnegie group, and after dropping the {s7['n_cooks_dropped']} Cook's-distance-flagged schools; a Benjamini-Hochberg correction across all {s7['bh']['n_tests']} spending p-values keeps the instruction and academic-support gaps in every comparison and never the student-services gap. VIF: only the share aged 25+ exceeds 5 ({s5['vif']['ug25abv']:.2f}); Pell share and first-gen share correlate at {s5['corr_pell_firstgen']:.2f} with VIFs of {s5['vif']['pctpell']:.2f} and {s5['vif']['first_gen']:.2f}. Bootstrap of 1,000 resamples (shrinkage re-applied each draw): top-decile schools stay top-decile {bs['mean_p_top_among_point_top']:.0%} of the time; two random resamples share {bs['mean_pairwise_top_decile_overlap']:.0%} of their top decile. Separate public and private models rank schools consistently with the main model (Spearman {sec['Public']['spearman_vs_pooled']:.2f} / {sec['Private nonprofit']['spearman_vs_pooled']:.2f}). Dropping the largest 5% of schools: Spearman {s8['drop5']['spearman']:.3f} (weak test, kept because the brief asked).

**What changed after review.** The first build used a stale Scorecard file, 2024 traits, FY2023-only spending and no Carnegie control. Only {s6['top20_overlap_vs_v1']} of its top-20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}); the instruction and academic-support spending pattern held through every change.

**Limitations.**
- *School-level data.* We observe institutions, not students. A school can over-perform because of program mix or who it enrolls in ways the predictors do not capture.
- *Correlation only.* Spending differences describe what over-performers look like; they do not show that moving dollars would raise completion.
- *Outcome definition.* Completion at the *same* institution within 6 years for federal-aid students; transfers who finish elsewhere count as non-completers.
- *Suppression bias.* Privacy-suppressed outcomes remove the smallest schools.
- *Budget shares* sum to 100% and are therefore not reported as findings separate from dollar differences.
    """)
