# urFunFarming

**Urban Farming Community and Local Harvest Marketplace**

Platform-Based Programming (PBP) Midterm Group Project, theme: Sustainable Living
Faculty of Computer Science, Universitas Indonesia, Odd Semester 2026/2027

![urFunFarming landing page](docs/screenshots/landing.png)

## Project Links

| Resource | Link |
| --- | --- |
| Repository | https://github.com/paramitasan/urFunFarming/ |
| Deployed app (PWS) | https://paramita-santoso-urfunfarming.pws.cs.ui.ac.id/ |
| Figma design | https://www.figma.com/design/rDovEM0bwhNE0xkgKZhwV4/Farmerzz?node-id=0-1&t=uf8tBdtybxcNt5PB-1 |
| External API | [BMKG public weather forecast API](https://data.bmkg.go.id/prakiraan-cuaca/) |

## Table of Contents

1. [About the App](#about-the-app)
2. [Group Members and Modules](#group-members-and-modules)
3. [User Roles](#user-roles)
4. [Features per Module](#features-per-module)
5. [External API](#external-api)
6. [Design System](#design-system)
7. [Tech Stack](#tech-stack)
8. [Run It Locally](#run-it-locally)
9. [Demo Data and Accounts](#demo-data-and-accounts)
10. [Testing and Coverage](#testing-and-coverage)
11. [Deployment](#deployment)
12. [Git Workflow](#git-workflow)
13. [Screenshots](#screenshots)
14. [AI Disclosure](#ai-disclosure)

## About the App

urFunFarming connects small urban growers with each other and with people nearby who want locally grown food. A resident who grows vegetables or herbs on a balcony, rooftop, small garden or hydroponic setup can:

- record their gardens and the plants in them,
- keep a dated journal of how each plant is growing,
- ask and answer growing questions in a community forum,
- post surplus harvest in a marketplace so buyers nearby can arrange pickup,
- check the weather before planning a pickup.

**Problem.** Progress notes, advice and produce offers are usually spread over separate chats and apps. urFunFarming puts them in one place, around the same gardens and growers.

**Benefit.** It makes local produce easier to find, gives growers a simple way to share or sell what they don't need (a price of zero means free), and supports people who are starting out in urban farming. These are intended benefits. We don't claim the app has already reduced waste.

The marketplace is post based. Growers post a harvest, and signed-in buyers see the grower's contact details to arrange payment and collection themselves. There is no in-app payment.

## Group Members and Modules

| Full name | NPM | Assigned module |
| --- | --- | --- |
| Angin Putih Ranulaksmi Tsurayya Hapsoro | 2506557936 | 3 |
| Azkal Azkiya Arifi Putra | 2506636991 | 2 |
| Marcel Mikula | 2606816592 | 4 |
| Muhamad Idris Kamal | 2506637073 | 1 |
| Paramita Santoso | 2506554171 | 6 |
| Tahir Ahmad | 2606816466 | 5 |

Module names: 1. Landing Page, Authentication and User Profiles; 2. Gardens and Plantings; 3. Plant Progress Journal; 4. Harvest Marketplace; 5. Care Planning and Weather; 6. Community Questions and Answers (Forum).

Each member owns one module with its own models, forms, views, URLs, templates, permissions, filters, interactivity and tests. Shared parts (base template, navbar, footer, settings, URLs, CI and deployment) were integrated together through pull requests.

## User Roles

| Role | What they can do |
| --- | --- |
| Visitor (not logged in) | See the landing page, browse marketplace listings, explore public gardens and read forum question titles. Contact details, full forum discussions and private records are hidden. |
| Grower | Everything a buyer can do, plus manage their own gardens and plantings, write plant journal entries, set each plant journal public or private, and post harvest listings. |
| Buyer | See growers' contact details on listings, read public gardens and public plant journals, and ask, answer and vote in the forum. |
| Administrator | Manage users and moderate all records through the Django admin. |

One account can be both a grower and a buyer (`accounts.Profile` has `is_grower` and `is_buyer`). Being logged in never lets a user edit someone else's records: every edit and delete view checks the owner, and private records are filtered out in the query itself, not only hidden in the template.

## Features per Module

### Module 1: Landing Page, Authentication and User Profiles (Idris)

- Landing page with real marketplace listings and a category filter (`/`, `/listings/`), plus a signed-in home page (`/home/`).
- Register (choose grower, buyer or both), login with "remember me", and logout (`/register/`, `/login/`, `/logout/`). Register and login also work through AJAX endpoints.
- Profile page to edit display name, bio, area, city, phone and contact email (`/profile/`).
- JSON endpoints: `/auth/me/json/` and `/profile/json/<username>/`.

### Module 2: Gardens and Plantings (Azkal)

- Full CRUD for gardens (name, location, growing method, public summary, private notes, public or private) and for plantings inside a garden (crop, optional name, planting date, growing method).
- "Explore gardens" for everyone, with search, location and growing method filters (`/gardens/explore/`), and "My gardens" for the owner (`/gardens/mine/`).
- Private notes and private gardens are only shown to the owner.
- Each planting links to its plant journal (Module 3).

### Module 3: Plant Progress Journal (Ranu)

- Growers write dated entries for their own plantings: date, time, height in cm, growth stage, plant health, observation and up to 5 photos (uploaded JPG/PNG/WEBP up to 5 MB, or image links).
- Journal list with search, plant, stage and health filters, sorting and pagination. Filters update the table with AJAX (`fetch`) and a debounced search box, and still work as a normal GET form (`/journal/`).
- Plant timeline page with height change since the previous entry, a growth stage tracker and newest or oldest first order (`/journal/plant/<id>/`).
- Create, edit and delete entries, and delete all entries of a plant, with a confirm dialog and toasts.
- Visibility is set per plant journal with a lock button (AJAX). Buyers reach a public plant from the garden page and see a read-only timeline; a private plant shows "This journal is private" and its entries are never sent to the page.
- Photos and links are checked on the server, not only in JavaScript, and thumbnails are built without `innerHTML` to avoid XSS.

### Module 4: Harvest Marketplace (Marcel)

- Full CRUD for harvest listings: title, description, crop category, quantity and unit, price (zero shows as Free), availability dates, pickup area and city, optional photo link.
- Live search, combined filters, sorting and pagination with `fetch`; the normal form still works without JavaScript (`/marketplace/`, `/marketplace/mine/`).
- Grower contact details are only shown to signed-in users, in both HTML and JSON.
- Pickup weather filter using BMKG forecasts (see [External API](#external-api)).
- JSON API: `/marketplace/api/listings/` and `/marketplace/api/listings/<id>/`.
- More detail in [docs/marketplace.md](docs/marketplace.md).

### Module 5: Care Planning and Weather (Tahir)

- Full CRUD for care tasks linked to the grower's own plantings: activity (for example watering), title, target date and optional time, notes and status (`/care/`).
- Change a task's status from the list, and filter the task list.
- Each grower sets their own weather limits (maximum rain, temperature and wind) in care settings, and the app suggests good times for a task from the BMKG forecast.
- Care tasks are private to their owner.

### Module 6: Community Questions and Answers (Paramita)

- Full CRUD for questions (title, description, topic, optional image) and replies, with an "edited" label (`/forum/`).
- Search, topic filter, answered or unanswered filter, sort and pagination.
- Upvotes for questions and replies, and the author can mark a question as answered.
- Visitors see question titles only; the full discussion needs login. Only the author can edit or delete their own post or reply.

## External API

We use the **[BMKG public weather forecast API](https://data.bmkg.go.id/prakiraan-cuaca/)** (Badan Meteorologi, Klimatologi, dan Geofisika). It is free, needs no API key, and gives forecasts for Indonesian villages by their area code (kode wilayah tingkat IV), which fits our Jabodetabek users.

How it is used:

- **Shared weather service** (`weather/services.py`): every page that shows weather goes through this one file. The server calls BMKG, never the browser, and turns the response into simple hourly slots (temperature, rain, wind, humidity).
- **Care planning (Module 5):** the forecast for the grower's area is compared with their own limits to suggest good times for a care task.
- **Marketplace (Module 4):** a buyer can filter pickup hours on a listing by date, time window, maximum rain and maximum temperature. Only hours inside the listing's availability are shown. The forecast is taken for the collection city's centre, never the grower's address.
- **Profile locations (Module 1):** the city, district and village dropdowns come from a local file (`accounts/data/jabodetabek.json`) with the same area codes BMKG uses.
- **Failure handling:** results are cached for an hour (BMKG updates twice a day and limits requests per IP), requests time out after 5 seconds, and after a failure the app waits a few minutes before asking again. Pages then show "Weather is unavailable right now" instead of breaking.
- Tests mock BMKG, so CI never calls the real service.

## Design System

- **Figma:** all screens are designed in the group file [Farmerzz](https://www.figma.com/design/rDovEM0bwhNE0xkgKZhwV4/Farmerzz?node-id=0-1&t=uf8tBdtybxcNt5PB-1), with one page per module (for example the PlantProgressJournal page has the list, timeline, forms, buyer views, delete overlays and all toasts).
- **Shared layout:** every page extends `templates/base.html` with the same navbar, footer and grower sub navigation (`templates/partials/`).
- **Shared tokens:** colors, radius, shadows and the Poppins font are CSS variables in the `:root` of `static/css/style.css`, and each module's CSS (`static/<module>/`) reuses them, so the modules look like one app.
- **Icons:** exported from the Figma file as SVG (Feather style), not AI generated.
- **Responsive:** layouts use Flexbox, Grid and media queries; the marketplace also uses a locally vendored Bootstrap 5.3.3 grid. Pages work on phone width (see the mobile screenshot below).
- **Interactivity:** `fetch` with the CSRF token (Tutorial 5 style) for filters, toggles and deletes, toasts for feedback, and HTMX in `templates/partials/chips.html`.

## Tech Stack

- Python 3.12, Django 5.2 (MVT, function views, ModelForms)
- SQLite locally, PostgreSQL on PWS
- HTML templates, plain CSS, vanilla JavaScript, HTMX, Bootstrap grid (marketplace)
- WhiteNoise for static files, Pillow for image uploads, Requests for the BMKG API
- `coverage` and Django `TestCase`, GitHub Actions for CI

## Run It Locally

```bash
git clone https://github.com/paramitasan/urFunFarming.git
cd urFunFarming
python -m venv env
# Windows: env\Scripts\activate    macOS/Linux: source env/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_marketplace
python manage.py seed_journal
python manage.py runserver
```

Open http://127.0.0.1:8000/. Without the `PRODUCTION` environment variable the app uses SQLite, so no `.env` file is needed for local work. To make an admin account, run `python manage.py createsuperuser`.

## Demo Data and Accounts

The deployed app has **more than 50 main records**:

| Command | What it creates |
| --- | --- |
| `python manage.py seed_marketplace` | 50 harvest listings from 10 demo growers (these demo growers cannot log in) |
| `python manage.py seed_journal` | 2 gardens, 12 plantings and 17 journal entries with photo links, plus the demo accounts below |

Both commands are safe to run again: they don't create duplicates and don't touch real users' records.

| Username | Password | Role |
| --- | --- | --- |
| `demo_grower` (Sari) | `Seedling-Tray-42` | Grower: owns the demo gardens and journals |
| `demo_buyer` (Dewi) | `Seedling-Tray-42` | Buyer: sees public gardens and journals read-only |

These are demo accounts with demo data only.

## Testing and Coverage

```bash
coverage run --source=accounts,main,marketplace,forum,gardens,journal manage.py test
coverage report
```

Result on `main` on 30 Oct 2026: **430 tests, all passing, 98% total coverage** across the six apps. Tests cover valid and invalid forms, full CRUD, owner checks, login-only data, private records, filters and pagination, JSON endpoints, CSRF, input escaping, weather API failures (mocked) and the seed commands.

GitHub Actions (`.github/workflows/django-tests.yml`) runs on every pull request and on pushes to `main` and feature branches. It runs `manage.py check`, checks that no migrations are missing, runs `collectstatic`, then runs the tests with a minimum coverage of 80% (`.coveragerc`).

## Deployment

The app is deployed on PWS: https://paramita-santoso-urfunfarming.pws.cs.ui.ac.id/

- `uff/settings.py` switches database by the `PRODUCTION` environment variable: SQLite in development, PostgreSQL on PWS (`DB_NAME`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `SCHEMA`).
- Database credentials are set as PWS environment variables and are never committed.
- Static files are served by WhiteNoise after `collectstatic`.
- Only `main` is deployed. A feature reaches `main` through a reviewed pull request with passing CI.

## Git Workflow

- `main` is the integration branch. Each member works on their own feature branch (for example `feat/harvest-marketplace`, `feat/gardens-and-plantings`, `fix/journal-review`) and opens a pull request into `main`.
- Members merge the latest `main` into their branch before opening a pull request and resolve conflicts in shared files (`settings.py`, `uff/urls.py`, `requirements.txt`, shared partials) by keeping both sides.
- Commits are small and use prefixes: `feat:`, `fix:`, `style:`, `refactor:`, `test:`, `docs:`.
- Pull requests must pass CI before merging. The full history is in the repository's [pull requests](https://github.com/paramitasan/urFunFarming/pulls?q=is%3Apr).

## Screenshots

Taken from a local run with the demo data.

| Marketplace | Explore gardens |
| --- | --- |
| ![Harvest Marketplace](docs/screenshots/marketplace.png) | ![Explore gardens](docs/screenshots/gardens-explore.png) |

| Plant journal (grower) | Marketplace on a phone |
| --- | --- |
| ![Plant journal list](docs/screenshots/journal-list.png) | ![Marketplace mobile view](docs/screenshots/mobile-marketplace.png) |

## AI Disclosure

We used AI tools during this project. Every member is responsible for their own module and can explain every part of it. No AI-generated images or logos are used anywhere in the app or the Figma file.

### Group level

- **ChatGPT** helped draft the first project description and module plan for Checkpoint 1. The group reviewed and changed the scope and the module split together.

### Module 3: Plant Progress Journal (Ranu)

**Tools and purpose**

- **Claude Code** (Anthropic) inside VS Code as a coding assistant.
- **Claude on claude.ai** as a planning helper in a separate chat. It did not write code into the project. It helped plan the module, write the instructions given to Claude Code, check Claude Code's plans, explain errors and git messages, and draft messages to the group.
- **Figma MCP**, so both assistants could read (never edit) the PlantProgressJournal frames.

**Prompt strategy**

- Claude Code was set up so it could not create or edit project files or run git commands that change anything. For every change it showed the file, the place, the old and new code and a short explanation, and **I typed every change myself**. Afterwards it read the file and pointed out my typos instead of fixing them.
- It had to follow the PBP tutorial style (function views, ModelForm, templates, `fetch` with the CSRF token, `TestCase`) and explain each piece so I could defend it.
- For big pieces it first wrote a plan in Plan mode, which I checked with the planning helper and corrected before accepting.
- I worked one Figma frame at a time ("Plant Journal (list)", "New Entry (errors)" and so on), sent screenshots when something looked wrong, and asked it to read the frame again whenever I changed the design.
- I made the design and behaviour decisions myself, for example visibility per plant journal instead of per entry, uploads and links with a limit of 5 photos, a private screen for buyers, AJAX filters with normal dropdowns, no Undo on delete toasts and only one toast at a time.
- I ran all commits, pushes, merges, `makemigrations` and `migrate` myself.

**Limitations and manual fixes**

- Its first plan said the marketplace app didn't exist, because my laptop hadn't fetched that branch. The planning helper checked GitHub and corrected it.
- The first plan also missed the existing grower role (`Profile.is_grower`) and a buyer page for an empty journal. I had both added before building.
- The timeline order link used `#timeline`, which made the page jump. I changed it to load with `fetch`.
- That link first came out bigger than the design with the arrow pointing sideways. I caught both from screenshots.
- `floatformat` showed one decimal by default, so 12.75 cm looked wrong until we used `floatformat:"-2"`.
- The fixed navbar covered the top of the buyer pages until the padding was fixed after I saw it in the browser.
- Toast icons broke when the server was off, so they are now preloaded.
- It forgot tests for `seed_journal` until the coverage report showed the gap.
- On Edit, removing every saved photo didn't bring back the big upload box. I found this while testing, and the template now uses one layout for both New and Edit.
- While Module 2 wasn't merged I used a temporary Garden and Planting model with my teammate's OK. When the gardens app was merged, I switched to `gardens.Planting` and reset my migrations, which the AI didn't plan for at first.
- Long code blocks sometimes got cut off when pasted, so I asked for smaller steps.

The full chat history is available if the teaching assistants want to see it.

### Module 4: Harvest Marketplace (Marcel)

ChatGPT assisted with the Django implementation, adapting the shared Figma design, tests and integration documentation. See [docs/marketplace.md](docs/marketplace.md) for the scope and how it was verified.

### Modules 1, 2, 5 and 6

<!-- Idris, Azkal, Tahir, Paramita: replace this with your own short disclosure: which tools, what you used them for, and at least one thing you had to fix yourself. Write "No AI tools were used" if that is true. -->
