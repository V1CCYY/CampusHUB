"""Diagnóstico do banco do CampusHub (TiDB Cloud) - rode no SEU PC, na pasta do projeto.

    python diagnostico.py              -> só mostra o que está certo/errado (não altera nada)
    python diagnostico.py --corrigir   -> cria tabelas/colunas/índices que estiverem faltando

O que ele faz:
 1. mede a latência até o TiDB (conexão + ida e volta de uma consulta simples);
 2. confere se todas as tabelas e colunas do database.sql existem;
 3. roda as MESMAS consultas das páginas Inventário, Requisições e Backup e mostra o erro
    exato (se houver) e quanto tempo cada uma levou;
 4. confere os índices de criar_indices.py.

Nunca apaga nada: o modo --corrigir só usa CREATE TABLE IF NOT EXISTS, ADD COLUMN e CREATE INDEX.
Usa o mesmo .env do projeto (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_SSL...).
"""
import os
import re
import sys
import time

import mysql.connector
from dotenv import load_dotenv

load_dotenv()
CORRIGIR = "--corrigir" in sys.argv
AQUI = os.path.dirname(os.path.abspath(__file__))
OK, ERRO, AVISO = "[ OK ]", "[ERRO]", "[ !! ]"

INDICES = [
    ("usuarios", "idx_usuarios_criado_por", "criado_por"),
    ("salas", "idx_salas_criado_por", "criado_por"),
    ("pecas", "idx_pecas_criado_por", "criado_por"),
    ("requisicoes", "idx_req_solicitante_data", "solicitante_id, data_solicitacao"),
    ("movimentacoes", "idx_mov_peca_data", "peca_id, data_hora"),
    ("logs", "idx_logs_usuario_data", "usuario_id, data_hora"),
]


def conectar():
    cfg = dict(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "4000")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "campushub"),
        connection_timeout=15,
        autocommit=True,
    )
    if os.environ.get("DB_SSL", "false").lower() == "true":
        from ssl_util import achar_ca
        cfg["ssl_ca"] = achar_ca()
        cfg["ssl_verify_cert"] = True
    return mysql.connector.connect(**cfg)


def esquema_esperado():
    """Lê o database.sql e devolve {tabela: (ddl_create, {coluna: definicao})}."""
    with open(os.path.join(AQUI, "database.sql"), "r", encoding="utf-8") as f:
        sql = f.read()
    sql = re.sub(r"DELIMITER \$\$.*?DELIMITER ;", "", sql, flags=re.S)  # TiDB não tem triggers
    esperado = {}
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        m = re.match(r"CREATE TABLE\s+(\w+)\s*\((.*)\)\s*ENGINE", stmt, flags=re.S | re.I)
        if not m:
            continue
        tabela, corpo = m.group(1), m.group(2)
        colunas = {}
        for linha in corpo.split("\n"):
            linha = linha.strip().rstrip(",")
            if not linha or re.match(r"(CONSTRAINT|FOREIGN|UNIQUE|PRIMARY|KEY|INDEX|REFERENCES|ON)\b", linha, re.I):
                continue
            nome, _, definicao = linha.partition(" ")
            colunas[nome] = definicao.strip()
        ddl = re.sub(r"CREATE TABLE", "CREATE TABLE IF NOT EXISTS", stmt, count=1, flags=re.I)
        esperado[tabela] = (ddl, colunas)
    return esperado


def main():
    print("=== Diagnóstico CampusHub ===")
    print(f"Banco: {os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT', '4000')} / "
          f"{os.environ.get('DB_NAME', 'campushub')}  (modo: {'CORRIGIR' if CORRIGIR else 'somente leitura'})\n")

    # 1) latência
    t0 = time.perf_counter()
    try:
        conn = conectar()
    except Exception as e:
        print(f"{ERRO} não conectou ao banco: {e}")
        print("      Confira o .env (host, usuário, senha) e se o IP está liberado no TiDB Cloud.")
        return 1
    t_conexao = time.perf_counter() - t0
    cur = conn.cursor(dictionary=True)
    rtts = []
    for _ in range(5):
        t = time.perf_counter()
        cur.execute("SELECT 1")
        cur.fetchall()
        rtts.append(time.perf_counter() - t)
    rtt = sum(rtts) / len(rtts) * 1000
    print(f"{OK} conexão (com TLS): {t_conexao * 1000:.0f} ms | ida e volta por consulta: {rtt:.0f} ms (do seu PC)")
    print("      (No Render, essa ida e volta depende da REGIÃO do serviço: o TiDB está em us-east-1,")
    print("       então o ideal é o Render em 'Virginia (US East)'.)\n")

    # 2) tabelas e colunas
    esperado = esquema_esperado()
    cur.execute("SELECT table_name AS t, column_name AS c FROM information_schema.columns "
                "WHERE table_schema = DATABASE()")
    existentes = {}
    for r in cur.fetchall():
        existentes.setdefault(r["t"].lower(), set()).add(r["c"].lower())

    problemas = 0
    for tabela, (ddl, colunas) in esperado.items():
        if tabela not in existentes:
            problemas += 1
            print(f"{ERRO} tabela '{tabela}' NÃO existe")
            if CORRIGIR:
                cur.execute(ddl)
                print(f"      -> criada '{tabela}'")
            continue
        faltando = [c for c in colunas if c.lower() not in existentes[tabela]]
        if not faltando:
            print(f"{OK} tabela '{tabela}' completa")
            continue
        problemas += 1
        print(f"{ERRO} tabela '{tabela}' sem as colunas: {', '.join(faltando)}")
        if CORRIGIR:
            for col in faltando:
                definicao = re.sub(r"\b(PRIMARY KEY|AUTO_INCREMENT)\b", "", colunas[col], flags=re.I).strip()
                try:
                    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {definicao}")
                    print(f"      -> coluna '{col}' adicionada")
                except mysql.connector.Error as e:
                    print(f"      -> não consegui adicionar '{col}': {e}")

    # 3) as consultas reais das páginas
    print("\n--- Consultas das páginas ---")
    cur.execute("SELECT id FROM usuarios WHERE tipo = 'admin' ORDER BY id LIMIT 1")
    adm = cur.fetchone()
    if not adm:
        print(f"{ERRO} não há nenhum usuário admin na tabela usuarios (rode criar_tabelas.py).")
        return 1
    a = adm["id"]
    paginas = {
        "Inventário TI": [("SELECT * FROM pecas WHERE criado_por = %s ORDER BY descricao", (a,))],
        "Requisições": [
            ("SELECT id, codigo, descricao, quantidade FROM pecas WHERE criado_por = %s ORDER BY descricao", (a,)),
            ("SELECT id, nome, bloco FROM salas WHERE criado_por = %s ORDER BY nome", (a,)),
            ("""SELECT r.*, u.nome AS solicitante_nome, s.nome AS sala_nome
                FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
                LEFT JOIN salas s ON s.id = r.sala_id
                WHERE u.id = %s OR u.criado_por = %s ORDER BY r.data_solicitacao DESC""", (a, a)),
        ],
        "Backup": [
            ("""SELECT 'usuarios' AS t, COUNT(*) AS n FROM usuarios WHERE id = %s OR criado_por = %s
                UNION ALL SELECT 'salas', COUNT(*) FROM salas WHERE criado_por = %s
                UNION ALL SELECT 'pecas', COUNT(*) FROM pecas WHERE criado_por = %s
                UNION ALL SELECT 'requisicoes', COUNT(*) FROM requisicoes r
                          JOIN usuarios u ON u.id = r.solicitante_id WHERE u.id = %s OR u.criado_por = %s
                UNION ALL SELECT 'movimentacoes', COUNT(*) FROM movimentacoes m
                          JOIN pecas p ON p.id = m.peca_id WHERE p.criado_por = %s""", (a,) * 7),
        ],
        "Logs": [("""SELECT l.acao, l.data_hora, u.nome FROM logs l
                     LEFT JOIN usuarios u ON u.id = l.usuario_id ORDER BY l.data_hora DESC LIMIT 50""", ())],
    }
    for pagina, consultas in paginas.items():
        for sql, params in consultas:
            t = time.perf_counter()
            try:
                cur.execute(sql, params)
                linhas = cur.fetchall()
                ms = (time.perf_counter() - t) * 1000
                marca = OK if ms < 1000 else AVISO
                print(f"{marca} {pagina}: {len(linhas)} linhas em {ms:.0f} ms")
            except mysql.connector.Error as e:
                problemas += 1
                print(f"{ERRO} {pagina}: {e}   <-- é ISSO que vira o 'Internal Server Error'")

    # 4) índices
    print("\n--- Índices ---")
    for tabela, nome, colunas in INDICES:
        cur.execute("SELECT 1 FROM information_schema.statistics WHERE table_schema = DATABASE() "
                    "AND table_name = %s AND index_name = %s LIMIT 1", (tabela, nome))
        if cur.fetchone():
            print(f"{OK} {nome}")
        elif CORRIGIR:
            try:
                cur.execute(f"CREATE INDEX {nome} ON {tabela} ({colunas})")
                print(f"{OK} {nome} criado")
            except mysql.connector.Error as e:
                print(f"{AVISO} {nome}: {e}")
        else:
            print(f"{AVISO} {nome} não existe (opcional; deixa as consultas mais rápidas)")

    cur.close()
    conn.close()
    print()
    if problemas and not CORRIGIR:
        print(f"{problemas} problema(s) encontrado(s). Rode:  python diagnostico.py --corrigir")
    elif problemas:
        print("Correções aplicadas. Rode o diagnóstico de novo para confirmar que está tudo [ OK ].")
    else:
        print("Banco OK. Se o site ainda der erro, abra Render > Logs: o traceback mostra a causa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
