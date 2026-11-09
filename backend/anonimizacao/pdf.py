"""Rasterizacao local de PDF, sem qualquer chamada externa.

O pipeline aceita PDF desde que a imagem resultante passe pela anonimizacao.
Nesta fase apenas PDF de uma pagina e suportado: o OCR externo recebe uma unica
imagem e PDFs multipagina poderiam esconder linhas/folhas nao anonimizadas.
Qualquer duvida bloqueia o arquivo (fail closed).
"""

from __future__ import annotations

import io

from .schemas import CodigoFalha


class ErroPdf(RuntimeError):
    def __init__(self, codigo: CodigoFalha, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


def eh_pdf(dados: bytes) -> bool:
    return dados.lstrip()[:5] == b"%PDF-"


def rasterizar_pdf(dados: bytes, dpi: int = 200) -> bytes:
    """Converte um PDF de uma pagina em PNG local.

    Levanta ``ErroPdf`` com codigo de falha quando o PDF e invalido, protegido,
    multipagina ou nao pode ser renderizado.
    """
    if not eh_pdf(dados):
        raise ErroPdf(CodigoFalha.INVALID_INPUT, "O conteudo nao e um PDF.")

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise ErroPdf(
            CodigoFalha.PDF_RASTERIZATION_ERROR,
            "pypdfium2 nao esta instalado no ambiente de anonimizacao.",
        ) from exc

    documento = None
    try:
        documento = pdfium.PdfDocument(dados)
        total = len(documento)
        if total != 1:
            raise ErroPdf(
                CodigoFalha.UNSUPPORTED_MULTIPAGE_PDF,
                f"PDF com {total} paginas; apenas uma pagina e suportada.",
            )

        pagina = documento[0]
        escala = max(0.5, float(dpi) / 72.0)
        bitmap = pagina.render(scale=escala)
        imagem = bitmap.to_pil()
        if imagem.width < 32 or imagem.height < 32:
            raise ErroPdf(
                CodigoFalha.PDF_RASTERIZATION_ERROR,
                "A pagina do PDF foi renderizada vazia.",
            )
        if imagem.mode not in ("RGB", "L"):
            imagem = imagem.convert("RGB")
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")
        return buffer.getvalue()
    except ErroPdf:
        raise
    except Exception as exc:  # noqa: BLE001 - qualquer falha do renderizador
        raise ErroPdf(
            CodigoFalha.PDF_RASTERIZATION_ERROR,
            f"Falha ao rasterizar o PDF: {type(exc).__name__}.",
        ) from exc
    finally:
        if documento is not None:
            try:
                documento.close()
            except Exception:  # noqa: BLE001
                pass
