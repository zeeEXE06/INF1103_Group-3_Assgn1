# Resume & Job Matcher

An AI-powered resume and job matching web app, built with Django.

This repo is being built in four sprints:

1. **UI** ← you are here
2. **Database** (Data Manager: CSV/JSON persistence)
3. **Logic** (Logic Manager: scoring, ranking, business rules)
4. **AI** (AI Manager: mock/demo mode first)

Docker is added at the very end, once all four sprints work.

---

## Sprint 1 — UI (current state)

What's real in this sprint:

- Full Django project, runnable end-to-end
- Landing page → Employer workflow / Job Seeker workflow
- Employer: upload a job posting PDF + multiple candidate resume PDFs
  (drag-and-drop, validated: must be `.pdf`, non-empty, under 10MB)
- Job seeker: upload a resume PDF
- Job results page: filter jobs by work arrangement / location(s) /
  working hours / industry
- Both results pages: ranked cards with match score, matched/missing
  skills, compatibility checks, empty states
- 17 automated tests covering page loads, upload validation,
  successful-submission redirects, the debug/live data mode toggle,
  and the job filters

What's **not** real yet (by design — later sprints):

- Uploaded files are validated but not read, stored, or processed —
  see [Where uploaded data goes](#where-uploaded-data-goes)
- In `debug` mode results pages show sample data; in `live` mode they're
  empty — see [Debug vs live mode](#debug-vs-live-mode)
- No database persistence (Data Manager — Sprint 2)
- No scoring/ranking logic (Logic Manager — Sprint 3)
- No AI analysis, even mocked (AI Manager — Sprint 4)
- The `matcher/managers/` and `matcher/services/` modules exist as
  documented placeholders for those sprints

---

## Setup (VS Code)

### 1. Prerequisites

- Python 3.10+ installed
- VS Code with the **Python** extension (ms-python.python) installed

### 2. Open the project

Open the folder in VS Code (**File → Open Folder…**).

### 3. Create and activate a virtual environment

Open a terminal in VS Code (`` Ctrl+` `` / `` Cmd+` ``):

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

VS Code should prompt you to select this environment as the workspace
interpreter — click **Yes**. If it doesn't, use **Python: Select
Interpreter** from the Command Palette (`Ctrl+Shift+P`) and pick the
`.venv` one.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Create your `.env` file

Make your own copy of the settings template:

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
copy .env.example .env
```

This creates a new file called `.env` in the project folder. **Don't
copy anything into `settings.py`** — it reads `.env` automatically.

The values in it work as-is for Sprint 1, so you don't need to change
anything yet. See [Settings and secrets](#settings-and-secrets-env) to
understand how it works.

### 6. Run the app

```bash
python manage.py migrate   # sets up Django's own internal tables only
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser.

### 7. Run the tests

```bash
python manage.py test matcher
```

You should see `Ran 17 tests ... OK`.

---

## Settings and secrets (`.env`)

Three files work together. You only ever edit **`.env`**.

| File | What it is | In git? | Do you edit it? |
|---|---|---|---|
| `config/settings.py` | Defines every setting, with a safe default | ✅ Yes | ❌ No (only to add a new setting) |
| `.env.example` | Template listing every setting you can change | ✅ Yes | ❌ No (only to add a new setting) |
| `.env` | **Your own copy** with your values and secrets | ❌ Never | ✅ Yes |

### How it works

1. When the app starts, `settings.py` loads your `.env` file.
2. Each setting uses the value from `.env` if it's there, or falls
   back to its default if it isn't:

   ```python
   DATA_MODE = os.environ.get("DATA_MODE", "debug")
   #                          from .env ↑   default ↑
   ```

3. So no `.env` file still works — you just get all the defaults.

After changing `.env`, **restart `runserver`** for it to take effect.

### Available settings

| Setting | Default | What it does |
|---|---|---|
| `DATA_MODE` | `debug` | `debug` = sample data, `live` = real data ([details](#debug-vs-live-mode)) |
| `MAX_UPLOAD_SIZE_MB` | `10` | Largest PDF users can upload |
| `AI_MODE` | `mock` | `mock` = fake AI replies, `live` = real AI calls (Sprint 4) |
| `AI_API_KEY` | *(empty)* | Your AI API key (Sprint 4) |
| `DJANGO_DEBUG` | `True` | Shows detailed error pages — set `False` if deployed |
| `DJANGO_SECRET_KEY` | placeholder | Must be a real random value if deployed |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Web addresses allowed to serve the app |

### ⚠️ Secrets rule

> **Real secrets (like `AI_API_KEY`) go in `.env` only — never in
> `settings.py`.**

`settings.py` is pushed to GitHub, so anyone can read it. It only holds
safe placeholder defaults. `.env` is git-ignored and never leaves your
computer. A leaked API key can be used by anyone and charged to your
account.

### Adding a new setting

1. Add it to `settings.py` with a safe default:
   `MY_SETTING = os.environ.get("MY_SETTING", "default")`
2. Add it to `.env.example` so teammates know it exists.
3. Tell the team to copy the new line into their own `.env`.

---

## Debug vs live mode

One setting controls where the results pages get their data.

**How to switch:** change this line in your `.env` file (not
`settings.py`), then restart `runserver`.

```bash
DATA_MODE=debug   # or: DATA_MODE=live
```

| Mode | What the results pages show | Use it for |
|---|---|---|
| `debug` *(default)* | Fixed sample data from `matcher/dummy_data.py` | Working on the UI, demos |
| `live` | Real saved data — **empty until Sprint 2** | Testing real uploads |

- If `DATA_MODE` isn't set, the app uses `debug`.
- The setting lives in `config/settings.py`; the switch happens in
  `get_ranked_candidates()` / `get_ranked_jobs()` in `matcher/views.py`.
- This is **not** Django's `DJANGO_DEBUG`. That one only controls
  Django's error pages.

---

## Where uploaded data goes

> **Right now (Sprint 1), nothing is saved.** Uploads are checked, then
> thrown away when the request ends.

### What users submit

| Who | Field | Python type | Example |
|---|---|---|---|
| Employer | `job_file` | `UploadedFile` (PDF) | `job.pdf` |
| Employer | `candidate_files` | `list` of `UploadedFile` (PDFs) | `[c1.pdf, c2.pdf]` |
| Job seeker | `resume_file` | `UploadedFile` (PDF) | `resume.pdf` |

### Job results filters

These are **not** uploaded or saved. They're picked on the job results
page and sent in the URL (e.g. `/job-seeker/results/?locations=North`).
Leaving a filter empty means "show all".

| Filter | Python type | Example |
|---|---|---|
| `work_arrangement` | `list` of `str` | `["WFH", "Hybrid"]` |
| `locations` | `list` of `str` | `["North", "Central"]` |
| `working_hours` | `list` of `str` | `["Flexible"]` |
| `industry` | `str` (`""` = all) | `"Technology / IT"` |

All of these are checked in `matcher/managers/io_manager.py` and given
clear names (marked `# DATA:`) in `matcher/views.py`. The filtering
itself is done by `filter_jobs()` in `matcher/managers/logic_manager.py`.

### Where it lives

| Sprint | PDF files | Resume / job details |
|---|---|---|
| **1 (now)** | Memory only (Django uses a temp file if it's over 2.5MB), deleted after the request | Not saved |
| **2 (planned)** | `media/uploads/` | `data/candidates.json` and `data/jobs.json` |

`data/candidates.json` and `data/jobs.json` already exist with sample
records showing the planned format (lists of JSON objects):

```json
{
  "candidate_id": "C001",
  "filename": "candidate_01.pdf",
  "name": "John Tan",
  "skills": ["Python", "Django", "SQL", "REST API"],
  "location": "Central",
  "work_preferences": { "wfh": true, "flexible_hours": true }
}
```

`db.sqlite3` is **not** used for app data — only Django's own internal
tables. It is git-ignored, as are `media/uploads/*` and `.env`.

---

## Project structure

```text
INF1103_Group-3_Assgn1/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── config/                    # Django project settings/urls/wsgi
├── data/                      # Sample CSV/JSON (wired up in Sprint 2)
├── media/uploads/             # Uploaded files land here in later sprints
└── matcher/
    ├── views.py                # Thin views: validate input, render templates
    ├── urls.py
    ├── models.py                 # Empty — no ORM models (see file for why)
    ├── dummy_data.py              # Sprint 1 stand-in for real records
    ├── context_processors.py      # Adds ?v= to CSS/JS links so browsers don't use old cached files
    ├── tests.py
    ├── managers/                  # See each file for its sprint
    │   ├── io_manager.py          # Upload + filter forms and validation
    │   ├── data_manager.py
    │   ├── logic_manager.py       # Job filtering (scoring/ranking: Sprint 3)
    │   └── ai_manager.py
    ├── services/                  # Sprint 2-4 placeholders
    │   ├── pdf_service.py
    │   ├── ocr_service.py
    │   └── matching_service.py
    ├── templates/matcher/
    │   ├── base.html
    │   ├── landing.html
    │   ├── employer.html
    │   ├── job_seeker.html
    │   ├── employer_results.html
    │   └── job_results.html
    └── static/
        ├── css/style.css
        └── js/main.js
```

## Architecture notes carried through all sprints

- **I/O Manager** — handles all user input and output: the upload and
  filter forms, file validation, and (later) formatting results and
  user-facing error messages. The only place `print()`/terminal I/O is
  allowed.
- **AI Manager** — zero business logic. Prompt building, API calls,
  schema validation, retries only.
- **Logic Manager** — the domain brain. Filtering, scoring, the
  multi-condition match rule, ranking. Never talks to the AI API or the filesystem
  directly.
- **Data Manager** — the only place that reads/writes `data/*.json`
  (or `.csv`). Handles missing/corrupt files without crashing.

The I/O Manager (forms and validation) and the Logic Manager's
`filter_jobs()` are already in use. The rest are placeholders with a
docstring and TODOs for their sprint — see `matcher/managers/`.

---

## Sprint roadmap

### Sprint 2 — Database

Goal: replace `matcher/dummy_data.py` with real, persistent records.

- Implement `matcher/managers/data_manager.py`:
  `save_record()`, `load_records()`, `filter_records()`
- Read/write CSV or JSON under `data/` (`candidates.json`, `jobs.json`
  already seeded with sample records)
- Wire employer/job-seeker uploads to actually save what's submitted,
  and have results pages load from disk instead of hardcoded data
- Handle missing files, empty files, invalid JSON, and malformed CSV
  without crashing — log and continue
- Tests: save/load round-trip, corrupt-file handling, missing-file
  handling, duplicate records

### Sprint 3 — Logic

Goal: turn stored records into scored, ranked results.

- Implement `matcher/managers/logic_manager.py`:
  scoring weights (Skills 40% / Experience 25% / Education 10% /
  Location 10% / Work Arrangement 10% / Working Hours 5%, configurable)
- At least one multi-condition business rule (e.g. skills ≥ 70% AND
  experience match AND location match → "Strong Match")
- Ranking is produced here, not by the AI — Logic Manager is the only
  thing that decides final score and order
- Since the AI Manager doesn't exist yet, Logic Manager will consume
  rule-based "AI-shaped" fields as a stand-in until Sprint 4
- Tests: scoring calculation, the multi-condition rule, candidate
  ranking, job ranking

### Sprint 4 — AI

Goal: replace the rule-based stand-in with a real (or mocked) AI
Manager.

- Implement `matcher/managers/ai_manager.py`: prompt construction →
  AI API call → parse JSON → validate schema → retry on malformed
  response → return structured output to the Logic Manager
- Ships with `AI_MODE=mock` by default (see `.env.example`) so the
  whole app works with zero API key — deterministic, demo-friendly output
- `AI_MODE=live` path added behind the same interface once a provider
  is chosen; zero business logic lives in this module either way
- Errors (timeout, API failure, malformed JSON) are logged and never
  crash the request — one bad response shouldn't take down the batch
- Tests: schema validation, retry-on-malformed-response, mocked API
  calls (no real network calls in the test suite)

### Docker — last

Goal: containerize the finished app, once Sprints 1–4 all work
together.

- `Dockerfile` for the Django app (built on the final `requirements.txt`)
- `docker-compose.yml` if a separate service (e.g. a real database) is
  introduced later; not needed while storage stays CSV/JSON
- `.dockerignore` (`.venv/`, `.env`, `db.sqlite3`, `media/uploads/*`, etc.)
- Verify `docker build` + `docker run` serve the app the same as
  `runserver` does locally

Keeping `requirements.txt` accurate as each sprint adds dependencies
(e.g. a PDF-parsing library in Sprint 2, an AI SDK in Sprint 4) means
this step should need no dependency archaeology when it's time to
write the Dockerfile.