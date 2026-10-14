"""
06_descriptive_figures.py  —  Supplementary descriptive figures.

Generates:
  1. AUROC vs sample size (bubble/scatter, coloured by validation type) —
     the key figure showing that small, internally-validated studies report
     higher/more-variable discrimination than large or externally-validated ones.
  2. AUROC vs number of features (if a feature-count file is present) —
     built to consume verified feature counts once extracted; skips cleanly
     with a message if the file is absent.
  3. Temporal plot — study count and mean AUROC by publication year.

Tested against the locked master. Feature-count figure activates only when
data/feature_counts.csv exists (num, n_features, stage columns).

Usage:
    uv run python analysis/scripts/06_descriptive_figures.py

Reads:   data/extraction_master_LOCKED*.xlsx
         data/feature_counts.csv                   (optional; final-model counts only)
Writes:  analysis/figures/desc_auroc_vs_n.pdf
         analysis/figures/desc_auroc_vs_features.pdf   (if input present)
         analysis/figures/desc_temporal.pdf
"""
import pandas as pd, numpy as np, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path

# House style (author decision 2026-09-04): no in-figure titles (the legend carries the title);
# middle-dot decimals on every numeric axis, as in main-text Figures 3-7; integer ticks on counts.
from matplotlib.ticker import FuncFormatter, MaxNLocator
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent)); from figstyle import DEC, dec, fmt as _fmt, axis_formatter, smart_axis_formatter, g_axis_formatter  # decimal mark from config.yaml (2026-09-04)
_MIDDOT = smart_axis_formatter()
def house_axes(ax, y_middot=True, y_int=False):
    if y_middot:
        ax.yaxis.set_major_formatter(_MIDDOT)
    if y_int:
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))


ROOT     = Path(__file__).resolve().parents[2]
EXTR_DIR = ROOT / "data"
FIG_DIR  = ROOT / "analysis" / "figures"
OUT_STATS=FIG_DIR.parent/"outputs"/"temporal_stats.json"
INP_DIR  = ROOT / "data"
FIG_DIR.mkdir(parents=True, exist_ok=True)

locked = sorted(EXTR_DIR.glob("extraction_master_LOCKED*.xlsx"))
df = pd.read_excel(locked[-1])
print(f"Loaded {locked[-1].name}")

def ay(sid):
    s=re.sub(r'^\d+_','',str(sid));ym=re.search(r'(19|20)\d{2}',s)
    au=re.split(r'\s+et al|\s*-\s*|-(?=\d)',s)[0].strip().rstrip(' -')
    return f"{au} {ym.group(0) if ym else ''}".strip()
df["label"]=df["study_id"].apply(ay)
df["pub_year"]=df["study_id"].apply(lambda s:int(re.search(r'(19|20)\d{2}',str(s)).group(0)) if re.search(r'(19|20)\d{2}',str(s)) else np.nan)
df["auc"]=pd.to_numeric(df["model_auc_final"],errors="coerce")
df["n"]=pd.to_numeric(df["total_sample_size"],errors="coerce")

# validation grouping (3 clean buckets)
def valgroup(v):
    v=str(v).lower()
    if "external" in v: return "External"
    if "cross" in v or "k-fold" in v: return "Cross-validation"
    if "split" in v or "internal" in v: return "Internal split"
    return "Not reported / other"
df["valgroup"]=df["validation_method"].apply(valgroup)

VCOLORS={"External":"#1D9E75","Cross-validation":"#3B7DD8",
         "Internal split":"#EF9F27","Not reported / other":"#B0B0B0"}

# AXIS WORDING, 2026-08-09. The y-axis says "discrimination estimate", not "AUROC":
# the plotted quantity mixes a binary AUROC, a ROC-derived C-statistic at one timepoint,
# a time-dependent AUC at one year and a global concordance index, so "AUROC" claims
# something narrower than the data. Main-text Figure 6 was corrected earlier; S1-S3 were
# not, and their legends already said "discrimination estimate" while the axes said AUROC.
# ---------- FIGURE 1: AUROC vs sample size ----------
sub=df[df["auc"].notna() & df["n"].notna()].copy()
fig,ax=plt.subplots(figsize=(9,6))
for g,c in VCOLORS.items():
    s=sub[sub["valgroup"]==g]
    ax.scatter(s["n"],s["auc"],s=70,c=c,edgecolors="black",linewidths=0.5,
               alpha=0.85,label=f"{g} (n={len(s)})",zorder=3)
ax.axhline(0.70,color="gray",ls=":",lw=1,zorder=1)
ax.text(sub["n"].min(),0.705,dec("0.70 reference"),fontsize=7.5,color="gray")
ax.set_xscale("log")
ax.set_xlabel("Total sample size (log scale)",fontsize=11)
ax.set_ylabel("Reported discrimination estimate",fontsize=11)
ax.legend(fontsize=9,loc="upper left",bbox_to_anchor=(1.01,1),title="Validation",frameon=False)  # outside the axes: at n=75 the lower-right corner holds data
ax.set_ylim(0.55,1.0)
ax.spines[["top","right"]].set_visible(False)
house_axes(ax)
# annotate a few extremes
# Labels: alternate the vertical offset for annotated points that sit within ~0.02 AUROC of each
# other at the low-n end, so neighbouring labels (Kozinski 2025 / Zhang 2026, 2026-09-04) do not overprint.
_ann=sub[(sub["auc"]>0.95)|((sub["n"]<200)&(sub["auc"]>0.85))].sort_values(["auc","n"]).reset_index(drop=True)
for _i,r in _ann.iterrows():
    _close=((_ann["auc"]-r["auc"]).abs()<0.02)&(_ann.index<_i)
    _dy=3+9*int(_close.sum())      # stack upward for each earlier near neighbour
    ax.annotate(r["label"],(r["n"],r["auc"]),fontsize=6.5,
                xytext=(4,_dy),textcoords="offset points",color="#555")
plt.tight_layout()
fig.savefig(FIG_DIR/"desc_auroc_vs_n.pdf",bbox_inches="tight")
fig.savefig(FIG_DIR/"desc_auroc_vs_n.png",bbox_inches="tight",dpi=140)
plt.close()
print(f"  desc_auroc_vs_n.pdf  ({len(sub)} studies plotted)")

# ---------- FIGURE 2: AUROC vs number of features (optional) ----------
feat_file=INP_DIR/"feature_counts.csv"
if feat_file.exists():
    fc=pd.read_csv(feat_file)
    # Figure S3 uses the predictor count of the final model only (stage final_after_selection)
    if "stage" in fc.columns: fc=fc[fc["stage"]=="final_after_selection"].copy()
    fc["nf"]=pd.to_numeric(fc["n_features"],errors="coerce")
    # Join on study number, not on a display label. Label matching silently dropped
    # more than half the feature counts (41 available -> 19 plotted) because the
    # feature file's label spelling differs from the master's, and it also collapses
    # two same-author same-year papers into one row. 'num' is unique per study.
    if "num" in fc.columns and "num" in df.columns:
        fc["kf"]=pd.to_numeric(fc["num"],errors="coerce")
        df["kf"]=pd.to_numeric(df["num"],errors="coerce")
    else:
        raise SystemExit("feature_counts.csv and the master must both carry 'num' to join safely")
    merged=df.merge(fc[["kf","nf"]],on="kf",how="left")
    fsub=merged[merged["auc"].notna() & merged["nf"].notna()].copy()
    # plausibility: n_features should be < sample size
    bad=fsub[fsub["nf"]>=fsub["n"]]
    if len(bad): print(f"  WARNING: {len(bad)} studies have n_features >= sample_size — check: {bad['label'].tolist()}")
    fig,ax=plt.subplots(figsize=(9,6))
    for g,c in VCOLORS.items():
        s=fsub[fsub["valgroup"]==g]
        ax.scatter(s["nf"],s["auc"],s=70,c=c,edgecolors="black",linewidths=0.5,alpha=0.85,label=g,zorder=3)
    ax.axhline(0.70,color="gray",ls=":",lw=1)
    ax.set_xscale("log")
    ax.set_xlabel("Number of input features (log scale)",fontsize=11)
    ax.set_ylabel("Reported discrimination estimate",fontsize=11)
    ax.legend(fontsize=9,loc="upper left",bbox_to_anchor=(1.01,1),title="Validation",frameon=False)  # outside the axes: at n=75 the lower-right corner holds data
    ax.set_ylim(0.55,1.0); ax.spines[["top","right"]].set_visible(False)
    house_axes(ax)
    plt.tight_layout()
    fig.savefig(FIG_DIR/"desc_auroc_vs_features.pdf",bbox_inches="tight")
    fig.savefig(FIG_DIR/"desc_auroc_vs_features.png",bbox_inches="tight",dpi=140)
    plt.close()
    print(f"  desc_auroc_vs_features.pdf  ({len(fsub)} studies with feature counts)")
else:
    print(f"  desc_auroc_vs_features.pdf  SKIPPED — no {feat_file.name} yet")
    print(f"     (place verified feature counts at {feat_file} with columns: study,n_features)")

# ---------- FIGURE 3: Temporal ----------
yr=df[df["pub_year"].notna()].copy()
counts=yr.groupby("pub_year").size()
mean_auc=yr[yr["auc"].notna()].groupby("pub_year")["auc"].mean()
fig,ax1=plt.subplots(figsize=(9,5))
ax1.bar(counts.index,counts.values,color="#C9E3D6",edgecolor="#1D9E75",label="Studies published")
ax1.set_xlabel("Publication year",fontsize=11)
ax1.set_ylabel("Number of studies",fontsize=11,color="#1D9E75")
ax1.tick_params(axis="y",labelcolor="#1D9E75")
ax2=ax1.twinx()
ax2.plot(mean_auc.index,mean_auc.values,"o-",color="#D85A30",lw=1.5,label="Mean reported discrimination estimate")
ax2.set_ylabel("Mean reported discrimination estimate",fontsize=11,color="#D85A30")
ax2.tick_params(axis="y",labelcolor="#D85A30")
ax2.set_ylim(0.5,1.0)
ax2.axhline(0.70,color="gray",ls=":",lw=0.8)
ax1.spines[["top"]].set_visible(False); ax2.spines[["top"]].set_visible(False)
house_axes(ax1, y_middot=False, y_int=True); house_axes(ax2)
plt.tight_layout()
# persist the statistics the Figure S1 legend quotes (gated in test_manuscript_numbers)
from scipy import stats as _st
import json as _json
_ok=yr["auc"].notna()
_rho,_p=_st.spearmanr(yr.loc[_ok,"pub_year"],yr.loc[_ok,"auc"])
_early=sorted(counts.index)[:3]
_json.dump({"n_with_auc":int(_ok.sum()),"rho_year_auc":round(float(_rho),3),"p_year_auc":round(float(_p),2),
            "per_year_counts":{int(k):int(v) for k,v in counts.items()},
            "per_year_mean_auc":{int(k):round(float(v),3) for k,v in mean_auc.items()},
            "earliest_three_years":[int(y) for y in _early],
            "earliest_three_n":int(sum(counts[y] for y in _early)),
            "earliest_three_all_below_070":bool(all(mean_auc[y]<0.70 for y in _early))},
           open(OUT_STATS,"w"),indent=1)
print(f"  temporal stats -> {OUT_STATS.name}: rho={_rho:.3f} p={_p:.2f} n={int(_ok.sum())}")
fig.savefig(FIG_DIR/"desc_temporal.pdf",bbox_inches="tight")
fig.savefig(FIG_DIR/"desc_temporal.png",bbox_inches="tight",dpi=140)
plt.close()
print(f"  desc_temporal.pdf  ({len(counts)} years)")
print("\nDone.")
