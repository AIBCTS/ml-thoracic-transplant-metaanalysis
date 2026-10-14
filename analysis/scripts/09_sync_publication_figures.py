#!/usr/bin/env python
"""
09_sync_publication_figures.py — copy pipeline figures to their publication names.

The shipped figures are copies of pipeline outputs under different names
(Figure2_PROBAST_summary <- rob_summary, FigureS1_temporal <- desc_temporal, ...). Until
30 Aug 2026 that copy was made by hand, so every pipeline run left the submission package
holding the previous render. It bit once for real: the run regenerated rob_summary.pdf with
the corrected appraisal distribution while Figure2_PROBAST_summary.* still carried the
29 July image, so the manuscript would have shipped text saying the analysis domain was
unclear in 45 (58%) above a figure drawing 44 (57%).

This runs as the last pipeline stage so the copy cannot lag the source. It also re-renders a
PNG that is older than its own PDF - 04_rob_figures.py writes rob_summary.pdf but not the
matching PNG, and a plain copy of the stale PNG is how the first manual fix went wrong.

Writes into BOTH figure directories, which test_package_consistency.py requires to agree.
"""
import shutil
import sys
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "analysis" / "figures"
PUB = ROOT / "results" / "figures"
PUB.mkdir(parents=True, exist_ok=True)

# publication name -> pipeline output name
FIGMAP = {
    "Figure2_PROBAST_summary":        "rob_summary",
    "FigureS1_PROBAST_traffic_light": "rob_traffic_light",
    # Figures 2-4 come from build_forest_forestploter.R (Lancet style: middle-dot
    # decimals, thin-space thousands, gray squares, transparent diamond), which writes
    # publication-named files directly into analysis/figures. From 30 Aug to 1 Sep
    # 2026 these three rows pointed at the matplotlib forests from 05b_forest_plots.py,
    # which use period decimals — that shipped in manuscript PDF v41-v48. The mpl files
    # remain as pipeline diagnostics but must not be shipped.
    "Figure3_forest_heart_1yr":       "Figure3_forest_heart_1yr",
    "Figure4_forest_heart_AR":        "Figure4_forest_heart_AR",
    "Figure5_forest_lung_1yr":        "Figure5_forest_lung_1yr",
    "FigureS4_temporal":              "desc_temporal",
    "FigureS2_auroc_vs_n":            "desc_auroc_vs_n",
    "FigureS3_auroc_vs_features":     "desc_auroc_vs_features",
    # identity rows: 10_determinants_figure.py and 11_ml_vs_linear_figure.py write these
    # publication names directly into analysis/figures (scripted since 2026-09-02)
    "Figure7_determinants":           "Figure7_determinants",
    "Figure6_ML_vs_linear":           "Figure6_ML_vs_linear",
}
# Not pipeline-derived, never touched here: Figure1_PRISMA (author-supplied).

DPI = 300
copied, rendered, missing = 0, [], []

for pub, src in FIGMAP.items():
    pdf, png = SRC / f"{src}.pdf", SRC / f"{src}.png"
    if not pdf.exists() and not png.exists():
        missing.append(src)
        continue
    # a PNG older than its own PDF is stale: re-render rather than copy it forward
    if pdf.exists() and (not png.exists() or png.stat().st_mtime < pdf.stat().st_mtime - 1):
        doc = pdfium.PdfDocument(str(pdf))
        doc[0].render(scale=DPI / 72).to_pil().save(png)
        rendered.append(src)
    for ext in ("pdf", "png"):
        s = SRC / f"{src}.{ext}"
        if not s.exists():
            continue
        for dst in (SRC / f"{pub}.{ext}", PUB / f"{pub}.{ext}"):
            if s.resolve() == dst.resolve():
                continue  # identity mapping: the source already carries the publication name
            shutil.copy2(s, dst)
            copied += 1

print(f"Synced {len(FIGMAP)} publication figures ({copied} files written)")
if rendered:
    print(f"  re-rendered from PDF because the PNG lagged it: {', '.join(rendered)}")
if missing:
    print(f"  MISSING pipeline source, not synced: {', '.join(missing)}")
    sys.exit(1)
