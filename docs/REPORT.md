# Project Report — Gamified Library System

## 1. Problem statement
Traditional library-management tools are effective at cataloguing books and transactions, but they do not necessarily motivate students to build consistent reading habits. This project explores whether a lightweight points system can make reading activity more visible and engaging.

## 2. Objective
Build a simple web-based library prototype that records reading completion, awards points and displays a leaderboard while preserving a clear relational data model.

## 3. Functional scope
- maintain a book catalogue
- maintain student profiles
- record a completed book
- award points based on the selected title
- retain a history of activity
- rank students by accumulated points

## 4. Implementation
The portfolio rebuild uses Flask for the application layer and SQLite for persistence. The server renders a responsive HTML dashboard. Reading-completion submissions are validated against existing student and book records before points are awarded.

## 5. Database design
Three tables separate students, books and reading activity. This avoids storing repeated book/student details in transaction records and provides an auditable activity history.

## 6. Gamification logic
Each book has a configurable point value. When a student records completion, the value is copied into the activity record and added to the student's total. Storing awarded points on each activity protects the historical record if a book's point value is changed later.

## 7. Limitations
This reconstruction intentionally stays small. It does not yet include authentication, borrowing/returns, duplicate-completion controls, educator moderation, accessibility testing, or production security hardening.

## 8. Future development
- login and role-based access
- reading challenges and badges
- borrowing and return workflow
- book recommendations
- achievement analytics
- PostgreSQL deployment
- automated tests and CI
- accessible design review

## 9. Portfolio integrity
This repository is a modern reconstruction based on the verified academic project description in the author's CV. It demonstrates how the original concept can be implemented today and is not represented as the exact archived university submission.
