import sqlite3


def get_user(db, user_id):
    # 신규 헬퍼 — 사용자 조회
    cur = db.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cur.fetchone()


def average(nums):
    return sum(nums) / len(nums)
