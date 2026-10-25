import sqlite3
import tempfile
import unittest
from pathlib import Path

import app as library_app


class LibraryAppTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        library_app.DATABASE = Path(self.tempdir.name) / "library-test.db"
        library_app.app.config.update(TESTING=True)
        self.client = library_app.app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_home_bootstraps_database(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Gamified Library System", response.data)
        self.assertTrue(library_app.DATABASE.exists())

        with sqlite3.connect(library_app.DATABASE) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM students").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM books").fetchone()[0], 4)

    def test_completing_book_awards_points(self):
        self.client.get("/")
        with sqlite3.connect(library_app.DATABASE) as db:
            before = db.execute("SELECT points FROM students WHERE id = 1").fetchone()[0]
            points = db.execute("SELECT points_value FROM books WHERE id = 2").fetchone()[0]

        response = self.client.post("/complete", data={"student_id": 1, "book_id": 2})
        self.assertEqual(response.status_code, 302)

        with sqlite3.connect(library_app.DATABASE) as db:
            after = db.execute("SELECT points FROM students WHERE id = 1").fetchone()[0]
            activity = db.execute("SELECT COUNT(*) FROM reading_activity").fetchone()[0]

        self.assertEqual(after, before + points)
        self.assertEqual(activity, 1)


if __name__ == "__main__":
    unittest.main()
