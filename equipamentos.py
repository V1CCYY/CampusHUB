"""Imagens genéricas por tipo de equipamento.

A categoria é descoberta pelo texto da descrição da peça (ex.: "Mouse USB" -> mouse).
Os ícones ficam em static/images/equipamentos/<categoria>.svg.
"""
import re
import unicodedata

from flask import url_for

# A ordem importa: a primeira categoria que casar vence.
CATEGORIAS = [
    ("notebook", ["notebook", "laptop", "netbook", "macbook", "chromebook"]),
    ("projetor", ["projetor", "datashow", "data show", "projector"]),
    ("monitor", ["monitor", "display", "tela"]),
    ("teclado", ["teclado", "keyboard"]),
    ("mouse", ["mouse", "mause"]),
    ("webcam", ["webcam", "camera"]),
    ("audio", ["headset", "fone", "headphone", "caixa de som", "microfone", "audio", "speaker"]),
    ("impressora", ["impressora", "toner", "cartucho", "scanner", "multifuncional"]),
    ("armazenamento", ["ssd", "hd", "hdd", "disco", "pendrive", "pen drive", "cartao de memoria", "sd card", "nvme"]),
    ("memoria", ["memoria", "ram", "ddr"]),
    ("cabo", ["cabo", "adaptador", "hdmi", "vga", "displayport", "usb", "conector", "extensor", "dvi", "rj45", "cat5", "cat6", "fio"]),
    ("rede", ["switch", "roteador", "router", "access point", "ponto de acesso", "patch panel", "modem", "wifi", "wi-fi", "antena", "rede"]),
    ("fonte", ["fonte", "carregador"]),
    ("energia", ["nobreak", "no-break", "no break", "estabilizador", "filtro de linha", "bateria"]),
    ("placa", ["placa", "processador", "cooler", "motherboard", "gpu", "chipset"]),
    ("computador", ["computador", "desktop", "gabinete", "cpu", "torre", "pc", "all in one", "all-in-one", "workstation"]),
]

_PADROES = [
    (chave, re.compile(r"\b(?:" + "|".join(re.escape(t) for t in termos) + r")(?:es|s)?\b"))
    for chave, termos in CATEGORIAS
]


def _normalizar(texto):
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )
    return sem_acento.lower()


def categoria_equipamento(descricao):
    texto = _normalizar(descricao)
    for chave, padrao in _PADROES:
        if padrao.search(texto):
            return chave
    return "generico"


def imagem_equipamento(descricao):
    """URL da imagem genérica do equipamento (uso nos templates: equip_img(item.descricao))."""
    return url_for("static", filename=f"images/equipamentos/{categoria_equipamento(descricao)}.svg")
