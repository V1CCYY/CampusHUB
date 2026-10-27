"""CampusBot: assistente por regras (sem IA externa) do painel CampusHUB.

Fala com static/js/chatbot.js via POST /chatbot ({text, state} -> {reply, cards, options, links, state}).
Tudo é filtrado pelo escopo do admin (admin_id) e revalidado no servidor.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from flask import url_for

import db
from equipamentos import imagem_equipamento


@dataclass
class Contexto:
    admin_id: int
    user_id: int
    nome: str
    eh_admin: bool
    montar_item_pedido: Callable
    registrar_log: Callable
    filtro_logs: Callable


TOM = {"Pendente": "aviso", "Aprovado": "ok", "Recusado": "erro"}


def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")
    return t.lower().strip()


def _resp(reply, cards=None, options=None, links=None, state=None, placeholder=None):
    return {"reply": reply, "cards": cards or [], "options": options or [],
            "links": links or [], "state": state, "placeholder": placeholder}


def _opt(label, value):
    return {"label": label, "value": value}


CANCELAR = _opt("Cancelar", "cmd:cancelar")


def _menu(ctx, intro):
    ops = [_opt("Ver chamados", "cmd:chamados"), _opt("Nova requisição", "cmd:nova"),
           _opt("Consultar estoque", "cmd:estoque"), _opt("Ver salas", "cmd:salas"),
           _opt("Últimos logs", "cmd:logs")]
    return _resp(intro, options=ops)


# ---------------------------------------------------------------- consultas
def _chamados(ctx, pendentes=False, meus=False, limite=6):
    where = "WHERE (u.id = %s OR u.criado_por = %s)"
    params = [ctx.admin_id, ctx.admin_id]
    if pendentes:
        where += " AND r.status = 'Pendente'"
    if meus:
        where += " AND r.solicitante_id = %s"
        params.append(ctx.user_id)
    base = ("FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id "
            "LEFT JOIN salas s ON s.id = r.sala_id " + where)
    total = db.query("SELECT COUNT(*) AS n " + base, params, fetchone=True)["n"]
    linhas = db.query(
        "SELECT r.id, r.item_pedido, r.motivo, r.status, r.data_solicitacao, "
        "u.nome AS solicitante_nome, s.nome AS sala_nome " + base +
        " ORDER BY r.data_solicitacao DESC LIMIT %s", params + [limite])
    return total, linhas


def _card_chamado(r):
    linhas = [r["item_pedido"], f"Sala: {r['sala_nome'] or '—'}",
              f"Por {r['solicitante_nome']} em {r['data_solicitacao']:%d/%m/%Y %H:%M}"]
    if r.get("motivo"):
        linhas.append(f"Motivo: {r['motivo']}")
    return {"titulo": f"Chamado #{r['id']}", "badge": {"texto": r["status"], "tom": TOM.get(r["status"], "aviso")},
            "linhas": linhas, "href": url_for("requisicoes")}


def _mostrar_chamados(ctx, pendentes=False, meus=False):
    total, linhas = _chamados(ctx, pendentes, meus)
    tipo = "pendentes" if pendentes else ("seus" if meus else "da sua equipe")
    if not linhas:
        return _resp(f"Não encontrei chamados {tipo}.", options=[_opt("Nova requisição", "cmd:nova")])
    extra = f" Mostrando os {len(linhas)} mais recentes." if total > len(linhas) else ""
    ops = [_opt("Nova requisição", "cmd:nova")]
    if not pendentes:
        ops.insert(0, _opt("Só pendentes", "cmd:pendentes"))
    return _resp(f"Encontrei {total} chamado(s) {tipo}.{extra}", cards=[_card_chamado(r) for r in linhas],
                 options=ops, links=[{"label": "Abrir Requisições", "href": url_for("requisicoes")}])


def _detalhe_chamado(ctx, req_id):
    r = db.query(
        """SELECT r.id, r.item_pedido, r.motivo, r.status, r.data_solicitacao,
                  u.nome AS solicitante_nome, s.nome AS sala_nome
           FROM requisicoes r JOIN usuarios u ON u.id = r.solicitante_id
           LEFT JOIN salas s ON s.id = r.sala_id
           WHERE r.id = %s AND (u.id = %s OR u.criado_por = %s)""",
        (req_id, ctx.admin_id, ctx.admin_id), fetchone=True)
    if not r:
        return _resp(f"Não achei o chamado #{req_id} na sua equipe.", options=[_opt("Ver chamados", "cmd:chamados")])
    return _resp(f"Aqui está o chamado #{req_id}:", cards=[_card_chamado(r)])


def _buscar_pecas(ctx, termo, so_estoque=False):
    sql = "SELECT id, codigo, descricao, quantidade, local_estoque FROM pecas WHERE criado_por = %s"
    params = [ctx.admin_id]
    if termo:
        sql += " AND (descricao LIKE %s OR codigo LIKE %s)"
        params += [f"%{termo}%", f"%{termo}%"]
    if so_estoque:
        sql += " AND quantidade > 0"
    return db.query(sql + " ORDER BY descricao LIMIT 8", params)


def _card_peca(p):
    tom = "erro" if p["quantidade"] < 3 else "ok"
    return {"titulo": p["descricao"], "badge": {"texto": f"{p['quantidade']} em estoque", "tom": tom},
            "linhas": [f"Código {p['codigo']}", f"Local: {p['local_estoque'] or '—'}"],
            "img": imagem_equipamento(p["descricao"]), "href": url_for("inventario")}


def _consultar_estoque(ctx, termo):
    achados = _buscar_pecas(ctx, termo)
    if not achados:
        return _resp(f"Não encontrei itens com “{termo}” no estoque.", options=[_opt("Consultar outro", "cmd:estoque")])
    return _resp(f"Encontrei {len(achados)} item(ns):", cards=[_card_peca(p) for p in achados],
                 options=[_opt("Nova requisição", "cmd:nova")])


def _salas(ctx):
    lista = db.query("SELECT * FROM salas WHERE criado_por = %s ORDER BY nome LIMIT 8", (ctx.admin_id,))
    if not lista:
        return _resp("Nenhuma sala cadastrada ainda.")
    tom = {"Ativo": "ok", "Manutenção": "aviso", "Inativo": "erro"}
    cards = [{"titulo": s["nome"], "badge": {"texto": s["status"], "tom": tom.get(s["status"], "aviso")},
              "linhas": [" · ".join(x for x in (s["tipo"], s["bloco"]) if x) or "—",
                         f"{s['computadores']} computador(es)"], "href": url_for("salas")} for s in lista]
    return _resp("Estas são as salas:", cards=cards)


def _logs(ctx):
    lista = db.query(
        """SELECT l.data_hora, l.acao, u.nome AS usuario_nome
           FROM logs l LEFT JOIN usuarios u ON u.id = l.usuario_id
           WHERE (u.id = %s OR u.criado_por = %s)""" + ctx.filtro_logs("u") +
        " ORDER BY l.data_hora DESC LIMIT 6", (ctx.admin_id, ctx.admin_id))
    if not lista:
        return _resp("Sem registros para o seu nível de acesso.")
    linhas = [f"{l['data_hora']:%d/%m %H:%M} · {l['usuario_nome'] or '-'}: {l['acao']}" for l in lista]
    return _resp("Últimas atividades que você pode ver:", cards=[{"titulo": "Logs recentes", "linhas": linhas}],
                 links=[{"label": "Abrir Logs", "href": url_for("logs")}])


# ---------------------------------------------------------------- fluxo "nova requisição"
def _salas_opts(ctx, filtro=""):
    sql, params = "SELECT id, nome, bloco FROM salas WHERE criado_por = %s", [ctx.admin_id]
    if filtro:
        sql += " AND nome LIKE %s"
        params.append(f"%{filtro}%")
    return db.query(sql + " ORDER BY nome LIMIT 8", params)


def _pergunta_sala(ctx, estado, filtro=""):
    salas = _salas_opts(ctx, filtro)
    if not salas:
        msg = "Não encontrei essa sala." if filtro else "Nenhuma sala cadastrada. Peça ao administrador para cadastrar."
        return _resp(msg, options=[CANCELAR], state=estado)
    return _resp("Para qual sala é a requisição? Toque numa opção ou digite parte do nome.",
                 options=[_opt(s["nome"], f"cmd:sala:{s['id']}") for s in salas] + [CANCELAR],
                 state=estado, placeholder="Nome da sala…")


def _pergunta_item(ctx, estado, termo=""):
    pecas = _buscar_pecas(ctx, termo, so_estoque=True)
    if not pecas:
        return _resp("Não achei item em estoque com esse nome.",
                     options=[_opt("Item fora do estoque", "cmd:outro"), CANCELAR], state=estado)
    ops = [_opt(f"{p['descricao']} ({p['quantidade']})", f"cmd:item:{p['id']}") for p in pecas]
    ops += [_opt("Item fora do estoque", "cmd:outro"), CANCELAR]
    return _resp("Qual item você precisa? Toque numa opção ou digite o nome.",
                 cards=[_card_peca(p) for p in pecas[:4]], options=ops, state=estado, placeholder="Nome do item…")


def _resumo(estado):
    return ", ".join(f"{i['quantidade']}x {i['descricao']}" for i in estado["itens"]) + \
        ((", " if estado["itens"] else "") + estado["outro"] if estado.get("outro") else "")


def _limpar_estado(e, ctx):
    """Reconstrói o estado vindo do cliente só com tipos seguros."""
    itens = []
    for i in e.get("itens") or []:
        try:
            itens.append({"peca_id": int(i["peca_id"]), "quantidade": int(i["quantidade"]),
                          "descricao": str(i.get("descricao", ""))[:80]})
        except (KeyError, TypeError, ValueError):
            pass
    out = {"flow": e.get("flow"), "step": e.get("step"), "itens": itens,
           "outro": str(e.get("outro") or "")[:100], "motivo": str(e.get("motivo") or "")[:150]}
    for k in ("sala_id", "peca_id"):
        try:
            out[k] = int(e[k]) if e.get(k) is not None else None
        except (TypeError, ValueError):
            out[k] = None
    return out


def _fluxo(ctx, texto, e):
    cmd = texto[4:] if texto.startswith("cmd:") else None
    norm = _norm(texto)
    step = e["step"]

    if step == "sala":
        if cmd and cmd.startswith("sala:"):
            sid = int(cmd[5:]) if cmd[5:].isdigit() else 0
            s = db.query("SELECT id, nome FROM salas WHERE id = %s AND criado_por = %s", (sid, ctx.admin_id), fetchone=True)
            if s:
                e.update(sala_id=s["id"], step="item")
                return _pergunta_item(ctx, e)
            return _pergunta_sala(ctx, e)
        achadas = _salas_opts(ctx, texto.strip())
        if len(achadas) == 1:
            e.update(sala_id=achadas[0]["id"], step="item")
            return _pergunta_item(ctx, e)
        return _pergunta_sala(ctx, e, texto.strip())

    if step == "item":
        if cmd == "outro":
            e["step"] = "outro"
            return _resp("Descreva o item que não está no estoque.", options=[CANCELAR], state=e, placeholder="Ex.: Cabo VGA 5m")
        if cmd and cmd.startswith("item:"):
            pid = int(cmd[5:]) if cmd[5:].isdigit() else 0
            p = db.query("SELECT id, descricao, quantidade FROM pecas WHERE id = %s AND criado_por = %s AND quantidade > 0",
                         (pid, ctx.admin_id), fetchone=True)
            if p:
                e.update(peca_id=p["id"], step="qtd")
                ops = [_opt(str(n), f"cmd:qtd:{n}") for n in (1, 2, 3, 5) if n <= p["quantidade"]]
                return _resp(f"Quantas unidades de {p['descricao']}? (em estoque: {p['quantidade']})",
                             options=ops + [CANCELAR], state=e, placeholder="Quantidade…")
        return _pergunta_item(ctx, e, "" if cmd else texto.strip())

    if step == "qtd":
        m = re.search(r"\d+", cmd[4:] if cmd and cmd.startswith("qtd:") else texto)
        p = db.query("SELECT id, descricao, quantidade FROM pecas WHERE id = %s AND criado_por = %s",
                     (e.get("peca_id"), ctx.admin_id), fetchone=True)
        if not p:
            e["step"] = "item"
            return _pergunta_item(ctx, e)
        ja = sum(i["quantidade"] for i in e["itens"] if i["peca_id"] == p["id"])
        if not m or not (0 < int(m.group()) <= p["quantidade"] - ja):
            return _resp(f"Informe uma quantidade entre 1 e {p['quantidade'] - ja}.", options=[CANCELAR], state=e)
        qtd = int(m.group())
        for i in e["itens"]:
            if i["peca_id"] == p["id"]:
                i["quantidade"] += qtd
                break
        else:
            e["itens"].append({"peca_id": p["id"], "quantidade": qtd, "descricao": p["descricao"]})
        e["step"] = "mais"
        return _resp(f"Adicionado: {qtd}x {p['descricao']}. Quer incluir mais algum item?",
                     options=[_opt("Adicionar outro item", "cmd:mais"), _opt("Concluir", "cmd:finalizar"), CANCELAR], state=e)

    if step == "outro":
        e["outro"] = texto.strip()[:100]
        e["step"] = "mais"
        return _resp("Item anotado. Quer incluir mais algum?",
                     options=[_opt("Adicionar outro item", "cmd:mais"), _opt("Concluir", "cmd:finalizar"), CANCELAR], state=e)

    if step == "mais":
        if cmd == "mais":
            e["step"] = "item"
            return _pergunta_item(ctx, e)
        e["step"] = "motivo"
        return _resp("Qual o motivo da requisição?", options=[_opt("Pular", "cmd:pular"), CANCELAR],
                     state=e, placeholder="Ex.: Substituição de item danificado")

    if step == "motivo":
        e["motivo"] = "" if cmd == "pular" else texto.strip()[:150]
        e["step"] = "confirma"
        s = db.query("SELECT nome FROM salas WHERE id = %s", (e.get("sala_id"),), fetchone=True)
        card = {"titulo": "Confirme a requisição", "linhas": [f"Sala: {s['nome'] if s else '—'}", f"Itens: {_resumo(e)}",
                                                              f"Motivo: {e['motivo'] or '—'}"]}
        return _resp("Está tudo certo?", cards=[card], options=[_opt("Confirmar", "cmd:confirmar"), CANCELAR], state=e)

    if step == "confirma" and cmd == "confirmar":
        s = db.query("SELECT id FROM salas WHERE id = %s AND criado_por = %s", (e.get("sala_id"), ctx.admin_id), fetchone=True)
        itens = []
        for i in e["itens"]:
            p = db.query("SELECT id, codigo, descricao, quantidade FROM pecas WHERE id = %s AND criado_por = %s",
                         (i["peca_id"], ctx.admin_id), fetchone=True)
            if not p or i["quantidade"] > p["quantidade"] or i["quantidade"] < 1:
                return _resp("Algum item mudou no estoque. Vamos recomeçar.", options=[_opt("Nova requisição", "cmd:nova")])
            itens.append({"peca_id": p["id"], "quantidade": i["quantidade"], "descricao": p["descricao"], "codigo": p["codigo"]})
        if not s or (not itens and not e["outro"]):
            return _resp("Faltam dados. Vamos recomeçar.", options=[_opt("Nova requisição", "cmd:nova")])
        pedido = ctx.montar_item_pedido(itens, e["outro"])
        if len(pedido) > 200:
            return _resp("A requisição ficou grande demais (máx. 200 caracteres). Faça duas requisições menores.",
                         options=[_opt("Nova requisição", "cmd:nova")])
        novo_id = db.query("INSERT INTO requisicoes (solicitante_id, sala_id, item_pedido, motivo) VALUES (%s, %s, %s, %s)",
                           (ctx.user_id, s["id"], pedido, e["motivo"]), commit=True)
        ctx.registrar_log(f"Requisição de '{pedido}' criada (via CampusBot).")
        return _resp(f"Pronto! Chamado #{novo_id} criado e aguardando avaliação.",
                     options=[_opt("Ver chamados", "cmd:chamados")])

    return _menu(ctx, "Não consegui continuar a requisição. O que deseja fazer?")


def _iniciar_requisicao(ctx):
    return _pergunta_sala(ctx, {"flow": "req", "step": "sala", "itens": [], "outro": "", "motivo": "",
                                "sala_id": None, "peca_id": None})


# ---------------------------------------------------------------- roteador
def responder(texto, estado, ctx):
    texto = (texto or "").strip()
    norm = _norm(texto)
    e = _limpar_estado(estado, ctx) if estado else None

    if norm in ("cmd:cancelar", "cancelar", "sair", "parar"):
        return _menu(ctx, "Cancelado. Em que posso ajudar?")
    if norm in ("cmd:inicio", ""):
        return _menu(ctx, f"Olá, {ctx.nome.split(' ')[0] or 'tudo bem'}! Sou o CampusBot. Posso mostrar chamados, "
                          "abrir uma requisição, consultar estoque e salas.")

    globais = ("cmd:chamados", "cmd:pendentes", "cmd:nova", "cmd:estoque", "cmd:salas", "cmd:logs", "menu", "ajuda")
    if e and e.get("flow") == "req" and norm not in globais:
        return _fluxo(ctx, texto, e)
    if e and e.get("flow") == "estoque" and norm not in globais and not norm.startswith("cmd:"):
        return _consultar_estoque(ctx, texto)

    if norm == "cmd:chamados":
        return _mostrar_chamados(ctx)
    if norm == "cmd:pendentes":
        return _mostrar_chamados(ctx, pendentes=True)
    if norm == "cmd:nova":
        return _iniciar_requisicao(ctx)
    if norm == "cmd:estoque":
        return _resp("Qual item você quer consultar? Digite o nome ou o código.",
                     state={"flow": "estoque"}, options=[CANCELAR], placeholder="Ex.: mouse")
    if norm == "cmd:salas":
        return _salas(ctx)
    if norm == "cmd:logs":
        return _logs(ctx)

    # texto livre
    m = re.search(r"#\s*(\d+)|\b(?:chamado|requisicao|pedido)\s+(\d+)", norm)
    if m:
        return _detalhe_chamado(ctx, int(m.group(1) or m.group(2)))
    if re.search(r"\b(nova|novo|criar|abrir|fazer|registrar|pedir)\b.*\b(requisicao|chamado|pedido)\b|\b(requisitar|solicitar)\b", norm):
        return _iniciar_requisicao(ctx)
    if re.search(r"\b(chamados?|requisicoes|requisicao|pedidos?)\b", norm):
        return _mostrar_chamados(ctx, pendentes="pendente" in norm, meus=bool(re.search(r"\b(meus|minhas|meu)\b", norm)))
    if "pendente" in norm:
        return _mostrar_chamados(ctx, pendentes=True)
    if re.search(r"\b(estoque|quantos|quantas|quantidade|disponivel|disponiveis|tem)\b", norm):
        termo = re.sub(r"\b(estoque|quantos|quantas|quantidade|disponivel|disponiveis|tem|de|do|da|no|na|em|o|a|os|as|ha|existe|ainda)\b|\?", " ", norm)
        termo = " ".join(termo.split())
        return _consultar_estoque(ctx, termo) if termo else _resp(
            "Qual item você quer consultar?", state={"flow": "estoque"}, options=[CANCELAR], placeholder="Ex.: mouse")
    if re.search(r"\b(salas?|laboratorios?|labs?)\b", norm):
        return _salas(ctx)
    if re.search(r"\b(logs?|historico|atividades?)\b", norm):
        return _logs(ctx)
    if re.search(r"\b(obrigad[oa]|valeu)\b", norm):
        return _menu(ctx, "Por nada! Posso ajudar em mais alguma coisa?")
    if re.search(r"\b(oi|ola|bom dia|boa tarde|boa noite|ajuda|menu|opcoes|comandos)\b", norm):
        return _menu(ctx, "Posso ajudar com:")
    return _menu(ctx, "Não entendi. Tente “meus chamados”, “nova requisição” ou “estoque de mouse”.")
