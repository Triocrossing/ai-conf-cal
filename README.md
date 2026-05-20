# 📅 Personal Conference Deadline Calendar

> An auto-updating calendar that tracks **only the conferences you submitted to**,
> including the **rebuttal / notification / camera-ready** dates that no public
> tool carries.

---

## What this project is

```
config.yml (which conferences you submitted to) ─┐
                                                  ├─► generate.py ─► deadlines.ics (subscribe once, updates forever)
overrides.yml (manual / agent-filled dates) ─────┘   ▲
                                                      │
                       ccfddl/ccf-deadlines public dataset (refreshed daily)
```

- **`config.yml`** — your submission list (name + year). The only file you normally edit.
- **`overrides.yml`** — rebuttal / notification / camera-ready dates. These have **no
  public data source** — they only exist as prose on each conference's CFP page. You
  used to fill these by hand; now a daily agent can do it for you.
- **`generate.py`** — merges the two with the live dataset, writes `deadlines.ics`.
- **`.github/workflows/update.yml`** — fallback: a GitHub Action runs `generate.py`
  daily (auto data only — does not scrape rebuttal/notification/camera-ready).

---

## Why a Claude Code Routine (this is the "do it for me every day" part)

`generate.py` can only pull fields the dataset **already has** (abstract / paper
deadlines, conference dates, location). But rebuttal / notification / camera-ready
only live as prose on each conference's website — **there is no machine-readable
source**. A plain script can't reliably parse these — but an agent with judgment
can read the page and pull the dates out.

A **Claude Code Routine** does exactly this: it runs on Anthropic's cloud on a
schedule, so it keeps working even when your laptop is off. Paste the contents of
`ROUTINE_PROMPT.md` into a daily Routine and the agent will, every day:

1. Read `config.yml` to see which conferences you care about.
2. Visit each conference's official CFP page and look for the three missing dates.
3. Update `overrides.yml` accordingly.
4. Run `generate.py` to regenerate `deadlines.ics`.
5. Commit and push.

Your subscribed calendar is then **truly hands-off** — even the "dates buried in
prose" get filled in.

---

## 5-minute setup (for humans)

### A. Deploy to GitHub
1. Create a new GitHub repo and push all files in this folder to it.
2. In the repo, go to **Settings → Actions → General → Workflow permissions** and
   select **Read and write permissions** (so the Action can commit the regenerated
   `.ics` back to `main`).

### B. Set up the daily Routine (the core; requires Pro plan or higher)
1. In Claude Code, connect this GitHub repo.
2. Create a new **Routine**:
   - Frequency: **daily**
   - Repo: this repo
   - Prompt: paste the entire contents of `ROUTINE_PROMPT.md`
3. Save. It will now run every day, regardless of whether your computer is on.

> Plan limits: Pro = 5 routine runs/day, Max = 15. One run per day is plenty.

### C. Subscribe to the calendar (one-time)
Use the **raw** URL of the generated file:
```
https://raw.githubusercontent.com/<your-username>/<repo-name>/main/deadlines.ics
```
- **Google Calendar**: Other calendars → ＋ → From URL → paste.
- **Apple Calendar**: File → New Calendar Subscription → paste.
- **Outlook**: Add calendar → Subscribe from web → paste.

> Make sure you **subscribe** by URL — don't **import** the file, or it won't
> auto-update.

---

## Add a conference

Edit `config.yml`:
```yaml
conferences:
  - name: CVPR
    year: 2026
    label: CVPR 2026
```
`name` is matched case-insensitively against the dataset. A few conferences have
unusual filenames — e.g. **NeurIPS** is stored as `nips.yml`. If auto-resolution
fails, add a `file:` hint:
```yaml
  - name: NeurIPS
    year: 2026
    file: conference/AI/nips.yml
```

## Run locally

```bash
pip install -r requirements.txt
python generate.py            # writes deadlines.ics
python generate.py --dry-run  # preview only, no file written
```

---

## Honest limitations
- **Reminders** fire 14 / 7 / 3 / 1 days before each deadline (configurable via
  `reminder_days` in `config.yml`). They're attached only to deadline-type events,
  not to the multi-day conference event itself.
- **Time zones** use fixed UTC offsets (including AoE = UTC-12). That's enough for
  a one-off deadline instant; we don't model daylight saving.
- **Data may lag**: early in the submission cycle, some conferences only have
  placeholder dates. The daily refresh picks up corrections automatically.
- **The dataset is community-maintained.** As deadlines approach, always
  cross-check against the conference's official website.

Dataset: [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines) — MIT license.
