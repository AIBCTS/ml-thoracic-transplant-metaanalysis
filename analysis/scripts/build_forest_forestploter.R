###############################################################################
# build_forest_forestploter.R
# Rebuild forest plots (Fig 2-4) in Lancet Digital Health style with forestploter.
# Reuses the metafor data-prep from 03_metaanalysis.R, renders each of the three
# poolable organ-outcome subgroups to PDF + PNG.
###############################################################################
suppressMessages({library(metafor); library(readxl); library(dplyr); library(forestploter); library(grid)})

# The default LC_CTYPE here is "C", in which sub()/write.csv cannot translate non-ASCII
# author names: "Koritsánszky" came out as "Korits<U+00E1>nszky" in
# metaanalysis_leave_one_out.csv, and a byte-level sub() then aborted with "unable to
# translate to a wide string". Setting a UTF-8 ctype fixes the class rather than each site.
invisible(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"))

find_root <- function() {
  wd <- normalizePath(getwd())
  parts <- strsplit(wd, .Platform$file.sep)[[1]]
  for (i in length(parts):1) {
    cand <- do.call(file.path, as.list(parts[1:i]))
    if (cand == "") cand <- .Platform$file.sep
    if (dir.exists(file.path(cand, "data")) && file.exists(file.path(cand, "config.yaml"))) return(cand)
  }
  stop("Run from the repository root (no data/ and config.yaml found)")
}
ROOT <- find_root()
EXTR_DIR <- file.path(ROOT, "data")
FIG_DIR  <- file.path(ROOT, "analysis", "figures")
# Write into the pipeline figures directory. 09_sync_publication_figures.py copies from
# there into the package's 02_figures. The previous value pointed at the long-renamed
# FINAL_submission_package_74_study, so from 30 Aug 2026 this script wrote into a dead
# directory and the sync stage silently shipped the matplotlib forests (period decimals)
# in place of these Lancet-style renders (middle-dot decimals) — manuscript PDF v41+.
OUT_FIG  <- file.path(ROOT, "analysis", "figures")

locked <- sort(list.files(EXTR_DIR, pattern="extraction_master_LOCKED.*\\.xlsx$", full.names=TRUE))
master_file <- tail(locked, 1)
cat("Loading:", basename(master_file), "\n")
df <- readxl::read_excel(master_file)

# Author-Year labels (same logic as 03_metaanalysis.R)
author_year <- function(sid) {
  s <- sub("^[0-9]+_", "", sid)
  ym <- regmatches(s, regexpr("(19|20)[0-9]{2}", s))
  yr <- if (length(ym) > 0) ym[1] else ""
  # Split on " et al", on the study_id's own " - " separator, or on a hyphen before the
  # year ("Hsich-2020"). NOT on any hyphen: "\\s*-\\s*" truncated hyphenated surnames, so
  # "71_Tran-Dinh A et al." rendered as "Tran" while Figure 6's own script rendered
  # "Tran-Dinh" - the two figures spelled one study differently (found 2026-09-04).
  au <- strsplit(s, "\\s+et al|\\s+-\\s+|-(?=[0-9])", perl=TRUE)[[1]][1]
  au <- trimws(sub("[ -]+$", "", au))
  # Drop trailing initials. The 2026-extension study_ids carry them before "et al"
  # ("Koritsánszky KB", "Sharma G", "Luo L", "Tran-Dinh A"), which leaked into labels the
  # legend describes as "first author and year". No surname in any pooled subgroup ends in
  # 1-3 capitals, so the pattern cannot clip a real name.
  # drop trailing initials carried by the 2026-extension study_ids ("Sharma G", "Luo L")
  au <- sub("\\s+[A-Z]{1,3}\\.?$", "", au, perl=TRUE)
  trimws(paste(au, yr))
}
df$label <- vapply(df$study_id, author_year, character(1))

prep <- function(d) {
  auc <- as.numeric(d$model_auc_final); se <- as.numeric(d$model_auc_se)
  keep <- !is.na(auc) & !is.na(se) & se > 0
  d <- d[keep,]; auc <- auc[keep]; se <- se[keep]
  auc_c <- pmin(pmax(auc, 0.501), 0.989)
  d$yi <- log(auc_c/(1-auc_c)); d$sei <- se/(auc_c*(1-auc_c))
  d$auc <- auc; d$N <- suppressWarnings(as.numeric(d$total_sample_size)); d
}

# Decimal mark from config.yaml -> figures.decimal_mark ("middot" | "period"); env FIG_DECIMAL_MARK
# overrides. Added 2026-09-04 so Figures 3-5 follow the same switch as the Python figures (figstyle.py).
read_decimal_mark <- function() {
  v <- Sys.getenv("FIG_DECIMAL_MARK", unset = "")
  if (v == "") {
    cfg <- readLines(file.path(ROOT, "config.yaml"), warn = FALSE)
    hit <- grep("^\\s*decimal_mark\\s*:", cfg, value = TRUE)
    v <- if (length(hit)) gsub('.*:\\s*"?([a-z]+)"?.*', "\\1", hit[1]) else "middot"
  }
  if (!v %in% c("middot", "period")) stop("figures.decimal_mark must be 'middot' or 'period', got: ", v)
  v
}
DECIMAL_MARK <- read_decimal_mark()
DEC <- if (DECIMAL_MARK == "middot") "\u00b7" else "."
cat(sprintf("  decimal mark: %s\n", DECIMAL_MARK))
# number formatter with the configured decimal mark
md <- function(x, digits=3) {
  s <- formatC(x, format="f", digits=digits)
  gsub(".", DEC, s, fixed = TRUE)
}
ci_txt <- function(est, lo, hi) sprintf("%s (%s\u2013%s)", md(est), md(lo), md(hi))

# Three subgroups in figure order: Heart/1yr (Fig2), Heart/AR (Fig3), Lung/1yr (Fig4)
subs <- list(
  list(fig="Figure3_forest_heart_1yr", organ="Heart", outcome="1-year survival",
       title="Forest plot: 1-year survival after heart transplantation"),
  list(fig="Figure4_forest_heart_AR", organ="Heart", outcome="Acute Rejection",
       title="Forest plot: acute rejection after heart transplantation"),
  list(fig="Figure5_forest_lung_1yr", organ="Lung", outcome="1-year survival",
       title="Forest plot: 1-year survival after lung transplantation")
)

# Lancet theme: gray filled squares, black diamond, dashed refline
tm <- forestploter::forest_theme(
  base_size = 11,
  ci_pch = 15,
  ci_col = "black",
  ci_fill = "#B0B0B0",          # gray square (Lancet)
  ci_lwd = 1.1,
  ci_Theight = 0.2,             # whisker end height
  refline_lty = "dashed",
  refline_col = "grey40",
  summary_col = "black",
  summary_fill = NA,               # transparent diamond — dashed line & row shading show through
  base_family = "",
  footnote_gp = gpar(cex=0.75, fontface="italic")
)

for (s in subs) {
  d <- prep(df %>% filter(organ_focus==s$organ, target_outcome==s$outcome, pooling_status=="POOL"))
  d <- as.data.frame(d)
  cat(sprintf("  [%s] k=%d\n", s$fig, nrow(d)))
  res <- rma(yi=as.numeric(d$yi), sei=as.numeric(d$sei), method="REML", test="knha")
  pred <- predict(res, transf=transf.ilogit)
  d$weight_pct <- as.numeric(weights(res))
  # per-study AUROC-scale CI
  d$est <- d$auc
  ci <- data.frame(lo=transf.ilogit(d$yi - 1.96*d$sei), hi=transf.ilogit(d$yi + 1.96*d$sei))
  d$lo <- ci$lo; d$hi <- ci$hi
  ord <- order(d$auc)
  d <- d[ord,]
  k <- nrow(d)

  # box sizes proportional to N (sqrt for area-proportionality, clamped)
  Nv <- d$N; Nv[is.na(Nv)] <- min(Nv, na.rm=TRUE)
  sz <- sqrt(Nv/max(Nv))
  sz <- 0.3 + 0.7*(sz - min(sz))/(max(sz)-min(sz) + 1e-9)

  # Build display table: study rows + summary row
  studies <- data.frame(
    Study = d$label,
    N = ifelse(d$N >= 10000, format(d$N, big.mark="\u2009", trim=TRUE), as.character(d$N)),  # Lancet format (D34)
    Weight = sprintf("%s%%", md(d$weight_pct, 1)),
    ` ` = paste(rep(" ", 26), collapse=" "),
    `AUROC (95% CI)` = mapply(ci_txt, d$est, d$lo, d$hi),
    check.names=FALSE, stringsAsFactors=FALSE
  )
  summ <- data.frame(
    Study = "Overall (RE model)",
    N = "", Weight = "",
    ` ` = paste(rep(" ", 26), collapse=" "),
    `AUROC (95% CI)` = ci_txt(pred$pred, pred$ci.lb, pred$ci.ub),
    check.names=FALSE, stringsAsFactors=FALSE
  )
  het <- data.frame(
    Study = sprintf("Heterogeneity: I\u00b2 = %.0f%%, \u03c4\u00b2 = %s", res$I2, md(res$tau2,3)),
    N="", Weight="",
    ` ` = paste(rep(" ", 26), collapse=" "), `AUROC (95% CI)`="",
    check.names=FALSE, stringsAsFactors=FALSE)
  tab <- rbind(studies, summ, het)

  est_v <- c(d$est, pred$pred, NA)
  lo_v  <- c(d$lo,  pred$ci.lb, NA)
  hi_v  <- c(d$hi,  pred$ci.ub, NA)
  sz_v  <- c(sz, 0.55, NA)   # summary diamond needs a non-NA size to render
  is_sum <- c(rep(FALSE, k), TRUE, FALSE)

  p <- forestploter::forest(tab,
              est = est_v, lower = lo_v, upper = hi_v, sizes = sz_v,
              is_summary = is_sum,
              ci_column = 4,
              ref_line = 0.70,
              xlim = c(0.4, 1.0),
              ticks_at = c(0.4, 0.6, 0.8, 1.0),
              xlab = "AUROC (95% CI)",
              theme = tm)
  # bold summary row; italic + smaller heterogeneity annotation row
  p <- forestploter::edit_plot(p, row=k+1, gp=gpar(fontface="bold"))
  p <- forestploter::edit_plot(p, row=k+2, gp=gpar(fontface="italic", cex=0.85))
  # heterogeneity row background always white (not zebra grey)
  p <- forestploter::edit_plot(p, row=k+2, which="background", gp=gpar(fill="white", col=NA))

  # Journal decimal style on the x-axis ticks. forestploter draws them from ticks_at and
  # exposes no hook for the label text (forest() has ticks_digits only), so the axis came
  # out "0.4 0.6 0.8" with periods while every data value in the table is middle-dot -
  # mixed within one figure, found 2026-09-04 by reading the shipped PDFs' text layer.
  # Rewrite bare numeric text grobs after the plot is built; the pattern anchors on a
  # whole label, so data cells (already middle-dot) and the xlab are untouched.
  fix_dec <- function(g) {
    if (!is.null(g$label) && is.character(g$label))
      g$label <- sub("^([0-9]+)\\.([0-9]+)$", paste0("\\1", DEC, "\\2"), g$label)
    if (!is.null(g$children)) g$children <- lapply(g$children, fix_dec)
    if (!is.null(g$grobs))    g$grobs    <- lapply(g$grobs, fix_dec)
    g
  }
  p <- fix_dec(p)

  pdf_out <- file.path(OUT_FIG, paste0(s$fig, ".pdf"))
  png_out <- file.path(OUT_FIG, paste0(s$fig, ".png"))
  gw <- forestploter::get_wh(plot=p, unit="in")
  ggplot2::ggsave(pdf_out, plot=p, width=gw[1], height=gw[2], device=cairo_pdf)
  ggplot2::ggsave(png_out, plot=p, width=gw[1], height=gw[2], dpi=300, bg="white")
  cat(sprintf("  %s  k=%d  AUROC=%.3f -> %s (+png)\n", s$fig, k, pred$pred, basename(pdf_out)))
}
cat("DONE\n")
