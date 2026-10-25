import os
import secrets
from datetime import UTC, date, datetime, timedelta
from functools import wraps
from pathlib import Path
import sqlite3

from flask import Flask, abort, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "library.db"


def _connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def bootstrap_database(db):
    db.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    db.executescript((BASE_DIR / "seed.sql").read_text(encoding="utf-8"))
    db.commit()


def ensure_demo_users(db, admin_password, student_password):
    aarav = db.execute("SELECT id FROM students WHERE email = ?", ("aarav@example.com",)).fetchone()
    if aarav is None:
        raise RuntimeError("seed student Aarav is required for the demo account")
    users = [
        ("admin", generate_password_hash(admin_password), "ADMIN", None),
        ("aarav", generate_password_hash(student_password), "STUDENT", aarav["id"]),
    ]
    with db:
        for username, password_hash, role, student_id in users:
            existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO users (username, password_hash, role, student_id) VALUES (?, ?, ?, ?)",
                    (username, password_hash, role, student_id),
                )


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
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='students'").fetchone()
        if exists is None:
            bootstrap_database(db)
        ensure_demo_users(db, app.config["DEMO_ADMIN_PASSWORD"], app.config["DEMO_STUDENT_PASSWORD"])


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
    dates = [item[0] for item in db.execute(
        "SELECT date(completed_at) FROM reading_activity WHERE student_id = ? ORDER BY completed_at",
        (student_id,),
    ).fetchall()]
    badges = [dict(item) for item in db.execute(
        """
        SELECT b.code, b.name, b.description, sb.awarded_at
        FROM student_badges sb JOIN badges b ON b.id = sb.badge_id
        WHERE sb.student_id = ? ORDER BY sb.awarded_at, b.id
        """,
        (student_id,),
    ).fetchall()]
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
    for rule in db.execute("SELECT * FROM badges ORDER BY threshold, id").fetchall():
        if progress[rule["metric"]] >= rule["threshold"]:
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
        DEMO_ADMIN_PASSWORD=os.getenv("DEMO_ADMIN_PASSWORD", "admin-demo"),
        DEMO_STUDENT_PASSWORD=os.getenv("DEMO_STUDENT_PASSWORD", "student-demo"),
    )
    if config:
        app.config.update(config)
    app.teardown_appcontext(close_db)
    ensure_database(app)

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return get_db().execute(
            "SELECT id, username, role, student_id FROM users WHERE id = ? AND active = 1",
            (user_id,),
        ).fetchone()

    def csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user() is None:
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def authorize_student(student_id):
        user = current_user()
        if user is None:
            abort(401)
        if user["role"] == "ADMIN":
            return
        if user["student_id"] != student_id:
            abort(403)

    @app.before_request
    def protect_form_posts():
        if request.method == "POST" and not request.is_json:
            expected = session.get("_csrf_token")
            supplied = request.form.get("csrf_token")
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                abort(400, description="Invalid CSRF token")

    @app.context_processor
    def inject_security_context():
        return {"csrf_token": csrf_token, "current_user": current_user()}

    @app.cli.command("init-db")
    def init_db_command():
        db = get_db()
        bootstrap_database(db)
        ensure_demo_users(db, current_app.config["DEMO_ADMIN_PASSWORD"], current_app.config["DEMO_STUDENT_PASSWORD"])
        print("Library database reset and initialised with sample data.")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            user = get_db().execute("SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                csrf_token()
                return redirect(url_for("index"))
            flash("Invalid username or password.", "error")
        csrf_token()
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def index():
        db = get_db()
        user = current_user()
        books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
        if user["role"] == "ADMIN":
            base_students = db.execute("SELECT id FROM students ORDER BY name").fetchall()
        else:
            base_students = db.execute("SELECT id FROM students WHERE id = ?", (user["student_id"],)).fetchall()
        students = [_progress_for_student(db, row["id"]) for row in base_students]
        students.sort(key=lambda student: (-student["points"], student["name"]))
        activity_query = """
            SELECT ra.completed_at, s.name AS student_name, b.title AS book_title, ra.points_awarded
            FROM reading_activity ra JOIN students s ON s.id = ra.student_id JOIN books b ON b.id = ra.book_id
        """
        params = ()
        if user["role"] != "ADMIN":
            activity_query += " WHERE ra.student_id = ?"
            params = (user["student_id"],)
        activity_query += " ORDER BY ra.completed_at DESC, ra.id DESC LIMIT 8"
        activity = db.execute(activity_query, params).fetchall()
        loan_query = """
            SELECT l.id, l.student_id, l.due_at, s.name AS student_name, b.title AS book_title
            FROM loans l JOIN students s ON s.id = l.student_id JOIN books b ON b.id = l.book_id
            WHERE l.returned_at IS NULL
        """
        loan_params = ()
        if user["role"] != "ADMIN":
            loan_query += " AND l.student_id = ?"
            loan_params = (user["student_id"],)
        loan_query += " ORDER BY l.due_at, l.id"
        active_loans = db.execute(loan_query, loan_params).fetchall()
        return render_template("index.html", books=books, students=students, activity=activity, active_loans=active_loans)

    @app.post("/complete")
    @login_required
    def complete_book():
        student_id = request.form.get("student_id", type=int)
        book_id = request.form.get("book_id", type=int)
        if not student_id or not book_id:
            flash("Choose both a student and a book.", "error")
            return redirect(url_for("index"))
        authorize_student(student_id)
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
    @login_required
    def borrow_book():
        student_id = request.form.get("student_id", type=int)
        book_id = request.form.get("book_id", type=int)
        if not student_id or not book_id:
            abort(400)
        authorize_student(student_id)
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
                db.execute("INSERT INTO loans (student_id, book_id, due_at) VALUES (?, ?, ?)", (student_id, book_id, due_at))
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
    @login_required
    def return_book(loan_id):
        db = get_db()
        loan = db.execute("SELECT id, student_id, book_id FROM loans WHERE id = ? AND returned_at IS NULL", (loan_id,)).fetchone()
        if loan is None:
            flash("Active loan was not found.", "error")
            return redirect(url_for("index"))
        authorize_student(loan["student_id"])
        with db:
            db.execute("UPDATE loans SET returned_at = CURRENT_TIMESTAMP WHERE id = ?", (loan_id,))
            db.execute(
                "UPDATE books SET available_copies = available_copies + 1 WHERE id = ? AND available_copies < total_copies",
                (loan["book_id"],),
            )
        flash("Book returned and inventory updated.", "success")
        return redirect(url_for("index"))

    @app.get("/api/students/<int:student_id>/progress")
    @login_required
    def student_progress(student_id):
        authorize_student(student_id)
        progress = _progress_for_student(get_db(), student_id)
        if progress is None:
            return jsonify({"error": "student not found"}), 404
        return jsonify(progress)

    @app.get("/api/catalogue")
    @login_required
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
