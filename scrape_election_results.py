#!/usr/bin/env python3
"""
Scrape Tamil Nadu assembly election results (May 2026) from ECI website
and save to CSV and Excel.

The results are spread across 12 pages:
  statewiseS221.htm  (page 1)
  statewiseS222.htm  (page 2)
  ...
  statewiseS2212.htm (page 12)

Usage:
    python3 scrape_election_results.py
"""

import subprocess
import sys

from bs4 import BeautifulSoup
import pandas as pd


BASE_URL = "https://results.eci.gov.in/ResultAcGenMay2026/"
# Page 1 has no number suffix; pages 2-12 append the page number.
PAGE_URLS = [f"{BASE_URL}statewiseS22{i}.htm" for i in range(1, 13)]

COLUMNS = [
    "Constituency", "Const. No.", "Leading Candidate", "Leading Party",
    "Trailing Candidate", "Trailing Party", "Margin", "Round", "Status",
]


def fetch_html(url: str) -> str:
    result = subprocess.run(
        [
            "curl", "-s", "-L",
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H", "Accept-Language: en-US,en;q=0.9",
            url,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl failed for {url}: {result.stderr}")
    return result.stdout


def cell_text(td) -> str:
    """Extract text from a <td>; for party-name cells, grab only the party name
    from the nested table, ignoring tooltip markup."""
    nested = td.find("table")
    if nested:
        first_td = nested.find("td")
        return first_td.get_text(strip=True) if first_td else ""
    return td.get_text(strip=True)


def parse_page(html: str) -> list[list]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        return []

    main_table = tables[0]
    tbody = main_table.find("tbody")
    if not tbody:
        return []

    rows = []
    for tr in tbody.children:
        if getattr(tr, "name", None) != "tr":
            continue
        cells = [cell_text(td) for td in tr.find_all(["td", "th"], recursive=False)]
        if not cells or all(c == "" for c in cells):
            continue
        # Pad/trim to 9 columns
        cells = cells[:9] + [""] * (9 - len(cells))
        rows.append(cells)

    return rows


def scrape_all() -> pd.DataFrame:
    all_rows = []
    for i, url in enumerate(PAGE_URLS, start=1):
        print(f"  Fetching page {i:2d}/12: {url}")
        try:
            html = fetch_html(url)
            rows = parse_page(html)
            print(f"             → {len(rows)} rows")
            all_rows.extend(rows)
        except Exception as exc:
            print(f"             → ERROR: {exc}", file=sys.stderr)

    return pd.DataFrame(all_rows, columns=COLUMNS)


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include="str").columns:
        df[col] = df[col].str.strip()

    for col in ("Margin", "Const. No."):
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ""), errors="coerce"
            )

    return df


def save_outputs(df: pd.DataFrame) -> None:
    csv_path = "tn_election_results_may2026.csv"
    xlsx_path = "tn_election_results_may2026.xlsx"

    df.to_csv(csv_path, index=False)
    print(f"\nCSV   saved → {csv_path}")

    try:
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        print(f"Excel saved → {xlsx_path}")
    except ImportError:
        print("openpyxl not installed — CSV saved but Excel skipped.")


def main() -> None:
    print(f"Scraping 12 pages from {BASE_URL}\n")
    df = scrape_all()
    df = clean_df(df)

    print(f"\nTotal rows collected: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst 5 rows:")
    print(df.head().to_string(index=False))

    save_outputs(df)


if __name__ == "__main__":
    main()
