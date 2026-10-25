"""Streamlit dashboard: which colleges help first-generation students graduate far more often than expected,
and how much money explains the gap.

Run from the project root:  streamlit run app/app.py
Reads data/clean/analysis_scored.parquet, data/clean/bootstrap_ranks.csv and reports/results.json (from src/05-08).
Plain-spoken labels everywhere; technical detail lives in the Methods tab.
Color meaning is fixed on every chart: teal = above expected / top 10%, coral = below expected / bottom 10%.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Colleges that help first-gen students graduate", layout="wide", page_icon="🎓")

# ------------------------------------------------------------------ palette (warm navy, teal above / coral below)
TEAL, CORAL, CREAM, SLATE, GOLD = "#2dd4bf", "#ff8a7a", "#f3e9d2", "#7c8aa5", "#f5c86b"
INK, INK2, GRID, SURFACE, HEAD = "#eef2f7", "#aab6c9", "rgba(255,255,255,0.09)", "#1f2e4d", "#243659"
CORE = {"exp_instruction": "Teaching", "exp_academic_support": "Academic support (advising, tutoring, libraries)", "exp_student_services": "Student services", "exp_institutional_support": "Administration"}
CORE_SHORT = {"exp_instruction": "Teaching", "exp_academic_support": "Academic support", "exp_student_services": "Student services", "exp_institutional_support": "Administration"}
CARN = "C(carnegie_group, Treatment(reference=\"Master's\"))"
PLAIN = {"pctpell": "Share of students on Pell Grants", "adm_rate": "Share of applicants admitted", "log_ugds": "Size (log of enrollment)", "pptug_ef": "Share studying part-time",
         "first_gen": "Share who are first-gen", "ug25abv": "Share aged 25 or older", "pct_distance": "Share fully online", "private": "Private college (vs public)", "hbcu_flag": "Historically Black college",
         f"{CARN}[T.Doctoral]": "Research university (vs master's)", f"{CARN}[T.Baccalaureate]": "Bachelor's-focused college (vs master's)"}

st.markdown(f"""
<style>
  .block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }}
  .hero {{ font-size: 1.5rem; font-weight: 700; line-height: 1.3; color: {INK}; margin-bottom: .35rem; }}
  .byline {{ font-size: .95rem; color: {INK2}; margin-bottom: 1rem; }}
  .panel-head {{ background:{HEAD}; border:1px solid #2f4470; border-bottom:none; padding:.5rem .9rem; border-radius:10px 10px 0 0; margin-top:.7rem;
                 font-size:.78rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:{INK}; }}
  .meaning {{ font-size:.92rem; color:{INK}; background:{SURFACE}; border:1px solid #2f4470; border-top:none; border-radius:0 0 10px 10px; padding:.55rem .9rem; margin-bottom:.4rem; }}
  .meaning b {{ color:{CREAM}; }}
  .kpi {{ padding:.2rem .2rem .6rem .2rem; }}
  .kpi .l {{ font-size:.82rem; letter-spacing:.02em; padding-bottom:.25rem; border-bottom:2px solid; margin-bottom:.35rem; color:{INK2}; }}
  .kpi .v {{ font-size:2.1rem; font-weight:800; line-height:1.05; }}
  .kpi .s {{ font-size:.74rem; color:{INK2}; margin-top:.25rem; }}
  .learn {{ background:{SURFACE}; border:1px solid #2f4470; border-radius:10px; padding:.8rem 1rem; height:100%; }}
  .learn .n {{ font-size:1.05rem; font-weight:700; color:{INK}; }}
  .learn .w {{ font-size:.86rem; color:{INK2}; margin:.2rem 0 .5rem 0; }}
  .learn .big {{ font-size:1.6rem; font-weight:800; color:{TEAL}; }}
  .learn .d {{ font-size:.9rem; color:{INK}; }}
  div[data-testid="stTabs"] button {{ letter-spacing:.04em; font-size:.9rem; font-weight:700; }}
  div[data-testid="stDataFrame"] {{ border:1px solid #2f4470; border-radius:10px; }}
</style>""", unsafe_allow_html=True)


def head(title: str):
    st.markdown(f'<div class="panel-head">{title}</div>', unsafe_allow_html=True)


def meaning(text: str):
    st.markdown(f'<div class="meaning"><b>What this means.</b> {text}</div>', unsafe_allow_html=True)


def kpi(col, label, value, sub, color):
    col.markdown(f'<div class="kpi"><div class="l" style="border-color:{color}">{label}</div><div class="v" style="color:{color}">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def styled(fig, height=360, legend=True):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=INK2, size=12), height=height,
                      margin=dict(l=10, r=10, t=30, b=10), title=None, showlegend=legend,
                      legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(color=INK2, size=11), bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor="#fdf6e3", font_color="#1b2540", bordercolor="#fdf6e3"))
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
    for k, lbl in list(CORE_SHORT.items()) + [("exp_core", "All four together")]:
        a, b = top[f"{k}_per_fte"], bot[f"{k}_per_fte"]
        rows.append({"Spending category": lbl, "Top 10%": a.median(), "Bottom 10%": b.median(), "Top ÷ bottom": a.median() / b.median(), "p-value": stats.mannwhitneyu(a, b, alternative="two-sided").pvalue})
    return pd.DataFrame(rows)


def spend_bar(top, bot, height=340):
    cats = list(CORE_SHORT.values())
    fig = go.Figure()
    fig.add_bar(name="Top 10% of schools", x=cats, y=[top[f"{k}_per_fte"].median() for k in CORE], marker_color=TEAL, marker_line_width=0, text=[f"${top[f'{k}_per_fte'].median():,.0f}" for k in CORE], textposition="outside", textfont=dict(color=INK2, size=10))
    fig.add_bar(name="Bottom 10% of schools", x=cats, y=[bot[f"{k}_per_fte"].median() for k in CORE], marker_color=CORAL, marker_line_width=0, text=[f"${bot[f'{k}_per_fte'].median():,.0f}" for k in CORE], textposition="outside", textfont=dict(color=INK2, size=10))
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, yaxis_title="Typical spending per student per year")
    return styled(fig, height)


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
pub, prv = sec["Public"]["spending"], sec["Private nonprofit"]["spending"]
TYPE = {"Public": "Public", "Private nonprofit": "Private"}
KIND = {"Doctoral": "Research university", "Master's": "Master's university", "Baccalaureate": "Bachelor's college"}

st.markdown('<div class="hero">Some colleges help first-gen students graduate far more often than expected. This dashboard shows which ones, and how much money explains the gap.</div>', unsafe_allow_html=True)
st.markdown('<div class="byline">Built by Isiah Luna, a first-gen transfer student at SDSU.</div>', unsafe_allow_html=True)

tab_over, tab_rank, tab_spend, tab_method = st.tabs(["Overview", "All schools", "Where the money goes", "Methods & limitations"])


def school_card(row):
    b_row = boot[boot.unitid == row.unitid].iloc[0]
    up = row.residual_eb >= 0
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Expected to graduate", f"{row.predicted:.0%}", "of first-gen students, given who the school enrolls", SLATE)
    kpi(k2, "Actually graduated", f"{row.firstgen_comp_orig_yr6_rt:.0%}", f"of {int(row.firstgen_yr6_n):,} first-gen students who started in 2017-18", TEAL if up else CORAL)
    kpi(k3, "Points above expected", f"{row.residual_eb_pct_pts:+.1f}", f"rank {int(row['rank'])} of {len(df):,} schools", TEAL if up else CORAL)
    kpi(k4, "Stays in the top 10% when we re-run", f"{b_row.p_top_decile:.0%}", "of 1,000 re-runs of the analysis", GOLD)
    st.caption(f"{TYPE[row.control_label]} · {KIND[row.carnegie_group]} · {int(row.ugds):,} undergrads in 2017 · {row.pctpell:.0%} on Pell Grants · {row.adm_rate:.0%} of applicants admitted · {row.first_gen:.0%} first-gen · "
               f"students who are not first-gen graduated at {row.not1stgen_comp_orig_yr6_rt:.0%}")
    a, b = st.columns([3, 2])
    with a:
        head("Where this school's money goes, compared with peers")
        peers = df[df.control_label == row.control_label]
        cats = list(CORE_SHORT.values())
        fig = go.Figure()
        fig.add_bar(name="This school", x=cats, y=[row[f"{k}_per_fte"] for k in CORE], marker_color=CREAM, marker_line_width=0)
        fig.add_bar(name=f"Typical {TYPE[row.control_label].lower()} school", x=cats, y=[peers[f"{k}_per_fte"].median() for k in CORE], marker_color=SLATE, marker_line_width=0)
        fig.add_bar(name=f"Typical top-10% {TYPE[row.control_label].lower()} school", x=cats, y=[peers[peers.group == "top 10%"][f"{k}_per_fte"].median() for k in CORE], marker_color=TEAL, marker_line_width=0)
        fig.update_layout(barmode="group", bargap=0.35, yaxis_title="Spending per student per year")
        st.plotly_chart(styled(fig, 360), use_container_width=True, key="card_spend")
        t_med = peers[peers.group == "top 10%"]["exp_instruction_per_fte"].median()
        meaning(f"{row.instnm} spends ${row.exp_instruction_per_fte:,.0f} per student on teaching; the typical top-10% {TYPE[row.control_label].lower()} school spends ${t_med:,.0f}. Cream is this school, grey is a typical peer, teal is a typical top-10% peer.")
    with b:
        head("Similar schools that do better")
        near = df[(df.predicted - row.predicted).abs() < 0.03].sort_values("residual_eb", ascending=False).head(8)
        st.dataframe(near[["rank", "instnm", "stabbr", "control_label", "ugds", "firstgen_comp_orig_yr6_rt", "residual_eb_pct_pts"]].assign(control_label=lambda d: d.control_label.map(TYPE)).rename(columns={"rank": "Rank", "instnm": "School", "stabbr": "State", "control_label": "Type", "ugds": "Undergrads", "firstgen_comp_orig_yr6_rt": "Actually graduated", "residual_eb_pct_pts": "Points above expected"})
                     .style.format({"Rank": "{:.0f}", "Actually graduated": "{:.0%}", "Points above expected": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True, height=330)
        meaning(f"These schools were expected to graduate about the same share of first-gen students as {row.instnm} (within 3 points) and are the ones that beat that expectation by the most. Call them.")


# ------------------------------------------------------------------ Overview
with tab_over:
    head("Look up any college")
    names = (df.sort_values("instnm")["instnm"] + " (" + df.sort_values("instnm")["stabbr"] + ")").reset_index(drop=True)
    default = "San Diego State University (CA)"
    pick = st.selectbox("Look up any college", names, index=int(names[names == default].index[0]) if (names == default).any() else 0, label_visibility="collapsed")
    row = df.sort_values("instnm").iloc[names[names == pick].index[0]]
    with st.expander(f"{row.instnm}: {row.residual_eb_pct_pts:+.1f} points above expected (rank {int(row['rank'])} of {len(df):,})", expanded=True):
        school_card(row)

    head("Schools worth learning from · large schools (over 500 first-gen students) that beat expectations by the most")
    big3 = df[df.firstgen_yr6_n > 500].sort_values("residual_eb", ascending=False).head(3)
    cols = st.columns(3)
    for col, r in zip(cols, big3.itertuples()):
        col.markdown(f'<div class="learn"><div class="n">{r.instnm}</div><div class="w">{r.stabbr} · {TYPE[r.control_label]} · {KIND[r.carnegie_group]} · {int(r.ugds):,} undergrads · {r.pctpell:.0%} on Pell</div>'
                     f'<div class="big">{r.residual_eb_pct_pts:+.0f} points above expected</div>'
                     f'<div class="d">Given who it enrolls, about <b>{r.predicted:.0%}</b> of its {int(r.firstgen_yr6_n):,} first-gen students were expected to graduate within six years. <b>{r.firstgen_comp_orig_yr6_rt:.0%}</b> did.</div></div>', unsafe_allow_html=True)
    meaning(f"Expected means what a school with the same mix of students, size and type usually achieves. These three beat that by {big3.residual_eb_pct_pts.min():.0f} to {big3.residual_eb_pct_pts.max():.0f} points with large cohorts, so the result is not a small-numbers fluke.")

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi(k1, "Colleges compared", f"{s5['n']:,}", f"four-year public and private; {s5['n_excluded']} special cases listed separately", CREAM)
    kpi(k2, "How much the model explains", f"{s5['r2_main']:.0%}", "of the difference in first-gen graduation between schools", CREAM)
    kpi(k3, "Typical first-gen graduation", f"{s5['outcome_mean']:.0%}", "within six years, same school", CREAM)
    kpi(k4, "Top 10% of schools beat expectations by", f"+{s6['top_decile_cut_pp']:.0f} pts", f"or more ({s6['top_decile_n']} schools)", TEAL)
    kpi(k5, "Share of the gap explained by money", f"{lm['r2']*100:.0f}%", "how much a school spends, and on what", GOLD)

    a, b = st.columns(2)
    with a:
        head("Expected vs actual first-gen graduation, one dot per college")
        fig = go.Figure()
        for g, c, nm in [("middle", SLATE, "Middle 80% of schools"), ("bottom 10%", CORAL, "Bottom 10%: below expected"), ("top 10%", TEAL, "Top 10%: above expected")]:
            d = df[df.group == g]
            fig.add_scatter(x=d.predicted, y=d.firstgen_comp_orig_yr6_rt, mode="markers", name=nm, marker=dict(color=c, size=6, opacity=.8 if g != "middle" else .4, line=dict(width=0)),
                            customdata=np.stack([d.instnm, d.stabbr, d.control_label.map(TYPE), d.ugds, d.pctpell], axis=1),
                            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>%{customdata[2]} · %{customdata[3]:,} undergrads · %{customdata[4]:.0%} on Pell<br>expected %{x:.0%} · actual %{y:.0%}<extra></extra>")
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=CREAM, dash="dash", width=1.5), name="Actual = expected", hoverinfo="skip")
        fig.update_layout(xaxis_title="Expected graduation rate", yaxis_title="Actual graduation rate", xaxis=dict(range=[0.05, 1], tickformat=".0%"), yaxis=dict(range=[0, 1], tickformat=".0%"))
        st.plotly_chart(styled(fig, 400), use_container_width=True, key="ov_scatter")
        meaning("Each dot is a college. The dashed line is where actual equals expected. Teal dots above the line graduate far more first-gen students than schools like them; coral dots far fewer. Hover for the name.")
    with b:
        head("How far each college lands from expected")
        fig = go.Figure(go.Histogram(x=df.residual_eb_pct_pts, nbinsx=45, marker_color=SLATE, marker_line=dict(color="#172238", width=1), name="schools", hovertemplate="%{x} points from expected: %{y} schools<extra></extra>"))
        fig.add_vline(x=s6["top_decile_cut_pp"], line=dict(color=TEAL, dash="dash", width=1.5), annotation_text=f"top 10% start here: +{s6['top_decile_cut_pp']:.0f}", annotation_position="top", annotation_font=dict(color=TEAL, size=10))
        fig.add_vline(x=s6["bottom_decile_cut_pp"], line=dict(color=CORAL, dash="dash", width=1.5), annotation_text=f"bottom 10% below {s6['bottom_decile_cut_pp']:+.0f}", annotation_position="top", annotation_font=dict(color=CORAL, size=10))
        fig.update_layout(xaxis_title="Points above (or below) expected", yaxis_title="Number of colleges", bargap=0.08)
        st.plotly_chart(styled(fig, 400, legend=False), use_container_width=True, key="ov_hist")
        meaning(f"Most colleges land within about 10 points of expected. The top 10% beat expectations by {s6['top_decile_cut_pp']:.0f} points or more; the bottom 10% fall {abs(s6['bottom_decile_cut_pp']):.0f} points or more short.")

    c, d_ = st.columns(2)
    with c:
        head("What predicts first-gen graduation")
        terms = [k for k in PLAIN if k in s5["coef_A"]]
        co = pd.DataFrame({"term": [PLAIN[k] for k in terms], "coef": [s5["coef_A"][k] * 100 for k in terms], "se": [s5["se_A"][k] * 100 for k in terms]})
        fig = go.Figure(go.Bar(x=co.coef, y=co.term, orientation="h", marker_color=[TEAL if v > 0 else CORAL for v in co.coef], marker_line_width=0,
                               error_x=dict(type="data", array=1.96 * co.se, color=INK2, thickness=1.2), hovertemplate="%{y}: %{x:+.1f} points<extra></extra>"))
        fig.update_layout(xaxis_title="Points of graduation rate, going from 0% to 100% of students (or from no to yes)", yaxis=dict(autorange="reversed"), bargap=0.35)
        st.plotly_chart(styled(fig, 420, legend=False), use_container_width=True, key="ov_coef")
        meaning(f"Teal bars raise expected graduation, coral bars lower it. A school where every student is on a Pell Grant is expected to graduate about {abs(s5['coef_A']['pctpell'])*100:.0f} points fewer first-gen students than one where none are. Expected rates are built from these, with separate versions for public and private schools.")
    with d_:
        head("Where the top 10% spend more than the bottom 10%")
        st.plotly_chart(spend_bar(df[df.group == "top 10%"], df[df.group == "bottom 10%"], 420), use_container_width=True, key="ov_spend")
        meaning(f"Schools that beat expectations spend about {pf['Instruction']['median_ratio']:.1f}× more per student on teaching and {pf['Academic support']['median_ratio']:.1f}× more on academic support than schools that fall short, and about the same on student services. But money explains only {lm['r2']*100:.0f}% of the gap, so learn from the schools, not just the budgets.")

# ------------------------------------------------------------------ Rankings
with tab_rank:
    head(f"All {len(df):,} colleges, ranked by points above expected")
    f1, f2, f3, f4, f5 = st.columns(5)
    states = f1.multiselect("State", sorted(df["stabbr"].unique()))
    ctrl = f2.multiselect("Public or private", ["Public", "Private nonprofit"], format_func=lambda v: TYPE[v])
    carn = f3.multiselect("Kind of school", sorted(df["carnegie_group"].unique()), format_func=lambda v: KIND[v])
    min_ugds = f4.number_input("At least this many undergrads (2017)", 0, int(df["ugds"].max()), 0, step=500)
    pell_rng = f5.slider("Share of students on Pell Grants", 0.0, 1.0, (0.0, 1.0), 0.05)
    d = df.copy()
    if states: d = d[d["stabbr"].isin(states)]
    if ctrl: d = d[d["control_label"].isin(ctrl)]
    if carn: d = d[d["carnegie_group"].isin(carn)]
    d = d[(d["ugds"] >= min_ugds) & (d["pctpell"].between(*pell_rng))].sort_values("residual_eb", ascending=False)
    d = d.merge(boot[["unitid", "p_top_decile", "boot_rank_p2_5", "boot_rank_p97_5"]], on="unitid", how="left")
    d["rank_range"] = d.boot_rank_p2_5.map(lambda v: f"{v:.0f}") + "–" + d.boot_rank_p97_5.map(lambda v: f"{v:.0f}")
    st.caption(f"{len(d):,} colleges match. Rank is among all {len(df):,}. 'Points above expected' is adjusted so small schools are not over-credited for lucky years; the unadjusted figure is shown too.")
    show = d[["rank", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "firstgen_yr6_n", "firstgen_comp_orig_yr6_rt", "predicted", "residual_eb_pct_pts", "residual_pct_pts", "p_top_decile", "rank_range", "exp_core_per_fte"]].assign(control_label=lambda x: x.control_label.map(TYPE), carnegie_group=lambda x: x.carnegie_group.map(KIND)).rename(columns={
        "rank": "Rank", "instnm": "School", "stabbr": "State", "control_label": "Type", "carnegie_group": "Kind", "ugds": "Undergrads (2017)", "pctpell": "On Pell", "firstgen_yr6_n": "First-gen students", "firstgen_comp_orig_yr6_rt": "Actually graduated",
        "predicted": "Expected", "residual_eb_pct_pts": "Points above expected", "residual_pct_pts": "Before small-school adjustment", "p_top_decile": "Stays in top 10% (share of re-runs)", "rank_range": "Likely rank range", "exp_core_per_fte": "Core spending per student"})
    st.dataframe(show.style.format({"Rank": "{:.0f}", "On Pell": "{:.0%}", "Actually graduated": "{:.0%}", "Expected": "{:.0%}", "Points above expected": "{:+.1f}", "Before small-school adjustment": "{:+.1f}", "Stays in top 10% (share of re-runs)": "{:.0%}",
                                   "Core spending per student": "${:,.0f}", "Undergrads (2017)": "{:,.0f}", "First-gen students": "{:,.0f}"}), use_container_width=True, height=520, hide_index=True)
    st.download_button("Download this list (CSV)", show.to_csv(index=False).encode(), "colleges_ranked.csv", "text/csv")
    meaning("A college at +15 graduates first-gen students 15 points more often than schools with the same kind of students usually do. 'Stays in top 10%' says how often it keeps that place when the analysis is re-run on random re-draws of the schools; near 100% means a solid result.")
    with st.expander(f"{len(sf)} special cases, scored but not ranked"):
        st.write("Three groups the comparison does not fit: colleges built around one program (nursing, faith, arts); campuses where more than half of students are 25+ or fully online; "
                 "and schools whose reported graduation numbers cannot be right (for example San Jose State's 3.8%, against a 68% overall graduation rate). Shown so nothing is hidden.")
        st.dataframe(sf.sort_values(["excluded_reason", "residual"], ascending=[True, False])[["excluded_reason", "instnm", "stabbr", "control_label", "ugds", "ug25abv", "pct_distance", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts"]].assign(control_label=lambda x: x.control_label.map(TYPE)).rename(columns={
            "excluded_reason": "Why set aside", "instnm": "School", "stabbr": "State", "control_label": "Type", "ugds": "Undergrads", "ug25abv": "Aged 25+", "pct_distance": "Fully online", "pctpell": "On Pell", "firstgen_comp_orig_yr6_rt": "Actually graduated", "predicted": "Expected", "residual_pct_pts": "Points above expected"})
                     .style.format({"On Pell": "{:.0%}", "Aged 25+": "{:.0%}", "Fully online": "{:.0%}", "Actually graduated": "{:.0%}", "Expected": "{:.0%}", "Points above expected": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ Spending
with tab_spend:
    head("Where the money goes: the top 10% of schools compared with the bottom 10%")
    scopes = {"All schools": "main", "All schools, simpler model": "pooled", "Public colleges only": "Public", "Private colleges only": "Private nonprofit", "Research universities": "Doctoral", "Master's universities": "Master's", "Bachelor's colleges": "Baccalaureate"}
    scope = scopes[st.radio("Compare within", list(scopes), horizontal=True, label_visibility="collapsed")]
    if scope == "main":
        top, bot = df[df.group == "top 10%"], df[df.group == "bottom 10%"]; tab = pf; note = "The top and bottom 10% from the main ranking, the same one shown on the other tabs."
    elif scope == "pooled":
        dp = df.assign(resid_pooled_eb=shrink(df["residual_pooled"], df["predicted_pooled"], df["firstgen_yr6_n"]))
        top, bot = decile_groups(dp, "resid_pooled_eb"); tab = None
        note = "A simpler version of the model that treats public and private schools the same way. Shown to check that the answer does not depend on that choice."
    elif scope in ("Public", "Private nonprofit"):
        dd = df[df.control_label == scope]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = sec[scope]["spending"]
        note = f"{TYPE[scope]} schools ranked only against other {TYPE[scope].lower()} schools (table); the chart shows the main-ranking groups restricted to {TYPE[scope].lower()} schools."
    else:
        dd = df[df.carnegie_group == scope]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = s7["within_carnegie"][scope]["per_fte"]
        note = f"Main-ranking groups restricted to {KIND[scope].lower()}s (top {len(top)}, bottom {len(bot)})."
    st.caption(note + " Spending is the yearly amount per student, averaged over the six years these students were enrolled (2018-2023).")
    a, b = st.columns([3, 2])
    a.plotly_chart(spend_bar(top, bot, 420), use_container_width=True, key="spend_tab_main")
    rename = {"Instruction": "Teaching", "Academic support": "Academic support", "Student services": "Student services", "Institutional support": "Administration", "Core (4 categories)": "All four together"}
    t = compare_table(top, bot) if tab is None else pd.DataFrame([{"Spending category": rename[k], "Top 10%": v["top10_median_$"], "Bottom 10%": v["bottom10_median_$"], "Top ÷ bottom": v["median_ratio"], "p-value": v["mann_whitney_p"]} for k, v in tab.items() if k in rename])
    b.dataframe(t.style.format({"Top 10%": "${:,.0f}", "Bottom 10%": "${:,.0f}", "Top ÷ bottom": "{:.2f}×", "p-value": "{:.3f}"}), hide_index=True, use_container_width=True)
    b.caption("p-value: the chance of seeing a gap this big if there were really no difference. Below 0.05 is the usual bar.")
    r_i, r_a, r_s = t.set_index("Spending category").loc["Teaching", "Top ÷ bottom"], t.set_index("Spending category").loc["Academic support", "Top ÷ bottom"], t.set_index("Spending category").loc["Student services", "Top ÷ bottom"]
    meaning(f"In this group, schools that beat expectations spend {r_i:.1f}× as much on teaching and {r_a:.1f}× as much on academic support per student as schools that fall short, and {r_s:.1f}× on student services. Teal is the top 10%, coral the bottom 10%.")
    st.markdown(f"**Public and private schools differ.** Among public colleges, the ones that beat expectations spend more on everything: teaching {pub['Instruction']['median_ratio']:.1f}×, academic support {pub['Academic support']['median_ratio']:.1f}×, student services {pub['Student services']['median_ratio']:.1f}×. "
                f"Among private colleges the gap is teaching ({prv['Instruction']['median_ratio']:.1f}×) and academic support ({prv['Academic support']['median_ratio']:.1f}×), with student services about equal ({prv['Student services']['median_ratio']:.1f}×). "
                f"The teaching and academic-support gaps hold up in every group we checked, including after a correction for running {s7['bh']['n_tests']} comparisons; the student-services gap does not.")
    with st.expander("Does the answer change if we look at different years, or adjust for inflation?"):
        var = pd.DataFrame({"2018-23, the main figure": {rename[k]: v["median_ratio"] for k, v in pf.items() if k in rename}, "2018-19 only (first two years)": {rename[k]: v["median_ratio"] for k, v in s7["per_fte_fy1819"].items() if k in rename},
                            "2018-23 in 2023 dollars": {rename[k]: v["median_ratio"] for k, v in s7["per_fte_real"].items() if k in rename}, "2023 only (after students left)": {rename[k]: v["median_ratio"] for k, v in s7["per_fte_fy23_only"].items() if k in rename}})
        st.dataframe(var.style.format("{:.2f}×"), use_container_width=True)
        meaning("No. The teaching and academic-support gaps are about the same size whichever years are used and whether or not dollars are adjusted for inflation.")

# ------------------------------------------------------------------ Methods (all technical detail lives here)
with tab_method:
    head("Methods & limitations: the technical version")
    st.markdown(f"""
**Plain-English labels used on the other tabs map to these terms.** "Expected" = fitted value of the ranking model. "Points above expected" = empirical-Bayes-shrunken residual (actual − predicted, ×100). "How much the model explains" = R² of the ranking model. "Top 10% of schools" = top decile of the shrunken residual. "Stays in top 10% when we re-run" = share of 1,000 bootstrap resamples in which the school lands in the top decile. "Before small-school adjustment" = raw residual.

**Timing.** The outcome is the NSLDS AY2017-18 entry cohort measured in AY2023-24 (Scorecard data dictionary cohort map). Predictors come from the 2017-18 Scorecard file; spending is the FY2018-FY2023 average per 12-month FTE from IPEDS; Carnegie is the 2018 classification. Control, level and Title IV status come from 2023 IPEDS and are assumed stable.

**Data.** College Scorecard Oct-2026 release (dated file; the undated download URL served a stale 2024 file); IPEDS HD2023, IC2023, EF2017A_DIST, F1718-F2223 finance (F1A public / F2 private nonprofit), EFIA2018-2023; BLS CPI-U via FRED; Opportunity Insights mobility report cards (context only). Joined on UNITID in DuckDB. 4-year = bachelor's-dominant in both 2017-18 and today and IPEDS level 4+ years. For-profits excluded (non-comparable finance form).

**Sample.** {s5['n']:,} schools (Carnegie doctoral, master's, baccalaureate) after dropping privacy-suppressed outcomes, first-gen cohorts under 50, schools missing an entry-year predictor, and schools with fewer than 3 fiscal years of finance data. Scored but not ranked: {s5['n_special_focus']} special-focus / tribal schools, {s5['n_nontraditional']} campuses with more than 50% of undergraduates aged 25+ or exclusively online, and {s5['n_anomaly']} schools with implausible Scorecard completion rates.

**Models.** Pooled Model A, OLS: first-gen 6-year same-institution completion ~ Pell share + admission rate (open-admission = 1.0) + log enrollment + part-time share + first-gen share + share of undergraduates aged 25+ + share exclusively online (all Fall 2017) + private + HBCU + Carnegie group. HC3 robust SEs. R² = {s5['r2_A']:.3f}. Residual = actual − predicted, then shrunk toward zero by τ²/(τ²+σ²) with σ² the binomial variance for the school's first-gen cohort (empirical Bayes; τ = {s6['tau_pp']:.1f} pts, median shrink {s6['shrink_median']:.2f}). The ranking model is {s5['main_model']}: Model A plus private × every trait (Carnegie dummies shared), adopted because its shrunken ranking overlaps the public-only and private-only rankings' top deciles at {s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} versus {s5['ranking_comparison']['overlap_pool_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_pool_vs_sector_private']:.0%} for the pooled model (R² {s5['r2_main']:.3f}). The coefficient chart on the Overview shows the pooled model's slopes for readability. Spending is left out of the ranking model on purpose so the spending comparison is not circular; Model B adds log core spending per FTE and the undergraduate share of FTE (R² {s5['r2_B']:.3f}).

**Sector slopes.** Joint Wald F test of the private × trait terms: F = {s5['joint_F_interactions']['F']:.2f}, p {'< 0.001' if s5['joint_F_interactions']['p'] < 0.001 else f"= {s5['joint_F_interactions']['p']:.3f}"}. A fractional-logit fit ranks schools the same (Spearman {s8['fractional_logit']['spearman_vs_main']:.3f}, top-decile overlap {s8['fractional_logit']['top_decile_overlap_vs_main']:.0%}).

**Level vs mix.** Shrunken residual regressed on log core spending per FTE, instruction share and academic-support share of core spending, with sector and Carnegie controls (HC3): R² = {lm['r2']:.3f} (level only {lm['r2_level_only']:.3f}, mix only {lm['r2_mix_only']:.3f}); one SD more academic-support share ≈ {lm['pp_per_sd_acad_share']:+.1f} pts (p = {lm['p']['acad_share']:.3f}), one SD more instruction share ≈ {lm['pp_per_sd_instr_share']:+.1f} (p = {lm['p']['instr_share']:.3f}), doubling core spending ≈ {pp_double:+.1f} pts. This is the "share of the gap explained by money" figure on the Overview.

**Spending comparison.** Top vs bottom decile medians of IPEDS functional expenses per FTE; Welch t-tests on logs and Mann-Whitney U; repeated within sector, within Carnegie group, with FY2018-19 only, in constant FY2023 dollars, and after dropping the {s7['n_cooks_dropped']} Cook's-distance-flagged schools (4/n). Benjamini-Hochberg across all {s7['bh']['n_tests']} Mann-Whitney p-values keeps the instruction and academic-support gaps in every comparison and never the student-services gap. Budget shares sum to 100% and are not reported as findings separate from dollar differences.

**Robustness.** VIF: only the share aged 25+ exceeds 5 ({s5['vif']['ug25abv']:.2f}); Pell share and first-gen share correlate at {s5['corr_pell_firstgen']:.2f} with VIFs of {s5['vif']['pctpell']:.2f} and {s5['vif']['first_gen']:.2f}. Bootstrap of 1,000 resamples (shrinkage re-applied each draw): top-decile schools stay top-decile {bs['mean_p_top_among_point_top']:.0%} of the time; two random resamples share {bs['mean_pairwise_top_decile_overlap']:.0%} of their top decile. Separate public and private models agree with the main ranking (Spearman {sec['Public']['spearman_vs_pooled']:.2f} / {sec['Private nonprofit']['spearman_vs_pooled']:.2f}). Dropping the largest 5% of schools: Spearman {s8['drop5']['spearman']:.3f} (weak test, kept because the brief asked).

**What changed after review.** The first build used a stale Scorecard file, 2024 traits, FY2023-only spending and no Carnegie control. Only {s6['top20_overlap_vs_v1']} of its top-20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}); the teaching and academic-support spending pattern held through every change.

**Limitations.**
- *School-level data.* We observe institutions, not students. A school can over-perform because of program mix or who it enrolls in ways the predictors do not capture.
- *Correlation only.* Spending differences describe what over-performers look like; they do not show that moving dollars would raise completion.
- *Outcome definition.* Completion at the *same* institution within 6 years for federal-aid students; transfers who finish elsewhere count as non-completers.
- *Suppression bias.* Privacy-suppressed outcomes remove the smallest schools.

Source code, reports and the decisions log: https://github.com/isiahmello24-beep/first-gen-beating-odds
    """)
