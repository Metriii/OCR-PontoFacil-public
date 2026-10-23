"""Importa planilhas consolidadas (.xlsx) para o SQLite.

Uso (a partir da raiz do projeto):

    python -m backend.importar_excel backend/_out/6330ce8c28_consolidado.xlsx

Cada aba vira um funcionario e cada linha vira um registro de ponto. A coluna A
traz somente o dia do mes (1..31) e e gravada assim em ``data_pontos``; as
colunas B, C, D e E trazem entrada, saida para intervalo, volta do intervalo e
saida final. A coluna F (``Hora total``) e ignorada. Dias sem nenhuma das
quatro batidas permanecem no Excel, mas nao sao gravados no banco.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from datetime import time
from pathlib import Path

from openpyxl import load_workbook

from . import banco, config
from .modelos import FolhaProcessada, Registro

_HORA_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
_DIA_RE = re.compile(r"^\s*(\d{1,2})(?:\D.*)?$")


def _texto(valor: object) -> str:
    return "" if valor is None else str(valor).strip()


def _dia(valor: object) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        dia = int(valor)
        return dia if 1 <= dia <= 31 else None
    encontrado = _DIA_RE.match(_texto(valor))
    if not encontrado:
        return None
    dia = int(encontrado.group(1))
    return dia if 1 <= dia <= 31 else None


def _hora(valor: object) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, time):
        return f"{valor.hour:02d}:{valor.minute:02d}"
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        minutos = int(round(float(valor) * 24 * 60)) % (24 * 60)
        return f"{minutos // 60:02d}:{minutos % 60:02d}"
    encontrado = _HORA_RE.search(_texto(valor))
    if not encontrado:
        return None
    hora, minuto = int(encontrado.group(1)), int(encontrado.group(2))
    if not (0 <= hora < 24 and 0 <= minuto < 60):
        return None
    return f"{hora:02d}:{minuto:02d}"


def _slug(texto: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (texto or "").lower()).strip("-")
    return base or "folha"


def ler_folhas(caminho: Path) -> list[FolhaProcessada]:
    """Le o .xlsx e devolve uma ``FolhaProcessada`` por aba."""
    origem_hash = hashlib.sha256(caminho.read_bytes()).hexdigest()
    pasta = load_workbook(caminho, read_only=True, data_only=True)
    folhas: list[FolhaProcessada] = []
    try:
        for aba in pasta.worksheets:
            funcionario = _texto(aba.title) or "Nao identificado"
            registros: list[Registro] = []
            linhas_excel: list[list[str]] = []

            for indice, linha in enumerate(
                aba.iter_rows(min_row=2, values_only=True)
            ):
                valores = list(linha) + [None] * (5 - len(linha))
                dia = _dia(valores[0])
                if dia is None:
                    continue

                entrada = _hora(valores[1])
                saida_almoco = _hora(valores[2])
                volta_almoco = _hora(valores[3])
                saida = _hora(valores[4])
                pontas = [entrada, saida_almoco, volta_almoco, saida]
                presentes = sum(ponta is not None for ponta in pontas)

                registros.append(
                    Registro(
                        id=f"{_slug(funcionario)}-{dia}-{indice}",
                        funcionario=funcionario,
                        data=str(dia),
                        entrada=entrada,
                        saida_almoco=saida_almoco,
                        volta_almoco=volta_almoco,
                        saida=saida,
                        confianca=round(presentes / 4, 2),
                        revisar=presentes < 4,
                    )
                )
                linhas_excel.append(
                    [
                        str(dia),
                        entrada or "",
                        saida_almoco or "",
                        volta_almoco or "",
                        saida or "",
                        "",
                    ]
                )

            if not registros:
                continue

            folhas.append(
                FolhaProcessada(
                    nome=funcionario,
                    funcionario=funcionario,
                    arquivo_origem=caminho.name,
                    registros=registros,
                    linhas_excel=linhas_excel,
                    origem_hash=origem_hash,
                )
            )
    finally:
        pasta.close()

    return folhas


def importar(caminho: Path, modelo: str = "modelo-1") -> dict[str, int]:
    """Importa o .xlsx para o banco. Reimportacoes sao deduplicadas."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    folhas = ler_folhas(caminho)
    if not folhas:
        return {"inseridos": 0, "duplicados": 0, "ignorados": 0, "vazios": 0}

    config.garantir_diretorios()
    banco.inicializar()
    return banco.inserir_folhas(folhas, modelo=modelo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importa uma planilha consolidada (.xlsx) para o SQLite."
    )
    parser.add_argument("arquivo", type=Path, help="Caminho do .xlsx consolidado")
    parser.add_argument(
        "--modelo",
        default="modelo-1",
        choices=sorted(config.MODELOS_VALIDOS),
        help="Modelo de origem (padrao: modelo-1)",
    )
    args = parser.parse_args(argv)

    try:
        resultado = importar(args.arquivo, args.modelo)
    except Exception as exc:  # noqa: BLE001
        print(f"Falha ao importar {args.arquivo}: {exc}")
        return 1

    print(f"Arquivo: {args.arquivo}")
    print(f"Modelo: {args.modelo}")
    print(
        "Inseridos: {inseridos} | Duplicados: {duplicados} | "
        "Ignorados: {ignorados}".format(**resultado)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
