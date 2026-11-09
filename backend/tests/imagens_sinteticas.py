"""Imagens sinteticas para os testes da anonimizacao local.

Nenhum dado pessoal real e usado. As imagens servem para exercitar recorte,
redacao e validacao sem depender do PP-StructureV3.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from backend.anonimizacao.schemas import Caixa, CelulaTabela, DeteccaoEstrutural

LARGURA = 900
ALTURA = 1200
TOPO_TABELA = 300
BASE_TABELA = 1100
ESQUERDA_TABELA = 40
DIREITA_TABELA = 860


def criar_folha_sintetica(
    *,
    cabecalho: str = "EMPRESA ALFA\nNome: JOAO DA SILVA\nCPF: 123.456.789-00",
    linhas: int = 6,
) -> bytes:
    """Desenha uma folha ficticia com cabecalho e tabela de horarios."""
    imagem = Image.new("RGB", (LARGURA, ALTURA), "white")
    desenho = ImageDraw.Draw(imagem)

    y = 40
    for linha in cabecalho.splitlines():
        desenho.text((50, y), linha, fill="black")
        y += 35

    altura_linha = (BASE_TABELA - TOPO_TABELA) // max(1, linhas)
    for indice in range(linhas + 1):
        y = TOPO_TABELA + indice * altura_linha
        desenho.line((ESQUERDA_TABELA, y, DIREITA_TABELA, y), fill="black", width=2)
    for x in (ESQUERDA_TABELA, 150, 300, 450, 600, 750, DIREITA_TABELA):
        desenho.line((x, TOPO_TABELA, x, BASE_TABELA), fill="black", width=2)

    desenho.text((55, TOPO_TABELA + 8), "Dia", fill="black")
    desenho.text((160, TOPO_TABELA + 8), "Entrada", fill="black")
    desenho.text((310, TOPO_TABELA + 8), "Saida", fill="black")
    for indice in range(1, linhas):
        y = TOPO_TABELA + indice * altura_linha + 10
        desenho.text((55, y), f"{indice:02d}", fill="black")
        desenho.text((160, y), "08:00", fill="black")
        desenho.text((310, y), "17:00", fill="black")

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()


def deteccao_sintetica(
    *,
    texto_cabecalho: str = "EMPRESA ALFA\nNome: JOAO DA SILVA\nCPF: 123.456.789-00",
    caixas_tabela: tuple[Caixa, ...] = (),
) -> DeteccaoEstrutural:
    """Deteccao coerente com ``criar_folha_sintetica`` para testes unitarios."""
    caixas: list[Caixa] = []
    y = 40
    for linha in texto_cabecalho.splitlines():
        caixas.append(Caixa(50, y, 420, 24, texto=linha))
        y += 35

    caixas.extend(
        [
            Caixa(55, TOPO_TABELA + 8, 60, 18, texto="Dia"),
            Caixa(160, TOPO_TABELA + 8, 90, 18, texto="Entrada"),
            Caixa(310, TOPO_TABELA + 8, 90, 18, texto="Saida"),
            Caixa(55, TOPO_TABELA + 100, 60, 18, texto="01"),
            Caixa(160, TOPO_TABELA + 100, 90, 18, texto="08:00"),
            Caixa(310, TOPO_TABELA + 100, 90, 18, texto="17:00"),
        ]
    )
    caixas.extend(caixas_tabela)

    celulas = tuple(
        CelulaTabela(
            caixa=Caixa(
                x=float(x),
                y=float(TOPO_TABELA + linha * 100),
                largura=120.0,
                altura=100.0,
            ),
            linha=linha,
            coluna=coluna,
        )
        for linha in range(3)
        for coluna, x in enumerate((40, 160, 280))
    )

    return DeteccaoEstrutural(
        largura=LARGURA,
        altura=ALTURA,
        tabela=Caixa(
            ESQUERDA_TABELA,
            TOPO_TABELA,
            DIREITA_TABELA - ESQUERDA_TABELA,
            BASE_TABELA - TOPO_TABELA,
        ),
        cabecalho=Caixa(0, 0, LARGURA, TOPO_TABELA),
        caixas_texto=tuple(caixas),
        celulas=celulas,
        linhas_horizontais=tuple(
            float(TOPO_TABELA + linha * 100) for linha in range(9)
        ),
        confianca=0.99,
        modelo_versao="teste",
    )
