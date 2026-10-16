# 🔍 Detector de Trinca

Sistema SaaS de inspeção visual com IA para detecção de trincas em conjuntos de engate de caminhões (pino-rei, quinta roda, chassi, para-lamas e porcas do berço).

Desenvolvido para transportadoras de combustível e carga pesada que precisam padronizar e documentar a inspeção periódica obrigatória.

---

## 📋 O que o sistema faz

- **Inspeção guiada de 9 fotos obrigatórias** — pino-rei 1ª carreta, pino-rei 2ª carreta, chassi/para-lamas direito e esquerdo (fora), chassi direito e esquerdo (dentro), porca do berço direita e esquerda, e foto da placa do caminhão
- **Verificação automática de qualidade das fotos** — bloqueia fotos desfocadas, escuras ou com resolução baixa
- **Análise por IA peça por peça** — cada peça é analisada individualmente pelo Gemini, retornando status (OK / TRINCA_LEVE / TRINCA_MODERADA / TRINCA_SEVERA)
- **Marcação visual da trinca** — a IA retorna coordenadas e o sistema desenha uma caixa vermelha na foto original
- **Laudo consolidado** — resumo com todas as peças, gravidade geral e recomendação
- **Bloqueio de 15 dias entre análises** — evita análise duplicada da mesma placa
- **Admin pode forçar análise** — com rastreabilidade (flag `forcado` no banco)
- **PDF exportável** — laudo completo com fotos, status por peça e observações
- **Dashboard de contadores** — total do dia, 7 dias, 30 dias, total geral e quebra por filial
- **Histórico filtrável** — por filial, placa e período
- **Multiusuário com filiais** — cada usuário vinculado a uma filial; admin gerencia tudo

---

## 🏗️ Arquitetura
detector-trinca/
├── app.py ← arquivo principal (roteamento e telas)
├── config.py ← constantes, checklist, limiares de qualidade
├── db.py ← funções de acesso ao Supabase
├── utils.py ← funções auxiliares (placa, username, qualidade de foto)
├── auth.py ← login, cadastro, logout, reautenticação
├── analise.py ← lógica de IA (análise por peça + retry automático)
├── admin.py ← painel admin (6 abas)
├── pdf.py ← geração de PDF (reportlab)
├── requirements.txt ← dependências Python
└── packages.txt ← dependências de sistema (libgl1)

text

### Stack

- **Frontend:** Streamlit
- **IA:** Google Gemini 3.5 Flash Lite (visão)
- **Banco:** Supabase (PostgreSQL + Auth + Storage)
- **PDF:** ReportLab
- **Imagem:** OpenCV, NumPy, Pillow
- **Hospedagem:** Streamlit Cloud

---

## 🔧 Instalação local

### Pré-requisitos

- Python 3.10 ou superior
- Conta no Supabase (free tier serve)
- Chave da API do Google Gemini

### Passos

1. **Clonar o repositório**
```bash
git clone https://github.com/SEU_USUARIO/detector-trinca.git
cd detector-trinca
Instalar dependências

bash
pip install -r requirements.txt
Criar arquivo de secrets
Crie .streamlit/secrets.toml na raiz:

toml
GEMINI_API_KEY = "sua_chave_aqui"
SUPABASE_URL = "https://seu-projeto.supabase.co"
SUPABASE_KEY = "sua_anon_key_aqui"
Configurar o banco no Supabase
Rode os SQLs de criação de tabelas, políticas RLS e funções RPC (ver DECISIONS.md para detalhes).

Rodar o app

bash
streamlit run app.py
O app abre em http://localhost:8501.

🗄️ Estrutura do banco
Tabelas
filiais

id (bigint, PK)

nome (text, único)

created_at (timestamptz)

profiles

id (uuid, PK, FK para auth.users)

username (text, único)

filial_id (bigint, FK para filiais)

status (text: pendente / aprovado / rejeitado)

role (text: user / admin)

created_at (timestamptz)

analises

id (bigint, PK)

user_id (uuid, FK)

filial_id (bigint, FK)

placa (text)

laudo (text)

tem_trinca (text)

gravidade (text)

recomendacao (text)

confianca (text)

forcado (boolean)

foto_pino_rei_1 ... foto_placa (text — URLs das 9 fotos)

status_pino_rei_1 ... status_porca_esq (text — status por peça)

foto_observacao (text — URL opcional)

texto_observacao (text — observação livre)

created_at (timestamptz)

Buckets
fotos (público)

Fotos das 9 peças + foto de observação

Caminho: {user_id}/{timestamp}_{nome_arquivo}.jpg

Funções RPC
ultima_analise_placa(p_placa) — retorna a análise mais recente da placa

historico_analises(...) — busca histórico com filtros

contadores_analises() — totais gerais

contadores_por_filial() — totais por filial

nome_usuario_por_id(p_id) — nome do usuário

nome_filial_por_id(p_id) — nome da filial

is_admin() — verifica se o usuário logado é admin

criar_filial(p_nome) — cria filial

deletar_filial(p_id) — deleta filial (só se não tiver usuários)

🚀 Deploy no Streamlit Cloud
Sobe o código pro GitHub

Acessa share.streamlit.io

Cria um novo app apontando pro app.py

Em Advanced settings → Secrets, cola:

toml
GEMINI_API_KEY = "sua_chave_aqui"
SUPABASE_URL = "https://seu-projeto.supabase.co"
SUPABASE_KEY = "sua_anon_key_aqui"
Deploy

O requirements.txt e o packages.txt são lidos automaticamente.

👥 Fluxo de uso
Usuário comum
Faz cadastro com username + senha + filial

Aguarda aprovação do admin

Após aprovado, faz login

Digita a placa do caminhão

Sobe as 9 fotos obrigatórias

Sistema valida qualidade das fotos

Clica em "Analisar com IA"

IA analisa peça por peça (~30s)

Baixa PDF do laudo

Admin
Além do fluxo comum:

Aprova/rejeita usuários pendentes

Promove/rebaixa admin

Bloqueia usuários

Cria/renomeia/deleta filiais

Vê dashboard com contadores

Acessa histórico completo com filtros

Pode forçar análise fora do prazo de 15 dias (com rastreabilidade)

Pode pular verificação de qualidade (se souber que a foto tá boa)

🔐 Segurança
Autenticação: Supabase Auth (senha criptografada, tokens JWT)

RLS (Row Level Security): cada usuário só vê suas próprias análises; admin vê tudo

Bucket público com policy restrita: fotos acessíveis por URL, mas não listáveis

Chaves de API: guardadas em st.secrets (nunca no código)

💰 Custos estimados
Serviço	Plano	Limite	Custo
Supabase	Free	500 MB banco + 1 GB storage	Grátis
Streamlit Cloud	Free	1 GB RAM	Grátis
Google Gemini	Free	~1500 req/dia	Grátis
Quando escalar (>100 análises/dia):

Supabase Pro: US$ 25/mês (8 GB banco + 100 GB storage)

Gemini pago: ~US$ 0,02 por análise
