import streamlit as st
import cv2
import numpy as np
from PIL import Image
import re
import io
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
    .main .block-container { max-width: 1100px; padding-top: 2rem; padding-bottom: 2rem; }
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
def fazer_login(email, senha):
    try:
        resposta = supabase.auth.sign_in_with_password({
            "email": email,
            "password": senha
        })
        st.session_state.access_token = resposta.session.access_token
        st.session_state.refresh_token = resposta.session.refresh_token
        return resposta.user, None
    except Exception as e:
        return None, str(e)


def fazer_cadastro(email, senha, username, filial_id):
    try:
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
        return False, str(e)


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

        elementos.append(Paragraph("🤖 Resultado da Análise por IA", estilo_sub))
        resultado_tabela = [
            ["Tem trinca?", analise.get("tem_trinca", "—")],
            ["Gravidade", analise.get("gravidade", "—")],
            ["Recomendação", analise.get("recomendacao", "—")],
            ["Confiança", analise.get("confianca", "—")],
        ]
        t2 = Table(resultado_tabela, colWidths=[5*cm, 10*cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3a5f')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        elementos.append(t2)
        elementos.append(Spacer(1, 15))

        url_img = analise.get("foto_marcada_url")
        if url_img:
            try:
                r = http_requests.get(url_img, timeout=10)
                if r.status_code == 200:
                    img_buffer = io.BytesIO(r.content)
                    elementos.append(Paragraph("📸 Imagem com marcação", estilo_sub))
                    img = RLImage(img_buffer, width=14*cm, height=10*cm, kind='proportional')
                    elementos.append(img)
                    elementos.append(Spacer(1, 15))
            except Exception:
                pass

        elementos.append(Paragraph("📝 Laudo Técnico Completo", estilo_sub))
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
# FUNÇÕES DE SALVAMENTO DE ANÁLISE
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


def extrair_campos_laudo(texto):
    campos = {"tem_trinca": None, "gravidade": None, "recomendacao": None, "confianca": None}

    match = re.search(r'TEM TRINCA\??\s*\**\s*(SIM|NÃO|NAO|NÃO SEI)', texto, re.IGNORECASE)
    if match:
        campos["tem_trinca"] = match.group(1).upper().replace("NAO", "NÃO")

    match = re.search(r'Gravidade[:\s]*\**\s*(LEVE|MODERADA|SEVERA)', texto, re.IGNORECASE)
    if match:
        campos["gravidade"] = match.group(1).upper()

    match = re.search(r'Recomenda[çc][ãa]o[:\s]*\**\s*(LIBERAR|INSPECIONAR|SUBSTITUIR)', texto, re.IGNORECASE)
    if match:
        campos["recomendacao"] = match.group(1).upper()

    match = re.search(r'Confian[çc]a[:\s]*\**\s*(ALTA|MÉDIA|MEDIA|BAIXA)', texto, re.IGNORECASE)
    if match:
        campos["confianca"] = match.group(1).upper().replace("MEDIA", "MÉDIA")

    return campos


def salvar_analise(perfil, placa, img_cinza, img_marcada_bgr, texto_laudo, forcado=False):
    try:
        user_id = perfil["id"]
        filial_id = perfil["filial_id"]

        url_original, erro1 = fazer_upload_imagem(img_cinza, user_id, "original")
        if erro1:
            return False, f"Erro no upload da original: {erro1}"

        url_marcada, erro2 = fazer_upload_imagem(img_marcada_bgr, user_id, "marcada")
        if erro2:
            return False, f"Erro no upload da marcada: {erro2}"

        campos = extrair_campos_laudo(texto_laudo)

        supabase.table("analises").insert({
            "user_id": user_id,
            "filial_id": filial_id,
            "placa": normalizar_placa(placa),
            "foto_original_url": url_original,
            "foto_marcada_url": url_marcada,
            "laudo": texto_laudo,
            "tem_trinca": campos["tem_trinca"],
            "gravidade": campos["gravidade"],
            "recomendacao": campos["recomendacao"],
            "confianca": campos["confianca"],
            "forcado": forcado,
        }).execute()

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
            email = st.text_input("📧 Email", key="login_email")
            senha = st.text_input("🔒 Senha", type="password", key="login_senha")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Entrar", type="primary", use_container_width=True):
                if not email or not senha:
                    st.warning("Preencha email e senha.")
                else:
                    user, erro = fazer_login(email, senha)
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
            email = st.text_input("📧 Email", key="cad_email")
            senha = st.text_input("🔒 Senha (mínimo 6 caracteres)", type="password", key="cad_senha")
            username = st.text_input("👤 Nome de usuário", key="cad_username")
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
                if not email or not senha or not username or not filial_id:
                    st.warning("Preencha todos os campos.")
                elif len(senha) < 6:
                    st.warning("A senha precisa ter pelo menos 6 caracteres.")
                else:
                    ok, erro = fazer_cadastro(email, senha, username, filial_id)
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
                col_d1, col_d2 = st.columns([1, 1])
                with col_d1:
                    st.markdown("**📸 Imagem com marcação**")
                    if a.get("foto_marcada_url"):
                        st.image(a["foto_marcada_url"], use_container_width=True)
                with col_d2:
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
# TELA DE ANÁLISE
# ============================================================
def tela_analise(perfil):
    st.title("🔍 Detector de Trinca")
    st.markdown("<p class='subtitulo'>Informe a placa e suba a foto para análise automática</p>", unsafe_allow_html=True)

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

        # ========== BOTÕES: VER LAUDO + BAIXAR PDF ==========
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
                col_l1, col_l2 = st.columns([1, 1])
                with col_l1:
                    st.markdown("**📸 Imagem com marcação**")
                    if u.get("foto_marcada_url"):
                        st.image(u["foto_marcada_url"], use_container_width=True)
                    else:
                        st.caption("Sem imagem salva")
                with col_l2:
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
        arquivo = st.file_uploader("📸 Escolha a foto do pino-rei ou quinta roda", type=["jpg", "jpeg", "png"])

        if arquivo is not None:
            bytes_img = arquivo.read()
            img_array = np.frombuffer(bytes_img, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            img_cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            img_clahe = clahe.apply(img_cinza)
            bordas = cv2.Canny(img_clahe, 50, 150)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.image(img_cinza, caption="Original (cinza)", use_container_width=True)
            with col2:
                st.image(img_clahe, caption="CLAHE (realce)", use_container_width=True)
            with col3:
                st.image(bordas, caption="Bordas (Canny)", use_container_width=True)

            if st.session_state.forcar_analise:
                st.warning("⚠️ Análise FORÇADA (fora do prazo de 15 dias)")

            if st.button("🔎 Analisar com IA", type="primary", use_container_width=True):
                with st.spinner("Analisando imagem..."):
                    client = genai.Client(api_key=CHAVE_GEMINI)
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

                        coords = None
                        match = re.search(r'COORDENADAS:\s*\[([\d,\s]+)\]', texto_laudo)
                        if match:
                            valores = [int(x.strip()) for x in match.group(1).split(',')]
                            if len(valores) == 4 and sum(valores) > 0:
                                coords = valores
                            texto_laudo = re.sub(r'COORDENADAS:\s*\[[\d,\s]+\]', '', texto_laudo).strip()

                        img_marcada_bgr = None

                        if coords:
                            y_min, x_min, y_max, x_max = coords
                            h, w = img_cinza.shape
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
                            img_marcada_bgr = img.copy()
                            cv2.rectangle(img_marcada_bgr, (x1, y1), (x2, y2), (0, 0, 255), 3)
                            cv2.putText(img_marcada_bgr, "TRINCA", (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                            img_marcada_rgb = cv2.cvtColor(img_marcada_bgr, cv2.COLOR_BGR2RGB)
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
                        with st.spinner("💾 Salvando análise..."):
                            if img_marcada_bgr is None:
                                img_marcada_bgr = img.copy()
                            ok, erro = salvar_analise(perfil, st.session_state.placa_validada, img_cinza, img_marcada_bgr, texto_laudo, forcado=st.session_state.forcar_analise)
                            if ok:
                                st.success("💾 Análise salva no histórico!")

                                # ========== BOTÃO PDF PÓS-ANÁLISE ==========
                                ultima_salva = buscar_ultima_analise_placa(st.session_state.placa_validada)
                                if ultima_salva:
                                    st.markdown("<br>", unsafe_allow_html=True)
                                    if st.button("📥 Baixar PDF deste laudo", type="primary", key="pdf_pos_analise"):
                                        with st.spinner("Gerando PDF..."):
                                            pdf_bytes, erro_pdf = gerar_pdf_analise(ultima_salva)
                                            if pdf_bytes:
                                                st.download_button(
                                                    label="💾 Clique para baixar o PDF",
                                                    data=pdf_bytes,
                                                    file_name=f"laudo_{normalizar_placa(ultima_salva['placa'])}_{ultima_salva['id']}.pdf",
                                                    mime="application/pdf",
                                                    key="dl_pos_analise"
                                                )
                                            else:
                                                st.error(f"Erro ao gerar PDF: {erro_pdf}")

                                st.session_state.forcar_analise = False
                                st.session_state.placa_validada = None
                                st.session_state.ultima_analise_placa = None
                                st.session_state.bloqueado_15dias = False
                                st.session_state.ver_laudo_anterior = None
                            else:
                                st.warning(f"Análise gerada mas não foi possível salvar: {erro}")
                        st.markdown("---")
                    except Exception as e:
                        st.error(f"Erro ao analisar: {e}")


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
