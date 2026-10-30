# Urban Farming Community and Local Harvest Marketplace

**Platform-Based Programming — Midterm Group Project**
Faculty of Computer Science, Universitas Indonesia
Odd Semester 2026/2027

This README describes the planned application and division of work for Checkpoint 1. The features below are implementation commitments, not claims of completed functionality.

## Project Links

| Resource | Link or status |
| --- | --- |
| Shared Git repository | https://github.com/paramitasan/urFunFarming/ |
| Figma design | https://www.figma.com/design/rDovEM0bwhNE0xkgKZhwV4/Farmerzz?node-id=0-1&t=uf8tBdtybxcNt5PB-1 |
| Deployed application | https://paramita-santoso-urfunfarming.pws.cs.ui.ac.id/ |

## Application Description and Problem

Our application will connect small urban growers with other growers and people interested in locally grown produce. It will combine a plant journal, community questions, weather information, and a marketplace for arranging local collection.

We focus on a practical scenario: a resident grows vegetables or herbs on a balcony, rooftop, small garden, or hydroponic setup. The resident wants to record plant development, ask other growers for advice, and offer available produce to people nearby. A potential buyer needs a way to discover these offers, check their details, and contact the grower about collection.

Our starting problem hypothesis is that these activities can be difficult to coordinate when progress notes, advice, and produce offers are spread across separate conversations and tools. The application will bring them together around the same gardens and growers.

The intended benefit is to support participation in urban farming, make local produce easier to discover, and give growers an additional way to share or sell surplus harvests. These are intended benefits; we do not claim that the application has already reduced waste or environmental impact.

The marketplace will be post-based. Growers post about their harvest, and upon seeing the post, interested buyers can contact growers through their profile to arrange payment and collection.

## Target Users and Roles

| Role | Planned access and activities |
| --- | --- |
| Visitor | Browse public garden summaries, available produce listings, and community question titles. |
| Registered grower | Manage their gardens, plantings, journal entries, harvest listings, and care tasks; participate in discussions and respond to requests for their listings. |
| Registered buyer | View contact information available to members, submit and manage their own collection requests, and participate in community discussions. |
| Administrator | Moderate inappropriate content and manage accounts through the administration interface. |

One registered account may act as both a grower and a buyer. Signing in will not give users permission to edit other people's records. Private garden details, private journal entries, care tasks, and collection conversations will be restricted to their owners or relevant participants.

## Group Members and Work Allocation

Each member will own exactly one of the six modules below, including its models, forms, views, URLs, templates, permissions, API filters, interactive behavior, and tests.

| Full name | NPM | Assigned module |
| --- | --- | --- |
| Angin Putih Ranulaksmi Tsurayya Hapsoro | 2506557936 | 3 |
| Azkal Azkiya Arifi Putra | 2506636991 | 2 |
| Marcel Mikula | 2606816592 | 4 |
| Muhamad Idris Kamal | 2506637073 | 1 |
| Paramita Santoso | 2506554171 | 6 |
| Tahir Ahmad | 2606816466 | 5 |

## The Six Modules

Every module will support creating, viewing, updating, and deleting its own application records. External weather observations will be retrieved and filtered, rather than edited by users.

| No. | Module | Records and responsibilities |
| --- | --- | --- |
| **1** | **Landing Page, Authentication & User Profiles** | Landing page as entry point: choose Farmer or Buyer registration (one account can be both). Profile management: display name, photo, bio, location, contact, password change. |
| **2** | **Gardens and Plantings** | Growers create and manage their growing locations and planted crops. Every plant records include a garden name, location, growing method, crop, and planting date. Public summaries introduce the grower and garden; private notes remain restricted to the owner. |
| **3** | **Plant Progress Journal** | Growers create dated progress entries linked to their own plantings, with observations, optional photographs, and a visibility setting. They can edit or delete entries and review a planting's timeline. Private entries remain visible only to their owner. This module documents progress; open questions and answers belong to Module 6. |
| **4** | **Harvest Marketplace** | Growers create and manage produce listings with a title, crop category, quantity, unit, price, availability, and collection area. Visitors can browse and filter available offers. Members can access the permitted contact details, while only the listing owner can change or delete an offer. A price of zero can represent produce offered for free. |
| **5** | **Care Planning and Weather** | Growers create and manage care tasks linked to their plantings, including an activity, planned date, notes, and completion status. They can inspect weather conditions when choosing a time and filter forecast periods using their own thresholds. Tasks are private to their owner. The editable care tasks provide the module's CRUD functionality. |
| **6** | **Community Questions and Answers** | Members create questions about growing methods, plant care, or observed problems and add answers to other members' questions. Authors can edit or delete their own questions and answers. Visitors see question titles; signed-in members can read full discussions and their weather context. Questions can reference a planting or an approximate location. |

## External Public API

We will use the [Open-Meteo Weather Forecast API](https://open-meteo.com/en/docs) for temperature, relative humidity, and precipitation at a selected location.

## Initial Data Plan

Our main dataset will contain **at least 50 harvest listings** in the deployed application. Each listing will be an individual offer with its own grower, produce description, quantity, price, and availability.

The initial seed will use ten fictional grower profiles with five listings each. Additional gardens, plantings, journal entries, and community questions will demonstrate the other modules. The seeded content will be identified as demonstration data and loaded through reproducible fixtures or a management command.

Weather data and produce listings serve different purposes: Open-Meteo provides the external API integration, while the seeded harvest listings populate the marketplace.

## Integration and Development Approach

The planned stack is Django with its MVT structure, Django templates, Bootstrap for responsive components, and HTMX for interactions such as filtering, form feedback, and list updates.

Authentication, common templates, API utilities, repository setup, and deployment are shared integration work. They do not replace any member's responsibility for a complete module. Members will use feature branches and pull requests, review changes together, and integrate their work into one application.

Tests will cover successful and invalid form submissions, complete CRUD behavior, access restrictions, filtering, missing records, and API failures. Automated tests will use mocked weather responses. The project will target at least 80% code coverage, alongside manual checks of the main user journeys and mobile layout.

## Marketplace implementation (Module 4)

The `feat/harvest-marketplace` branch implements Marcel's harvest listing CRUD, authenticated contact visibility, owner permissions, interactive filtering, and Open-Meteo pickup-time filtering using the shared group design. It also connects the landing-page offers to the marketplace database.

For setup, the repeatable **50-listing seed command**, JSON endpoints, verification, and the group integration checklist, see [docs/marketplace.md](docs/marketplace.md). The remaining modules and the final deployed integration must still be verified by the group.

## Demo data

`python manage.py seed_demo` fills every module with demo content set in Jakarta and Depok: 8 users with profiles, 16 gardens (public and private) with 50 plantings, journal entries, 30 care tasks, 54 market listings and 15 forum questions with answers. Photos are left empty, so the "no photo" tiles show. The data is the same on every run, and dates are counted back from the day you run it.

**Locally**, after `python manage.py migrate`:

```
python manage.py seed_demo
```

**On PWS**, set the `DEMO_PASSWORD` environment variable first, then run the same command wherever you run `migrate` for the deployment. Add `--force` if `DEBUG` is off there.

| Flag | What it does |
| --- | --- |
| *(none)* | Creates whatever is missing. Running it again adds no duplicates. |
| `--reset` | Deletes every account whose username starts with `demo_`, and everything those accounts own, then seeds again. Other accounts are never touched. This also removes the `demo_` accounts made by `seed_journal` and `seed_marketplace`. |
| `--force` | Lets the command run while `DEBUG` is off. Without it, the command refuses. |

All demo users share one password: the `DEMO_PASSWORD` setting, which is read from the environment and defaults to `tanam-sayur-demo` for local use.

| Username | Role | Area |
| --- | --- | --- |
| `demo_ayu` | Grower | Tebet, Jakarta Selatan |
| `demo_bima` | Grower | Beji, Depok |
| `demo_rina` | Grower | Pulogadung, Jakarta Timur |
| `demo_dimas` | Grower | Pancoran Mas, Depok |
| `demo_nadia` | Grower and buyer | Beji, Depok |
| `demo_yoga` | Grower and buyer | Jagakarsa, Jakarta Selatan |
| `demo_sekar` | Buyer | Tebet, Jakarta Selatan |
| `demo_fajar` | Buyer | Beji, Depok |

## AI Assistance

ChatGPT assisted with drafting this initial project description and module plan. The group will review the proposed scope and allocation together and will be responsible for implementation decisions, verification, and explaining the completed application.

For Module 4, ChatGPT also assisted with the Django implementation, adaptation to the shared Figma design, tests, and integration documentation. See the module guide for the implementation scope and verification.
