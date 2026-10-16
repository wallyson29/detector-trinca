import cv2
import numpy as np
import time
from PIL import Image
import re
import streamlit as st
from google import genai

from config import (
    MODELO_GEMINI,
    MAX_TENTATIVAS_IA,
    ESPERA_ENTRE_TENTATIVAS,
    CHECKLIST_FOTOS,
)
from db import fazer_upload_imagem


def analisar_peca(client, img_original_bgr, nome_peca):
    """Analisa 1 peça com 2 imagens (original + CLAHE). Com retry automático."""
    max_tentativas = MAX_TENTATIVAS_IA
    espera = ESPERA_ENTRE_TENTATIVAS

    for tentativa in range(1, max_tentativas + 1):
        try:
            img_cinza = cv2.cvtColor(img_original_bgr, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            img_clahe = clahe.apply(img_cinza)

            img_a = Image.fromarray(cv2.cvtColor(img_original_bgr, cv2.COLOR_BGR2RGB))
            img_b = Image.fromarray(img_clahe)

            prompt = f"""Você é um inspetor técnico especializado em pino-rei, quinta roda e conjunto de engate de caminhão.

Analise APENAS esta peça: {nome_peca}

IMAGEM A: foto original
IMAGEM B: foto com realce de contraste (CLAHE)

Responda EXATAMENTE neste formato:

STATUS: OK | TRINCA_LEVE | TRINCA_MODERADA | TRINCA_SEVERA | NAO_SEI
TEM TRINCA: SIM | NÃO | NÃO SEI
GRAVIDADE: LEVE | MODERADA | SEVERA | —
CONFIANÇA: ALTA | MÉDIA | BAIXA
OBSERVAÇÃO: (1 frase curta descrevendo o que viu)
COORDENADAS: [y_min, x_min, y_max, x_max]

REGRAS PARA COORDENADAS:
- Valores entre 0 e 1000 (0,0 = canto superior esquerdo)
- A caixa deve envolver APENAS a trinca, não a peça toda
- Seja preciso: uma trinca fina gera uma caixa fina
- Se não houver trinca: [0, 0, 0, 0]

Seja objetivo e técnico."""

            resposta = client.models.generate_content(
                model=MODELO_GEMINI,
                contents=[prompt, img_a, img_b]
            )
            texto = resposta.text

            status = "NAO_SEI"
            match = re.search(r'STATUS:\s*\**\s*(OK|TRINCA_LEVE|TRINCA_MODERADA|TRINCA_SEVERA|NAO_SEI)', texto, re.IGNORECASE)
            if match:
                status = match.group(1).upper()

            tem_trinca = "NÃO SEI"
            match = re.search(r'TEM TRINCA:\s*\**\s*(SIM|NÃO|NAO|NÃO SEI)', texto, re.IGNORECASE)
            if match:
                tem_trinca = match.group(1).upper().replace("NAO", "NÃO")

            gravidade = "—"
            match = re.search(r'GRAVIDADE:\s*\**\s*(LEVE|MODERADA|SEVERA|—)', texto, re.IGNORECASE)
            if match:
                gravidade = match.group(1).upper()

            confianca = "—"
            match = re.search(r'CONFIAN[ÇC]A:\s*\**\s*(ALTA|MÉDIA|MEDIA|BAIXA|—)', texto, re.IGNORECASE)
            if match:
                confianca = match.group(1).upper().replace("MEDIA", "MÉDIA")

            obs = ""
            match = re.search(r'OBSERVA[ÇC][ÃA]O:\s*\**\s*(.+)', texto, re.IGNORECASE)
            if match:
                obs = match.group(1).strip()

            coords = None
            match = re.search(r'COORDENADAS:\s*\[([\d,\s]+)\]', texto)
            if match:
                valores = [int(x.strip()) for x in match.group(1).split(',')]
                if len(valores) == 4 and sum(valores) > 0:
                    coords = valores

            img_marcada = img_original_bgr.copy()
            if coords and status.startswith("TRINCA"):
                y_min, x_min, y_max, x_max = coords
                h, w = img_original_bgr.shape[:2]
                x1 = int((x_min / 1000) * w)
                y1 = int((y_min / 1000) * h)
                x2 = int((x_max / 1000) * w)
                y2 = int((y_max / 1000) * h)

                largura_max = int(w * 0.5)
                altura_max = int(h * 0.5)
                if (x2 - x1) > largura_max:
                    cx = (x1 + x2) // 2
                    x1 = cx - largura_max // 2
                    x2 = cx + largura_max // 2
                if (y2 - y1) > altura_max:
                    cy = (y1 + y2) // 2
                    y1 = cy - altura_max // 2
                    y2 = cy + altura_max // 2

                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(0, min(x2, w - 1))
                y2 = max(0, min(y2, h - 1))

                cv2.rectangle(img_marcada, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(img_marcada, "TRINCA", (x1, max(y1 - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            return {
                "status": status,
                "tem_trinca": tem_trinca,
                "gravidade": gravidade,
                "confianca": confianca,
                "observacao": obs,
                "img_marcada": img_marcada,
            }

        except Exception as e:
            erro_str = str(e)
            if "503" in erro_str and tentativa < max_tentativas:
                time.sleep(espera)
                continue
            elif "429" in erro_str and tentativa < max_tentativas:
                time.sleep(espera * 2)
                continue
            return {
                "status": "ERRO",
                "tem_trinca": "NÃO SEI",
                "gravidade": "—",
                "confianca": "—",
                "observacao": f"Erro após {tentativa} tentativa(s): {erro_str[:100]}",
                "img_marcada": img_original_bgr.copy(),
            }


def analisar_pecas_selecionadas(client, pecas_para_analisar, fotos_brutas, perfil, resultados_existentes=None):
    """Analisa um subconjunto de peças (só as que precisam)."""
    resultados = resultados_existentes.copy() if resultados_existentes else {}
    fotos_urls = {}
    erros = []

    total_pecas = len(pecas_para_analisar)

    barra_progresso = st.progress(0)
    status_texto = st.empty()

    for i, item in enumerate(pecas_para_analisar):
        status_texto.markdown(f"**Analisando peça {i+1}/{total_pecas}:** {item['label']}...")

        img_original = fotos_brutas.get(item["id"])
        if img_original is None:
            erros.append(item)
            barra_progresso.progress((i + 1) / total_pecas)
            continue

        resultado = analisar_peca(client, img_original, item["label"])

        if resultado["status"] == "ERRO":
            erros.append(item)
            status_texto.markdown(f"**Analisando peça {i+1}/{total_pecas}:** {item['label']}... 🟡 **ERRO**")
        else:
            resultados[item["id"]] = resultado
            url_marcada, _ = fazer_upload_imagem(resultado["img_marcada"], perfil["id"], item["id"])
            fotos_urls[item["id"]] = url_marcada

            if resultado["status"].startswith("TRINCA"):
                status_texto.markdown(f"**Analisando peça {i+1}/{total_pecas}:** {item['label']}... 🔴 **TRINCA**")
            elif resultado["status"] == "OK":
                status_texto.markdown(f"**Analisando peça {i+1}/{total_pecas}:** {item['label']}... ✅ OK")
            else:
                status_texto.markdown(f"**Analisando peça {i+1}/{total_pecas}:** {item['label']}... 🟡 {resultado['status']}")

        barra_progresso.progress((i + 1) / total_pecas)

    return resultados, fotos_urls, erros


def gerar_laudo_consolidado(resultados, placa):
    linhas = [f"LAUDO DE INSPEÇÃO — PLACA {placa}", ""]

    tem_trinca_geral = False
    pecas_com_trinca = []
    gravidades = []
    confiancas = []

    for i, item in enumerate(CHECKLIST_FOTOS):
        if not item["analisar"]:
            continue
        res = resultados.get(item["id"])
        if not res:
            continue

        status = res["status"]
        if status.startswith("TRINCA"):
            emoji = "🔴"
            tem_trinca_geral = True
            pecas_com_trinca.append(f"{i+1}. {item['label']}")
            if res["gravidade"] != "—":
                gravidades.append(res["gravidade"])
        elif status == "OK":
            emoji = "✅"
        else:
            emoji = "🟡"

        linhas.append(f"PEÇA {i+1} ({item['label']}): {emoji} {status}")
        if res.get("observacao"):
            linhas.append(f"   Obs: {res['observacao']}")

        if res["confianca"] != "—":
            confiancas.append(res["confianca"])

    linhas.append("")
    linhas.append("RESUMO:")
    linhas.append(f"1. TEM TRINCA? {'SIM' if tem_trinca_geral else 'NÃO'}")
    if pecas_com_trinca:
        linhas.append(f"2. Peças com trinca: {', '.join(pecas_com_trinca)}")
    else:
        linhas.append("2. Peças com trinca: nenhuma")

    if gravidades:
        prioridade = {"SEVERA": 3, "MODERADA": 2, "LEVE": 1}
        grav_max = max(gravidades, key=lambda g: prioridade.get(g, 0))
        linhas.append(f"3. Gravidade geral: {grav_max}")
        if grav_max == "SEVERA":
            linhas.append("4. Recomendação: SUBSTITUIR")
        else:
            linhas.append("4. Recomendação: INSPECIONAR")
    else:
        linhas.append("3. Gravidade geral: —")
        linhas.append("4. Recomendação: LIBERAR")

    if confiancas:
        if "BAIXA" in confiancas:
            conf_geral = "BAIXA"
        elif "MÉDIA" in confiancas:
            conf_geral = "MÉDIA"
        else:
            conf_geral = "ALTA"
    else:
        conf_geral = "—"
    linhas.append(f"5. Confiança: {conf_geral}")

    return "\n".join(linhas)
