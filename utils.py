import cv2
import numpy as np
import re
from datetime import datetime, timezone
from config import (
    DOMINIO_FAKE,
    LIMIAR_NITIDEZ,
    LIMIAR_BRILHO_MIN,
    LIMIAR_BRILHO_MAX,
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
    try:
        arr = np.frombuffer(arquivo_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False, "Não foi possível ler a imagem", {}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = img.shape[:2]

        nitidezes = []
        for i in range(2):
            for j in range(2):
                q = gray[i*h//2:(i+1)*h//2, j*w//2:(j+1)*w//2]
                if q.size > 0:
                    nitidezes.append(cv2.Laplacian(q, cv2.CV_64F).var())
        nitidez = max(nitidezes) if nitidezes else 0

        brilho = float(np.mean(gray))

        problemas = []
        if nitidez < LIMIAR_NITIDEZ:
            problemas.append(f"foto desfocada (nitidez: {nitidez:.0f}, mínimo {LIMIAR_NITIDEZ})")
        if brilho < LIMIAR_BRILHO_MIN:
            problemas.append(f"foto muito escura (brilho: {brilho:.0f}, mínimo {LIMIAR_BRILHO_MIN})")
        elif brilho > LIMIAR_BRILHO_MAX:
            problemas.append(f"foto muito clara (brilho: {brilho:.0f}, máximo {LIMIAR_BRILHO_MAX})")
        if w < RESOLUCAO_MIN_LARGURA or h < RESOLUCAO_MIN_ALTURA:
            problemas.append(f"resolução baixa ({w}x{h})")

        metricas = {
            "nitidez": nitidez,
            "brilho": brilho,
            "resolucao": f"{w}x{h}",
            "ok_nitidez": nitidez >= LIMIAR_NITIDEZ,
            "ok_brilho": LIMIAR_BRILHO_MIN <= brilho <= LIMIAR_BRILHO_MAX,
            "ok_resolucao": w >= RESOLUCAO_MIN_LARGURA and h >= RESOLUCAO_MIN_ALTURA,
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
