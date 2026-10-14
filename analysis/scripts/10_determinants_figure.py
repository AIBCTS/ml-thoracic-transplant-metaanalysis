#!/usr/bin/env python3
"""10_determinants_figure.py — statistics AND figure for the determinants analysis (Figure 6).

Produces, from the newest LOCKED master:
  analysis/outputs/determinants_stats.json   (every number cited in main text + appendix S10.12)
  analysis/figures/Figure7_determinants.png/.pdf  (publication-named; figsync ships them)

Until 2026-09-02 these statistics and this figure had NO producing script: they were computed
in-session on 2026-07-30 against the then-current master, and the 2026-08-30/09-01 relocks
moved them in the third decimal while the manuscript kept the stale values (found by the
independent statistics audit, 09_review/STATISTICS_AUDIT_2026-09-01.md). This script is the
single source for those numbers; test_manuscript_numbers.py pins the carriers against its
output. Analysis definitions are as documented in appendix S10.12: analysis set = studies
reporting both a discrimination estimate and a total sample size; Spearman on log10(n);
Mann-Whitney between image/pathology/waveform and tabular-only modalities.
"""
import json, glob, os, re
import numpy as np, pandas as pd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

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

_apply_style((11, 10, 9))

locked = sorted(glob.glob(os.path.join(ROOT, "data", "extraction_master_LOCKED*.xlsx")))
master = locked[-1]
m = pd.read_excel(master, sheet_name="Sheet1")
num = lambda s: pd.to_numeric(s, errors="coerce")
d = m[num(m["model_auc_final"]).notna() & num(m["total_sample_size"]).notna()].copy()
d["auc"] = num(d["model_auc_final"]); d["n"] = num(d["total_sample_size"])

def cls3(s):
    s = str(s).lower()
    if any(k in s for k in ["imaging", "patholog", "waveform"]): return "perception"
    if "tabular" in s: return "tabular"
    return "other"
def vcls(s):
    s = str(s).lower()
    if "external" in s: return "External"
    if "cross" in s or "fold" in s: return "Cross-validation"
    if "split" in s or "hold" in s: return "Internal split"
    return "Not reported/other"
d["cls"] = d["input_modalities"].astype(str).map(cls3)
d["vc"]  = d["validation_method"].map(vcls)

rho, p_rho = stats.spearmanr(np.log10(d["n"]), d["auc"])
per, tab = d[d.cls == "perception"]["auc"], d[d.cls == "tabular"]["auc"]
U, p_U = stats.mannwhitneyu(per, tab)
big, small = d[d.n >= 10000], d[d.n < 2000]
S = dict(master=os.path.basename(master), n_plotted=int(len(d)),
         rho=round(float(rho), 3), p_rho=float(f"{p_rho:.2g}"),
         U=round(float(U), 1), p_U=round(float(p_U), 4),
         per_n=int(len(per)), per_median=round(float(per.median()), 3),
         tab_n=int(len(tab)), tab_median=round(float(tab.median()), 3),
         other_n=int((d.cls == "other").sum()), mw_denominator=int(len(per) + len(tab)),
         ge10k_n=int(len(big)), ge10k_median=round(float(big["auc"].median()), 2),
         lt2k_n=int(len(small)), lt2k_median=round(float(small["auc"].median()), 3))
out = os.path.join(ROOT, "analysis", "outputs", "determinants_stats.json")
json.dump(S, open(out, "w"), indent=1)
print("determinants:", json.dumps(S))

# ---- Figure 6 (layout of the approved 2026-07-30 build) ----
SHAPE = {"perception": "^", "tabular": "o", "other": "s"}
LBL   = {"perception": "Image / pathology / waveform", "tabular": "Registry or tabular",
          "other": "Other or not reported"}
VCOL  = {"External": "#1b6ca8", "Cross-validation": "#e08214", "Internal split": "#7b3294",
          "Not reported/other": META_GREY}
fig, ax = plt.subplots(figsize=(8.4, 5.2))
for cl, mk in SHAPE.items():
    g = d[d.cls == cl]
    for vc, col in VCOL.items():
        gg = g[g.vc == vc]
        if len(gg):
            ax.scatter(gg["n"], gg["auc"], marker=mk, s=46, facecolor=col,
                       edgecolor="white", linewidth=0.6, alpha=0.9, zorder=3)
ax.set_xscale("log")
ax.axhline(0.70, ls=":", lw=0.9, color=META_GREY, zorder=1)
ax.set_xlabel("Study sample size"); ax.set_ylabel("Reported discrimination estimate")
# NO in-figure title (author decision 2026-09-04, every figure except Figure 1): the legend
# states the trend and the Spearman statistic verbatim, so a title would duplicate it.
ax.margins(0.06)
ax.set_xticks([1e2, 1e3, 1e4, 1e5]); ax.set_xticklabels(["100", "1k", "10k", "100k"])
# journal decimal style on the y-axis (0·95, not 0.95) - the same formatter Figure 6 uses.
# The shipped PDF text layer had periods here while Figure 6 had middle dots; found 2026-09-04.
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent)); from figstyle import DEC, dec, fmt as _fmt, axis_formatter, smart_axis_formatter, g_axis_formatter  # decimal mark from config.yaml (2026-09-04)
ax.yaxis.set_major_formatter(axis_formatter("{:.2f}"))
h1 = [plt.Line2D([], [], marker=mk, ls="", mfc=META_GREY, mec="white", ms=7, label=LBL[cl])
      for cl, mk in SHAPE.items()]
h2 = [plt.Line2D([], [], marker="o", ls="", mfc=c, mec="white", ms=7, label=k)
      for k, c in VCOL.items()]
l1 = ax.legend(handles=h1, title="Input modality", loc="upper left", bbox_to_anchor=(1.02, 1.0),
               frameon=False, fontsize=9, title_fontsize=9, alignment="left", handletextpad=0.5)
ax.add_artist(l1)
ax.legend(handles=h2, title="Validation", loc="upper left", bbox_to_anchor=(1.02, 0.55),
          frameon=False, fontsize=9, title_fontsize=9, alignment="left", handletextpad=0.5)
fig.subplots_adjust(right=0.70)
FD = os.path.join(ROOT, "analysis", "figures")
# bbox_extra_artists: without it, tight bbox ignores the ax.add_artist legend and the
# longest modality label clips at the canvas edge (the 2026-07-30 session hit exactly this)
_extra = [l1] + [a for a in ax.get_children() if isinstance(a, mpl.legend.Legend)]
fig.savefig(os.path.join(FD, "Figure7_determinants.png"), dpi=300, bbox_inches="tight",
            pad_inches=0.15, bbox_extra_artists=_extra)
fig.savefig(os.path.join(FD, "Figure7_determinants.pdf"), bbox_inches="tight",
            pad_inches=0.15, bbox_extra_artists=_extra)
print(f"Figure7_determinants written (n={len(d)}, rho={S['rho']})")
