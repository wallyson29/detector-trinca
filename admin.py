import streamlit as st
from db import (
    listar_pendentes, listar_aprovados, atualizar_usuario,
    nome_filial, nome_usuario, listar_filiais,
    criar_filial, deletar_filial, contar_usuarios_filial,
    atualizar_usuario_filial, buscar_contadores, buscar_contadores_filial,
    buscar_historico,
)
from utils import normalizar_placa, formatar_placa
from pdf import gerar_pdf_analise
from config import CHECKLIST_FOTOS


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


def tela_admin(perfil, tela_analise_fn):
    """Painel completo do admin. Recebe a função tela_analise por parâmetro."""
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
        tela_analise_fn(perfil)
