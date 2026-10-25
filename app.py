import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import sqlite3

from flask import Flask, current_app, flash, g, jsonify, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "library.db"


def _connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def bootstrap_database(db):
    """Reset the demo schema and deterministic seed data."""
    db.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    db.executescript((BASE_DIR / "seed.sql").read_text(encoding="utf-8"))
    db.commit()


def get_db():
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_database(app):
    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='students'"
        ).fetchone()
        if exists is None:
            bootstrap_database(db)


def level_for_points(points):
    points = int(points)
    if points >= 200:
        return "Platinum"
    if points >= 100:
        return "Gold"
    if points >= 50:
        return "Silver"
    return "Bronze"


def calculate_streak(completion_dates):
    """Return consecutive-day completion streak ending on the latest completion day."""
    days = sorted({
        value if isinstance(value, date) else datetime.fromisoformat(str(value)).date()
        for value in completion_dates
    })
    if not days:
        return 0
    streak = 1
    cursor = days[-1]
    for previous in reversed(days[:-1]):
        if previous == cursor - timedelta(days=1):
            streak += 1
            cursor = previous
        elif previous < cursor - timedelta(days=1):
            break
    return streak


def _progress_for_student(db, student_id):
    row = db.execute(
        """
        SELECT s.id, s.name, s.email,
               COUNT(ra.id) AS completed_count,
               COALESCE(SUM(ra.points_awarded), 0) AS points
        FROM students s
        LEFT JOIN reading_activity ra ON ra.student_id = s.id
        WHERE s.id = ?
        GROUP BY s.id
        """,
        (student_id,),
    ).fetchone()
    if row is None:
        return None
    dates = [
        item[0]
        for item in db.execute(
            "SELECT date(completed_at) FROM reading_activity WHERE student_id = ? ORDER BY completed_at",
            (student_id,),
        ).fetchall()
    ]
    badges = [
        dict(item)
        for item in db.execute(
            """
            SELECT b.code, b.name, b.description, sb.awarded_at
            FROM student_badges sb
            JOIN badges b ON b.id = sb.badge_id
            WHERE sb.student_id = ? ORDER BY sb.awarded_at, b.id
            """,
            (student_id,),
        ).fetchall()
    ]
    result = dict(row)
    result["completed_books"] = result["completed_count"]
    result["level"] = level_for_points(result["points"])
    result["streak"] = calculate_streak(dates)
    result["badges"] = badges
    return result


def _award_eligible_badges(db, student_id):
    progress = _progress_for_student(db, student_id)
    if progress is None:
        return []
    awarded = []
    rules = db.execute("SELECT * FROM badges ORDER BY threshold, id").fetchall()
    for rule in rules:
        metric_value = progress[rule["metric"]]
        if metric_value >= rule["threshold"]:
            cursor = db.execute(
                "INSERT OR IGNORE INTO student_badges (student_id, badge_id) VALUES (?, ?)",
                (student_id, rule["id"]),
            )
            if cursor.rowcount:
                awarded.append(rule["name"])
    return awarded


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=Path(os.getenv("LIBRARY_DATABASE", DEFAULT_DATABASE)),
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-library-secret"),
    )
    if config:
        app.config.update(config)
    app.teardown_appcontext(close_db)
    ensure_database(app)

    @app.cli.command("init-db")
    def init_db_command():
        bootstrap_database(get_db())
        print("Library database reset and initialised with sample data.")

    @app.get("/")
    def index():
        db = get_db()
        books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
        base_students = db.execute("SELECT id FROM students ORDER BY name").fetchall()
        students = [_progress_for_student(db, row["id"]) for row in base_students]
        students.sort(key=lambda student: (-student["points"], student["name"]))
        activity = db.execute(
            """
            SELECT ra.completed_at, s.name AS student_name,
                   b.title AS book_title, ra.points_awarded
            FROM reading_activity ra
            JOIN students s ON s.id = ra.student_id
            JOIN books b ON b.id = ra.book_id
            ORDER BY ra.completed_at DESC, ra.id DESC
            LIMIT 8
            """
        ).fetchall()
        active_loans = db.execute(
            """
            SELECT l.id, l.due_at, s.name AS student_name, b.title AS book_title
            FROM loans l
            JOIN students s ON s.id = l.student_id
            JOIN books b ON b.id = l.book_id
            WHERE l.returned_at IS NULL
            ORDER BY l.due_at, l.id
            """
        ).fetchall()
        return render_template(
            "index.html",
            books=books,
            students=students,
            activity=activity,
            active_loans=active_loans,
        )

    @app.post("/complete")
    def complete_book():
        student_id = request.form.get("student_id", type=int)
        book_id = request.form.get("book_id", type=int)
        if not student_id or not book_id:
            flash("Choose both a student and a book.", "error")
            return redirect(url_for("index"))

        db = get_db()
        book = db.execute("SELECT points_value FROM books WHERE id = ?", (book_id,)).fetchone()
        student = db.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
        if book is None or student is None:
            flash("Student or book was not found.", "error")
            return redirect(url_for("index"))

        try:
            with db:
                db.execute(
                    "INSERT INTO reading_activity (student_id, book_id, points_awarded) VALUES (?, ?, ?)",
                    (student_id, book_id, book["points_value"]),
                )
                new_badges = _award_eligible_badges(db, student_id)
        except sqlite3.IntegrityError:
            flash("That student has already completed this book; points were not awarded twice.", "error")
            return redirect(url_for("index"))

        message = f"Completion recorded (+{book['points_value']} points)."
        if new_badges:
            message += " New badge: " + ", ".join(new_badges)
        flash(message, "success")
        return redirect(url_for("index"))

    @app.post("/borrow")
    def borrow_book():
        student_id = request.form.get("student_id", type=int)
        book_id = request.form.get("book_id", type=int)
        db = get_db()
        student = db.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
        book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if student is None or book is None:
            flash("Student or book was not found.", "error")
            return redirect(url_for("index"))
        if book["available_copies"] <= 0:
            flash("No copy is currently available.", "error")
            return redirect(url_for("index"))

        due_at = (datetime.now(UTC) + timedelta(days=14)).replace(microsecond=0).isoformat()
        try:
            with db:
                db.execute(
                    "INSERT INTO loans (student_id, book_id, due_at) VALUES (?, ?, ?)",
                    (student_id, book_id, due_at),
                )
                cursor = db.execute(
                    "UPDATE books SET available_copies = available_copies - 1 WHERE id = ? AND available_copies > 0",
                    (book_id,),
                )
                if cursor.rowcount != 1:
                    raise sqlite3.IntegrityError("copy no longer available")
        except sqlite3.IntegrityError:
            flash("This loan could not be created (already borrowed or no copy available).", "error")
            return redirect(url_for("index"))
        flash("Book borrowed for 14 days.", "success")
        return redirect(url_for("index"))

    @app.post("/return/<int:loan_id>")
    def return_book(loan_id):
        db = get_db()
        loan = db.execute(
            "SELECT id, book_id FROM loans WHERE id = ? AND returned_at IS NULL", (loan_id,)
        ).fetchone()
        if loan is None:
            flash("Active loan was not found.", "error")
            return redirect(url_for("index"))
        with db:
            db.execute("UPDATE loans SET returned_at = CURRENT_TIMESTAMP WHERE id = ?", (loan_id,))
            db.execute(
                "UPDATE books SET available_copies = available_copies + 1 WHERE id = ? AND available_copies < total_copies",
                (loan["book_id"],),
            )
        flash("Book returned and inventory updated.", "success")
        return redirect(url_for("index"))

    @app.get("/api/students/<int:student_id>/progress")
    def student_progress(student_id):
        progress = _progress_for_student(get_db(), student_id)
        if progress is None:
            return jsonify({"error": "student not found"}), 404
        return jsonify(progress)

    @app.get("/api/catalogue")
    def catalogue():
        rows = [dict(row) for row in get_db().execute("SELECT * FROM books ORDER BY title").fetchall()]
        return jsonify({"count": len(rows), "books": rows})

    @app.get("/health")
    def health():
        get_db().execute("SELECT 1").fetchone()
        return jsonify({"status": "ok", "service": "gamified-library-system"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
