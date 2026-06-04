def divide(a, b):
    # 0 나눗셈 가드 없음
    return a / b


def run_query(db, name):
    # f-string SQL 보간 — injection
    return db.execute(f"SELECT * FROM t WHERE name = '{name}'")
