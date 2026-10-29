# Harvest Marketplace — Module 4

Owner: Marcel Mikula, NPM 2606816592. Django app: `marketplace`.

## Start locally

From the repository root, with a virtual environment active:

```bash
python -m pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_marketplace
python manage.py runserver
```

Open `/marketplace/`. Register through the existing account module and select **I grow food** to create listings. One account can have both roles. Existing owners can still edit or remove their own offers if they later turn the grower role off.

The seed command creates 50 available listings from ten fictional profiles. It is repeatable and refreshes only its own demonstration records. Every demo offer is labelled on its detail page. Demo users have unusable passwords and cannot sign in. The command refuses collisions with real accounts or listings rather than replacing them. Create a normal account to try the CRUD flow.

## Implemented behavior

| Requirement | Implementation |
| --- | --- |
| Model and complete CRUD | `HarvestListing`, validated `ListingForm`, list/detail/create/edit/delete pages, Django admin |
| Required offer data | Title, description, crop category, available quantity, unit, price and price quantity, availability dates, collection area and city; optional photo URL |
| Free produce | A price of zero is shown as Free; quantity per price is distinct from total available stock |
| Authentication filtering | Visitors never receive contact information in HTML or JSON; signed-in members can view grower contacts on offer details |
| Ownership | Only the owner can open management forms or update/delete through HTML and JSON; owner and demo flags are never accepted from user input |
| Client interactivity | Fetch-based live search, combined filters, sorting, pagination, form feedback, CRUD, and pickup-weather filtering; normal form submissions remain functional |
| Responsive CSS framework | Locally vendored Bootstrap 5.3.3 grid with scoped marketplace CSS and existing group colors, navigation, footer and Poppins typography |
| External API filtering | Real BMKG 3-hourly forecasts (through the shared `weather` service) filtered by date, time interval, maximum rain and temperature; future slots must also fall within the listing's availability |
| Initial data | `python manage.py seed_marketplace`: 50 offers, ten growers, deterministic IDs and collision protection |
| Integration | Shared Profile roles/contact data, shared base/navbar/footer, real database listings on the landing page, safe login return paths |
| Tests | Model/database validation, public and private queries, HTML and JSON CRUD, CSRF, ownership, input escaping, pagination, weather service failure/cache/filtering, safe seed reruns, and existing account/landing tests |

The shared design is [Marketplace / Desktop, node 276:16708](https://www.figma.com/design/rDovEM0bwhNE0xkgKZhwV4/Farmerzz?node-id=276-16708). This implements the newer group design, rather than replacing the shared theme with the earlier inspiration mockup. Existing shared components remain in use. Marketplace icons are exact SVG exports from that design, stored in `static/marketplace/img`.

## JSON interface

All URLs below start with `/marketplace/`. JSON writes use the existing Django login session and CSRF protection. There are no CSRF-exempt endpoints and no independent authentication system. For a browser session, obtain a CSRF cookie from the create page and send it as `X-CSRFToken`. Mobile authentication/CORS configuration belongs to the later group integration.

| Method | URL | Access and result |
| --- | --- | --- |
| GET | `api/listings/` | Public; `count`, `page`, `pages`, `results`; six results per page |
| POST | `api/listings/` | Signed-in grower; create from a JSON object or form data |
| GET | `api/listings/<uuid>/` | Public offer details; contact object included only for authenticated members |
| PUT / PATCH | `api/listings/<uuid>/` | Owner only; full or partial update |
| DELETE | `api/listings/<uuid>/` | Owner only |
| GET | `<uuid>/weather/` | Public for a visible offer; add `Accept: application/json` for JSON rather than HTML |

Listing filters: `q`, `category` (`vegetables`, `fruits`, `herbs`), `availability` (`now`, `any`), `price_type` (`free`, `paid`), `max_price`, `city`, `area`, `grower` (username), `sort` (`newest`, `price_asc`, `price_desc`, `title`) and `page`. `max_price` and price sorting compare the price of each offer's displayed lot, not a converted per-kilogram price. Blank optional filters mean all. Invalid filters produce a visible form error or JSON 400, not a server error.

`mine/` always filters by the signed-in owner and includes paused and expired offers. Public browsing excludes paused/expired offers and inactive owners. `availability=now` additionally excludes future harvests; `any` includes upcoming harvests. Public detail access to a paused/expired offer returns 404; its owner retains access.

Pickup-weather parameters: `date` (today through two days ahead, the range BMKG covers), `start_time`, `end_time`, `max_rain` (mm), `max_temperature` (°C). All collection times use **Asia/Jakarta / WIB**, independently of the project's global timezone. Each collection city maps to a fixed BMKG village code near its centre (`CITY_ADM4` in `marketplace/weather.py`); the server never fetches a user-provided URL. The shared service caches each 3-day forecast for an hour. Missing observations are skipped; network or invalid-provider responses return 503 and an explicit retry message, never fabricated weather. Listing CRUD and ordinary browsing do not depend on the external API being online.

API documentation: https://data.bmkg.go.id/prakiraan-cuaca/ (fields `t`, `tp`, `hu`, `ws`, normalized by `weather/services.py`). Pages show "Source: BMKG" as BMKG requires. The small collection planner is independent of Module 5's private care tasks.

## Verify

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
coverage run manage.py test
coverage report
```

Coverage excludes test code and migrations, includes branches, and must be at least 80%. An included GitHub Actions workflow runs these commands after pushes and pull requests. External API calls in automated tests are mocked. Test output and local SQLite files are ignored by Git. Remote CI has not run yet: the connected GitHub integration rejected writes to the group repository with HTTP 403, although read access worked.

Manual checks: browse and filter as a guest; inspect a grower's contact panel before and after login; create, edit, pause and delete an offer as its owner; try a buyer-only account; check My listings and the mobile layout; request pickup times, then test an unreachable weather provider.

### Verification performed on 23 October 2026

- All **91 Django tests** passed, including the 39 existing group tests and 52 marketplace tests. Marketplace statement-and-branch coverage was approximately **98.6%**; total measured application coverage rounded to **98%**.
- Configuration checks, migration consistency, JavaScript syntax, `collectstatic`, and whitespace checks passed.
- A real Chromium browser exercised live search, sorting, filtering, pagination and empty results; AJAX create/edit/delete; guest versus member contact visibility; and optional photos. No uncaught JavaScript errors were observed.
- Widths **320, 390, 768, 1024 and 1440 pixels** had no horizontal overflow. The mobile filter toggle was exercised.
- Create/delete and mobile filtering were also exercised with JavaScript disabled.

Visual inspection used local demonstration/test data, not a deployed production application. Provider success/failure behavior is covered by mocked service tests; PWS connectivity must still be checked after group integration.

## Group integration and submission

1. Review `feat/harvest-marketplace` together before merging. This branch does not merge or publish itself.
2. Keep the `marketplace` app registration and URL include when integrating other modules. Merge their URL additions rather than replacing the root URL file.
3. Run `python manage.py migrate` on the integrated deployment, then `python manage.py seed_marketplace` to satisfy the minimum initial-data requirement. A repository full of fixtures alone does not populate the deployed database.
4. Run all tests again with the other modules integrated and verify the deployed URL from the README. The branch's local checks do not validate PWS deployment or other members' unfinished modules.
5. Confirm the deadline with the TA: the linked midterm assignment states **23 October 2026, 23:59 WIB**, while the pasted group chat mentions finishing modules on 24 October. Use the earlier deadline until an official correction is verified.
6. Check deployment security settings before publishing. The inherited project settings currently use `DEBUG=True`; production configuration is a group deployment concern, not proof of a secure production release.

Assignment references: [Midterm](https://pbp.cs.ui.ac.id/en/assignments/group/midterm.html), [Group guide](https://pbp.cs.ui.ac.id/en/assignments/group/midterm-guide.html), [Final project](https://pbp.cs.ui.ac.id/en/assignments/group/finalterm.html). The midterm page was available during implementation; the guide and final-project pages returned access errors, so no unverified additional rubric or final-project requirements are claimed.

## AI assistance

ChatGPT assisted Marcel with the marketplace's Django implementation, adaptation to the shared Figma design, integration, tests and documentation. The group remains responsible for reviewing the code, explaining its behavior, combining the modules and checking the final deployed submission.
