import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.consulta_formatter import montar_view

PRIMARY = colors.HexColor("#4f6ef7")
TEXT_MUTED = colors.HexColor("#6b7280")
BORDER = colors.HexColor("#eaecf1")
SUCCESS = colors.HexColor("#17924f")
ERROR = colors.HexColor("#d64545")


def _tabela_campos(campos: list[tuple[str, str]]) -> Table:
    linhas = [[label, valor] for label, valor in campos]
    tabela = Table(linhas, colWidths=[45 * mm, 110 * mm])
    tabela.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), TEXT_MUTED),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
            ]
        )
    )
    return tabela


def gerar_pdf_consulta(consulta: dict, resultado: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=24 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#1a1d29"), spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleCustom", parent=styles["Normal"], fontSize=10, textColor=TEXT_MUTED, spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "SectionCustom", parent=styles["Heading2"], fontSize=12, textColor=PRIMARY, spaceBefore=16, spaceAfter=8,
    )
    item_style = ParagraphStyle("Item", parent=styles["Normal"], fontSize=9.5, spaceAfter=4)

    elements = [
        Paragraph("Relatório de Consulta Veicular", title_style),
        Paragraph(
            f"Tipo: {consulta['tipo']} · Placa: {consulta['placa']} · Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            subtitle_style,
        ),
    ]

    view = montar_view(resultado)

    if view.campos_principais:
        elements.append(Paragraph("Dados principais", section_style))
        elements.append(_tabela_campos(view.campos_principais))

    for secao in view.secoes:
        elements.append(Paragraph(secao.titulo, section_style))
        if secao.campos:
            elements.append(_tabela_campos(secao.campos))
        for item in secao.itens:
            cor = ERROR if "NADA CONSTA" not in item.upper() else SUCCESS
            elements.append(
                Paragraph(f"• {item}", ParagraphStyle("ItemCor", parent=item_style, textColor=cor))
            )

    if not view.campos_principais and not view.secoes:
        elements.append(Paragraph("Esta consulta não possui dados detalhados.", item_style))

    elements.append(Spacer(1, 20 * mm))
    elements.append(
        Paragraph(
            f"Consulta #{consulta['id']} · Custo: {consulta['custo_creditos']} créditos · "
            f"Realizada em {consulta['created_at']}",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=TEXT_MUTED),
        )
    )

    doc.build(elements)
    return buffer.getvalue()
