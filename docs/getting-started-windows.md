# Getting started (Windows)

Everything below happens in a regular Command Prompt (Windows key → type
`cmd` → Enter) unless it says otherwise. Do the steps in order; each one is
short. If a step fails, stop there and note the exact message.

## 0. What you need installed

| Tool | Check | If missing |
|---|---|---|
| Python 3.11+ | `python --version` | python.org → Downloads → tick "Add python.exe to PATH" during install |
| Node.js LTS | `node --version` | nodejs.org → green LTS button → accept defaults |
| Git | `git --version` | git-scm.com → accept defaults |

Close and reopen Command Prompt after any install so it picks up the new PATH.

## 1. Get the code onto your machine

Unzip `cds-portfolio.zip` somewhere sensible, for example `C:\Projects\cds-portfolio`.
Then open a Command Prompt **in that folder** (in File Explorer, click the
address bar, type `cmd`, press Enter). Every command below assumes you are
in that folder.

## 2. Python packages

```
pip install -r requirements.txt
```

This installs dbt and the database driver. Takes a minute or two the first time.

Check it worked: `python pipeline\run_dbt.py --version` should print `Core: installed: 1.x`.

## 3. Your database credential

1. In the Neon dashboard click **Connect**, turn **off** "Connection pooling",
   click **Copy snippet**.
2. In the project folder, copy `.env.example` to `.env`:
   ```
   copy .env.example .env
   ```
3. Open `.env` in Notepad (`notepad .env`), replace the placeholder line with
   your real connection string, save.

`.env` is listed in `.gitignore`, so it never gets committed. This is the
**only** file on your machine that holds the password.

## 4. Run the pipeline

Three commands, in order. Each prints what it did.

```
python projects\education_attendance\generate.py
python pipeline\load_raw.py education_attendance
python pipeline\run_dbt.py build
```

- The first writes four CSVs to `data\raw\education_attendance\` (≈427,000 rows).
- The second loads them into Neon as `raw_education_attendance.*` tables.
- The third runs dbt: 9 models and 36 tests. You want the last line to say
  `PASS=36 WARN=0 ERROR=0`.

Go look in Neon → SQL Editor and run
`select * from marts.school_monthly_attendance limit 20;` — those are your tables.

## 5. Dashboards

One-time install of Evidence (a few minutes, lots of output, that's normal):

```
cd evidence
npm install
cd ..
```

Then pull the data and start the local preview:

```
python pipeline\run_evidence.py sources
python pipeline\run_evidence.py dev
```

A browser tab opens at http://localhost:3000 with the portfolio. Edit any
file in `evidence\pages\` and the page reloads. Press `Ctrl+C` in the
Command Prompt to stop it.

## 6. Publish (GitHub Pages)

1. On github.com create a new **public** repository named `cds-portfolio`
   (no README, no .gitignore; the folder already has those).
2. In the project folder:
   ```
   git init
   git add .
   git commit -m "Portfolio: education attendance project"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/cds-portfolio.git
   git push -u origin main
   ```
3. On GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
   Name `DATABASE_URL`, value = your Neon connection string. Save.
4. **Settings → Pages → Source**: choose **GitHub Actions**.
5. **Actions** tab → `pipeline` → **Run workflow**. About 4–6 minutes later the
   site is live at `https://YOUR-USERNAME.github.io/cds-portfolio/`.
6. Edit `evidence\pages\index.md` and replace `YOUR-GITHUB-USERNAME` with your
   real username, commit, push. The site rebuilds itself.

From then on: every push to `main` rebuilds the site, and it also rebuilds
every Monday morning on its own.

## 7. Linking from creativedatasolutions.tech

Add a "Work" or "Portfolio" link in the site nav pointing at the Pages URL.
If you'd rather it live at `portfolio.creativedatasolutions.tech`, see
`docs/custom-domain.md`.

## Day-to-day commands

| I want to… | Run |
|---|---|
| Re-run everything after changing a model | `python pipeline\run_dbt.py build` |
| Run only the tests | `python pipeline\run_dbt.py test` |
| See the lineage graph and docs | `python pipeline\run_dbt.py docs generate` then `python pipeline\run_dbt.py docs serve` |
| Refresh dashboard data after a dbt change | `python pipeline\run_evidence.py sources` |
| Preview dashboards | `python pipeline\run_evidence.py dev` |
| Publish | `git add . && git commit -m "..." && git push` |
