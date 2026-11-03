"""Cria índices no banco para as consultas do painel ficarem rápidas (rode UMA vez; pode repetir sem problema)."""
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

INDICES = [
    ("usuarios", "idx_usuarios_criado_por", "criado_por"),
    ("salas", "idx_salas_criado_por", "criado_por"),
    ("pecas", "idx_pecas_criado_por", "criado_por"),
    ("requisicoes", "idx_req_solicitante_data", "solicitante_id, data_solicitacao"),
    ("movimentacoes", "idx_mov_peca_data", "peca_id, data_hora"),
    ("logs", "idx_logs_usuario_data", "usuario_id, data_hora"),
]

cfg = dict(
    host=os.environ["DB_HOST"],
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ.get("DB_NAME", "campushub"),
)
if os.environ.get("DB_SSL", "false").lower() == "true":
    from ssl_util import achar_ca
    cfg["ssl_ca"] = achar_ca()
    cfg["ssl_verify_cert"] = True

conn = mysql.connector.connect(**cfg)
cur = conn.cursor()
for tabela, nome, colunas in INDICES:
    try:
        cur.execute(f"CREATE INDEX {nome} ON {tabela} ({colunas})")
        print(f"criado   {nome}")
    except mysql.connector.Error as e:
        if e.errno == 1061:  # Duplicate key name
            print(f"ja existe {nome}")
        else:
            print(f"FALHOU   {nome}: {e}")
conn.commit()
cur.close()
conn.close()
print("Pronto.")
