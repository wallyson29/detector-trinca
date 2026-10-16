import streamlit as st
from supabase import create_client

# ========== CONEXÃO ==========
def get_supabase():
    """Retorna o cliente Supabase configurado com a sessão atual."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# Cliente global (usado em todo o app)
supabase = get_supabase()


# ========== PERFIL E USUÁRIOS ==========
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


# ========== FILIAIS ==========
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


# ========== ANÁLISES ==========
def buscar_ultima_analise_placa(placa):
    try:
        resposta = supabase.rpc("ultima_analise_placa", {"p_placa": placa}).execute()
        if resposta.data:
            return resposta.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao buscar última análise: {e}")
        return None


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


def salvar_analise_completa(perfil, placa, resultados, fotos_urls, texto_laudo,
                             foto_observacao_url=None, texto_observacao=None, forcado=False):
    """Salva uma análise completa no banco."""
    from utils import normalizar_placa, extrair_campos_laudo
    from config import CHECKLIST_FOTOS

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


# ========== STORAGE ==========
def fazer_upload_imagem(imagem_np, user_id, nome_arquivo):
    """Faz upload de uma imagem numpy no Supabase Storage."""
    import cv2
    from datetime import datetime

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
