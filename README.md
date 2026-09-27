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
- Job seeker: upload a resume PDF + set work arrangement / location(s) /
  working hours preferences
- Both results pages: ranked cards with match score, matched/missing
  skills, compatibility checks, empty states
- 10 automated tests covering page loads, upload validation, and
  successful-submission redirects

What's **not** real yet (by design — later sprints):

- Uploaded files are validated but not read, stored, or processed —
  results pages currently show hardcoded sample data
  (`matcher/dummy_data.py`)
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

### 5. Configure environment variables (Not needed for sprint 1)

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
copy .env.example .env
```

The defaults in `.env.example` work as-is for Sprint 1 — nothing needs
to be filled in yet (no AI API key is required until Sprint 4).

### 6. Run the app

```bash
python manage.py migrate   # sets up Django's own internal tables only 
python manage.py runserver (Use this)
```

Open **http://127.0.0.1:8000/** in your browser.

### 7. Run the tests

```bash
python manage.py test matcher
```

You should see `Ran 10 tests ... OK`.

---

## Project structure

```text
resume_matcher/
├── manage.py
├── requirements.txt
├── .env.example
├── config/                    # Django project settings/urls/wsgi
├── data/                      # Sample CSV/JSON (wired up in Sprint 2)
├── media/uploads/             # Uploaded files land here in later sprints
└── matcher/
    ├── views.py                # Thin views: validate input, render templates
    ├── urls.py
    ├── forms.py                 # Upload + preference form validation
    ├── models.py                 # Empty — no ORM models (see file for why)
    ├── dummy_data.py              # Sprint 1 stand-in for real records
    ├── tests.py
    ├── managers/                  # Sprint 2-4 placeholders (see each file)
    │   ├── io_manager.py
    │   ├── data_manager.py
    │   ├── logic_manager.py
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

- **I/O Manager** — the only place `print()`/terminal I/O is allowed;
  in a Django app this mostly means: the only place that formats
  user-facing messages and validation errors.
- **AI Manager** — zero business logic. Prompt building, API calls,
  schema validation, retries only.
- **Logic Manager** — the domain brain. Scoring, the multi-condition
  match rule, ranking. Never talks to the AI API or the filesystem
  directly.
- **Data Manager** — the only place that reads/writes `data/*.json`
  (or `.csv`). Handles missing/corrupt files without crashing.

Each manager is a placeholder module right now with a docstring
explaining what it will own — see `matcher/managers/`.
