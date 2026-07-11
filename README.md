# Quiz System

Flask-based live quiz with admin-controlled rounds, timer, and leaderboard.

## Run
```
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000

- Players: pick a team name + password (auto-registers on first login)
- Admin: http://localhost:5000/admin/login  (default `admin` / `admin123`)

## Flow
1. Teams log in → waiting page (auto-refreshes status)
2. Admin opens the current round → teams auto-redirected to quiz
3. Teams submit (or timer auto-submits) → round_finished
4. Admin closes round, advances to next, repeats
5. Admin clicks Finish Quiz → all teams see thank_you with leaderboard

DB is SQLite at `database/quiz.db`, schema in `database/quiz.sql` (auto-initialized on first run with sample questions).
