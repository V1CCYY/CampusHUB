from functools import wraps
from datetime import datetime
import io
import json
import os
import re
import unicodedata
import zipfile

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, Response, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

import db
import chatbot
from config import SECRET_KEY
from equipamentos import imagem_equipamento

app = Flask(__name__, static_folder="public/static", static_url_path="/static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
app.secret_key = SECRET_KEY
db.init_app(app)

# Diagnóstico: com a variável DEBUG_ERROS=true no servidor, o erro real aparece na tela
# (em vez de "Internal Server Error"). Desligue depois de resolver.
if os.environ.get("DEBUG_ERROS", "").lower() == "true":
    import traceback

    @app.errorhandler(Exception)
    def mostrar_erro(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        app.logger.exception("Erro não tratado")
        return Response("<pre>" + traceback.format_exc().replace("<", "&lt;") + "</pre>",
                        status=500, mimetype="text/html")

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("tipo") != "admin":
            flash("Apenas administradores podem acessar esta área.")
            return redirect(url_for("visao_geral"))
        return view(*args, **kwargs)
    return wrapped

def admin_scope_id():
    if session.get("tipo") == "admin":
        return session["user_id"]
    return session.get("criado_por")

def registrar_log(acao):
    db.query(
        "INSERT INTO logs (usuario_id, acao) VALUES (%s, %s)",
        (session.get("user_id"), acao),
        commit=True,
    )

@app.context_processor
def inject_user():
    return {
        "logado_nome": session.get("nome"),
        "logado_tipo": session.get("tipo"),
        "logado_cargo": session.get("cargo"),
        "logado_id": session.get("user_id"),
        "equip_img": imagem_equipamento,
    }

@app.route("/")
def home():
    return render_template("HOME.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form.get("login", "").strip()
        senha = request.form.get("senha", "")

        usuario = db.query(
            "SELECT * FROM usuarios WHERE login = %s AND ativo = 1",
            (login_input,), fetchone=True
        )

        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session["user_id"] = usuario["id"]
            session["nome"] = usuario["nome"]
            session["tipo"] = usuario["tipo"]
            session["cargo"] = usuario["cargo"]
            session["criado_por"] = usuario["criado_por"]
            registrar_log(f"Login realizado por {usuario['nome']}.")
            return redirect(url_for("visao_geral"))

        flash("Usuário ou senha inválidos.")
        return redirect(url_for("login"))

    return render_template("LOGIN.html")

@app.route("/logout")
def logout():
    if "user_id" in session:
        registrar_log(f"Logout realizado por {session.get('nome')}.")
    session.clear()
    return redirect(url_for("login"))

@app.route("/recursos")
def recursos():
    return render_template("RECURSOS.html")

@app.route("/sobrenos")
def sobrenos():
    return render_template("SOBRENOS.html")

@app.route("/mapa-sistema")
def mapa_sistema():
    return render_template("MAPA_SISTEMA.html")

@app.route("/solicitar-acesso")
def solicitar_acesso():
    return render_template("SOLICITAR_ACESSO.html")

@app.route("/solicitar-acesso/enviado")
def solicitar_acesso_enviado():
    return render_template("SOLICITACAO_ENVIADA.html")

def _serie_ultimos_dias(linhas, dias=7):
    """Preenche com zero os dias sem registro e devolve (rótulos, valores)."""
    from datetime import date, timedelta
    por_dia = {l["dia"]: l["total"] for l in linhas}
    hoje = date.today()
    rotulos, valores = [], []
    for i in range(dias - 1, -1, -1):
        d = hoje - timedelta(days=i)
        rotulos.append(d.strftime("%d/%m"))
        valores.append(int(por_dia.get(d, 0)))
    return rotulos, valores

@app.route("/visaogeral")
@login_required
def visao_geral():
    admin_id = admin_scope_id()
    equipe = (admin_id, admin_id)

    # 8 consultas rodando AO MESMO TEMPO (uma ida e volta ao banco, não oito em fila).
    (pecas, salas, status_rows, saidas_rows, reqs_rows,
     requisicoes_pendentes, atividade_recente, movimentacoes) = db.query_many([
        ("SELECT codigo, descricao, quantidade, local_estoque FROM pecas WHERE criado_por = %s", (admin_id,)),
        ("SELECT nome, status, computadores FROM salas WHERE criado_por = %s", (admin_id,)),
        ("""SELECT r.status, COUNT(*) AS total
            FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
            WHERE u.id = %s OR u.criado_por = %s GROUP BY r.status""", equipe),
        ("""SELECT DATE(m.data_hora) AS dia, COUNT(*) AS total
            FROM movimentacoes m JOIN pecas p ON p.id = m.peca_id
            WHERE p.criado_por = %s AND m.data_hora >= CURDATE() - INTERVAL 6 DAY
            GROUP BY DATE(m.data_hora)""", (admin_id,)),
        ("""SELECT DATE(r.data_solicitacao) AS dia, COUNT(*) AS total
            FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
            WHERE (u.id = %s OR u.criado_por = %s)
              AND r.data_solicitacao >= CURDATE() - INTERVAL 6 DAY
            GROUP BY DATE(r.data_solicitacao)""", equipe),
        ("""SELECT r.id, r.item_pedido, r.data_solicitacao, u.nome AS solicitante_nome
            FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
            WHERE (u.id = %s OR u.criado_por = %s) AND r.status = 'Pendente'
            ORDER BY r.data_solicitacao DESC LIMIT 5""", equipe),
        ("""SELECT l.data_hora, l.acao, u.nome AS usuario_nome
            FROM logs l LEFT JOIN usuarios u ON u.id = l.usuario_id
            WHERE u.id = %s OR u.criado_por = %s
            ORDER BY l.data_hora DESC LIMIT 6""", equipe),
        ("""SELECT p.codigo, p.descricao, m.destino, m.status, m.data_hora
            FROM movimentacoes m JOIN pecas p ON p.id = m.peca_id
            WHERE p.criado_por = %s ORDER BY m.data_hora DESC LIMIT 15""", (admin_id,)),
    ])
    reqs_por_status = {r["status"]: int(r["total"]) for r in status_rows}
    rotulos, saidas_7d = _serie_ultimos_dias(saidas_rows)
    _, reqs_7d = _serie_ultimos_dias(reqs_rows)

    # ---------- Indicadores (cards) ----------
    itens_cadastrados = len(pecas)
    unidades_estoque = sum(int(p["quantidade"]) for p in pecas)
    estoque_critico = sum(1 for p in pecas if p["quantidade"] < 3)
    saidas_hoje = saidas_7d[-1] if saidas_7d else 0
    reqs_pendentes = reqs_por_status.get("Pendente", 0)
    reqs_total = sum(reqs_por_status.values())

    # ---------- Dados dos gráficos ----------
    por_estoque = sorted(pecas, key=lambda p: (p["quantidade"], (p["descricao"] or "").lower()))
    menores_estoques = por_estoque[:6]
    alertas_estoque = [p for p in por_estoque if p["quantidade"] < 3][:6]

    locais = {}
    for p in pecas:
        nome = (p["local_estoque"] or "").strip() or "Sem local"
        chave = nome.casefold()
        if chave not in locais:
            locais[chave] = {"local_nome": nome, "total": 0}
        locais[chave]["total"] += int(p["quantidade"])
    estoque_por_local = sorted(locais.values(), key=lambda l: -l["total"])
    if len(estoque_por_local) > 5:
        resto = sum(l["total"] for l in estoque_por_local[5:])
        estoque_por_local = estoque_por_local[:5] + [{"local_nome": "Outros", "total": resto}]

    contagem_status = {}
    for s in salas:
        contagem_status[s["status"]] = contagem_status.get(s["status"], 0) + 1
    computadores_por_sala = sorted(salas, key=lambda s: (-int(s["computadores"] or 0), s["nome"]))[:6]

    graficos = {
        "atividade": {
            "labels": rotulos,
            "series": [
                {"name": "Saídas", "values": saidas_7d, "color": "#22d3ee"},
                {"name": "Requisições", "values": reqs_7d, "color": "#a78bfa"},
            ],
        },
        "requisicoes": [
            {"label": "Pendentes", "value": reqs_por_status.get("Pendente", 0), "color": "#f59e0b"},
            {"label": "Aprovadas", "value": reqs_por_status.get("Aprovado", 0), "color": "#22d3ee"},
            {"label": "Recusadas", "value": reqs_por_status.get("Recusado", 0), "color": "#f43f5e"},
        ],
        "menores_estoques": [
            {"label": p["descricao"], "value": int(p["quantidade"]),
             "color": "#f43f5e" if p["quantidade"] < 3 else "#22d3ee"}
            for p in menores_estoques
        ],
        "estoque_local": [
            {"label": l["local_nome"], "value": int(l["total"])} for l in estoque_por_local
        ],
        "salas_status": [
            {"label": status, "value": total,
             "color": {"Ativo": "#22d3ee", "Manutenção": "#f59e0b", "Inativo": "#f43f5e"}.get(status, "#94a3b8")}
            for status, total in contagem_status.items()
        ],
        "computadores_sala": [
            {"label": s["nome"], "value": int(s["computadores"] or 0), "color": "#3b82f6"}
            for s in computadores_por_sala
        ],
    }

    return render_template(
        "VisaoGeral.html",
        itens_cadastrados=itens_cadastrados,
        unidades_estoque=unidades_estoque,
        estoque_critico=estoque_critico,
        saidas_hoje=saidas_hoje,
        reqs_pendentes=reqs_pendentes,
        reqs_total=reqs_total,
        salas_total=len(salas),
        salas_ativas=sum(1 for s in salas if s["status"] == "Ativo"),
        computadores_total=sum(int(s["computadores"] or 0) for s in salas),
        graficos=graficos,
        alertas_estoque=alertas_estoque,
        requisicoes_pendentes=requisicoes_pendentes,
        atividade_recente=atividade_recente,
        movimentacoes=movimentacoes,
    )

@app.route("/inventario")
@login_required
def inventario():
    admin_id = admin_scope_id()
    itens = db.query(
        "SELECT * FROM pecas WHERE criado_por = %s ORDER BY descricao",
        (admin_id,)
    )
    return render_template("INVENTARIO.html", itens=itens)

@app.route("/inventario/gerenciar", methods=["GET", "POST"])
@admin_required
def inventario_gerenciar():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        quantidade = request.form.get("quantidade", "0") or "0"
        local_estoque = request.form.get("local", "").strip()

        db.query(
            """INSERT INTO pecas (codigo, descricao, quantidade, local_estoque, criado_por)
               VALUES (%s, %s, %s, %s, %s)""",
            (codigo, descricao, quantidade, local_estoque, admin_scope_id()),
            commit=True,
        )
        registrar_log(f"Peça '{descricao}' ({codigo}) cadastrada.")
        flash("Peça cadastrada com sucesso.")
        return redirect(url_for("inventario"))

    return render_template("GERENCIAR_PECA.html", peca=None)

@app.route("/inventario/editar/<int:peca_id>", methods=["GET", "POST"])
@admin_required
def inventario_editar(peca_id):
    admin_id = admin_scope_id()
    peca = db.query(
        "SELECT * FROM pecas WHERE id = %s AND criado_por = %s",
        (peca_id, admin_id), fetchone=True
    )
    if not peca:
        flash("Peça não encontrada.")
        return redirect(url_for("inventario"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        quantidade = request.form.get("quantidade", "0") or "0"
        local_estoque = request.form.get("local", "").strip()

        db.query(
            """UPDATE pecas SET codigo = %s, descricao = %s, quantidade = %s, local_estoque = %s
               WHERE id = %s AND criado_por = %s""",
            (codigo, descricao, quantidade, local_estoque, peca_id, admin_id),
            commit=True,
        )
        registrar_log(f"Peça '{descricao}' ({codigo}) editada.")
        flash("Peça atualizada com sucesso.")
        return redirect(url_for("inventario"))

    return render_template("GERENCIAR_PECA.html", peca=peca)

@app.route("/inventario/excluir/<int:peca_id>", methods=["POST"])
@admin_required
def inventario_excluir(peca_id):
    db.query(
        "DELETE FROM pecas WHERE id = %s AND criado_por = %s",
        (peca_id, admin_scope_id()), commit=True
    )
    registrar_log(f"Peça #{peca_id} excluída.")
    return redirect(url_for("inventario"))

@app.route("/salas")
@login_required
def salas():
    admin_id = admin_scope_id()
    lista = db.query(
        """SELECT s.*, u.nome AS responsavel_nome
           FROM salas s
           LEFT JOIN usuarios u ON u.id = s.responsavel_id
           WHERE s.criado_por = %s
           ORDER BY s.nome""",
        (admin_id,)
    )
    return render_template("SALAS.html", salas=lista)

@app.route("/salas/gerenciar", methods=["GET", "POST"])
@admin_required
def salas_gerenciar():
    admin_id = admin_scope_id()
    equipe = db.query(
        "SELECT id, nome FROM usuarios WHERE id = %s OR criado_por = %s ORDER BY nome",
        (admin_id, admin_id)
    )

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "").strip()
        bloco = request.form.get("bloco", "").strip()
        computadores = request.form.get("computadores", "0") or "0"
        responsavel_id = request.form.get("responsavel_id") or None
        status = request.form.get("status", "Ativo")

        db.query(
            """INSERT INTO salas (nome, tipo, bloco, computadores, responsavel_id, status, criado_por)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (nome, tipo, bloco, computadores, responsavel_id, status, admin_id),
            commit=True,
        )
        registrar_log(f"Sala '{nome}' cadastrada.")
        flash("Sala cadastrada com sucesso.")
        return redirect(url_for("salas"))

    return render_template("GERENCIAR_SALA.html", equipe=equipe, sala=None)

@app.route("/salas/editar/<int:sala_id>", methods=["GET", "POST"])
@admin_required
def salas_editar(sala_id):
    admin_id = admin_scope_id()
    sala = db.query(
        "SELECT * FROM salas WHERE id = %s AND criado_por = %s",
        (sala_id, admin_id), fetchone=True
    )
    if not sala:
        flash("Sala não encontrada.")
        return redirect(url_for("salas"))

    equipe = db.query(
        "SELECT id, nome FROM usuarios WHERE id = %s OR criado_por = %s ORDER BY nome",
        (admin_id, admin_id)
    )

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "").strip()
        bloco = request.form.get("bloco", "").strip()
        computadores = request.form.get("computadores", "0") or "0"
        responsavel_id = request.form.get("responsavel_id") or None
        status = request.form.get("status", "Ativo")

        db.query(
            """UPDATE salas SET nome = %s, tipo = %s, bloco = %s, computadores = %s,
               responsavel_id = %s, status = %s WHERE id = %s AND criado_por = %s""",
            (nome, tipo, bloco, computadores, responsavel_id, status, sala_id, admin_id),
            commit=True,
        )
        registrar_log(f"Sala '{nome}' editada.")
        flash("Sala atualizada com sucesso.")
        return redirect(url_for("salas"))

    return render_template("GERENCIAR_SALA.html", equipe=equipe, sala=sala)

@app.route("/salas/excluir/<int:sala_id>", methods=["POST"])
@admin_required
def salas_excluir(sala_id):
    db.query(
        "DELETE FROM salas WHERE id = %s AND criado_por = %s",
        (sala_id, admin_scope_id()), commit=True
    )
    registrar_log(f"Sala #{sala_id} excluída.")
    return redirect(url_for("salas"))

def coletar_itens_selecionados(pecas):
    itens = []
    for peca in pecas:
        bruto = request.form.get(f"qtd_{peca['id']}", "0").strip()
        try:
            qtd = int(bruto) if bruto else 0
        except ValueError:
            qtd = 0
        if qtd > 0:
            itens.append({
                "peca_id": peca["id"], "quantidade": qtd,
                "descricao": peca["descricao"], "codigo": peca["codigo"],
            })
    return itens

def montar_item_pedido(itens, outro_item):
    partes = [f"{i['quantidade']}x {i['descricao']} ({i['codigo']})" for i in itens]
    if outro_item:
        partes.append(outro_item)
    return ", ".join(partes)

def extrair_itens_do_pedido(item_pedido, pecas):
    pecas_por_codigo = {p["codigo"]: p for p in pecas}
    itens = []
    for qtd_texto, codigo in re.findall(r"(\d+)x\s+.+?\s+\(([^)]+)\)", item_pedido):
        peca = pecas_por_codigo.get(codigo)
        if peca:
            itens.append({
                "peca_id": peca["id"], "quantidade": int(qtd_texto),
                "descricao": peca["descricao"], "codigo": codigo,
                "estoque_atual": peca["quantidade"],
            })
    return itens

def _sala_valida(valor, salas_lista):
    """Devolve o id da sala se ele pertence ao escopo do admin; senão None."""
    valor = (valor or "").strip()
    if not valor.isdigit():
        return None
    ids = {s["id"] for s in salas_lista}
    return int(valor) if int(valor) in ids else None

@app.route("/requisicoes", methods=["GET", "POST"])
@login_required
def requisicoes():
    admin_id = admin_scope_id()
    pecas = db.query(
        "SELECT id, codigo, descricao, quantidade FROM pecas WHERE criado_por = %s ORDER BY descricao",
        (admin_id,)
    )

    salas_lista = db.query(
        "SELECT id, nome, bloco FROM salas WHERE criado_por = %s ORDER BY nome",
        (admin_id,)
    )

    if request.method == "POST":
        outro_item = request.form.get("item_pedido", "").strip()
        motivo = request.form.get("motivo", "").strip()
        itens_selecionados = coletar_itens_selecionados(pecas)

        if not itens_selecionados and not outro_item:
            flash("Selecione ao menos um item do estoque ou descreva o item desejado.")
            return redirect(url_for("requisicoes"))

        sala_id = _sala_valida(request.form.get("sala_id"), salas_lista)
        if salas_lista and sala_id is None:
            flash("Selecione a sala da requisição.")
            return redirect(url_for("requisicoes"))

        item_pedido = montar_item_pedido(itens_selecionados, outro_item)

        db.query(
            """INSERT INTO requisicoes (solicitante_id, sala_id, item_pedido, motivo)
               VALUES (%s, %s, %s, %s)""",
            (session["user_id"], sala_id, item_pedido, motivo), commit=True
        )
        registrar_log(f"Requisição de '{item_pedido}' criada.")
        flash("Requisição enviada.")
        return redirect(url_for("requisicoes"))

    lista = db.query(
        """SELECT r.*, u.nome AS solicitante_nome, s.nome AS sala_nome
           FROM requisicoes r
           JOIN usuarios u ON u.id = r.solicitante_id
           LEFT JOIN salas s ON s.id = r.sala_id
           WHERE u.id = %s OR u.criado_por = %s
           ORDER BY r.data_solicitacao DESC""",
        (admin_id, admin_id)
    )

    return render_template("REQUISICOES.html", requisicoes=lista, pecas=pecas, salas=salas_lista)

@app.route("/requisicoes/<int:req_id>/editar", methods=["GET", "POST"])
@login_required
def requisicoes_editar(req_id):
    admin_id = admin_scope_id()
    requisicao = db.query(
        """SELECT r.*, u.nome AS solicitante_nome, u.id AS solicitante_uid, u.criado_por AS solicitante_admin
           FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
           WHERE r.id = %s""",
        (req_id,), fetchone=True
    )

    if not requisicao or (requisicao["solicitante_uid"] != admin_id and requisicao["solicitante_admin"] != admin_id):
        flash("Requisição não encontrada.")
        return redirect(url_for("requisicoes"))

    if requisicao["status"] != "Pendente":
        flash("Só é possível editar requisições pendentes.")
        return redirect(url_for("requisicoes"))

    pode_editar = session.get("tipo") == "admin" or requisicao["solicitante_id"] == session["user_id"]
    if not pode_editar:
        flash("Você não tem permissão para editar esta requisição.")
        return redirect(url_for("requisicoes"))

    pecas = db.query(
        "SELECT id, codigo, descricao, quantidade FROM pecas WHERE criado_por = %s ORDER BY descricao",
        (admin_id,)
    )
    quantidades_atuais = {
        item["peca_id"]: item["quantidade"]
        for item in extrair_itens_do_pedido(requisicao["item_pedido"], pecas)
    }
    salas_lista = db.query(
        "SELECT id, nome, bloco FROM salas WHERE criado_por = %s ORDER BY nome",
        (admin_id,)
    )

    if request.method == "POST":
        outro_item = request.form.get("item_pedido", "").strip()
        motivo = request.form.get("motivo", "").strip()
        itens_selecionados = coletar_itens_selecionados(pecas)

        if not itens_selecionados and not outro_item:
            flash("Selecione ao menos um item do estoque ou descreva o item desejado.")
            return redirect(url_for("requisicoes_editar", req_id=req_id))

        sala_id = _sala_valida(request.form.get("sala_id"), salas_lista)
        if salas_lista and sala_id is None:
            flash("Selecione a sala da requisição.")
            return redirect(url_for("requisicoes_editar", req_id=req_id))

        item_pedido = montar_item_pedido(itens_selecionados, outro_item)

        db.query(
            "UPDATE requisicoes SET item_pedido = %s, motivo = %s, sala_id = %s WHERE id = %s",
            (item_pedido, motivo, sala_id, req_id), commit=True
        )
        registrar_log(f"Requisição #{req_id} editada.")
        flash("Requisição atualizada com sucesso.")
        return redirect(url_for("requisicoes"))

    return render_template(
        "EDITAR_REQUISICAO.html",
        requisicao=requisicao,
        pecas=pecas,
        salas=salas_lista,
        quantidades_atuais=quantidades_atuais,
    )

@app.route("/requisicoes/<int:req_id>/excluir", methods=["POST"])
@admin_required
def requisicoes_excluir(req_id):
    admin_id = admin_scope_id()
    requisicao = db.query(
        """SELECT r.* FROM requisicoes r
           JOIN usuarios u ON u.id = r.solicitante_id
           WHERE r.id = %s AND (u.id = %s OR u.criado_por = %s)""",
        (req_id, admin_id, admin_id), fetchone=True
    )
    if not requisicao:
        flash("Requisição não encontrada.")
        return redirect(url_for("requisicoes"))

    db.query("DELETE FROM requisicoes WHERE id = %s", (req_id,), commit=True)
    registrar_log(f"Requisição #{req_id} excluída.")
    flash("Requisição excluída com sucesso.")
    return redirect(url_for("requisicoes"))

def avaliar_requisicao(req_id, acao, admin_id):
    """Aprova ou recusa uma requisição da equipe do admin. Devolve (ok, mensagem).

    Aprovar baixa o estoque (só se houver saldo), registra a movimentação e muda o status,
    tudo na MESMA transação: ou grava tudo, ou nada.
    """
    req = db.query(
        """SELECT r.* FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
           WHERE r.id = %s AND (u.id = %s OR u.criado_por = %s)""",
        (req_id, admin_id, admin_id), fetchone=True
    )
    if not req:
        return False, f"Não achei a requisição #{req_id} na sua equipe."
    if req["status"] != "Pendente":
        return False, "Esta requisição já foi avaliada."

    if acao == "recusar":
        db.query("UPDATE requisicoes SET status = 'Recusado' WHERE id = %s AND status = 'Pendente'",
                 (req_id,), commit=True)
        registrar_log(f"Requisição #{req_id} marcada como Recusado.")
        return True, f"Requisição #{req_id} recusada."

    pecas = db.query(
        "SELECT id, codigo, descricao, quantidade FROM pecas WHERE criado_por = %s", (admin_id,)
    )
    itens = extrair_itens_do_pedido(req["item_pedido"], pecas)

    conn = db.get_db()
    try:
        conn.start_transaction()
        cur = conn.cursor()
        for item in itens:
            cur.execute(
                "UPDATE pecas SET quantidade = quantidade - %s "
                "WHERE id = %s AND criado_por = %s AND quantidade >= %s",
                (item["quantidade"], item["peca_id"], admin_id, item["quantidade"])
            )
            if cur.rowcount != 1:
                conn.rollback()
                cur.close()
                return False, f"Estoque insuficiente de '{item['descricao']}' para aprovar esta requisição."
            cur.execute(
                "INSERT INTO movimentacoes (peca_id, destino, status) VALUES (%s, %s, 'Concluído')",
                (item["peca_id"], f"{item['quantidade']}x - Requisição #{req_id}")
            )
        cur.execute("UPDATE requisicoes SET status = 'Aprovado' WHERE id = %s AND status = 'Pendente'", (req_id,))
        if cur.rowcount != 1:
            conn.rollback()
            cur.close()
            return False, "Esta requisição já foi avaliada."
        conn.commit()
        cur.close()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        db.release(conn)

    registrar_log(f"Requisição #{req_id} marcada como Aprovado.")
    baixas = ", ".join(f"-{i['quantidade']} {i['descricao']}" for i in itens)
    return True, f"Requisição #{req_id} aprovada." + (f" Estoque atualizado: {baixas}." if baixas else "")

@app.route("/requisicoes/<int:req_id>/<acao>", methods=["POST"])
@admin_required
def requisicoes_avaliar(req_id, acao):
    if acao not in ("aprovar", "recusar"):
        abort(404)
    ok, msg = avaliar_requisicao(req_id, acao, admin_scope_id())
    flash(msg)
    return redirect(url_for("requisicoes"))

def _nivel_sql(alias):
    """Nível de acesso de quem gerou o log: 3 = admin, 2 = técnico, 1 = usuário."""
    return (f"(CASE WHEN {alias}.tipo = 'admin' THEN 3 "
            f"WHEN LOWER({alias}.cargo) LIKE '%%técnico%%' OR LOWER({alias}.cargo) LIKE '%%tecnico%%' THEN 2 "
            f"ELSE 1 END)")

def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()

def nivel_logado():
    if session.get("tipo") == "admin":
        return 3
    if "tecnico" in _sem_acento(session.get("cargo")):
        return 2
    return 1

def filtro_logs(alias="u"):
    """Fragmento SQL (já com %% escapado) que limita os logs ao nível do usuário logado."""
    nivel = nivel_logado()
    if nivel >= 3:
        return ""
    return f" AND {_nivel_sql(alias)} <= {nivel}"

@app.route("/logs")
@login_required
def logs():
    admin_id = admin_scope_id()
    lista = db.query(
        f"""SELECT l.data_hora, l.acao, u.nome AS usuario_nome,
                  CASE {_nivel_sql('u')} WHEN 3 THEN 'Administrador' WHEN 2 THEN 'Técnico' ELSE 'Usuário' END AS perfil
           FROM logs l
           LEFT JOIN usuarios u ON u.id = l.usuario_id
           WHERE (u.id = %s OR u.criado_por = %s){filtro_logs('u')}
           ORDER BY l.data_hora DESC LIMIT 200""",
        (admin_id, admin_id)
    )
    escopo = {3: "todas as atividades da equipe", 2: "atividades de técnicos e usuários",
              1: "apenas atividades de usuários"}[nivel_logado()]
    return render_template("LOGS.html", logs=lista, escopo=escopo)

@app.route("/usuarios", methods=["GET", "POST"])
@admin_required
def usuarios():
    admin_id = session["user_id"]

    if request.method == "POST":
        equipe_atual = db.query(
            "SELECT COUNT(*) AS total FROM usuarios WHERE criado_por = %s",
            (admin_id,), fetchone=True
        )["total"]

        if equipe_atual >= 4:
            flash("Limite de 4 usuários por administrador já foi atingido.")
            return redirect(url_for("usuarios"))

        nome = request.form.get("nome", "").strip()
        login_novo = request.form.get("login", "").strip()
        senha = request.form.get("senha", "").strip()
        cargo = request.form.get("cargo", "Usuário").strip()

        existente = db.query(
            "SELECT id FROM usuarios WHERE login = %s", (login_novo,), fetchone=True
        )
        if existente:
            flash("Já existe um usuário com esse login.")
            return redirect(url_for("usuarios"))

        senha_hash = generate_password_hash(senha)
        db.query(
            """INSERT INTO usuarios (nome, login, senha_hash, cargo, tipo, criado_por)
               VALUES (%s, %s, %s, %s, 'usuario', %s)""",
            (nome, login_novo, senha_hash, cargo, admin_id), commit=True
        )
        registrar_log(f"Usuário '{nome}' ({login_novo}) cadastrado.")
        flash("Usuário cadastrado com sucesso.")
        return redirect(url_for("usuarios"))

    equipe = db.query(
        "SELECT * FROM usuarios WHERE id = %s OR criado_por = %s ORDER BY tipo DESC, nome",
        (admin_id, admin_id)
    )
    vagas_restantes = 4 - db.query(
        "SELECT COUNT(*) AS total FROM usuarios WHERE criado_por = %s",
        (admin_id,), fetchone=True
    )["total"]

    return render_template("USUARIOS.html", equipe=equipe, vagas_restantes=vagas_restantes)

@app.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@admin_required
def usuarios_editar(usuario_id):
    admin_id = session["user_id"]
    usuario = db.query(
        "SELECT * FROM usuarios WHERE id = %s AND (id = %s OR criado_por = %s)",
        (usuario_id, admin_id, admin_id), fetchone=True
    )
    if not usuario:
        flash("Usuário não encontrado.")
        return redirect(url_for("usuarios"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        login_novo = request.form.get("login", "").strip()
        cargo = request.form.get("cargo", "").strip()

        existente = db.query(
            "SELECT id FROM usuarios WHERE login = %s AND id != %s",
            (login_novo, usuario_id), fetchone=True
        )
        if existente:
            flash("Já existe um usuário com esse login.")
            return redirect(url_for("usuarios_editar", usuario_id=usuario_id))

        db.query(
            "UPDATE usuarios SET nome = %s, login = %s, cargo = %s WHERE id = %s",
            (nome, login_novo, cargo, usuario_id), commit=True
        )
        registrar_log(f"Usuário '{nome}' ({login_novo}) editado.")
        flash("Usuário atualizado com sucesso.")
        return redirect(url_for("usuarios"))

    return render_template("USUARIOS_EDITAR.html", usuario=usuario)

@app.route("/usuarios/<int:usuario_id>/excluir", methods=["POST"])
@admin_required
def usuarios_excluir(usuario_id):
    db.query(
        "DELETE FROM usuarios WHERE id = %s AND criado_por = %s",
        (usuario_id, session["user_id"]), commit=True
    )
    registrar_log(f"Usuário #{usuario_id} removido.")
    return redirect(url_for("usuarios"))

@app.route("/usuarios/<int:usuario_id>/senha", methods=["GET", "POST"])
@admin_required
def usuarios_senha(usuario_id):
    admin_id = session["user_id"]
    usuario = db.query(
        "SELECT * FROM usuarios WHERE id = %s AND (id = %s OR criado_por = %s)",
        (usuario_id, admin_id, admin_id), fetchone=True
    )
    if not usuario:
        flash("Usuário não encontrado.")
        return redirect(url_for("usuarios"))

    if request.method == "POST":
        nova_senha = request.form.get("senha", "").strip()
        if not nova_senha:
            flash("Informe uma senha.")
            return redirect(url_for("usuarios_senha", usuario_id=usuario_id))

        senha_hash = generate_password_hash(nova_senha)
        db.query(
            "UPDATE usuarios SET senha_hash = %s WHERE id = %s",
            (senha_hash, usuario_id), commit=True
        )
        registrar_log(f"Senha do usuário '{usuario['nome']}' redefinida.")
        flash(f"Senha de {usuario['nome']} redefinida para: {nova_senha}")
        return redirect(url_for("usuarios"))

    return render_template("USUARIOS_SENHA.html", usuario=usuario)

TABELAS_BACKUP = ["usuarios", "salas", "pecas", "requisicoes", "movimentacoes"]

def _dados_backup(admin_id):
    equipe = (admin_id, admin_id)
    return {
        "usuarios": db.query("SELECT * FROM usuarios WHERE id = %s OR criado_por = %s ORDER BY id", equipe),
        "salas": db.query("SELECT * FROM salas WHERE criado_por = %s ORDER BY id", (admin_id,)),
        "pecas": db.query("SELECT * FROM pecas WHERE criado_por = %s ORDER BY id", (admin_id,)),
        "requisicoes": db.query(
            """SELECT r.* FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
               WHERE u.id = %s OR u.criado_por = %s ORDER BY r.id""", equipe),
        "movimentacoes": db.query(
            """SELECT m.* FROM movimentacoes m JOIN pecas p ON p.id = m.peca_id
               WHERE p.criado_por = %s ORDER BY m.id""", (admin_id,)),
    }

def _sql_valor(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    texto = str(v).replace("\\", "\\\\").replace("'", "''")
    return f"'{texto}'"

@app.route("/backup")
@admin_required
def backup():
    admin_id = session["user_id"]
    linhas = db.query(
        """SELECT 'usuarios' AS t, COUNT(*) AS n FROM usuarios WHERE id = %s OR criado_por = %s
           UNION ALL SELECT 'salas', COUNT(*) FROM salas WHERE criado_por = %s
           UNION ALL SELECT 'pecas', COUNT(*) FROM pecas WHERE criado_por = %s
           UNION ALL SELECT 'requisicoes', COUNT(*) FROM requisicoes r
                     JOIN usuarios u ON u.id = r.solicitante_id WHERE u.id = %s OR u.criado_por = %s
           UNION ALL SELECT 'movimentacoes', COUNT(*) FROM movimentacoes m
                     JOIN pecas p ON p.id = m.peca_id WHERE p.criado_por = %s""",
        (admin_id,) * 7
    )
    por_tabela = {l["t"]: int(l["n"]) for l in linhas}
    contagem = {t: por_tabela.get(t, 0) for t in TABELAS_BACKUP}
    return render_template("BACKUP.html", contagem=contagem)

@app.route("/backup/download")
@admin_required
def backup_download():
    admin_id = session["user_id"]
    dados = _dados_backup(admin_id)

    linhas = [f"-- Backup CampusHUB gerado em {datetime.now():%d/%m/%Y %H:%M:%S}"]
    for tabela in TABELAS_BACKUP:
        for reg in dados[tabela]:
            colunas = ", ".join(reg.keys())
            valores = ", ".join(_sql_valor(v) for v in reg.values())
            linhas.append(f"INSERT INTO {tabela} ({colunas}) VALUES ({valores});")

    pacote = {
        "versao": 1,
        "admin_id": admin_id,
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tabelas": dados,
    }

    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("backup.json", json.dumps(pacote, ensure_ascii=False, default=str, indent=1))
        z.writestr("backup.sql", "\n".join(linhas))
    memoria.seek(0)

    registrar_log("Backup do banco gerado e baixado.")
    nome = f"campushub_backup_{datetime.now():%Y%m%d_%H%M}.zip"
    return Response(
        memoria.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={nome}"},
    )

@app.route("/backup/restaurar", methods=["POST"])
@admin_required
def backup_restaurar():
    admin_id = session["user_id"]
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename.lower().endswith(".zip"):
        flash("Envie um arquivo .zip gerado pelo próprio sistema.")
        return redirect(url_for("backup"))

    try:
        bruto = arquivo.read(10 * 1024 * 1024 + 1)
        if len(bruto) > 10 * 1024 * 1024:
            raise ValueError("Arquivo grande demais (máx. 10 MB).")
        with zipfile.ZipFile(io.BytesIO(bruto)) as z:
            pacote = json.loads(z.read("backup.json").decode("utf-8"))
        tabelas = pacote["tabelas"]
        if pacote.get("admin_id") != admin_id:
            flash("Este backup pertence a outra conta e não pode ser restaurado aqui.")
            return redirect(url_for("backup"))
    except Exception:
        flash("Arquivo de backup inválido.")
        return redirect(url_for("backup"))

    conn = db.get_db()
    conn.start_transaction()
    cur = conn.cursor(dictionary=True)
    resumo = {}
    try:
        # ids que pertencem ao escopo deste admin (tudo o que não for dele é ignorado)
        equipe_ids = {admin_id}
        pecas_ids = set()
        for tabela in TABELAS_BACKUP:
            cur.execute(f"SHOW COLUMNS FROM {tabela}")
            validas = {c["Field"] for c in cur.fetchall()}
            total = 0
            for reg in tabelas.get(tabela, []):
                reg = {k: v for k, v in reg.items() if k in validas}
                if "id" not in reg:
                    continue

                if tabela == "usuarios":
                    if reg["id"] == admin_id:
                        reg["tipo"], reg["criado_por"] = "admin", None
                    elif reg.get("criado_por") == admin_id:
                        reg["tipo"] = "usuario"
                        equipe_ids.add(reg["id"])
                    else:
                        continue
                elif tabela == "salas" or tabela == "pecas":
                    if reg.get("criado_por") != admin_id:
                        continue
                    if tabela == "pecas":
                        pecas_ids.add(reg["id"])
                elif tabela == "requisicoes":
                    if reg.get("solicitante_id") not in equipe_ids:
                        continue
                elif tabela == "movimentacoes":
                    if reg.get("peca_id") not in pecas_ids:
                        continue

                colunas = list(reg.keys())
                marcadores = ", ".join(["%s"] * len(colunas))
                atualiza = ", ".join(f"{c} = VALUES({c})" for c in colunas if c != "id")
                cur.execute(
                    f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({marcadores}) "
                    f"ON DUPLICATE KEY UPDATE {atualiza}",
                    [reg[c] for c in colunas],
                )
                total += 1
            resumo[tabela] = total
        conn.commit()
    except Exception:
        conn.rollback()
        cur.close()
        db.release(conn)
        app.logger.exception("Falha ao restaurar backup")
        flash("Não foi possível restaurar o backup (nada foi alterado).")
        return redirect(url_for("backup"))
    cur.close()
    db.release(conn)

    registrar_log("Backup restaurado.")
    flash("Backup restaurado: " + ", ".join(f"{v} {k}" for k, v in resumo.items()) + ".")
    return redirect(url_for("backup"))

@app.route("/chatbot", methods=["POST"])
@login_required
def chatbot_rota():
    dados = request.get_json(silent=True) or {}
    ctx = chatbot.Contexto(
        admin_id=admin_scope_id(),
        user_id=session["user_id"],
        nome=session.get("nome") or "",
        eh_admin=session.get("tipo") == "admin",
        montar_item_pedido=montar_item_pedido,
        registrar_log=registrar_log,
        filtro_logs=filtro_logs,
        avaliar_requisicao=lambda rid, acao: avaliar_requisicao(rid, acao, admin_scope_id()),
    )
    return jsonify(chatbot.responder(dados.get("text", ""), dados.get("state"), ctx))

if __name__ == "__main__":
    app.run(debug=False)
