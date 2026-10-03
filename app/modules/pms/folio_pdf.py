"""Minimal PDF builder for guest folio statements (stdlib only — no reportlab)."""

from __future__ import annotations

from datetime import date, datetime


def _pdf_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _safe(text: str) -> str:
    """Helvetica is WinAnsi; keep printable ASCII-ish chars."""
    cleaned = (
        text.replace("₹", "Rs.")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in cleaned)


def build_simple_pdf(lines: list[str], *, title: str = "Guest Folio") -> bytes:
    """Build a single-page text PDF from plain lines."""
    content_lines = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    # Title
    content_lines.append(f"({_pdf_escape(_safe(title))}) Tj")
    content_lines.append("T*")
    content_lines.append("T*")
    content_lines.append("/F1 10 Tf")
    for line in lines:
        safe = _pdf_escape(_safe(line))
        # Truncate very long lines for page width
        if len(safe) > 95:
            safe = safe[:92] + "..."
        content_lines.append(f"({safe}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


def format_money(amount: float) -> str:
    return f"Rs.{abs(amount):,.2f}"


def folio_statement_lines(
    *,
    outlet_name: str,
    folio_number: str,
    confirmation_number: str,
    guest_name: str,
    guest_email: str | None,
    guest_mobile: str,
    room_number: str | None,
    room_type_name: str | None,
    check_in: date,
    check_out: date,
    folio_status: str,
    balance: float,
    entries: list[tuple[str, str, float, datetime | None]],
) -> list[str]:
    lines = [
        f"Property: {outlet_name}",
        f"Folio: {folio_number}   Status: {folio_status}",
        f"Confirmation: {confirmation_number}",
        f"Guest: {guest_name}",
        f"Mobile: {guest_mobile}" + (f"   Email: {guest_email}" if guest_email else ""),
        f"Stay: {check_in.isoformat()} to {check_out.isoformat()}",
    ]
    if room_number or room_type_name:
        lines.append(
            f"Room: {room_number or '-'} ({room_type_name or 'room type n/a'})"
        )
    lines.append("-" * 72)
    lines.append(f"{'Type':<14} {'Description':<36} {'Amount':>12}")
    lines.append("-" * 72)
    for entry_type, description, amount, _created in entries:
        sign = "-" if amount < 0 else " "
        desc = description[:36]
        lines.append(f"{entry_type:<14} {desc:<36} {sign}{format_money(amount):>11}")
    lines.append("-" * 72)
    lines.append(f"{'Balance due':<51} {format_money(balance):>12}")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("This is a system-generated folio statement.")
    return lines
