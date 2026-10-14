# Eligibility criteria — operational guide

This document describes the criteria as applied during screening and full-text review.
Source: Covidence eligibility criteria, five-reviewer consensus.

---

## Inclusion criteria (all must be met)

1. **Population:** Study includes adults who are heart and/or lung transplant candidates, recipients, or donors.
2. **Intervention:** The primary analytical component is a non-linear ML model (decision tree, neural network, random forest, gradient boosting, deep learning, etc.).
3. **Outcome:** At least one of: survival, waitlist mortality, post-transplant complications, quality of life, or health economics.
4. **Publication date:** January 1 2018 or later.
5. **Study type:** RCT, registry study, or observational study — peer-reviewed and published in full.
6. **Language:** English.

---

## Exclusion criteria (any one is sufficient to exclude)

| Priority | Reason | Notes |
|----------|--------|-------|
| 1 | Wrong population: animal study | Exclude at T&A |
| 2 | Wrong population: paediatric only | Exclude at T&A; flag mixed if adult data extractable |
| 3 | Wrong intervention: linear model only | Logistic regression, Cox regression without ML |
| 4 | Wrong intervention: ML is secondary component | ML analyses omics output but is not the primary tool |
| 5 | Wrong intervention: LVAD as destination therapy focus | Not transplant |
| 6 | Wrong study type: abstract / conference proceeding | Not peer-reviewed full text |
| 7 | Wrong study type: case report | |
| 8 | Wrong study type: review / systematic review | |
| 9 | Wrong study type: letter / editorial | |
| 10 | Wrong study type: pre-publication (preprint) | |
| 11 | Wrong language: non-English | |
| 12 | Wrong date: published before January 1 2018 | |

---

## Uncertain / borderline handling

- **Meta-analyses:** Classify as "maybe" at title/abstract screening. Assess at full text; exclude from quantitative synthesis but retain for background/discussion.
- **Mixed adult/paediatric populations:** Include if adult subgroup data can be extracted separately. Flag `flag_reeval = 1` with reason `SUBGROUP_ONLY` in master dataset.
- **ML as primary vs secondary:** If unclear from abstract, retrieve full text. Exclude if the ML model is applied only to process the output of another primary method.

---

## Full-text exclusion reasons (Covidence order)

Applied in this priority order during full-text review:

1. Wrong population (animal / paediatric)
2. Wrong intervention (no ML / ML secondary only)
3. Wrong outcome (no eligible outcome reported)
4. Wrong study type (review / letter / editorial / conference / preprint)
5. Wrong language
6. Wrong date (pre-2018)
7. Duplicate publication (earlier version of same dataset — retain most complete)
8. Insufficient data for extraction (no extractable results despite eligible design)
