import sqlite3

conn = sqlite3.connect("database/hospital.db")

tables = conn.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
""").fetchall()

print("Tables in database:")

for table in tables:
    table_name = table[0]

    count = conn.execute(
        f"SELECT COUNT(*) FROM [{table_name}]"
    ).fetchone()[0]

    print(table_name, ":", count, "rows")

conn.close()