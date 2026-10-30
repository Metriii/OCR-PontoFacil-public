"""Persistencia dos registros de ponto em SQLite.

O banco e criado automaticamente e fica fora do controle de versao. A chave
unica evita duplicidades de recarregamentos/reprocessamentos sem depender
apenas de nome e data.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from . import config, logs
from .modelos import FolhaProcessada, Registro

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS registros_ponto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_funcionario TEXT NOT NULL,
    data_pontos TEXT NOT NULL,
    entrada TEXT,
    saida_intervalo TEXT,
    volta_intervalo TEXT,
    saida_final TEXT,
    data_processado TEXT NOT NULL,
    modelo TEXT NOT NULL,
    chave_unica TEXT NOT NULL UNIQUE,
    origem_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_registros_funcionario_data
    ON registros_ponto (nome_funcionario, data_pontos);
CREATE INDEX IF NOT EXISTS idx_registros_modelo_data
    ON registros_ponto (modelo, data_pontos);
CREATE INDEX IF NOT EXISTS idx_registros_processado
    ON registros_ponto (data_processado);
CREATE TRIGGER IF NOT EXISTS trg_ignorar_dia_sem_horarios
BEFORE INSERT ON registros_ponto
FOR EACH ROW
WHEN COALESCE(TRIM(NEW.entrada), '') = ''
 AND COALESCE(TRIM(NEW.saida_intervalo), '') = ''
 AND COALESCE(TRIM(NEW.volta_intervalo), '') = ''
 AND COALESCE(TRIM(NEW.saida_final), '') = ''
BEGIN
    SELECT RAISE(IGNORE);
END;
"""

_CAMPOS = (
    "id, nome_funcionario, data_pontos, entrada, saida_intervalo, "
    "volta_intervalo, saida_final, data_processado, modelo"
)

_HORA_RE = re.compile(r"^\d{2}:\d{2}$")
_DIA_MES_RE = re.compile(r"^(\d{1,2})(?:\D.*)?$")
_CAMPOS_HORARIO = (
    "entrada",
    "saida_almoco",
    "volta_almoco",
    "saida",
)


class ErroBanco(RuntimeError):
    """Falha de inicializacao, consulta ou gravacao no SQLite."""


def _sem_horarios(registro: Registro) -> bool:
    """Dia sem nenhuma das quatro batidas nao gera linha no banco."""
    return all(
        not (getattr(registro, campo) or "").strip() for campo in _CAMPOS_HORARIO
    )


def _conectar() -> sqlite3.Connection:
    config.ARQUIVO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(config.ARQUIVO_BANCO, timeout=15)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA journal_mode=WAL")
    conexao.execute("PRAGMA busy_timeout=15000")
    return conexao


def conectar() -> sqlite3.Connection:
    """Conexao publica para os modulos de autenticacao e auditoria."""
    return _conectar()


def inicializar() -> None:
    """Cria o banco/tabela/indices, sem apagar dados existentes."""
    conexao = _conectar()
    try:
        with conexao:
            conexao.executescript(_ESQUEMA)
            conexao.execute("PRAGMA user_version=2")
    except sqlite3.Error as exc:
        logs.error("SQLite", f"Falha ao inicializar banco: {exc}")
        raise ErroBanco(f"Falha ao inicializar o banco SQLite: {exc}") from exc
    finally:
        conexao.close()

    logs.info("SQLite", "Banco inicializado", lote=None)


def _normalizar_nome(nome: str) -> str:
    sem_acento = (
        unicodedata.normalize("NFKD", nome or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return " ".join(sem_acento.casefold().split())


def _data_iso(valor: str | None) -> str | None:
    texto = (valor or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return None


def _dia_mes(valor: str | None) -> str | None:
    """Aceita apenas o dia do mes (1..31), com ou sem texto adicional.

    A planilha consolidada nao traz mes/ano; nesse caso ``data_pontos`` guarda
    somente o dia, por exemplo ``"1"`` ou ``"27"`` (de ``"27 - FERIADO"``).
    """
    texto = (valor or "").strip()
    encontrado = _DIA_MES_RE.match(texto)
    if not encontrado:
        return None
    dia = int(encontrado.group(1))
    return str(dia) if 1 <= dia <= 31 else None


def _hora(valor: str | None) -> str | None:
    texto = (valor or "").strip()
    return texto if _HORA_RE.match(texto) else None


def _dia_de_data_pontos(valor: str | None) -> int | None:
    """Extrai o dia tanto de ``1``/``27 - FERIADO`` quanto de ``2026-10-01``."""
    texto = (valor or "").strip()
    iso = _data_iso(texto)
    if iso:
        return int(iso[-2:])
    dia = _dia_mes(texto)
    return int(dia) if dia else None


def _chave_unica(
    modelo: str,
    nome: str,
    data_pontos: str,
    entrada: str | None,
    saida_intervalo: str | None,
    volta_intervalo: str | None,
    saida_final: str | None,
) -> str:
    partes = [
        modelo,
        _normalizar_nome(nome),
        data_pontos,
        entrada or "-",
        saida_intervalo or "-",
        volta_intervalo or "-",
        saida_final or "-",
    ]
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


def _registro_para_linha(
    registro: Registro,
    folha: FolhaProcessada,
    modelo: str,
    data_processado: str,
) -> tuple[tuple, str] | None:
    nome = (
        registro.funcionario
        or folha.funcionario
        or folha.nome
        or "Não identificado"
    ).strip()
    data_pontos = _data_iso(registro.data) or _dia_mes(registro.data)
    if not data_pontos:
        return None

    entrada = _hora(registro.entrada)
    saida_intervalo = _hora(registro.saida_almoco)
    volta_intervalo = _hora(registro.volta_almoco)
    saida_final = _hora(registro.saida)
    chave = _chave_unica(
        modelo,
        nome,
        data_pontos,
        entrada,
        saida_intervalo,
        volta_intervalo,
        saida_final,
    )
    valores = (
        nome,
        data_pontos,
        entrada,
        saida_intervalo,
        volta_intervalo,
        saida_final,
        data_processado,
        modelo,
        chave,
        folha.origem_hash,
    )
    return valores, chave


def inserir_folhas(
    folhas: list[FolhaProcessada],
    modelo: str,
    lote: str | None = None,
    data_processado: str | None = None,
) -> dict[str, int]:
    """Persiste os registros de um lote em uma unica transacao.

    Retorna ``{"inseridos", "duplicados", "ignorados", "vazios"}``. Dias sem
    nenhuma das quatro batidas nao sao gravados; registros sem data valida sao
    ignorados e horarios ausentes viram NULL.
    """
    if modelo not in config.MODELOS_VALIDOS:
        raise ValueError(f"Modelo invalido: {modelo}")

    data_processado = data_processado or logs.agora().date().isoformat()
    linhas: list[tuple] = []
    ignorados = 0
    vazios = 0

    for folha in folhas:
        for registro in folha.registros:
            if _sem_horarios(registro):
                vazios += 1
                continue
            linha = _registro_para_linha(registro, folha, modelo, data_processado)
            if linha is None:
                ignorados += 1
                continue
            linhas.append(linha[0])

    inseridos = 0
    duplicados = 0
    if linhas:
        conexao = _conectar()
        try:
            with conexao:
                for valores in linhas:
                    cursor = conexao.execute(
                        """
                        INSERT OR IGNORE INTO registros_ponto (
                            nome_funcionario, data_pontos, entrada,
                            saida_intervalo, volta_intervalo, saida_final,
                            data_processado, modelo, chave_unica, origem_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        valores,
                    )
                    if cursor.rowcount:
                        inseridos += 1
                    else:
                        duplicados += 1
        except sqlite3.Error as exc:
            logs.error("SQLite", f"Falha ao persistir registros: {exc}", lote)
            raise ErroBanco(f"Falha ao persistir os registros: {exc}") from exc
        finally:
            conexao.close()

    if ignorados:
        logs.warning(
            "SQLite",
            f"{ignorados} registro(s) ignorado(s) por data ausente/invalida",
            lote,
        )
    if vazios:
        logs.info(
            "SQLite",
            f"{vazios} dia(s) sem horarios nao persistido(s); "
            "permanecem apenas no Excel",
            lote,
        )
    logs.info(
        "SQLite",
        f"Persistencia concluida: inseridos={inseridos}, "
        f"duplicados={duplicados}, ignorados={ignorados}, vazios={vazios}",
        lote,
    )
    return {
        "inseridos": inseridos,
        "duplicados": duplicados,
        "ignorados": ignorados,
        "vazios": vazios,
    }


def sincronizar_folhas(
    folhas: list[FolhaProcessada],
    modelo: str,
    lote: str | None = None,
    data_processado: str | None = None,
) -> dict[str, int]:
    """Insere ou atualiza registros de planilhas editadas.

    A linha existente e localizada por modelo + nome normalizado + dia. O
    ``UPDATE`` usa a chave primaria e altera apenas os horarios que mudaram e a
    ``chave_unica``; ``data_processado`` e ``origem_hash`` de linhas existentes
    sao preservados para nao quebrar o agrupamento do resumo por lote.
    """
    if modelo not in config.MODELOS_VALIDOS:
        raise ValueError(f"Modelo invalido: {modelo}")

    resultado = {
        "inseridos": 0,
        "atualizados": 0,
        "inalterados": 0,
        "vazios": 0,
        "ignorados": 0,
    }
    if not folhas:
        return resultado

    hoje = logs.agora().date().isoformat()
    conexao = _conectar()
    avisos_duplicidade: set[tuple[int, str]] = set()
    try:
        with conexao:
            indice: dict[tuple[int, str], list[dict]] = {}
            for linha in conexao.execute(
                f"SELECT {_CAMPOS}, chave_unica, origem_hash "
                "FROM registros_ponto WHERE modelo = ?",
                (modelo,),
            ):
                registro = dict(linha)
                dia = _dia_de_data_pontos(registro["data_pontos"])
                if dia is None:
                    continue
                chave_logica = (dia, _normalizar_nome(registro["nome_funcionario"]))
                indice.setdefault(chave_logica, []).append(registro)

            for folha in folhas:
                data_lote = folha.data_processado or data_processado or hoje
                for registro in folha.registros:
                    if _sem_horarios(registro):
                        resultado["vazios"] += 1
                        continue

                    linha = _registro_para_linha(
                        registro, folha, modelo, data_lote
                    )
                    if linha is None:
                        resultado["ignorados"] += 1
                        continue

                    valores, chave_nova = linha
                    dia = _dia_de_data_pontos(valores[1])
                    chave_logica = (dia, _normalizar_nome(valores[0]))
                    candidatos = indice.setdefault(chave_logica, [])
                    if not candidatos:
                        cursor = conexao.execute(
                            """
                            INSERT INTO registros_ponto (
                                nome_funcionario, data_pontos, entrada,
                                saida_intervalo, volta_intervalo, saida_final,
                                data_processado, modelo, chave_unica, origem_hash
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            valores,
                        )
                        resultado["inseridos"] += 1
                        candidatos.append(
                            {
                                "id": cursor.lastrowid,
                                "nome_funcionario": valores[0],
                                "data_pontos": valores[1],
                                "entrada": valores[2],
                                "saida_intervalo": valores[3],
                                "volta_intervalo": valores[4],
                                "saida_final": valores[5],
                                "data_processado": valores[6],
                                "modelo": valores[7],
                                "chave_unica": valores[8],
                                "origem_hash": valores[9],
                            }
                        )
                        continue

                    selecionado = max(candidatos, key=lambda item: int(item["id"]))
                    if len(candidatos) > 1 and chave_logica not in avisos_duplicidade:
                        avisos_duplicidade.add(chave_logica)
                        logs.warning(
                            "SQLite",
                            f"Mais de um registro no dia {selecionado['data_pontos']}; "
                            f"atualizando o mais recente (id={selecionado['id']})",
                            lote,
                        )

                    alvo = {
                        "entrada": valores[2],
                        "saida_intervalo": valores[3],
                        "volta_intervalo": valores[4],
                        "saida_final": valores[5],
                    }
                    diferencas = {
                        coluna: valor
                        for coluna, valor in alvo.items()
                        if selecionado.get(coluna) != valor
                    }
                    if not diferencas:
                        resultado["inalterados"] += 1
                        continue

                    chave_recalculada = _chave_unica(
                        modelo,
                        selecionado["nome_funcionario"],
                        selecionado["data_pontos"],
                        alvo["entrada"],
                        alvo["saida_intervalo"],
                        alvo["volta_intervalo"],
                        alvo["saida_final"],
                    )
                    campos = [f"{coluna} = ?" for coluna in diferencas]
                    parametros = list(diferencas.values()) + [chave_recalculada]
                    campos.append("chave_unica = ?")
                    parametros.extend([selecionado["id"], modelo])
                    cursor = conexao.execute(
                        f"UPDATE registros_ponto SET {', '.join(campos)} "
                        "WHERE id = ? AND modelo = ?",
                        parametros,
                    )
                    if not cursor.rowcount:
                        resultado["ignorados"] += 1
                        logs.warning(
                            "SQLite",
                            f"Registro id={selecionado['id']} nao encontrado "
                            "durante a sincronizacao",
                            lote,
                        )
                        continue

                    selecionado.update(diferencas)
                    selecionado["chave_unica"] = chave_recalculada
                    resultado["atualizados"] += 1
    except sqlite3.Error as exc:
        logs.error("SQLite", f"Falha ao sincronizar planilha: {exc}", lote)
        raise ErroBanco(f"Falha ao sincronizar os registros: {exc}") from exc
    finally:
        conexao.close()

    logs.info(
        "SQLite",
        "Sincronizacao concluida: "
        f"inseridos={resultado['inseridos']}, "
        f"atualizados={resultado['atualizados']}, "
        f"inalterados={resultado['inalterados']}, "
        f"vazios={resultado['vazios']}, "
        f"ignorados={resultado['ignorados']}",
        lote,
    )
    return resultado


def listar_registros(
    funcionario: str | None = None,
    data: str | None = None,
    modelo: str | None = None,
    limite: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Consulta registros persistidos, sem executar OCR ou gerar planilhas."""
    if modelo and modelo not in config.MODELOS_VALIDOS:
        raise ValueError(f"Modelo invalido: {modelo}")

    filtros: list[str] = []
    parametros: list[object] = []
    if funcionario:
        filtros.append("nome_funcionario LIKE ?")
        parametros.append(f"%{funcionario.strip()}%")
    if data:
        data_filtro = _data_iso(data) or _dia_mes(data)
        if not data_filtro:
            raise ValueError(
                "Data invalida. Use YYYY-MM-DD, DD/MM/AAAA ou o dia (1-31)."
            )
        filtros.append("data_pontos = ?")
        parametros.append(data_filtro)
    if modelo:
        filtros.append("modelo = ?")
        parametros.append(modelo)

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    parametros.extend([max(1, min(int(limite), 1000)), max(0, int(offset))])
    sql = (
        f"SELECT {_CAMPOS} FROM registros_ponto {where} "
        "ORDER BY "
        "CASE WHEN data_pontos GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
        "THEN data_pontos "
        "ELSE printf('%02d', CAST(data_pontos AS INTEGER)) END DESC, "
        "nome_funcionario ASC, id DESC "
        "LIMIT ? OFFSET ?"
    )

    conexao = _conectar()
    try:
        with conexao:
            linhas = conexao.execute(sql, parametros).fetchall()
    except sqlite3.Error as exc:
        logs.error("SQLite", f"Falha ao consultar registros: {exc}")
        raise ErroBanco(f"Falha ao consultar os registros: {exc}") from exc
    finally:
        conexao.close()

    logs.debug("SQLite", f"Consulta concluida: {len(linhas)} registro(s)")
    return [dict(linha) for linha in linhas]


def listar_resumo_registros(limite: int = 4) -> list[dict]:
    """Retorna o ultimo lote de cada funcionario, com a faixa de datas.

    Um lote e identificado por funcionario + origem_hash + modelo + data de
    processamento. O lote escolhido e o de data_processado mais recente (mais
    proximo de hoje); em empate, vence o maior id. A faixa usa o primeiro e o
    ultimo id do lote, conforme a ordem de insercao.
    """
    limite = max(1, min(int(limite), 4))
    sql = """
    WITH lotes AS (
        SELECT nome_funcionario,
               COALESCE(origem_hash, '') AS origem_hash,
               modelo,
               data_processado,
               MIN(id) AS primeiro_id,
               MAX(id) AS ultimo_id
        FROM registros_ponto
        GROUP BY nome_funcionario, COALESCE(origem_hash, ''), modelo, data_processado
    ),
    ultimos AS (
        SELECT lotes.*,
               ROW_NUMBER() OVER (
                   PARTITION BY nome_funcionario
                   ORDER BY data_processado DESC, ultimo_id DESC
               ) AS ordem
        FROM lotes
    )
    SELECT u.ultimo_id AS id,
           u.nome_funcionario,
           ini.data_pontos AS data_inicio,
           fim.data_pontos AS data_fim,
           u.data_processado,
           u.modelo
    FROM ultimos u
    JOIN registros_ponto ini ON ini.id = u.primeiro_id
    JOIN registros_ponto fim ON fim.id = u.ultimo_id
    WHERE u.ordem = 1
    ORDER BY u.data_processado DESC, u.ultimo_id DESC
    LIMIT ?
    """

    conexao = _conectar()
    try:
        with conexao:
            linhas = conexao.execute(sql, (limite,)).fetchall()
    except sqlite3.Error as exc:
        logs.error("SQLite", f"Falha ao consultar o resumo de registros: {exc}")
        raise ErroBanco(f"Falha ao consultar o resumo dos registros: {exc}") from exc
    finally:
        conexao.close()

    logs.debug("SQLite", f"Consulta de resumo concluida: {len(linhas)} registro(s)")
    return [dict(linha) for linha in linhas]


def caminho_banco() -> Path:
    return config.ARQUIVO_BANCO
