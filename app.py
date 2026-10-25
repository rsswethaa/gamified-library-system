from pathlib import Path
import sqlite3
from flask import Flask, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "library.db"

app = Flask(__name__)


def bootstrap_database(db):
    """Create the demo schema and sample data when the database is empty."""
    schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    seed = (BASE_DIR / "seed.sql").read_text(encoding="utf-8")
    db.executescript(schema)
    db.executescript(seed)
    db.commit()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        table_exists = g.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='students'"
        ).fetchone()
        if table_exists is None:
            bootstrap_database(g.db)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.cli.command("init-db")
def init_db_command():
    bootstrap_database(get_db())
    print("Database initialised with sample data.")


@app.route("/")
def index():
    db = get_db()
    books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
    students = db.execute("SELECT * FROM students ORDER BY points DESC, name").fetchall()
    activity = db.execute(
        """
        SELECT reading_activity.completed_at, students.name AS student_name,
               books.title AS book_title, reading_activity.points_awarded
        FROM reading_activity
        JOIN students ON students.id = reading_activity.student_id
        JOIN books ON books.id = reading_activity.book_id
        ORDER BY reading_activity.completed_at DESC
        LIMIT 8
        """
    ).fetchall()
    return render_template("index.html", books=books, students=students, activity=activity)


@app.post("/complete")
def complete_book():
    student_id = request.form.get("student_id", type=int)
    book_id = request.form.get("book_id", type=int)
    if not student_id or not book_id:
        return redirect(url_for("index"))

    db = get_db()
    book = db.execute("SELECT points_value FROM books WHERE id = ?", (book_id,)).fetchone()
    student = db.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
    if book is None or student is None:
        return redirect(url_for("index"))

    points = book["points_value"]
    db.execute(
        "INSERT INTO reading_activity (student_id, book_id, points_awarded) VALUES (?, ?, ?)",
        (student_id, book_id, points),
    )
    db.execute("UPDATE students SET points = points + ? WHERE id = ?", (points, student_id))
    db.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
