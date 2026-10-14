"""
R7: studies contributing to a pooled estimate versus the remainder, recomputed across all 78
studies from the newest locked master. Until 2026-09-04 the R7 table had no producing code.

Pooled = pooling_status POOL AND organ/outcome in one of the three pooled subgroups (18).
OUTPUT analysis/outputs/pooled_vs_not_comparison.json
"""
import glob, json, os
import pandas as pd
from scipy import stats

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MASTER = sorted(glob.glob(os.path.join(REPO, "data", "extraction_master_LOCKED*.xlsx")))[-1]
OUT = os.path.join(REPO, "analysis", "outputs", "pooled_vs_not_comparison.json")
SG = {"Heart / 1-year survival", "Lung / 1-year survival", "Heart / Acute Rejection"}


def main():
    m = pd.read_excel(MASTER, sheet_name="Sheet1")
    S = lambda c: m[c].astype(str).str.strip()
    num = lambda c: pd.to_numeric(m[c], errors="coerce")
    sub = S("organ_focus") + " / " + S("target_outcome")
    pool_any = S("pooling_status").eq("POOL")
    in3 = pool_any & sub.isin(SG)
    auc, n = num("model_auc_final"), num("total_sample_size")
    ext = S("validation_method").str.contains("xternal", case=False)
    A, B = in3, ~in3
    out = {"master": os.path.basename(MASTER), "n_pooled": int(A.sum()), "n_not": int(B.sum()),
           "n_with_metric": int(auc.notna().sum()), "n_pool_status_any": int(pool_any.sum()),
           "n_pool_status_outside_3": int((pool_any & ~in3).sum()),
           "median_n_pooled": int(round(n[A].median())), "median_n_not": int(round(n[B].median())),
           "ext_pooled": int(ext[A].sum()), "ext_pooled_pct": round(100 * ext[A].mean()),
           "ext_not": int(ext[B].sum()), "ext_not_pct": round(100 * ext[B].mean()),
           "median_auc_pooled": round(float(auc[A].median()), 3), "median_auc_not": round(float(auc[B].median()), 3),
           "auc_reported_pooled": int(auc[A].notna().sum()), "auc_reported_not": int(auc[B].notna().sum()),
           "auc_reported_not_pct": round(100 * auc[B].notna().mean()),
           "p_mw_n": round(float(stats.mannwhitneyu(n[A].dropna(), n[B].dropna()).pvalue), 3),
           "p_mw_auc": round(float(stats.mannwhitneyu(auc[A].dropna(), auc[B].dropna()).pvalue), 3)}
    json.dump(out, open(OUT, "w"), indent=1)
    print("  " + json.dumps({k: v for k, v in out.items() if k != "master"}))


if __name__ == "__main__":
    main()
