# Testing Plan

## Functional tests

| Test | Expected result |
|---|---|
| Initialise database | Tables and seed data are created without errors |
| Load dashboard | Books and students render successfully |
| Record valid completion | Activity row is created and student points increase |
| Missing form value | User returns safely to dashboard with no database change |
| Invalid student or book | No points are awarded |
| Leaderboard ordering | Highest points appear first |

## Data-integrity checks
- `student_id` and `book_id` must reference existing records.
- Awarded points should match the book value at completion time.
- Student totals should equal prior total plus newly awarded points.

## Manual UI checks
- dashboard works on narrow and desktop widths
- selects and button remain keyboard accessible
- long book titles do not break layout
- empty activity state is understandable

## Future automated testing
A production version should add `pytest` coverage for routes, database operations and edge cases, plus CI on every pull request.
