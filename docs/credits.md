# Credits

urFunFarming uses the outside resources below. No images, icons or logos in the app or in our Figma file were made with AI.

## Data

| Source | Used for | Terms |
| --- | --- | --- |
| [BMKG public weather forecast API](https://data.bmkg.go.id/prakiraan-cuaca/) (Badan Meteorologi, Klimatologi, dan Geofisika) | Weather forecasts for care planning and the marketplace pickup filter | Free public data. BMKG asks users to credit BMKG as the source, which we do in the site footer ("Weather data by BMKG"). |
| [wilayah.id](https://wilayah.id/) (Kemendagri area codes) | City, district and village list in `accounts/data/jabodetabek.json` for profile locations | Public area codes, the same codes BMKG uses |

## Images

**Demo photos** in `seed_journal` are links to Wikimedia Commons. They are not stored in this repository:

- [Tomato_je.jpg](https://commons.wikimedia.org/wiki/File:Tomato_je.jpg)
- [Tomatoes_plain_and_sliced.jpg](https://commons.wikimedia.org/wiki/File:Tomatoes_plain_and_sliced.jpg)
- [Ocimum_basilicum_8zz.jpg](https://commons.wikimedia.org/wiki/File:Ocimum_basilicum_8zz.jpg)

Each file's author and license are on its Commons page.

**Logo, illustrations and icons** (`static/img/`, `static/<module>/`) were drawn or exported from our group Figma file, [Farmerzz](https://www.figma.com/design/rDovEM0bwhNE0xkgKZhwV4/Farmerzz?node-id=0-1&t=uf8tBdtybxcNt5PB-1). The line icons follow the [Feather](https://feathericons.com/) icon style (MIT License).

## Fonts

- [Poppins](https://fonts.google.com/specimen/Poppins), loaded from Google Fonts (SIL Open Font License 1.1)

## Front-end libraries

| Library | How it's loaded | License |
| --- | --- | --- |
| [HTMX](https://htmx.org/) 1.9.12 | cdnjs | BSD 2-Clause |
| [GSAP](https://gsap.com/) 3.12.5 and ScrollTrigger | cdnjs | GreenSock standard license |
| [Bootstrap](https://getbootstrap.com/) 5.3.3 grid (marketplace only) | `static/vendor/bootstrap-grid.min.css` | MIT, see `static/vendor/BOOTSTRAP-LICENSE.txt` |

## Python packages

From `requirements.txt` and `requirements-dev.txt`:

| Package | License |
| --- | --- |
| [Django](https://www.djangoproject.com/) 5.2 | BSD 3-Clause |
| [WhiteNoise](https://whitenoise.readthedocs.io/) | MIT |
| [Pillow](https://python-pillow.org/) | MIT-CMU (HPND) |
| [Gunicorn](https://gunicorn.org/) | MIT |
| [psycopg2-binary](https://www.psycopg.org/) | LGPL |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD 3-Clause |
| [Coverage.py](https://coverage.readthedocs.io/) | Apache 2.0 |

## Course material

The project structure follows the PBP 2026/2027 tutorials from Fasilkom UI.
