"""Streamlit dashboard: which colleges graduate first gen students far more often than expected,
and how much money explains the gap.

Run from the project root:  streamlit run app/app.py
Reads data/clean/analysis_scored.parquet, data/clean/bootstrap_ranks.csv and reports/results.json (from src/05 to src/08).

Design direction: editorial data desk. Warm paper base, hairline rules instead of shadows, one serif for headlines and body, one sans for labels, numbers, tabs, tables and charts, and ONE accent color reserved for the finding (schools above expected).
Color meaning is fixed on every chart: accent = above expected or top 10%, graphite = below expected or bottom 10%.
Asymmetric twelve column grid: 8/4, 4/8, 7/5. Plain spoken labels. Technical detail lives in the Methods tab.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Colleges that beat the odds for first gen students", layout="wide")

# ------------------------------------------------------------------ palette: paper base, one accent
PAPER, SURFACE, RULE, INK, INK2, MUTE = "#F6F3EC", "#FFFFFF", "#D9D4C7", "#161616", "#5E5A52", "#C9C3B5"
ACCENT, GRAPHITE, MID = "#C8401A", "#6B6B6B", "#C4BEB0"          # above expected / below expected / middle
CORE = {"exp_instruction": "Teaching", "exp_academic_support": "Academic support", "exp_student_services": "Student services", "exp_institutional_support": "Administration"}
CARN = "C(carnegie_group, Treatment(reference=\"Master's\"))"
PLAIN = {"pctpell": "Share of students on Pell Grants", "adm_rate": "Share of applicants admitted", "log_ugds": "Size (log of enrollment)", "pptug_ef": "Share studying part-time",
         "first_gen": "Share who are first-gen", "ug25abv": "Share aged 25 or older", "pct_distance": "Share fully online", "private": "Private college (vs public)", "hbcu_flag": "Historically Black college",
         f"{CARN}[T.Doctoral]": "Research university (vs master's)", f"{CARN}[T.Baccalaureate]": "Bachelor's-focused college (vs master's)"}
TYPE = {"Public": "Public", "Private nonprofit": "Private"}
KIND = {"Doctoral": "Research university", "Master's": "Master's university", "Baccalaureate": "Bachelor's college"}

st.markdown(f"""
<style>
  html, body, .stApp, .stApp p, .stApp li, .stMarkdown, .stCaption, .hero .d, .stat .s, .list .nm, .list .meta, .meaning, .dl .r span:first-child, .mast .by {{ font-family: "Times New Roman", Times, serif; }}
  .mono, div[data-testid="stTabs"] button, div[data-testid="stTabs"] button p, [data-testid="stDataFrame"], [data-testid="stDataFrame"] *, .hero .n, .stat .n, .list .pt, .dl .r span:last-child,
  .stSelectbox *, .stMultiSelect *, .stRadio *, .stNumberInput *, .stSlider *, .stButton *, .stDownloadButton *, div[data-testid="stExpander"] summary * {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; }}
  .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background: {PAPER}; color: {INK}; }}
  .stApp p, .stApp li, .stApp label, .stApp span {{ color: inherit; }}
  .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1440px; }}
  .mono {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 10px; letter-spacing: .14em; text-transform: uppercase; color: {INK2}; }}
  .mast {{ border-top: 3px solid {INK}; padding-top: .6rem; }}
  .mast h1 {{ font-family: "Times New Roman", Times, serif; font-weight: 500; font-size: 2.6rem; line-height: 1.12; letter-spacing: -.01em; color: {INK}; margin: .5rem 0 .6rem 0; max-width: 20ch; }}
  .mast .by {{ font-size: .92rem; color: {INK2}; }}
  .mast .by b {{ color: {INK}; font-weight: 500; }}
  .rule {{ border-top: 1px solid {RULE}; margin: 1.1rem 0 .9rem 0; }}
  .rule-strong {{ border-top: 2px solid {INK}; margin: 1.4rem 0 .9rem 0; }}
  .sec {{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:.25rem 1rem; border-bottom: 1px solid {RULE}; padding-bottom:.35rem; margin: .2rem 0 .7rem 0; }}
  .sec .mono {{ margin-left:auto; }}
  .sec .t {{ font-family: "Times New Roman", Times, serif; font-size: 1.25rem; font-weight: 500; color: {INK}; }}
  .hero .n {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 72px; font-weight: 300; line-height: .95; color: {ACCENT}; margin: .35rem 0 .2rem 0; letter-spacing: -.02em; }}
  .hero .d {{ font-size: 1.02rem; color: {INK}; max-width: 56ch; line-height: 1.5; }}
  .stat {{ border-top: 1px solid {RULE}; padding: .55rem 0 .3rem 0; }}
  .stat .n {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 30px; font-weight: 500; color: {INK}; line-height: 1.05; margin: .25rem 0 .15rem 0; }}
  .stat .n.acc {{ color: {ACCENT}; }}
  .stat .s {{ font-size: .8rem; color: {INK2}; }}
  .list .row {{ border-bottom: 1px solid {RULE}; padding: .6rem 0 .55rem 0; }}
  .list .row:first-child {{ border-top: 1px solid {RULE}; }}
  .list .nm {{ font-weight: 600; color: {INK}; font-size: .98rem; }}
  .list .pt {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; color: {ACCENT}; font-size: 1.35rem; font-weight: 500; float: right; margin-top: -.1rem; }}
  .list .meta {{ font-size: .8rem; color: {INK2}; margin-top: .15rem; }}
  .list .meta b {{ color: {INK}; font-weight: 500; }}
  .surface {{ background: {SURFACE}; border: 1px solid {RULE}; padding: 1rem 1.1rem .4rem 1.1rem; }}
  .meaning {{ font-size: .9rem; color: {INK}; border-left: 2px solid {INK}; padding: .15rem 0 .15rem .75rem; margin: .1rem 0 .6rem 0; max-width: 72ch; }}
  .meaning b {{ font-weight: 600; }}
  .dl .r {{ display:flex; justify-content:space-between; border-bottom:1px solid {RULE}; padding:.4rem 0; font-size:.9rem; }}
  .dl .r span:first-child {{ color:{INK2}; }}
  .dl .r span:last-child {{ color:{INK}; font-weight:500; font-variant-numeric: tabular-nums; }}
  @media (max-width: 900px) {{
    .mast h1 {{ font-size: 1.45rem; line-height: 1.2; margin: .35rem 0 .4rem 0; }}
    .hero .n {{ font-size: 52px; }}
    .block-container {{ padding-top: .8rem; }}
    .mono {{ font-size: 10px; }}
  }}
  div[data-testid="stTabs"] button {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }}
  div[data-testid="stDataFrame"] {{ border: 1px solid {RULE}; }}
  div[data-testid="stExpander"] {{ border: 1px solid {RULE}; border-radius: 0; }}
  div[data-testid="stExpander"] details summary p {{ font-family: "Times New Roman", Times, serif; font-weight: 600; }}
</style>""", unsafe_allow_html=True)


def mono(text):
    st.markdown(f'<div class="mono">{text}</div>', unsafe_allow_html=True)


def section(title, right=""):
    st.markdown(f'<div class="sec"><span class="t">{title}</span><span class="mono">{right}</span></div>', unsafe_allow_html=True)


def meaning(text):
    st.markdown(f'<div class="meaning">{text}</div>', unsafe_allow_html=True)


def stat(col, label, value, sub, accent=False):
    col.markdown(f'<div class="stat"><div class="mono">{label}</div><div class="n{" acc" if accent else ""}">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def chart(fig, height=340, legend=True, ygrid=True):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Helvetica Neue, Helvetica, Arial, sans-serif", color=INK2, size=12), height=height,
                      margin=dict(l=6, r=6, t=26, b=6), title=None, showlegend=legend,
                      legend=dict(orientation="h", y=-0.24, x=0, xanchor="left", font=dict(color=INK2, size=11), bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor=INK, font_color=PAPER, bordercolor=INK, font_family="Helvetica Neue, Helvetica, Arial, sans-serif"))
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=RULE, tickfont=dict(color=INK2, size=11), title_font=dict(color=INK2, size=11))
    fig.update_yaxes(showgrid=ygrid, gridcolor="#E9E4D9", gridwidth=1, zeroline=False, linecolor=RULE, tickfont=dict(color=INK2, size=11), title_font=dict(color=INK2, size=11))
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
    for k, lbl in list(CORE.items()) + [("exp_core", "All four together")]:
        a, b = top[f"{k}_per_fte"], bot[f"{k}_per_fte"]
        rows.append({"Spending category": lbl, "Top 10%": a.median(), "Bottom 10%": b.median(), "Top ÷ bottom": a.median() / b.median(), "p-value": stats.mannwhitneyu(a, b, alternative="two-sided").pvalue})
    return pd.DataFrame(rows)


def spend_bar(top, bot, height=340):
    cats = list(CORE.values())
    fig = go.Figure()
    fig.add_bar(name="Top 10% of schools", x=cats, y=[top[f"{k}_per_fte"].median() for k in CORE], marker_color=ACCENT, marker_line_width=0, text=[f"${top[f'{k}_per_fte'].median():,.0f}" for k in CORE], textposition="outside", textfont=dict(color=INK, size=11, family="Helvetica Neue, Helvetica, Arial, sans-serif"))
    fig.add_bar(name="Bottom 10% of schools", x=cats, y=[bot[f"{k}_per_fte"].median() for k in CORE], marker_color=GRAPHITE, marker_line_width=0, text=[f"${bot[f'{k}_per_fte'].median():,.0f}" for k in CORE], textposition="outside", textfont=dict(color=INK2, size=11, family="Helvetica Neue, Helvetica, Arial, sans-serif"))
    fig.update_layout(barmode="group", bargap=0.4, bargroupgap=0.06, yaxis_title="Spending per student per year", yaxis=dict(tickprefix="$", separatethousands=True))
    return chart(fig, height)


FILES = [ROOT / "data/clean/analysis_scored.parquet", ROOT / "data/clean/bootstrap_ranks.csv", ROOT / "reports/results.json"]


@st.cache_data
def load(mtimes: tuple):   # the mtimes ARE the cache key (an underscore prefix would exclude them and serve stale data after a pipeline rerun)
    full = pd.read_parquet(FILES[0]); boot = pd.read_csv(FILES[1]); res = json.loads(FILES[2].read_text())
    return full, boot, res


full, boot, res = load(tuple(f.stat().st_mtime for f in FILES))
df = full[full.in_main == 1].copy(); sf = full[full.in_main == 0].copy()
s5, s6, s7, s8 = res["step5"], res["step6"], res["step7"], res["step8"]
pf, bs, sec, lm = s7["per_fte"], s8["bootstrap"], s8["sector"], s5["money"]
pp_double = lm["pp_per_doubling"]
pub, prv = s7["within_control"]["Public"]["per_fte"], s7["within_control"]["Private nonprofit"]["per_fte"]

# ------------------------------------------------------------------ masthead
st.markdown(f'''<div class="mast"><div class="mono">First gen completion · students who entered in fall 2017 · {s5["n"]:,} four year colleges · data through 2024</div>
<h1>Some colleges graduate first gen students far more often than expected.</h1>
<div class="by">Which ones, and how much of the gap is money. Built by <b>Isiah Luna</b>, a first gen transfer student at SDSU.</div></div>''', unsafe_allow_html=True)

tab_over, tab_rank, tab_spend, tab_method = st.tabs(["Overview", "All schools", "Where the money goes", "Methods & limitations"])


def school_block(row):
    """Lookup detail: ruled definition list (4 cols) beside the peer-spending chart (8 cols), then the similar-schools table."""
    b_row = boot[boot.unitid == row.unitid].iloc[0]
    up = row.residual_eb >= 0
    left, right = st.columns([4, 8])
    with left:
        st.markdown(f'<div class="hero"><div class="mono">Points above expected</div><div class="n" style="font-size:56px;color:{ACCENT if up else GRAPHITE}">{row.residual_eb_pct_pts:+.1f}</div></div>', unsafe_allow_html=True)
        st.markdown(f'''<div class="dl">
<div class="r"><span>Expected to graduate</span><span>{row.predicted:.0%}</span></div>
<div class="r"><span>Actually graduated</span><span>{row.firstgen_comp_orig_yr6_rt:.0%}</span></div>
<div class="r"><span>First-gen students in this cohort</span><span>{int(row.firstgen_yr6_n):,}</span></div>
<div class="r"><span>Rank among {len(df):,} colleges</span><span>{int(row['rank'])}</span></div>
<div class="r"><span>Stays in top 10% when re-run</span><span>{b_row.p_top_decile:.0%}</span></div>
<div class="r"><span>Type</span><span>{TYPE[row.control_label]} · {KIND[row.carnegie_group]}</span></div>
<div class="r"><span>Undergrads (2017)</span><span>{int(row.ugds):,}</span></div>
<div class="r"><span>On Pell Grants · admitted · first-gen</span><span>{row.pctpell:.0%} · {row.adm_rate:.0%} · {row.first_gen:.0%}</span></div>
<div class="r"><span>Non-first-gen students graduated</span><span>{row.not1stgen_comp_orig_yr6_rt:.0%}</span></div>
</div>''', unsafe_allow_html=True)
    with right:
        section("Where this school's money goes, compared with peers", "$ per student per year · 2018-23 average")
        peers = df[df.control_label == row.control_label]
        cats = list(CORE.values())
        fig = go.Figure()
        fig.add_bar(name="This school", x=cats, y=[row[f"{k}_per_fte"] for k in CORE], marker_color=INK, marker_line_width=0)
        fig.add_bar(name=f"Typical {TYPE[row.control_label].lower()} school", x=cats, y=[peers[f"{k}_per_fte"].median() for k in CORE], marker_color=MID, marker_line_width=0)
        fig.add_bar(name=f"Typical top-10% {TYPE[row.control_label].lower()} school", x=cats, y=[peers[peers.group == "top 10%"][f"{k}_per_fte"].median() for k in CORE], marker_color=ACCENT, marker_line_width=0)
        fig.update_layout(barmode="group", bargap=0.4, yaxis=dict(tickprefix="$", separatethousands=True))
        st.plotly_chart(chart(fig, 330), use_container_width=True, key="card_spend")
        t_med = peers[peers.group == "top 10%"]["exp_instruction_per_fte"].median()
        meaning(f"{row.instnm} spends ${row.exp_instruction_per_fte:,.0f} per student on teaching. The typical top 10% {TYPE[row.control_label].lower()} school spends ${t_med:,.0f}.")
    section("Similar schools that do better", "expected within ±3 points")
    near = df[(df.predicted - row.predicted).abs() < 0.03].sort_values("residual_eb", ascending=False).head(8)
    st.dataframe(near[["rank", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "predicted", "firstgen_comp_orig_yr6_rt", "residual_eb_pct_pts"]].assign(control_label=lambda d: d.control_label.map(TYPE), carnegie_group=lambda d: d.carnegie_group.map(KIND)).rename(columns={"rank": "Rank", "instnm": "School", "stabbr": "State", "control_label": "Type", "carnegie_group": "Kind", "ugds": "Undergrads", "pctpell": "On Pell", "predicted": "Expected", "firstgen_comp_orig_yr6_rt": "Actually graduated", "residual_eb_pct_pts": "Points above expected"})
                 .style.format({"Rank": "{:.0f}", "On Pell": "{:.0%}", "Expected": "{:.0%}", "Actually graduated": "{:.0%}", "Points above expected": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True, height=320)
    meaning(f"Each was expected to graduate about {row.predicted:.0%} of its first gen students, like {row.instnm}, and beat that by the most. Call them.")


# ------------------------------------------------------------------ Overview
with tab_over:
    # Row 1 (8/4): the hero number beside the dense list
    L, R = st.columns([8, 4])
    with L:
        st.markdown(f'''<div class="hero"><div class="mono">Share of the gap explained by money</div><div class="n">{lm["r2"]*100:.0f}%</div>
<div class="d">How much a college spends, and what it spends it on, explains about {lm["r2"]*100:.0f}% of why some schools beat the odds for first gen students. The other {100 - lm["r2"]*100:.0f}% sits outside the budget data. The useful output is the school list beside this and the search box below.</div></div>''', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        stat(c1, "Colleges compared", f"{s5['n']:,}", f"four-year public and private · {s5['n_excluded']} special cases set aside")
        stat(c2, "How much the model explains", f"{s5['r2_main']:.0%}", "of the difference in first-gen graduation between schools")
        stat(c3, "Typical first-gen graduation", f"{s5['outcome_mean']:.0%}", "within six years, same school")
        stat(c4, "Top 10% beat expectations by", f"+{s6['top_decile_cut_pp']:.0f} pts", f"or more · {s6['top_decile_n']} schools", accent=True)
    with R:
        section("Large schools that beat expectations", "500 or more first gen students in the cohort")
        big = df[df.firstgen_yr6_n >= 500].sort_values("residual_eb", ascending=False).head(6)
        rows = "".join(f'<div class="row"><span class="pt">{r.residual_eb_pct_pts:+.0f}</span><div class="nm">{r.instnm}</div>'
                       f'<div class="meta">{r.stabbr} · {TYPE[r.control_label]} · {int(r.firstgen_yr6_n):,} first-gen students · expected <b>{r.predicted:.0%}</b>, graduated <b>{r.firstgen_comp_orig_yr6_rt:.0%}</b></div></div>' for r in big.itertuples())
        st.markdown(f'<div class="list">{rows}</div>', unsafe_allow_html=True)
        meaning(f"Expected is what a school with the same mix of students, size and type usually achieves. These six beat it by {big.residual_eb_pct_pts.min():.0f} to {big.residual_eb_pct_pts.max():.0f} points on cohorts of {big.firstgen_yr6_n.min():,.0f} or more, so small numbers cannot explain it.")

    st.markdown('<div class="rule-strong"></div>', unsafe_allow_html=True)
    # Row 2 (4/8): lookup beside the scatter
    L, R = st.columns([4, 8])
    with L:
        section("Look up any college")
        names = (df.sort_values("instnm")["instnm"] + " (" + df.sort_values("instnm")["stabbr"] + ")").reset_index(drop=True)
        default = "San Diego State University (CA)"
        pick = st.selectbox("Look up any college", names, index=int(names[names == default].index[0]) if (names == default).any() else 0, label_visibility="collapsed")
        row = df.sort_values("instnm").iloc[names[names == pick].index[0]]
        st.markdown(f'<div class="mono" style="margin-top:.6rem">Selected</div><div style="font-family:"Times New Roman",Times,serif;font-size:1.35rem;font-weight:500;color:{INK};line-height:1.2;margin:.2rem 0 .4rem 0">{row.instnm}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="dl"><div class="r"><span>Points above expected</span><span style="color:{ACCENT if row.residual_eb >= 0 else GRAPHITE}">{row.residual_eb_pct_pts:+.1f}</span></div><div class="r"><span>Expected · actual</span><span>{row.predicted:.0%} · {row.firstgen_comp_orig_yr6_rt:.0%}</span></div><div class="r"><span>Rank</span><span>{int(row["rank"])} of {len(df):,}</span></div></div>', unsafe_allow_html=True)
        st.caption("Full detail for this school is further down the page.")
    with R:
        section("Expected vs actual first-gen graduation", "one dot per college")
        fig = go.Figure()
        for g, c, nm, op, sz in [("middle", MID, "Middle 80% of schools", .9, 5), ("bottom 10%", GRAPHITE, "Bottom 10%: below expected", .9, 6), ("top 10%", ACCENT, "Top 10%: above expected", .95, 6)]:
            d = df[df.group == g]
            fig.add_scatter(x=d.predicted, y=d.firstgen_comp_orig_yr6_rt, mode="markers", name=nm, marker=dict(color=c, size=sz, opacity=op, line=dict(width=0)),
                            customdata=np.stack([d.instnm, d.stabbr, d.control_label.map(TYPE), d.ugds, d.pctpell], axis=1),
                            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>%{customdata[2]} · %{customdata[3]:,} undergrads · %{customdata[4]:.0%} on Pell<br>expected %{x:.0%} · actual %{y:.0%}<extra></extra>")
        fig.add_scatter(x=[row.predicted], y=[row.firstgen_comp_orig_yr6_rt], mode="markers+text", name=row.instnm, marker=dict(color=INK, size=11, symbol="circle-open", line=dict(width=2, color=INK)), text=[row.instnm.split("-")[0]], textposition="top left", textfont=dict(color=INK, size=11), hoverinfo="skip")
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=INK, dash="dot", width=1), name="Actual = expected", hoverinfo="skip")
        fig.update_layout(xaxis_title="Expected graduation rate", yaxis_title="Actual graduation rate", xaxis=dict(range=[0.05, 1], tickformat=".0%"), yaxis=dict(range=[0, 1], tickformat=".0%"))
        st.plotly_chart(chart(fig, 420), use_container_width=True, key="ov_scatter")
        meaning(f"One dot per college, {len(df):,} in all. Above the dotted line a college graduated more first gen students than expected, below it fewer. The open circle is {row.instnm}.")

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    # Row 3 (7/5): spending bars beside the compact predictor list
    L, R = st.columns([7, 5])
    with L:
        section("Where the top 10% spend more", "median $ per student per year · top vs bottom 10%")
        st.plotly_chart(spend_bar(df[df.group == "top 10%"], df[df.group == "bottom 10%"], 380), use_container_width=True, key="ov_spend")
        meaning(f"Schools that beat expectations spend {pf['Instruction']['median_ratio']:.1f} times as much per student on teaching and {pf['Academic support']['median_ratio']:.1f} times as much on academic support as schools that fall short, {pf['Student services']['median_ratio']:.2f} times on student services and {pf['Institutional support']['median_ratio']:.2f} times on administration. With the budget size held fixed, one standard deviation more academic support share is associated with {lm['pp_per_sd_acad_share']:+.1f} points, and doubling the budget with {pp_double:+.1f}. Set against a top 10% bar of +{s6['top_decile_cut_pp']:.0f}, both are small. That is the {lm['r2']*100:.0f}%.")
    with R:
        section("What predicts first-gen graduation", "points, going from 0% to 100%")
        terms = [k for k in PLAIN if k in s5["coef_A"]]
        co = pd.DataFrame({"term": [PLAIN[k] for k in terms], "coef": [s5["coef_A"][k] * 100 for k in terms], "se": [s5["se_A"][k] * 100 for k in terms]})
        fig = go.Figure(go.Bar(x=co.coef, y=co.term, orientation="h", marker_color=[ACCENT if v > 0 else GRAPHITE for v in co.coef], marker_line_width=0,
                               error_x=dict(type="data", array=1.96 * co.se, color=INK2, thickness=1), hovertemplate="%{y}: %{x:+.1f} points<extra></extra>"))
        fig.update_layout(yaxis=dict(autorange="reversed"), bargap=0.45, xaxis=dict(ticksuffix=" pts"))
        st.plotly_chart(chart(fig, 380, legend=False, ygrid=False), use_container_width=True, key="ov_coef")
        meaning(f"A school where every student is on a Pell Grant is expected to graduate about {abs(s5['coef_A']['pctpell'])*100:.0f} points fewer first gen students than one where none are. Expected rates come from slopes like these, fitted with separate slopes for public and private schools.")

    st.markdown('<div class="rule-strong"></div>', unsafe_allow_html=True)
    section(f"{row.instnm}", f"full detail for the selected school")
    school_block(row)

# ------------------------------------------------------------------ All schools
with tab_rank:
    section(f"All {len(df):,} colleges, ranked by points above expected", "filters apply to the table and the download")
    f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 3, 3])
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
    mono(f"{len(d):,} colleges match · rank is among all {len(df):,} · points above expected are shrunk toward zero for small cohorts, so a lucky year at a small school counts for less")
    show = d[["rank", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "firstgen_yr6_n", "firstgen_comp_orig_yr6_rt", "predicted", "residual_eb_pct_pts", "residual_pct_pts", "p_top_decile", "rank_range", "exp_core_per_fte"]].assign(control_label=lambda x: x.control_label.map(TYPE), carnegie_group=lambda x: x.carnegie_group.map(KIND)).rename(columns={
        "rank": "Rank", "instnm": "School", "stabbr": "State", "control_label": "Type", "carnegie_group": "Kind", "ugds": "Undergrads (2017)", "pctpell": "On Pell", "firstgen_yr6_n": "First-gen students", "firstgen_comp_orig_yr6_rt": "Actually graduated",
        "predicted": "Expected", "residual_eb_pct_pts": "Points above expected", "residual_pct_pts": "Before small-school adjustment", "p_top_decile": "Stays in top 10% (share of re-runs)", "rank_range": "Likely rank range", "exp_core_per_fte": "Core spending per student"})
    st.dataframe(show.style.format({"Rank": "{:.0f}", "On Pell": "{:.0%}", "Actually graduated": "{:.0%}", "Expected": "{:.0%}", "Points above expected": "{:+.1f}", "Before small-school adjustment": "{:+.1f}", "Stays in top 10% (share of re-runs)": "{:.0%}",
                                   "Core spending per student": "${:,.0f}", "Undergrads (2017)": "{:,.0f}", "First-gen students": "{:,.0f}"}), use_container_width=True, height=560, hide_index=True)
    st.download_button("Download this list (CSV)", show.to_csv(index=False).encode(), "colleges_ranked.csv", "text/csv")
    meaning(f"A college at {s6['top_decile_cut_pp']:+.0f} graduates first gen students {s6['top_decile_cut_pp']:.0f} points more often than schools with the same kind of students usually do. 'Stays in top 10%' is how often it keeps that place across {bs['B']:,} re runs that redraw both the set of schools and each school's own graduation count. Top 10% schools keep their place {bs['mean_p_top_among_point_top']:.0%} of the time on average, and a typical top 10% school's likely rank range spans {bs['median_rank_ci_width_top_decile']:.0f} positions.")
    with st.expander(f"{len(sf)} special cases, scored but not ranked"):
        st.write(f"Four groups the comparison does not fit. {s5['n_special_focus']} colleges built around one program (nursing, faith, arts). {s5['n_nontraditional']} campuses where more than half of students are aged 25 or older or fully online. "
                 f"{s5['n_anomaly']} schools whose reported graduation numbers cannot be right (San Jose State's {res['step4']['anomalies'][0]['firstgen_rate']:.1%} against a {res['step4']['anomalies'][0]['ipeds_grad_rate_c150_4']:.0%} overall graduation rate). "
                 f"{s5['n_shared_opeid']} campuses whose first gen graduation rate is pooled with other campuses under one OPEID, because the Scorecard reports completion per OPEID rather than per campus. A campus stays in the ranking only if it holds at least {res['step4']['thresholds']['opeid_share_cut']:.0%} of its group's undergraduates. Shown so nothing is hidden.")
        st.dataframe(sf.sort_values(["excluded_reason", "residual"], ascending=[True, False])[["excluded_reason", "instnm", "stabbr", "control_label", "ugds", "ug25abv", "pct_distance", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts"]].assign(control_label=lambda x: x.control_label.map(TYPE)).rename(columns={
            "excluded_reason": "Why set aside", "instnm": "School", "stabbr": "State", "control_label": "Type", "ugds": "Undergrads", "ug25abv": "Aged 25+", "pct_distance": "Fully online", "pctpell": "On Pell", "firstgen_comp_orig_yr6_rt": "Actually graduated", "predicted": "Expected", "residual_pct_pts": "Points above expected"})
                     .style.format({"On Pell": "{:.0%}", "Aged 25+": "{:.0%}", "Fully online": "{:.0%}", "Actually graduated": "{:.0%}", "Expected": "{:.0%}", "Points above expected": "{:+.1f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ Where the money goes
with tab_spend:
    section("Where the money goes", "top 10% of schools compared with the bottom 10% · $ per student per year, 2018-23 average")
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
        note = f"Table: {TYPE[scope].lower()} schools ranked only against other {TYPE[scope].lower()} schools. Chart: the main ranking's top and bottom 10% restricted to {TYPE[scope].lower()} schools (top {len(top)}, bottom {len(bot)})."
    else:
        dd = df[df.carnegie_group == scope]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = s7["within_carnegie"][scope]["per_fte"]
        note = f"Main ranking groups restricted to {KIND[scope].lower()}s (top {len(top)}, bottom {len(bot)})."
    mono(note)
    L, R = st.columns([7, 5])
    L.plotly_chart(spend_bar(top, bot, 400), use_container_width=True, key="spend_tab_main")
    rename = {"Instruction": "Teaching", "Academic support": "Academic support", "Student services": "Student services", "Institutional support": "Administration", "Core (4 categories)": "All four together"}
    t = compare_table(top, bot) if tab is None else pd.DataFrame([{"Spending category": rename[k], "Top 10%": v["top10_median_$"], "Bottom 10%": v["bottom10_median_$"], "Top ÷ bottom": v["median_ratio"], "p-value": v["mann_whitney_p"]} for k, v in tab.items() if k in rename])
    R.dataframe(t.style.format({"Top 10%": "${:,.0f}", "Bottom 10%": "${:,.0f}", "Top ÷ bottom": "{:.2f}×", "p-value": "{:.3f}"}), hide_index=True, use_container_width=True)
    R.caption("p-value: the chance of seeing a gap this big if there were really no difference. Below 0.05 is the usual bar.")
    ti = t.set_index("Spending category")
    meaning(f"In this group, schools that beat expectations spend {ti.loc['Teaching', 'Top ÷ bottom']:.2f} times as much per student on teaching and {ti.loc['Academic support', 'Top ÷ bottom']:.2f} times as much on academic support as schools that fall short, {ti.loc['Student services', 'Top ÷ bottom']:.2f} times on student services and {ti.loc['Administration', 'Top ÷ bottom']:.2f} times on administration.")
    st.markdown(f"Among public colleges, the ones that beat expectations spend more on everything: teaching {pub['Instruction']['median_ratio']:.2f} times as much as the publics that fall short, academic support {pub['Academic support']['median_ratio']:.2f} times, student services {pub['Student services']['median_ratio']:.2f} times. "
                f"Among private colleges the gap is teaching ({prv['Instruction']['median_ratio']:.2f} times) and academic support ({prv['Academic support']['median_ratio']:.2f} times), with student services about equal ({prv['Student services']['median_ratio']:.2f} times). "
                f"The teaching and academic support gaps hold in every group I checked, including after a Benjamini and Hochberg correction for running {s7['bh']['n_tests']} comparisons. The student services gap does not.")
    with st.expander("Does the answer change if we look at different years, or adjust for inflation?"):
        var = pd.DataFrame({"2018-23, the main figure": {rename[k]: v["median_ratio"] for k, v in pf.items() if k in rename}, "2018-19 only (first two years)": {rename[k]: v["median_ratio"] for k, v in s7["per_fte_fy1819"].items() if k in rename},
                            "2018-23 in 2023 dollars": {rename[k]: v["median_ratio"] for k, v in s7["per_fte_real"].items() if k in rename}, "2023 only (after students left)": {rename[k]: v["median_ratio"] for k, v in s7["per_fte_fy23_only"].items() if k in rename}})
        st.dataframe(var.style.format("{:.2f}×"), use_container_width=True)
        meaning(f"No. Teaching stays between {var.loc['Teaching'].min():.2f} and {var.loc['Teaching'].max():.2f} times and academic support between {var.loc['Academic support'].min():.2f} and {var.loc['Academic support'].max():.2f} times, whichever years are used and with or without the inflation adjustment.")

# ------------------------------------------------------------------ Methods (all technical detail lives here)
with tab_method:
    section("Methods & limitations", "the technical version")
    st.markdown(f"""
**Plain English labels on the other tabs map to these terms.** "Expected" = fitted value of the ranking model. "Points above expected" = the residual (actual minus predicted, times 100) after empirical Bayes shrinkage. "How much the model explains" = R² of the ranking model. "Top 10% of schools" = top decile of the shrunken residual. "Stays in top 10%" = share of {bs['B']:,} bootstrap resamples in which the school lands in the top decile. "Before small school adjustment" = raw residual. "Share of the gap explained by money" = partial R² of the ranking model with and without spending level and mix.

**Timing.** The outcome is the NSLDS cohort that entered in the 2017 to 2018 academic year, measured in 2023 to 2024 (Scorecard data dictionary cohort map). Predictors come from the 2017 to 2018 Scorecard file. Spending is the FY2018 to FY2023 average per twelve month FTE from IPEDS. Carnegie is the 2018 classification. Control, level and Title IV status come from 2023 IPEDS and are assumed stable.

**Data.** College Scorecard October 2026 release, dated file (the undated download URL served a stale 2024 file). IPEDS HD2023, IC2023, EF2017A_DIST, F1718 through F2223 finance (F1A public, F2 private nonprofit), EFIA2018 through EFIA2023. BLS CPI for all urban consumers via FRED. Opportunity Insights mobility report cards (context only). Joined on UNITID in DuckDB, with UNITID asserted unique after every join. Four year = bachelor's dominant in both 2017 to 2018 and today, and IPEDS level four or more years. For profits excluded (their finance form is not comparable).

**Sample.** {s5['n']:,} schools (Carnegie doctoral, master's, baccalaureate) after dropping privacy suppressed outcomes, first gen cohorts under {res['step4']['thresholds']['min_cohort']}, schools missing an entry year predictor, and schools with fewer than {res['step4']['thresholds']['min_fin_years']} fiscal years of finance data. Scored but not ranked: {s5['n_special_focus']} special focus or tribal schools, {s5['n_nontraditional']} campuses with more than {res['step4']['thresholds']['nontraditional_cut']:.0%} of undergraduates aged 25 or older or exclusively online, {s5['n_anomaly']} schools with implausible Scorecard completion rates (first gen and non first gen rates both under {res['step4']['thresholds']['anomaly_ratio']:.0%} of the IPEDS graduation rate), and {s5['n_shared_opeid']} campuses whose outcome is pooled with other campuses under one OPEID. The Scorecard reports NSLDS completion per six digit OPEID, so a campus is kept only if it holds at least {res['step4']['thresholds']['opeid_share_cut']:.0%} of its group's Fall 2017 undergraduates.

**Who is missing.** The {res['step4']['missingness']['privacy suppressed']['schools']:.0f} privacy suppressed schools have a median of {res['step4']['missingness']['privacy suppressed']['median_undergrads']:,.0f} undergraduates and are {res['step4']['missingness']['privacy suppressed']['private_share']:.0%} private, against {res['step4']['missingness']['main sample']['median_undergrads']:,.1f} and {res['step4']['missingness']['main sample']['private_share']:.0%} in the main sample, so the ranking over represents larger and public colleges and says nothing about colleges with fewer than {res['step4']['thresholds']['min_cohort']} first gen federal aid students in the cohort.

**Models.** Pooled Model A, OLS: first gen six year same institution completion ~ Pell share + admission rate (open admission = 1.0) + log enrollment + part time share + first gen share + share of undergraduates aged 25 or older + share exclusively online (all Fall 2017) + private + HBCU + Carnegie group. HC3 robust SEs. R² = {s5['r2_A']:.3f}. Residual = actual minus predicted, then shrunk toward zero by τ²/(τ²+σ²) with σ² the binomial variance for the school's first gen cohort (empirical Bayes, τ = {s6['tau_pp']:.1f} points, median shrink {s6['shrink_median']:.2f}). The ranking model is {s5['main_model']}: Model A plus private × every trait (Carnegie dummies shared), adopted because its shrunken ranking overlaps the public only and private only rankings' top deciles at {s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} versus {s5['ranking_comparison']['overlap_pool_vs_sector_public']:.0%} and {s5['ranking_comparison']['overlap_pool_vs_sector_private']:.0%} for the pooled model (R² {s5['r2_main']:.3f}). The predictor chart on the Overview shows the pooled model's slopes for readability. Spending is left out of the ranking model on purpose so the spending comparison is not circular.

**Sector slopes.** Joint Wald F test of the private × trait terms: F = {s5['joint_F_interactions']['F']:.2f}, p {'< 0.001' if s5['joint_F_interactions']['p'] < 0.001 else f"= {s5['joint_F_interactions']['p']:.3f}"}. A fractional logit fit ranks schools the same (Spearman {s8['fractional_logit']['spearman_vs_main']:.3f}, top decile overlap {s8['fractional_logit']['top_decile_overlap_vs_main']:.0%}).

**How much is money.** Partial R² of nested models: adding log core spending per FTE, the undergraduate share of FTE, instruction share and academic support share to the ranking model removes {lm['r2']:.1%} of its unexplained variance (level alone {lm['r2_level_only']:.1%}, mix alone {lm['r2_mix_only']:.1%}, full model R² {lm['r2_full_model']:.3f} against {lm['r2_ranking_model']:.3f}). Doubling core spending per FTE is associated with {pp_double:+.1f} points (p {'< 0.001' if lm['p']['log_core_per_fte'] < 0.001 else f"= {lm['p']['log_core_per_fte']:.3f}"}), one SD more academic support share with {lm['pp_per_sd_acad_share']:+.1f} (p = {lm['p']['acad_share']:.3f}) and one SD more instruction share with {lm['pp_per_sd_instr_share']:+.1f} (p = {lm['p']['instr_share']:.3f}). The earlier regression of the shrunken residual on raw spending (R² {s7['residual_on_raw_spending']['r2']:.3f}) is kept in Step 7 as a sensitivity. It understates the coefficients, since spending overlaps the traits already in the model.

**Spending comparison.** Top against bottom decile medians of IPEDS functional expenses per FTE. Mann Whitney U is the decision test, with a Welch t test on log dollars beside it. Repeated within sector, within Carnegie group, with FY2018 to FY2019 only, in constant FY2023 dollars, and after dropping the {s7['n_cooks_dropped']} schools flagged by Cook's distance (4/n rule). A Benjamini and Hochberg correction across all {s7['bh']['n_tests']} Mann Whitney p values keeps the instruction and academic support gaps in every comparison and never the student services gap. The within sector numbers quoted on the money tab are the main ranking's deciles split by sector (public top {s7['within_control']['Public']['n_top']}, bottom {s7['within_control']['Public']['n_bottom']}, private top {s7['within_control']['Private nonprofit']['n_top']}, bottom {s7['within_control']['Private nonprofit']['n_bottom']}), because those tests sit inside that family. The separate public and private models in Step 8 agree with the main ranking (Spearman {sec['Public']['spearman_vs_pooled']:.2f} and {sec['Private nonprofit']['spearman_vs_pooled']:.2f}). Budget shares sum to 100% and are not reported as findings separate from dollar differences.

**Robustness.** VIF: only the share aged 25 or older exceeds five ({s5['vif']['ug25abv']:.2f}). Pell share and first gen share correlate at {s5['corr_pell_firstgen']:.2f} with VIFs of {s5['vif']['pctpell']:.2f} and {s5['vif']['first_gen']:.2f}. Bootstrap of {bs['B']:,} resamples: each resample redraws the set of schools with replacement and each school's graduation count from Binomial(cohort, observed rate), then refits the model and re applies the shrinkage, so the intervals carry each school's own sampling noise as well as the uncertainty in the prediction line. Top decile schools stay top decile {bs['mean_p_top_among_point_top']:.0%} of the time, two random resamples share {bs['mean_pairwise_top_decile_overlap']:.0%} of their top decile, and the median width of a top decile school's likely rank range is {bs['median_rank_ci_width_top_decile']:.0f} positions out of {s5['n']:,}. Dropping the largest 5% of schools: Spearman {s8['drop5']['spearman']:.3f} (weak test, kept because the brief asked).

**What changed after review.** The first build used a stale Scorecard file, 2024 traits, FY2023 only spending and no Carnegie control. Only {s6['top20_overlap_vs_v1']} of its top 20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}). Setting aside the shared OPEID campuses in the sixth pass replaced {20 - s6['top20_overlap_vs_v4']} of the previous top 20 (Spearman {s6['spearman_vs_v4']:.3f} on the schools both rankings share). The teaching and academic support spending pattern held through every change.

**Limitations.**
- *School level data.* I observe institutions, not students. A school can over perform through program mix, or through who it enrolls, in ways the predictors do not capture.
- *Correlation only.* Spending differences describe what over performers look like. They do not show that moving dollars would raise completion.
- *Outcome definition.* Completion at the same institution within six years for federal aid students. Transfers who finish elsewhere count as non completers.
- *Suppression bias.* Privacy suppression removes the smallest and mostly private schools, as the paragraph on who is missing says, so the ranking describes colleges with at least {res['step4']['thresholds']['min_cohort']} first gen federal aid students in the cohort.

Source code, reports and the decisions log: https://github.com/isiahmello24-beep/first-gen-beating-odds
    """)
