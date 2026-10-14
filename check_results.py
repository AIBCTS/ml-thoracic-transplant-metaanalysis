#!/usr/bin/env python3
"""Compare the pipeline outputs with the values reported in the manuscript (expected_results.json)."""
import json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
O = ROOT / "analysis" / "outputs"
E = json.loads((ROOT / "expected_results.json").read_text())
fails = []
def eq(label, got, exp):
    # the R outputs are stored to four decimals; a printed three-decimal value matches when it is
    # within half a unit of the third decimal of the stored value (avoids double rounding: 0.96648 -> 0.9665 -> 0.967)
    g, x = (got if isinstance(got, list) else [got]), (exp if isinstance(exp, list) else [exp])
    try: ok = all(abs(float(a) - float(b)) <= 0.00055 if "." in str(b) else str(a) == str(b) for a, b in zip(g, x))
    except ValueError: ok = str(got) == str(exp)
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got} (manuscript {exp})")
    if not ok: fails.append(label)
f3 = lambda x: f"{x:.4f}"

mr = pd.read_csv(O / "metaanalysis_results.csv").set_index("subgroup")
for sg, e in E["pooled"].items():
    r = mr.loc[sg]
    eq(f"{sg} k", int(r.k), e["k"]); eq(f"{sg} AUROC", f3(r.pooled_auroc), e["auroc"])
    eq(f"{sg} 95% CI", [f3(r.ci_lo), f3(r.ci_hi)], e["ci"]); eq(f"{sg} 95% PI", [f3(r.pi_lo), f3(r.pi_hi)], e["pi"])
    if "I2" in e: eq(f"{sg} I2", round(r.I2), e["I2"])
rs = pd.read_csv(O / "metaanalysis_sensitivity_registry.csv").set_index("subgroup").loc["Heart / 1-year survival"]
eq("Heart 1-year, one estimate per registry, 95% CI", [f3(rs.ci_lo), f3(rs.ci_hi)], E["registry_sensitivity_heart_ci"])
ml = pd.read_csv(O / "ml_vs_linear_stats.csv").iloc[0]; e = E["ml_vs_linear_tier1"]
eq("ML vs linear pairs", int(ml.n), e["n"]); eq("ML higher", int(ml.higher), e["higher"])
eq("median difference", f3(ml.median_delta), e["median_delta"]); eq("Wilcoxon p", f"{ml.p:.4f}", e["p"]) if False else eq("Wilcoxon p", f"{ml.p:.4f}"[:6], e["p"])
d = json.loads((O / "determinants_stats.json").read_text()); e = E["determinants"]
eq("studies plotted", d["n_plotted"], e["n"]); eq("Spearman rho (cohort size)", f"{d['rho']:.3f}", e["rho"]); eq("Mann-Whitney p (input type)", f"{d['p_U']:.4f}", e["p_U"])
eq("image/pathology/waveform studies", d["per_n"], e["n_image_pathology_waveform"]); eq("tabular studies", d["tab_n"], e["n_tabular"])
lb = pd.read_csv(O / "metaanalysis_sensitivity_lung_binary.csv").iloc[0]; e = E["lung_binary_only"]
eq("Lung 1-year, binary AUROC only, k", int(lb.k), e["k"]); eq("Lung 1-year, binary AUROC only", f3(lb.pooled_auroc), e["pooled"])
eq("Lung 1-year, binary AUROC only, 95% CI", [f3(lb.ci_lo), f3(lb.ci_hi)], e["ci"])
org = pd.read_csv(O / "pilot" / "table_organ_focus.csv").set_index("Organ focus")["n"]
for k in ["Heart", "Lung", "Other"]: eq(f"Table 1 {k}", int(org[k]), E["table1"][k])
val = pd.read_csv(O / "pilot" / "table_validation_method.csv").set_index("Validation method")["n"]
eq("Table 1 external validation", int(val[val.index.str.startswith("External")].sum()), E["table1"]["external_validation"])
oc = pd.read_csv(O / "pilot" / "table_target_outcome.csv").set_index("Target outcome")["n"]
eq("Table 1 1-year survival", int(oc["1-year survival"]), E["table1"]["one_year_survival"])
print("\nALL MATCH" if not fails else f"\n{len(fails)} MISMATCH(ES)"); sys.exit(1 if fails else 0)
