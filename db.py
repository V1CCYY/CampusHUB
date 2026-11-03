"""Acesso ao MySQL/TiDB com POOL de conexões compartilhado entre threads.

Cada requisição pega uma conexão já aberta do pool (sem novo handshake TLS) e devolve.
Funciona no servidor de desenvolvimento do Flask (uma thread por requisição), no gunicorn
e na Vercel. Conexão derrubada por inatividade é descartada e a consulta repetida uma vez.
"""
import queue
from concurrent.futures import ThreadPoolExecutor

import mysql.connector

from config import DB_CONFIG

# autocommit=True: conexão reaproveitada não pode manter transação aberta (leitura "congelada").
_CONFIG = {**DB_CONFIG, "autocommit": True, "connection_timeout": 10}
_MAX_OCIOSAS = 8
_pool = queue.LifoQueue()
_executor = ThreadPoolExecutor(max_workers=4)


def _nova():
    return mysql.connector.connect(**_CONFIG)


def get_db():
    """Pega uma conexão do pool (ou abre uma). Quem usa direto deve chamar release()."""
    try:
        return _pool.get_nowait()
    except queue.Empty:
        return _nova()


def release(conn):
    if conn is None:
        return
    if _pool.qsize() < _MAX_OCIOSAS:
        _pool.put(conn)
    else:
        _fechar(conn)


def _fechar(conn):
    try:
        conn.close()
    except Exception:
        pass


def query(sql, params=None, fetchone=False, commit=False):
    """Executa uma query e devolve os resultados como lista de dicts."""
    conn = get_db()
    for tentativa in (1, 2):
        cursor = None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, params or ())
            result = None
            if cursor.description:
                result = cursor.fetchone() if fetchone else cursor.fetchall()
            if commit:
                conn.commit()
            last_id = cursor.lastrowid
            cursor.close()
            release(conn)
            return last_id if commit else result
        except Exception:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            try:
                viva = conn.is_connected()
            except Exception:
                viva = False
            if viva:
                release(conn)
                raise
            _fechar(conn)
            if tentativa == 2:
                raise
            conn = _nova()  # a do pool estava velha: abre uma fresca e repete


def query_many(consultas):
    """Roda várias consultas ao mesmo tempo. consultas = [(sql, params), ...] -> lista de resultados."""
    futuros = [_executor.submit(query, sql, params) for sql, params in consultas]
    return [f.result() for f in futuros]


def init_app(app):
    return app
