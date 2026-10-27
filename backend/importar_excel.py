"""Importa planilhas consolidadas (.xlsx) para o SQLite.

Uso (a partir da raiz do projeto):

    python -m backend.importar_excel backend/_out/6330ce8c28_consolidado.xlsx

Cada aba vira um funcionario e cada linha vira um registro de ponto. A coluna A
traz somente o dia do mes (1..31) e e gravada assim em ``data_pontos``; as
colunas B, C, D e E trazem entrada, saida para intervalo, volta do intervalo e
saida final. A coluna F (``Hora total``) e ignorada. Dias sem nenhuma das
quatro batidas permanecem no Excel, mas nao sao gravados no banco.

Planilhas geradas pelo PontoFacil possuem a aba muito oculta ``_PontoFacil``
com o modelo, o lote, o funcionario real e a referencia de cada aba. Arquivos
sem essa aba continuam aceitos na importacao manual, usando o nome da aba como
funcionario.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from . import banco, config, excel, logs
from .modelos import FolhaProcessada, Registro

_HORA_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
_DIA_RE = re.compile(r"^\s*(\d{1,2})(?:\D.*)?$")
_DATA_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VAZIOS = {"", "-", "--", "—", "——", "---", "n/a", "na"}

_CABECALHO_BASE = [
    "Dia da semana",
    "Entrar",
    "Saída para intervalo",
    "Volta intervalo",
    "Saída",
    "Hora total",
]
_CABECALHO_MODELO2 = [*_CABECALHO_BASE, "Revisar"]


class PlanilhaIgnorada(RuntimeError):
    """Arquivo que nao deve ser sincronizado automaticamente."""


def _texto(valor: object) -> str:
    return "" if valor is None else str(valor).strip()


def _normalizar_cabecalho(valor: object) -> str:
    sem_acento = (
        unicodedata.normalize("NFKD", _texto(valor))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento.casefold()).split())


def _cabecalho_esperado(modelo: str) -> list[str]:
    if modelo == "modelo-2":
        return _CABECALHO_MODELO2
    return _CABECALHO_BASE


def _dia(valor: object) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, datetime):
        return valor.day if 1 <= valor.day <= 31 else None
    if isinstance(valor, date):
        return valor.day if 1 <= valor.day <= 31 else None
    if isinstance(valor, (int, float)):
        dia = int(valor)
        return dia if 1 <= dia <= 31 else None

    texto = _texto(valor)
    if _DATA_ISO_RE.match(texto):
        try:
            return datetime.strptime(texto, "%Y-%m-%d").day
        except ValueError:
            return None
    encontrado = _DIA_RE.match(texto)
    if not encontrado:
        return None
    dia = int(encontrado.group(1))
    return dia if 1 <= dia <= 31 else None


def _ler_hora(valor: object) -> tuple[str | None, str]:
    """Retorna (horario normalizado, estado): vazio, ok, invalido ou formula."""
    if valor is None:
        return None, "vazio"
    if isinstance(valor, bool):
        return None, "invalido"
    if isinstance(valor, datetime):
        valor = valor.time()
    if isinstance(valor, time):
        return f"{valor.hour:02d}:{valor.minute:02d}", "ok"
    if isinstance(valor, (int, float)):
        numero = float(valor)
        if not 0 <= numero < 1:
            return None, "invalido"
        minutos = int(round(numero * 24 * 60)) % (24 * 60)
        return f"{minutos // 60:02d}:{minutos % 60:02d}", "ok"

    texto = _texto(valor)
    if texto.casefold() in _VAZIOS:
        return None, "vazio"
    if texto.startswith("="):
        return None, "formula"
    encontrado = _HORA_RE.search(texto)
    if not encontrado:
        return None, "invalido"
    hora, minuto = int(encontrado.group(1)), int(encontrado.group(2))
    if not (0 <= hora < 24 and 0 <= minuto < 60):
        return None, "invalido"
    return f"{hora:02d}:{minuto:02d}", "ok"


def _hora(valor: object) -> str | None:
    return _ler_hora(valor)[0]


def _slug(texto: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (texto or "").lower()).strip("-")
    return base or "folha"


def _data_processado_iso(valor: object) -> str | None:
    texto = _texto(valor)
    if not texto:
        return None
    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _ler_metadados(pasta) -> dict:
    if excel.ABA_METADADOS not in pasta.sheetnames:
        return {}

    aba = pasta[excel.ABA_METADADOS]
    linhas = list(aba.iter_rows(values_only=True))
    if not linhas:
        return {}

    cabecalho = [_normalizar_cabecalho(valor) for valor in linhas[0]]
    posicoes = {nome: indice for indice, nome in enumerate(cabecalho)}

    def campo(linha: tuple, nome: str) -> object:
        indice = posicoes.get(_normalizar_cabecalho(nome))
        if indice is None or indice >= len(linha):
            return None
        return linha[indice]

    por_titulo: dict[str, dict] = {}
    por_indice: dict[int, dict] = {}
    modelo = ""
    lote = ""
    data_processado = None

    for linha in linhas[1:]:
        info = {
            "aba": _texto(campo(linha, "aba")),
            "funcionario": _texto(campo(linha, "funcionario")),
            "referencia": _texto(campo(linha, "referencia")),
            "origem_hash": _texto(campo(linha, "origem_hash")),
            "data_processado": _data_processado_iso(campo(linha, "data_processado")),
        }
        if not any(info.values()):
            continue

        modelo = modelo or _texto(campo(linha, "modelo"))
        lote = lote or _texto(campo(linha, "lote"))
        data_processado = data_processado or info["data_processado"]

        if info["aba"]:
            por_titulo[info["aba"]] = info
        try:
            indice = int(campo(linha, "indice"))
        except (TypeError, ValueError):
            indice = 0
        if indice > 0:
            por_indice[indice] = info

    if not por_titulo and not por_indice:
        return {}

    return {
        "modelo": modelo or None,
        "lote": lote or None,
        "data_processado": data_processado,
        "por_titulo": por_titulo,
        "por_indice": por_indice,
    }


def _cabecalho_da_aba(aba) -> list[object]:
    linha = next(aba.iter_rows(min_row=1, max_row=1, values_only=True), ())
    return list(linha)


def _cabecalho_valido(linha: list[object], modelo: str) -> bool:
    esperado = _cabecalho_esperado(modelo)[:6]
    normalizado = [_normalizar_cabecalho(valor) for valor in linha[:6]]
    return normalizado == [_normalizar_cabecalho(valor) for valor in esperado]


def _modelo_pelo_cabecalho(linha: list[object]) -> str | None:
    normalizado = [_normalizar_cabecalho(valor) for valor in linha]
    if len(normalizado) >= 7 and normalizado[6] == "revisar":
        return "modelo-2"
    return None


def _resolver_modelo(
    metadados: dict,
    informado: str | None,
    primeira_linha: list[object],
) -> str:
    modelo_meta = metadados.get("modelo")
    if informado and informado not in config.MODELOS_VALIDOS:
        raise ValueError(f"Modelo invalido: {informado}")
    if modelo_meta and modelo_meta not in config.MODELOS_VALIDOS:
        raise ValueError(f"Modelo invalido nos metadados: {modelo_meta}")
    if informado and modelo_meta and informado != modelo_meta:
        raise ValueError(
            f"Modelo informado ({informado}) difere dos metadados ({modelo_meta})."
        )

    return (
        informado
        or modelo_meta
        or _modelo_pelo_cabecalho(primeira_linha)
        or "modelo-1"
    )


def _ler_planilha(
    caminho: Path,
    modelo: str | None = None,
    exigir_metadados: bool = False,
) -> tuple[list[FolhaProcessada], str, dict, int, int]:
    conteudo = caminho.read_bytes()
    origem_hash = hashlib.sha256(conteudo).hexdigest()
    pasta = load_workbook(BytesIO(conteudo), read_only=True, data_only=False)
    try:
        metadados = _ler_metadados(pasta)
        if exigir_metadados and not metadados:
            raise PlanilhaIgnorada("planilha sem metadados do PontoFacil")

        abas_visiveis = [
            aba
            for aba in pasta.worksheets
            if aba.title != excel.ABA_METADADOS and aba.sheet_state == "visible"
        ]
        primeira_linha = _cabecalho_da_aba(abas_visiveis[0]) if abas_visiveis else []
        modelo_final = _resolver_modelo(metadados, modelo, primeira_linha)

        folhas: list[FolhaProcessada] = []
        lidos = 0
        invalidos = 0
        indice_visivel = 0

        for aba in abas_visiveis:
            indice_visivel += 1
            info = (
                metadados.get("por_titulo", {}).get(aba.title)
                or metadados.get("por_indice", {}).get(indice_visivel)
                or {}
            )
            funcionario = info.get("funcionario") or _texto(aba.title) or "Nao identificado"
            referencia = info.get("referencia") or None
            origem = info.get("origem_hash") or origem_hash
            data_lote = info.get("data_processado") or metadados.get("data_processado")

            cabecalho = _cabecalho_da_aba(aba)
            if not _cabecalho_valido(cabecalho, modelo_final):
                invalidos += 1
                logs.warning(
                    "ImportacaoExcel",
                    f"Aba '{aba.title}' ignorada: cabecalho incompativel",
                    metadados.get("lote"),
                )
                continue

            por_dia: dict[int, tuple[Registro, list[str]]] = {}
            for numero_linha, linha in enumerate(
                aba.iter_rows(min_row=2, values_only=True), start=2
            ):
                valores = list(linha) + [None] * (6 - len(linha))
                dia = _dia(valores[0])
                conteudo_horarios = any(_texto(valor) for valor in valores[1:5])

                if dia is None:
                    if conteudo_horarios:
                        invalidos += 1
                        logs.warning(
                            "ImportacaoExcel",
                            f"Aba '{aba.title}', linha {numero_linha}: dia invalido; "
                            "linha ignorada",
                            metadados.get("lote"),
                        )
                    continue

                estados: list[str] = []
                horas: list[str | None] = []
                for valor in valores[1:5]:
                    hora, estado = _ler_hora(valor)
                    horas.append(hora)
                    estados.append(estado)

                if any(estado in {"invalido", "formula"} for estado in estados):
                    invalidos += 1
                    logs.warning(
                        "ImportacaoExcel",
                        f"Aba '{aba.title}', linha {numero_linha}: horario "
                        "invalido/formula; linha ignorada",
                        metadados.get("lote"),
                    )
                    continue

                lidos += 1
                presentes = sum(hora is not None for hora in horas)
                revisar = presentes < 4
                if modelo_final == "modelo-2" and len(valores) >= 7:
                    revisar = _texto(valores[6]).casefold() in {
                        "sim",
                        "s",
                        "true",
                        "1",
                        "x",
                    }

                registro = Registro(
                    id=f"{_slug(funcionario)}-{dia}-{numero_linha}",
                    funcionario=funcionario,
                    data=str(dia),
                    entrada=horas[0],
                    saida_almoco=horas[1],
                    volta_almoco=horas[2],
                    saida=horas[3],
                    confianca=round(presentes / 4, 2),
                    revisar=revisar,
                )
                linha_excel = [
                    str(dia),
                    horas[0] or "",
                    horas[1] or "",
                    horas[2] or "",
                    horas[3] or "",
                    "",
                ]
                por_dia[dia] = (registro, linha_excel)

            if not por_dia:
                continue

            folhas.append(
                FolhaProcessada(
                    nome=funcionario,
                    funcionario=funcionario,
                    referencia=referencia,
                    arquivo_origem=caminho.name,
                    registros=[item[0] for item in por_dia.values()],
                    linhas_excel=[item[1] for item in por_dia.values()],
                    origem_hash=origem,
                    data_processado=data_lote,
                )
            )

        return folhas, modelo_final, metadados, lidos, invalidos
    finally:
        pasta.close()


def ler_folhas(
    caminho: Path,
    modelo: str | None = None,
    exigir_metadados: bool = False,
) -> list[FolhaProcessada]:
    """Le o .xlsx e devolve uma ``FolhaProcessada`` por aba."""
    return _ler_planilha(caminho, modelo, exigir_metadados)[0]


def importar(
    caminho: Path,
    modelo: str | None = None,
    exigir_metadados: bool = False,
) -> dict[str, int]:
    """Sincroniza o .xlsx com o banco, inserindo ou atualizando linhas."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    folhas, modelo_final, metadados, lidos, invalidos = _ler_planilha(
        caminho, modelo, exigir_metadados
    )
    if not folhas:
        return {
            "lidos": lidos,
            "inseridos": 0,
            "atualizados": 0,
            "inalterados": 0,
            "vazios": 0,
            "invalidos": invalidos,
        }

    config.garantir_diretorios()
    banco.inicializar()
    resultado = banco.sincronizar_folhas(
        folhas,
        modelo=modelo_final,
        lote=metadados.get("lote"),
        data_processado=metadados.get("data_processado"),
    )
    return {
        "lidos": lidos,
        "inseridos": resultado["inseridos"],
        "atualizados": resultado["atualizados"],
        "inalterados": resultado["inalterados"],
        "vazios": resultado["vazios"],
        "invalidos": invalidos + resultado["ignorados"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importa uma planilha consolidada (.xlsx) para o SQLite."
    )
    parser.add_argument("arquivo", type=Path, help="Caminho do .xlsx consolidado")
    parser.add_argument(
        "--modelo",
        default=None,
        choices=sorted(config.MODELOS_VALIDOS),
        help="Modelo de origem (padrao: metadados ou inferido)",
    )
    args = parser.parse_args(argv)

    try:
        resultado = importar(args.arquivo, args.modelo)
    except Exception as exc:  # noqa: BLE001
        print(f"Falha ao importar {args.arquivo}: {exc}")
        return 1

    print(f"Arquivo: {args.arquivo}")
    print(f"Modelo: {args.modelo or 'metadados/inferido'}")
    print(
        "Lidos: {lidos} | Inseridos: {inseridos} | Atualizados: {atualizados} | "
        "Inalterados: {inalterados} | Vazios: {vazios} | Invalidos: {invalidos}".format(
            **resultado
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
