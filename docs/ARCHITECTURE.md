# Architecture

## System overview

```mermaid
flowchart LR
    U[Student / Librarian] --> W[Flask Web App]
    W --> C[Library Catalogue]
    W --> G[Gamification Logic]
    W --> D[(SQLite Database)]
    G --> D
    D --> L[Leaderboard]
    D --> A[Reading Activity]
```

## Data model

```mermaid
erDiagram
    STUDENTS ||--o{ READING_ACTIVITY : completes
    BOOKS ||--o{ READING_ACTIVITY : recorded_in
    STUDENTS {
      int id PK
      string name
      string email
      int points
    }
    BOOKS {
      int id PK
      string title
      string author
      string genre
      int points_value
    }
    READING_ACTIVITY {
      int id PK
      int student_id FK
      int book_id FK
      datetime completed_at
      int points_awarded
    }
```

## Main workflow
1. User opens the dashboard.
2. Flask reads books, students and recent activity from SQLite.
3. User selects a student and completed book.
4. The application validates both records.
5. The book's point value is written to `reading_activity`.
6. The student's cumulative points are updated.
7. The leaderboard refreshes using database totals.

## Design decisions
- Flask keeps the prototype small and understandable.
- SQLite makes the project runnable without external infrastructure.
- A separate activity table preserves a history of completed reading rather than storing only totals.
- Point values are stored on books, allowing differentiated rewards.
