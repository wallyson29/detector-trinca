import streamlit as st
from db import supabase
from utils import username_para_email


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


def fazer_logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def reautenticar_sessao():
    """Reautentica o token de sessão em cada rerun do Streamlit."""
    if st.session_state.get("access_token"):
        try:
            supabase.auth.set_session(
                st.session_state.access_token,
                st.session_state.refresh_token
            )
        except Exception:
            st.session_state.usuario = None
            st.session_state.access_token = None
            st.session_state.refresh_token = None
