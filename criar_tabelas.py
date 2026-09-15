import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.environ.get("DB_HOST"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER"),
    password=os.environ.get("DB_PASSWORD"),
    ssl_ca=os.path.join(os.path.dirname(__file__), "certs", "ca.pem"),
    ssl_verify_cert=True,
)

with open(os.path.join(os.path.dirname(__file__), "database.sql"), "r", encoding="utf-8") as f:
    sql_script = f.read()

cursor = conn.cursor()
for statement in sql_script.split(";"):
    statement = statement.strip()
    if statement:
        cursor.execute(statement)

conn.commit()
print("Tabelas criadas com sucesso!")
cursor.close()
conn.close()
