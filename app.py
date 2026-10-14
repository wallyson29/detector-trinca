import streamlit as st
import cv2
import numpy as np
from PIL import Image
import re
from google import genai

# ========== CONFIGURAÇÃO DA PÁGINA ==========
st.set_page_config(
    page_title="Detector de Trinca - Pino Rei",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Detector de Trinca em Pino-Rei")
st.markdown("Tire uma foto ou suba uma imagem para análise automática.")

# ========== CHAVE DA API ==========
try:
    CHAVE_GEMINI = st.secrets["GEMINI_API_KEY"]
except:
    CHAVE_GEMINI = "SUA_CHAVE_AQUI"

# ========== UPLOAD ==========
arquivo = st.file_uploader(
    "Escolha a foto do pino-rei ou quinta roda",
    type=["jpg", "jpeg", "png"]
)

if arquivo is not None:
    # Ler imagem
    bytes_img = arquivo.read()
    img_array = np.frombuffer(bytes_img, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    img_cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ========== PRÉ-PROCESSAMENTO ==========
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    img_clahe = clahe.apply(img_cinza)

    bordas = cv2.Canny(img_clahe, 50, 150)

    # ========== MOSTRAR AS 3 VERSÕES ==========
    col1, col2, col3 = st.columns(3)

    with col1:
        st.image(img_cinza, caption="Original (cinza)", use_container_width=True)
    with col2:
        st.image(img_clahe, caption="CLAHE (realce)", use_container_width=True)
    with col3:
        st.image(bordas, caption="Bordas (Canny)", use_container_width=True)

    # ========== ENVIAR PRO GEMINI ==========
    if st.button("🔎 Analisar com IA", type="primary"):
        with st.spinner("Analisando imagem..."):
            # Cria o client aqui dentro pra garantir
            try:
                chave = st.secrets["GEMINI_API_KEY"]
            except:
                chave = CHAVE_GEMINI

            client = genai.Client(api_key=chave)

            img1 = Image.fromarray(img_cinza)
            img2 = Image.fromarray(img_clahe)
            img3 = Image.fromarray(bordas)

            prompt = """Você é um inspetor técnico especializado em pino-rei e quinta roda
de caminhão. Analise as 3 imagens (original em cinza, realce CLAHE e bordas).

Responda de forma estruturada:

1. TEM TRINCA? (SIM / NÃO / NÃO SEI)
2. Se SIM, onde está localizada?
3. Gravidade: (LEVE / MODERADA / SEVERA)
4. Recomendação: (LIBERAR / INSPECIONAR / SUBSTITUIR)
5. Confiança: (ALTA / MÉDIA / BAIXA)

REGRAS PARA AS COORDENADAS:
- Adicione no final uma linha EXATAMENTE assim:
  COORDENADAS: [y_min, x_min, y_max, x_max]
- Valores entre 0 e 1000 (0,0 = canto superior esquerdo)
- A caixa deve envolver APENAS a trinca, não a peça toda
- Seja preciso: uma trinca fina deve gerar uma caixa fina
- Se a trinca for pequena, a caixa deve ser pequena (menos de 30% da imagem)
- Se não houver trinca: [0, 0, 0, 0]

Exemplo de resposta correta para uma trinca pequena no centro:
COORDENADAS: [420, 380, 560, 520]"""

            try:
                resposta = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=[prompt, img1, img2, img3]
                )

                texto_laudo = resposta.text

                # ========== EXTRAIR COORDENADAS ==========
                coords = None
                match = re.search(r'COORDENADAS:\s*\[([\d,\s]+)\]', texto_laudo)
                if match:
                    valores = [int(x.strip()) for x in match.group(1).split(',')]
                    if len(valores) == 4 and sum(valores) > 0:
                        coords = valores
                    texto_laudo = re.sub(
                        r'COORDENADAS:\s*\[[\d,\s]+\]', '', texto_laudo
                    ).strip()

                st.success("✅ Análise concluída!")
                st.markdown("---")

                # ========== EXIBIR RESULTADO ==========
                if coords:
                    y_min, x_min, y_max, x_max = coords
                    h, w = img_cinza.shape

                    # Converter de 0-1000 para pixels reais
                    x1 = int((x_min / 1000) * w)
                    y1 = int((y_min / 1000) * h)
                    x2 = int((x_max / 1000) * w)
                    y2 = int((y_max / 1000) * h)

                    # ========== LIMITAR TAMANHO MÁXIMO DA CAIXA ==========
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

                    # Garantir que a caixa esteja dentro da imagem
                    x1 = max(0, min(x1, w - 1))
                    y1 = max(0, min(y1, h - 1))
                    x2 = max(0, min(x2, w - 1))
                    y2 = max(0, min(y2, h - 1))

                    # Desenhar retângulo vermelho na imagem original em cores
                    img_marcada = img.copy()
                    cv2.rectangle(img_marcada, (x1, y1), (x2, y2), (0, 0, 255), 3)

                    # Adicionar label "TRINCA" em cima da caixa
                    cv2.putText(
                        img_marcada, "TRINCA",
                        (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
                    )

                    img_marcada_rgb = cv2.cvtColor(img_marcada, cv2.COLOR_BGR2RGB)

                    col_a, col_b = st.columns([1, 1])
                    with col_a:
                        st.subheader("📸 Imagem com marcação")
                        st.image(img_marcada_rgb, use_container_width=True)
                    with col_b:
                        st.subheader("📋 Laudo da IA")
                        st.markdown(texto_laudo)

                else:
                    st.subheader("📋 Laudo da IA")
                    st.markdown(texto_laudo)

                st.markdown("---")

            except Exception as e:
                st.error(f"Erro ao analisar: {e}")
