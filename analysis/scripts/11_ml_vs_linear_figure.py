#!/usr/bin/env python3
"""11_ml_vs_linear_figure.py — render Figure 7 (paired ML vs linear comparator, Tier 1).

Reads analysis/outputs/ml_vs_linear_paired.csv (produced by 07_ml_vs_linear.py) and the
newest LOCKED master (external-validation flags), renders the publication figure into
analysis/figures/Figure6_ML_vs_linear.png/.pdf. Until 2026-09-02 this figure had no
producing script — it was built in-session on 2026-07-28. Layout is that approved build.
The title's counts are computed from the data, so a Tier-1 change re-titles the figure
rather than shipping a stale claim (figure-style rule: claim-titles must be true).
"""
import glob, os, re
import numpy as np, pandas as pd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# -- figure style (inlined from the session's apply_figure_style; scripts must be standalone) --
def _apply_style(sizes):
    big, mid, small = sizes
    mpl.rcParams.update({
        "font.size": big, "axes.titlesize": big, "axes.labelsize": big,
        "legend.fontsize": mid, "xtick.labelsize": small, "ytick.labelsize": small,
        "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.6, "lines.linewidth": 1.2, "patch.linewidth": 0.6,
        "xtick.major.size": 3.0, "xtick.major.width": 0.6,
        "ytick.major.size": 3.0, "ytick.major.width": 0.6,
        "legend.frameon": False, "figure.dpi": 200, "savefig.dpi": 300,
        "savefig.bbox": "tight", "pdf.fonttype": 42, "ps.fonttype": 42,
    })
META_GREY = "#888888"

_apply_style((9, 8, 7))

lv = pd.read_csv(os.path.join(ROOT, "analysis", "outputs", "ml_vs_linear_paired.csv"))
locked = sorted(glob.glob(os.path.join(ROOT, "data", "extraction_master_LOCKED*.xlsx")))
m = pd.read_excel(locked[-1], sheet_name="Sheet1").set_index("num")
lv = lv[lv["num"].isin(m.index)]                     # guard: only studies in the locked master
lv["t1"] = lv["tier1"].astype(str).str.lower().eq("true")
lv["ext"] = lv["num"].map(lambda n: "External" in str(m.loc[n, "validation_method"]))
t1 = lv[lv["t1"]].copy().sort_values("delta")
# Row labels are bare surnames (the approved 2026-07-28 design): first token of the label
# after stripping the "(num)" suffix and any trailing "et al."/initials; Tran -> Tran-Dinh
# is the one truncation the CSV carries that a surname rule cannot recover.
def surname(lbl):
    s = re.sub(r"\s*\(\d+\)", "", str(lbl)).strip()
    s = re.split(r"\s+", s)[0].rstrip(".,")
    return {"Tran": "Tran-Dinh"}.get(s, s)
t1["nm"] = t1["label"].map(surname)
t1["tie"] = t1["delta"].abs() <= 0.005
n_higher = int((t1["delta"] > 0.005).sum())

fig, ax = plt.subplots(figsize=(7.2, 4.8))
y = np.arange(len(t1)); ML, LIN = "#1b6ca8", "#8c8c8c"
for i, (_, r) in enumerate(t1.iterrows()):
    ax.plot([r["linear_model_auc"], r["ml"]], [i, i], color="#d0d0d0", lw=1.5,
            zorder=1, solid_capstyle="round")
off = t1["tie"].map({True: 0.10, False: 0.0})
ax.scatter(t1["linear_model_auc"], y - off, s=46, facecolors="none", edgecolors=LIN,
           linewidths=1.3, zorder=3, label="Linear comparator")
ax.scatter(t1["ml"], y + off, s=46, c=ML, zorder=4, label="Machine learning")
lbl = [f"{n} \u2020" if e else n for n, e in zip(t1["nm"], t1["ext"])]
ax.set_yticks(y); ax.set_yticklabels(lbl, fontsize=8)
for i, e in enumerate(t1["ext"]):
    if e: ax.get_yticklabels()[i].set_fontweight("bold")
for i, tie in enumerate(t1["tie"]):
    if tie:
        ax.annotate("tied", (max(t1.iloc[i]["ml"], t1.iloc[i]["linear_model_auc"]), i),
                    textcoords="offset points", xytext=(11, -3), fontsize=7, color="#777777")
ax.set_xlabel("AUROC"); ax.set_xlim(0.5, 1.0); ax.set_ylim(-0.9, len(t1) - 0.2)
# journal decimal style on the axis (the shipped figure writes 0·5, not 0.5)
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent)); from figstyle import DEC, dec, fmt as _fmt, axis_formatter, smart_axis_formatter, g_axis_formatter  # decimal mark from config.yaml (2026-09-04)
ax.xaxis.set_major_formatter(g_axis_formatter())
# NO in-figure title (author decision 2026-09-04, every figure except Figure 1): the
# journal sets the title from the legend, so a title in the artwork duplicates it and
# can drift from it.
# The legend states the 12 studies and the two ties, and Results carries "higher in 10".
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.30), ncol=2, handletextpad=0.4)
fig.tight_layout()
FD = os.path.join(ROOT, "analysis", "figures")
fig.savefig(os.path.join(FD, "Figure6_ML_vs_linear.png"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FD, "Figure6_ML_vs_linear.pdf"), bbox_inches="tight")
print(f"Figure7 written: tier1 n={len(t1)} | higher {n_higher} | tied {int(t1['tie'].sum())} "
      f"| external {int(t1['ext'].sum())} | paired total {len(lv)}")
