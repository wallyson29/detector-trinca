import streamlit as st
import cv2
import numpy as np
from PIL import Image
import re
import io
import time
from datetime import datetime, timezone
from google import genai
from supabase import create_client

# Para PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import requests as http_requests

# ========== CONFIGURAÇÃO DA PÁGINA ==========
st.set_page_config(
    page_title="Detector de Trinca",
    page_icon="🔍",
    layout="wide"
)

# ========== CSS CUSTOMIZADO ==========
def aplicar_estilo():
    st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .main .block-container { max-width: 1200px; padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #1e3a5f; font-weight: 700; text-align: center; padding-bottom: 0.5rem; }
    h2, h3 { color: #2c5282; font-weight: 600; }
    .subtitulo { text-align: center; color: #6b7280; font-size: 1.05rem; margin-bottom: 2rem; }
    .stButton > button { border-radius: 8px; font-weight: 600; padding: 0.5rem 1.5rem; transition: all 0.2s; }
    .stButton > button[kind="primary"] { background-color: #2c5282; border-color: #2c5282; }
    .stButton > button[kind="primary"]:hover { background-color: #1e3a5f; border-color: #1e3a5f; }
    .barra-usuario { background: white; padding: 1rem 1.5rem; border-radius: 10px; border-left: 4px solid #2c5282; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05); margin-bottom: 1.5rem; }
    .stTextInput > div > div > input { border-radius: 8px; border: 1px solid #d1d5db; }
    .stTextInput > div > div > input:focus { border-color: #2c5282; box-shadow: 0 0 0 3px rgba(44, 82, 130, 0.1); }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: white; padding: 0.5rem; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05); }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; font-weight: 600; padding: 0.6rem 1.2rem; }
    .stTabs [aria-selected="true"] { background-color: #2c5282 !important; color: white !important; }
    [data-testid="stVerticalBlockBorderWrapper"] { background-color: white; border-radius: 10px; border: 1px solid #e5e7eb; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04); }
    .stAlert { border-radius: 10px; }
    .card-contador { background: white; padding: 1.5rem; border-radius: 12px; border-left: 5px solid #2c5282; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06); text-align: center; }
    .card-contador .numero { font-size: 2.5rem; font-weight: 700; color: #1e3a5f; line-height: 1; }
    .card-contador .rotulo { color: #6b7280; font-size: 0.9rem; margin-top: 0.5rem; font-weight: 500; }
    .card-contador .sub { color: #9ca3af; font-size: 0.75rem; margin-top: 0.25rem; }
    .peca-ok { background: #d1fae5; padding: 1rem; border-radius: 8px; border-left: 4px solid #10b981; margin-bottom: 0.5rem; }
    .peca-trinca { background: #fee2e2; padding: 1rem; border-radius: 8px; border-left: 4px solid #ef4444; margin-bottom: 0.5rem; }
    .metricas-ok { color: #10b981; font-size: 0.75rem; font-weight: 600; }
    .metricas-ruim { color: #ef4444; font-size: 0.75rem; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)


aplicar_estilo()

# ========== CONEXÕES ==========
CHAVE_GEMINI = st.secrets["GEMINI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== CONSTANTES ==========
DIAS_MINIMOS_ENTRE_ANALISES = 15
DOMINIO_FAKE = "@detector.local"

# Limiares de qualidade da foto
LIMIAR_NITIDEZ = 200      # variância do Laplaciano
LIMIAR_BRILHO_MIN = 60    # luminância mínima
LIMIAR_BRILHO_MAX = 200   # luminância máxima
RESOLUCAO_MIN_LARGURA = 800
RESOLUCAO_MIN_ALTURA = 600

CHECKLIST_FOTOS = [
    {"id": "foto_pino_rei_1", "status_col": "status_pino_rei_1", "label": "1. Pino-rei — 1ª carreta", "analisar": True},
    {"id": "foto_pino_rei_2", "status_col": "status_pino_rei_2", "label": "2. Pino-rei — 2ª carreta", "analisar": True},
    {"id": "foto_para_lamas_dir", "status_col": "status_para_lamas_dir", "label": "3. Chassi/para-lamas — 1ª carreta — lado direito + fora", "analisar": True},
    {"id": "foto_para_lamas_esq", "status_col": "status_para_lamas_esq", "label": "4. Chassi/para-lamas — 1ª carreta — lado esquerdo + fora", "analisar": True},
    {"id": "foto_chassi_dir", "status_col": "status_chassi_dir", "label": "5. Chassi — 1ª carreta — lado direito + dentro", "analisar": True},
    {"id": "foto_chassi_esq", "status_col": "status_chassi_esq", "label": "6. Chassi — 1ª carreta — lado esquerdo + dentro", "analisar": True},
    {"id": "foto_porca_dir", "status_col": "status_porca_dir", "label": "7. Porca do berço — direito", "analisar": True},
    {"id": "foto_porca_esq", "status_col": "status_porca_esq", "label": "8. Porca do berço — esquerdo", "analisar": True},
    {"id": "foto_placa", "status_col": None, "label": "9. Foto da placa do caminhão", "analisar": False},
]

# ========== ESTADO DA SESSÃO ==========
if "usuario" not in st.session_state:
    st.session_state.usuario = None

if "tela" not in st.session_state:
    st.session_state.tela = "login"

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None

if "forcar_analise" not in st.session_state:
    st.session_state.forcar_analise = False

if "ver_laudo_anterior" not in st.session_state:
    st.session_state.ver_laudo_anterior = None

if "placa_validada" not in st.session_state:
    st.session_state.placa_validada = None

if "ultima_analise_placa" not in st.session_state:
    st.session_state.ultima_analise_placa = None

if "bloqueado_15dias" not in st.session_state:
    st.session_state.bloqueado_15dias = False

if "resultado_analise" not in st.session_state:
    st.session_state.resultado_analise = None

# ========== REAUTENTICAR SESSÃO ==========
if st.session_state.access_token:
    try:
        supabase.auth.set_session(
            st.session_state.access_token,
            st.session_state.refresh_token
        )
    except Exception:
        st.session_state.usuario = None
        st.session_state.access_token = None
        st.session_state.refresh_token = None


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def username_para_email(username):
    username_limpo = username.lower().replace(" ", "").replace("-", "").strip()
    return f"{username_limpo}{DOMINIO_FAKE}"


def validar_username(username):
    if not username or len(username) < 3:
        return False, "Nome de usuário precisa ter pelo menos 3 caracteres"
    if len(username) > 30:
        return False, "Nome de usuário muito longo (máximo 30 caracteres)"
    if not re.match(r'^[a-zA-Z0-9._-]+$', username):
        return False, "Use apenas letras, números, ponto, hífen ou underline"
    return True, None


def fazer_login(username, senha):
    try:
        email = username_para_email(username)
        resposta = supabase.auth.sign_in_with_password({
            "email": email,
            "password": senha
        })
        st.session_state.access_token = resposta.session.access_token
        st.session_state.refresh_token = resposta.session.refresh_token
        return resposta.user, None
    except Exception as e:
        erro_str = str(e)
        if "Invalid login credentials" in erro_str:
            return None, "Nome de usuário ou senha incorretos"
        return None, erro_str


def fazer_cadastro(username, senha, filial_id):
    try:
        existe = supabase.table("profiles").select("id").eq("username", username).execute()
        if existe.data:
            return False, "Este nome de usuário já está em uso. Escolha outro."

        email = username_para_email(username)
        resposta = supabase.auth.sign_up({
            "email": email,
            "password": senha
        })
        user_id = resposta.user.id

        supabase.table("profiles").insert({
            "id": user_id,
            "username": username,
            "filial_id": filial_id,
            "status": "pendente",
            "role": "user"
        }).execute()

        return True, None
    except Exception as e:
        erro_str = str(e)
        if "already registered" in erro_str.lower():
            return False, "Este nome de usuário já está em uso"
        return False, erro_str


def buscar_perfil(user_id):
    try:
        resposta = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if resposta.data:
            return resposta.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao buscar perfil: {e}")
        return None


def listar_filiais():
    try:
        resposta = supabase.table("filiais").select("*").order("nome").execute()
        return resposta.data
    except Exception:
        return []


def fazer_logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# ============================================================
# FUNÇÕES DE PLACA
# ============================================================
def normalizar_placa(placa):
    if not placa:
        return ""
    return placa.replace("-", "").replace(" ", "").upper().strip()


def validar_placa(placa):
    p = normalizar_placa(placa)
    if len(p) != 7:
        return False, "Placa deve ter 7 caracteres (ex: RSB1A56 ou ABC1234)"
    if re.match(r'^[A-Z]{3}\d[A-Z]\d{2}$', p):
        return True, None
    if re.match(r'^[A-Z]{3}\d{4}$', p):
        return True, None
    return False, "Formato inválido. Use Mercosul (RSB1A56) ou antigo (ABC1234)"


def formatar_placa(placa):
    p = normalizar_placa(placa)
    if len(p) == 7:
        return f"{p[:3]}-{p[3:]}"
    return p


def buscar_ultima_analise_placa(placa):
    try:
        p = normalizar_placa(placa)
        resposta = supabase.rpc("ultima_analise_placa", {"p_placa": p}).execute()
        if resposta.data:
            return resposta.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao buscar última análise: {e}")
        return None


def dias_desde(data_iso):
    try:
        dt = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
        agora = datetime.now(timezone.utc)
        delta = agora - dt
        return delta.days
    except Exception:
        return 999


# ============================================================
# FUNÇÃO DE VERIFICAÇÃO DE QUALIDADE DA FOTO
# ============================================================
def verificar_qualidade_foto(arquivo_bytes):
    """
    Verifica qualidade da foto ANTES de mandar pra IA.
    Retorna (ok, mensagem, metricas).
    """
    try:
        arr = np.frombuffer(arquivo_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False, "Não foi possível ler a imagem", {}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Nitidez (variância do Laplaciano)
        nitidez = cv2.Laplacian(gray, cv2.CV_64F).var()

        # 2. Brilho (luminância média)
        brilho = float(np.mean(gray))

        # 3. Resolução
        h, w = img.shape[:2]

        problemas = []
        if nitidez < LIMIAR_NITIDEZ:
            problemas.append(f"foto desfocada/borrada (nitidez: {nitidez:.0f})")
        if brilho < LIMIAR_BRILHO_MIN:
            problemas.append(f"foto muito escura (brilho: {brilho:.0f})")
        elif brilho > LIMIAR_BRILHO_MAX:
            problemas.append(f"foto muito clara/estourada (brilho: {brilho:.0f})")
        if w < RESOLUCAO_MIN_LARGURA or h < RESOLUCAO_MIN_ALTURA:
            problemas.append(f"resolução baixa ({w}x{h}, mínimo {RESOLUCAO_MIN_LARGURA}x{RESOLUCAO_MIN_ALTURA})")

        metricas = {
            "nitidez": nitidez,
            "brilho": brilho,
            "resolucao": f"{w}x{h}",
            "ok_nitidez": nitidez >= LIMIAR_NITIDEZ,
            "ok_brilho": LIMIAR_BRILHO_MIN <= brilho <= LIMIAR_BRILHO_MAX,
            "ok_resolucao": w >= RESOLUCAO_MIN_LARGURA and h >= RESOLUCAO_MIN_ALTURA,
        }

        if problemas:
            msg = "⚠️ " + " • ".join(problemas)
            return False, msg, metricas

        return True, "✅ Foto OK", metricas
    except Exception as e:
        return False, f"Erro ao verificar: {e}", {}


def exibir_metricas(metricas):
    """Exibe as métricas de qualidade da foto em formato amigável."""
    if not metricas:
        return
    nit_ok = "metricas-ok" if metricas.get("ok_nitidez") else "metricas-ruim"
    bri_ok = "metricas-ok" if metricas.get("ok_brilho") else "metricas-ruim"
    res_ok = "metricas-ok" if metricas.get("ok_resolucao") else "metricas-ruim"

    st.markdown(
        f'<span class="{nit_ok}">Nitidez: {metricas["nitidez"]:.0f}</span> • '
        f'<span class="{bri_ok}">Brilho: {metricas["brilho"]:.0f}</span> • '
        f'<span class="{res_ok}">Res: {metricas["resolucao"]}</span>',
        unsafe_allow_html=True
    )


# ============================================================
# FUNÇÕES DE ADMIN
# ============================================================
def listar_pendentes():
    try:
        resposta = (
            supabase.table("profiles")
            .select("*")
            .eq("status", "pendente")
            .order("created_at")
            .execute()
        )
        return resposta.data
    except Exception as e:
        st.error(f"Erro ao listar pendentes: {e}")
        return []


def listar_aprovados():
    try:
        resposta = (
            supabase.table("profiles")
            .select("*")
            .eq("status", "aprovado")
            .order("created_at")
            .execute()
        )
        return resposta.data
    except Exception as e:
        st.error(f"Erro ao listar aprovados: {e}")
        return []


def atualizar_usuario(user_id, dados):
    try:
        supabase.table("profiles").update(dados).eq("id", user_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def nome_filial(filial_id):
    try:
        resposta = supabase.rpc("nome_filial_por_id", {"p_id": filial_id}).execute()
        if resposta.data:
            return resposta.data
        return "—"
    except Exception:
        return "—"


def nome_usuario(user_id):
    try:
        resposta = supabase.rpc("nome_usuario_por_id", {"p_id": user_id}).execute()
        if resposta.data:
            return resposta.data
        return "—"
    except Exception:
        return "—"


# ============================================================
# FUNÇÕES DE FILIAIS
# ============================================================
def criar_filial(nome):
    try:
        supabase.rpc("criar_filial", {"p_nome": nome.strip()}).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def deletar_filial(filial_id):
    try:
        resposta = supabase.rpc("deletar_filial", {"p_id": filial_id}).execute()
        if resposta.data is True:
            return True, None
        else:
            return False, "Não é possível deletar: há usuários vinculados a esta filial."
    except Exception as e:
        return False, str(e)


def contar_usuarios_filial(filial_id):
    try:
        resposta = (
            supabase.table("profiles")
            .select("*", count="exact")
            .eq("filial_id", filial_id)
            .execute()
        )
        return resposta.count if resposta.count else 0
    except Exception:
        return 0


def atualizar_usuario_filial(filial_id, dados):
    try:
        supabase.table("filiais").update(dados).eq("id", filial_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)


# ============================================================
# FUNÇÕES DE CONTADORES
# ============================================================
def buscar_contadores():
    try:
        resposta = supabase.rpc("contadores_analises").execute()
        if resposta.data:
            return resposta.data[0]
        return None
    except Exception:
        return None


def buscar_contadores_filial():
    try:
        resposta = supabase.rpc("contadores_por_filial").execute()
        return resposta.data or []
    except Exception:
        return []


# ============================================================
# FUNÇÕES DE HISTÓRICO
# ============================================================
def buscar_historico(filial_id=None, placa=None, dias=None, user_id=None, limite=100, offset=0):
    try:
        resposta = supabase.rpc("historico_analises", {
            "p_filial_id": filial_id,
            "p_placa": placa,
            "p_dias": dias,
            "p_limite": limite,
            "p_offset": offset,
            "p_user_id": user_id,
        }).execute()
        return resposta.data or []
    except Exception as e:
        st.error(f"Erro ao buscar histórico: {e}")
        return []


# ============================================================
# FUNÇÕES DE UPLOAD
# ============================================================
def fazer_upload_imagem(imagem_np, user_id, nome_arquivo):
    try:
        sucesso, buffer = cv2.imencode(".jpg", imagem_np)
        if not sucesso:
            return None, "Falha ao codificar imagem"

        bytes_img = buffer.tobytes()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        caminho = f"{user_id}/{timestamp}_{nome_arquivo}.jpg"

        supabase.storage.from_("fotos").upload(
            path=caminho,
            file=bytes_img,
            file_options={"content-type": "image/jpeg"}
        )

        url = supabase.storage.from_("fotos").get_public_url(caminho)
        return url, None
    except Exception as e:
        return None, str(e)


# ============================================================
# FUNÇÃO DE ANÁLISE POR PEÇA (COM RETRY)
# ============================================================
def analisar_peca(client, img_original_bgr, nome_peca):
    """
    Analisa 1 peça com 2 imagens (original + CLAHE).
    Faz retry automático em caso de erro 503.
    """
    max_tentativas = 3
    espera = 5

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
                model="gemini-3.5-flash-lite",
                contents=[prompt, img_a, img_b]
            )
            texto = resposta.text

            # Se chegou aqui, funcionou. Extrai os campos.
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


def gerar_laudo_consolidado(resultados, placa):
    """Monta o laudo consolidado a partir dos resultados por peça."""
    linhas = [f"LAUDO DE INSPEÇÃO — PLACA {placa}", ""]

    tem_trinca_geral = False
    tem_erro = False
    pecas_com_trinca = []
    pecas_com_erro = []
    gravidades = []
    confiancas = []

    for i, item in enumerate(CHECKLIST_FOTOS):
        if not item["analisar"]:
            continue
        res = resultados.get(item["id"])
        if not res:
            continue

        status = res["status"]
        if status == "ERRO":
            emoji = "🟡"
            tem_erro = True
            pecas_com_erro.append(f"{i+1}. {item['label']}")
        elif status.startswith("TRINCA"):
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

    if tem_erro:
        linhas.append(f"⚠️ ANÁLISE INCOMPLETA — {len(pecas_com_erro)} peça(s) não puderam ser analisadas")
        linhas.append(f"   Peças com erro: {', '.join(pecas_com_erro)}")
        linhas.append("   Recomendação: Refazer a análise dessas peças manualmente")
        linhas.append("")

    linhas.append(f"1. TEM TRINCA? {'SIM' if tem_trinca_geral else ('NÃO SEI' if tem_erro else 'NÃO')}")
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
        linhas.append("4. Recomendação: LIBERAR" if not tem_erro else "4. Recomendação: REFAZER ANÁLISE")

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


def extrair_campos_laudo(texto):
    campos = {"tem_trinca": None, "gravidade": None, "recomendacao": None, "confianca": None}

    match = re.search(r'TEM TRINCA\??\s*\**\s*(SIM|NÃO|NAO|NÃO SEI)', texto, re.IGNORECASE)
    if match:
        campos["tem_trinca"] = match.group(1).upper().replace("NAO", "NÃO")

    match = re.search(r'Gravidade geral[:\s]*\**\s*(LEVE|MODERADA|SEVERA)', texto, re.IGNORECASE)
    if match:
        campos["gravidade"] = match.group(1).upper()

    match = re.search(r'Recomenda[çc][ãa]o[:\s]*\**\s*(LIBERAR|INSPECIONAR|SUBSTITUIR|REFAZER)', texto, re.IGNORECASE)
    if match:
        campos["recomendacao"] = match.group(1).upper()

    match = re.search(r'Confian[çc]a[:\s]*\**\s*(ALTA|MÉDIA|MEDIA|BAIXA)', texto, re.IGNORECASE)
    if match:
        campos["confianca"] = match.group(1).upper().replace("MEDIA", "MÉDIA")

    return campos


def salvar_analise_completa(perfil, placa, resultados, fotos_urls, texto_laudo, foto_observacao_url=None, texto_observacao=None, forcado=False):
    try:
        user_id = perfil["id"]
        filial_id = perfil["filial_id"]

        dados = {
            "user_id": user_id,
            "filial_id": filial_id,
            "placa": normalizar_placa(placa),
            "laudo": texto_laudo,
            "forcado": forcado,
            "foto_observacao": foto_observacao_url,
            "texto_observacao": texto_observacao,
        }

        campos = extrair_campos_laudo(texto_laudo)
        dados["tem_trinca"] = campos["tem_trinca"]
        dados["gravidade"] = campos["gravidade"]
        dados["recomendacao"] = campos["recomendacao"]
        dados["confianca"] = campos["confianca"]

        for item in CHECKLIST_FOTOS:
            dados[item["id"]] = fotos_urls.get(item["id"])

        for item in CHECKLIST_FOTOS:
            if item["status_col"]:
                res = resultados.get(item["id"])
                dados[item["status_col"]] = res["status"] if res else None

        supabase.table("analises").insert(dados).execute()
        return True, None
    except Exception as e:
        return False, str(e)


# ============================================================
# TELA DE LOGIN
# ============================================================
def tela_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_esq, col_centro, col_dir = st.columns([1, 1.2, 1])
    with col_centro:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="font-size: 2.2rem; margin-bottom: 0.3rem;">🔍 Detector de Trinca</h1>
            <p class="subtitulo">Inspeção inteligente de pino-rei e quinta roda</p>
        </div>
        """, unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### 🔐 Acesso")
            st.markdown("<br>", unsafe_allow_html=True)
            username = st.text_input("👤 Nome de usuário", key="login_username", placeholder="Ex: joao.silva")
            senha = st.text_input("🔒 Senha", type="password", key="login_senha")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Entrar", type="primary", use_container_width=True):
                if not username or not senha:
                    st.warning("Preencha nome de usuário e senha.")
                else:
                    user, erro = fazer_login(username.strip(), senha)
                    if erro:
                        st.error(f"Erro no login: {erro}")
                    else:
                        st.session_state.usuario = user
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #6b7280; margin: 0;'>Não tem conta?</p>", unsafe_allow_html=True)
            if st.button("Cadastre-se", use_container_width=True):
                st.session_state.tela = "cadastro"
                st.rerun()


# ============================================================
# TELA DE CADASTRO
# ============================================================
def tela_cadastro():
    st.markdown("<br>", unsafe_allow_html=True)
    col_esq, col_centro, col_dir = st.columns([1, 1.2, 1])
    with col_centro:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="font-size: 2rem;">📝 Criar Conta</h1>
            <p class="subtitulo">Preencha os dados para solicitar acesso</p>
        </div>
        """, unsafe_allow_html=True)
        with st.container(border=True):
            username = st.text_input("👤 Nome de usuário", key="cad_username", placeholder="Ex: joao.silva")
            st.caption("Use apenas letras, números, ponto, hífen ou underline (3-30 caracteres)")
            senha = st.text_input("🔒 Senha (mínimo 6 caracteres)", type="password", key="cad_senha")
            confirmar = st.text_input("🔒 Confirme a senha", type="password", key="cad_confirmar")

            filiais = listar_filiais()
            if filiais:
                opcoes = {f["nome"]: f["id"] for f in filiais}
                filial_escolhida = st.selectbox("🏢 Filial", list(opcoes.keys()), key="cad_filial")
                filial_id = opcoes[filial_escolhida]
            else:
                st.error("Nenhuma filial cadastrada. Contate o administrador.")
                filial_id = None

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Cadastrar", type="primary", use_container_width=True):
                valido, msg = validar_username(username)
                if not valido:
                    st.warning(msg)
                elif not senha or len(senha) < 6:
                    st.warning("A senha precisa ter pelo menos 6 caracteres.")
                elif senha != confirmar:
                    st.warning("As senhas não coincidem.")
                elif not filial_id:
                    st.warning("Selecione uma filial.")
                else:
                    ok, erro = fazer_cadastro(username.strip(), senha, filial_id)
                    if ok:
                        st.success("✅ Cadastro realizado! Aguarde aprovação do administrador.")
                        st.info("Depois de aprovado, você poderá fazer login.")
                    else:
                        st.error(f"Erro no cadastro: {erro}")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("← Voltar para login", use_container_width=True):
                st.session_state.tela = "login"
                st.rerun()


# ============================================================
# TELA DE AGUARDANDO APROVAÇÃO
# ============================================================
def tela_pendente(perfil):
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_esq, col_centro, col_dir = st.columns([1, 1.5, 1])
    with col_centro:
        with st.container(border=True):
            st.markdown(f"""
            <div style="text-align: center; padding: 1rem;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">⏳</div>
                <h2 style="color: #2c5282;">Aguardando aprovação</h2>
                <p style="color: #6b7280; font-size: 1.05rem;">
                    Olá, <strong>{perfil['username']}</strong>!<br>
                    Seu cadastro está pendente.
                </p>
                <p style="color: #6b7280; margin-top: 1.5rem;">
                    O administrador precisa aprovar sua conta antes de você usar o detector.
                    Assim que for aprovado, faça login novamente.
                </p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("← Sair", use_container_width=True):
                fazer_logout()


# ============================================================
# ABA DE ADMIN — PENDENTES
# ============================================================
def aba_pendentes():
    st.subheader("👥 Usuários aguardando aprovação")
    pendentes = listar_pendentes()
    if not pendentes:
        st.info("Nenhum usuário pendente no momento.")
        return
    for u in pendentes:
        filial_nome = nome_filial(u.get("filial_id"))
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**{u['username']}**")
                st.caption(f"🏢 {filial_nome}")
                st.caption(f"📅 {u['created_at'][:19]}")
            with col2:
                if st.button("✅ Aprovar", key=f"aprovar_{u['id']}", type="primary", use_container_width=True):
                    ok, erro = atualizar_usuario(u["id"], {"status": "aprovado"})
                    if ok:
                        st.success(f"{u['username']} aprovado!")
                        st.rerun()
                    else:
                        st.error(f"Erro: {erro}")
            with col3:
                if st.button("❌ Rejeitar", key=f"rejeitar_{u['id']}", use_container_width=True):
                    ok, erro = atualizar_usuario(u["id"], {"status": "rejeitado"})
                    if ok:
                        st.warning(f"{u['username']} rejeitado.")
                        st.rerun()
                    else:
                        st.error(f"Erro: {erro}")


# ============================================================
# ABA DE ADMIN — APROVADOS
# ============================================================
def aba_aprovados():
    st.subheader("✅ Usuários aprovados")
    aprovados = listar_aprovados()
    if not aprovados:
        st.info("Nenhum usuário aprovado ainda.")
        return
    for u in aprovados:
        filial_nome = nome_filial(u.get("filial_id"))
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                badge = "🛡️ ADMIN" if u["role"] == "admin" else "👤 Usuário"
                st.markdown(f"**{u['username']}** — {badge}")
                st.caption(f"🏢 {filial_nome}")
            with col2:
                if u["role"] == "user":
                    if st.button("⬆️ Tornar Admin", key=f"promover_{u['id']}", use_container_width=True):
                        ok, erro = atualizar_usuario(u["id"], {"role": "admin"})
                        if ok:
                            st.success(f"{u['username']} agora é admin.")
                            st.rerun()
                        else:
                            st.error(f"Erro: {erro}")
                else:
                    st.caption("Já é admin")
            with col3:
                if u["role"] == "admin":
                    if st.button("⬇️ Rebaixar", key=f"rebaixar_{u['id']}", use_container_width=True):
                        ok, erro = atualizar_usuario(u["id"], {"role": "user"})
                        if ok:
                            st.warning(f"{u['username']} agora é user.")
                            st.rerun()
                        else:
                            st.error(f"Erro: {erro}")
                else:
                    if st.button("🚫 Bloquear", key=f"bloquear_{u['id']}", use_container_width=True):
                        ok, erro = atualizar_usuario(u["id"], {"status": "rejeitado"})
                        if ok:
                            st.warning(f"{u['username']} bloqueado.")
                            st.rerun()
                        else:
                            st.error(f"Erro: {erro}")


# ============================================================
# ABA DE ADMIN — FILIAIS
# ============================================================
def aba_filiais():
    st.subheader("🏢 Gerenciar Filiais")
    with st.expander("➕ Adicionar nova filial", expanded=False):
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            nova_filial = st.text_input("Nome da filial", placeholder="Ex: Filial Palmas", key="nova_filial_nome")
        with col_f2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Adicionar", type="primary", use_container_width=True):
                if not nova_filial or not nova_filial.strip():
                    st.warning("Digite o nome da filial.")
                else:
                    ok, erro = criar_filial(nova_filial)
                    if ok:
                        st.success(f"✅ Filial '{nova_filial}' criada!")
                        st.rerun()
                    else:
                        st.error(f"Erro: {erro}")
    st.markdown("---")
    filiais = listar_filiais()
    if not filiais:
        st.info("Nenhuma filial cadastrada ainda. Adicione a primeira acima.")
        return
    st.markdown(f"**Total:** {len(filiais)} filial(is)")
    for f in filiais:
        qtd_usuarios = contar_usuarios_filial(f["id"])
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**🏢 {f['nome']}**")
                st.caption(f"ID: {f['id']}")
                st.caption(f"👥 {qtd_usuarios} usuário(s)")
            with col2:
                novo_nome = st.text_input("Renomear:", value=f["nome"], key=f"renomear_{f['id']}", label_visibility="collapsed", placeholder="Novo nome")
                if st.button("💾 Salvar", key=f"salvar_nome_{f['id']}", use_container_width=True):
                    if not novo_nome or not novo_nome.strip():
                        st.warning("Nome não pode ser vazio.")
                    elif novo_nome.strip() == f["nome"]:
                        st.info("Nada mudou.")
                    else:
                        ok, erro = atualizar_usuario_filial(f["id"], {"nome": novo_nome.strip()})
                        if ok:
                            st.success("Nome atualizado!")
                            st.rerun()
                        else:
                            st.error(f"Erro: {erro}")
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if qtd_usuarios == 0:
                    if st.button("🗑️ Deletar", key=f"deletar_{f['id']}", use_container_width=True):
                        ok, msg = deletar_filial(f["id"])
                        if ok:
                            st.warning(f"Filial '{f['nome']}' deletada.")
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.caption("🔒 Tem usuários")


# ============================================================
# ABA DE ADMIN — DASHBOARD
# ============================================================
def aba_dashboard():
    st.subheader("📊 Dashboard de Análises")
    contadores = buscar_contadores()
    if contadores:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="card-contador">
                <div class="numero">{contadores.get('total_hoje', 0)}</div>
                <div class="rotulo">Hoje</div>
                <div class="sub">{contadores.get('forcadas_hoje', 0)} forçada(s)</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="card-contador">
                <div class="numero">{contadores.get('total_7dias', 0)}</div>
                <div class="rotulo">Últimos 7 dias</div>
                <div class="sub">&nbsp;</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="card-contador">
                <div class="numero">{contadores.get('total_30dias', 0)}</div>
                <div class="rotulo">Últimos 30 dias</div>
                <div class="sub">&nbsp;</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="card-contador">
                <div class="numero">{contadores.get('total_geral', 0)}</div>
                <div class="rotulo">Total geral</div>
                <div class="sub">&nbsp;</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 🏢 Por Filial")
    contadores_filial = buscar_contadores_filial()
    if not contadores_filial:
        st.info("Nenhuma filial cadastrada.")
        return
    for cf in contadores_filial:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**🏢 {cf['filial_nome']}**")
            with col2:
                st.markdown(f"**Hoje:** {cf.get('total_hoje', 0)}")
            with col3:
                st.markdown(f"**Total:** {cf.get('total_geral', 0)}")


# ============================================================
# FUNÇÃO AUXILIAR — MOSTRAR FOTOS DE UMA ANÁLISE
# ============================================================
def mostrar_fotos_analise(analise):
    st.markdown("**📸 Fotos da inspeção**")
    cols = st.columns(3)
    for i, item in enumerate(CHECKLIST_FOTOS):
        url = analise.get(item["id"])
        if url:
            with cols[i % 3]:
                st.image(url, caption=item["label"], use_container_width=True)

    if analise.get("foto_observacao"):
        st.markdown("**📸 Foto de observação**")
        st.image(analise["foto_observacao"], use_container_width=True)

    if analise.get("texto_observacao"):
        st.markdown("**📝 Observação do técnico**")
        st.info(analise["texto_observacao"])


# ============================================================
# ABA DE ADMIN — HISTÓRICO
# ============================================================
def aba_historico():
    st.subheader("📄 Histórico de Análises")
    with st.expander("🔍 Filtros", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filiais = listar_filiais()
            opcoes_filial = {"Todas as filiais": None}
            for f in filiais:
                opcoes_filial[f["nome"]] = f["id"]
            filial_nome_sel = st.selectbox("🏢 Filial", list(opcoes_filial.keys()), key="hist_filial")
            filial_filtro = opcoes_filial[filial_nome_sel]
        with col_f2:
            placa_filtro = st.text_input("🚗 Placa (opcional)", placeholder="Ex: RSB2I29", key="hist_placa")
            if placa_filtro:
                placa_filtro = normalizar_placa(placa_filtro)
        with col_f3:
            dias_filtro = st.selectbox("📅 Período", ["Todos", "Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias"], key="hist_dias")
            mapa_dias = {"Todos": None, "Últimos 7 dias": 7, "Últimos 30 dias": 30, "Últimos 90 dias": 90}
            dias_filtro_valor = mapa_dias[dias_filtro]

    resultados = buscar_historico(
        filial_id=filial_filtro,
        placa=placa_filtro if placa_filtro else None,
        dias=dias_filtro_valor,
        user_id=None,
        limite=50,
        offset=0
    )
    if not resultados:
        st.info("Nenhuma análise encontrada com esses filtros.")
        return
    st.markdown(f"**{len(resultados)} análise(s) encontrada(s)**")
    st.markdown("---")
    for a in resultados:
        placa = formatar_placa(a.get("placa", "—"))
        data = a.get("created_at", "")[:19].replace("T", " ")
        quem = nome_usuario(a.get("user_id"))
        filial = nome_filial(a.get("filial_id"))
        tem_trinca = a.get("tem_trinca", "—")
        gravidade = a.get("gravidade", "—")
        if tem_trinca == "SIM":
            status_emoji = "🔴"
        elif tem_trinca == "NÃO":
            status_emoji = "🟢"
        else:
            status_emoji = "🟡"
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            with col1:
                st.markdown(f"**{status_emoji} {placa}**")
                st.caption(f"📅 {data}")
            with col2:
                st.markdown(f"**Resultado:** {tem_trinca}")
                if gravidade and gravidade != "—":
                    st.caption(f"Gravidade: {gravidade}")
            with col3:
                st.caption(f"👤 {quem}")
                st.caption(f"🏢 {filial}")
            with col4:
                if st.button("👁️ Ver", key=f"exp_{a['id']}", use_container_width=True):
                    if st.session_state.get(f"mostrar_{a['id']}"):
                        st.session_state[f"mostrar_{a['id']}"] = False
                    else:
                        st.session_state[f"mostrar_{a['id']}"] = True
                    st.rerun()
            if st.session_state.get(f"mostrar_{a['id']}"):
                st.markdown("---")
                mostrar_fotos_analise(a)
                st.markdown("---")
                st.markdown("**📋 Laudo**")
                st.markdown(a.get("laudo", "—"))
                if a.get("forcado"):
                    st.caption("⚠️ Esta análise foi FORÇADA (fora do prazo de 15 dias)")
                st.markdown("---")
                if st.button(f"📥 Baixar PDF", key=f"pdf_{a['id']}", type="primary"):
                    with st.spinner("Gerando PDF..."):
                        pdf_bytes, erro = gerar_pdf_analise(a)
                        if pdf_bytes:
                            st.download_button(
                                label="💾 Clique para baixar",
                                data=pdf_bytes,
                                file_name=f"laudo_{normalizar_placa(a['placa'])}_{a['id']}.pdf",
                                mime="application/pdf",
                                key=f"dl_{a['id']}"
                            )
                        else:
                            st.error(f"Erro ao gerar PDF: {erro}")


# ============================================================
# FUNÇÕES DE PDF
# ============================================================
def gerar_pdf_analise(analise):
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


# ============================================================
# TELA DE ANÁLISE (1 PEÇA POR VEZ + VERIFICAÇÃO DE QUALIDADE)
# ============================================================
def tela_analise(perfil):
    st.title("🔍 Detector de Trinca")
    st.markdown("<p class='subtitulo'>Inspeção completa do conjunto de engate</p>", unsafe_allow_html=True)

    placa_input = st.text_input("🚗 Placa do caminhão", placeholder="RSB-1A56 ou ABC-1234", key="placa_input")

    if placa_input:
        valida, msg_erro = validar_placa(placa_input)
        if not valida:
            st.error(msg_erro)
            st.session_state.placa_validada = None
            st.session_state.bloqueado_15dias = False
            st.session_state.ultima_analise_placa = None
        else:
            placa_normalizada = normalizar_placa(placa_input)
            if st.session_state.placa_validada != placa_normalizada:
                st.session_state.placa_validada = placa_normalizada
                st.session_state.ver_laudo_anterior = None
                st.session_state.forcar_analise = False
                st.session_state.ultima_analise_placa = None
                st.session_state.bloqueado_15dias = False
                st.session_state.resultado_analise = None

            ultima = buscar_ultima_analise_placa(placa_normalizada)
            st.session_state.ultima_analise_placa = ultima

            if ultima is None:
                st.session_state.bloqueado_15dias = False
                st.success(f"✅ Placa {formatar_placa(placa_normalizada)} — nenhuma análise anterior. Pode analisar.")
            else:
                dias = dias_desde(ultima["created_at"])
                if dias < DIAS_MINIMOS_ENTRE_ANALISES:
                    st.session_state.bloqueado_15dias = True
                else:
                    st.session_state.bloqueado_15dias = False
                    st.success(f"✅ Placa {formatar_placa(placa_normalizada)} — última análise há {dias} dias. Pode analisar.")

    if st.session_state.bloqueado_15dias and st.session_state.ultima_analise_placa:
        u = st.session_state.ultima_analise_placa
        dias = dias_desde(u["created_at"])
        quem = nome_usuario(u["user_id"])
        filial = nome_filial(u["filial_id"])
        tipo = "⚠️ análise FORÇADA" if u.get("forcado") else "análise"

        st.warning(
            f"⚠️ **Placa {formatar_placa(u['placa'])} já foi analisada há {dias} dias.**\n\n"
            f"Última {tipo}:\n"
            f"- **Data:** {u['created_at'][:19]}\n"
            f"- **Por:** {quem}\n"
            f"- **Filial:** {filial}\n"
            f"- **Resultado:** {u.get('tem_trinca', '—')} / {u.get('gravidade', '—')}\n\n"
            f"É necessário aguardar **{DIAS_MINIMOS_ENTRE_ANALISES} dias** entre análises da mesma placa."
        )

        col_v1, col_v2, col_v3 = st.columns([1, 1, 2])
        with col_v1:
            if st.button("📄 Ver laudo", use_container_width=True):
                if st.session_state.ver_laudo_anterior == u["id"]:
                    st.session_state.ver_laudo_anterior = None
                else:
                    st.session_state.ver_laudo_anterior = u["id"]
                st.rerun()

        with col_v2:
            if st.button("📥 Baixar PDF", use_container_width=True, type="primary"):
                with st.spinner("Gerando PDF..."):
                    pdf_bytes, erro_pdf = gerar_pdf_analise(u)
                    if pdf_bytes:
                        st.download_button(
                            label="💾 Clique para baixar",
                            data=pdf_bytes,
                            file_name=f"laudo_{normalizar_placa(u['placa'])}_{u['id']}.pdf",
                            mime="application/pdf",
                            key="dl_bloqueio"
                        )
                    else:
                        st.error(f"Erro ao gerar PDF: {erro_pdf}")

        if st.session_state.get("ver_laudo_anterior") == u["id"]:
            st.markdown("---")
            st.subheader("📄 Laudo anterior")
            with st.container(border=True):
                mostrar_fotos_analise(u)
                st.markdown("---")
                st.markdown("**📋 Laudo**")
                st.markdown(u.get("laudo", "—"))
                st.markdown("---")
                st.caption(f"👤 {quem} • 🏢 {filial} • 📅 {u['created_at'][:19]} • 🚗 {formatar_placa(u['placa'])}")
                if u.get("forcado"):
                    st.caption("⚠️ Esta análise foi FORÇADA (fora do prazo de 15 dias)")

        if perfil["role"] == "admin":
            st.markdown("---")
            st.info("🛡️ Como admin, você pode forçar uma nova análise.")
            if st.button("⚠️ Forçar análise mesmo assim", type="secondary"):
                st.session_state.forcar_analise = True
                st.session_state.bloqueado_15dias = False
                st.session_state.ver_laudo_anterior = None
                st.rerun()

    placa_ok = st.session_state.placa_validada is not None
    nao_bloqueado = not st.session_state.bloqueado_15dias

    if placa_ok and nao_bloqueado:
        st.markdown("---")
        st.markdown("### 📸 Checklist de Fotos")
        st.caption("Todas as 9 fotos são obrigatórias. A IA analisa as 8 primeiras (a placa é só registro).")
        st.caption("📋 **Critérios de qualidade:** nitidez mínima, brilho adequado e resolução ≥ 800x600.")

        if st.session_state.forcar_analise:
            st.warning("⚠️ Análise FORÇADA (fora do prazo de 15 dias)")

        # Admin pode desabilitar a verificação de qualidade
        pular_verificacao = False
        if perfil["role"] == "admin":
            pular_verificacao = st.checkbox(
                "🛡️ Admin: pular verificação de qualidade das fotos",
                value=False,
                key="pular_verificacao_admin"
            )
            if pular_verificacao:
                st.warning("⚠️ Verificação de qualidade DESATIVADA pelo admin. Fotos ruins podem ir pra IA.")

        # Upload em grid 3x3
        fotos_upload = {}
        fotos_qualidade = {}
        total_ok = 0
        total_ruim = 0

        for linha in range(3):
            cols = st.columns(3)
            for col in range(3):
                idx = linha * 3 + col
                if idx >= len(CHECKLIST_FOTOS):
                    break
                item = CHECKLIST_FOTOS[idx]
                with cols[col]:
                    label_ok = "✅" if st.session_state.get(f"uploaded_{item['id']}") else "📤"
                    st.markdown(f"**{label_ok} {item['label']}**")
                    arquivo = st.file_uploader(
                        item["label"],
                        type=["jpg", "jpeg", "png"],
                        key=f"upload_{item['id']}",
                        label_visibility="collapsed"
                    )
                    if arquivo:
                        # Verifica qualidade
                        if pular_verificacao:
                            ok_q, msg_q, metricas_q = True, "✅ Verificação pulada (admin)", {}
                        else:
                            ok_q, msg_q, metricas_q = verificar_qualidade_foto(arquivo.getvalue())

                        fotos_qualidade[item["id"]] = {
                            "ok": ok_q,
                            "msg": msg_q,
                            "metricas": metricas_q,
                        }

                        if ok_q:
                            fotos_upload[item["id"]] = arquivo
                            st.session_state[f"uploaded_{item['id']}"] = True
                            total_ok += 1
                            st.markdown(f'<span class="metricas-ok">✅ Qualidade OK</span>', unsafe_allow_html=True)
                            if metricas_q:
                                exibir_metricas(metricas_q)
                        else:
                            st.session_state[f"uploaded_{item['id']}"] = False
                            total_ruim += 1
                            st.error(f"❌ {msg_q}")
                            if metricas_q:
                                exibir_metricas(metricas_q)
                    else:
                        st.session_state[f"uploaded_{item['id']}"] = False

        st.markdown("---")
        st.markdown(f"**Progresso:** {total_ok}/9 fotos válidas")

        if total_ruim > 0:
            st.warning(f"⚠️ {total_ruim} foto(s) com qualidade ruim. Corrija antes de analisar.")

        with st.expander("📝 Observação (opcional)", expanded=False):
            foto_obs = st.file_uploader(
                "Foto de peça trincada (fora do checklist)",
                type=["jpg", "jpeg", "png"],
                key="upload_observacao"
            )
            texto_obs = st.text_area(
                "Descrição da observação",
                placeholder="Ex: Encontrei trinca no suporte do para-lama traseiro",
                key="texto_observacao_input"
            )

        # Botão Analisar (só libera se todas as 9 estão OK)
        if total_ok == 9:
            st.markdown("---")
            if st.button("🔎 Analisar com IA", type="primary", use_container_width=True):
                with st.spinner("Preparando análise..."):
                    try:
                        client = genai.Client(api_key=CHAVE_GEMINI)

                        # ========== UPLOAD DAS FOTOS ==========
                        fotos_urls = {}
                        fotos_brutas = {}

                        for item in CHECKLIST_FOTOS:
                            arquivo = fotos_upload.get(item["id"])
                            if arquivo:
                                bytes_img = arquivo.read()
                                img_array = np.frombuffer(bytes_img, np.uint8)
                                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                fotos_brutas[item["id"]] = img

                        foto_obs_url = None
                        if foto_obs:
                            bytes_obs = foto_obs.read()
                            arr_obs = np.frombuffer(bytes_obs, np.uint8)
                            img_obs = cv2.imdecode(arr_obs, cv2.IMREAD_COLOR)
                            foto_obs_url, _ = fazer_upload_imagem(img_obs, perfil["id"], "observacao")

                        # ========== ANÁLISE PEÇA POR PEÇA ==========
                        resultados = {}
                        pecas_para_analisar = [item for item in CHECKLIST_FOTOS if item["analisar"]]
                        total_pecas = len(pecas_para_analisar)

                        barra_progresso = st.progress(0)
                        status_texto = st.empty()

                        for i, item in enumerate(pecas_para_analisar):
                            status_texto.markdown(f"**Analisando peça {i+1}/{total_pecas}:** {item['label']}...")

                            img_original = fotos_brutas.get(item["id"])
                            if img_original is None:
                                continue

                            resultado = analisar_peca(client, img_original, item["label"])
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

                        # Upload da placa
                        if "foto_placa" in fotos_brutas:
                            url_placa, _ = fazer_upload_imagem(fotos_brutas["foto_placa"], perfil["id"], "foto_placa")
                            fotos_urls["foto_placa"] = url_placa

                        status_texto.markdown("**✅ Análise concluída!**")

                        texto_laudo = gerar_laudo_consolidado(resultados, formatar_placa(st.session_state.placa_validada))

                        with st.spinner("💾 Salvando análise..."):
                            ok, erro = salvar_analise_completa(
                                perfil,
                                st.session_state.placa_validada,
                                resultados,
                                fotos_urls,
                                texto_laudo,
                                foto_observacao_url=foto_obs_url,
                                texto_observacao=texto_obs if texto_obs else None,
                                forcado=st.session_state.forcar_analise
                            )

                            if ok:
                                st.success("💾 Análise salva com sucesso!")
                                st.session_state.resultado_analise = {
                                    "resultados": resultados,
                                    "laudo": texto_laudo,
                                    "placa": st.session_state.placa_validada,
                                }
                                st.session_state.forcar_analise = False
                                st.session_state.placa_validada = None
                                st.session_state.ultima_analise_placa = None
                                st.session_state.bloqueado_15dias = False
                                st.session_state.ver_laudo_anterior = None
                                st.rerun()
                            else:
                                st.warning(f"Análise gerada mas não foi possível salvar: {erro}")

                    except Exception as e:
                        st.error(f"Erro na análise: {e}")
        else:
            faltando = 9 - total_ok
            if faltando > 0:
                st.info(f"📸 Faltam **{faltando}** foto(s) válida(s) para liberar a análise.")

        # ========== MOSTRA RESULTADO SE TIVER ==========
        if st.session_state.get("resultado_analise"):
            res = st.session_state.resultado_analise
            st.markdown("---")
            st.subheader(f"📋 Resultado da Análise — {formatar_placa(res['placa'])}")

            for item in CHECKLIST_FOTOS:
                if not item["analisar"]:
                    continue
                r = res["resultados"].get(item["id"])
                if not r:
                    continue

                status = r["status"]
                if status.startswith("TRINCA"):
                    st.markdown(f'<div class="peca-trinca">🔴 <b>{item["label"]}</b> — {status}<br><small>{r.get("observacao", "")}</small></div>', unsafe_allow_html=True)
                elif status == "OK":
                    st.markdown(f'<div class="peca-ok">✅ <b>{item["label"]}</b> — OK</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="peca-ok">🟡 <b>{item["label"]}</b> — {status}</div>', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**📋 Laudo Consolidado**")
            st.markdown(res["laudo"])

            st.markdown("---")
            if st.button("🆕 Fazer nova análise", type="primary"):
                st.session_state.resultado_analise = None
                st.rerun()


# ============================================================
# TELA DE ADMIN
# ============================================================
def tela_admin(perfil):
    st.title("🛡️ Painel do Administrador")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard",
        "📄 Histórico",
        "👥 Pendentes",
        "✅ Aprovados",
        "🏢 Filiais",
        "🔍 Análise"
    ])

    with tab1:
        aba_dashboard()
    with tab2:
        aba_historico()
    with tab3:
        aba_pendentes()
    with tab4:
        aba_aprovados()
    with tab5:
        aba_filiais()
    with tab6:
        tela_analise(perfil)


# ============================================================
# ROTEAMENTO PRINCIPAL
# ============================================================
if st.session_state.usuario is None:
    if st.session_state.tela == "login":
        tela_login()
    else:
        tela_cadastro()
else:
    perfil = buscar_perfil(st.session_state.usuario.id)

    if perfil is None:
        st.error("Perfil não encontrado. Contate o administrador.")
        if st.button("Sair"):
            fazer_logout()
    elif perfil["status"] == "pendente":
        tela_pendente(perfil)
    elif perfil["status"] == "rejeitado":
        st.error("🚫 Sua conta foi rejeitada. Contate o administrador.")
        if st.button("Sair"):
            fazer_logout()
    elif perfil["status"] == "aprovado":
        filial_nome_user = nome_filial(perfil.get("filial_id"))
        badge_icon = "🛡️" if perfil["role"] == "admin" else "👤"
        badge_txt = "Admin" if perfil["role"] == "admin" else "Usuário"

        col_a, col_b = st.columns([5, 1])
        with col_a:
            st.markdown(f"""
            <div class="barra-usuario">
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <div style="font-size: 1.5rem;">{badge_icon}</div>
                    <div>
                        <div style="font-weight: 600; color: #1e3a5f; font-size: 1.05rem;">
                            {perfil['username']}
                        </div>
                        <div style="color: #6b7280; font-size: 0.85rem;">
                            {badge_txt} • 🏢 {filial_nome_user}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_b:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Sair", use_container_width=True):
                fazer_logout()

        if perfil["role"] == "admin":
            tela_admin(perfil)
        else:
            tela_analise(perfil)
    else:
        st.error("Status desconhecido. Contate o administrador.")
        if st.button("Sair"):
            fazer_logout()
