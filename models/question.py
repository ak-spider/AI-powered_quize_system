class Question:
    @staticmethod
    def by_round(db, round_number):
        return db.execute(
            "SELECT * FROM questions WHERE round_number=? ORDER BY id",
            (round_number,),
        ).fetchall()

    @staticmethod
    def all(db):
        return db.execute("SELECT * FROM questions ORDER BY round_number, id").fetchall()

    @staticmethod
    def get(db, qid):
        return db.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()

    @staticmethod
    def create(db, round_number, text, a, b, c, d, correct):
        db.execute(
            "INSERT INTO questions (round_number,text,option_a,option_b,option_c,option_d,correct_option) VALUES (?,?,?,?,?,?,?)",
            (round_number, text, a, b, c, d, correct.upper()),
        )
        db.commit()

    @staticmethod
    def delete(db, qid):
        db.execute("DELETE FROM questions WHERE id=?", (qid,))
        db.commit()

    @staticmethod
    def rounds(db):
        rows = db.execute("SELECT DISTINCT round_number FROM questions ORDER BY round_number").fetchall()
        return [r["round_number"] for r in rows]
