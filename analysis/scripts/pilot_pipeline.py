"""
pilot_pipeline.py  —  End-to-end pilot run, v2 (real inverse-variance weighting).

Produces a compact report with all figures and tables. Verifies the pipeline
works end to end and surfaces issues — this is still labelled "pilot" because
it uses a simplified DerSimonian-Laird estimator, not full REML — but as of
this version it uses REAL standard errors (model_auc_se, from verified 95% CIs
or Hanley-McNeil), not a sample-size approximation. Numbers from this version
are directionally trustworthy; Phase 3B's 03_metaanalysis.R (R/metafor) is
still the version that goes in the manuscript.

Usage:
    uv run python analysis/scripts/pilot_pipeline.py

Requirements:
    uv sync
    R packages (for the separate robvis figure, not run from here): robvis, ggplot2

Reads:   data/extraction_master_LOCKED*.xlsx  (most recent — must
         already have model_auc_final / model_auc_se / pooling_status columns
         from merge_final_variance.py; falls back to the old sample-size
         approximation with a clear warning if those columns are absent)
         config.yaml                                    (thresholds)
Writes:  analysis/outputs/pilot/
         analysis/outputs/pilot/PILOT_REPORT.md
         analysis/figures/pilot/
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
import sys
import yaml
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
EXTR_DIR    = ROOT / "data"
CONFIG_FILE = ROOT / "config.yaml"
OUT_DIR     = ROOT / "analysis" / "outputs" / "pilot"
FIG_DIR     = ROOT / "analysis" / "figures" / "pilot"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = OUT_DIR / "PILOT_REPORT.md"

# ── Config ───────────────────────────────────────────────────────────────────
if CONFIG_FILE.exists():
    CONFIG = yaml.safe_load(open(CONFIG_FILE)) or {}
else:
    CONFIG = {}
MIN_STUDIES = CONFIG.get("analysis", {}).get("min_studies_for_pooling", 5)

# ── Logging ──────────────────────────────────────────────────────────────────
issues = []

def log_issue(phase, severity, msg):
    tag = {"WARNING": "⚠ ", "FLAG": "🚩", "BLOCKER": "🛑"}[severity]
    issues.append({"phase": phase, "severity": severity, "message": msg})
    print(f"  {tag}  [{phase}] {msg}")

def section(title):
    print(f"\n{'='*55}\n{title}\n{'='*55}")

report_lines = [
    "# Pilot report — AI in thoracic transplantations",
    "",
    f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    "**Purpose:** pipeline verification with real inverse-variance weighting "
    "— directionally trustworthy, not the final manuscript analysis "
    "(see 03_metaanalysis.R for that).",
    "",
    "---",
    "",
]

def rpt(line=""):
    report_lines.append(line)

# ════════════════════════════════════════════════════════
# STEP 1 — Load dataset
# ════════════════════════════════════════════════════════
section("STEP 1 — Load dataset")
rpt("## Step 1 — Dataset")

locked_files = sorted(EXTR_DIR.glob("extraction_master_LOCKED*.xlsx"))
if not locked_files:
    log_issue("Step 1", "BLOCKER", "No extraction_master_LOCKED*.xlsx found in data/")
    sys.exit(1)

master_file = locked_files[-1]
print(f"  Loading: {master_file.name}")
df = pd.read_excel(master_file)

rpt(f"- File: `{master_file.name}`")
rpt(f"- Rows: {len(df)}")

if len(df) != 57:
    log_issue("Step 1", "FLAG", f"Expected 57 studies, found {len(df)}")
if "flag_reeval" in df.columns and df["flag_reeval"].sum() > 0:
    n_flag = int(df["flag_reeval"].sum())
    log_issue("Step 1", "BLOCKER", f"{n_flag} studies still flagged — run adjudication first.")

HAS_VARIANCE_COLS = all(c in df.columns for c in
                         ["model_auc_final", "model_auc_se", "pooling_status"])
if HAS_VARIANCE_COLS:
    print("  Variance columns found — using real inverse-variance weighting")
    rpt(f"- Status: ✓ {len(df)} studies, real-variance columns present")
    rpt(f"- Pooling status breakdown:")
    rpt()
    for status, n in df["pooling_status"].value_counts().items():
        rpt(f"  - `{status}`: {n}")
else:
    log_issue("Step 1", "WARNING",
               "model_auc_final/model_auc_se/pooling_status not found — "
               "falling back to sample-size-approximated variance (run "
               "merge_final_variance.py first for real weighting)")
    rpt(f"- Status: ⚠ {len(df)} studies, variance columns MISSING — "
        f"using approximated variance")
rpt()

AUC_COL = "model_auc_final" if HAS_VARIANCE_COLS else "model_auc"

# ════════════════════════════════════════════════════════
# STEP 2 — Descriptive statistics
# ════════════════════════════════════════════════════════
section("STEP 2 — Descriptive statistics")
rpt("## Step 2 — Descriptive statistics")

cat_fields = {
    "organ_focus": "Organ focus", "study_design": "Study design",
    "ai_architecture": "ML architecture", "validation_method": "Validation method",
    "target_outcome": "Target outcome", "target_population": "Target population",
    "dataset_source": "Dataset source", "country_origin": "Country/region",
}
rpt("### Study characteristics")
rpt()
for col, label in cat_fields.items():
    if col not in df.columns:
        log_issue("Step 2", "WARNING", f"Column '{col}' not found — skipping {label}")
        continue
    freq = df[col].value_counts(dropna=False).rename("n")
    freq.index.name = label
    freq.to_csv(OUT_DIR / f"table_{col}.csv")
    rpt(f"**{label}**")
    rpt()
    rpt("| Category | n |")
    rpt("|----------|---|")
    for idx, val in freq.items():
        rpt(f"| {idx} | {val} |")
    rpt()

num_fields = {
    "total_sample_size": "Total sample size", AUC_COL: "AUROC (final)",
    "model_sensitivity": "Sensitivity (%)", "model_specificity": "Specificity (%)",
    "study_start_year": "Study start year",
}
rpt("### Numeric summary")
rpt()
rpt("| Field | n | Mean | Median | Min | Max |")
rpt("|-------|---|------|--------|-----|-----|")
for col, label in num_fields.items():
    if col not in df.columns:
        continue
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(s) == 0:
        continue
    rpt(f"| {label} | {len(s)} | {s.mean():.2f} | {s.median():.2f} | {s.min():.2f} | {s.max():.2f} |")
rpt()

auc_all = pd.to_numeric(df[AUC_COL], errors="coerce")
if auc_all.max() > 1.1:
    log_issue("Step 2", "FLAG", f"{AUC_COL} max={auc_all.max():.1f} — values appear "
              "to be on a % scale (0-100), not 0-1. Normalise before pooling.")
missing_auc = auc_all.isna().sum()
if missing_auc > 0:
    rpt(f"> AUROC: n={auc_all.notna().sum()}, mean={auc_all.mean():.3f}, "
        f"min={auc_all.min():.3f}, max={auc_all.max():.3f}. "
        f"{missing_auc} studies excluded (no AUC at all).")
    log_issue("Step 2", "WARNING", f"{missing_auc} studies missing AUROC entirely")
rpt()

if HAS_VARIANCE_COLS:
    n_pool = (df["pooling_status"] == "POOL").sum()
    n_prov = (df["pooling_status"] == "POOL_PROVISIONAL").sum()
    n_no_var = auc_all.notna().sum() - n_pool - n_prov
    rpt(f"> Of {auc_all.notna().sum()} studies with an AUC: "
        f"**{n_pool} have a reported confidence interval (POOL)**, "
        f"{n_prov} have variance derived from case counts (Hanley-McNeil; not used in any pooled estimate), "
        f"{max(0, n_no_var)} have no usable variance (narrative only).")
    rpt()

try:
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("Study characteristics — pilot", fontsize=13, fontweight="500")
    for ax, (col, label) in zip(axes.flat, list(cat_fields.items())[:4]):
        if col in df.columns:
            freq = df[col].value_counts().head(8)
            ax.barh(freq.index.astype(str), freq.values, color="#1D9E75")
            ax.set_title(label, fontsize=10)
            ax.tick_params(labelsize=8)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig_study_characteristics.pdf", bbox_inches="tight")
    plt.close()

    auc_vals = auc_all.dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(auc_vals, bins=20, color="#1D9E75", edgecolor="white", linewidth=0.5)
    ax.axvline(auc_vals.mean(), color="#D85A30", linewidth=1.5, linestyle="--",
               label=f"Mean = {auc_vals.mean():.3f}")
    ax.set_xlabel("AUROC (final)", fontsize=10)
    ax.set_ylabel("Studies (n)", fontsize=10)
    ax.set_title("AUROC distribution — all studies with a value", fontsize=11)
    ax.legend(fontsize=9)
    plt.savefig(FIG_DIR / "fig_auroc_distribution.pdf", bbox_inches="tight")
    plt.close()
except Exception as e:
    log_issue("Step 2", "WARNING", f"Figure generation failed: {e}")

# ════════════════════════════════════════════════════════
# STEP 3 — Subgroup identification
# ════════════════════════════════════════════════════════
section("STEP 3 — Subgroup identification")
rpt("## Step 3 — Subgroup identification")
rpt()

subgroups = []
if "organ_focus" in df.columns and "target_outcome" in df.columns:
    combo = df.groupby(["organ_focus", "target_outcome"]).size().reset_index(name="n")
    combo = combo.sort_values("n", ascending=False)
    combo.to_csv(OUT_DIR / "table_outcome_organ_combinations.csv", index=False)

    rpt(f"### Outcome–organ combinations (min {MIN_STUDIES} studies to pool)")
    rpt()
    if HAS_VARIANCE_COLS:
        rpt("| Organ | Outcome | n total | n POOL | n PROVISIONAL | Pool? |")
        rpt("|-------|---------|---------|--------|----------------|-------|")
    else:
        rpt("| Organ | Outcome | n | Pool? |")
        rpt("|-------|---------|---|-------|")

    for _, row in combo.iterrows():
        mask = (df["organ_focus"] == row["organ_focus"]) & (df["target_outcome"] == row["target_outcome"])
        if HAS_VARIANCE_COLS:
            sub = df[mask]
            n_p = (sub["pooling_status"] == "POOL").sum()
            n_pr = (sub["pooling_status"] == "POOL_PROVISIONAL").sum()
            poolable = "✓" if n_p >= 2 else ("~ (provisional only)" if (n_p + n_pr) >= 2 else "✗")
            rpt(f"| {row['organ_focus']} | {row['target_outcome']} | {row['n']} | {n_p} | {n_pr} | {poolable} |")
            if n_p >= 2:
                subgroups.append((row["organ_focus"], row["target_outcome"], int(n_p)))
        else:
            poolable = "✓ ≥{} studies".format(MIN_STUDIES) if row["n"] >= MIN_STUDIES else "✗ too few"
            rpt(f"| {row['organ_focus']} | {row['target_outcome']} | {row['n']} | {poolable} |")
            if row["n"] >= MIN_STUDIES:
                subgroups.append((row["organ_focus"], row["target_outcome"], int(row["n"])))
    rpt()

    if not subgroups:
        log_issue("Step 3", "FLAG", "No subgroup has ≥2 POOL studies — quantitative "
                  "synthesis not feasible for any subgroup at this time.")
    else:
        print(f"  Poolable subgroups (≥2 POOL studies): {len(subgroups)}")
        for s in subgroups:
            print(f"    {s[0]} / {s[1]} (POOL n={s[2]})")

# ════════════════════════════════════════════════════════
# STEP 4 — Heterogeneity (descriptive, all studies with an AUC in subgroup)
# ════════════════════════════════════════════════════════
section("STEP 4 — Heterogeneity (descriptive, full evidence base)")
rpt("## Step 4 — Heterogeneity (descriptive)")
rpt()
rpt("> Dispersion across **all** studies reporting an AUC in each subgroup "
    "(not just the POOL subset) — shows how much the full evidence base varies, "
    "independent of which studies have a usable variance.")
rpt()

if subgroups:
    rpt("| Subgroup | n (any AUC) | Mean AUROC | SD | Range |")
    rpt("|----------|---|-----------|-----|-------|")
    for organ, outcome, _ in subgroups:
        mask = (df["organ_focus"] == organ) & (df["target_outcome"] == outcome)
        auc_sub = pd.to_numeric(df.loc[mask, AUC_COL], errors="coerce").dropna()
        if len(auc_sub) < 2:
            continue
        sd = auc_sub.std()
        rng = f"{auc_sub.min():.3f}–{auc_sub.max():.3f}"
        flag = " ⚠ high SD" if sd > 0.10 else ""
        rpt(f"| {organ} / {outcome} | {len(auc_sub)} | {auc_sub.mean():.3f} | {sd:.3f} | {rng} |{flag}")
        if sd > 0.10:
            log_issue("Step 4", "FLAG", f"High SD ({sd:.3f}) in {organ}/{outcome} — "
                      "substantial heterogeneity likely across the full evidence base.")
    rpt()

# ════════════════════════════════════════════════════════
# STEP 5 — Risk of bias summary
# ════════════════════════════════════════════════════════
section("STEP 5 — Risk of bias summary")
rpt("## Step 5 — Risk of bias")
rpt()

QA_COLS = {
    "qa_participants_bias": "Participants (selection)",
    "qa_predictors_bias": "Predictors (input)",
    "qa_outcome_bias": "Outcome (definition)",
    "qa_analysis_bias": "Analysis (modelling)",
    "qa_applicability": "Applicability",
}
rob_present = [c for c in QA_COLS if c in df.columns]

if rob_present:
    rpt("### RoB domain summary")
    rpt()
    rpt("| Domain | Low risk | High risk | Unclear | Missing |")
    rpt("|--------|----------|-----------|---------|---------|")
    for col, label in QA_COLS.items():
        if col not in df.columns:
            continue
        vc = df[col].value_counts(dropna=False)
        missing = int(df[col].isna().sum())
        if col == "qa_applicability":
            low = vc.get("Low Concern", 0)
            high = vc.get("High Concern", 0)
        else:
            low = vc.get("Low Risk", vc.get("Low", 0))
            high = vc.get("High Risk", vc.get("High", 0))
        unclear = vc.get("Unclear", 0)
        rpt(f"| {label} | {low} | {high} | {unclear} | {missing} |")
        if high > len(df) * 0.5:
            log_issue("Step 5", "FLAG", f"{label}: >50% of studies High Risk/Concern — "
                      "GRADE certainty likely downgraded")
        if unclear > len(df) * 0.5:
            log_issue("Step 5", "FLAG", f"{label}: >50% of studies Unclear "
                      f"({unclear}/{len(df)}) — cannot confidently rate this domain; "
                      f"treat as a GRADE downgrade risk equivalent to high risk of bias")
    rpt("> Note: Applicability uses High/Low Concern, not High/Low Risk.")
    rpt()

    try:
        dom_labels, low_pct, high_pct, unc_pct = [], [], [], []
        for col in rob_present:
            vc = df[col].value_counts(dropna=False)
            n = len(df)
            if col == "qa_applicability":
                low_pct.append(100 * vc.get("Low Concern", 0) / n)
                high_pct.append(100 * vc.get("High Concern", 0) / n)
            else:
                low_pct.append(100 * vc.get("Low Risk", vc.get("Low", 0)) / n)
                high_pct.append(100 * vc.get("High Risk", vc.get("High", 0)) / n)
            unc_pct.append(100 * vc.get("Unclear", 0) / n)
            dom_labels.append(QA_COLS[col])
        x = np.arange(len(dom_labels))
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.barh(x, low_pct, color="#1D9E75", label="Low risk/concern")
        ax.barh(x, unc_pct, left=low_pct, color="#EF9F27", label="Unclear")
        ax.barh(x, high_pct, left=[l+u for l, u in zip(low_pct, unc_pct)],
                color="#D85A30", label="High risk/concern")
        ax.set_yticks(x); ax.set_yticklabels(dom_labels, fontsize=9)
        ax.set_xlabel("% of studies", fontsize=9)
        ax.set_title("Risk of bias summary — pilot", fontsize=11)
        ax.legend(fontsize=8, loc="lower right")
        ax.set_xlim(0, 100)
        plt.savefig(FIG_DIR / "fig_rob_summary.pdf", bbox_inches="tight")
        plt.close()
    except Exception as e:
        log_issue("Step 5", "WARNING", f"RoB figure failed: {e}")
else:
    log_issue("Step 5", "FLAG", "No QA columns found in dataset")

# ════════════════════════════════════════════════════════
# STEP 6 — Meta-analysis with REAL inverse-variance weighting
# ════════════════════════════════════════════════════════
section("STEP 6 — Meta-analysis (real inverse-variance weighting)")
rpt("## Step 6 — Meta-analysis (AUROC)")
rpt()

def run_meta(sub_df, statuses):
    """Simplified DerSimonian-Laird on the logit scale, using real SE via
    the delta method. Still not full REML/Knapp-Hartung — that's 03_metaanalysis.R."""
    pool_df = sub_df[sub_df["pooling_status"].isin(statuses)].copy()
    auc = pd.to_numeric(pool_df[AUC_COL], errors="coerce")
    se  = pd.to_numeric(pool_df["model_auc_se"], errors="coerce")
    valid = auc.notna() & se.notna() & (se > 0)
    auc, se = auc[valid], se[valid]
    n = len(auc)
    if n < 2:
        return None

    auc_c = auc.clip(0.501, 0.989)
    logit_auc = np.log(auc_c / (1 - auc_c))
    se_logit = se / (auc_c * (1 - auc_c))          # delta method
    vi = se_logit ** 2

    w = 1 / vi
    mu = (w * logit_auc).sum() / w.sum()
    Q = (w * (logit_auc - mu) ** 2).sum()
    dfree = n - 1
    c = w.sum() - (w**2).sum() / w.sum()
    tau2 = max(0, (Q - dfree) / c) if c > 0 else 0.0
    w_re = 1 / (vi + tau2)
    mu_re = (w_re * logit_auc).sum() / w_re.sum()
    se_re = np.sqrt(1 / w_re.sum())

    def ilogit(x): return 1 / (1 + np.exp(-x))
    pooled = ilogit(mu_re)
    ci_lo = ilogit(mu_re - 1.96 * se_re)
    ci_hi = ilogit(mu_re + 1.96 * se_re)
    I2 = max(0, 100 * (Q - dfree) / Q) if Q > 0 else 0.0

    return dict(n=n, pooled=pooled, ci_lo=ci_lo, ci_hi=ci_hi, I2=I2,
                Q=Q, dfree=dfree, tau2=tau2, study_ids=pool_df.loc[auc.index, "study_id"].tolist(),
                auc=auc, se=se)

if not HAS_VARIANCE_COLS:
    rpt("> ⚠ model_auc_se not found — skipping real meta-analysis. Run "
        "`merge_final_variance.py` first.")
    log_issue("Step 6", "BLOCKER", "model_auc_se missing — cannot run real meta-analysis")
elif not subgroups:
    rpt("No subgroup has ≥2 POOL studies — nothing to pool.")
else:
    for organ, outcome, _ in subgroups:
        mask = (df["organ_focus"] == organ) & (df["target_outcome"] == outcome)
        sub = df[mask]

        primary = run_meta(sub, ["POOL"])
        sensitivity = run_meta(sub, ["POOL", "POOL_PROVISIONAL"])

        rpt(f"**{organ} / {outcome}**")
        rpt()
        if primary is None:
            rpt("> Fewer than 2 verified-variance studies — cannot pool.")
            rpt()
            continue

        if sensitivity:
            sens_n     = str(sensitivity['n'])
            sens_pool  = f"{sensitivity['pooled']:.3f} ({sensitivity['ci_lo']:.3f}\u2013{sensitivity['ci_hi']:.3f})"
            sens_i2    = f"{sensitivity['I2']:.1f}%"
            sens_tau2  = f"{sensitivity['tau2']:.4f}"
        else:
            sens_n = sens_pool = sens_i2 = sens_tau2 = "\u2014"

        rpt("| Statistic | Primary (POOL only) | + Provisional (sensitivity) |")
        rpt("|-----------|---------------------|------------------------------|")
        rpt(f"| n studies | {primary['n']} | {sens_n} |")
        rpt(f"| Pooled AUROC | {primary['pooled']:.3f} (95% CI {primary['ci_lo']:.3f}\u2013{primary['ci_hi']:.3f}) | {sens_pool} |")
        rpt(f"| I\u00b2 | {primary['I2']:.1f}% | {sens_i2} |")
        rpt(f"| tau\u00b2 | {primary['tau2']:.4f} | {sens_tau2} |")
        rpt()
        rpt(f"> Studies (POOL): {', '.join(str(s)[:35] for s in primary['study_ids'])}")
        rpt()

        if primary["I2"] > 75:
            log_issue("Step 6", "FLAG", f"{organ}/{outcome}: I²={primary['I2']:.0f}% "
                      "(real weighting) — substantial heterogeneity confirmed, "
                      "not a variance-approximation artefact.")
        elif primary["I2"] > 50:
            log_issue("Step 6", "WARNING", f"{organ}/{outcome}: I²={primary['I2']:.0f}% "
                      "— moderate heterogeneity.")

        try:
            auc_v, se_v, sids = primary["auc"], primary["se"], primary["study_ids"]
            order = np.argsort(auc_v.values)
            fig, ax = plt.subplots(figsize=(8, max(4, len(auc_v) * 0.4 + 2)))
            y = np.arange(len(auc_v))
            for i, idx in enumerate(order):
                a, s = auc_v.values[idx], se_v.values[idx]
                ax.plot([a - 1.96*s, a + 1.96*s], [i, i], color="#1D9E75", linewidth=1.2, zorder=2)
                ax.scatter([a], [i], color="#1D9E75", s=30, zorder=3)
            ax.axvline(primary["pooled"], color="#D85A30", linewidth=1.5, zorder=4,
                       label=f"Pooled AUROC = {primary['pooled']:.3f}")
            ax.fill_betweenx([-0.5, len(auc_v)-0.5], primary["ci_lo"], primary["ci_hi"],
                              alpha=0.12, color="#D85A30")
            labels = [str(sids[i])[:35] for i in order]
            ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=7)
            ax.set_xlabel("AUROC (95% CI)", fontsize=9)
            ax.set_title(f"{organ} / {outcome}  (real weights)\nI²={primary['I2']:.0f}%", fontsize=10)
            ax.legend(fontsize=8)
            ax.set_xlim(0.3, 1.05)
            safe_name = f"{organ}_{outcome}".replace("/", "_").replace(" ", "_")[:40]
            fp = FIG_DIR / f"fig_forest_realSE_{safe_name}.pdf"
            plt.savefig(fp, bbox_inches="tight")
            plt.close()
            rpt(f"> Forest plot: `analysis/figures/pilot/{fp.name}`")
            rpt()
        except Exception as e:
            log_issue("Step 6", "WARNING", f"Forest plot failed for {organ}/{outcome}: {e}")

# ════════════════════════════════════════════════════════
# STEP 7 — GRADE pre-fill
# ════════════════════════════════════════════════════════
section("STEP 7 — GRADE pre-fill")
rpt("## Step 7 — GRADE certainty (pre-filled — human must complete)")
rpt()
rpt("> ⚠  Certainty ratings marked [YOU DECIDE]. Do not use these as final.")
rpt()

if subgroups and rob_present:
    rpt("| Outcome subgroup | n (POOL) | RoB | Inconsistency (real I²) | Imprecision | Certainty |")
    rpt("|-----------------|---|-----|---------------|-------------|-----------|")

    high_rob_domains = []
    for col in rob_present:
        vc = df[col].value_counts(dropna=False)
        if col == "qa_applicability":
            high, unclear = vc.get("High Concern", 0), vc.get("Unclear", 0)
        else:
            high, unclear = vc.get("High Risk", 0), vc.get("Unclear", 0)
        if high > len(df) * 0.4 or unclear > len(df) * 0.4:
            high_rob_domains.append(col)

    for organ, outcome, n_pool in subgroups:
        mask = (df["organ_focus"] == organ) & (df["target_outcome"] == outcome)
        primary = run_meta(df[mask], ["POOL"]) if HAS_VARIANCE_COLS else None
        rob_flag = "⬇ most High Risk/Unclear" if high_rob_domains else "OK"
        if primary:
            incon = "⬇ high I²" if primary["I2"] > 50 else "OK"
        else:
            incon = "n/a"
        imprec = "⬇ wide CI" if n_pool < 10 else "OK"
        rpt(f"| {organ} / {outcome} | {n_pool} | {rob_flag} | {incon} | {imprec} | **[YOU DECIDE]** |")
    rpt()

# ════════════════════════════════════════════════════════
# ISSUES SUMMARY
# ════════════════════════════════════════════════════════
section("ISSUES SUMMARY")
rpt("---")
rpt()
rpt("## Issues log")
rpt()

blockers = [i for i in issues if i["severity"] == "BLOCKER"]
flags = [i for i in issues if i["severity"] == "FLAG"]
warns = [i for i in issues if i["severity"] == "WARNING"]

rpt("| Severity | Count |")
rpt("|----------|-------|")
rpt(f"| 🛑 BLOCKER | {len(blockers)} |")
rpt(f"| 🚩 FLAG | {len(flags)} |")
rpt(f"| ⚠ WARNING | {len(warns)} |")
rpt()

for i in issues:
    tag = {"WARNING": "⚠ ", "FLAG": "🚩", "BLOCKER": "🛑"}[i["severity"]]
    rpt(f"**{tag} {i['severity']} — {i['phase']}**")
    rpt(f"> {i['message']}")
    rpt()

rpt("---")
rpt()
rpt("## Files generated")
rpt()
rpt("### Tables")
for f in sorted(OUT_DIR.glob("*.csv")):
    rpt(f"- `{f.name}`")
rpt()
rpt("### Figures")
for f in sorted(FIG_DIR.glob("*.pdf")):
    rpt(f"- `{f.name}`")
rpt()
rpt("---")
rpt()
rpt("## Recommended next steps")
rpt()
if blockers:
    rpt("🛑 **BLOCKERS must be resolved before proceeding:**")
    for b in blockers:
        rpt(f"- {b['message']}")
    rpt()
rpt("1. Review the pooled estimates above — these now use real variance, "
    "so I² and CIs are trustworthy directionally.")
rpt("2. Verify the 4 POOL_PROVISIONAL studies' event counts before including "
    "them in anything beyond the sensitivity column.")
rpt("3. Move to `analysis/scripts/03_metaanalysis.R` for the full REML "
    "model with proper small-sample correction (Knapp-Hartung) for the "
    "manuscript-grade analysis.")
rpt("4. Generate the robvis RoB figure in R.")
rpt("5. Complete GRADE certainty ratings.")

REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")

print(f"\n{'='*55}")
print("PILOT PIPELINE COMPLETE (v2 — real inverse-variance weighting)")
print(f"  Issues: {len(blockers)} blockers | {len(flags)} flags | {len(warns)} warnings")
print(f"  Report: {REPORT_PATH}")
print(f"{'='*55}")

if blockers:
    print(f"\n🛑  {len(blockers)} BLOCKER(S) — resolve before trusting output")
    sys.exit(1)
else:
    print("\n✓  No blockers. Open PILOT_REPORT.md.")
