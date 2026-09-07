from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, Response
)
from werkzeug.security import generate_password_hash, check_password_hash

import db
from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
db.init_app(app)

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
    """
    ID do administrador "dono" do time do usuário logado.
    - Se quem está logado é admin -> o próprio id.
    - Se é um usuário comum -> o id de quem o criou (seu admin).
    Isso é o que garante que cada admin (e os até 4 usuários que ele
    criou) só enxergue e mexa nos dados do próprio time.
    """
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

@app.route("/solicitar-acesso")
def solicitar_acesso():
    return render_template("SOLICITAR_ACESSO.html")

@app.route("/solicitar-acesso/enviado")
def solicitar_acesso_enviado():
    return render_template("SOLICITACAO_ENVIADA.html")

@app.route("/visaogeral")
@login_required
def visao_geral():
    admin_id = admin_scope_id()

    itens_cadastrados = db.query(
        "SELECT COUNT(*) AS total FROM pecas WHERE criado_por = %s",
        (admin_id,), fetchone=True
    )["total"]

    estoque_critico = db.query(
        "SELECT COUNT(*) AS total FROM pecas WHERE criado_por = %s AND quantidade < 3",
        (admin_id,), fetchone=True
    )["total"]

    saidas_hoje = db.query(
        """SELECT COUNT(*) AS total FROM movimentacoes m
           JOIN pecas p ON p.id = m.peca_id
           WHERE p.criado_por = %s AND DATE(m.data_hora) = CURDATE()""",
        (admin_id,), fetchone=True
    )["total"]

    movimentacoes = db.query(
        """SELECT p.codigo, p.descricao, m.destino, m.status, m.data_hora
           FROM movimentacoes m
           JOIN pecas p ON p.id = m.peca_id
           WHERE p.criado_por = %s
           ORDER BY m.data_hora DESC LIMIT 15""",
        (admin_id,)
    )

    return render_template(
        "VisaoGeral.html",
        itens_cadastrados=itens_cadastrados,
        estoque_critico=estoque_critico,
        saidas_hoje=saidas_hoje,
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

    return render_template("GERENCIAR_PECA.html")

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

    return render_template("GERENCIAR_SALA.html", equipe=equipe)

@app.route("/requisicoes", methods=["GET", "POST"])
@login_required
def requisicoes():
    admin_id = admin_scope_id()

    if request.method == "POST":
        item_pedido = request.form.get("item_pedido", "").strip()
        motivo = request.form.get("motivo", "").strip()
        db.query(
            """INSERT INTO requisicoes (solicitante_id, item_pedido, motivo)
               VALUES (%s, %s, %s)""",
            (session["user_id"], item_pedido, motivo), commit=True
        )
        registrar_log(f"Requisição de '{item_pedido}' criada.")
        flash("Requisição enviada.")
        return redirect(url_for("requisicoes"))

    lista = db.query(
        """SELECT r.*, u.nome AS solicitante_nome
           FROM requisicoes r
           JOIN usuarios u ON u.id = r.solicitante_id
           WHERE u.id = %s OR u.criado_por = %s
           ORDER BY r.data_solicitacao DESC""",
        (admin_id, admin_id)
    )
    return render_template("REQUISICOES.html", requisicoes=lista)

@app.route("/requisicoes/<int:req_id>/<acao>", methods=["POST"])
@admin_required
def requisicoes_avaliar(req_id, acao):
    novo_status = "Aprovado" if acao == "aprovar" else "Recusado"
    db.query(
        "UPDATE requisicoes SET status = %s WHERE id = %s",
        (novo_status, req_id), commit=True
    )
    registrar_log(f"Requisição #{req_id} marcada como {novo_status}.")
    return redirect(url_for("requisicoes"))

@app.route("/logs")
@login_required
def logs():
    admin_id = admin_scope_id()
    lista = db.query(
        """SELECT l.data_hora, l.acao, u.nome AS usuario_nome
           FROM logs l
           LEFT JOIN usuarios u ON u.id = l.usuario_id
           WHERE u.id = %s OR u.criado_por = %s
           ORDER BY l.data_hora DESC LIMIT 200""",
        (admin_id, admin_id)
    )
    return render_template("LOGS.html", logs=lista)

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

@app.route("/usuarios/<int:usuario_id>/excluir", methods=["POST"])
@admin_required
def usuarios_excluir(usuario_id):
    db.query(
        "DELETE FROM usuarios WHERE id = %s AND criado_por = %s",
        (usuario_id, session["user_id"]), commit=True
    )
    registrar_log(f"Usuário #{usuario_id} removido.")
    return redirect(url_for("usuarios"))

@app.route("/backup")
@admin_required
def backup():
    return render_template("BACKUP.html")

@app.route("/backup/download")
@admin_required
def backup_download():
    admin_id = session["user_id"]
    linhas = [f"-- Backup CampusHUB gerado em {datetime.now():%d/%m/%Y %H:%M:%S}\n"]

    tabelas = {
        "usuarios": "SELECT * FROM usuarios WHERE id = %s OR criado_por = %s",
        "salas": "SELECT * FROM salas WHERE criado_por = %s",
        "pecas": "SELECT * FROM pecas WHERE criado_por = %s",
    }

    for tabela, sql in tabelas.items():
        params = (admin_id, admin_id) if tabela == "usuarios" else (admin_id,)
        registros = db.query(sql, params)
        for reg in registros:
            colunas = ", ".join(reg.keys())
            valores = ", ".join(
                "NULL" if v is None else f"'{str(v).replace(chr(39), chr(39)+chr(39))}'"
                for v in reg.values()
            )
            linhas.append(f"INSERT INTO {tabela} ({colunas}) VALUES ({valores});")

    conteudo = "\n".join(linhas)
    registrar_log("Backup do banco gerado e baixado.")
    return Response(
        conteudo,
        mimetype="application/sql",
        headers={"Content-Disposition": "attachment; filename=campushub_backup.sql"},
    )

if __name__ == "__main__":
    app.run(debug=True)
