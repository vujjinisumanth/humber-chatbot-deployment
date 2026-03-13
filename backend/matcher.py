import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ✅ Fix (goes one level up from backend/ to find output/)
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULLTIME_XLSX = os.path.join(BASE_DIR, "output", "Humber_FullTime2.xlsx")


def clean_text(x: str) -> str:
    x = "" if x is None else str(x)
    x = re.sub(r"\s+", " ", x).strip()
    return x

def load_fulltime(path: str) -> pd.DataFrame:
    df = pd.read_excel(path).fillna("")
    for col in ["PROGRAM NAME","PROGRAM OVERVIEW","CREDENTIALS","CODE",
                "WORK INTEGRATED LEARNING","FACULTY","YOUR CAREER",
                "PGWP-Eligible","Start Dates","Program Length","SOURCE URL"]:
        if col not in df.columns:
            df[col] = ""
    for c in ["PROGRAM NAME","FACULTY","CREDENTIALS","WORK INTEGRATED LEARNING",
              "PGWP-Eligible","Start Dates","Program Length","SOURCE URL"]:
        df[c] = df[c].astype(str).apply(clean_text)

    df["MATCH_TEXT"] = (
        df["PROGRAM NAME"] + " " +
        df["PROGRAM OVERVIEW"].astype(str) + " " +
        df["YOUR CAREER"].astype(str) + " " +
        df["CREDENTIALS"] + " " +
        df["FACULTY"] + " " +
        df["Program Length"] + " " +
        df["Start Dates"] + " " +
        df["PGWP-Eligible"]
    ).apply(clean_text)
    return df

def apply_filters(df, cred_selected, pgwp_choice,
                  start_choice, length_selected, wil_choice):
    out = df.copy()
    if cred_selected:
        out = out[out["CREDENTIALS"].isin(cred_selected)]
    if pgwp_choice != "All":
        if pgwp_choice == "Not Available":
            out = out[out["PGWP-Eligible"].eq("")]
        else:
            out = out[out["PGWP-Eligible"].str.contains(pgwp_choice, case=False, na=False)]
    if start_choice != "All":
        out = out[out["Start Dates"].str.contains(start_choice, case=False, na=False)]
    if length_selected:
        mask = np.zeros(len(out), dtype=bool)
        pl = out["Program Length"].fillna("").astype(str)
        for token in length_selected:
            mask |= pl.str.contains(re.escape(token), case=False, na=False)
        out = out[mask]
    if wil_choice != "All":
        if wil_choice == "Not Available":
            out = out[out["WORK INTEGRATED LEARNING"].eq("")]
        else:
            out = out[out["WORK INTEGRATED LEARNING"].str.contains("yes", case=False, na=False)]
    return out

def rank_programs(df, jd_text, top_k):
    jd_text = clean_text(jd_text)
    if not jd_text or df.empty:
        return []

    n_docs = len(df)
    min_df = 1 if n_docs <= 2 else 2

    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2),
        min_df=min_df, max_df=1.0
    )
    matrix = vectorizer.fit_transform(df["MATCH_TEXT"].tolist())
    jd_vec = vectorizer.transform([jd_text])
    sims = cosine_similarity(jd_vec, matrix).flatten()
    match_pct = np.round(np.clip(sims, 0, 1) * 100, 2)

    out = df.copy()
    out["MATCH %"] = match_pct
    out = out.sort_values("MATCH %", ascending=False).head(top_k).reset_index(drop=True)

    results = []
    for _, row in out.iterrows():
        results.append({
            "program_name":   row["PROGRAM NAME"],
            "faculty":        row["FACULTY"],
            "credential":     row["CREDENTIALS"],
            "pgwp":           row["PGWP-Eligible"] or "Not Available",
            "start_dates":    row["Start Dates"]   or "Not Available",
            "length":         row["Program Length"] or "Not Available",
            "wil":            row["WORK INTEGRATED LEARNING"] or "Not Available",
            "match_pct":      float(row["MATCH %"]),
            "url":            row["SOURCE URL"]
        })
    return results

