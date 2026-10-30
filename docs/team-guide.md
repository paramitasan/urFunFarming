# Team Guide

How our group works on urFunFarming. If you're new to the repo, read this first, then the [README](../README.md).

## Who owns what

| Module | Owner | Apps and folders |
| --- | --- | --- |
| 1. Landing, Auth and Profiles | Idris | `main/`, `accounts/` |
| 2. Gardens and Plantings | Azkal | `gardens/` |
| 3. Plant Progress Journal | Ranu | `journal/` |
| 4. Harvest Marketplace | Marcel | `marketplace/` |
| 5. Care Planning and Weather | Tahir | `care/`, `weather/` |
| 6. Community Q&A (Forum) | Paramita | `forum/` |

Each owner is responsible for their module's models, forms, views, URLs, templates, static files and tests.

**Shared files**, which affect everyone: `uff/settings.py`, `uff/urls.py`, `requirements.txt`, `templates/base.html`, `templates/partials/`, `static/css/style.css`, `.coveragerc` and `.github/workflows/`. If you need to change one of them, say so in the group chat first, and keep the change as small as you can.

## Branches

- `main` is the integration branch and is the only branch deployed to PWS. Nobody pushes to it directly.
- Make your own branch from the latest `main`. Name it after what it does:
  - `feat/<what>` for a new feature, for example `feat/journal-entries`;
  - `fix/<what>` for a bug fix, for example `fix/journal-review`;
  - `docs/<what>` for documentation only.

```bash
git checkout main
git pull origin main
git checkout -b feat/<what>
```

## Commits

- Commit small, working steps, not one big commit at the end.
- Add files by name. **Never use `git add .`**, so local files (`.env`, `db.sqlite3`, `media/`, your own notes) don't get committed by accident.
- Start the message with a prefix:

| Prefix | Use it for |
| --- | --- |
| `feat:` | a new feature or page |
| `fix:` | a bug fix |
| `style:` | CSS or layout only |
| `refactor:` | cleaner code, same behaviour |
| `test:` | tests only |
| `docs:` | README or docs only |

```bash
git add journal/views.py templates/journal/list.html
git commit -m "feat: add search and filters to the journal list"
```

## Pull requests

1. Before opening a PR, bring in the latest `main` and run the tests:
   ```bash
   git pull origin main
   python manage.py test
   ```
2. Push your branch and open a PR into `main`. Write what changed and how to test it.
3. CI (GitHub Actions) must be green before merging.
4. Another member looks at it before it's merged, especially if it touches shared files.

## Merge conflicts

They usually happen in shared files (`settings.py`, `uff/urls.py`, `requirements.txt`, `grower_subnav.html`).

- **Keep both sides.** For example, keep both apps in `INSTALLED_APPS` and both lines in `urls.py`.
- Delete the `<<<<<<<`, `=======` and `>>>>>>>` markers.
- Run `python manage.py check` and `python manage.py test` before committing the merge.
- If you're not sure what someone else's code needs, ask them before you delete it.

## Running locally

```bash
python -m venv env
# Windows: env\Scripts\activate    macOS/Linux: source env/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_marketplace
python manage.py seed_journal
python manage.py runserver
```

After pulling someone else's work, run `pip install -r requirements-dev.txt` and `python manage.py migrate` again.

## Migrations

- Only make migrations for your own app: `python manage.py makemigrations <your_app>`.
- Commit the migration files together with the model change.
- Don't edit or delete another member's migrations.

## Tests and coverage

```bash
coverage run --source=accounts,main,marketplace,forum,gardens,journal manage.py test
coverage report
```

- Every module has its own tests in its app.
- CI fails under 80% coverage, so add tests with your feature, not after.
- Mock outside services (like BMKG) in tests. Tests must never call the real API.

## Demo data

- Seed commands live in `<app>/management/commands/`.
- They must be safe to run more than once (use `get_or_create`), and they must never change real users' records.
- Use image links, not uploaded files, for demo photos. PWS redeploys can wipe uploaded media.

## Deployment (PWS)

- PWS deploys from `main` and runs `migrate` on deploy.
- The production database settings are PWS environment variables (`PRODUCTION`, `DB_NAME`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `SCHEMA`).
- **Never put credentials in the repo or in the group chat.** `.env` and `.env.prod` stay in `.gitignore`.
- Seed data is loaded into PWS once, by whoever has the database details, by running the seed commands with those environment variables set.

## Windows and OneDrive tip

If the repo is inside a OneDrive folder, git may ask "Deletion of directory ... failed. Should I try again?". Answer `n`, run `git config gc.auto 0` once, and pause OneDrive syncing while you work.
