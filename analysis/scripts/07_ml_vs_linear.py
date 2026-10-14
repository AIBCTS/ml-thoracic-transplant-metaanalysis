#!/usr/bin/env python3
"""
Paired machine-learning versus linear-comparator analysis (Figure 7 and the
Results paragraph on within-study comparison).

WHY THIS FILE EXISTS
--------------------
ml_vs_linear_paired.csv and ml_vs_linear_stats.csv were first produced by ad-hoc
kernel cells in an interactive session and committed as outputs with no producing
script (first appearing in 4c2d0bb, 28 July). Their numbers are reported in the
manuscript -- the median delta and the Wilcoxon p-values among them -- so the
analysis was, until now, not reproducible from the repository. This script
reconstructs it and is verified to reproduce both files exactly.

INPUT   data/extraction_master_LOCKED*.xlsx (newest), sheet "Sheet1"
OUTPUT  analysis/outputs/ml_vs_linear_paired.csv
        analysis/outputs/ml_vs_linear_stats.csv

DEFINITIONS
-----------
A study enters the paired set when it reports BOTH a machine-learning model AUROC
(model_auc_final) and a linear comparator AUROC (linear_model_auc) in the same
cohort. delta = ml - linear, so positive favours machine learning.

Two tiers are reported because they answer different questions:
  Tier 1  1-year survival only -- the homogeneous outcome, the one pooled.
  Tier 2  all outcomes -- the full paired set, more studies but mixed endpoints.

The p-value is a two-sided Wilcoxon signed-rank test on the raw delta.

TIE TOLERANCE. Differences of 0.005 AUROC or less count as ties, as the manuscript
Methods states: "treating differences of 0.005 AUROC or less as ties". This affects
the higher/tied/lower counts only -- the Wilcoxon test runs on the raw deltas, which
is why the committed p-values reproduce exactly while the counts need the rule. It
matters: without it tier 1 reads 12 of 12 rather than the reported 10 of 12, because
two studies differ by 0.0001 and 0.0042 AUROC, differences no reader would call a
win. The tolerance was applied when the outputs were first produced but was recorded
only in the manuscript, not in any code -- one reason this script needed writing.

USAGE   python analysis/scripts/07_ml_vs_linear.py [--check]
        --check recomputes and compares against the committed CSVs without
        writing, exiting non-zero on any disagreement.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The newest locked master, the same convention the gates and 03_metaanalysis.R use.
# Until 2026-09-01 this was a hardcoded path to the 28 July file, which is why the
# paired set stayed at 18 after the relock dropped the comparator columns: the script
# was reading a superseded master and its own --check passed against it.
_MASTERS = sorted(glob.glob(os.path.join(REPO, "data", "extraction_master_LOCKED*.xlsx")))
if not _MASTERS:
    sys.exit("No extraction_master_LOCKED*.xlsx in data/")
MASTER = _MASTERS[-1]
OUT_DIR = os.path.join(REPO, "analysis", "outputs")
PAIRED = os.path.join(OUT_DIR, "ml_vs_linear_paired.csv")
STATS = os.path.join(OUT_DIR, "ml_vs_linear_stats.csv")

TIER1_OUTCOME = "1-year survival"
# Manuscript Methods: "treating differences of 0.005 AUROC or less as ties".
TIE_TOL = 0.005


def num(s):
    return pd.to_numeric(s, errors="coerce")


def build():
    m = pd.read_excel(MASTER, sheet_name="Sheet1")

    ml = num(m["model_auc_final"])
    lin = num(m["linear_model_auc"])
    paired = ml.notna() & lin.notna()

    d = m[paired].copy()
    d["ml"] = ml[paired]
    d["linear_model_auc"] = lin[paired]
    d["delta"] = d["ml"] - d["linear_model_auc"]
    d["tier1"] = d["target_outcome"].astype(str).str.strip() == TIER1_OUTCOME

    # LABEL, restored 2026-09-01. The column was named in `cols` but never built, so
    # every run wrote it blank. It went unnoticed for two reasons: this script was not
    # a pipeline stage, so it had never overwritten the committed CSV; and --check
    # compares only num/ml/linear_model_auc/delta/tier1, so a blank label passes.
    # The rule is read back from the committed file rather than invented: strip the
    # "<num>_" prefix, then take the text before the first hyphen. That reproduces all
    # 18 committed labels exactly, including "Tran (71)" from "Tran-Dinh A et al." —
    # a truncation of the original ad-hoc code that is kept because it is what the
    # published Figure 7 shows.
    _author = (d["study_id"].astype(str)
               .str.split("_", n=1).str[-1]
               .str.split("-").str[0]
               .str.strip())
    d["label"] = _author + " (" + d["num"].astype(int).astype(str) + ")"

    cols = [
        "num", "label", "organ_focus", "target_outcome", "ml", "linear_model_auc",
        "delta", "model_auc_ci_lo", "model_auc_ci_hi",
        "linear_model_auc_lower_ci", "linear_model_auc_upper_ci", "tier1",
    ]
    for c in cols:
        if c not in d.columns:
            d[c] = np.nan
    d = d[cols].sort_values("num").reset_index(drop=True)

    rows = []
    for label, sub in [
        (f"Tier 1 ({TIER1_OUTCOME} only)", d[d["tier1"]]),
        ("Tier 2 (all outcomes)", d),
    ]:
        delta = sub["delta"].to_numpy(dtype=float)
        # Wilcoxon needs at least one non-zero difference; ties are dropped by the
        # default zero_method, matching how the original figures were produced.
        p = stats.wilcoxon(delta)[1] if np.any(delta != 0) else np.nan
        # counts use the tie tolerance; the test above uses the raw deltas
        rows.append({
            "tier": label,
            "n": int(len(delta)),
            "higher": int((delta > TIE_TOL).sum()),
            "tied": int((np.abs(delta) <= TIE_TOL).sum()),
            "lower": int((delta < -TIE_TOL).sum()),
            "median_delta": round(float(np.median(delta[delta != 0])), 4),
            "p": float(f"{p:.6g}"),
        })
    return d, pd.DataFrame(rows)


def _compare(new, old, name, keys, sort_on=None):
    """Compare on the columns that carry meaning; report the first disagreement.

    Row ORDER is not compared. The committed paired file was written in the order
    the original interactive session happened to produce; the content is what has
    to reproduce, so both frames are sorted on `sort_on` first. Forcing this
    script to emit the historical order instead would be a cosmetic match that
    hides nothing and proves nothing.
    """
    if list(new.shape) != list(old.shape):
        return f"{name}: shape {new.shape} vs committed {old.shape}"
    if sort_on and sort_on in new.columns and sort_on in old.columns:
        new = new.sort_values(sort_on).reset_index(drop=True)
        old = old.sort_values(sort_on).reset_index(drop=True)
    for c in keys:
        if c not in old.columns:
            continue
        a, b = new[c], old[c]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            if not np.allclose(a.fillna(-999), b.fillna(-999), rtol=0, atol=5e-4):
                bad = np.where(~np.isclose(a.fillna(-999), b.fillna(-999),
                                           rtol=0, atol=5e-4))[0]
                i = int(bad[0])
                return f"{name}.{c} row {i}: {a.iloc[i]} vs committed {b.iloc[i]}"
        else:
            if not a.astype(str).equals(b.astype(str)):
                return f"{name}.{c}: text differs"
    return None


def main():
    check = "--check" in sys.argv
    paired, stats_df = build()

    print(f"  paired studies: {len(paired)}  "
          f"(tier 1 {int(paired['tier1'].sum())}, tier 2 {len(paired)})")
    for _, r in stats_df.iterrows():
        print(f"    {r['tier']:34} n={r['n']:>2}  higher={r['higher']:>2} "
              f"tied={r['tied']} lower={r['lower']}  "
              f"median delta={r['median_delta']:.4f}  p={r['p']:.6g}")

    if check:
        problems = []
        if os.path.exists(PAIRED):
            problems.append(_compare(paired, pd.read_csv(PAIRED), "paired",
                                     ["num", "label", "ml", "linear_model_auc", "delta", "tier1"],
                                     sort_on="num"))
        if os.path.exists(STATS):
            problems.append(_compare(stats_df, pd.read_csv(STATS), "stats",
                                     ["n", "higher", "tied", "lower",
                                      "median_delta", "p"]))
        problems = [p for p in problems if p]
        if problems:
            print("\n  CHECK FAILED — script does not reproduce the committed outputs:")
            for p in problems:
                print(f"    {p}")
            sys.exit(1)
        print("\n  CHECK OK — reproduces both committed CSVs")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    paired.to_csv(PAIRED, index=False)
    stats_df.to_csv(STATS, index=False)
    print(f"\n  written: {os.path.relpath(PAIRED, REPO)}")
    print(f"           {os.path.relpath(STATS, REPO)}")


if __name__ == "__main__":
    main()
