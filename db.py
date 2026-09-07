import mysql.connector
from flask import g
from config import DB_CONFIG

def get_db():
    """Retorna uma conexão MySQL reaproveitada durante a mesma requisição."""
    if "db" not in g:
        g.db = mysql.connector.connect(**DB_CONFIG)
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def query(sql, params=None, fetchone=False, commit=False):
    """Executa uma query e devolve os resultados como lista de dicts."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params or ())

    result = None
    if cursor.description:
        result = cursor.fetchone() if fetchone else cursor.fetchall()

    if commit:
        conn.commit()

    last_id = cursor.lastrowid
    cursor.close()

    if commit:
        return last_id
    return result

def init_app(app):
    app.teardown_appcontext(close_db)
