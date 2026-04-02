"""
report_export_service.py - PDF export helpers for AI reports.
Builds a downloadable PDF from the existing structured report payload.
"""

from io import BytesIO
from typing import Any

from app.utils.helpers import truncate


def _severity_colors(severity: str):
    from reportlab.lib import colors

    palette = {
        "critical": (colors.HexColor("#FDE7E7"), colors.HexColor("#A61B1B")),
        "high": (colors.HexColor("#FFF1DE"), colors.HexColor("#9A5600")),
        "medium": (colors.HexColor("#E7F0FE"), colors.HexColor("#0D4EA6")),
        "low": (colors.HexColor("#E6F7F0"), colors.HexColor("#0B6B48")),
    }
    return palette.get(severity.lower(), (colors.HexColor("#ECECEC"), colors.HexColor("#444444")))


def _build_styles():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=8,
        textColor=colors.HexColor("#102A43"),
    ))
    styles.add(ParagraphStyle(
        name="SectionMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#486581"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="FindingTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#102A43"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="FindingBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=6,
    ))
    return styles


def _finding_table(finding: dict[str, Any], styles):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Table, TableStyle

    severity = str(finding.get("severity", "unknown")).lower()
    badge_bg, badge_fg = _severity_colors(severity)
    affected_nodes = ", ".join(finding.get("affected_nodes") or []) or "None listed"
    kill_chain = finding.get("kill_chain") or "Not provided"

    rows = [
        [
            Paragraph(
                f'<font color="{badge_fg}"><b>{severity.upper()}</b></font>',
                ParagraphStyle(
                    "SeverityBadge",
                    parent=styles["FindingBody"],
                    backColor=badge_bg,
                    borderPadding=(3, 6, 3),
                    spaceAfter=0,
                ),
            ),
            Paragraph(
                f"<b>Category:</b> {finding.get('category', 'unknown')}<br/>"
                f"<b>Effort:</b> {finding.get('effort', 'unknown')}",
                styles["FindingBody"],
            ),
        ],
        [Paragraph(f"<b>Description:</b> {finding.get('description', '')}", styles["FindingBody"]), ""],
        [Paragraph(f"<b>Kill Chain:</b> {kill_chain}", styles["FindingBody"]), ""],
        [Paragraph(f"<b>Affected Nodes:</b> {affected_nodes}", styles["FindingBody"]), ""],
        [Paragraph(f"<b>Recommendation:</b> {finding.get('recommendation', '')}", styles["FindingBody"]), ""],
    ]

    table = Table(rows, colWidths=[1.45 * inch, 4.95 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("SPAN", (0, 1), (1, 1)),
        ("SPAN", (0, 2), (1, 2)),
        ("SPAN", (0, 3), (1, 3)),
        ("SPAN", (0, 4), (1, 4)),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D9E2EC")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E2EC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def build_report_pdf(report: dict[str, Any]) -> bytes:
    """
    Render a structured report dict into PDF bytes.
    """
    buffer = BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = _build_styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=str(report.get("report_title", "Attack Path Analysis Report")),
        author="Attack Path Analyzer",
    )

    findings = report.get("findings") or []
    story = [
        Paragraph(str(report.get("report_title", "Attack Path Analysis Report")), styles["ReportTitle"]),
        Paragraph(f"<b>Cluster:</b> {report.get('cluster', 'unknown')}", styles["SectionMeta"]),
        Paragraph(f"<b>Generated:</b> {report.get('generated_at', 'unknown')}", styles["SectionMeta"]),
        Paragraph(f"<b>Tool:</b> {report.get('tool', 'Attack Path Analyzer')}", styles["SectionMeta"]),
        Paragraph(f"<b>Total Findings:</b> {report.get('total_findings', len(findings))}", styles["SectionMeta"]),
        Spacer(1, 0.18 * inch),
    ]

    if not findings:
        story.append(Paragraph("No findings were returned for this report.", styles["FindingBody"]))
    else:
        for index, finding in enumerate(findings, start=1):
            title = truncate(str(finding.get("title", f"Finding {index}")), max_len=110)
            finding_id = finding.get("id", f"finding_{index:03d}")
            story.append(
                Paragraph(f"{index}. {title} <font size=9 color='#486581'>({finding_id})</font>", styles["FindingTitle"])
            )
            story.append(_finding_table(finding, styles))
            story.append(Spacer(1, 0.16 * inch))

    doc.build(story)
    return buffer.getvalue()
