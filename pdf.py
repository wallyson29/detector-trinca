import io
from datetime import datetime
import requests as http_requests

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.enums import TA_CENTER

from config import CHECKLIST_FOTOS
from db import nome_usuario, nome_filial
from utils import formatar_placa, normalizar_placa


def gerar_pdf_analise(analise):
    """Gera PDF da análise e retorna bytes."""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()
        estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#1e3a5f'), alignment=TA_CENTER, spaceAfter=20)
        estilo_sub = ParagraphStyle('Sub', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#2c5282'), spaceAfter=10, spaceBefore=15)
        estilo_corpo = ParagraphStyle('Corpo', parent=styles['BodyText'], fontSize=11, leading=16)
        estilo_legenda = ParagraphStyle('Legenda', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6b7280'), alignment=TA_CENTER)

        elementos = []
        elementos.append(Paragraph("🔍 Detector de Trinca", estilo_titulo))
        elementos.append(Paragraph(
            "Relatório de Inspeção de Pino-Rei / Quinta Roda",
            ParagraphStyle('sub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, textColor=colors.HexColor('#6b7280'))
        ))
        elementos.append(Spacer(1, 20))

        placa = formatar_placa(analise.get("placa", "—"))
        data = analise.get("created_at", "")[:19].replace("T", " ")
        quem = nome_usuario(analise.get("user_id"))
        filial = nome_filial(analise.get("filial_id"))
        forcado = "⚠️ SIM (fora do prazo)" if analise.get("forcado") else "Não"

        elementos.append(Paragraph("📋 Dados da Inspeção", estilo_sub))
        dados_tabela = [
            ["Placa do veículo", placa],
            ["Data/Hora", data],
            ["Técnico responsável", quem],
            ["Filial", filial],
            ["Análise forçada", forcado],
        ]
        t = Table(dados_tabela, colWidths=[5*cm, 10*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3a5f')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        elementos.append(t)
        elementos.append(Spacer(1, 15))

        elementos.append(Paragraph("🔍 Status por Peça", estilo_sub))

        tabela_pecas = [["Peça", "Status"]]
        for item in CHECKLIST_FOTOS:
            if item["status_col"]:
                status = analise.get(item["status_col"], "—")
                emoji = "🔴" if status and status.startswith("TRINCA") else ("✅" if status == "OK" else "🟡")
                tabela_pecas.append([item["label"], f"{emoji} {status}"])

        tp = Table(tabela_pecas, colWidths=[10*cm, 5*cm])
        tp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elementos.append(tp)
        elementos.append(Spacer(1, 15))

        elementos.append(Paragraph("📸 Fotos da Inspeção", estilo_sub))

        fotos_validas = [(item["label"], analise.get(item["id"])) for item in CHECKLIST_FOTOS if analise.get(item["id"])]

        for i in range(0, len(fotos_validas), 2):
            par = fotos_validas[i:i+2]
            linha_imgs = []
            linha_legendas = []
            for label, url in par:
                try:
                    r = http_requests.get(url, timeout=10)
                    if r.status_code == 200:
                        img_buffer = io.BytesIO(r.content)
                        img = RLImage(img_buffer, width=7*cm, height=5*cm, kind='proportional')
                        linha_imgs.append(img)
                        linha_legendas.append(Paragraph(label, estilo_legenda))
                    else:
                        linha_imgs.append(Paragraph("(falha)", estilo_corpo))
                        linha_legendas.append(Paragraph(label, estilo_legenda))
                except Exception:
                    linha_imgs.append(Paragraph("(falha)", estilo_corpo))
                    linha_legendas.append(Paragraph(label, estilo_legenda))

            if linha_imgs:
                tabela_fotos = Table([linha_imgs, linha_legendas], colWidths=[8*cm, 8*cm])
                tabela_fotos.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                ]))
                elementos.append(tabela_fotos)
                elementos.append(Spacer(1, 8))

        if analise.get("foto_observacao"):
            try:
                r = http_requests.get(analise["foto_observacao"], timeout=10)
                if r.status_code == 200:
                    img_buffer = io.BytesIO(r.content)
                    elementos.append(Paragraph("📸 Foto de Observação", estilo_sub))
                    img = RLImage(img_buffer, width=14*cm, height=10*cm, kind='proportional')
                    elementos.append(img)
                    elementos.append(Spacer(1, 10))
            except Exception:
                pass

        if analise.get("texto_observacao"):
            elementos.append(Paragraph("📝 Observação do Técnico", estilo_sub))
            elementos.append(Paragraph(
                analise["texto_observacao"].replace("<", "&lt;").replace(">", "&gt;"),
                estilo_corpo
            ))

        elementos.append(Paragraph("📝 Laudo Completo", estilo_sub))
        laudo_txt = analise.get("laudo", "—")
        for paragrafo in laudo_txt.split("\n"):
            if paragrafo.strip():
                elementos.append(Paragraph(
                    paragrafo.replace("<", "&lt;").replace(">", "&gt;"),
                    estilo_corpo
                ))

        elementos.append(Spacer(1, 30))
        elementos.append(Paragraph(
            f"Documento gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle('rodape', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#9ca3af'), alignment=TA_CENTER)
        ))

        doc.build(elementos)
        buffer.seek(0)
        return buffer.getvalue(), None
    except Exception as e:
        return None, str(e)
