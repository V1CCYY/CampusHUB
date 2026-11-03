"""Acesso ao MySQL/TiDB com POOL de conexões compartilhado entre threads.

Cada requisição pega uma conexão já aberta do pool (sem novo handshake TLS) e devolve.
Funciona no servidor de desenvolvimento do Flask, no gunicorn (gthread) e na Vercel.

Melhorias para hospedagem (Render + TiDB Cloud):
- Conexão parada há muito tempo é descartada ANTES de usar (o TiDB/proxy derruba conexões
  ociosas; antes isso gerava erro/lentidão na 1ª requisição depois de um tempo sem uso).
- Qualquer erro de conexão (não só "is_connected() == False") abre uma conexão nova e repete a
  consulta uma vez.
- O pool é "aquecido" em segundo plano ao iniciar, então a 1ª página não paga o handshake TLS.
- Consultas lentas (> 1s) aparecem em Render > Logs com o trecho do SQL.
"""
import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import mysql.connector

from config import DB_CONFIG

log = logging.getLogger("campushub.db")

# autocommit=True: conexão reaproveitada não pode manter transação aberta (leitura "congelada").
_CONFIG = {**DB_CONFIG, "autocommit": True, "connection_timeout": 10}
_MAX_OCIOSAS = 8
_OCIOSA_MAX_SEG = 120      # conexão parada mais que isso é descartada em vez de reaproveitada
_LENTA_SEG = 1.0           # acima disso a consulta é registrada no log
_pool = queue.LifoQueue()  # itens: (conexao, instante_em_que_foi_devolvida)
_executor = ThreadPoolExecutor(max_workers=4)

# Erros em que vale abrir uma conexão nova e repetir (conexão caiu / foi derrubada pelo servidor).
_ERROS_CONEXAO = (
    mysql.connector.errors.InterfaceError,
    mysql.connector.errors.OperationalError,
    ConnectionError,
    BrokenPipeError,
    TimeoutError,
)
_ERRNOS_CONEXAO = {2006, 2013, 2055, 2003, 1927, 1053, 1317}


def _nova():
    return mysql.connector.connect(**_CONFIG)


def _fechar(conn):
    try:
        conn.close()
    except Exception:
        pass


def get_db():
    """Pega uma conexão do pool (ou abre uma). Quem usa direto deve chamar release()."""
    while True:
        try:
            conn, desde = _pool.get_nowait()
        except queue.Empty:
            return _nova()
        if time.monotonic() - desde > _OCIOSA_MAX_SEG:
            _fechar(conn)  # provavelmente já derrubada pelo servidor
            continue
        return conn


def release(conn):
    if conn is None:
        return
    if _pool.qsize() < _MAX_OCIOSAS:
        _pool.put((conn, time.monotonic()))
    else:
        _fechar(conn)


def _erro_de_conexao(exc, conn):
    if isinstance(exc, _ERROS_CONEXAO) or getattr(exc, "errno", None) in _ERRNOS_CONEXAO:
        return True
    try:
        return not conn.is_connected()
    except Exception:
        return True


def query(sql, params=None, fetchone=False, commit=False):
    """Executa uma query e devolve os resultados como lista de dicts."""
    conn = get_db()
    inicio = time.monotonic()
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
            gasto = time.monotonic() - inicio
            if gasto > _LENTA_SEG:
                log.warning("consulta lenta (%.2fs): %s", gasto, " ".join(sql.split())[:140])
            return last_id if commit else result
        except Exception as exc:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if not _erro_de_conexao(exc, conn):
                release(conn)  # erro de SQL de verdade: a conexão está boa, repassa o erro
                raise
            _fechar(conn)
            if tentativa == 2:
                raise
            log.warning("conexão do pool estava velha (%s); abrindo uma nova", exc)
            conn = _nova()


def query_many(consultas):
    """Roda várias consultas ao mesmo tempo. consultas = [(sql, params), ...] -> lista de resultados."""
    futuros = [_executor.submit(query, sql, params) for sql, params in consultas]
    return [f.result() for f in futuros]


def _aquecer(qtd=2):
    """Abre algumas conexões em segundo plano para a 1ª página não pagar o handshake TLS."""
    try:
        conns = [_nova() for _ in range(qtd)]
        for c in conns:
            release(c)
        log.info("pool aquecido com %d conexões", qtd)
    except Exception as exc:  # banco fora do ar no boot não pode derrubar o site
        log.warning("não foi possível aquecer o pool: %s", exc)


def init_app(app):
    threading.Thread(target=_aquecer, daemon=True).start()
    return app
