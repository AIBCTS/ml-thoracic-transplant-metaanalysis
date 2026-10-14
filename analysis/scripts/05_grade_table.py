"""
05_grade_table.py  —  GRADE Summary-of-Findings certainty table (pre-filled).

Reads the meta-analysis results and pre-fills a GRADE certainty assessment for
each pooled subgroup, applying standard downgrade logic. Final certainty ratings
are marked [CONFIRM] — the human rater makes the call; this only surfaces the
evidence and a defensible starting suggestion.

Note (13 Oct 2026): the downgrading rules coded below are the pre-filled starting suggestion.
The certainty ratings reported in the manuscript (Table 3) were confirmed by the authors on
4 Sep 2026 under the rules stated in appendix M8.5 (CI and prediction interval against a
discrimination target); the two agree for all three subgroups, but the rules are not identical.

GRADE approach for prognostic model discrimination follows Foroutan et al.
(2020, J Clin Epidemiol) — start at HIGH certainty, then downgrade for risk of
bias, inconsistency, indirectness, imprecision, and publication bias.

Usage:
    uv run python analysis/scripts/05_grade_table.py

Reads:   analysis/outputs/metaanalysis_results.csv   (from 03_metaanalysis.R)
         data/extraction_master_LOCKED*.xlsx    (for RoB context)
Writes:  analysis/outputs/GRADE_SoF_table.xlsx
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
EXTR_DIR = ROOT / "data"
OUT_DIR  = ROOT / "analysis" / "outputs"
RESULTS  = OUT_DIR / "metaanalysis_results.csv"

if not RESULTS.exists():
    raise FileNotFoundError(f"{RESULTS} not found — run 03_metaanalysis.R first")

res = pd.read_csv(RESULTS)
print(f"Loaded {len(res)} pooled subgroups from metaanalysis_results.csv")

# RoB context — the review-wide Analysis-domain Unclear rate is the RoB driver
locked = sorted(EXTR_DIR.glob("extraction_master_LOCKED*.xlsx"))
analysis_unclear_pct = None
if locked:
    m = pd.read_excel(locked[-1])
    if "qa_analysis_bias" in m.columns:
        analysis_unclear_pct = 100*(m["qa_analysis_bias"]=="Unclear").sum()/len(m)

LVL = {4:"High", 3:"Moderate", 2:"Low", 1:"Very Low"}

def assess(row):
    k     = int(row["k"])
    auroc = row["pooled_auroc"]
    ci_lo, ci_hi = row["ci_lo"], row["ci_hi"]
    pi_lo, pi_hi = row["pi_lo"], row["pi_hi"]
    i2    = row["I2"]

    down = 0; reasons = []

    # 1. Risk of bias
    rob = "Serious (\u22121)"; down += 1
    rob_note = "Analysis domain Unclear in majority of studies"
    if analysis_unclear_pct:
        rob_note = f"Analysis domain Unclear in {analysis_unclear_pct:.0f}% of studies"
    reasons.append(f"RoB: {rob_note}")

    # 2. Inconsistency (I^2)
    if i2 >= 75:
        incon = "Very serious (\u22122)"; down += 2; reasons.append(f"Inconsistency: I\u00b2={i2:.0f}%")
    elif i2 >= 50:
        incon = "Serious (\u22121)"; down += 1; reasons.append(f"Inconsistency: I\u00b2={i2:.0f}%")
    else:
        incon = "Not serious"

    # 3. Imprecision — prediction interval width + k
    pi_w = pi_hi - pi_lo
    if k < 3 or pi_w > 0.40:
        imprec = "Very serious (\u22122)"; down += 2
        reasons.append(f"Imprecision: k={k}, PI width={pi_w:.2f}")
    elif pi_w > 0.20 or (ci_hi-ci_lo) > 0.10:
        imprec = "Serious (\u22121)"; down += 1
        reasons.append(f"Imprecision: PI width={pi_w:.2f}")
    else:
        imprec = "Not serious"

    # 4. Indirectness — AUTHOR DECISION (2026-09-04): "Not serious (0)" for all
    # three pooled subgroups. Rationale: populations (thoracic-transplant cohorts),
    # model class (non-linear ML) and outcomes (directly measured survival/rejection,
    # no surrogates) match the review question in every PICO leg; the acute-rejection
    # pool's diagnostic character is disclosed and priced via the dagger footnote and
    # its exploratory label, and is not double-counted here (the corrected scope is
    # "prediction model", r5-20). Logged in CHANGE_LOG_review_rounds_2026-08-09.md.
    indirect = "Not serious (0)"

    # 5. Publication bias
    if k < 10:
        pubbias = "Not assessable (small-study tests underpowered, k<10)"  # wording per external review 2026-09-04
    else:
        # v1.1 (2026-09-04): k reached 10 for heart/1-year; Egger's regression test from 03_metaanalysis.R
        _eg = pd.read_csv(OUT_DIR / "egger_test.csv")
        _eg = _eg[_eg["subgroup"] == row["subgroup"]]
        assert len(_eg) == 1, f"egger_test.csv has no row for {row["subgroup"]}"
        pubbias = f"Not detected (Egger z={_eg['egger_z'].iloc[0]:.2f}, p={_eg['egger_p'].iloc[0]:.2f}; low power at k={k})"

    final = max(1, 4 - down)
    return pd.Series({
        "Outcome": row["subgroup"],
        "No. studies (k)": k,
        "Pooled AUROC (95% CI)": f"{auroc:.3f} ({ci_lo:.3f}\u2013{ci_hi:.3f})",
        "95% Prediction interval": f"{pi_lo:.3f}\u2013{pi_hi:.3f}",
        "Risk of bias": rob,
        "Inconsistency": incon,
        "Indirectness": indirect,
        "Imprecision": imprec,
        "Publication bias": pubbias,
        # [CONFIRM] retired 2026-09-04: all five domains now carry adjudicated values
        # (indirectness by author decision above), so the suggestion stands confirmed.
        "Certainty (suggested)": f"\u2295 {LVL[final]} (author-confirmed 2026-09-04)",
        "Downgrade rationale": "; ".join(reasons),
        "Fragile (k<3)": "YES" if row.get("fragile_small_k", False) else "",
    })

grade = res.apply(assess, axis=1)

# Instructions sheet
instr = pd.DataFrame({"How to use this GRADE table": [
    "GRADE Summary of Findings — AI discrimination in thoracic transplantation",
    "",
    "Each row is a pooled outcome subgroup. Certainty starts at HIGH (per Foroutan",
    "2020 GRADE guidance for prognostic model studies) and is downgraded for the",
    "five GRADE domains.",
    "",
    "The 'Certainty (suggested)' column is a STARTING POINT computed from the data",
    "(I2, prediction interval, k, review-wide RoB). Marked [CONFIRM] — you make the",
    "final call. Two domains cannot be automated and are marked [REVIEW]:",
    "  - Indirectness: does the study population/setting match your review question?",
    "  - Publication bias: only assessable with adequate k (>=10); funnel/Egger.",
    "",
    "IMPORTANT: subgroups flagged 'Fragile (k<3)=YES' should not be presented as",
    "robust pooled estimates. Their wide prediction intervals (e.g. 0.11-0.998)",
    "show the pooled number is essentially uninformative. Report these narratively.",
    "",
    "The primary, defensible finding is Heart / 1-year survival (k=9): its leave-",
    "one-out range (0.68-0.71) and sensitivity analyses all confirm ~0.70.",
    "",
    "Certainty scale: High (++++), Moderate (+++), Low (++), Very Low (+)",
]})

with pd.ExcelWriter(OUT_DIR/"GRADE_SoF_table.xlsx", engine="openpyxl") as w:
    instr.to_excel(w, sheet_name="Instructions", index=False)
    grade.to_excel(w, sheet_name="GRADE_SoF", index=False)

print(f"\nSaved: analysis/outputs/GRADE_SoF_table.xlsx")
print("\nSuggested certainty per subgroup (all [CONFIRM] — you decide final):")
for _, r in grade.iterrows():
    print(f"  {r['Outcome']:<28} {r['Certainty (suggested)']}")
print("\nNote: the uniformly Very Low suggestion reflects the genuine state of this")
print("evidence base — high heterogeneity + Unclear RoB + small k. That is itself")
print("a reportable finding, not a limitation of the analysis.")
