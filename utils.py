import cv2
import numpy as np
import re
from datetime import datetime, timezone
from config import (
    DOMINIO_FAKE,
    LIMIAR_NITIDEZ,
    LIMIAR_BRILHO_MIN,
    LIMIAR_BRILHO_MAX,
    LIMIAR_DENSIDADE_BORDAS,
    RESOLUCAO_MIN_LARGURA,
    RESOLUCAO_MIN_ALTURA,
)


# ========== USERNAME ==========
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


# ========== PLACA ==========
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


# ========== DATAS ==========
def dias_desde(data_iso):
    try:
        dt = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
        agora = datetime.now(timezone.utc)
        delta = agora - dt
        return delta.days
    except Exception:
        return 999


# ========== QUALIDADE DA FOTO ==========
def verificar_qualidade_foto(arquivo_bytes):
    """
    Verifica qualidade da foto.
    Usa 2 métricas combinadas: variância do Laplaciano + densidade de bordas Canny.
    """
    try:
        arr = np.frombuffer(arquivo_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False, "Não foi possível ler a imagem", {}

        h_original, w_original = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Métrica 1: nitidez
        nitidez = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Métrica 2: densidade de bordas
        bordas = cv2.Canny(gray, 50, 150)
        densidade_bordas = np.count_nonzero(bordas) / (h_original * w_original) * 100

        brilho = float(np.mean(gray))

        # Critério: passa se nitidez OU densidade atender
        foto_boa = (nitidez >= LIMIAR_NITIDEZ) or (densidade_bordas >= LIMIAR_DENSIDADE_BORDAS)

        problemas = []
        if not foto_boa:
            problemas.append(f"foto desfocada (nitidez: {nitidez:.0f}, bordas: {densidade_bordas:.2f}%)")
        if brilho < LIMIAR_BRILHO_MIN:
            problemas.append(f"foto muito escura (brilho: {brilho:.0f}, mínimo {LIMIAR_BRILHO_MIN})")
        elif brilho > LIMIAR_BRILHO_MAX:
            problemas.append(f"foto muito clara (brilho: {brilho:.0f}, máximo {LIMIAR_BRILHO_MAX})")
        if w_original < RESOLUCAO_MIN_LARGURA or h_original < RESOLUCAO_MIN_ALTURA:
            problemas.append(f"resolução baixa ({w_original}x{h_original})")

        metricas = {
            "nitidez": nitidez,
            "densidade_bordas": densidade_bordas,
            "brilho": brilho,
            "resolucao": f"{w_original}x{h_original}",
            "ok_nitidez": foto_boa,
            "ok_brilho": LIMIAR_BRILHO_MIN <= brilho <= LIMIAR_BRILHO_MAX,
            "ok_resolucao": w_original >= RESOLUCAO_MIN_LARGURA and h_original >= RESOLUCAO_MIN_ALTURA,
        }

        if problemas:
            return False, "❌ " + " • ".join(problemas), metricas

        return True, "✅ Foto OK", metricas
    except Exception as e:
        return False, f"Erro ao verificar: {e}", {}


# ========== EXTRAÇÃO DE CAMPOS DO LAUDO ==========
def extrair_campos_laudo(texto):
    campos = {"tem_trinca": None, "gravidade": None, "recomendacao": None, "confianca": None}

    match = re.search(r'TEM TRINCA\??\s*\**\s*(SIM|NÃO|NAO|NÃO SEI)', texto, re.IGNORECASE)
    if match:
        campos["tem_trinca"] = match.group(1).upper().replace("NAO", "NÃO")

    match = re.search(r'Gravidade geral[:\s]*\**\s*(LEVE|MODERADA|SEVERA)', texto, re.IGNORECASE)
    if match:
        campos["gravidade"] = match.group(1).upper()

    match = re.search(r'Recomenda[çc][ãa]o[:\s]*\**\s*(LIBERAR|INSPECIONAR|SUBSTITUIR)', texto, re.IGNORECASE)
    if match:
        campos["recomendacao"] = match.group(1).upper()

    match = re.search(r'Confian[çc]a[:\s]*\**\s*(ALTA|MÉDIA|MEDIA|BAIXA)', texto, re.IGNORECASE)
    if match:
        campos["confianca"] = match.group(1).upper().replace("MEDIA", "MÉDIA")

    return campos
