from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.evidence.checksum import sha256_file
from app.evidence.paths import ensure_under
from app.reporting.html import render_final_html


TAG_RE = re.compile(r"<[^>]+>")


def render_final_pdf(snapshot: dict[str, Any], output_path: str | Path) -> tuple[str, str]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = render_final_html(snapshot)
    text = TAG_RE.sub(" ", html)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    _write_simple_pdf(path, lines)
    return str(path), sha256_file(path)


def render_pdf_under(root: Path, snapshot: dict[str, Any], relative_path: str) -> tuple[str, str]:
    path = ensure_under(root, root / relative_path)
    return render_final_pdf(snapshot, path)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_simple_pdf(path: Path, lines: list[str]) -> None:
    content_lines = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    for line in lines:
        for chunk in _wrap(line, 95):
            content_lines.append(f"({_pdf_escape(chunk)}) Tj")
            content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(bytes(out))


def _wrap(text: str, width: int):
    while len(text) > width:
        yield text[:width]
        text = text[width:]
    yield text
