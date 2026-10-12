# Resume & Job Matcher

A Django web app that matches resumes and jobs using Google Gemini.

- **Job seekers** upload a resume and get a ranked list of suitable job
  titles, each linking to the matching openings on Jobstreet Singapore.
- **Employers** upload one job posting and several resumes and get the
  candidates scored and ranked against the job.

---

## Features

**Job seeker**

- Upload a resume PDF. Gemini reads its education, experience and skills.
- Get up to `MAX_JOBS` suggested job titles, best match first, each with a
  match %, the skills that match, a short reason and a Jobstreet link.
- Filter the results by work arrangement, location, working hours and
  industry. Filtering uses the saved results, so it never calls the AI again.

**Employer**

- Upload one job posting PDF and up to `MAX_CANDIDATES` resume PDFs.
- Gemini compares every resume with the job in one request.
- Each candidate gets a score, matched and missing skills, a ✓/✗ for each
  requirement and a **Strong Match** badge when they qualify.

**Both**

- Drag-and-drop uploads, checked to be non-empty PDFs under the size limit.
- `AI_MODE=mock` runs the whole app with fixed sample replies and no API key.
- If Gemini is busy, the app retries and then tries a backup model. If the
  AI still fails, the user sees a clear message instead of an error page.

---

## How it works

```text
            views.py  (pages, messages)
                │
                ▼
     services/matching_service.py   (the three AI flows)
        │            │            │
        ▼            ▼            ▼
   ai_manager   data_manager   logic_manager        io_manager
   (Gemini)     (data/*.json)  (score, rank,        (forms and
                               filter)              upload checks)
```

| Module | Job |
|---|---|
| `managers/io_manager.py` | Upload and filter forms, PDF checks |
| `managers/ai_manager.py` | Sends prompts and PDFs to Gemini, retries, reads the JSON reply. No business logic. |
| `managers/data_manager.py` | The only code that reads and writes `data/*.json`. Missing or broken files never crash the app. |
| `managers/logic_manager.py` | Scores and ranks candidates, ranks and filters jobs. Never calls the AI or reads files. |
| `services/matching_service.py` | `read_resume()`, `match_jobs_to_resume()`, `match_candidates_to_job()` |

### Candidate scoring (employer)

The AI only reports what matches. The Logic Manager decides the score:

| Part | Weight |
|---|---|
| Skills (share of the job's skills the candidate has) | 40 |
| Experience | 25 |
| Education | 10 |
| Location | 10 |
| Work arrangement | 10 |
| Working hours | 5 |

**Strong Match** = skills ≥ 70% **and** experience matches **and**
location matches.

---

## Setup (VS Code)

### 1. Prerequisites

- Python 3.10+
- VS Code with the **Python** extension (ms-python.python)

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

If VS Code asks whether to use this environment, click **Yes**. Otherwise
run **Python: Select Interpreter** (`Ctrl+Shift+P`) and pick `.venv`.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

Run this again after every `git pull` in case packages changed. If the app
fails with `ModuleNotFoundError`, this is the fix.

### 5. Create your `.env` file

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
copy .env.example .env
```

The defaults run the app in mock mode with sample results. To use the real
AI, see [Mock vs live](#mock-vs-live).

### 6. Run the app

```bash
python manage.py migrate   # sets up Django's own internal tables only
python manage.py runserver
```

Open **http://127.0.0.1:8000/**.

### 7. Run the tests

```bash
python manage.py test matcher
```

You should see `Ran 51 tests ... OK`. The tests never call the real AI.

---

## Mock vs live

Two settings in `.env` control this. Restart `runserver` after changing them.

| Setting | `mock` / `debug` (default) | `live` |
|---|---|---|
| `AI_MODE` | Fixed sample AI replies, no key needed | Real Gemini calls, needs `AI_API_KEY` |
| `DATA_MODE` | Results pages show sample results from `dummy_data.py` | Results pages show the visitor's own saved results |

For the full app, set both to `live` and add a free Gemini key from
[Google AI Studio](https://aistudio.google.com/apikey):

```bash
AI_MODE=live
DATA_MODE=live
AI_API_KEY=your-key-here
```

On the free tier Gemini allows only a few requests per minute and a daily
limit per model; check your usage at https://aistudio.google.com/usage.
Free-tier requests may also be used by Google to improve its models, so
avoid uploading real people's resumes you don't have permission to share.

---

## Settings and secrets (`.env`)

| File | What it is | In git? | Do you edit it? |
|---|---|---|---|
| `config/settings.py` | Every setting, with a safe default | ✅ Yes | Only to add a new setting |
| `.env.example` | Template listing every setting | ✅ Yes | Only to add a new setting |
| `.env` | **Your own copy** with your values and secrets | ❌ Never | ✅ Yes |

`settings.py` loads `.env` when the app starts. A setting missing from
`.env` falls back to its default:

```python
DATA_MODE = os.environ.get("DATA_MODE", "debug")
#                          from .env ↑   default ↑
```

### Available settings

| Setting | Default | What it does |
|---|---|---|
| `AI_MODE` | `mock` | `mock` = sample AI replies, `live` = real Gemini calls |
| `DATA_MODE` | `debug` | `debug` = sample results, `live` = the visitor's saved results |
| `AI_API_KEY` | *(empty)* | Your Gemini API key (`GEMINI_API_KEY` also works) |
| `AI_MODEL` | `gemini-3.8-flash` | Gemini model to use |
| `AI_FALLBACK_MODELS` | `gemini-3.5-flash` | Backup models (comma-separated) tried if `AI_MODEL` is busy |
| `MAX_UPLOAD_SIZE_MB` | `10` | Largest PDF users can upload |
| `MAX_CANDIDATES` | `10` | Most resumes an employer can compare at once |
| `MAX_JOBS` | `15` | Most jobs suggested for one resume |
| `DJANGO_DEBUG` | `True` | Detailed error pages; set `False` if deployed |
| `DJANGO_SECRET_KEY` | placeholder | Must be a real random value if deployed |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Web addresses allowed to serve the app |

> **Real secrets (like `AI_API_KEY`) go in `.env` only — never in
> `settings.py`.** `settings.py` is on GitHub for anyone to read; `.env`
> is git-ignored and never leaves your computer.

To add a setting: add it to `settings.py` with a safe default, add it to
`.env.example`, and tell the team to copy it into their `.env`.

---

## Where data goes

Uploaded PDFs are sent to Gemini and never saved to disk. What Gemini
returns is saved by the Data Manager as JSON in `data/`:

| File | Saved when | Contains |
|---|---|---|
| `data/resumes.json` | A job seeker uploads a resume | Education, experience and skills |
| `data/job_matches.json` | Right after that | The suggested jobs for that resume |
| `data/candidate_matches.json` | An employer uploads | The job posting details and scored candidates |

Each visitor's session (a signed cookie) remembers which saved result is
theirs, so the results pages only show their own results. These files hold
people's personal details, so they are listed in `.gitignore` and should be
kept out of git.

`db.sqlite3` is only used by Django itself, not for app data.

---

## Project structure

```text
INF1103_Group-3_Assgn1/
├── manage.py
├── requirements.txt
├── .env.example
├── config/                         # Django settings, urls, wsgi
├── data/                           # Saved results (JSON)
└── matcher/
    ├── views.py                    # Pages: handle the request, show messages
    ├── urls.py
    ├── dummy_data.py               # Sample results for DATA_MODE=debug
    ├── context_processors.py       # Adds ?v= to CSS/JS links so browsers load new versions
    ├── models.py                   # Empty: no database models
    ├── tests.py
    ├── managers/
    │   ├── io_manager.py           # Forms and upload checks
    │   ├── ai_manager.py           # Google Gemini calls
    │   ├── data_manager.py         # JSON save/load
    │   └── logic_manager.py        # Scoring, ranking, filtering
    ├── services/
    │   └── matching_service.py     # The three AI flows
    ├── templates/matcher/          # landing, employer, job_seeker and the two results pages
    └── static/
        ├── css/style.css
        └── js/main.js              # Drag-and-drop uploads, loading spinner
```
