#!/usr/bin/env python3
"""
Personal conference deadline calendar generator.

What it does
------------
1. Reads config.yml  -> the list of conferences YOU submitted to (by name/year).
2. Pulls the latest structured dates (abstract + paper submission, conference
   dates, location, link) from the community-maintained ccfddl/ccf-deadlines
   dataset. These are the dates that exist in a machine-readable feed.
3. Merges in overrides.yml -> the dates that NO public feed carries:
   rebuttal, notification, camera-ready. You fill these in by hand from each
   conference's call-for-papers (it takes ~1 minute per conference).
4. Writes deadlines.ics -> one calendar file you subscribe to once. Each event
   gets reminders (default: 14/7/3/1 days before).

Why this design
---------------
The submission/abstract dates change and are best pulled fresh daily (a GitHub
Action does this). The rebuttal/notification/camera-ready dates only live in
prose on conference websites, so they are manual — but once you type them they
persist in git. The .ics is the single source of truth your calendar reads.

Usage
-----
    python generate.py                 # writes deadlines.ics
    python generate.py --dry-run       # print events, write nothing
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

import requests
import yaml
from icalendar import Alarm, Calendar, Event

# --- Paths & constants -----------------------------------------------------

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yml"
OVERRIDES_PATH = ROOT / "overrides.yml"
OUTPUT_PATH = ROOT / "deadlines.ics"

# Subject-area folders in the ccfddl repo. AI is by far the richest for ML/NLP/CV.
SUBJECT_DIRS = ["AI", "DB", "DS", "SE", "NW", "SC", "CG", "HI", "MX", "CT"]
RAW_BASE = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference"
INDEX_API = "https://api.github.com/repos/ccfddl/ccf-deadlines/git/trees/main?recursive=1"

CAL_NAME = "My Conference Deadlines"
REMINDER_DAYS = [14, 7, 3, 1]  # reminders before deadline-type events

# Which event kinds get countdown reminders (the conference itself doesn't).
REMINDER_KINDS = {"abstract", "submission", "rebuttal", "notification", "camera_ready"}

# Human labels for each event kind.
KIND_LABELS = {
    "abstract": "Abstract deadline",
    "submission": "Paper deadline",
    "rebuttal": "Rebuttal",
    "notification": "Notification",
    "camera_ready": "Camera-ready",
    "conference": "Conference",
}


# --- Timezone & datetime parsing -------------------------------------------

def parse_offset(tz) -> dt.timezone:
    """ccfddl timezone string ('UTC-8', 'UTC+0', 'AoE') -> fixed UTC offset.

    Fixed offsets are sufficient for a single reminder timestamp; we are not
    modelling daylight saving for a one-off deadline instant.
    """
    if tz is None:
        return dt.timezone.utc
    s = str(tz).strip()
    if s.upper() == "AOE":  # Anywhere on Earth = UTC-12 (latest possible)
        return dt.timezone(dt.timedelta(hours=-12))
    m = re.match(r"UTC([+-]?\d{1,2})(?::?(\d{2}))?$", s, re.IGNORECASE)
    if m:
        hours = int(m.group(1))
        mins = int(m.group(2) or 0)
        sign = -1 if hours < 0 else 1
        return dt.timezone(dt.timedelta(hours=hours, minutes=sign * mins))
    return dt.timezone.utc


def parse_datetime(value, tz: dt.timezone):
    """Parse 'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD' -> aware dt."""
    if value is None:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    return None


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def parse_conf_dates(date_str, year):
    """Best-effort parse of a human conference date string into (start, end) dates.

    Handles forms like:
      'May 01-05, 2026'              -> (2026-05-01, 2026-05-05)
      'February 25 - March 4, 2025'  -> (2025-02-25, 2025-03-04)
      'July 6-12, 2026'              -> (2026-07-06, 2026-07-12)
    Returns (start_date, end_date) or (None, None) if it can't be parsed.
    """
    if not date_str:
        return None, None
    s = str(date_str).strip()
    yr_match = re.search(r"(20\d{2})", s)
    yr = int(yr_match.group(1)) if yr_match else int(year)

    # Find "Month Day" tokens.
    tokens = re.findall(r"([A-Za-z]+)\s+(\d{1,2})", s)
    months_seen = re.findall(r"([A-Za-z]+)", s)
    parsed = []
    for mon, day in tokens:
        key = mon[:3].lower()
        if key in MONTHS:
            parsed.append((MONTHS[key], int(day)))

    if not parsed:
        return None, None

    start_m, start_d = parsed[0]
    # End day: a trailing range number like '01-05' isn't caught by the regex
    # above (only first day gets a month). Look for 'start-end' patterns.
    range_match = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", s)

    if len(parsed) >= 2:
        end_m, end_d = parsed[1]
    elif range_match:
        end_m, end_d = start_m, int(range_match.group(2))
    else:
        end_m, end_d = start_m, start_d

    try:
        start = dt.date(yr, start_m, start_d)
        # If end month < start month, the range crosses a year boundary is rare;
        # assume same year unless end month earlier -> bump year.
        end_year = yr + 1 if end_m < start_m else yr
        end = dt.date(end_year, end_m, end_d)
        return start, end
    except ValueError:
        return None, None


# --- Data source -----------------------------------------------------------

def fetch_index(session) -> dict[str, str]:
    """Return {lowercase_filename_stem: full_path} for every conference .yml.

    Falls back to an empty dict if the GitHub tree API is rate-limited; in that
    case we resolve conferences by probing raw filenames instead.
    """
    try:
        r = session.get(INDEX_API, timeout=30,
                        headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 200 and "tree" in r.json():
            index = {}
            for t in r.json()["tree"]:
                p = t["path"]
                if p.startswith("conference/") and p.endswith(".yml"):
                    stem = p.split("/")[-1][:-4].lower()
                    index[stem] = p
            return index
    except Exception as e:  # noqa: BLE001
        print(f"  (index fetch failed: {e}; will probe raw files)", file=sys.stderr)
    return {}


def load_conference_yaml(session, path_or_stem: str):
    """Fetch and parse one conference .yml given a 'conference/AI/iclr.yml' path
    or a bare stem we probe across subject dirs."""
    if path_or_stem.startswith("conference/"):
        url = f"https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/{path_or_stem}"
        r = session.get(url, timeout=30)
        if r.status_code == 200:
            return yaml.safe_load(r.text)
        return None
    # probe
    for sub in SUBJECT_DIRS:
        url = f"{RAW_BASE}/{sub}/{path_or_stem}.yml"
        r = session.get(url, timeout=30)
        if r.status_code == 200:
            return yaml.safe_load(r.text)
    return None


def resolve_conference(session, index, name, file_hint=None):
    """Find the conference record for a given title/name.

    Resolution order:
      1. explicit `file:` hint in config (most reliable)
      2. dataset index lookup by filename stem == name.lower()
      3. raw-file probe by name.lower()
      4. scan: download candidates and match on the `title` field
    Returns the parsed YAML doc (a list with one conf dict) or None.
    """
    candidates = []
    if file_hint:
        candidates.append(file_hint)
    stem = re.sub(r"[^a-z0-9]", "", name.lower())
    if index:
        # try exact stem, then contains
        if stem in index:
            candidates.append(index[stem])
        for s, p in index.items():
            if s == stem or s == name.lower():
                candidates.append(p)
    candidates.append(stem)  # raw probe fallback

    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        doc = load_conference_yaml(session, c)
        if doc:
            return doc
    return None


# --- Event construction ----------------------------------------------------

def make_uid(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:16] + "@conf-cal"


def add_timed_event(cal, summary, when: dt.datetime, kind, link, location, desc):
    ev = Event()
    ev.add("uid", make_uid(summary, when.isoformat(), kind))
    ev.add("summary", summary)
    # 30-minute window ending at the deadline instant.
    ev.add("dtstart", when - dt.timedelta(minutes=30))
    ev.add("dtend", when)
    ev.add("dtstamp", dt.datetime.now(dt.timezone.utc))
    if location:
        ev.add("location", location)
    description = desc or ""
    if link:
        description = (description + f"\n{link}").strip()
    if description:
        ev.add("description", description)
    if link:
        ev.add("url", link)
    if kind in REMINDER_KINDS:
        for days in REMINDER_DAYS:
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", f"{summary} in {days} day(s)")
            alarm.add("trigger", dt.timedelta(days=-days))
            ev.add_component(alarm)
    cal.add_component(ev)


def add_allday_event(cal, summary, start: dt.date, end: dt.date, link, location, desc):
    ev = Event()
    ev.add("uid", make_uid(summary, start.isoformat(), "conference"))
    ev.add("summary", summary)
    ev.add("dtstart", start)
    # iCal all-day DTEND is exclusive -> add a day.
    ev.add("dtend", (end or start) + dt.timedelta(days=1))
    ev.add("dtstamp", dt.datetime.now(dt.timezone.utc))
    if location:
        ev.add("location", location)
    description = desc or ""
    if link:
        description = (description + f"\n{link}").strip()
    if description:
        ev.add("description", description)
    if link:
        ev.add("url", link)
    cal.add_component(ev)


def find_conf_year(doc, year):
    """From a parsed conference doc, return the conf dict matching `year`."""
    if not doc:
        return None
    record = doc[0] if isinstance(doc, list) else doc
    title = record.get("title", "?")
    for conf in record.get("confs", []):
        if int(conf.get("year", -1)) == int(year):
            return title, conf
    return title, None


# --- Main ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CONFIG_PATH.exists():
        print("config.yml not found.", file=sys.stderr)
        sys.exit(1)

    config = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    overrides = {}
    if OVERRIDES_PATH.exists():
        overrides = yaml.safe_load(OVERRIDES_PATH.read_text()) or {}

    reminder_days = config.get("reminder_days", REMINDER_DAYS)
    globals()["REMINDER_DAYS"] = reminder_days

    session = requests.Session()
    session.headers.update({"User-Agent": "conf-calendar/1.0"})
    gh_token = __import__("os").environ.get("GITHUB_TOKEN")
    if gh_token:
        session.headers.update({"Authorization": f"Bearer {gh_token}"})

    print("Building index of ccfddl dataset ...")
    index = fetch_index(session)
    print(f"  indexed {len(index)} conference files"
          if index else "  (no index; using raw probes)")

    cal = Calendar()
    cal.add("prodid", "-//conf-calendar//personal//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", config.get("calendar_name", CAL_NAME))
    cal.add("x-wr-timezone", "UTC")

    total_events = 0
    for entry in config.get("conferences", []):
        name = entry["name"]
        year = entry["year"]
        file_hint = entry.get("file")
        key = f"{name}{year}".lower().replace(" ", "")
        print(f"\n[{name} {year}]")

        doc = resolve_conference(session, index, name, file_hint)
        if not doc:
            print("  !! could not find in dataset — add a `file:` hint or rely on overrides")
        title, conf = (None, None)
        if doc:
            title, conf = find_conf_year(doc, year)
            if not conf:
                print(f"  !! found '{title}' but no entry for year {year}")

        link = (conf or {}).get("link") if conf else entry.get("link")
        place = (conf or {}).get("place") if conf else None
        label = entry.get("label", name)

        # --- automatic dates from the dataset ---
        if conf:
            tz = parse_offset(conf.get("timezone"))
            for tl in conf.get("timeline", []):
                comment = tl.get("comment", "")
                abs_dt = parse_datetime(tl.get("abstract_deadline"), tz)
                sub_dt = parse_datetime(tl.get("deadline"), tz)
                if abs_dt:
                    add_timed_event(cal, f"{label} — {KIND_LABELS['abstract']}",
                                    abs_dt, "abstract", link, place, comment)
                    total_events += 1
                    print(f"  + abstract   {abs_dt:%Y-%m-%d %H:%M %z}")
                if sub_dt:
                    add_timed_event(cal, f"{label} — {KIND_LABELS['submission']}",
                                    sub_dt, "submission", link, place, comment)
                    total_events += 1
                    print(f"  + submission {sub_dt:%Y-%m-%d %H:%M %z}")

            # conference dates (all-day span)
            start, end = parse_conf_dates(conf.get("date"), year)
            if start:
                add_allday_event(cal, f"{label} — {KIND_LABELS['conference']}",
                                 start, end, link, place, conf.get("date"))
                total_events += 1
                print(f"  + conference {start} → {end}  ({place})")

        # --- manual dates from overrides.yml (rebuttal/notif/camera-ready) ---
        ov = overrides.get(key) or overrides.get(f"{name} {year}") or {}
        ov_tz = parse_offset(ov.get("timezone", "AoE"))
        for kind in ("rebuttal", "notification", "camera_ready"):
            val = ov.get(kind)
            if not val:
                continue
            when = parse_datetime(val, ov_tz)
            if when:
                add_timed_event(cal, f"{label} — {KIND_LABELS[kind]}",
                                when, kind, link, place,
                                ov.get(f"{kind}_note", ""))
                total_events += 1
                print(f"  + {kind:12s}{when:%Y-%m-%d %H:%M %z}  (manual)")

    print(f"\nTotal events: {total_events}")
    if args.dry_run:
        print("(dry run — not writing file)")
        return

    OUTPUT_PATH.write_bytes(cal.to_ical())
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
