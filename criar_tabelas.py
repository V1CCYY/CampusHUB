"""Cria o banco e as tabelas no TiDB Cloud (rode UMA vez)."""
import os
import re
import mysql.connector
from dotenv import load_dotenv
from ssl_util import achar_ca

load_dotenv()

ca = achar_ca()
print("Usando certificado:", ca)

conn = mysql.connector.connect(
    host=os.environ["DB_HOST"],
    port=int(os.environ.get("DB_PORT", "4000")),
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    ssl_ca=ca,
    ssl_verify_cert=True,
)

with open(os.path.join(os.path.dirname(__file__), "database.sql"), "r", encoding="utf-8") as f:
    sql = f.read()

# TiDB NAO suporta triggers: remove o bloco DELIMITER/TRIGGER.
# O limite de 4 usuarios por admin ja e validado no app.py.
sql = re.sub(r"DELIMITER \$\$.*?DELIMITER ;", "", sql, flags=re.S)

cursor = conn.cursor()
for stmt in sql.split(";"):
    stmt = stmt.strip()
    if stmt:
        cursor.execute(stmt)
conn.commit()
print("Banco e tabelas criados com sucesso!")
cursor.close()
conn.close()
