# Installs the R packages used by the analysis, at the versions used for the manuscript.
# Run once:  Rscript install_r_packages.R      (R 4.5.3 was used)
if (!requireNamespace("remotes", quietly = TRUE)) install.packages("remotes", repos = "https://cloud.r-project.org")
pk <- c(metafor = "5.0.1", readxl = "1.5.0", dplyr = "1.2.1", forestploter = "1.1.4", gridExtra = "2.3.1")
for (p in names(pk)) {
  have <- tryCatch(as.character(packageVersion(p)), error = function(e) "")
  if (have != pk[[p]]) remotes::install_version(p, version = pk[[p]], repos = "https://cloud.r-project.org", upgrade = "never")
}
