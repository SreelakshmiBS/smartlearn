import sqlite3

# Connect to your DB
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Drop the leftover Alembic temp table if it exists
cursor.execute('DROP TABLE IF EXISTS "_alembic_tmp_Student";')

conn.commit()
conn.close()
print("Temporary Alembic table dropped successfully.")
