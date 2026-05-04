#!/usr/bin/env python3
"""
Compare two election result snapshots and print a change report.

Usage:
    python3 compare_results.py                          # auto: current vs _prev
    python3 compare_results.py old.csv new.csv          # explicit files
"""

import sys
import pandas as pd


def add_scores(df: pd.DataFrame) -> pd.DataFrame:
    split = df["Round"].astype(str).str.extract(r"(\d+)/(\d+)").astype(float)
    df = df.copy()
    df["rounds_done"]  = split[0]
    df["rounds_total"] = split[1]
    df["pct_complete"] = df["rounds_done"] / df["rounds_total"]
    df["projected_margin"] = (
        (df["Margin"] / df["rounds_done"]) * df["rounds_total"]
    ).round(0)
    df["contest_index"] = df["Margin"] / (df["pct_complete"] * df["rounds_total"])
    return df


def classify(row) -> str:
    ci, pm, pct, m = (
        row["contest_index"], row["projected_margin"],
        row["pct_complete"], row["Margin"],
    )
    if ci <= 10 or pm < 500:
        return "knife-edge"
    if ci <= 40 or pm < 3_000:
        return "competitive"
    if pm >= 20_000 or (pct >= 0.75 and m >= 5_000):
        return "decided"
    return ""


def compare(old_path: str, new_path: str) -> None:
    old = add_scores(pd.read_csv(old_path))
    new = add_scores(pd.read_csv(new_path))
    new["category"] = new.apply(classify, axis=1)

    m = old.merge(new, on="Constituency", suffixes=("_old", "_new"))
    m["round_delta"]  = m["rounds_done_new"] - m["rounds_done_old"]
    m["margin_delta"] = m["Margin_new"] - m["Margin_old"]

    # --- Seat tally ---
    old_tally = old.groupby("Leading Party").size().rename("before")
    new_tally = new.groupby("Leading Party").size().rename("now")
    tally = pd.concat([old_tally, new_tally], axis=1).fillna(0).astype(int)
    tally["change"] = tally["now"] - tally["before"]
    print("=== SEAT TALLY ===")
    print(tally.sort_values("now", ascending=False).to_string())

    # --- Lead changes ---
    flips = m[m["Leading Party_old"] != m["Leading Party_new"]]
    print(f"\n=== LEAD CHANGES ({len(flips)}) ===")
    for _, r in flips.iterrows():
        print(
            f"  {r['Constituency']:25s}  "
            f"{r['Leading Party_old']} → {r['Leading Party_new']}  "
            f"({r['Margin_old']:,} → {r['Margin_new']:,})"
        )

    # --- Results declared ---
    status_chg = m[m["Status_old"] != m["Status_new"]]
    print(f"\n=== RESULTS DECLARED THIS UPDATE ({len(status_chg)}) ===")
    for _, r in status_chg.iterrows():
        print(
            f"  {r['Constituency']:25s}  "
            f"{r['Leading Candidate_new']} ({r['Leading Party_new']})  "
            f"margin {r['Margin_new']:,}"
        )

    # --- Seats in play ---
    print("\n=== SEATS IN PLAY ===")
    close = new[new["category"].isin(["knife-edge", "competitive"])].sort_values(
        "projected_margin"
    )
    print(
        f"{'Constituency':25s} {'Cat':12s} {'Leader':35s} "
        f"{'Margin':>7} {'Round':>7} {'Proj':>7}"
    )
    for _, r in close.iterrows():
        was = old[old["Constituency"] == r["Constituency"]]
        flag = (
            " <<FLIPPED"
            if not was.empty and was.iloc[0]["Leading Party"] != r["Leading Party"]
            else ""
        )
        print(
            f"  {r['Constituency']:23s} {r['category']:12s} "
            f"{r['Leading Party']:35s} {r['Margin']:>7,} "
            f"{r['Round']:>7} {r['projected_margin']:>7,.0f}{flag}"
        )

    # --- Declared total ---
    declared = new[new["Status"] == "Result Declared"]
    print(f"\n=== TOTAL RESULTS DECLARED: {len(declared)} ===")

    # --- Summary ---
    print(f"\n=== SUMMARY ===")
    print(
        f"Avg counting done : {new['pct_complete'].mean()*100:.1f}%"
        f"  (was {old['pct_complete'].mean()*100:.1f}%)"
    )
    print(f"Seats advanced    : {(m['round_delta'] > 0).sum()}")
    print(f"Lead changes      : {len(flips)}")
    print(f"Margins widened   : {(m['margin_delta'] > 300).sum()}")
    print(f"Margins narrowed  : {(m['margin_delta'] < -300).sum()}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        old_csv, new_csv = sys.argv[1], sys.argv[2]
    else:
        old_csv = "tn_election_results_may2026_prev.csv"
        new_csv = "tn_election_results_may2026.csv"

    compare(old_csv, new_csv)
