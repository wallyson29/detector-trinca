# ========== CONFIGURAÇÕES GLOBAIS ==========

# Domínio fake para converter username em email (Supabase Auth exige email)
DOMINIO_FAKE = "@detector.local"

# Regra de negócio: dias mínimos entre análises da mesma placa
DIAS_MINIMOS_ENTRE_ANALISES = 15

# ========== LIMIARES DE QUALIDADE DE FOTO ==========
LIMIAR_NITIDEZ = 15
LIMIAR_BRILHO_MIN = 100
LIMIAR_BRILHO_MAX = 220
RESOLUCAO_MIN_LARGURA = 800
RESOLUCAO_MIN_ALTURA = 600
LIMIAR_DENSIDADE_BORDAS = 0.7   # mínimo de 1.5% de pixels de borda

# ========== CHECKLIST DE FOTOS ==========
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

# ========== MODELO DE IA ==========
MODELO_GEMINI = "gemini-3.5-flash-lite"
MAX_TENTATIVAS_IA = 3
ESPERA_ENTRE_TENTATIVAS = 5
