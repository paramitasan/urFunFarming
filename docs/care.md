# Module 5: Plant Care and Weather

Care tasks for a grower's own plants, judged against the weather forecast for
their city. Tasks are private: a task is only ever visible to the account that
created it.

## Pages

| URL | What it does |
| --- | --- |
| `/care/` | The task list, the weather card and the filters |
| `/care/new/` | Plan a task, with suggested hours from the forecast |
| `/care/<id>/edit/` | Change a task |
| `/care/<id>/delete/` | Confirm, then delete |
| `/care/<id>/done/` | POST only, ticks a task off or back on |
| `/care/limits/` | POST only, saves the weather limits |
| `/care/weather-check/` | GET, judges one date and time, used while filling the form |

## Models

`CareTask` holds the activity, the planned date, an optional time, private
notes and whether it is done. `completed_at` is set in `save()` from `is_done`,
so the two can never disagree. `clean()` refuses a planting that belongs to a
different grower. That is model-level validation on the save path, not a database
constraint, so the form is what actually enforces it on every request.

`WeatherPreference` holds the city and three limits: rain, temperature and
humidity. `accepts(slot)` answers whether one forecast hour stays inside all
three. The city lives here rather than on the shared `Profile`, so this module
does not have to change another member's model.

## Weather

The forecast comes from `marketplace.weather.forecast()`, which the Marketplace
module already uses for collection planning. Reusing it keeps one Open-Meteo
adapter in the project rather than two, including its cache and its validation.

`care/planning.py` turns that raw forecast into advice:

- `suggestions()` lists the next few hours that stay inside every limit
- `verdict()` judges a chosen date, with or without a time
- `today_outlook()` is the one-line summary on the list page

Every one of them answers sensibly when the service is unavailable, because
`load_forecast()` catches `WeatherUnavailable` and returns `None`.

## Permissions

| Who | May do |
| --- | --- |
| Not signed in | redirected to the login page |
| Signed in, no grower role | may read and manage what they already own, but creating and editing answers 403 |
| Grower | everything, but only with their own tasks and their own plants |

A task belonging to someone else answers **404**, not 403, so the response does
not even confirm that it exists. The plant dropdown is narrowed to the grower's
own plants inside the form, which means the restriction also holds when the
form is posted rather than only in the rendered page.

## AJAX

Four things happen without reloading the page. Each one sends the header
`X-Requested-With: fetch`, which is the same handshake the Marketplace module
uses, and the view then answers with JSON instead of a redirect.

| Action | Endpoint | Answer |
| --- | --- | --- |
| Tick a task off | `POST /care/<id>/done/` | the new state of that task |
| Change a filter | `GET /care/` | the re-rendered list plus the counts |
| Save the limits | `POST /care/limits/` | the refreshed outlook |
| Check a time | `GET /care/weather-check/` | the verdict for that moment |

All of it is an enhancement. With JavaScript switched off the same forms submit
normally, the filter has an Apply button, and every page still works.

## Tests

`python manage.py test care` runs 48 tests. No test touches the network: the base
test case patches `care.planning.forecast` for every case, so the suite also
passes with outbound connections blocked.
