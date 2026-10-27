"""Independent recompute of the three headline numbers. Imports NO project code.
Reads only data/clean/analysis.parquet (the cleaned file, before any model) and prints:
  (1) share of the over-performance residual explained by spending level and mix (R^2),
  (2) the top-decile cut of the shrunken residual in points,
  (3) top-decile / bottom-decile median instruction spending per FTE.
Run from the project root:  python -I src/check_headlines.py data/clean/analysis.parquet
Compare the printed values with reports/results.json: step7.level_vs_mix.r2, step6.top_decile_cut_pp, step7.per_fte.Instruction.median_ratio.
"""
import sys, json, numpy as np, pandas as pd, statsmodels.formula.api as smf
d = pd.read_parquet(sys.argv[1]); d = d[d.in_main == 1].copy()
y = "firstgen_comp_orig_yr6_rt"
traits = ["pctpell", "adm_rate", "log_ugds", "pptug_ef", "first_gen", "ug25abv", "pct_distance", "hbcu_flag"]
carn = "C(carnegie_group, Treatment(reference=\"Master's\"))"
f = f"{y} ~ private + " + " + ".join(traits) + " + " + " + ".join(f"private:{t}" for t in traits) + f" + {carn}"
m = smf.ols(f, data=d).fit()
d["pred"] = m.fittedvalues; d["res"] = d[y] - d["pred"]
p = d.pred.clip(0.05, 0.95); s2 = p * (1 - p) / d.firstgen_yr6_n
t2 = max(d.res.var() - s2.mean(), 1e-6); d["res_eb"] = d.res * t2 / (t2 + s2)
dec = pd.qcut(d.res_eb, 10, labels=False); top, bot = d[dec == 9], d[dec == 0]
cut = top.res_eb.min() * 100
core = d[["exp_instruction_per_fte", "exp_academic_support_per_fte", "exp_student_services_per_fte", "exp_institutional_support_per_fte"]].sum(axis=1)
d["log_core"] = np.log(core); d["instr_share"] = d.exp_instruction_per_fte / core; d["acad_share"] = d.exp_academic_support_per_fte / core
lm = smf.ols(f"res_eb ~ log_core + instr_share + acad_share + private + {carn}", data=d).fit()
ratio = top.exp_instruction_per_fte.median() / bot.exp_instruction_per_fte.median()
out = {"n": len(d), "r2_model": round(m.rsquared, 4), "money_r2_pct": round(lm.rsquared * 100, 2), "top_decile_cut_pp": round(cut, 2), "top_decile_n": len(top),
       "instruction_ratio": round(ratio, 3), "acad_support_ratio": round(top.exp_academic_support_per_fte.median() / bot.exp_academic_support_per_fte.median(), 3),
       "pp_per_sd_acad_share": round(lm.params["acad_share"] * d.acad_share.std() * 100, 2), "pp_per_sd_instr_share": round(lm.params["instr_share"] * d.instr_share.std() * 100, 2), "pp_per_doubling": round(lm.params["log_core"] * np.log(2) * 100, 2)}
print(json.dumps(out, indent=1))
