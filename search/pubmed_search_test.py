#!/usr/bin/env python3
"""Re-run the PubMed search (search/search_strings.md) through NCBI E-utilities.

1. Search 1 as it stood on 11 June 2024 (records entered in PubMed up to that day).
2. Search 3 with its recorded publication-date filter (2025/8/5 to 2026/6/30).
3. The full review window (publication dates 2018/1/1 to 2026/6/30).
4. Recall: how many of the included studies indexed in PubMed the string retrieves.

PubMed changes over time (new indexing, MeSH updates, corrections), so counts are expected to
be close to, not identical with, the counts recorded at the original search dates.
Usage: python search/pubmed_search_test.py   (needs internet; no API key required)
"""
import csv, json, time, urllib.parse, urllib.request
from pathlib import Path

E = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
HERE = Path(__file__).resolve().parent
L1 = ('heart transplantation[Mesh] OR heart-lung transplantation[Mesh] OR lung transplantation[Mesh] OR "heart transplant*"[tw] OR "heart lung transplant*"[tw] OR cardiac transplant*[tw] OR cardiothoracic transplant*[tw] OR lung transplant*[tw] OR cardiac allograft*[tw] OR heart allograft*[tw] OR lung allograft*[tw] OR cardiac heterograft*[tw] OR heart heterograft*[tw] OR lung heterograft*[tw] OR cardiac hemograft*[tw] OR heart hemograft*[tw] OR lung hemograft*[tw]')
L2 = ('artificial intelligence[Mesh] OR "Machine Learning"[Mesh] OR "Neural Networks, Computer"[Mesh] OR machine learning[tw] OR ML model*[tw] OR neural network*[tw] OR deep learning[tw] OR decision tree*[tw] OR "wearable sensor"[tiab:~3] OR "wearable sensors"[tiab:~3] OR "artificial intelligence" OR AI[tw] OR random forest*[tw] OR random survival forest*[tw] OR natural language processing[tw] OR NLP[tw] OR chatgpt[tw] OR chat gpt[tw] OR large language model*[tw] OR convolutional network*[tw] OR digital twin*[tw] OR gradient boost*[tw] OR bayesian network*[tw] OR vector machine*[tw] OR naive Bayes[tw] OR wearable device*[tw] OR applewatch[tw] OR apple watch[tw] OR galaxy watch[tw] OR tree of predict*[tw]')
L3 = ('"Mortality"[Mesh] OR "Prognosis"[Mesh] OR "Graft Rejection"[Mesh] OR "Immunosuppressive Agents"[Mesh] OR "Diagnostic Imaging"[Mesh] OR "Biopsy"[Mesh] OR "Genomics"[Mesh] OR "Precision Medicine"[Mesh] OR "Renal Insufficiency"[Mesh] OR infections[Mesh] OR outcome*[tiab] OR donor evaluation*[tiab] OR candidate evaluation*[tiab] OR survival[tiab] OR mortality[tiab] OR death*[tiab] OR complication*[tiab] OR rejection*[tiab] OR prognostic[tiab] OR prognosis[tiab] OR predict*[tiab] OR immunosuppressi*[tiab] OR matching[tiab] OR waitlist[tiab] OR wait* time[tiab] OR image[tiab] OR imaging[tiab] OR biops*[tiab] OR genomics[tiab] OR omics[tiab] OR personalized[tiab] OR allograft vasculopathy[tiab] OR renal failure[tiab] OR graft failure*[tiab] OR malignancy[tiab] OR infection*[tiab] OR allocation*[tiab] OR graft rejection*[tiab] OR comorbidit*[tiab] OR cellular rejection*[tiab] OR ACR[tiab] OR "hospital stay"[tiab] OR monitoring[tiab] OR surveillance[tiab] OR modeling[tiab]')
QUERY = f"(({L1}) AND ({L2}) AND ({L3})) NOT (animals[mh] NOT humans[mh])"

def esearch(term, retmax=0, **kw):
    q = {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json", **kw}
    req = urllib.request.Request(E + "esearch.fcgi", data=urllib.parse.urlencode(q).encode())
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.load(r)["esearchresult"]; time.sleep(0.4); return res
        except Exception:
            time.sleep(2 + 2 * attempt)
    raise RuntimeError("E-utilities not reachable")

def main():
    rows = []
    s1 = esearch(QUERY, datetype="edat", mindate="1800/01/01", maxdate="2024/06/11")
    rows.append(("Search 1, records in PubMed by 11 Jun 2024", 320, int(s1["count"])))
    s3 = esearch(f"({QUERY}) AND 2025/8/5:2026/6/30[pdat]")
    rows.append(("Search 3, publication date 5 Aug 2025 to 30 Jun 2026", 105, int(s3["count"])))
    win = esearch(f"({QUERY}) AND 2018/1/1:2026/6/30[pdat]", retmax=10000)
    rows.append(("Review window, publication date 1 Jan 2018 to 30 Jun 2026", None, int(win["count"])))
    hits = set(win["idlist"])
    # recall against the included studies that have a DOI in data/included_studies.csv
    inc = list(csv.DictReader(open(HERE.parent / "data" / "included_studies.csv", encoding="utf-8")))
    found, missed, not_indexed = [], [], []
    for s in inc:
        r = esearch(f'"{s["doi"]}"[doi]', retmax=5)
        if not r["idlist"]: not_indexed.append(s["study_id"]); continue
        (found if r["idlist"][0] in hits else missed).append(s["study_id"])
    print(f"{'Search':58} {'recorded':>9} {'today':>7}")
    for name, rec, now in rows: print(f"{name:58} {rec if rec is not None else '':>9} {now:>7}")
    print(f"\nRecall: {len(found)} of {len(found) + len(missed)} included studies indexed in PubMed are retrieved by the PubMed string")
    if missed: print("  not retrieved:", "; ".join(missed))
    print(f"  not found in PubMed by DOI (indexed elsewhere): {len(not_indexed)}")
    out = {"counts": [{"search": n, "recorded": r, "today": c} for n, r, c in rows],
           "recall": {"retrieved": found, "not_retrieved": missed, "not_in_pubmed": not_indexed}}
    (HERE / "pubmed_search_test_result.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))

if __name__ == "__main__":
    main()
