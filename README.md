# Gamified Library System

> **Portfolio reconstruction:** This is a modern rebuild based on the verified academic project description in my CV. It is not presented as the exact archived source code from the original submission.

A web application that combines basic library management with gamification to encourage students to read more consistently.

## Core features
- Browse books
- Record completed reading
- Award points for reading activity
- Display a leaderboard
- Store students, books and reading history in a relational database
- Responsive student-friendly interface

## Technology
Python · Flask · SQLite · HTML · CSS

## Repository contents
- `app.py` — application logic
- `schema.sql` — relational database schema
- `seed.sql` — sample data
- `templates/` — web interface
- `static/` — styling
- `docs/ARCHITECTURE.md` — system and data-flow diagram
- `docs/REPORT.md` — project report
- `docs/TESTING.md` — testing plan

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app init-db
flask --app app run
```

Open `http://127.0.0.1:5000`.

## Author
Swethaa Sri Ravi Sankar — B.Tech Computer Science and Business Systems; Master of Applied Finance candidate, University of Auckland.
