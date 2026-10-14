"""
R3: number of input features versus reported discrimination.

Reproduces every statistic in appendix R3 from feature_counts.csv (stage-labelled
final-model counts) and the newest locked master (model_auc_final, total_sample_size).
Until 2026-09-04 these figures had no producing script (built in-session 2026-07-28).

Set: studies with stage == final_after_selection AND a reported discrimination estimate.
Stats: strata medians (<10, 10-29, >=30 features), Spearman rho of count vs AUROC,
Spearman rho of count vs log10(cohort size), partial Spearman (count vs AUROC | log10 n),
stratum cohort-size medians.

OUTPUT analysis/outputs/r3_feature_count_stats.json
"""
import glob, json, os
import numpy as np, pandas as pd
from scipy import stats

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FC = os.path.join(REPO, "data", "feature_counts.csv")
MASTER = sorted(glob.glob(os.path.join(REPO, "data", "extraction_master_LOCKED*.xlsx")))[-1]
OUT = os.path.join(REPO, "analysis", "outputs", "r3_feature_count_stats.json")


def partial_spearman(x, y, z):
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    def resid(a, b):
        b1 = np.c_[np.ones_like(b), b]
        return a - b1 @ np.linalg.lstsq(b1, a, rcond=None)[0]
    r, p = stats.pearsonr(resid(rx, rz), resid(ry, rz))
    return float(r), float(p)


def main():
    fc = pd.read_csv(FC)
    m = pd.read_excel(MASTER, sheet_name="Sheet1")
    m["num"] = pd.to_numeric(m["num"], errors="coerce")
    d = fc.merge(m[["num", "model_auc_final", "total_sample_size"]], on="num", how="left")
    d["n_features"] = pd.to_numeric(d["n_features"], errors="coerce")
    d["auc"] = pd.to_numeric(d["model_auc_final"], errors="coerce")
    d["n"] = pd.to_numeric(d["total_sample_size"], errors="coerce")
    stage = d["stage"].astype(str).str.strip()
    counts = {"not_stated": int((stage == "not_stated").sum()), "reported": int(d["n_features"].notna().sum()),
              "final_after_selection": int((stage == "final_after_selection").sum()),
              "candidate_pool": int((stage == "candidate_pool").sum()),
              "derived_imaging_features": int((stage == "derived_imaging_features").sum())}
    a = d[(stage == "final_after_selection") & d["auc"].notna() & d["n_features"].notna()].copy()
    a["stratum"] = pd.cut(a["n_features"], [0, 9.5, 29.5, np.inf], labels=["<10", "10-29", ">=30"])
    strata = {str(k): {"n": int(len(g)), "median_auc": round(float(g["auc"].median()), 3),
                       "median_cohort": int(round(g["n"].median()))} for k, g in a.groupby("stratum", observed=True)}
    rho, p = stats.spearmanr(a["n_features"], a["auc"])
    rho_n, p_n = stats.spearmanr(a["n_features"], np.log10(a["n"]))
    pr, pp = partial_spearman(a["n_features"].values, a["auc"].values, np.log10(a["n"].values))
    other = a[a["stratum"] != ">=30"]
    out = {"master": os.path.basename(MASTER), "stage_counts": counts, "n_analysed": int(len(a)),
           "features_min": int(a["n_features"].min()), "features_max": int(a["n_features"].max()),
           "features_median": float(a["n_features"].median()), "strata": strata,
           "rho_count_auc": round(float(rho), 3), "p_count_auc": round(float(p), 3),
           "rho_count_logn": round(float(rho_n), 3), "p_count_logn": round(float(p_n), 3),
           "partial_rho": round(pr, 3), "partial_p": round(pp, 3),
           "median_cohort_ge30": int(round(a.loc[a["stratum"] == ">=30", "n"].median())),
           "median_cohort_lt30": int(round(other["n"].median()))}
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"  n={out['n_analysed']} features {out['features_min']}-{out['features_max']} median {out['features_median']}")
    print(f"  strata: {strata}")
    print(f"  rho(count,auc)={out['rho_count_auc']} p={out['p_count_auc']} | rho(count,log n)={out['rho_count_logn']} p={out['p_count_logn']}"
          f" | partial rho={out['partial_rho']} p={out['partial_p']} | cohort >=30: {out['median_cohort_ge30']} vs {out['median_cohort_lt30']}")


if __name__ == "__main__":
    main()
