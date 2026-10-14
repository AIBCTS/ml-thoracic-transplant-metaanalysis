"""
04_rob_figures.py  —  Risk-of-bias figures (PROBAST-based, 5 domains).

Produces a traffic-light plot (all studies) and a domain-summary stacked bar.
Tested, matplotlib-only — no dependency on robvis's fragile Generic template.
For the canonical robvis aesthetic, 04_rob_figures.R is also provided.

Usage:
    uv run python analysis/scripts/04_rob_figures.py

Reads:   data/extraction_master_LOCKED*.xlsx  (most recent)
Writes:  analysis/figures/rob_summary.pdf
         analysis/figures/rob_traffic_light.pdf
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
EXTR_DIR = ROOT / "data"
FIG_DIR  = ROOT / "analysis" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

locked = sorted(EXTR_DIR.glob("extraction_master_LOCKED*.xlsx"))
if not locked:
    raise FileNotFoundError("No extraction_master_LOCKED*.xlsx in data/")
df = pd.read_excel(locked[-1])
print(f"Loaded {locked[-1].name}: {len(df)} studies")

QA = {
    "qa_participants_bias": "Participants",
    "qa_predictors_bias":   "Predictors",
    "qa_outcome_bias":      "Outcome",
    "qa_analysis_bias":     "Analysis",
    "qa_applicability":     "Applicability",
}
def norm(v):
    if pd.isna(v): return "Unclear"
    return {"Low Concern":"Low","Low Risk":"Low","High Concern":"High",
            "High Risk":"High","Unclear":"Unclear"}.get(str(v).strip(), "Unclear")

colors  = {"Low":"#1D9E75", "Unclear":"#EF9F27", "High":"#D85A30"}
symbols = {"Low":"+", "Unclear":"?", "High":"\u2212"}
levels  = ["Low","Unclear","High"]

# ---- Summary stacked bar ----
fig, ax = plt.subplots(figsize=(9, 3.2))
for i, col in enumerate(QA):
    vals = df[col].apply(norm); n = len(vals); left = 0
    for lv in levels:
        pct = 100*(vals==lv).sum()/n
        if pct > 0:
            ax.barh(i, pct, left=left, color=colors[lv], edgecolor="white", linewidth=0.7)
            if pct > 6:
                ax.text(left+pct/2, i, f"{pct:.0f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        left += pct
ax.set_yticks(range(len(QA))); ax.set_yticklabels([QA[c] for c in QA], fontsize=10)
ax.set_xlabel("Percentage of studies (%)", fontsize=10); ax.set_xlim(0,100); ax.invert_yaxis()
# NO in-figure title (author decision 2026-09-04, applies to every figure except Figure 1,
# whose title is part of the PRISMA diagram): most journals set the title from the legend,
# so a title in the artwork duplicates it and can drift from it. The legend carries what
# this title said - the domain summary, the 78 studies, and the adapted-rubric disclosure -
# and states the two scales apart, which is why the earlier "Risk of bias" title was wrong
# over the applicability row (bias domains rate RISK OF BIAS, applicability rates CONCERN).
# The per-study figure below (appendix figure S4) still carries a title; deferred to the
# supplement pass with S1-S3 (FOLLOWUP item 12).
ax.legend([Rectangle((0,0),1,1,fc=colors[lv]) for lv in levels], levels,
          loc="lower center", bbox_to_anchor=(0.5,-0.42), ncol=3, fontsize=9,
          frameon=False)   # no legend title: it collides with the x-axis label
                           # ("Percentage of studies (%)") at this figure height
plt.tight_layout(); plt.savefig(FIG_DIR/"rob_summary.pdf", bbox_inches="tight"); plt.close()
print("Saved: figures/rob_summary.pdf")

# ---- Traffic light ----
# Study labels are "First-author Year" to match the forest plots and manuscript
# citation style (NOT the internal "12_Author-Year-Title" extraction id). Rows are
# grouped by organ (Heart, Lung, Other) and sorted alphabetically within each group.
# The two 2025 Singh papers are disambiguated as 2025a / 2025b.
import re as _re
def _clean_label(sid):
    m = _re.match(r"\d+_(.+)", str(sid))
    rest = m.group(1) if m else str(sid)
    ym = _re.search(r"(19|20)\d\d", rest)
    year = ym.group(0) if ym else ""
    author = _re.split(r" et al| - |-(?:19|20)\d\d|-", rest)[0].strip().rstrip("-").strip()
    # Some study_ids carry the first author's initials ("Allehyani B", "Weigt SS").
    # Strip them so every row is "Surname Year" — mixed styles read as an error.
    author = _re.sub(r"\s+[A-Z]{1,3}$", "", author).strip()
    # transliterate characters the PDF font cannot render
    author = author.replace("Koritsánszky", "Koritsanszky")
    # study_id 16 carries the SECOND author's surname; the paper's first author is G. Sangeetha
    if author == "Gnanasambandhan": author = "Sangeetha"
    # restore hyphenated surnames truncated by the split on "-"
    author = {"Tran": "Tran-Dinh", "Davalos": "Davalos-Yerovi",
              "Dueñas": "Duenas-Jurado", "Rajand": "Rajand-Safna"}.get(author, author)
    return f"{author} {year}".strip()
df = df.copy()
df["_label"] = df["study_id"].map(_clean_label)
_organ_order = {"Heart": 0, "Lung": 1, "Other": 2}
df["_o"] = df["organ_focus"].map(lambda x: _organ_order.get(str(x), 3))
df = df.sort_values(["_o", "_label"]).reset_index(drop=True)
# Singh 2025a/b (two distinct papers in the same year)
_singh = df.index[df["_label"] == "Singh 2025"].tolist()
for _rank, _i in enumerate(_singh):
    df.loc[_i, "_label"] = f"Singh 2025{chr(ord('a') + _rank)}"

# Two side-by-side columns: 74 rows in one column is taller than a journal page,
# so the study list is split in half and drawn as two panels sharing one legend.
n = len(df)
# Split at an organ boundary rather than the exact midpoint, so each column holds
# whole organ groups: a band label spanning two rows at a column edge reads as an error.
# Choose the boundary whose split is closest to half.
_bounds = [0] + list(df["organ_focus"].ne(df["organ_focus"].shift()).to_numpy().nonzero()[0][1:]) + [n]
_cut = min(_bounds[1:-1], key=lambda b: abs(b - n/2)) if len(_bounds) > 2 else (n+1)//2
splits = [df.iloc[:_cut].reset_index(drop=True), df.iloc[_cut:].reset_index(drop=True)]
rows_max = max(len(s) for s in splits)
fig, axes = plt.subplots(1, 2, figsize=(9.6, max(6.0, rows_max*0.175)))
for ax, sub in zip(axes, splits):
    m = len(sub)
    for xi, col in enumerate(QA):
        for yi in range(m):
            v = norm(sub.iloc[yi][col])
            ax.scatter(xi, yi, s=64, c=colors[v], edgecolors="black", linewidths=0.4, zorder=3)
            ax.text(xi, yi, symbols[v], ha="center", va="center", fontsize=4.5,
                    color="white", fontweight="bold", zorder=4)
    ax.set_xticks(range(len(QA)))
    ax.set_xticklabels([QA[c] for c in QA], rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(m)); ax.set_yticklabels(list(sub["_label"]), fontsize=5.5)
    ax.set_xlim(-0.5, len(QA)-0.5); ax.set_ylim(rows_max-0.5, -0.5)
    for sp in ("top","right","bottom","left"): ax.spines[sp].set_visible(False)
    ax.tick_params(length=0)
    # organ separators and band labels, computed within this panel
    org = sub["organ_focus"].to_numpy()
    for b in sub["organ_focus"].ne(sub["organ_focus"].shift()).to_numpy().nonzero()[0][1:]:
        # span the grid only: axhline runs the full axes width and would cross the
        # rotated band label sitting just outside the last column
        ax.plot([-0.5, len(QA)-0.5], [b-0.5, b-0.5], color="0.6", lw=0.8,
                clip_on=False, zorder=1)
    for organ in ["Heart", "Lung", "Other"]:
        pos = np.where(org == organ)[0]
        if len(pos):
            ax.text(len(QA) - 0.30, pos.mean(), organ, rotation=270, va="center",
                    ha="left", fontsize=7, fontweight="bold", color="0.3")
# No in-figure title (author decision 2026-09-04; the legend carries it; FOLLOWUP item 12 - the old
# title also asserted "risk of bias" over the applicability column, which is rated as concern).
fig.legend(handles=[Line2D([0],[0], marker='o', color='w', markerfacecolor=colors[lv],
           markeredgecolor='black', markersize=7, label=lv) for lv in levels],
           loc="lower center", ncol=3, fontsize=8, title="Rating", frameon=False,  # "Rating": covers both scales (bias / concern); author decision 2026-09-04
           bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=(0, 0.03, 1, 0.97))
fig.savefig(FIG_DIR/"rob_traffic_light.pdf", bbox_inches="tight")
fig.savefig(FIG_DIR/"rob_traffic_light.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("Saved: figures/rob_traffic_light.pdf")
print("\nDone. Both RoB figures generated.")
