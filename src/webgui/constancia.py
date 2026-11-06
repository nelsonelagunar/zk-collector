"""
Constancia de asistencia - generacion de PDF (MYK-593)

Genera el PDF de la constancia de asistencia de un colaborador para un periodo,
reutilizando los numeros del reporte de asistencia (`compute_attendance_stats`).
El PDF es apto para imprimir y entregar al trabajador como soporte de su
asistencia en el periodo solicitado (LFT / registro electronico de jornada).
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_HEX_GRAY_BG = "#e5e7eb"
_HEX_GRID = "#cbd5e1"
_HEX_ROW_ALT = "#f8fafc"
_HEX_TITLE = "#111827"
_HEX_SUBTITLE = "#6b7280"
_HEX_LABEL = "#374151"
_HEX_SIG_MUTED = "#6b7280"


def _pct_label(value: Any) -> str:
    if value is None:
        return "—"
    return f"{value}%"


def build_constancia_pdf(
    employee_name: str,
    employee_code: str,
    department: str,
    hire_date: str | None,
    period: dict[str, str],
    stats: dict[str, Any],
    company_name: str,
    issued_at: date,
) -> bytes:
    """Construir el PDF de la constancia de asistencia y devolver sus bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Constancia de asistencia - {employee_code}",
        author=company_name or "",
        subject="Constancia de asistencia",
    )

    company_style = ParagraphStyle(
        "company",
        fontName="Helvetica-Bold",
        fontSize=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor(_HEX_TITLE),
    )
    title_style = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor(_HEX_TITLE),
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "subtitle",
        fontName="Helvetica",
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor(_HEX_SUBTITLE),
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    label_style = ParagraphStyle(
        "label",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=colors.HexColor(_HEX_LABEL),
    )

    story = []
    story.append(Paragraph(company_name or "Attendance Collector", company_style))
    story.append(Paragraph("CONSTANCIA DE ASISTENCIA", title_style))
    story.append(
        Paragraph("Registro electronico de jornada - control de asistencia", subtitle_style)
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(_HEX_TITLE), spaceAfter=10)
    )

    hire_text = f", con fecha de ingreso {hire_date}" if hire_date else ""
    story.append(
        Paragraph(
            f"Por medio de la presente se certifica que <b>{employee_name}</b> "
            f"(codigo {employee_code}){hire_text}, del departamento "
            f"<b>{department}</b>, asistio a su centro de trabajo durante el "
            f"periodo comprendido entre el <b>{period['start_date']}</b> y el "
            f"<b>{period['end_date']}</b>, con los siguientes resultados:",
            body_style,
        )
    )

    rows = [
        ["Concepto", "Valor"],
        ["Dias laborables esperados", str(stats.get("days_expected") or 0)],
        ["Dias presentes", str(stats.get("days_present") or 0)],
        ["Dias ausentes", str(stats.get("days_absent") or 0)],
        ["Dias por incapacidad", str(stats.get("days_incapacity") or 0)],
        ["Dias de vacaciones", str(stats.get("days_vacation") or 0)],
        ["Retardos", str(stats.get("late_arrivals") or 0)],
        ["Puntualidad", _pct_label(stats.get("punctuality_pct"))],
        ["Ausentismo", _pct_label(stats.get("absenteeism_pct"))],
    ]
    table = Table(rows, colWidths=[70 * mm, 80 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_HEX_GRAY_BG)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_HEX_TITLE)),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(_HEX_GRID)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(_HEX_ROW_ALT)]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))

    issued = issued_at.strftime("%d de %B de %Y")
    story.append(
        Paragraph(
            f"Se extiende la presente constancia a solicitud del interesado para "
            f"los fines que le convenga, a <b>{issued}</b>.",
            body_style,
        )
    )
    story.append(Spacer(1, 14))
    story.append(
        HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#9ca3af"), spaceAfter=6)
    )
    sig = ParagraphStyle(
        "sig", fontName="Helvetica", fontSize=10, alignment=TA_CENTER, spaceAfter=2
    )
    sig_muted = ParagraphStyle(
        "sig_muted",
        fontName="Helvetica",
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor(_HEX_SIG_MUTED),
    )
    story.append(Paragraph("_______________________________", sig))
    story.append(Paragraph("Nombre y firma - Recursos Humanos", sig_muted))
    story.append(Spacer(1, 10))
    story.append(Paragraph("_______________________________", sig))
    story.append(Paragraph("Conforme - Colaborador", sig_muted))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
