INSERT INTO students (name, email) VALUES
('Aarav', 'aarav@example.com'),
('Meera', 'meera@example.com'),
('Liam', 'liam@example.com');

INSERT INTO books (title, author, genre, points_value, total_copies, available_copies) VALUES
('The Alchemist', 'Paulo Coelho', 'Fiction', 10, 2, 2),
('Atomic Habits', 'James Clear', 'Self Development', 15, 2, 2),
('A Brief History of Time', 'Stephen Hawking', 'Science', 20, 1, 1),
('The Psychology of Money', 'Morgan Housel', 'Finance', 15, 2, 2);

INSERT INTO badges (code, name, description, metric, threshold) VALUES
('FIRST_FINISH', 'First Finish', 'Complete your first book.', 'completed_books', 1),
('BOOKWORM', 'Bookworm', 'Complete three different books.', 'completed_books', 3),
('CENTURY', 'Century Reader', 'Earn 100 reading points.', 'points', 100);
