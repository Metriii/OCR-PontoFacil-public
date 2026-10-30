"""Leitura das planilhas geradas disponiveis em DIR_SAIDA.

A pasta `_out` e a fonte da verdade do historico: o que esta la pode ser
baixado e visualizado, independentemente do banco. As informacoes de modelo,
funcionarios e referencia vem da aba oculta `_PontoFacil`; arquivos sem essa
aba continuam listados, com os campos que derem para inferir do proprio .xlsx.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

from openpyxl import load_workbook

from . import config
from .excel import ABA_METADADOS

LIMITE_LINHAS_PREVIA = 200
LIMITE_COLUNAS_PREVIA = 50
LIMITE_ABAS_PREVIA = 20


class ErroPlanilha(RuntimeError):
    """Falha ao ler uma planilha para pre-visualizacao."""


def _iso_local(momento: float) -> str:
    return datetime.fromtimestamp(momento).astimezone().isoformat(timespec="seconds")


def _iso_gerado(texto: object) -> str | None:
    """Converte o `gerado_em` da planilha ("aaaa-mm-dd hh:mm:ss") para ISO."""
    if not texto:
        return None
    valor = str(texto).strip()
    if not valor:
        return None
    return valor.replace(" ", "T", 1)


def _sem_repetir(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    unicos: list[str] = []
    for valor in valores:
        chave = valor.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(valor)
    return unicos


def _ler_metadados(caminho: Path) -> dict[str, object]:
    """Extrai modelo/funcionarios/referencia da aba oculta, sem quebrar o arquivo."""
    vazio: dict[str, object] = {
        "modelo": None,
        "gerado_em": None,
        "funcionarios": [],
        "referencias": [],
    }
    try:
        wb = load_workbook(caminho, read_only=True, data_only=True)
    except Exception:
        return vazio

    try:
        abas = [nome for nome in wb.sheetnames if nome != ABA_METADADOS]
        if ABA_METADADOS not in wb.sheetnames:
            return {**vazio, "funcionarios": _sem_repetir(abas)}

        linhas = wb[ABA_METADADOS].iter_rows(values_only=True)
        cabecalho = next(linhas, None)
        if not cabecalho:
            return {**vazio, "funcionarios": _sem_repetir(abas)}

        colunas = {
            str(valor).strip(): indice
            for indice, valor in enumerate(cabecalho)
            if valor is not None
        }

        def coluna(linha: tuple[object, ...], nome: str) -> object:
            indice = colunas.get(nome)
            if indice is None or indice >= len(linha):
                return None
            return linha[indice]

        modelo: str | None = None
        gerado_em: str | None = None
        funcionarios: list[str] = []
        referencias: list[str] = []
        for linha in linhas:
            valor_modelo = str(coluna(linha, "modelo") or "").strip()
            if modelo is None and valor_modelo in config.MODELOS_VALIDOS:
                modelo = valor_modelo
            gerado_em = gerado_em or _iso_gerado(coluna(linha, "gerado_em"))
            funcionario = str(coluna(linha, "funcionario") or "").strip()
            if funcionario:
                funcionarios.append(funcionario)
            referencia = str(coluna(linha, "referencia") or "").strip()
            if referencia:
                referencias.append(referencia)

        return {
            "modelo": modelo,
            "gerado_em": gerado_em,
            "funcionarios": _sem_repetir(funcionarios) or _sem_repetir(abas),
            "referencias": _sem_repetir(referencias),
        }
    except Exception:
        return vazio
    finally:
        wb.close()


def _arquivos_xlsx(pasta: Path) -> list[Path]:
    try:
        return sorted(
            (caminho for caminho in pasta.glob("*.xlsx") if caminho.is_file()),
            key=lambda caminho: caminho.name.casefold(),
        )
    except OSError:
        return []


def listar_planilhas(diretorio: Path | None = None) -> list[dict[str, object]]:
    """Lista os .xlsx da pasta de saida, do mais recente para o mais antigo."""
    pasta = diretorio or config.DIR_SAIDA
    if not pasta.is_dir():
        return []

    itens: list[dict[str, object]] = []
    for caminho in _arquivos_xlsx(pasta):
        try:
            info = caminho.stat()
        except OSError:
            continue
        metadados = _ler_metadados(caminho)
        itens.append(
            {
                "arquivo": caminho.name,
                "tamanho": info.st_size,
                "modificado_em": _iso_local(info.st_mtime),
                "gerado_em": metadados["gerado_em"],
                "modelo": metadados["modelo"],
                "funcionarios": metadados["funcionarios"],
                "referencias": metadados["referencias"],
            }
        )

    itens.sort(
        key=lambda item: (str(item["gerado_em"] or ""), str(item["modificado_em"])),
        reverse=True,
    )
    return itens


def _texto_celula(valor: object) -> str | None:
    """Converte o valor da celula em texto exibivel no navegador."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M:%S").replace(" 00:00:00", "")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, time):
        return valor.strftime("%H:%M:%S").replace(":00", "")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    texto = str(valor).strip()
    return texto or None


def _sem_linhas_vazias(linhas: list[list[str | None]]) -> list[list[str | None]]:
    while linhas and not any(celula for celula in linhas[-1]):
        linhas.pop()
    return linhas


def ler_previa(
    caminho: Path,
    *,
    limite_linhas: int = LIMITE_LINHAS_PREVIA,
    limite_colunas: int = LIMITE_COLUNAS_PREVIA,
    limite_abas: int = LIMITE_ABAS_PREVIA,
) -> dict[str, object]:
    """Le uma planilha em modo somente leitura para exibir no navegador.

    A aba oculta ``_PontoFacil`` (metadados internos) nunca e exposta. Cada aba
    e limitada em linhas/colunas e o numero de abas tambem e limitado, para que
    arquivos grandes nao sobrecarreguem a resposta HTTP.
    """
    try:
        wb = load_workbook(caminho, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ErroPlanilha("Nao foi possivel ler a planilha.") from exc

    try:
        nomes = [nome for nome in wb.sheetnames if nome != ABA_METADADOS]
        abas: list[dict[str, object]] = []
        truncada = False
        for nome in nomes[:limite_abas]:
            aba = wb[nome]
            total_linhas = int(aba.max_row or 0)
            total_colunas = int(aba.max_column or 0)
            linhas: list[list[str | None]] = []
            for linha in aba.iter_rows(
                min_row=1,
                max_row=min(total_linhas, limite_linhas),
                max_col=min(total_colunas, limite_colunas),
                values_only=True,
            ):
                linhas.append([_texto_celula(valor) for valor in linha])
            _sem_linhas_vazias(linhas)
            limitada = (
                total_linhas > limite_linhas or total_colunas > limite_colunas
            )
            truncada = truncada or limitada
            abas.append(
                {
                    "nome": nome,
                    "linhas": linhas,
                    "total_linhas": total_linhas,
                    "total_colunas": total_colunas,
                    "truncada": limitada,
                }
            )

        return {
            "arquivo": caminho.name,
            "abas": abas,
            "abas_totais": len(nomes),
            "abas_omitidas": max(0, len(nomes) - limite_abas),
            "limite_linhas": limite_linhas,
            "limite_colunas": limite_colunas,
            "truncada": truncada or len(nomes) > limite_abas,
        }
    except Exception as exc:  # noqa: BLE001
        raise ErroPlanilha("Nao foi possivel ler a planilha.") from exc
    finally:
        wb.close()

