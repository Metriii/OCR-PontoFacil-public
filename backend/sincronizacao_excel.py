"""Sincronizacao automatica de planilhas Excel editadas com o SQLite.

O watcher observa ``backend/_out``, a pasta Downloads e diretorios extras. Um
unico worker aguarda a gravacao estabilizar, ignora arquivos temporarios e
arquivos recem-gerados pelo proprio sistema, e delega a leitura/validacao para
``backend.importar_excel``.
"""

from __future__ import annotations

import queue
import re
import threading
import time
from pathlib import Path
from zipfile import BadZipFile

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - dependencia opcional em ambientes minimos
    FileSystemEvent = object  # type: ignore[assignment,misc]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    Observer = None  # type: ignore[assignment]

from openpyxl.utils.exceptions import InvalidFileException

from . import banco, config, excel, importar_excel, logs

_COMPONENTE = "SincronizacaoExcel"
_TEMPORARIO = re.compile(r"^~\$|\.tmp$|\.crdownload$", re.IGNORECASE)


def _relevante(caminho: Path) -> bool:
    if caminho.suffix.casefold() != ".xlsx":
        return False
    return not _TEMPORARIO.search(caminho.name)


def _aguardar_estavel(caminho: Path, parar: threading.Event) -> None:
    anterior: tuple[int, int] | None = None
    for _ in range(10):
        if parar.is_set():
            return
        try:
            info = caminho.stat()
        except OSError:
            parar.wait(0.2)
            continue
        atual = (info.st_size, info.st_mtime_ns)
        if atual == anterior:
            return
        anterior = atual
        parar.wait(0.25)


class _Handler(FileSystemEventHandler):
    def __init__(self, sincronizador: "SincronizadorExcel") -> None:
        self._sincronizador = sincronizador

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._sincronizador.enfileirar(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._sincronizador.enfileirar(Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            destino = getattr(event, "dest_path", "")
            if destino:
                self._sincronizador.enfileirar(Path(destino))


class SincronizadorExcel:
    def __init__(self) -> None:
        self._fila: queue.Queue[Path | None] = queue.Queue()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._observer = None
        self._tentativas: dict[Path, int] = {}
        self._lock = threading.Lock()

    @property
    def ativo(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def iniciar(self) -> bool:
        with self._lock:
            if self.ativo:
                return True
            if not config.SYNC_EXCEL_ATIVO:
                logs.info(_COMPONENTE, "Sincronizacao desativada por configuracao")
                return False
            if Observer is None:
                logs.error(
                    _COMPONENTE,
                    "watchdog nao instalado; sincronizacao automatica indisponivel",
                )
                return False

            pastas = [pasta for pasta in config.pastas_sincronizacao() if pasta.is_dir()]
            if not pastas:
                logs.warning(
                    _COMPONENTE,
                    "Nenhuma pasta existente para monitorar",
                )
                return False

            self._parar.clear()
            self._fila = queue.Queue()
            self._tentativas.clear()
            self._thread = threading.Thread(
                target=self._worker,
                name="sincronizacao-excel",
                daemon=True,
            )
            self._thread.start()

            observer = Observer()
            handler = _Handler(self)
            try:
                for pasta in pastas:
                    observer.schedule(handler, str(pasta), recursive=False)
                observer.start()
            except Exception as exc:  # noqa: BLE001
                self._parar.set()
                self._fila.put(None)
                self._thread.join(timeout=2)
                logs.error(_COMPONENTE, f"Falha ao iniciar monitoramento: {exc}")
                self._thread = None
                return False

            self._observer = observer
            logs.info(
                _COMPONENTE,
                "Monitorando: " + ", ".join(str(pasta) for pasta in pastas),
            )
            return True

    def parar(self, timeout: float = 5.0) -> None:
        with self._lock:
            thread = self._thread
            observer = self._observer
            self._thread = None
            self._observer = None
        self._parar.set()
        self._fila.put(None)
        if thread:
            thread.join(timeout)
        if observer:
            observer.stop()
            observer.join(timeout)
        if thread or observer:
            logs.info(_COMPONENTE, "Monitoramento encerrado")

    def enfileirar(self, caminho: Path) -> None:
        if self._parar.is_set() or not _relevante(caminho):
            return
        if excel.foi_gerado_recentemente(caminho):
            return
        self._fila.put(caminho)

    def _worker(self) -> None:
        pendentes: dict[Path, float] = {}
        while not self._parar.is_set():
            try:
                item = self._fila.get(timeout=0.2)
            except queue.Empty:
                item = ...
            else:
                if item is None:
                    break
                pendentes[item] = time.monotonic()

            agora = time.monotonic()
            for caminho, momento in list(pendentes.items()):
                if agora - momento < config.SYNC_EXCEL_DEBOUNCE:
                    continue
                pendentes.pop(caminho, None)
                if self._parar.is_set():
                    break
                self._processar(caminho)

    def _reagendar(self, caminho: Path, motivo: str) -> None:
        tentativas = self._tentativas.get(caminho, 0) + 1
        self._tentativas[caminho] = tentativas
        if tentativas <= config.SYNC_EXCEL_TENTATIVAS:
            logs.warning(
                _COMPONENTE,
                f"{caminho.name}: {motivo}; nova tentativa "
                f"{tentativas}/{config.SYNC_EXCEL_TENTATIVAS}",
            )
            if not self._parar.wait(config.SYNC_EXCEL_ESPERA * tentativas):
                self._fila.put(caminho)
            return

        logs.error(
            _COMPONENTE,
            f"{caminho.name}: falha apos {tentativas} tentativa(s): {motivo}",
        )
        self._tentativas.pop(caminho, None)

    def _processar(self, caminho: Path) -> None:
        if self._parar.is_set() or not caminho.is_file():
            return
        if excel.foi_gerado_recentemente(caminho):
            return

        inicio = time.monotonic()
        try:
            _aguardar_estavel(caminho, self._parar)
            resultado = importar_excel.importar(caminho, exigir_metadados=True)
        except importar_excel.PlanilhaIgnorada:
            logs.debug(
                _COMPONENTE,
                f"{caminho.name}: ignorado (sem metadados do PontoFacil)",
            )
            self._tentativas.pop(caminho, None)
            return
        except (PermissionError, OSError, BadZipFile) as exc:
            self._reagendar(caminho, f"arquivo indisponivel ({exc})")
            return
        except (InvalidFileException, ValueError, banco.ErroBanco) as exc:
            logs.warning(
                _COMPONENTE,
                f"{caminho.name}: sincronizacao rejeitada ({exc})",
            )
            self._tentativas.pop(caminho, None)
            return
        except Exception as exc:  # noqa: BLE001
            logs.error(
                _COMPONENTE,
                f"{caminho.name}: falha inesperada na sincronizacao ({exc})",
            )
            self._tentativas.pop(caminho, None)
            return

        self._tentativas.pop(caminho, None)
        duracao = time.monotonic() - inicio
        logs.info(
            _COMPONENTE,
            f"{caminho.name}: lidos={resultado['lidos']}, "
            f"inseridos={resultado['inseridos']}, "
            f"atualizados={resultado['atualizados']}, "
            f"inalterados={resultado['inalterados']}, "
            f"vazios={resultado['vazios']}, "
            f"invalidos={resultado['invalidos']} em {duracao:.2f}s",
        )


_SINCRONIZADOR: SincronizadorExcel | None = None


def iniciar() -> bool:
    global _SINCRONIZADOR
    if _SINCRONIZADOR is None:
        _SINCRONIZADOR = SincronizadorExcel()
    return _SINCRONIZADOR.iniciar()


def parar() -> None:
    global _SINCRONIZADOR
    if _SINCRONIZADOR is not None:
        _SINCRONIZADOR.parar()
        _SINCRONIZADOR = None
