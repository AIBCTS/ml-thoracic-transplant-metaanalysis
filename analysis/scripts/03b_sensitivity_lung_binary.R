###############################################################################
# 03b_sensitivity_lung_binary.R
# Sensitivity analysis: lung / 1-year survival restricted to studies reporting a
# binary AUROC (appendix M8.3). Tian 2023 and Sharma 2025 report a one-year
# time-dependent AUC and are excluded. Same method as the primary analysis
# (03_metaanalysis.R): logit AUROC with delta-method SE, REML, Knapp-Hartung.
#
# Run from the project root:  Rscript analysis/scripts/03b_sensitivity_lung_binary.R
# Reads:  data/extraction_master_LOCKED*.xlsx (most recent)
# Writes: analysis/outputs/metaanalysis_sensitivity_lung_binary.csv
###############################################################################
suppressPackageStartupMessages({ library(readxl); library(metafor) })
find_root <- function() {
  wd <- getwd()
  if (dir.exists(file.path(wd, "data"))) return(wd)
  # walk up
  parts <- strsplit(normalizePath(wd), .Platform$file.sep)[[1]]
  for (i in length(parts):1) {
    cand <- do.call(file.path, as.list(parts[1:i]))
    if (dir.exists(file.path(cand, "data"))) return(cand)
  }
  stop("Could not locate project root (no data/ found). ",
       "Run from the project directory.")
}
ROOT     <- find_root()
ROOT    <- find_root()
locked  <- sort(list.files(file.path(ROOT, "data"), pattern = "extraction_master_LOCKED.*\\.xlsx$", full.names = TRUE))
df      <- read_excel(tail(locked, 1))
d <- subset(df, organ_focus == "Lung" & target_outcome == "1-year survival" & pooling_status == "POOL")
d <- d[!(grepl("^50_Tian", d$study_id) | grepl("^70_Sharma", d$study_id)), ]
auc <- as.numeric(d$model_auc_final); se <- as.numeric(d$model_auc_se)
res <- rma(yi = qlogis(auc), sei = se / (auc * (1 - auc)), method = "REML", test = "knha")
p   <- predict(res, transf = transf.ilogit)
out <- data.frame(subgroup = "Lung / 1-year survival, binary AUROC only", k = res$k,
                  pooled_auroc = round(p$pred, 4), ci_lo = round(p$ci.lb, 4), ci_hi = round(p$ci.ub, 4),
                  pi_lo = round(p$pi.lb, 4), pi_hi = round(p$pi.ub, 4), I2 = round(res$I2, 1),
                  studies = paste(sub(" .*", "", sub("^[0-9]+_", "", d$study_id)), collapse = "; "))
write.csv(out, file.path(ROOT, "analysis", "outputs", "metaanalysis_sensitivity_lung_binary.csv"), row.names = FALSE)
print(out)
