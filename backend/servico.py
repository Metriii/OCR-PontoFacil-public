"""Servicos de processamento do lote (expansao + OCR + mapeamento)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import config, logs, mcp_client, parser
from .anonimizacao import service as anonimizacao_service
from .anonimizacao.artefato import ArtefatoAnonimizado
from .anonimizacao.schemas import ResultadoAnonimizacao
from .mapper import map_registro
from .modelo2 import imagem as modelo2_imagem
from .modelo2 import mapper as modelo2_mapper
from .modelo2 import parser as modelo2_parser
from .modelo3 import mapper as modelo3_mapper
from .modelo3 import parser as modelo3_parser
from .modelo4 import imagem as modelo4_imagem
from .modelo4 import mapper as modelo4_mapper
from .modelo4 import parser as modelo4_parser
from .modelo5 import imagem as modelo5_imagem
from .modelo5 import mapper as modelo5_mapper
from .modelo5 import parser as modelo5_parser
from .modelos import FolhaProcessada

log = logging.getLogger("pontofacil")


@dataclass(frozen=True)
class _Fluxo:
    selecionar_grid: Callable[[str], list[list[str]] | None]
    nome_colaborador: Callable[[list[list[str]], str], str | None]
    referencia: Callable[[list[list[str]], str], str | None]
    linhas_dia: Callable[[list[list[str]]], list[list[str]]]
    map_registro: Callable[
        [list[str], int, str | None, str | None],
        tuple[Any, list[str]],
    ]
    manter_registro: Callable[[Any], bool]
    aceitar_sem_registros: bool = False
    jornada_prevista: Callable[[list[list[str]], str], Any] | None = None
    map_folha: Callable[
        [list[list[str]], str | None, str | None, Any],
        tuple[list[Any], list[list[str]]],
    ] | None = None
    preparar_imagem: Callable[[bytes], bytes] | None = None
    diagnostico: Callable[[list[list[str]], str], str] | None = None
    avisos_estrutura: Callable[[list[list[str]]], list[str]] | None = None
    validar_layout: Callable[[list[list[str]], str], str | None] | None = None
    salvar_ocr_sem_grid: bool = False
    modelo: str | None = None


_FLUXO_MODELO1 = _Fluxo(
    selecionar_grid=parser.selecionar_grid,
    nome_colaborador=parser.nome_colaborador,
    referencia=parser.referencia,
    linhas_dia=parser.linhas_dia,
    map_registro=map_registro,
    manter_registro=lambda _registro: True,
    modelo="modelo-1",
)

_FLUXO_MODELO2 = _Fluxo(
    selecionar_grid=modelo2_parser.selecionar_grid,
    nome_colaborador=modelo2_parser.nome_colaborador,
    referencia=modelo2_parser.referencia,
    linhas_dia=modelo2_parser.linhas_dia,
    map_registro=modelo2_mapper.map_registro,
    manter_registro=modelo2_mapper.registro_tem_conteudo,
    aceitar_sem_registros=True,
    jornada_prevista=modelo2_parser.jornada_prevista,
    map_folha=modelo2_mapper.mapear_folha,
    preparar_imagem=modelo2_imagem.preparar_imagem,
    modelo="modelo-2",
)

_FLUXO_MODELO3 = _Fluxo(
    selecionar_grid=modelo3_parser.selecionar_grid,
    nome_colaborador=modelo3_parser.nome_colaborador,
    referencia=modelo3_parser.referencia,
    linhas_dia=modelo3_parser.linhas_dia,
    map_registro=modelo3_mapper.map_registro,
    manter_registro=lambda _registro: True,
    map_folha=modelo3_mapper.mapear_folha,
    modelo="modelo-3",
)

_FLUXO_MODELO4 = _Fluxo(
    selecionar_grid=modelo4_parser.selecionar_grid,
    nome_colaborador=modelo4_parser.nome_colaborador,
    referencia=modelo4_parser.referencia,
    linhas_dia=modelo4_parser.linhas_dia,
    map_registro=modelo4_mapper.map_registro,
    manter_registro=modelo4_mapper.registro_tem_conteudo,
    map_folha=modelo4_mapper.mapear_folha_linha_unica,
    preparar_imagem=modelo4_imagem.preparar_imagem,
    diagnostico=modelo4_parser.diagnostico,
    avisos_estrutura=modelo4_parser.avisos_estrutura,
    validar_layout=modelo4_parser.validar_layout,
    modelo="modelo-4",
)

_FLUXO_MODELO5 = _Fluxo(
    selecionar_grid=modelo5_parser.selecionar_grid,
    nome_colaborador=modelo5_parser.nome_colaborador,
    referencia=modelo5_parser.referencia,
    linhas_dia=modelo5_parser.linhas_dia,
    map_registro=modelo5_mapper.map_registro,
    manter_registro=modelo5_mapper.registro_tem_conteudo,
    map_folha=modelo5_mapper.mapear_folha,
    preparar_imagem=modelo5_imagem.preparar_imagem,
    diagnostico=modelo5_parser.diagnostico,
    avisos_estrutura=modelo5_parser.avisos_estrutura,
    validar_layout=modelo5_parser.validar_layout,
    salvar_ocr_sem_grid=True,
    modelo="modelo-5",
)

_FLUXOS: dict[str, _Fluxo] = {
    "modelo-1": _FLUXO_MODELO1,
    "modelo-2": _FLUXO_MODELO2,
    "modelo-3": _FLUXO_MODELO3,
    "modelo-4": _FLUXO_MODELO4,
    "modelo-5": _FLUXO_MODELO5,
}


def fluxo_do_modelo(modelo: str) -> _Fluxo:
    """Devolve o fluxo do modelo validando o identificador."""
    try:
        return _FLUXOS[modelo]
    except KeyError as exc:
        raise ValueError(f"Modelo invalido: {modelo}") from exc


def _ext(nome: str) -> str:
    return Path(nome).suffix.lower()


def expandir_arquivos(
    arquivos: list[tuple[str, bytes]],
) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Separa imagens de ZIPs (expandindo o conteudo). Retorna (imagens, avisos)."""
    imagens: list[tuple[str, bytes]] = []
    avisos: list[str] = []

    for nome, dados in arquivos:
        base = Path(nome).name
        ext = _ext(base)
        if ext in config.EXTENSOES_IMAGEM:
            imagens.append((base, dados))
        elif ext in config.EXTENSOES_ZIP:
            try:
                with zipfile.ZipFile(io.BytesIO(dados)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        interno = info.filename
                        if interno.startswith("__MACOSX"):
                            continue
                        if _ext(interno) not in config.EXTENSOES_IMAGEM:
                            continue
                        imagens.append((Path(interno).name, zf.read(info)))
            except zipfile.BadZipFile:
                avisos.append(f'Nao foi possivel ler o ZIP "{base}".')
        else:
            avisos.append(f'Formato nao suportado: "{base}".')
    return imagens, avisos


async def _ocr_com_retry(
    sessao: Any,
    dados: bytes,
    nome: str,
    lote: str | None,
    preparar: Callable[[bytes], bytes] | None = None,
) -> str:
    """Executa o OCR com retentativas para falhas transitorias do provedor."""
    total = config.TENTATIVAS_OCR
    for tentativa in range(1, total + 1):
        try:
            if preparar is None:
                return await mcp_client.ocr_imagem(sessao, dados)
            return await mcp_client.ocr_imagem(sessao, dados, preparar)
        except Exception as exc:  # noqa: BLE001
            if tentativa >= total:
                raise
            espera = config.ESPERA_RETRY_OCR * tentativa
            logs.warning(
                "MCP PaddleOCR",
                f"OCR de {nome} falhou (tentativa {tentativa}/{total}): "
                f"{type(exc).__name__}: {exc}; nova tentativa em {espera:.0f}s",
                lote,
            )
            await asyncio.sleep(espera)
    raise AssertionError("fluxo de retentativa inesperado")


@dataclass(frozen=True)
class _ResultadoOCR:
    markdown: str | None = None
    erro: Exception | None = None
    segundos: float = 0.0


async def _ocr_uma(
    sessao: Any,
    semaforo: asyncio.Semaphore,
    indice: int,
    total: int,
    nome: str,
    dados: bytes,
    lote: str | None,
    preparar: Callable[[bytes], bytes] | None = None,
) -> _ResultadoOCR:
    async with semaforo:
        inicio = time.monotonic()
        try:
            markdown = await _ocr_com_retry(
                sessao, dados, nome, lote, preparar
            )
        except Exception as exc:  # noqa: BLE001
            duracao = time.monotonic() - inicio
            detalhe = f"{type(exc).__name__}: {exc}"
            log.warning("Falha no OCR de %s: %s", nome, detalhe)
            logs.error(
                "MCP PaddleOCR",
                f"Falha no OCR da imagem {indice}/{total} ({nome}): {detalhe}",
                lote,
            )
            return _ResultadoOCR(erro=exc, segundos=duracao)

        duracao = time.monotonic() - inicio
        logs.info(
            "MCP PaddleOCR",
            f"OCR {indice}/{total} concluido em {duracao:.2f}s: {nome}",
            lote,
        )
        return _ResultadoOCR(markdown=markdown, segundos=duracao)


async def _ocr_todas(
    sessao: Any,
    imagens: list[tuple[str, bytes]],
    lote: str | None,
    preparar: Callable[[bytes], bytes] | None = None,
) -> list[_ResultadoOCR]:
    if not imagens:
        return []

    semaforo = asyncio.Semaphore(config.CONCORRENCIA_OCR)
    total = len(imagens)
    tarefas = [
        asyncio.create_task(
            _ocr_uma(sessao, semaforo, indice, total, nome, dados, lote, preparar)
        )
        for indice, (nome, dados) in enumerate(imagens, start=1)
    ]
    return list(await asyncio.gather(*tarefas))


def _salvar_markdown_ocr(
    markdown: str, nome: str, lote: str | None
) -> Path | None:
    """Grava o OCR bruto de um cartao sem registros, para diagnostico."""
    if not markdown or not config.salvar_ocr_falha():
        return None
    try:
        pasta = config.DIR_LOGS / "ocr"
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{lote or 'avulso'}-{Path(nome).stem}.md"
        destino.write_text(markdown, encoding="utf-8")
        return destino
    except OSError as exc:  # noqa: BLE001
        log.warning("Nao foi possivel salvar o OCR de %s: %s", nome, exc)
        return None


def _processar_markdown(
    markdown: str,
    nome: str,
    origem_hash: str,
    indice: int,
    total: int,
    fluxo: _Fluxo,
    lote: str | None,
    texto_cabecalho: str | None = None,
) -> tuple[FolhaProcessada | None, list[str]]:
    grid = fluxo.selecionar_grid(markdown)
    if not grid:
        logs.warning(
            "OCR",
            f"Imagem {indice}/{total} sem folha reconhecida",
            lote,
        )
        if fluxo.salvar_ocr_sem_grid:
            salvo = _salvar_markdown_ocr(markdown, nome, lote)
            if salvo is not None:
                logs.info("OCR", f"OCR bruto salvo em {salvo}", lote)
        return None, [f'Nenhuma folha de ponto reconhecida em "{nome}".']

    if fluxo.validar_layout is not None:
        motivo = fluxo.validar_layout(grid, markdown)
        if motivo:
            logs.warning(
                "OCR",
                f"Imagem {indice}/{total} recusada: {motivo}",
                lote,
            )
            _salvar_markdown_ocr(markdown, nome, lote)
            return None, [f'"{nome}": {motivo}']

    # Nome, periodo e jornada vem do cabecalho lido localmente. O markdown
    # externo so contem a tabela anonimizada e nao deve ser a fonte desses
    # dados. O fallback para o markdown mantem compatibilidade com chamadas
    # antigas (por exemplo, scripts e testes que nao usam a camada local).
    texto_metadados = texto_cabecalho or markdown
    funcionario = fluxo.nome_colaborador(grid, texto_metadados)
    referencia = fluxo.referencia(grid, texto_metadados)
    linhas = fluxo.linhas_dia(grid)

    registros = []
    linhas_excel = []
    if fluxo.map_folha is not None:
        jornada = (
            fluxo.jornada_prevista(grid, texto_metadados)
            if fluxo.jornada_prevista is not None
            else None
        )
        registros, linhas_excel = fluxo.map_folha(
            linhas, referencia, funcionario, jornada
        )
    else:
        for i, linha in enumerate(linhas):
            registro, linha_excel = fluxo.map_registro(
                linha, i, referencia, funcionario
            )
            linhas_excel.append(linha_excel)
            if fluxo.manter_registro(registro):
                registros.append(registro)

    if not registros and not fluxo.aceitar_sem_registros:
        detalhe = fluxo.diagnostico(grid, markdown) if fluxo.diagnostico else ""
        logs.warning(
            "OCR",
            f"Imagem {indice}/{total} sem horarios reconhecidos"
            + (f": {detalhe}" if detalhe else ""),
            lote,
        )
        salvo = _salvar_markdown_ocr(markdown, nome, lote)
        if salvo is not None:
            logs.info("OCR", f"OCR bruto salvo em {salvo}", lote)
        return None, [f'Nenhum horario reconhecido em "{nome}".']

    avisos_folha: list[str] = []
    if registros and fluxo.avisos_estrutura is not None:
        for aviso in fluxo.avisos_estrutura(grid):
            avisos_folha.append(aviso)
            for registro in registros:
                registro.revisar = True
                if registro.confianca is None or registro.confianca > 0.7:
                    registro.confianca = 0.7
                registro.observacao = (
                    f"{registro.observacao} {aviso}"
                    if registro.observacao
                    else aviso
                )

    stem = Path(nome).stem
    logs.info(
        "OCR",
        f"Imagem {indice}/{total} mapeada: {len(registros)} registro(s)",
        lote,
    )
    folha = FolhaProcessada(
        nome=funcionario or stem,
        funcionario=funcionario,
        referencia=referencia,
        arquivo_origem=nome,
        registros=registros,
        linhas_excel=linhas_excel,
        origem_hash=origem_hash,
    )
    return folha, avisos_folha


async def _processar_com(
    imagens: list[tuple[str, bytes]],
    lote: str | None,
    fluxo: _Fluxo,
    estatisticas: dict[str, int] | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    if not imagens:
        return [], []

    total = len(imagens)
    logs.info(
        "OCR",
        f"Inicio do processamento de {total} imagem(ns), "
        f"concorrencia={config.CONCORRENCIA_OCR}",
        lote,
    )

    # A fronteira de privacidade fica antes de abrir o MCP: a partir daqui so
    # existem artefatos aprovados pela anonimizacao local.
    resultados_anon = await anonimizacao_service.processar_lote(
        imagens, lote, modelo=fluxo.modelo
    )
    aprovadas: list[
        tuple[str, ArtefatoAnonimizado, ResultadoAnonimizacao, str]
    ] = []
    avisos: list[str] = []
    for (nome, dados), resultado in zip(imagens, resultados_anon):
        if not resultado.aprovado or resultado.artefato is None:
            codigo = (
                resultado.codigo_falha.value
                if resultado.codigo_falha is not None
                else "ANONYMIZATION_ERROR"
            )
            avisos.append(f'"{nome}": {codigo}')
            continue
        aprovadas.append(
            (
                nome,
                resultado.artefato,  # type: ignore[arg-type]
                resultado,
                hashlib.sha256(dados).hexdigest(),
            )
        )

    folhas, avisos_ocr = await _processar_aprovadas(
        aprovadas, lote, fluxo, estatisticas, total_cartoes=total
    )
    return folhas, [*avisos, *avisos_ocr]


async def _processar_aprovadas(
    aprovadas: list[tuple[str, ArtefatoAnonimizado, ResultadoAnonimizacao, str]],
    lote: str | None,
    fluxo: _Fluxo,
    estatisticas: dict[str, int] | None = None,
    *,
    total_cartoes: int | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Segue o pipeline a partir de artefatos ja aprovados pela anonimizacao.

    ``aprovadas`` traz ``(nome, artefato, resultado_anon, origem_hash)``. Os
    bytes originais nao circulam aqui; o hash preserva o vinculo com o arquivo
    de origem sem manter a imagem em memoria.
    """
    folhas: list[FolhaProcessada] = []
    avisos: list[str] = []
    total = (
        len(aprovadas)
        if total_cartoes is None
        else max(len(aprovadas), total_cartoes)
    )
    bloqueadas = total - len(aprovadas)
    if estatisticas is not None:
        estatisticas["bloqueadas_anonimizacao"] = bloqueadas
        estatisticas["aprovadas_anonimizacao"] = len(aprovadas)

    if not aprovadas:
        logs.warning(
            "OCR",
            f"Nenhuma imagem aprovada pela anonimizacao ({bloqueadas} "
            "bloqueada(s)); MCP nao foi aberto.",
            lote,
        )
        return folhas, avisos

    if bloqueadas:
        logs.warning(
            "OCR",
            f"{bloqueadas} imagem(ns) bloqueada(s) pela anonimizacao; "
            f"{len(aprovadas)} seguir(am) para o OCR externo.",
            lote,
        )

    inicio_lote = time.monotonic()
    async with mcp_client.abrir_mcp() as sessao:
        resultados = await _ocr_todas(
            sessao,
            [(nome, artefato) for nome, artefato, _r, _h in aprovadas],
            lote,
            fluxo.preparar_imagem,
        )

    for indice, (
        (nome, _artefato, resultado_anon, origem_hash),
        resultado,
    ) in enumerate(zip(aprovadas, resultados), start=1):
        if resultado.erro is not None:
            detalhe = f"{type(resultado.erro).__name__}: {resultado.erro}"
            avisos.append(f'Falha ao ler "{nome}": {detalhe}')
            continue

        folha, avisos_imagem = _processar_markdown(
            resultado.markdown or "",
            nome,
            origem_hash,
            indice,
            len(aprovadas),
            fluxo,
            lote,
            texto_cabecalho=resultado_anon.texto_cabecalho,
        )
        avisos.extend(avisos_imagem)
        if folha is not None:
            folhas.append(folha)

    logs.info(
        "OCR",
        f"Processamento concluido: {len(folhas)} folha(s), "
        f"{len(avisos)} aviso(s) em {time.monotonic() - inicio_lote:.2f}s, "
        f"concorrencia={config.CONCORRENCIA_OCR}",
        lote,
    )
    return folhas, avisos


async def processar_folhas(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
    estatisticas: dict[str, int] | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline do Modelo 1 (mantido sem alteracao de comportamento)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO1, estatisticas)


async def processar_folhas_modelo2(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
    estatisticas: dict[str, int] | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline da folha diaria (Modelo 2)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO2, estatisticas)


async def processar_folhas_modelo3(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
    estatisticas: dict[str, int] | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline do cartao tradicional quinzenal (Modelo 3)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO3, estatisticas)


async def processar_folhas_modelo4(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
    estatisticas: dict[str, int] | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline do cartao quinzenal (Modelo 4)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO4, estatisticas)


async def processar_folhas_modelo5(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
    estatisticas: dict[str, int] | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline do registro com duas linhas por data (Modelo 5)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO5, estatisticas)


async def processar_folhas_aprovadas(
    modelo: str,
    aprovadas: list[tuple[str, ArtefatoAnonimizado, ResultadoAnonimizacao, str]],
    lote: str | None = None,
    estatisticas: dict[str, int] | None = None,
    *,
    total_cartoes: int | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Processa artefatos ja aprovados pela previa, sem reanonimizar."""
    return await _processar_aprovadas(
        aprovadas,
        lote,
        fluxo_do_modelo(modelo),
        estatisticas,
        total_cartoes=total_cartoes,
    )
