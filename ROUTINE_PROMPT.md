# ROUTINE_PROMPT.md

Copy everything between the two `===` lines into the prompt box of a Claude Code
Routine. Recommended frequency: once per day.

================================================================================

You are an agent maintaining a "personal conference deadline calendar" repo. On
each scheduled run, do the following:

## Steps

1. Read `config.yml` at the repo root to get the list of conferences I submitted
   to (each entry has `name` + `year`).

2. For **every** conference in that list, visit its official website (prefer the
   call-for-papers / important-dates page) and look for these three dates. They
   are not in any public dataset — they only exist as prose on the official page:
   - **rebuttal** (author response window — usually a range; use the start date)
   - **notification** (acceptance notification date)
   - **camera_ready** (camera-ready / final-version deadline)

   You can find the conference URL in the `link` field of `config.yml`, or in the
   dataset entry for that conference. If a date has not been announced yet, skip
   it — do **not** invent one.

3. Write / update the dates in `overrides.yml`. The format is strict (the key is
   `<name><year>` in lowercase with no spaces; use `"YYYY-MM-DD HH:MM:SS"`, and
   if only the day is known, use `23:59:00`):

   ```yaml
   neurips2026:
     timezone: AoE
     rebuttal: "2026-07-29 23:59:00"
     notification: "2026-09-18 23:59:00"
     camera_ready: "2026-10-22 23:59:00"
   ```

   - Only update the fields you found; preserve all other existing content.
   - If a value disagrees with what's already in the file, trust the **official
     website** and update.

4. Run `python generate.py` to regenerate `deadlines.ics`.
   (Run `pip install -r requirements.txt` first if needed.)

5. If `overrides.yml` or `deadlines.ics` changed, commit and push. Write a clear
   message like `update: NeurIPS 2026 notification + camera-ready dates`. If
   nothing changed, do not commit.

## Principles

- **Never invent dates.** If you can't find one, leave it out. A missing field
  is far better than a wrong one.
- Every date must come from the conference's **official** page. Third-party
  aggregators can be used to find the official URL, but the official page is the
  source of truth.
- **Briefly summarize the run for me**: per conference, which dates you found
  or updated, and which are still unannounced.
- Don't modify `config.yml` (I maintain that). Don't change the logic of
  `generate.py`.

================================================================================
