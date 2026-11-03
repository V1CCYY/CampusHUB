"""Configuração do gunicorn para o Render (lida automaticamente se estiver na raiz do projeto).

Por que assim:
- gthread: várias requisições ao mesmo tempo dentro de UM processo, compartilhando o pool de
  conexões do db.py (o worker "sync" padrão atende uma requisição por vez e deixa tudo em fila).
- 1 worker: o plano grátis do Render tem pouca CPU/memória; mais processos só competem entre si
  e cada um abriria suas próprias conexões TLS com o TiDB.
- timeout 120: a primeira visita após o site "dormir" pode passar dos 30s padrão e o gunicorn
  mataria o worker no meio da requisição.
"""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "10000")
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "8"))
timeout = 120
graceful_timeout = 30
keepalive = 75               # reaproveita a conexão com o proxy do Render
worker_tmp_dir = "/dev/shm"  # heartbeat em memória (evita travar em disco lento)

# Mostra o erro real (traceback) em Render > Logs
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
