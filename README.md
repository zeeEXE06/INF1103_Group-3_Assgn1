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
- **Scoring profiles:** choose how the score is weighted, either one of three
  built-in profiles or a **Custom** one with your own weights, which is saved
  so you can pick it next time. The results page shows which profile was
  used. Scoring the same files again with another profile doesn't call the
  AI again.

**Both**

- Drag-and-drop uploads, checked to be non-empty PDFs under the size limit.
- **Everything depends on the AI.** There is no sample data or offline mode:
  if Gemini can't process an upload, the user sees an error and can't reach
  any results.
- If Gemini is busy, the app retries and then tries a backup model. It gives
  up after `AI_TIMEOUT_SECONDS` instead of hanging. Replies that aren't valid
  JSON or have the wrong structure are rejected and asked for again.
- **Failures never crash a page.** Every failure shows a clear message (see
  [Errors and what the user sees](#errors-and-what-the-user-sees)).
- **Same input, same output.** Gemini runs at temperature 0, and every
  uploaded PDF is fingerprinted: uploading the same file (or the same set of
  files) again returns the saved result instead of asking the AI again.

---

## How it works

```text
        views.py  (class-based views: pages, messages)
            │                         │
            ▼                         ▼
   MatchingService               io_manager
   (the three AI flows)          (UploadValidator, JobFilterForm,
                                  ScoringProfileForm)
     │          │          │
     ▼          ▼          ▼
 AIManager  JsonRepository  CandidateScorer, rankers, JobFilter
 (Gemini)   (data/*.json)   (logic_manager)
```

Every manager is a set of classes built on the abstract contracts in
`matcher/contracts/`, and they pass domain objects (`Resume`, `Candidate`,
`Shortlist`, ...) from `matcher/domain/` between them. `MatchingService` is
given its managers when it is created, so the tests can give it a
`FakeProvider` and an `InMemoryRepository` instead. The full class diagram is
in [docs/class-diagram.md](docs/class-diagram.md).

| Module | Job |
|---|---|
| `managers/io_manager.py` | `UploadValidator` checks uploads are real, readable PDFs (with `pypdf`) under the limits; `JobFilterForm` reads the results-page filters and gives the AI its allowed values; `ScoringProfileForm` reads the employer's picked or custom scoring profile |
| `managers/ai_manager.py` | `AIManager` runs any AI task through an AI provider, checks the JSON reply and asks again if it's in the wrong format. No business logic. |
| `managers/ai_providers.py` | `GeminiProvider`: sends the prompts and PDFs to Gemini, retries, falls back to backup models |
| `managers/ai_tasks.py` | `ResumeExtractionTask`, `JobSuggestionTask`, `CandidateComparisonTask`: each builds its prompt and checks its reply's structure |
| `managers/data_manager.py` | `JsonRepository`: the only code that reads and writes `data/*.json`. Saving, loading, the `find()`/`filter()` queries and a check of every file at startup. Missing or broken files never crash the app. |
| `managers/logic_manager.py` | `CandidateScorer` (made of six score components, weighted by a `ScoringProfile`) and `StrongMatchRule` score candidates; `CandidateRanker`, `JobRanker` and `JobFilter` order and filter results. Never calls the AI or reads files. |
| `services/matching_service.py` | `MatchingService`: `read_resume()`, `match_jobs_to_resume()`, `match_candidates_to_job()`, the scoring profiles, plus the lookups the results pages use |
| `views.py` | One class-based view per page; the two upload pages share an `UploadView` base class |

### Candidate scoring (employer)

The AI only reports what matches. The Logic Manager decides the score,
using the scoring profile the employer chose:

| Part | Balanced | Skills first | Experience first |
|---|---|---|---|
| Skills (share of the job's skills the candidate has) | 40 | 60 | 30 |
| Experience | 25 | 15 | 40 |
| Education | 10 | 5 | 10 |
| Location | 10 | 10 | 10 |
| Work arrangement | 10 | 5 | 5 |
| Working hours | 5 | 5 | 5 |
| Strong Match skills share | 70% | 80% | 60% |

**Strong Match** = skills ≥ the profile's share **and** experience matches
**and** location matches.

A **Custom** profile needs a name, whole-number weights that add up to 100
and a Strong Match share from 0 to 100%. Anything else is rejected with a
message before the AI is called. Balanced is the default, and results saved
before profiles existed count as Balanced.

To add a new part to the score, write a `ScoreComponent` subclass and add it
to `CandidateScorer.COMPONENT_TYPES`; the scorer itself doesn't change
(`test_a_new_score_component_needs_no_change_to_the_scorer`).

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

Then add your Gemini API key to `.env` — the app needs it for every upload.
See [Gemini API key](#gemini-api-key).

### 6. Run the app

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/**.

### 7. Run the tests

```bash
python run_tests.py
```

You should see `Ran ... tests ... OK`. Every test is a plain function in a
`matcher/tests/test_*.py` file; none of them call the real AI or touch
`data/`. A failing test prints its name and the line that failed.

| File | What it tests |
|---|---|
| `test_app.py` | Every page and the AI flows, from upload to results |
| `test_failures.py` | What the user sees for each kind of failure (the error matrix below) |
| `test_contracts.py` | The abstract classes and interface |
| `test_domain.py` | Domain classes: encapsulation, saving and loading, `ScoringProfile` checks |
| `test_ai_providers.py`, `test_ai_tasks.py`, `test_ai_manager.py` | AI Manager: Gemini fallbacks and timeouts, prompts, reply checks |
| `test_data.py` | Data Manager: JSON files, broken files, both repositories |
| `test_logic.py` | Logic Manager: scoring, profiles, ranking, filters |
| `test_io.py` | IO Manager: upload checks, filters, the scoring profile form |
| `test_matching_service.py` | `MatchingService`, broken saved records, and that any provider or repository gives the same results |

---

## Run with Docker

Docker runs the app the same way on any computer, with no Python setup.
You need [Docker Desktop](https://www.docker.com/products/docker-desktop/)
running, and a `.env` file with your Gemini API key (see step 5 above).

```bash
docker compose up --build        # build and start, then open http://localhost:8000
docker compose run --rm web python run_tests.py   # run the tests in the container
docker compose down              # stop it (or press Ctrl+C)
```

How it is set up:

- **`Dockerfile`** builds an image with Python 3.13, the packages in
  `requirements.txt` and the code, and starts `runserver` on port 8000.
- **`docker-compose.yml`** passes in your `.env` at run time, so the API key
  is never built into the image, and shares your `data/` folder with the
  container, so saved results survive restarts and rebuilds.
- **`.dockerignore`** keeps `.env`, `data/`, `.venv/` and `.git/` out of the image.

Run `docker compose up --build` again after pulling code changes.

---

## Gemini API key

Get a free key from [Google AI Studio](https://aistudio.google.com/apikey)
and put it in `.env`, then restart `runserver`:

```bash
AI_API_KEY=your-key-here
```

Without a working key every upload fails with "The AI could not process
your upload", and the results pages stay empty.

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
MAX_JOBS = int(os.environ.get("MAX_JOBS", "15"))
#                             from .env ↑  default ↑
```

### Available settings

| Setting | Default | What it does |
|---|---|---|
| `AI_API_KEY` | *(empty)* | **Required.** Your Gemini API key (`GEMINI_API_KEY` also works) |
| `AI_MODEL` | `gemini-3.8-flash` | Gemini model to use |
| `AI_FALLBACK_MODELS` | `gemini-3.5-flash` | Backup models (comma-separated) tried if `AI_MODEL` is busy |
| `AI_TIMEOUT_SECONDS` | `60` | Longest wait for one Gemini reply (the SDK tries up to 3 times) |
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

## Errors and what the user sees

Every failure is caught where it happens and turned into a message; none of
them crash a page or leave half-saved results. Each row has a test, most of
them in `matcher/tests/test_failures.py`.

| Failure | Caught by | What the user sees |
|---|---|---|
| Not a PDF, empty, over `MAX_UPLOAD_SIZE_MB`, corrupt or password-protected | `UploadValidator` (IO Manager) | The upload form again, with a message under the file; the AI isn't called |
| More than `MAX_CANDIDATES` resumes | `UploadValidator` | "Upload at most N resumes at a time." |
| Custom profile with bad weights | `ScoringProfileForm` / `ScoringProfile` | The form again with e.g. "The weights must add up to 100, not 150."; the AI isn't called |
| No API key, bad key, network down, every model busy | `GeminiProvider` raises `AIProviderError` | "The AI could not process your upload right now. Please try again later." |
| No reply within `AI_TIMEOUT_SECONDS` | `GeminiProvider` raises `AIProviderError` | Same message |
| Reply isn't JSON or has the wrong structure | `AIManager` asks once more, then gives up | Same message if the second reply is also bad |
| AI skips one of the resumes | `MatchingService` | That candidate is shown last as "Could not read this resume." |
| Resume read but the job search fails | `MatchingService` raises `MatchingError` | "Resume received, but the job search failed." The resume is kept. |
| A data file isn't valid JSON | `JsonRepository` | Nothing; the file is treated as empty and kept as `<name>.broken.json` |
| A saved record is broken (e.g. edited by hand) | `MatchingService._from_saved()` | The results page shows "No candidates yet" / "No matches yet"; an upload asks the AI again |
| An unknown address | Django, `404.html` | "Page not found" with a link home |
| Any error nobody planned for (with `DJANGO_DEBUG=False`) | Django, `500.html` | "Something went wrong" with no error details |

Problems are also written to the terminal log (e.g. a model fallback, a
rejected AI reply or a skipped record).

---

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:

1. **tests**: installs `requirements.txt` on Python 3.13 and runs
   `python run_tests.py`.
2. **docker**: builds the Docker image and runs the tests inside it, so the
   image is checked too.

A pull request into `phase2Main` should only be merged when both are green.

---

## Where data goes

Uploaded PDFs are sent to Gemini and never saved to disk. What Gemini
returns is saved by the Data Manager as JSON in `data/`:

| File | Saved when | Contains |
|---|---|---|
| `data/resumes.json` | A job seeker uploads a resume | Education, experience and skills |
| `data/job_matches.json` | Right after that | The suggested jobs for that resume |
| `data/candidate_matches.json` | An employer uploads | The job posting details, the scoring profile used and the scored candidates |
| `data/scoring_profiles.json` | An employer uses a Custom profile | The profile's name, weights and Strong Match share |

Each visitor's session (a signed cookie) remembers which saved result is
theirs, so the results pages only show their own results. These files hold
people's personal details, so they are listed in `.gitignore` and should be
kept out of git.

The app doesn't use a database: sessions are signed cookies and data is JSON.

---

## Project structure

```text
INF1103_Group-3_Assgn1/
├── manage.py
├── run_tests.py                    # Test script: python run_tests.py
├── requirements.txt
├── Dockerfile                      # Image: Python + packages + code, runs runserver
├── docker-compose.yml              # docker compose up: port 8000, .env, data/ volume
├── .dockerignore                   # Keeps .env, data/ and .venv out of the image
├── .env.example
├── .github/workflows/ci.yml        # CI: runs the tests, and the tests inside Docker
├── config/                         # Django settings, urls, wsgi
├── data/                           # Saved results (JSON)
├── docs/
│   └── class-diagram.md            # Phase 2 class diagram (Mermaid)
└── matcher/
    ├── views.py                    # Class-based views: handle the request, show messages
    ├── urls.py
    ├── context_processors.py       # Adds ?v= to CSS/JS links so browsers load new versions
    ├── models.py                   # Empty: no database models
    ├── tests/                      # Test functions (test_*.py), run by run_tests.py
    ├── contracts/                  # Abstract base classes the managers build on
    │   ├── ai.py                   # AIProvider, AITask
    │   ├── data.py                 # RecordRepository
    │   └── scoring.py              # ScoreComponent
    ├── domain/                     # Resume, JobSuggestion, JobPosting, Candidate,
    │                               # MatchResult, Shortlist, ScoringProfile
    ├── managers/
    │   ├── io_manager.py           # UploadValidator, JobFilterForm, ScoringProfileForm
    │   ├── ai_manager.py           # AIManager: runs AI tasks, checks replies
    │   ├── ai_providers.py         # GeminiProvider: Google Gemini calls
    │   ├── ai_tasks.py             # The three AI requests: prompts and reply checks
    │   ├── data_manager.py         # JsonRepository: JSON save/load
    │   └── logic_manager.py        # CandidateScorer, rankers, JobFilter
    ├── services/
    │   └── matching_service.py     # MatchingService: the three AI flows
    ├── templates/
    │   ├── 404.html, 500.html      # Friendly error pages
    │   └── matcher/                # landing, employer, job_seeker and the two results pages
    └── static/
        ├── css/style.css
        └── js/main.js              # Drag-and-drop uploads, loading spinner
```
