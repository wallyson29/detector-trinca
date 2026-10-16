import streamlit as st
import cv2
import numpy as np
from PIL import Image
from google import genai

from config import (
    CHECKLIST_FOTOS,
    LIMIAR_NITIDEZ,
    LIMIAR_BRILHO_MIN,
    LIMIAR_BRILHO_MAX,
    RESOLUCAO_MIN_LARGURA,
    RESOLUCAO_MIN_ALTURA,
    DIAS_MINIMOS_ENTRE_ANALISES,
)
from db import (
    buscar_perfil, listar_filiais, nome_filial,
    buscar_ultima_analise_placa,
    salvar_analise_completa,
    fazer_upload_imagem,
)
from utils import (
    validar_placa, normalizar_placa, formatar_placa, dias_desde,
    validar_username, verificar_qualidade_foto,
)
from auth import (
    fazer_login, fazer_cadastro, fazer_logout, reautenticar_sessao,
)
from analise import (
    analisar_pecas_selecionadas, gerar_laudo_consolidado,
)
from pdf import gerar_pdf_analise
from admin import tela_admin


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
    .peca-erro { background: #fef3c7; padding: 1rem; border-radius: 8px; border-left: 4px solid #f59e0b; margin-bottom: 0.5rem; }
    .metricas-ok { color: #10b981; font-size: 0.75rem; font-weight: 600; }
    .metricas-ruim { color: #ef4444; font-size: 0.75rem; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)


aplicar_estilo()


# ========== ESTADO DA SESSÃO ==========
defaults = {
    "usuario": None,
    "tela": "login",
    "access_token": None,
    "refresh_token": None,
    "forcar_analise": False,
    "ver_laudo_anterior": None,
    "placa_validada": None,
    "ultima_analise_placa": None,
    "bloqueado_15dias": False,
    "analise_em_andamento": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Reautentica sessão
reautenticar_sessao()


# ========== FUNÇÕES DE UI ==========
def exibir_metricas(metricas):
    if not metricas:
        return
    nit_ok = "metricas-ok" if metricas.get("ok_nitidez") else "metricas-ruias"
    bri_ok = "metricas-ok" if metricas.get("ok_brilho") else "metricas-ruias"
    res_ok = "metricas-ok" if metricas.get("ok_resolucao") else "metricas-ruias"
    st.markdown(
        f'<span class="{nit_ok}">Nitidez: {metricas["nitidez"]:.0f}</span> • '
        f'<span class="{bri_ok}">Brilho: {metricas["brilho"]:.0f}</span> • '
        f'<span class="{res_ok}">Res: {metricas["resolucao"]}</span>',
        unsafe_allow_html=True
    )


# ========== TELAS ==========
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
                st.session_state.analise_em_andamento = None

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
                from admin import mostrar_fotos_analise
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
        st.caption(f"Todas as 9 fotos são obrigatórias. Critérios: nitidez ≥ {LIMIAR_NITIDEZ}, brilho entre {LIMIAR_BRILHO_MIN} e {LIMIAR_BRILHO_MAX}, resolução ≥ {RESOLUCAO_MIN_LARGURA}x{RESOLUCAO_MIN_ALTURA}.")

        if st.session_state.forcar_analise:
            st.warning("⚠️ Análise FORÇADA (fora do prazo de 15 dias)")

        pular_verificacao = False
        if perfil["role"] == "admin":
            pular_verificacao = st.checkbox(
                "🛡️ Admin: pular verificação de qualidade das fotos",
                value=False,
                key="pular_verificacao_admin"
            )
            if pular_verificacao:
                st.warning("⚠️ Verificação de qualidade DESATIVADA pelo admin.")

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
                        if pular_verificacao:
                            ok_q, msg_q, metricas_q = True, "✅ Verificação pulada (admin)", {}
                        else:
                            ok_q, msg_q, metricas_q = verificar_qualidade_foto(arquivo.getvalue())

                        fotos_qualidade[item["id"]] = {"ok": ok_q, "msg": msg_q, "metricas": metricas_q}

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
                            st.error(msg_q)
                            if metricas_q:
                                exibir_metricas(metricas_q)
                    else:
                        st.session_state[f"uploaded_{item['id']}"] = False

        st.markdown("---")
        st.markdown(f"**Progresso:** {total_ok}/9 fotos válidas")

        if total_ruim > 0:
            st.warning(f"⚠️ {total_ruim} foto(s) com qualidade ruim. Corrija antes de analisar.")

        with st.expander("📝 Observação (opcional)", expanded=False):
            st.caption("Use este campo para registrar qualquer anormalidade fora do checklist. Não passa pela IA.")
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

        # ========== ESTADO DE ANÁLISE ==========
        if total_ok == 9:
            st.markdown("---")

            if st.session_state.analise_em_andamento is None:
                if st.button("🔎 Analisar com IA", type="primary", use_container_width=True):
                    with st.spinner("Preparando análise..."):
                        try:
                            chave_gemini = st.secrets["GEMINI_API_KEY"]
                            client = genai.Client(api_key=chave_gemini)

                            foto_obs_url = None
                            if foto_obs:
                                bytes_obs = foto_obs.read()
                                arr_obs = np.frombuffer(bytes_obs, np.uint8)
                                img_obs = cv2.imdecode(arr_obs, cv2.IMREAD_COLOR)
                                foto_obs_url, _ = fazer_upload_imagem(img_obs, perfil["id"], "observacao")

                            fotos_brutas = {}
                            for item in CHECKLIST_FOTOS:
                                arquivo = fotos_upload.get(item["id"])
                                if arquivo:
                                    bytes_img = arquivo.read()
                                    img_array = np.frombuffer(bytes_img, np.uint8)
                                    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                    fotos_brutas[item["id"]] = img

                            pecas_para_analisar = [item for item in CHECKLIST_FOTOS if item["analisar"]]
                            resultados, fotos_urls, erros = analisar_pecas_selecionadas(
                                client, pecas_para_analisar, fotos_brutas, perfil
                            )

                            if "foto_placa" in fotos_brutas:
                                url_placa, _ = fazer_upload_imagem(fotos_brutas["foto_placa"], perfil["id"], "foto_placa")
                                fotos_urls["foto_placa"] = url_placa

                            st.session_state.analise_em_andamento = {
                                "resultados": resultados,
                                "fotos_urls": fotos_urls,
                                "erros": erros,
                                "fotos_brutas": fotos_brutas,
                                "foto_obs_url": foto_obs_url,
                                "texto_obs": texto_obs if texto_obs else None,
                            }
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro na análise: {e}")

            if st.session_state.analise_em_andamento:
                estado = st.session_state.analise_em_andamento
                resultados = estado["resultados"]
                fotos_urls = estado["fotos_urls"]
                erros = estado["erros"]
                fotos_brutas = estado["fotos_brutas"]
                foto_obs_url = estado["foto_obs_url"]
                texto_obs_salvo = estado["texto_obs"]

                st.markdown("---")
                st.subheader("📋 Resultado parcial da análise")

                for item in CHECKLIST_FOTOS:
                    if not item["analisar"]:
                        continue
                    r = resultados.get(item["id"])
                    if not r:
                        st.markdown(f'<div class="peca-erro">🟡 <b>{item["label"]}</b> — NÃO ANALISADA (erro)</div>', unsafe_allow_html=True)
                    elif r["status"].startswith("TRINCA"):
                        st.markdown(f'<div class="peca-trinca">🔴 <b>{item["label"]}</b> — {r["status"]}<br><small>{r.get("observacao", "")}</small></div>', unsafe_allow_html=True)
                    elif r["status"] == "OK":
                        st.markdown(f'<div class="peca-ok">✅ <b>{item["label"]}</b> — OK</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="peca-ok">🟡 <b>{item["label"]}</b> — {r["status"]}</div>', unsafe_allow_html=True)

                if erros:
                    st.markdown("---")
                    st.error(f"⚠️ **{len(erros)} peça(s) NÃO puderam ser analisadas.** O laudo só será concluído quando TODAS as peças forem analisadas com sucesso.")
                    st.markdown("**Peças com erro:**")
                    for item_erro in erros:
                        st.markdown(f"- 🔴 {item_erro['label']}")

                    st.markdown("---")
                    col_r1, col_r2 = st.columns([1, 1])
                    with col_r1:
                        if st.button("🔄 Reanalisar peças com erro", type="primary", use_container_width=True):
                            with st.spinner(f"Reanalisando {len(erros)} peça(s)..."):
                                try:
                                    chave_gemini = st.secrets["GEMINI_API_KEY"]
                                    client = genai.Client(api_key=chave_gemini)
                                    novos_resultados, novas_urls, novos_erros = analisar_pecas_selecionadas(
                                        client, erros, fotos_brutas, perfil, resultados_existentes=resultados
                                    )
                                    estado["resultados"] = novos_resultados
                                    estado["fotos_urls"].update(novas_urls)
                                    estado["erros"] = novos_erros
                                    st.session_state.analise_em_andamento = estado
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro na reanálise: {e}")

                    with col_r2:
                        if st.button("🗑️ Cancelar análise", use_container_width=True):
                            st.session_state.analise_em_andamento = None
                            st.rerun()

                else:
                    st.markdown("---")
                    st.success("✅ Todas as peças foram analisadas com sucesso!")

                    texto_laudo = gerar_laudo_consolidado(resultados, formatar_placa(st.session_state.placa_validada))

                    with st.spinner("💾 Salvando análise..."):
                        ok, erro = salvar_analise_completa(
                            perfil,
                            st.session_state.placa_validada,
                            resultados,
                            fotos_urls,
                            texto_laudo,
                            foto_observacao_url=foto_obs_url,
                            texto_observacao=texto_obs_salvo,
                            forcado=st.session_state.forcar_analise
                        )

                        if ok:
                            st.success("💾 Análise salva com sucesso!")
                            st.markdown("---")
                            st.markdown("**📋 Laudo Consolidado**")
                            st.markdown(texto_laudo)

                            ultima_salva = buscar_ultima_analise_placa(st.session_state.placa_validada)
                            if ultima_salva:
                                st.markdown("---")
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

                            st.session_state.analise_em_andamento = None
                            st.session_state.forcar_analise = False
                            st.session_state.placa_validada = None
                            st.session_state.ultima_analise_placa = None
                            st.session_state.bloqueado_15dias = False
                            st.session_state.ver_laudo_anterior = None

                            st.markdown("---")
                            if st.button("🆕 Fazer nova análise", type="secondary"):
                                st.rerun()
                        else:
                            st.error(f"Análise completa mas não foi possível salvar: {erro}")

        else:
            faltando = 9 - total_ok
            if faltando > 0:
                st.info(f"📸 Faltam **{faltando}** foto(s) válida(s) para liberar a análise.")


# ========== ROTEAMENTO PRINCIPAL ==========
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
            tela_admin(perfil, tela_analise)
        else:
            tela_analise(perfil)
    else:
        st.error("Status desconhecido. Contate o administrador.")
        if st.button("Sair"):
            fazer_logout()
