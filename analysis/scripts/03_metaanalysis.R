###############################################################################
# 03_metaanalysis.R
# Phase 3B — manuscript-grade meta-analysis of ML discrimination (AUROC / C-index)
# AI in thoracic transplantation systematic review
#
# Random-effects meta-analysis (REML) with Knapp-Hartung small-sample
# correction, on the logit scale (delta-method SE), back-transformed for
# reporting. Prediction intervals reported alongside CIs — essential given
# the high between-study heterogeneity.
#
# Run from the project root:
#   Rscript analysis/scripts/03_metaanalysis.R
#
# Requires (install once):
#   install.packages(c("metafor","readxl","dplyr"))
#
# Reads:  data/extraction_master_LOCKED*.xlsx  (most recent)
# Writes: analysis/outputs/metaanalysis_results.csv
#         analysis/outputs/metaanalysis_leave_one_out.csv
#         analysis/figures/forest_<subgroup>.pdf
#         analysis/figures/funnel_<subgroup>.pdf
###############################################################################

suppressWarnings(suppressMessages({
  ok <- requireNamespace("metafor", quietly = TRUE) &&
        requireNamespace("readxl",  quietly = TRUE) &&
        requireNamespace("dplyr",   quietly = TRUE)
}))
if (!ok) stop("Missing packages. Run: install.packages(c('metafor','readxl','dplyr'))")
suppressMessages({library(metafor); library(readxl); library(dplyr)})

# The default LC_CTYPE here is "C", in which sub()/write.csv cannot translate non-ASCII
# author names: "Koritsánszky" came out as "Korits<U+00E1>nszky" in
# metaanalysis_leave_one_out.csv, and a byte-level sub() then aborted with "unable to
# translate to a wide string". Setting a UTF-8 ctype fixes the class rather than each site.
invisible(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"))

# ---- Paths (assumes run from project root) ---------------------------------
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
EXTR_DIR <- file.path(ROOT, "data")
OUT_DIR  <- file.path(ROOT, "analysis", "outputs")
FIG_DIR  <- file.path(ROOT, "analysis", "figures")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)
dir.create(FIG_DIR, showWarnings = FALSE, recursive = TRUE)

# ---- Load most recent locked master ----------------------------------------
locked <- sort(list.files(EXTR_DIR, pattern = "extraction_master_LOCKED.*\\.xlsx$",
                          full.names = TRUE))
if (length(locked) == 0) stop("No extraction_master_LOCKED*.xlsx in data/")
master_file <- tail(locked, 1)
cat("Loading:", basename(master_file), "\n")
df <- readxl::read_excel(master_file)

req <- c("model_auc_final", "model_auc_se", "pooling_status",
         "organ_focus", "target_outcome", "study_id", "total_sample_size")
miss <- setdiff(req, names(df))
if (length(miss) > 0)
  stop("Master file missing required columns: ", paste(miss, collapse = ", "),
       "\nRun merge_final_variance.py first.")


# ---- Short "Author Year" labels for forest plots --------------------------
author_year <- function(sid) {
  s <- sub("^[0-9]+_", "", sid)                       # strip leading "NN_"
  ym <- regmatches(s, regexpr("(19|20)[0-9]{2}", s))  # 4-digit year
  yr <- if (length(ym) > 0) ym[1] else ""
  # author = text before " et al", the study_id's " - " separator, or "-<year>".
  # NOT any hyphen: "\\s*-\\s*" truncated hyphenated surnames ("Tran-Dinh A" -> "Tran").
  au <- strsplit(s, "\\s+et al|\\s+-\\s+|-(?=[0-9])", perl = TRUE)[[1]][1]
  au <- trimws(sub("[ -]+$", "", au))
  # drop trailing initials carried by the 2026-extension study_ids ("Sharma G", "Luo L")
  # drop trailing initials carried by the 2026-extension study_ids ("Sharma G", "Luo L")
  au <- sub("\\s+[A-Z]{1,3}\\.?$", "", au, perl=TRUE)
  trimws(paste(au, yr))
}
df$label <- vapply(df$study_id, author_year, character(1))

# ---- Logit transform with delta-method SE ----------------------------------
prep <- function(d) {
  auc <- as.numeric(d$model_auc_final)
  se  <- as.numeric(d$model_auc_se)
  keep <- !is.na(auc) & !is.na(se) & se > 0
  d <- d[keep, ]; auc <- auc[keep]; se <- se[keep]
  auc_c <- pmin(pmax(auc, 0.501), 0.989)
  d$yi  <- log(auc_c / (1 - auc_c))          # logit
  d$sei <- se / (auc_c * (1 - auc_c))        # delta-method SE on logit scale
  d$auc <- auc
  d$se_raw <- se
  if (!"label" %in% names(d)) d$label <- d$study_id
  d$N <- suppressWarnings(as.numeric(d$total_sample_size))
  d
}

# ---- Core analysis: one random-effects model -------------------------------
run_ma <- function(d, label, min_k = 3) {
  d <- prep(d)
  k <- nrow(d)
  if (k < 2) {
    cat(sprintf("  [%s] only %d study — skipped\n", label, k))
    return(NULL)
  }
  fragile <- k < min_k
  res <- tryCatch(
    rma(yi = d$yi, sei = d$sei, method = "REML", test = "knha"),
    error = function(e) { cat("  rma error:", conditionMessage(e), "\n"); NULL })
  if (is.null(res)) return(NULL)

  pred <- predict(res, transf = transf.ilogit)
  d$weight_pct <- as.numeric(weights(res))  # metafor: % contribution to the RE model
  out <- data.frame(
    subgroup        = label,
    k               = k,
    fragile_small_k = fragile,
    pooled_auroc    = round(pred$pred, 4),
    ci_lo           = round(pred$ci.lb, 4),
    ci_hi           = round(pred$ci.ub, 4),
    pi_lo           = round(pred$pi.lb, 4),   # prediction interval
    pi_hi           = round(pred$pi.ub, 4),
    I2              = round(res$I2, 1),
    H2              = round(res$H2, 2),
    tau2            = round(res$tau2, 4),
    Q               = round(res$QE, 3),
    Q_pval          = signif(res$QEp, 4),
    stringsAsFactors = FALSE
  )
  attr(out, "res") <- res
  attr(out, "data") <- d
  out
}

# ---- Define subgroups (organ x outcome), primary = POOL only ---------------
combos <- df %>%
  filter(pooling_status %in% c("POOL", "POOL_PROVISIONAL")) %>%
  count(organ_focus, target_outcome, name = "n_any") %>%
  arrange(desc(n_any))

cat("\n=== PRIMARY ANALYSES (pooling_status == POOL) ===\n")
results <- list()
for (i in seq_len(nrow(combos))) {
  og <- combos$organ_focus[i]; oc <- combos$target_outcome[i]
  sub <- df %>% filter(organ_focus == og, target_outcome == oc,
                       pooling_status == "POOL")
  lab <- paste(og, "/", oc)
  r <- run_ma(sub, lab)
  if (!is.null(r)) {
    results[[lab]] <- r
    cat(sprintf("  %-32s k=%d  AUROC=%.3f [%.3f, %.3f]  PI=[%.3f, %.3f]  I2=%.0f%%%s\n",
                lab, r$k, r$pooled_auroc, r$ci_lo, r$ci_hi, r$pi_lo, r$pi_hi, r$I2,
                if (r$fragile_small_k) "  (FRAGILE, k<3)" else ""))
  }
}

if (length(results) == 0) stop("No poolable subgroups with >= 2 POOL studies.")

results_df <- do.call(rbind, lapply(results, function(x) { attr(x,"res")<-NULL; attr(x,"data")<-NULL; x }))
rownames(results_df) <- NULL
write.csv(results_df, file.path(OUT_DIR, "metaanalysis_results.csv"), row.names = FALSE)
cat("\nSaved: analysis/outputs/metaanalysis_results.csv\n")

# ---- Metafor-style forest plot for EVERY poolable subgroup -----------------
# Same layout as the primary Heart/1-year figure, generated for all subgroups
# so the whole figure set shares one consistent style.
sanitize <- function(s) gsub("[^A-Za-z0-9]+", "_", s)
cat("\n=== FOREST PLOTS (metafor style, all poolable subgroups) ===\n")
for (lab in names(results)) {
  r   <- results[[lab]]
  res <- attr(r, "res")
  d   <- attr(r, "data")
  if (is.null(res) || is.null(d) || r$k < 2) next
  fname <- paste0("forest_", sanitize(lab), "_metafor.pdf")
  ord   <- order(d$auc)
  # For high-tau2 subgroups the 95% prediction interval can span almost the whole
  # axis; drawing it as a line (addpred=TRUE) makes the summary row overrun the
  # plot. Instead we REPORT the PI in the summary label and draw only the diamond.
  # Uses metafor's default annotation column (proven, correctly ordered).
  mlab_txt <- sprintf("RE model (REML + Knapp-Hartung): I2=%.0f%%, tau2=%.3f, k=%d\n95%% prediction interval: %.2f - %.2f",
                      res$I2, res$tau2, res$k, r$pi_lo, r$pi_hi)
  # Per-study N and meta-analytic weight (%), matching the Lancet forest-plot
  # convention. ilab columns are placed left of the AUROC/CI annotation column.
  ilab_mat <- cbind(format(d$N, big.mark = ",", trim = TRUE),
                     sprintf("%.1f%%", d$weight_pct))
  pdf(file.path(FIG_DIR, fname), width = 10.6, height = 5.9)
  par(mar = c(5, 4, 3, 2))
  forest(res, transf = transf.ilogit, refline = 0.70, order = ord,
         addpred = FALSE,
         xlab = "AUROC (95% CI)",
         header = c("Study (Author Year)", "AUROC [95% CI]"),
         slab = d$label, digits = 3,
         ilab = ilab_mat, ilab.xpos = c(1.30, 1.55), ilab.pos = 2,
         xlim = c(-0.60, 2.05), alim = c(0.40, 1.00), steps = 7,
         cex = 0.85, psize = 1.0, col = "#1D9E75",
         mlab = mlab_txt)
  text(c(1.30, 1.55), r$k + 2.2, c("N", "Weight"), cex = 0.85, font = 2, pos = 2, xpd = TRUE)
  dev.off()
  cat(sprintf("  %-32s k=%d -> figures/%s%s\n",
              lab, r$k, fname, if (r$fragile_small_k) "  (FRAGILE, k<3)" else ""))
}

# ---- Headline subgroup: full diagnostics -----------------------------------
# Heart / 1-year survival is the best-powered; run the complete work-up.
headline_lab <- "Heart / 1-year survival"
if (headline_lab %in% names(results)) {
  cat("\n=== FULL DIAGNOSTICS:", headline_lab, "===\n")
  r   <- results[[headline_lab]]
  res <- attr(r, "res")
  d   <- attr(r, "data")

  # Forest plot (back-transformed to AUROC scale), studies ordered by AUROC.
  # addpred=TRUE draws the 95% prediction interval on the summary row (the
  # canonical metafor way — robust across versions).
  ord <- order(d$auc)
  d$weight_pct <- as.numeric(weights(res))
  ilab_mat <- cbind(format(d$N, big.mark = ",", trim = TRUE),
                     sprintf("%.1f%%", d$weight_pct))
  pdf(file.path(FIG_DIR, "forest_Heart_1_year_survival_metafor.pdf"), width = 10.6, height = 6.3)
  par(mar = c(5, 4, 3, 2))
  # mlab split across two lines (\n) so the summary label does not run
  # rightward into the forest region near the reference line.
  mlab_txt <- sprintf("RE model (REML + Knapp-Hartung)\nI2 = %.0f%%, tau2 = %.3f, k = %d",
                      res$I2, res$tau2, res$k)
  forest(res, transf = transf.ilogit, refline = 0.70, order = ord,
         addpred = TRUE,
         xlab = "AUROC (95% CI)",
         header = c("Study (Author Year)", "AUROC [95% CI]"),
         slab = d$label, digits = 3,
         ilab = ilab_mat, ilab.xpos = c(1.30, 1.55), ilab.pos = 2,
         xlim = c(-0.60, 2.05), alim = c(0.4, 1.0), steps = 7,
         cex = 0.9, psize = 1.1, col = "#1D9E75",
         mlab = mlab_txt)
  text(c(1.30, 1.55), r$k + 3.2, c("N", "Weight"), cex = 0.9, font = 2, pos = 2, xpd = TRUE)
  dev.off()
  cat("  Forest plot -> figures/forest_Heart_1_year_survival_metafor.pdf\n")
  cat(sprintf("    95%% prediction interval: %.3f - %.3f (shown as dotted line on summary row)\n",
              r$pi_lo, r$pi_hi))

  # Funnel plot + Egger's test (low power at k=9 — reported with caveat)
  pdf(file.path(FIG_DIR, "funnel_heart_1yr_survival.pdf"), width = 7, height = 6)
  funnel(res, xlab = "logit(AUROC)")
  dev.off()
  egg <- tryCatch(regtest(res, model = "rma"), error = function(e) NULL)
  if (!is.null(egg)) {
    cat(sprintf("  Egger's test: z=%.3f, p=%.4f  (LOW POWER at k=%d — interpret with caution)\n",
                egg$zval, egg$pval, r$k))
    # 2026-09-04 (v1.1): persisted so the GRADE table can cite it once k reaches 10
    write.csv(data.frame(subgroup = "Heart / 1-year survival", k = r$k,
                         egger_z = round(egg$zval, 3), egger_p = round(egg$pval, 4)),
              file.path(OUT_DIR, "egger_test.csv"), row.names = FALSE)
  }

  # Leave-one-out
  l1o <- leave1out(res, transf = transf.ilogit)
  l1o_df <- data.frame(omitted = d$label,
                       pooled_auroc = round(l1o$estimate, 4),
                       ci_lo = round(l1o$ci.lb, 4),
                       ci_hi = round(l1o$ci.ub, 4),
                       I2 = round(l1o$I2, 1))
  write.csv(l1o_df, file.path(OUT_DIR, "metaanalysis_leave_one_out.csv"), row.names = FALSE)
  cat("  Leave-one-out -> outputs/metaanalysis_leave_one_out.csv\n")
  cat(sprintf("    range of pooled AUROC across leave-one-out: %.3f - %.3f\n",
              min(l1o$estimate), max(l1o$estimate)))

  # ---- Sensitivity 1: include POOL_PROVISIONAL ----
  sub_sens <- df %>% filter(organ_focus == "Heart", target_outcome == "1-year survival",
                            pooling_status %in% c("POOL", "POOL_PROVISIONAL"))
  r_sens <- run_ma(sub_sens, paste(headline_lab, "(+provisional)"))
  if (!is.null(r_sens))
    cat(sprintf("  SENSITIVITY (+provisional): k=%d  AUROC=%.3f [%.3f, %.3f]  I2=%.0f%%\n",
                r_sens$k, r_sens$pooled_auroc, r_sens$ci_lo, r_sens$ci_hi, r_sens$I2))


  # ---- Sensitivity 3: registry overlap (appendix R4, main-text Results/Limitations) ----
  # Studies within a pool drawing on the same national registry (SRTR) over overlapping
  # enrolment windows are not independent. Retain only the LARGEST SRTR study in each pooled
  # subgroup together with every non-SRTR study, and re-pool. Until 2026-09-04 these figures
  # (heart 0.696 [0.464, 0.858]; lung 0.815 [0.524, 0.946]) had no producing code.
  is_srtr <- grepl("SRTR", as.character(df$DatasetName), fixed = TRUE)
  reg_rows <- list()
  for (sg in list(c("Heart", "1-year survival"), c("Lung", "1-year survival"), c("Heart", "Acute Rejection"))) {
    sub_all <- df[df$organ_focus == sg[1] & df$target_outcome == sg[2] & df$pooling_status == "POOL", ]
    srtr_sub <- is_srtr[df$organ_focus == sg[1] & df$target_outcome == sg[2] & df$pooling_status == "POOL"]
    n_srtr <- sum(srtr_sub)
    if (n_srtr <= 1) {
      reg_rows[[length(reg_rows) + 1]] <- data.frame(subgroup = paste(sg[1], "/", sg[2]), k_full = nrow(sub_all),
        n_srtr = n_srtr, k_reduced = nrow(sub_all), pooled_auroc = NA, ci_lo = NA, ci_hi = NA, I2 = NA,
        note = "no or one SRTR study - unaffected")
      next
    }
    N_sub <- suppressWarnings(as.numeric(sub_all$total_sample_size))
    keep_idx <- !srtr_sub | (srtr_sub & N_sub == max(N_sub[srtr_sub], na.rm = TRUE))
    r_reg <- run_ma(sub_all[keep_idx, ], paste(sg[1], "/", sg[2], "(largest SRTR + non-SRTR)"))
    if (!is.null(r_reg)) {
      reg_rows[[length(reg_rows) + 1]] <- data.frame(subgroup = paste(sg[1], "/", sg[2]), k_full = nrow(sub_all),
        n_srtr = n_srtr, k_reduced = r_reg$k, pooled_auroc = r_reg$pooled_auroc, ci_lo = r_reg$ci_lo,
        ci_hi = r_reg$ci_hi, I2 = r_reg$I2, note = "largest SRTR study retained")
      cat(sprintf("  SENSITIVITY (registry overlap) %s / %s: k=%d -> %d  AUROC=%.3f [%.3f, %.3f]  I2=%.0f%%\n",
                  sg[1], sg[2], nrow(sub_all), r_reg$k, r_reg$pooled_auroc, r_reg$ci_lo, r_reg$ci_hi, r_reg$I2))
    }
  }
  write.csv(do.call(rbind, reg_rows), file.path(OUT_DIR, "metaanalysis_sensitivity_registry.csv"), row.names = FALSE)

  # ---- Sensitivity 4: internally validated studies only (appendix R5) ----
  # Until 2026-09-04 the internal-only pools quoted in R5 (heart 0.715, lung 0.784) had no
  # producing code. Same run_ma; external = validation_method contains "External".
  int_rows <- list()
  for (sg in list(c("Heart", "1-year survival"), c("Lung", "1-year survival"), c("Heart", "Acute Rejection"))) {
    sub_all <- df[df$organ_focus == sg[1] & df$target_outcome == sg[2] & df$pooling_status == "POOL", ]
    is_ext <- grepl("External", as.character(sub_all$validation_method))
    r_int <- if (sum(!is_ext) >= 2) run_ma(sub_all[!is_ext, ], paste(sg[1], "/", sg[2], "(internal only)")) else NULL
    int_rows[[length(int_rows) + 1]] <- data.frame(subgroup = paste(sg[1], "/", sg[2]), k_full = nrow(sub_all),
      n_external = sum(is_ext), k_internal = sum(!is_ext),
      pooled_auroc = if (is.null(r_int)) NA else r_int$pooled_auroc, ci_lo = if (is.null(r_int)) NA else r_int$ci_lo,
      ci_hi = if (is.null(r_int)) NA else r_int$ci_hi, I2 = if (is.null(r_int)) NA else r_int$I2)
    if (!is.null(r_int))
      cat(sprintf("  SENSITIVITY (internal only) %s / %s: k=%d -> %d  AUROC=%.3f [%.3f, %.3f]\n",
                  sg[1], sg[2], nrow(sub_all), r_int$k, r_int$pooled_auroc, r_int$ci_lo, r_int$ci_hi))
  }
  write.csv(do.call(rbind, int_rows), file.path(OUT_DIR, "metaanalysis_sensitivity_internal.csv"), row.names = FALSE)

  # ---- Sensitivity 5: externally validated studies only (appendix R5) ----
  # v1.1 (2026-09-04): with Miller 2022 the heart 1-year pool holds three externally validated
  # studies, so the external-only pool becomes estimable at the pre-specified k>=3 minimum.
  ext_rows <- list()
  for (sg in list(c("Heart", "1-year survival"), c("Lung", "1-year survival"), c("Heart", "Acute Rejection"))) {
    sub_all <- df[df$organ_focus == sg[1] & df$target_outcome == sg[2] & df$pooling_status == "POOL", ]
    is_ext <- grepl("External", as.character(sub_all$validation_method))
    r_ext <- if (sum(is_ext) >= 3) run_ma(sub_all[is_ext, ], paste(sg[1], "/", sg[2], "(external only)")) else NULL
    ext_rows[[length(ext_rows) + 1]] <- data.frame(subgroup = paste(sg[1], "/", sg[2]), k_full = nrow(sub_all),
      k_external = sum(is_ext),
      pooled_auroc = if (is.null(r_ext)) NA else r_ext$pooled_auroc, ci_lo = if (is.null(r_ext)) NA else r_ext$ci_lo,
      ci_hi = if (is.null(r_ext)) NA else r_ext$ci_hi, I2 = if (is.null(r_ext)) NA else r_ext$I2,
      pi_lo = if (is.null(r_ext)) NA else r_ext$pi_lo, pi_hi = if (is.null(r_ext)) NA else r_ext$pi_hi)
    if (!is.null(r_ext))
      cat(sprintf("  SENSITIVITY (external only) %s / %s: k=%d -> %d  AUROC=%.3f [%.3f, %.3f]  I2=%.0f%%\n",
                  sg[1], sg[2], nrow(sub_all), r_ext$k, r_ext$pooled_auroc, r_ext$ci_lo, r_ext$ci_hi, r_ext$I2))
  }
  write.csv(do.call(rbind, ext_rows), file.path(OUT_DIR, "metaanalysis_sensitivity_external.csv"), row.names = FALSE)

  # ---- Exploratory meta-regression: validation method as moderator ----
  # Tests whether validation methodology explains the heterogeneity.
  # NOTE: exploratory only — very low power at k=9; report as hypothesis-generating.
  if ("validation_method" %in% names(df)) {
    dmod <- prep(df %>% filter(organ_focus=="Heart", target_outcome=="1-year survival",
                               pooling_status=="POOL"))
    # as.data.frame + local vectors: rma() evaluates `mods` in the calling frame, so a
    # tibble column assigned with $ was not visible to it and the fit silently errored
    # into the tryCatch NULL branch — the result existed but was never reported.
    dmod <- as.data.frame(dmod)
    .yi <- dmod$yi; .sei <- dmod$sei
    val_ext <- grepl("External", dmod$validation_method)
    if (length(unique(val_ext)) > 1) {
      mr <- tryCatch(rma(yi=.yi, sei=.sei, mods=~val_ext, method="REML", test="knha"),
                     error=function(e) NULL)
      if (!is.null(mr)) {
        cat(sprintf("\n  META-REGRESSION (external vs internal validation):\n    moderator p=%.4f, R2=%.1f%% (EXPLORATORY, low power)\n",
                    mr$pval[2], ifelse(is.na(mr$R2), 0, mr$R2)))
        # persist it: the main text cites this p-value, so it must not live only in stdout
        bt <- function(x) exp(x)/(1+exp(x))
        write.csv(data.frame(
          subgroup = "Heart / 1-year survival",
          moderator = "validation_type_external_vs_internal",
          k = nrow(dmod), n_external = sum(val_ext), n_internal = sum(!val_ext),
          moderator_p = round(mr$pval[2], 4), QM_p = round(mr$QMp, 4),
          R2_pct = round(ifelse(is.na(mr$R2), 0, mr$R2), 1),
          auroc_internal = round(bt(mr$b[1]), 3),
          auroc_external = round(bt(mr$b[1] + mr$b[2]), 3),
          # 2026-09-04: appendix R5 prints the coefficient table; persist it so it is gated.
          b_intercept = round(mr$b[1], 4), ci_lo_intercept = round(mr$ci.lb[1], 4), ci_hi_intercept = round(mr$ci.ub[1], 4),
          p_intercept = round(mr$pval[1], 4),
          b_external = round(mr$b[2], 4), ci_lo_external = round(mr$ci.lb[2], 4), ci_hi_external = round(mr$ci.ub[2], 4),
          QM = round(mr$QM, 4), tau2_before = round(res$tau2, 4), tau2_after = round(mr$tau2, 4),
          note = "Exploratory; REML with Knapp-Hartung; low power; hypothesis-generating only"),
          file.path(OUT_DIR, "metaregression_validation.csv"), row.names = FALSE)
      }
    }
  }
}

cat("\n=== DONE ===\n")
cat("Primary results: analysis/outputs/metaanalysis_results.csv\n")
cat("Figures:         analysis/figures/forest_*.pdf, funnel_*.pdf\n")
cat("\nReminder: fragile_small_k=TRUE subgroups (k<3) are hypothesis-generating\n")
cat("only — Cochran's Q has near-zero power to detect heterogeneity at k=2-3.\n")
