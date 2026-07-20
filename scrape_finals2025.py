#!/usr/bin/env python3
"""
Scrape Swim England Diving National Skills Finals 2026 dive sheets (E/D brackets)
from diverecorder.co.uk and write a tidy CSV.

Run locally where you have network access to diverecorder.co.uk:

    python3 scrape_skills.py

Output: dives.csv  (hand this back to Claude for analysis)

Requires only the standard library + `requests`:
    pip install requests
"""

import csv
import os
import re
import sys
import time
import html
import urllib.request

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
BASE = "https://diverecorder.co.uk/meetexplorer"
MREF = 1326

# E/D brackets only, both genders. eref -> (bracket, gender)
EVENTS = {
    1: ("E", "F"),
    3: ("D2", "F"),
    2: ("D1", "F"),
    9: ("E", "M"),
    11: ("D2", "M"),
    10: ("D1", "M"),
}

CACHE_DIR = "cache_finals2025"          # raw HTML cached here so re-runs don't re-hit the server
OUT_CSV = "dives_finals2025.csv"
DELAY = 0.5                  # seconds between network requests (be polite)

HEADER = ["meet", "event", "bracket", "gender", "dref", "diver", "club",
          "round", "dive_code", "position", "M", "DD", "j1", "j2", "j3", "total"]


# ---------------------------------------------------------------------------
# fetching (with on-disk cache)
# ---------------------------------------------------------------------------
def fetch(url, cache_key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, cache_key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research scraper)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    time.sleep(DELAY)
    return text


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def frac(s):
    """'7½' -> 7.5, '½' -> 0.5, '7' -> 7.0"""
    s = s.strip().replace("&frac12;", "½").replace("½", ".5")
    if s == ".5":
        return 0.5
    return float(s)


def get_diver_and_club(page_text):
    """The sheet header row is: <strong>Name</strong>, Club  (in the HTML table)."""
    # strip tags to plain text, then find "Name, Club" just after the bracket/date line
    txt = re.sub(r"<[^>]+>", " ", page_text)
    txt = html.unescape(txt)
    # diver name is inside <strong>...</strong> on the page
    m = re.search(r"<strong>\s*(.+?)\s*</strong>\s*,\s*([^<\n]+)", page_text)
    if m:
        return html.unescape(m.group(1)).strip(), html.unescape(m.group(2)).strip()
    return "?", "?"


def parse_sheet(page_text, meet, eref, bracket, gender, dref):
    diver, club = get_diver_and_club(page_text)

    # Extract table rows. The dive table is HTML <tr><td>...</td></tr>.
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page_text, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
        cells = [c for c in cells if c != ""]
        if len(cells) < 9:
            continue
        if not re.match(r"^\d+$", cells[0]):        # first cell must be a round number
            continue
        rnd = int(cells[0])
        code, pos, M, DD = cells[1], cells[2], cells[3], cells[4]
        if not re.match(r"^\d+$", M):                # skip footer/DD-total rows
            continue
        try:
            j1, j2, j3 = frac(cells[5]), frac(cells[6]), frac(cells[7])
            total = frac(cells[8])
        except ValueError:
            continue
        rows.append([meet, eref, bracket, gender, dref, diver, club,
                     rnd, code, pos, int(M), float(DD), j1, j2, j3, total])
    return rows


def get_diver_links(event_html):
    """From a selectsheet page, return list of dref ids (ints)."""
    drefs = re.findall(r"showsheet\.php\?[^\"']*dref=(\d+)", event_html)
    # dedupe preserving order
    seen, out = set(), []
    for d in drefs:
        if d not in seen:
            seen.add(d)
            out.append(int(d))
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    all_rows = []
    for eref, (bracket, gender) in EVENTS.items():
        list_url = f"{BASE}/selectsheet.php?mref={MREF}&eref={eref}"
        try:
            event_html = fetch(list_url, f"event_{eref}.html")
        except Exception as e:
            print(f"[warn] could not fetch event {eref} ({bracket} {gender}): {e}", file=sys.stderr)
            continue
        drefs = get_diver_links(event_html)
        print(f"{bracket} {gender} (eref {eref}): {len(drefs)} divers")
        for dref in drefs:
            sheet_url = f"{BASE}/showsheet.php?mref={MREF}&eref={eref}&dref={dref}"
            try:
                sheet_html = fetch(sheet_url, f"sheet_{eref}_{dref}.html")
            except Exception as e:
                print(f"  [warn] dref {dref}: {e}", file=sys.stderr)
                continue
            rows = parse_sheet(sheet_html, "meet6", str(eref), bracket, gender, dref)
            if not rows:
                print(f"  [warn] dref {dref}: no dive rows parsed", file=sys.stderr)
            all_rows.extend(rows)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(all_rows)

    divers = len({(r[1], r[4]) for r in all_rows})
    print(f"\nDone. {len(all_rows)} dive rows from {divers} divers -> {OUT_CSV}")
    print("Send dives.csv back to Claude.")


if __name__ == "__main__":
    main()
