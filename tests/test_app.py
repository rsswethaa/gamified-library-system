import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import app as library_app


class LibraryAppTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "library-test.db"
        self.app = library_app.create_app(
            {
                "TESTING": True,
                "DATABASE": self.database,
                "SECRET_KEY": "test-secret",
                "DEMO_ADMIN_PASSWORD": "admin-test",
                "DEMO_STUDENT_PASSWORD": "student-test",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def set_csrf(self):
        with self.client.session_transaction() as session:
            session["_csrf_token"] = "test-csrf"
        return "test-csrf"

    def login(self, username="admin", password="admin-test"):
        token = self.set_csrf()
        return self.client.post(
            "/login",
            data={"username": username, "password": password, "csrf_token": token},
            follow_redirects=True,
        )

    def post(self, path, data):
        token = self.set_csrf()
        data = {**data, "csrf_token": token}
        return self.client.post(path, data=data)

    def test_dashboard_requires_login_and_users_exist(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Gamified Library System", response.data)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2)
            columns = [row[1] for row in db.execute("PRAGMA table_info(students)")]
        self.assertNotIn("points", columns)

    def test_csrf_required(self):
        self.login()
        response = self.client.post("/complete", data={"student_id": 1, "book_id": 2})
        self.assertEqual(response.status_code, 400)

    def test_completion_points_are_derived_and_duplicate_is_blocked(self):
        self.login()
        self.post("/complete", {"student_id": 1, "book_id": 2})
        progress = self.client.get("/api/students/1/progress").get_json()
        self.assertEqual(progress["points"], 15)
        second = self.post("/complete", {"student_id": 1, "book_id": 2})
        self.assertEqual(second.status_code, 302)
        progress = self.client.get("/api/students/1/progress").get_json()
        self.assertEqual(progress["points"], 15)

    def test_first_completion_awards_badge(self):
        self.login()
        self.post("/complete", {"student_id": 1, "book_id": 1})
        progress = self.client.get("/api/students/1/progress").get_json()
        self.assertEqual([badge["code"] for badge in progress["badges"]], ["FIRST_FINISH"])

    def test_borrow_and_return_updates_inventory(self):
        self.login()
        with sqlite3.connect(self.database) as db:
            before = db.execute("SELECT available_copies FROM books WHERE id = 1").fetchone()[0]
        self.post("/borrow", {"student_id": 1, "book_id": 1})
        with sqlite3.connect(self.database) as db:
            loan = db.execute("SELECT id FROM loans WHERE student_id = 1 AND book_id = 1 AND returned_at IS NULL").fetchone()
            after_borrow = db.execute("SELECT available_copies FROM books WHERE id = 1").fetchone()[0]
        self.assertEqual(after_borrow, before - 1)
        self.post(f"/return/{loan[0]}", {})
        with sqlite3.connect(self.database) as db:
            after_return = db.execute("SELECT available_copies FROM books WHERE id = 1").fetchone()[0]
        self.assertEqual(after_return, before)

    def test_student_cannot_act_for_another_student(self):
        self.login("aarav", "student-test")
        response = self.post("/complete", {"student_id": 2, "book_id": 1})
        self.assertEqual(response.status_code, 403)
        own = self.post("/complete", {"student_id": 1, "book_id": 1})
        self.assertEqual(own.status_code, 302)
        self.assertEqual(self.client.get("/api/students/2/progress").status_code, 403)

    def test_duplicate_active_loan_is_blocked(self):
        self.login()
        self.post("/borrow", {"student_id": 1, "book_id": 1})
        self.post("/borrow", {"student_id": 1, "book_id": 1})
        with sqlite3.connect(self.database) as db:
            active = db.execute("SELECT COUNT(*) FROM loans WHERE student_id = 1 AND book_id = 1 AND returned_at IS NULL").fetchone()[0]
        self.assertEqual(active, 1)

    def test_level_and_streak_helpers(self):
        self.assertEqual(library_app.level_for_points(50), "Silver")
        self.assertEqual(library_app.level_for_points(100), "Gold")
        self.assertEqual(library_app.calculate_streak([date(2026,10,1), date(2026,10,2), date(2026,10,3)]), 3)

    def test_health_and_catalogue_api(self):
        self.assertEqual(self.client.get("/health").get_json()["status"], "ok")
        self.assertEqual(self.client.get("/api/catalogue").status_code, 302)
        self.login()
        catalogue = self.client.get("/api/catalogue").get_json()
        self.assertEqual(catalogue["count"], 4)


if __name__ == "__main__":
    unittest.main()
