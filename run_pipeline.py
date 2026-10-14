#!/usr/bin/env python3
"""Run the full analysis from the locked extraction database.

    python run_pipeline.py            # all stages, from data/ to results/
    python run_pipeline.py --check    # then compare key results with expected_results.json

Every stage reads data/extraction_master_LOCKED.xlsx (and, for two stages, the
feature-count files). Statistics are written to analysis/outputs/, figures to
analysis/figures/, and publication-named figures to results/figures/.
"""
import subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
S = ROOT / "analysis" / "scripts"
STAGES = [  # (script, runner, what it produces)
    ("03_metaanalysis.R",          "R",  "pooled AUROC, heterogeneity, prediction intervals, sensitivity analyses (Table 2)"),
    ("03b_sensitivity_lung_binary.R","R", "lung 1-year binary-AUROC-only sensitivity analysis (appendix M8.3)"),
    ("05_grade_table.py",          "py", "GRADE summary of findings (Table 3)"),
    ("04_rob_figures.py",          "py", "risk-of-bias figures (Figure 2, Figure S1)"),
    ("build_forest_forestploter.R","R",  "forest plots (Figures 3-5)"),
    ("pilot_pipeline.py",          "py", "study characteristics (Table 1)"),
    ("07_ml_vs_linear.py",         "py", "paired machine learning vs linear comparison (statistics)"),
    ("11_ml_vs_linear_figure.py",  "py", "Figure 6"),
    ("10_determinants_figure.py",  "py", "determinants of reported discrimination (Figure 7 and statistics)"),
    ("06_descriptive_figures.py",  "py", "Figures S2-S4"),
    ("12_feature_count_stats.py",  "py", "predictor count vs discrimination (statistics)"),
    ("13_pooled_vs_not.py",        "py", "pooled vs not pooled studies (statistics)"),
    ("09_sync_publication_figures.py", "py", "copy figures to results/figures with publication names"),
]
OPTIONAL = {"pilot_pipeline.py"}  # exits 1 when it lists data-quality flags; its tables are still written

def export_tables():
    """Copy the generated tables to results/tables under the manuscript's table names."""
    import shutil
    out = ROOT / "results" / "tables"; out.mkdir(parents=True, exist_ok=True)
    O = ROOT / "analysis" / "outputs"
    for src, dst in [(O / "metaanalysis_results.csv", "Table2_pooled_estimates.csv"),
                     (O / "GRADE_SoF_table.xlsx", "Table3_GRADE_summary_of_findings.xlsx")]:
        shutil.copy2(src, out / dst)
    for f in sorted((O / "pilot").glob("table_*.csv")):
        shutil.copy2(f, out / f"Table1_{f.name[6:]}")
    print(f"--> tables written to {out.relative_to(ROOT)}")

def main():
    for script, runner, what in STAGES:
        cmd = ["Rscript", str(S / script)] if runner == "R" else [sys.executable, str(S / script)]
        t = time.time(); print(f"--> {script}: {what}", flush=True)
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        (ROOT / "analysis" / "outputs" / "logs").mkdir(parents=True, exist_ok=True)
        (ROOT / "analysis" / "outputs" / "logs" / f"{script}.log").write_text(r.stdout + r.stderr)
        if r.returncode != 0 and script not in OPTIONAL:
            print(r.stdout[-2000:], r.stderr[-2000:]); sys.exit(f"stage {script} failed (exit {r.returncode})")
        print(f"    ok ({time.time()-t:.0f} s)", flush=True)
    export_tables()
    if "--check" in sys.argv:
        sys.exit(subprocess.run([sys.executable, str(ROOT / "check_results.py")], cwd=ROOT).returncode)

if __name__ == "__main__":
    main()
