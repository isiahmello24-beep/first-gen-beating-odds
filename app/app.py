"""Streamlit dashboard: which colleges graduate first gen students far more often than expected,
and how much money explains the gap.

Run from the project root:  streamlit run app/app.py
Reads data/clean/analysis_scored.parquet, data/clean/bootstrap_ranks.csv and reports/results.json (from src/05 to src/08).

Design direction: editorial data desk. Warm paper base, hairline rules instead of shadows, Newsreader (self hosted, OFL) for the headline, section titles, hero and stat numbers, IBM Plex Sans (self hosted, OFL, tabular figures) for body, labels, tabs, tables, widgets and charts, and ONE accent color reserved for the finding (schools above expected).
Color meaning is fixed on every chart: accent = above expected or top 10%, graphite = below expected or bottom 10%. Streamlit chrome is hidden. Widgets are square with a single hairline.
Asymmetric twelve column grid: 8/4, 4/8, 7/5. Plain spoken labels. Technical detail lives in the Methods tab, capped at 72ch.
"""
import base64
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
PLAIN = {"pctpell": "Share of students on Pell Grants", "adm_rate": "Share of applicants admitted", "log_ugds": "Size (per doubling of enrollment)", "pptug_ef": "Share studying part time",
         "first_gen": "Share who are first gen", "ug25abv": "Share aged 25 or older", "pct_distance": "Share fully online", "private": "Private college (vs public)", "hbcu_flag": "Historically Black college",
         f"{CARN}[T.Doctoral]": "Research university (vs master's)", f"{CARN}[T.Baccalaureate]": "Bachelor's focused college (vs master's)"}
TYPE = {"Public": "Public", "Private nonprofit": "Private"}
KIND = {"Doctoral": "Research university", "Master's": "Master's university", "Baccalaureate": "Bachelor's college"}

SERIF = '"Newsreader", Georgia, "Times New Roman", serif'
SANS = '"IBM Plex Sans", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif'


@st.cache_resource
def font_faces():
    """@font-face rules for the self-hosted fonts in app/static/fonts (OFL), inlined as base64 so the page calls no outside font server."""
    faces = [("Newsreader", "newsreader.woff2", "normal", "200 800"), ("Newsreader", "newsreader-italic.woff2", "italic", "200 800"),
             ("IBM Plex Sans", "plexsans.woff2", "normal", "100 700"), ("IBM Plex Sans", "plexsans-italic.woff2", "italic", "100 700")]
    rules = []
    for family, name, style, weight in faces:
        path = ROOT / "app" / "static" / "fonts" / name
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            rules.append(f'@font-face {{ font-family: "{family}"; src: url(data:font/woff2;base64,{data}) format("woff2"); font-weight: {weight}; font-style: {style}; font-display: swap; }}')
    return "\n".join(rules)


st.markdown(f"""
<style>
  {font_faces()}
  /* ---- type: Newsreader for headlines and display numbers, IBM Plex Sans for everything else (tabular figures by default) */
  html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp input, .stApp button, .stMarkdown, .stCaption, [data-testid="stMarkdownContainer"], .mono,
  [data-testid="stDataFrame"], [data-testid="stDataFrame"] *, [data-baseweb="select"] *, [data-baseweb="popover"] *, [data-baseweb="menu"] *, [data-baseweb="tab"] *,
  .stRadio *, .stNumberInput *, .stButton *, .stDownloadButton *, .stTextInput * {{ font-family: {SANS} !important; }}
  .mast h1, .sec .t, .hero .n, .stat .n, .list .pt, .sel-name, div[data-testid="stExpander"] summary p {{ font-family: {SERIF} !important; font-optical-sizing: auto; }}
  .stApp [data-testid="stIconMaterial"] {{ font-family: "Material Symbols Rounded" !important; }}
  .hero .n, .stat .n, .list .pt, .dl .r, [data-testid="stDataFrame"], [data-testid="stDataFrame"] * {{ font-variant-numeric: tabular-nums; }}
  /* ---- Streamlit chrome off: header, toolbar, menu, decoration strip, footer, element toolbars, plotly modebar */
  header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], #MainMenu, footer,
  [data-testid="stElementToolbar"], .modebar {{ display: none !important; }}
  .stApp, [data-testid="stAppViewContainer"] {{ background: {PAPER}; color: {INK}; }}
  .stApp p, .stApp li, .stApp label, .stApp span {{ color: inherit; }}
  .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1440px; }}
  .mono {{ font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: {INK2}; }}
  .mast {{ border-top: 3px solid {INK}; padding-top: .6rem; }}
  .mast h1 {{ font-weight: 500; font-size: 2.6rem; line-height: 1.1; letter-spacing: -.005em; color: {INK}; margin: .5rem 0 .6rem 0; max-width: 34ch; }}
  .mast h1 a, .mast h1 [data-testid="stHeaderActionElements"] {{ display: none !important; }}
  .mast .by {{ font-size: .92rem; color: {INK2}; }}
  .mast .by b {{ color: {INK}; font-weight: 500; }}
  .rule {{ border-top: 1px solid {RULE}; margin: 1.1rem 0 .9rem 0; }}
  .rule-strong {{ border-top: 2px solid {INK}; margin: 1.4rem 0 .9rem 0; }}
  .sec {{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:.25rem 1rem; border-bottom: 1px solid {RULE}; padding-bottom:.35rem; margin: .2rem 0 .7rem 0; }}
  .sec .mono {{ margin-left:auto; }}
  .sec .t {{ font-size: 1.3rem; font-weight: 500; color: {INK}; }}
  .hero .n {{ font-size: 76px; font-weight: 400; line-height: .95; color: {ACCENT}; margin: .35rem 0 .2rem 0; letter-spacing: -.01em; }}
  .hero .d {{ font-size: 1rem; color: {INK}; max-width: 56ch; line-height: 1.5; }}
  .stat {{ border-top: 1px solid {RULE}; padding: .55rem 0 .3rem 0; }}
  .stat .n {{ font-size: 32px; font-weight: 500; color: {INK}; line-height: 1.05; margin: .25rem 0 .15rem 0; }}
  .stat .n.acc {{ color: {ACCENT}; }}
  .stat .s {{ font-size: .8rem; color: {INK2}; }}
  .list .row {{ border-bottom: 1px solid {RULE}; padding: .6rem 0 .55rem 0; }}
  .list .row:first-child {{ border-top: 1px solid {RULE}; }}
  .list .nm {{ font-weight: 600; color: {INK}; font-size: .95rem; }}
  .list .pt {{ color: {ACCENT}; font-size: 1.5rem; font-weight: 500; float: right; margin-top: -.15rem; }}
  .list .meta {{ font-size: .8rem; color: {INK2}; margin-top: .15rem; }}
  .list .meta b {{ color: {INK}; font-weight: 500; }}
  .sel-name {{ font-size: 1.35rem; font-weight: 500; color: {INK}; line-height: 1.2; margin: .2rem 0 .4rem 0; }}
  .surface {{ background: {SURFACE}; border: 1px solid {RULE}; padding: 1rem 1.1rem .4rem 1.1rem; }}
  .meaning {{ font-size: .9rem; color: {INK}; border-left: 2px solid {INK}; padding: .15rem 0 .15rem .75rem; margin: .1rem 0 .6rem 0; max-width: 72ch; }}
  .meaning b {{ font-weight: 600; }}
  .dl .r {{ display:flex; justify-content:space-between; gap: 1rem; border-bottom:1px solid {RULE}; padding:.4rem 0; font-size:.9rem; }}
  .dl .r span:first-child {{ color:{INK2}; }}
  .dl .r span:last-child {{ color:{INK}; font-weight:500; text-align: right; }}
  .st-key-methods [data-testid="stMarkdown"] {{ max-width: 72ch; }}
  /* ---- tabs: sans caps, ink underline on the active tab (no accent), wraps instead of clipping on narrow screens */
  [data-testid="stTabs"] [role="tablist"] {{ gap: 0 1.4rem; flex-wrap: wrap; overflow: visible; border-bottom: 1px solid {RULE}; }}
  [data-testid="stTab"], [data-baseweb="tab"] {{ padding: .55rem 0 .45rem 0 !important; margin: 0 !important; background: transparent !important; border-bottom: 2px solid transparent; margin-bottom: -1px !important; }}
  [data-testid="stTab"][aria-selected="true"], [data-baseweb="tab"][aria-selected="true"] {{ border-bottom-color: {INK}; }}
  [data-testid="stTab"] p, [data-baseweb="tab"] p {{ font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: {INK2}; }}
  [data-testid="stTab"][aria-selected="true"] p, [data-testid="stTab"]:hover p, [data-baseweb="tab"][aria-selected="true"] p {{ color: {INK}; }}
  [data-testid="stTabs"] .react-aria-SelectionIndicator, [data-baseweb="tab-highlight"] {{ display: none !important; }}
  [data-baseweb="tab-border"] {{ background-color: {RULE}; }}
  /* ---- widgets: square corners, one hairline in the rule color, no double frames */
  [data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"], .react-aria-Popover, .react-aria-Popover > div, [role="listbox"], [role="listbox"] > div,
  [data-testid="stNumberInputContainer"], [data-baseweb="base-input"], [data-baseweb="input"], [data-baseweb="popover"] > div, [data-baseweb="menu"], [data-baseweb="tag"], [data-testid="stMultiSelectTagsContainer"] > div > span, [data-testid="stMultiSelectTagsContainer"] > div > div,
  .stNumberInput button, [data-testid="stDataFrame"] > div, [data-testid="stDataFrame"] [data-testid="stDataFrameResizable"], [data-testid="stDataFrame"] .dvn-scroller, [data-testid="stDataFrame"] .gdg-wmyidgi,
  div[data-testid="stExpander"] details, div[data-testid="stExpander"] summary, .stDownloadButton button {{ border-radius: 0 !important; }}
  [data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"], [data-testid="stNumberInputContainer"] {{ border: 1px solid {RULE} !important; background: {SURFACE} !important; }}
  [data-baseweb="select"] > div:focus-within, [data-testid="stSelectbox"] [role="group"]:focus-within, [data-testid="stMultiSelect"] [role="group"]:focus-within, [data-testid="stNumberInputContainer"]:focus-within {{ border-color: {INK} !important; box-shadow: none !important; outline: none !important; }}
  .react-aria-Popover, [data-testid="stMultiSelectDropdown"], [data-testid="stSelectboxDropdown"], [data-testid="stSelectboxVirtualDropdown"] {{ border: 1px solid {RULE} !important; border-radius: 0 !important; box-shadow: none !important; background: {SURFACE} !important; }}
  [data-testid="stMultiSelectDropdown"] [role="listbox"], [data-testid="stSelectboxDropdown"] [role="listbox"], [data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {{ border: none !important; }}
  [role="option"], [role="option"] > div {{ border-radius: 0 !important; }}
  [data-baseweb="base-input"], [data-baseweb="input"] {{ border: none !important; background: transparent !important; }}
  .stNumberInput button {{ border-left: 1px solid {RULE} !important; background: transparent !important; }}
  [data-baseweb="tag"] {{ background: {PAPER} !important; border: 1px solid {RULE} !important; color: {INK} !important; }}
  [data-baseweb="tag"] span, [data-baseweb="tag"] svg {{ color: {INK} !important; }}
  [data-testid="stDataFrame"] > div, [data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {{ border: 1px solid {RULE} !important; }}
  [data-testid="stDataFrame"] .dvn-scroller, [data-testid="stDataFrame"] .gdg-wmyidgi {{ border: none !important; }}
  [data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {{ background-color: {INK} !important; border-color: {INK} !important; }}
  [data-testid="stRadioOption"] > div > div:first-child {{ border-color: {INK2} !important; }}
  div[data-testid="stExpander"] {{ border: none; }}
  div[data-testid="stExpander"] details {{ border: 1px solid {RULE} !important; background: transparent; }}
  div[data-testid="stExpander"] summary p {{ font-size: 1.05rem; font-weight: 500; }}
  div[data-testid="stExpander"] summary:hover, div[data-testid="stExpander"] summary:hover p {{ color: {INK} !important; }}
  .stDownloadButton button {{ border: 1px solid {INK} !important; background: transparent !important; color: {INK} !important; min-height: 0 !important; padding: .4rem .9rem !important; line-height: 1.3; }}
  .stDownloadButton button p {{ font-size: 13px !important; }}
  .stDownloadButton button:hover {{ background: {INK} !important; color: {PAPER} !important; }}
  .stDownloadButton button:hover p {{ color: {PAPER} !important; }}
  @media (max-width: 900px) {{
    .mast h1 {{ font-size: 1.5rem; line-height: 1.2; margin: .35rem 0 .4rem 0; max-width: none; }}
    .hero .n {{ font-size: 56px; }}
    .block-container {{ padding-top: .8rem; }}
    [data-testid="stTabs"] [role="tablist"], [data-baseweb="tab-list"] {{ gap: 0 .9rem; }}
    [data-testid="stTab"] p, [data-baseweb="tab"] p {{ letter-spacing: .06em; }}
  }}
</style>""", unsafe_allow_html=True)


def mono(text):
    st.markdown(f'<div class="mono">{text}</div>', unsafe_allow_html=True)


def section(title, right=""):
    st.markdown(f'<div class="sec"><span class="t">{title}</span><span class="mono">{right}</span></div>', unsafe_allow_html=True)


def meaning(text):
    st.markdown(f'<div class="meaning">{text}</div>', unsafe_allow_html=True)


def stat(col, label, value, sub, accent=False):
    col.markdown(f'<div class="stat"><div class="mono">{label}</div><div class="n{" acc" if accent else ""}">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


NOBAR = {"displayModeBar": False}           # passed as config= to every st.plotly_chart
HOVER_USD = "%{customdata}: $%{y:,.0f} per student per year<extra>%{fullData.name}</extra>"   # bars carry the category name in customdata


def chart(fig, height=340, legend=True, ygrid=True):
    """House style for every plotly figure: transparent paper, 12px minimum text, no legend unless asked (direct labels are preferred)."""
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family=SANS, color=INK2, size=12), height=height,
                      margin=dict(l=6, r=6, t=26, b=6), title=None, showlegend=legend,
                      legend=dict(orientation="h", y=-0.24, x=0, xanchor="left", font=dict(color=INK2, size=12), bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor=INK, font_color=PAPER, bordercolor=INK, font_family=SANS, font_size=12))
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=RULE, tickfont=dict(color=INK2, size=12), title_font=dict(color=INK2, size=12))
    fig.update_yaxes(showgrid=ygrid, gridcolor="#E9E4D9", gridwidth=1, zeroline=False, linecolor=RULE, tickfont=dict(color=INK2, size=12), title_font=dict(color=INK2, size=12))
    return fig


def note(fig, x, y, text, color, xanchor="left", yanchor="bottom", xref="x", yref="y", **kw):
    """Direct label: a plain annotation in place of a legend entry."""
    fig.add_annotation(x=x, y=y, xref=xref, yref=yref, text=text, showarrow=False, xanchor=xanchor, yanchor=yanchor, align="left" if xanchor == "left" else "right",
                       font=dict(color=color, size=12, family=SANS), **kw)


def fmt_p(p):
    return "<0.001" if p < 0.0005 else f"{p:.3f}"


def rank_range(b):
    """'A to B': the span of a school's rank across the middle ninety five percent of bootstrap re runs."""
    return f"{b.boot_rank_p2_5:.0f} to {b.boot_rank_p97_5:.0f}"


def with_boot(d):
    return d.merge(boot[["unitid", "p_top_decile", "boot_rank_p2_5", "boot_rank_p97_5"]], on="unitid", how="left")


def short_name(nm, limit=28):
    return nm if len(nm) <= limit else nm[: limit - 1].rstrip() + "…"


def shrink(resid, pred, n):
    pred = pred.clip(0.05, 0.95); sigma2 = pred * (1 - pred) / n
    tau2 = max(float(resid.var() - sigma2.mean()), 1e-6)
    return resid * tau2 / (tau2 + sigma2)


def decile_groups(d, resid_col):
    dec = pd.qcut(d[resid_col], 10, labels=range(1, 11)).astype(int)
    return d[dec == 10], d[dec == 1]


def compare_table(top, bot):
    """Medians, ratio and Mann Whitney p for the SAME two groups the chart draws, so chart and table never disagree."""
    rows = []
    for k, lbl in list(CORE.items()) + [("exp_core", "All four together")]:
        a, b = top[f"{k}_per_fte"], bot[f"{k}_per_fte"]
        rows.append({"Spending category": lbl, "Top 10%": a.median(), "Bottom 10%": b.median(), "Top ÷ bottom": a.median() / b.median(), "p-value": stats.mannwhitneyu(a, b, alternative="two-sided").pvalue})
    return pd.DataFrame(rows)


def spend_bar(top, bot, height=340):
    """Grouped medians, top 10% in ACCENT and bottom 10% in GRAPHITE. The two groups are named once, above the first pair, instead of in a legend."""
    cats = list(CORE.values()); xs = list(range(len(cats)))
    t = [top[f"{k}_per_fte"].median() for k in CORE]; b = [bot[f"{k}_per_fte"].median() for k in CORE]
    fig = go.Figure()
    fig.add_bar(name=f"Top 10% (n = {len(top)})", x=xs, y=t, marker_color=ACCENT, marker_line_width=0, text=[f"${v:,.0f}" for v in t], textposition="outside", textfont=dict(color=INK, size=12, family=SANS), cliponaxis=False, hovertemplate=HOVER_USD, customdata=cats)
    fig.add_bar(name=f"Bottom 10% (n = {len(bot)})", x=xs, y=b, marker_color=GRAPHITE, marker_line_width=0, text=[f"${v:,.0f}" for v in b], textposition="outside", textfont=dict(color=INK2, size=12, family=SANS), cliponaxis=False, hovertemplate=HOVER_USD, customdata=cats)
    top_y = max(t + b)
    y0 = max(t[0], b[0])                       # two stacked lines, left-aligned on the first pair, clear of the $ labels
    note(fig, -0.3, y0, f"Top 10% · n = {len(top)}", ACCENT, yshift=40)
    note(fig, -0.3, y0, f"Bottom 10% · n = {len(bot)}", GRAPHITE, yshift=22)
    fig.update_layout(barmode="group", bargap=0.4, bargroupgap=0.06, yaxis_title="$ per student per year", yaxis=dict(tickprefix="$", separatethousands=True, range=[0, top_y * 1.32]),
                      xaxis=dict(tickvals=xs, ticktext=[c.replace(" ", "<br>") for c in cats], tickangle=0, range=[-0.5, len(cats) - 0.25]))
    return chart(fig, height, legend=False)


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
        st.markdown(f'<div class="hero"><div class="mono">Points above expected</div><div class="n" style="font-size:56px;color:{ACCENT if up else GRAPHITE}">{row.residual_eb_pct_pts:+.0f}</div></div>', unsafe_allow_html=True)
        st.markdown(f'''<div class="dl">
<div class="r"><span>Expected to graduate</span><span>{row.predicted:.0%}</span></div>
<div class="r"><span>Actually graduated</span><span>{row.firstgen_comp_orig_yr6_rt:.0%}</span></div>
<div class="r"><span>First gen students in this cohort</span><span>{int(row.firstgen_yr6_n):,}</span></div>
<div class="r"><span>Rank among {len(df):,} colleges</span><span>{int(row['rank'])} · likely {rank_range(b_row)} on re runs</span></div>
<div class="r"><span>In the top 10% on re runs</span><span>{b_row.p_top_decile:.0%} of re runs</span></div>
<div class="r"><span>Type</span><span>{TYPE[row.control_label]} · {KIND[row.carnegie_group]}</span></div>
<div class="r"><span>Undergrads (2017)</span><span>{int(row.ugds):,}</span></div>
<div class="r"><span>On Pell Grants · admitted · first gen</span><span>{row.pctpell:.0%} · {row.adm_rate:.0%} · {row.first_gen:.0%}</span></div>
<div class="r"><span>Not first gen students graduated</span><span>{row.not1stgen_comp_orig_yr6_rt:.0%}</span></div>
</div>''', unsafe_allow_html=True)
    with right:
        peers = df[df.control_label == row.control_label]; tops = peers[peers.group == "top 10%"]; kind = TYPE[row.control_label].lower()
        t_med = tops["exp_instruction_per_fte"].median()
        section(f"{row.instnm} spends ${row.exp_instruction_per_fte:,.0f} per student on teaching. Top 10% {kind} peers spend ${t_med:,.0f}",
                f"$ per student per year · 2018 to 2023 average · n = {len(peers)} {kind} schools, {len(tops)} in the top 10%")
        cats = list(CORE.values()); xs = list(range(len(cats)))
        series = [("This school", [row[f"{k}_per_fte"] for k in CORE], dict(marker_color="rgba(0,0,0,0)", marker_line=dict(color=INK, width=1.5)), INK),
                  (f"Typical {kind} school (n = {len(peers)})", [peers[f"{k}_per_fte"].median() for k in CORE], dict(marker_color=MID, marker_line_width=0), INK2),
                  (f"Top 10% {kind} peers (n = {len(tops)})", [tops[f"{k}_per_fte"].median() for k in CORE], dict(marker_color=ACCENT, marker_line_width=0), ACCENT)]
        fig = go.Figure()
        for nm, ys, style, tc in series:
            fig.add_bar(name=nm, x=xs, y=ys, customdata=cats, text=[f"${v / 1000:.1f}k" for v in ys], textposition="outside", textfont=dict(color=tc, size=12, family=SANS), cliponaxis=False, hovertemplate=HOVER_USD, **style)
        key = (f'<span style="color:{INK}">▢ This school</span>   <span style="color:{INK2}">■ Typical {kind} school · n = {len(peers)}</span><br>'
               f'<span style="color:{ACCENT}">■ Top 10% {kind} peers · n = {len(tops)}</span>')
        note(fig, 0, 1.0, key, INK2, xref="paper", yref="paper", yanchor="bottom", yshift=2)
        fig.update_layout(barmode="group", bargap=0.4, bargroupgap=0.05, yaxis=dict(tickprefix="$", separatethousands=True, range=[0, max(v for _, ys, _, _ in series for v in ys) * 1.18]),
                          xaxis=dict(tickvals=xs, ticktext=[c.replace(" ", "<br>") for c in cats], tickangle=0, range=[-0.5, len(cats) - 0.25]))
        fig = chart(fig, 340, legend=False); fig.update_layout(margin=dict(t=44))
        st.plotly_chart(fig, use_container_width=True, key="card_spend", config=NOBAR)
        meaning(f"{row.instnm} spends ${row.exp_instruction_per_fte:,.0f} per student on teaching. The typical top 10% {TYPE[row.control_label].lower()} school spends ${t_med:,.0f}.")
    pool = df[(df.predicted - row.predicted).abs() < 0.03]
    near = with_boot(pool.sort_values("residual_eb", ascending=False).head(8))
    section("Similar schools that do better", f"top {len(near)} of {len(pool)} schools expected within 3 points")
    near["rank_range"] = near.apply(rank_range, axis=1)
    st.dataframe(near[["rank", "rank_range", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "predicted", "firstgen_comp_orig_yr6_rt", "residual_eb_pct_pts"]].assign(control_label=lambda d: d.control_label.map(TYPE), carnegie_group=lambda d: d.carnegie_group.map(KIND)).rename(columns={"rank": "Rank", "rank_range": "Likely rank on re runs", "instnm": "School", "stabbr": "State", "control_label": "Type", "carnegie_group": "Kind", "ugds": "Undergrads", "pctpell": "On Pell", "predicted": "Expected", "firstgen_comp_orig_yr6_rt": "Actually graduated", "residual_eb_pct_pts": "Points above expected"})
                 .style.format({"Rank": "{:.0f}", "On Pell": "{:.0%}", "Expected": "{:.0%}", "Actually graduated": "{:.0%}", "Points above expected": "{:+.0f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True, height=320)
    meaning(f"Each was expected to graduate about {row.predicted:.0%} of its first gen students, like {row.instnm}, and beat that by the most. Call them.")


# ------------------------------------------------------------------ Overview
with tab_over:
    # Row 1 (8/4): the hero number beside the dense list
    L, R = st.columns([8, 4])
    with L:
        st.markdown(f'''<div class="hero"><div class="mono">Share of the gap explained by money</div><div class="n">{lm["r2"]*100:.0f}%</div>
<div class="d">How much a college spends, and what it spends it on, explains about {lm["r2"]*100:.0f}% of why some schools beat the odds for first gen students. The other {100 - lm["r2"]*100:.0f}% sits outside the budget data. The useful output is the school list beside this and the search box below.</div></div>''', unsafe_allow_html=True)
        c1, c2 = st.columns(2)   # hero + two tiles = the three headline numbers; R² and the outcome mean live in Methods
        stat(c1, "Top 10% beat expectations by", f"+{s6['top_decile_cut_pp']:.0f} pts", f"or more · {s6['top_decile_n']} schools", accent=True)
        stat(c2, "Colleges compared", f"{s5['n']:,}", f"four year public and private · {s5['n_excluded']} set aside")
    with R:
        section("Large schools that beat expectations", f"{s6['large_cohort_min']} or more first gen students in the cohort")
        big = with_boot(df[df.firstgen_yr6_n >= s6["large_cohort_min"]].sort_values("residual_eb", ascending=False).head(6))
        rows = "".join(f'<div class="row"><span class="pt">{r.residual_eb_pct_pts:+.0f}</span><div class="nm">{r.instnm}</div>'
                       f'<div class="meta">{r.stabbr} · {TYPE[r.control_label]} · {int(r.firstgen_yr6_n):,} first gen students · expected <b>{r.predicted:.0%}</b>, graduated <b>{r.firstgen_comp_orig_yr6_rt:.0%}</b> · '
                       f'rank <b>{int(r.rank)}</b>, likely {rank_range(r)} on re runs</div></div>' for r in big.itertuples())
        st.markdown(f'<div class="list">{rows}</div>', unsafe_allow_html=True)
        meaning(f"Expected is what a school with the same mix of students, size and type usually achieves. These six beat it by {big.residual_eb_pct_pts.min():.0f} to {big.residual_eb_pct_pts.max():.0f} points on cohorts of {big.firstgen_yr6_n.min():,.0f} or more, so small numbers cannot explain it.")

    st.markdown('<div class="rule-strong"></div>', unsafe_allow_html=True)
    # Row 2 (4/8): lookup beside the scatter
    L, R = st.columns([4, 8])
    with L:
        section("Look up any college")
        names = (df.sort_values("instnm")["instnm"] + " (" + df.sort_values("instnm")["stabbr"] + ")").reset_index(drop=True)
        default = "San Diego State University (CA)"
        idx = int(names[names == default].index[0]) if (names == default).any() else 0
        q = st.query_params.get("school")           # ?school=Channel%20Islands preselects the first case-insensitive substring match
        if q:
            hit = names[names.str.contains(q, case=False, regex=False)]
            if len(hit): idx = int(hit.index[0])
        pick = st.selectbox("Look up any college", names, index=idx, label_visibility="collapsed")
        row = df.sort_values("instnm").iloc[names[names == pick].index[0]]
        b_pick = boot[boot.unitid == row.unitid].iloc[0]
        st.markdown(f'<div class="mono" style="margin-top:.6rem">Selected</div><div class="sel-name">{row.instnm}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="dl"><div class="r"><span>Points above expected</span><span style="color:{ACCENT if row.residual_eb >= 0 else GRAPHITE}">{row.residual_eb_pct_pts:+.0f}</span></div><div class="r"><span>Expected · actual</span><span>{row.predicted:.0%} · {row.firstgen_comp_orig_yr6_rt:.0%}</span></div><div class="r"><span>Rank</span><span>{int(row["rank"])} of {len(df):,} · likely {rank_range(b_pick)}</span></div><div class="r"><span>In the top 10% on re runs</span><span>{b_pick.p_top_decile:.0%} of re runs</span></div></div>', unsafe_allow_html=True)
        st.caption("Full detail for this school is further down the page.")
    with R:
        n_top, n_bot, n_mid = (df.group == "top 10%").sum(), (df.group == "bottom 10%").sum(), (df.group == "middle").sum()
        section(f"{n_top} of {len(df):,} colleges graduate first gen students {s6['top_decile_cut_pp']:.0f} or more points above expected", f"one dot per college · n = {len(df):,}")
        fig = go.Figure()
        for g, c, nm, op, sz in [("middle", MID, f"Middle 80% (n = {n_mid})", .9, 5), ("bottom 10%", GRAPHITE, f"Bottom 10%: below expected (n = {n_bot})", .9, 6), ("top 10%", ACCENT, f"Top 10%: above expected (n = {n_top})", .95, 6)]:
            d = df[df.group == g]
            fig.add_scatter(x=d.predicted, y=d.firstgen_comp_orig_yr6_rt, mode="markers", name=nm, marker=dict(color=c, size=sz, opacity=op, line=dict(width=0)),
                            customdata=np.stack([d.instnm, d.stabbr, d.control_label.map(TYPE), d.ugds, d.pctpell], axis=1),
                            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>%{customdata[2]} · %{customdata[3]:,} undergrads · %{customdata[4]:.0%} on Pell<br>expected %{x:.0%} · actual %{y:.0%}<extra>%{fullData.name}</extra>")
        fig.add_scatter(x=[row.predicted], y=[row.firstgen_comp_orig_yr6_rt], mode="markers+text", name=row.instnm, marker=dict(color=INK, size=11, symbol="circle-open", line=dict(width=2, color=INK)), text=[short_name(row.instnm)], textposition="top right" if row.predicted < 0.3 else ("top left" if row.predicted > 0.7 else "top center"), textfont=dict(color=INK, size=12, family=SANS), hoverinfo="skip")
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=INK, dash="dot", width=1), name="Actual = expected", hoverinfo="skip")
        note(fig, 0.03, 0.97, f"Top 10%: above expected<br>n = {n_top}", ACCENT, yanchor="top")
        note(fig, 0.97, 0.03, f"Bottom 10%: below expected<br>n = {n_bot}", GRAPHITE, xanchor="right")
        fig.add_annotation(x=0.12, y=0.12, ax=30, ay=24, text="actual = expected", showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor=INK2, font=dict(color=INK2, size=12, family=SANS), xanchor="left")
        fig.update_layout(xaxis_title="Expected graduation rate", yaxis_title="Actual graduation rate", xaxis=dict(range=[0, 1], tickformat=".0%"), yaxis=dict(range=[0, 1], tickformat=".0%"))
        st.plotly_chart(chart(fig, 420, legend=False), use_container_width=True, key="ov_scatter", config=NOBAR)
        meaning(f"One dot per college, {len(df):,} in all. Above the dotted line a college graduated more first gen students than expected, below it fewer. The open circle is {row.instnm}.")

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    # Row 3 (7/5): spending bars beside the compact predictor list
    L, R = st.columns([7, 5])
    with L:
        section(f"Top 10% schools spend {pf['Instruction']['median_ratio']:.1f} times as much on teaching and {pf['Academic support']['median_ratio']:.1f} times as much on academic support",
                f"median $ per student per year · n = {s7['n_top']} vs {s7['n_bottom']}")
        st.plotly_chart(spend_bar(df[df.group == "top 10%"], df[df.group == "bottom 10%"], 380), use_container_width=True, key="ov_spend", config=NOBAR)
        meaning(f"Schools that beat expectations spend {pf['Instruction']['median_ratio']:.1f} times as much per student on teaching and {pf['Academic support']['median_ratio']:.1f} times as much on academic support as schools that fall short, {pf['Student services']['median_ratio']:.2f} times on student services and {pf['Institutional support']['median_ratio']:.2f} times on administration. With the budget size held fixed, one standard deviation more academic support share is associated with {lm['pp_per_sd_acad_share']:+.1f} points, and doubling the budget with {pp_double:+.1f}. Set against a top 10% bar of +{s6['top_decile_cut_pp']:.0f}, both are small. That is the {lm['r2']*100:.0f}%.")
    with R:
        terms = [k for k in PLAIN if k in s5["coef_A"]]
        scale = {k: (np.log(2) if k == "log_ugds" else 1.0) * 100 for k in terms}     # log enrollment is rescaled to "per doubling" (x ln 2); shares and yes/no terms stay 0 to 1
        co = pd.DataFrame({"term": [PLAIN[k] for k in terms], "coef": [s5["coef_A"][k] * scale[k] for k in terms], "se": [s5["se_A"][k] * scale[k] for k in terms]})
        big_k = max(terms, key=lambda k: abs(s5["coef_A"][k] * scale[k])); big_v = s5["coef_A"][big_k] * scale[big_k]
        section(f"{PLAIN[big_k]} predicts the most: {big_v:+.0f} points going from none to all", f"n = {s5['n']:,} · shares none to all · types yes vs no · size per doubling")
        fig = go.Figure(go.Bar(x=co.coef, y=co.term, orientation="h", marker_color=GRAPHITE, marker_line_width=0,
                               error_x=dict(type="data", array=1.96 * co.se, color=INK2, thickness=1), hovertemplate="%{y}: %{x:+.1f} points (95% interval shown)<extra></extra>"))
        for t, v, e in zip(co.term, co.coef, co.se):                       # value labels sit just outside the 95% interval so they never cross the bar or its whisker
            note(fig, v + np.sign(v) * (1.96 * e + 0.8), t, f"{v:+.0f}", INK, xanchor="left" if v > 0 else "right", yanchor="middle")
        pad = (co.coef.abs() + 1.96 * co.se).max() * 1.35
        fig.update_layout(yaxis=dict(autorange="reversed"), bargap=0.45, xaxis=dict(range=[-pad, pad], title="Change in expected<br>first gen graduation (points)"))
        fig = chart(fig, 380, legend=False, ygrid=False)
        fig.update_xaxes(zeroline=True, zerolinecolor=INK, zerolinewidth=1, automargin=True, title_standoff=6)
        st.plotly_chart(fig, use_container_width=True, key="ov_coef", config=NOBAR)
        meaning(f"A school where every student is on a Pell Grant is expected to graduate about {abs(s5['coef_A']['pctpell'])*100:.0f} points fewer first gen students than one where none are. Expected rates come from slopes like these, fitted with separate slopes for public and private schools.")

    st.markdown('<div class="rule-strong"></div>', unsafe_allow_html=True)
    section(f"{row.instnm}", f"full detail for the selected school")
    school_block(row)

# ------------------------------------------------------------------ All schools
with tab_rank:
    section(f"All {len(df):,} colleges, ranked by points above expected", "filters apply to the table and the download")
    f1, f2, f3, f4, f5, f6 = st.columns([2, 2, 2, 3, 2, 2])
    states = f1.multiselect("State", sorted(df["stabbr"].unique()))
    ctrl = f2.multiselect("Public or private", ["Public", "Private nonprofit"], format_func=lambda v: TYPE[v])
    carn = f3.multiselect("Kind of school", sorted(df["carnegie_group"].unique()), format_func=lambda v: KIND[v])
    min_ugds = f4.number_input("At least this many undergrads (2017)", 0, int(df["ugds"].max()), 0, step=500)
    pell_lo = f5.number_input("On Pell Grants, at least (%)", 0, 100, 0, step=5)
    pell_hi = f6.number_input("On Pell Grants, at most (%)", 0, 100, 100, step=5)
    pell_rng = (pell_lo / 100, pell_hi / 100)
    d = df.copy()
    if states: d = d[d["stabbr"].isin(states)]
    if ctrl: d = d[d["control_label"].isin(ctrl)]
    if carn: d = d[d["carnegie_group"].isin(carn)]
    d = d[(d["ugds"] >= min_ugds) & (d["pctpell"].between(*pell_rng))].sort_values("residual_eb", ascending=False)
    d = d.merge(boot[["unitid", "p_top_decile", "boot_rank_p2_5", "boot_rank_p97_5"]], on="unitid", how="left")
    d["rank_range"] = d.apply(rank_range, axis=1)
    mono(f"{len(d):,} colleges match · rank is among all {len(df):,} · points above expected are shrunk toward zero for small cohorts, so a lucky year at a small school counts for less")
    show = d[["rank", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "firstgen_yr6_n", "firstgen_comp_orig_yr6_rt", "predicted", "residual_eb_pct_pts", "residual_pct_pts", "p_top_decile", "rank_range", "exp_core_per_fte"]].assign(control_label=lambda x: x.control_label.map(TYPE), carnegie_group=lambda x: x.carnegie_group.map(KIND)).rename(columns={
        "rank": "Rank", "instnm": "School", "stabbr": "State", "control_label": "Type", "carnegie_group": "Kind", "ugds": "Undergrads (2017)", "pctpell": "On Pell", "firstgen_yr6_n": "First gen students", "firstgen_comp_orig_yr6_rt": "Actually graduated",
        "predicted": "Expected", "residual_eb_pct_pts": "Points above expected", "residual_pct_pts": "Before small school adjustment", "p_top_decile": "Stays in top 10% (share of re runs)", "rank_range": "Likely rank on re runs", "exp_core_per_fte": "Core spending per student per year (2018 to 2023 avg)"})
    st.dataframe(show.style.format({"Rank": "{:.0f}", "On Pell": "{:.0%}", "Actually graduated": "{:.0%}", "Expected": "{:.0%}", "Points above expected": "{:+.0f}", "Before small school adjustment": "{:+.0f}", "Stays in top 10% (share of re runs)": "{:.0%}",
                                   "Core spending per student per year (2018 to 2023 avg)": "${:,.0f}", "Undergrads (2017)": "{:,.0f}", "First gen students": "{:,.0f}"}), use_container_width=True, height=560, hide_index=True)
    st.download_button("Download this list (CSV)", show.round({"Points above expected": 1, "Before small school adjustment": 1}).to_csv(index=False).encode(), "colleges_ranked.csv", "text/csv")
    meaning(f"A college at {s6['top_decile_cut_pp']:+.0f} graduates first gen students {s6['top_decile_cut_pp']:.0f} points more often than schools with the same kind of students usually do. 'Stays in top 10%' is how often it keeps that place across {bs['B']:,} re runs that redraw both the set of schools and each school's own graduation count. Top 10% schools keep their place {bs['mean_p_top_among_point_top']:.0%} of the time on average, and a typical top 10% school's likely rank range spans {bs['median_rank_ci_width_top_decile']:.0f} positions.")
    with st.expander(f"{len(sf)} special cases, scored but not ranked"):
        st.write(f"Four groups the comparison does not fit. {s5['n_special_focus']} colleges built around one program (nursing, faith, arts). {s5['n_nontraditional']} campuses where more than half of students are aged 25 or older or fully online. "
                 f"{s5['n_anomaly']} schools whose reported graduation numbers cannot be right (San Jose State's {res['step4']['anomalies'][0]['firstgen_rate']:.1%} against a {res['step4']['anomalies'][0]['ipeds_grad_rate_c150_4']:.0%} overall graduation rate). "
                 f"{s5['n_shared_opeid']} campuses whose first gen graduation rate is pooled with other campuses under one OPEID, because the Scorecard reports completion per OPEID rather than per campus. A campus stays in the ranking only if it holds at least {res['step4']['thresholds']['opeid_share_cut']:.0%} of its group's undergraduates. Shown so nothing is hidden.")
        st.dataframe(sf.sort_values(["excluded_reason", "residual"], ascending=[True, False])[["excluded_reason", "instnm", "stabbr", "control_label", "ugds", "ug25abv", "pct_distance", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts"]].assign(control_label=lambda x: x.control_label.map(TYPE)).rename(columns={
            "excluded_reason": "Why set aside", "instnm": "School", "stabbr": "State", "control_label": "Type", "ugds": "Undergrads", "ug25abv": "Aged 25+", "pct_distance": "Fully online", "pctpell": "On Pell", "firstgen_comp_orig_yr6_rt": "Actually graduated", "predicted": "Expected", "residual_pct_pts": "Points above expected (before small school adjustment)"})
                     .style.format({"On Pell": "{:.0%}", "Aged 25+": "{:.0%}", "Fully online": "{:.0%}", "Actually graduated": "{:.0%}", "Expected": "{:.0%}", "Points above expected (before small school adjustment)": "{:+.0f}", "Undergrads": "{:,.0f}"}), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ Where the money goes
with tab_spend:
    scopes = {"All schools": "main", "All schools, simpler model": "pooled", "Public colleges only": "Public", "Private colleges only": "Private nonprofit", "Research universities": "Doctoral", "Master's universities": "Master's", "Bachelor's colleges": "Baccalaureate"}
    scope = scopes[st.radio("Compare within", list(scopes), horizontal=True, label_visibility="collapsed")]
    if scope == "main":
        top, bot = df[df.group == "top 10%"], df[df.group == "bottom 10%"]; tab = pf; scope_note = "The top and bottom 10% from the main ranking, the same one shown on the other tabs."
    elif scope == "pooled":
        dp = df.assign(resid_pooled_eb=shrink(df["residual_pooled"], df["predicted_pooled"], df["firstgen_yr6_n"]))
        top, bot = decile_groups(dp, "resid_pooled_eb"); tab = None
        scope_note = "A simpler version of the model that treats public and private schools the same way. Shown to check that the answer does not depend on that choice."
    elif scope in ("Public", "Private nonprofit"):
        dd = df[df.control_label == scope]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = None   # chart and table come from these same two groups
        scope_note = f"Main ranking groups restricted to {TYPE[scope].lower()} schools (top {len(top)}, bottom {len(bot)}). The chart and the table use the same two groups."
    else:
        dd = df[df.carnegie_group == scope]; top, bot = dd[dd.group == "top 10%"], dd[dd.group == "bottom 10%"]; tab = s7["within_carnegie"][scope]["per_fte"]
        scope_note = f"Main ranking groups restricted to {KIND[scope].lower()}s (top {len(top)}, bottom {len(bot)})."
    mono(scope_note)
    rename = {"Instruction": "Teaching", "Academic support": "Academic support", "Student services": "Student services", "Institutional support": "Administration", "Core (4 categories)": "All four together"}
    t = compare_table(top, bot) if tab is None else pd.DataFrame([{"Spending category": rename[k], "Top 10%": v["top10_median_$"], "Bottom 10%": v["bottom10_median_$"], "Top ÷ bottom": v["median_ratio"], "p-value": v["mann_whitney_p"]} for k, v in tab.items() if k in rename])
    ti = t.set_index("Spending category")
    section(f"Top 10% schools spend {ti.loc['Teaching', 'Top ÷ bottom']:.1f} times as much on teaching and {ti.loc['Academic support', 'Top ÷ bottom']:.1f} times as much on academic support",
            f"median $ per student per year, 2018 to 2023 average · n = {len(top)} vs {len(bot)}")
    L, R = st.columns([7, 5])
    L.plotly_chart(spend_bar(top, bot, 400), use_container_width=True, key="spend_tab_main", config=NOBAR)
    col_top, col_bot = f"Top 10% (n={len(top)})", f"Bottom 10% (n={len(bot)})"
    R.dataframe(t.rename(columns={"Spending category": "Category", "Top 10%": col_top, "Bottom 10%": col_bot, "Top ÷ bottom": "Top ÷ bottom", "p-value": "p"}).style.format({col_top: "${:,.0f}", col_bot: "${:,.0f}", "Top ÷ bottom": "{:.1f}×", "p": fmt_p}), hide_index=True, use_container_width=True)
    R.caption("p value: the chance of seeing a gap this big if there were really no difference. Below 0.05 is the usual bar.")
    meaning(f"In this group, schools that beat expectations spend {ti.loc['Teaching', 'Top ÷ bottom']:.2f} times as much per student on teaching and {ti.loc['Academic support', 'Top ÷ bottom']:.2f} times as much on academic support as schools that fall short, {ti.loc['Student services', 'Top ÷ bottom']:.2f} times on student services and {ti.loc['Administration', 'Top ÷ bottom']:.2f} times on administration.")
    st.markdown(f"Among public colleges, the ones that beat expectations spend more on everything: teaching {pub['Instruction']['median_ratio']:.2f} times as much as the publics that fall short, academic support {pub['Academic support']['median_ratio']:.2f} times, student services {pub['Student services']['median_ratio']:.2f} times. "
                f"Among private colleges the gap is teaching ({prv['Instruction']['median_ratio']:.2f} times) and academic support ({prv['Academic support']['median_ratio']:.2f} times), with student services about equal ({prv['Student services']['median_ratio']:.2f} times). "
                f"The teaching and academic support gaps hold in every group I checked, including after a Benjamini and Hochberg correction for running {s7['bh']['n_tests']} comparisons. The student services gap does not.")
    with st.expander("Does the answer change if I use different years, or adjust for inflation?"):
        cell = lambda v: f"{v['median_ratio']:.1f}× · p {fmt_p(v['mann_whitney_p'])}"
        var = pd.DataFrame({"2018 to 2023, the main figure": {rename[k]: cell(v) for k, v in pf.items() if k in rename}, "2018 and 2019 only (first two years)": {rename[k]: cell(v) for k, v in s7["per_fte_fy1819"].items() if k in rename},
                            "2018 to 2023 in 2023 dollars": {rename[k]: cell(v) for k, v in s7["per_fte_real"].items() if k in rename}, "2023 only (after students left)": {rename[k]: cell(v) for k, v in s7["per_fte_fy23_only"].items() if k in rename}})
        st.dataframe(var, use_container_width=True)
        st.caption(f"Top 10% median as a multiple of the bottom 10% median, with the Mann Whitney p · n = {s7['n_top']} vs {s7['n_bottom']} in every column.")
        meaning("No. The teaching and academic support gaps are about the same size whichever years are used and whether or not dollars are adjusted for inflation.")

# ------------------------------------------------------------------ Methods (all technical detail lives here)
with tab_method:
    section("Methods & limitations", "the technical version")
    with st.container(key="methods"):   # .st-key-methods caps the prose at 72ch (CSS block)
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
