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
            {"TESTING": True, "DATABASE": self.database, "SECRET_KEY": "test-secret"}
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_home_bootstraps_database(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Gamified Library System", response.data)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM students").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM books").fetchone()[0], 4)
            student_columns = [row[1] for row in db.execute("PRAGMA table_info(students)")]
        self.assertNotIn("points", student_columns)

    def test_completion_points_are_derived_and_duplicate_is_blocked(self):
        response = self.client.post("/complete", data={"student_id": 1, "book_id": 2})
        self.assertEqual(response.status_code, 302)
        progress = self.client.get("/api/students/1/progress").get_json()
        self.assertEqual(progress["points"], 15)
        self.assertEqual(progress["completed_count"], 1)

        second = self.client.post(
            "/complete",
            data={"student_id": 1, "book_id": 2},
            follow_redirects=True,
        )
        self.assertIn(b"points were not awarded twice", second.data)
        progress = self.client.get("/api/students/1/progress").get_json()
        self.assertEqual(progress["points"], 15)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reading_activity").fetchone()[0], 1)

    def test_first_completion_awards_badge(self):
        self.client.post("/complete", data={"student_id": 1, "book_id": 1})
        progress = self.client.get("/api/students/1/progress").get_json()
        self.assertEqual([badge["code"] for badge in progress["badges"]], ["FIRST_FINISH"])

    def test_borrow_and_return_updates_inventory(self):
        with sqlite3.connect(self.database) as db:
            before = db.execute("SELECT available_copies FROM books WHERE id = 1").fetchone()[0]
        self.client.post("/borrow", data={"student_id": 1, "book_id": 1})
        with sqlite3.connect(self.database) as db:
            loan = db.execute(
                "SELECT id FROM loans WHERE student_id = 1 AND book_id = 1 AND returned_at IS NULL"
            ).fetchone()
            after_borrow = db.execute("SELECT available_copies FROM books WHERE id = 1").fetchone()[0]
        self.assertEqual(after_borrow, before - 1)

        self.client.post(f"/return/{loan[0]}")
        with sqlite3.connect(self.database) as db:
            after_return = db.execute("SELECT available_copies FROM books WHERE id = 1").fetchone()[0]
            returned_at = db.execute("SELECT returned_at FROM loans WHERE id = ?", (loan[0],)).fetchone()[0]
        self.assertEqual(after_return, before)
        self.assertIsNotNone(returned_at)

    def test_duplicate_active_loan_is_blocked(self):
        self.client.post("/borrow", data={"student_id": 1, "book_id": 1})
        response = self.client.post(
            "/borrow", data={"student_id": 1, "book_id": 1}, follow_redirects=True
        )
        self.assertIn(b"could not be created", response.data)
        with sqlite3.connect(self.database) as db:
            active = db.execute(
                "SELECT COUNT(*) FROM loans WHERE student_id = 1 AND book_id = 1 AND returned_at IS NULL"
            ).fetchone()[0]
        self.assertEqual(active, 1)

    def test_level_and_streak_helpers(self):
        self.assertEqual(library_app.level_for_points(0), "Bronze")
        self.assertEqual(library_app.level_for_points(50), "Silver")
        self.assertEqual(library_app.level_for_points(100), "Gold")
        self.assertEqual(library_app.level_for_points(200), "Platinum")
        self.assertEqual(
            library_app.calculate_streak([date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]),
            3,
        )

    def test_health_and_catalogue_api(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")
        catalogue = self.client.get("/api/catalogue").get_json()
        self.assertEqual(catalogue["count"], 4)
        self.assertIn("available_copies", catalogue["books"][0])


if __name__ == "__main__":
    unittest.main()
