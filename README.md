# Gamified Library System

> **Portfolio reconstruction:** This is a modern rebuild based on the verified academic project description in my CV. It is not presented as the exact archived source code from the original submission.

A web application that combines basic library management with gamification to encourage students to read more consistently.

![Gamified Library System browser demo](docs/assets/library-demo.png)

## Verified status
- GitHub Actions CI: **passing**
- Fresh-clone database setup: **automatic**
- Core reading-points workflow: **tested**
- Browser demo: **rendered and visually checked in Chromium**
- Static GitHub Pages demo: available in `docs/index.html` and ready to publish

## Core features
- Browse books
- Record completed reading
- Award points for reading activity
- Display a leaderboard
- Store students, books and reading history in a relational database
- Responsive student-friendly interface

## Technology
Python · Flask · SQLite · HTML · CSS · JavaScript · GitHub Actions

## Repository contents
- `app.py` — application logic
- `schema.sql` — relational database schema
- `seed.sql` — sample data
- `tests/` — automated application tests
- `templates/` — Flask web interface
- `static/` — Flask interface styling
- `docs/index.html` — standalone interactive portfolio demo for GitHub Pages
- `docs/assets/library-demo.png` — real Chromium browser capture
- `docs/ARCHITECTURE.md` — system and data-flow diagram
- `docs/REPORT.md` — project report
- `docs/TESTING.md` — testing plan

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run
```

The app now creates its SQLite schema and sample data automatically on first run. Use `flask --app app init-db` only when you deliberately want to reset the demo database.

Open `http://127.0.0.1:5000`.

## Publish the static demo
GitHub Pages cannot be enabled by the connected GitHub App, but the deployable site is already prepared. In this repository open **Settings → Pages**, choose **Deploy from a branch**, select **main** and **/docs**, then save. The expected public URL is:

`https://rsswethaa.github.io/gamified-library-system/`

## Author
Swethaa Sri Ravi Sankar — B.Tech Computer Science and Business Systems; Master of Applied Finance candidate, University of Auckland.
