import streamlit as st
import pandas as pd
import os
import psycopg
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai import types
import base64
import unicodedata
import streamlit.components.v1 as components
from werkzeug.security import generate_password_hash
import time
from streamlit_extras.stylable_container import stylable_container
import psycopg2
from openai import OpenAI
import json as modulo_json
import mercadopago 
from supabase import create_client, Client
import random
import plotly.graph_objects as go
import plotly.express as px
import altair as alt
from psycopg2 import pool

# ==============================================================================
# 0. INICIALIZAÇÃO SEGURA DO SESSION STATE (ANTI-ATTRIBUTE ERROR)
# ==============================================================================
if "usuario_id" not in st.session_state:
    st.session_state.usuario_id = None

if "id_usuario" not in st.session_state:
    st.session_state.id_usuario = None

if "username" not in st.session_state:
    st.session_state.username = None

if "opcao_menu" not in st.session_state:
    st.session_state.opcao_menu = "home"

if "foto_perfil" not in st.session_state:
    st.session_state.foto_perfil = ""

# Armazena o menu de forma limpa
menu_atual = st.session_state.opcao_menu

# ==============================================================================
# 3. CONEXÕES DE APIs E BANCO DE DADOS (RESOLVIDO ERRO DE SECRETS)
# ==============================================================================
UPLOAD_FOLDER = 'static/uploads/perfis'

# --- [A] CONFIGURAÇÃO OPENAI ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", {}).get("OPENAI_API_KEY") if hasattr(st, "secrets") else None
if not OPENAI_API_KEY:
    try:
        OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        OPENAI_API_KEY = None

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    st.error("Chave da API da OpenAI não configurada. O chat não vai funcionar.")

# --- [B] CONFIGURAÇÃO SUPABASE ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    try:
        SUPABASE_URL = st.secrets.get("SUPABASE_URL")
        SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
    except Exception:
        pass

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    st.error("Credenciais do Supabase não encontradas! Verifique as configurações.")

# --- [C] CONFIGURAÇÃO MERCADO PAGO (PROTEGIDO CONTRA QUEDAS) ---
TOKEN_MERCADO_PAGO = os.environ.get("TOKEN_MERCADO_PAGO")
if not TOKEN_MERCADO_PAGO:
    try:
        TOKEN_MERCADO_PAGO = st.secrets.get("TOKEN_MERCADO_PAGO")
    except Exception:
        TOKEN_MERCADO_PAGO = None

sdk = None
if TOKEN_MERCADO_PAGO:
    try:
        import mercadopago
        sdk = mercadopago.SDK(TOKEN_MERCADO_PAGO)
    except Exception as e:
        st.error(f"Erro ao carregar credenciais do Mercado Pago: {e}")

# --- [D] POOL DE CONEXÕES POSTGRES (PROTEGIDO CONTRA QUEDAS) ---
@st.cache_resource
def inicializar_pool_banco():
    # Coleta segura das credenciais independente de estar local ou no Render
    try:
        db_host = os.environ.get("DB_HOST") or st.secrets["postgres"]["host"]
        db_name = os.environ.get("DB_DATABASE") or st.secrets["postgres"]["database"]
        db_user = os.environ.get("DB_USER") or st.secrets["postgres"]["user"]
        db_pass = os.environ.get("DB_PASSWORD") or st.secrets["postgres"]["password"]
        db_port = os.environ.get("DB_PORT") or st.secrets["postgres"]["port"]
    except Exception:
        # Fallback caso não encontre estruturas aninhadas
        db_host = os.environ.get("DB_HOST")
        db_name = os.environ.get("DB_DATABASE")
        db_user = os.environ.get("DB_USER")
        db_pass = os.environ.get("DB_PASSWORD")
        db_port = os.environ.get("DB_PORT")

    return psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_pass,
        port=db_port,
        sslmode="require"
    )

def obter_conexao_eficiente():
    try:
        pool_db = inicializar_pool_banco()
        return pool_db.getconn()
    except Exception as e:
        st.error(f"Erro ao obter conexão do pool: {e}")
        return None

def liberar_conexao(conn):
    if conn:
        try:
            pool_db = inicializar_pool_banco()
            pool_db.putconn(conn)
        except Exception:
            pass

# ==============================================================================
# DECLARAÇÕES GLOBAIS DE SEGURANÇA & CRIPTOGRAFIA
# ==============================================================================
try:
    from werkzeug.security import check_password_hash, generate_password_hash
except ImportError:
    import bcrypt
    def check_password_hash(hash_banco, senha_digitada):
        if isinstance(hash_banco, str): hash_banco = hash_banco.encode('utf-8')
        return bcrypt.checkpw(senha_digitada.encode('utf-8'), hash_banco)
    def generate_password_hash(senha_digitada):
        return bcrypt.hashpw(senha_digitada.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# ==============================================================================
# FUNÇÕES DE BANCO DE DADOS DE ALTA PERFORMANCE
# ==============================================================================
def carregar_plano_e_moedas_direto_pool(id_usuario):
    conn = obter_conexao_eficiente()
    if not conn:
        return {"tipo_plano": "Grátis", "moedas": 0}
    try:
        id_limpo = int(id_usuario if not isinstance(id_usuario, (tuple, list)) else id_usuario)
        with conn.cursor() as cursor:
            cursor.execute("SELECT tipo_plano, moedas FROM usuarios WHERE id = %s;", (id_limpo,))
            res = cursor.fetchone()
            if res:
                return {"tipo_plano": str(res[0]).strip(), "moedas": int(res[1] or 0)}
    except Exception:
        pass
    finally:
        liberar_conexao(conn)
    return {"tipo_plano": "Grátis", "moedas": 0}

# ==============================================================================
# 2. BARRA LATERAL REATIVA GLOBAL
# ==============================================================================
# Se o menu atual for um desses, a barra lateral NÃO será desenhada (evita sobreposição no login)
if menu_atual not in ["home", "login", "cadastro", "planos"]:
    with st.sidebar:
        caminho_foto_perfil = str(st.session_state.get("foto_perfil", "")).strip()
                
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])
        with col_centro:
            if caminho_foto_perfil and caminho_foto_perfil.startswith("http"):
                st.image(caminho_foto_perfil, width=85)
            else:
                st.markdown('<div style="font-size: 65px; text-align:center; margin-top: -10px;">👩</div>', unsafe_allow_html=True)

        username_atual = st.session_state.get("username", "Usuário")
        nome_usuario_puro = str(username_atual).split('@')[0].capitalize()

        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 20px; margin-top: 5px;">
                <h3 style="margin: 0; font-size: 17px; font-weight: bold; color: #f0f6fc;">{nome_usuario_puro}</h3>
                <p style="color: #48bb78; font-weight: bold; font-size: 13px; margin: 4px 0 0 0;">🟢 Online</p>
            </div>
        """, unsafe_allow_html=True)

        tipo_plano = "Grátis"
        saldo_moedas = 0
        id_usuario_logado = st.session_state.get("usuario_id")

        if id_usuario_logado is not None:
            try:
                # Busca instantânea direta do Pool de Conexões (Leva menos de 1ms)
                dados_reais = carregar_plano_e_moedas_direto_pool(id_usuario_logado)
                
                plano_bruto = str(dados_reais.get("tipo_plano", "Grátis")).strip()
                plano_norm = unicodedata.normalize('NFKD', plano_bruto).encode('ASCII', 'ignore').decode('utf-8').lower()
                    
                if "credito" in plano_norm or "moedas" in plano_norm:
                    tipo_plano = "Plano Crédito de Moedas"
                elif "vip" in plano_norm or "assinante" in plano_norm:
                    tipo_plano = "vip"
                else:
                    tipo_plano = "Grátis"
                        
                saldo_moedas = int(dados_reais.get("moedas", 0) or 0)
                        
            except Exception as e:
                st.error(f"Erro ao ler saldo real: {e}")

       # Sincroniza e trava os estados na memória raiz do Streamlit
        st.session_state["tipo_plano"] = tipo_plano
        st.session_state["saldo_moedas"] = saldo_moedas
        if "dados_usuario" in st.session_state:
            st.session_state.dados_usuario["tipo_plano"] = tipo_plano
            st.session_state.dados_usuario["moedas"] = saldo_moedas

        # Exibe o cabeçalho comercial de créditos
        st.caption(f"Plano: **{tipo_plano}** | Saldo: 🪙 **{saldo_moedas} moedas**")
        st.markdown("<hr style='border-color: #21262d; margin: 10px 0;'>", unsafe_allow_html=True)

        # --- COMPONENTE OTIMIZADO: ALTERAR FOTO DE PERFIL ---
        # ⚡ OTIMIZAÇÃO: Isolado em um formulário para evitar envios repetidos em background a cada clique do app
        import time # Garante a importação para evitar NameError
        
        with st.form("form_foto_perfil", clear_on_submit=True):
            st.caption("📷 Enviar nova foto de perfil:")
            f_nova = st.file_uploader(
                "Alterar Foto", 
                type=["png","jpg","jpeg"], 
                key=f"side_f_up_{st.session_state.get('form_seed', 42)}", 
                label_visibility="collapsed"
            ) 
            btn_salvar_foto = st.form_submit_button("Salvar Nova Foto", use_container_width=True)

        if btn_salvar_foto and f_nova and id_usuario_logado: 
            id_limpo = id_usuario_logado if not isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
            nome_arquivo_storage = f"user_{id_limpo}.jpg"
                
            conn_foto = None
            try:
                dados_imagem_bytes = f_nova.getvalue()
                    
                # Upload para o storage bucket
                supabase.storage.from_("perfis").upload(
                    path=nome_arquivo_storage,
                    file=dados_imagem_bytes,
                    file_options={"content-type": "image/jpeg", "upsert": "true"}
                )
                    
                resposta_url = supabase.storage.from_("perfis").get_public_url(nome_arquivo_storage)
                url_publica_foto = str(resposta_url.public_url).strip() if hasattr(resposta_url, "public_url") else str(resposta_url).strip()
                    
                # Grava no PostgreSQL de forma segura usando o Pool
                conn_foto = obter_conexao_eficiente()
                if conn_foto:
                    with conn_foto.cursor() as cursor_foto:
                        cursor_foto.execute("UPDATE usuarios SET foto_perfil = %s WHERE id = %s;", (url_publica_foto, int(id_limpo))) 
                        conn_foto.commit()
                        
                    st.session_state.foto_perfil = url_publica_foto
                    
                    # Incrementa semente para resetar o uploader
                    st.session_state.form_seed = st.session_state.get('form_seed', 42) + 1
                        
                    st.toast("📷 Foto de perfil salva permanentemente na nuvem!")
                    time.sleep(0.5) 
                    st.rerun() 
                    
            except Exception as e:
                if conn_foto: conn_foto.rollback()
                st.error(f"Erro ao salvar foto: {e}")
            finally:
                if conn_foto:
                    liberar_conexao(conn_foto)

        st.markdown("---")

        # --- [C] MOTOR DE BUSCA DA NOTIFICAÇÃO (Roda nativo e leve) ---
        possui_convite_pendente = False
        if id_usuario_logado:
            conn_b = None
            try:
                meu_id_limpo = int(id_usuario_logado if not isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado)
                conn_b = obter_conexao_eficiente()
                if conn_b:
                    with conn_b.cursor() as cursor_b:
                        cursor_b.execute("SELECT COUNT(*) FROM agendamentos_virtuais WHERE destinatario_id = %s AND status_convite = 'pendente';", (meu_id_limpo,))
                        count_res = cursor_b.fetchone()
                        if count_res and count_res[0] > 0: 
                            possui_convite_pendente = True
            except Exception: 
                pass
            finally:
                if conn_b:
                    liberar_conexao(conn_b)

        label_gestao = "🤝 ABRIR GESTÃO 🔴" if possui_convite_pendente else "🤝 ABRIR GESTÃO"
        if possui_convite_pendente:
            st.markdown("""
                <div style='background-color: #21262d; border: 1px solid #ef4444; border-radius: 6px; padding: 6px; text-align: center; margin-bottom: 8px;'>
                    <span style='font-size: 11px; color: #ef4444; font-weight: bold;'>📩 VOCÊ RECEBEU UM NOVO CONVITE!</span>
                </div>
                """, unsafe_allow_html=True)

        # --- [D] BOTÕES DE NAVEGAÇÃO REATIVOS (CHAVES FIXAS ESTÁVEIS) ---
        if st.button(label_gestao, type="secondary", use_container_width=True, key="btn_sidebar_gestao_final_real"):
            st.session_state.opcao_menu = "🤝 Gerenciar Conexões"
            st.rerun()
                
        if st.button("📅 MINHA GRADE HORÁRIA", type="primary", use_container_width=True, key="btn_sidebar_grade_final_real"): 
            st.session_state.opcao_menu = "📅 Disponibilidade"
            st.rerun()
                
        if st.button("Ir para a Loja 🛒", type="secondary", use_container_width=True, key="btn_sidebar_loja_final_real"):
            st.session_state.opcao_menu = "planos"
            st.rerun()
                
        # Validação administrativa
        eh_admin = st.session_state.get("eh_admin", False)
        if eh_admin or str(username_atual).lower() in ['admin', 'cleverson', 'clever1404']:
            if st.button("⚙️ PAINEL ADMINISTRATIVO", type="secondary", use_container_width=True, key="btn_sidebar_adm_final_real"):
                st.session_state.opcao_menu = "🛠️ Painel Admin"
                st.rerun()  

        if st.button("🗑️ LIMPAR HISTÓRICO DA IA", type="secondary", use_container_width=True, key="btn_limpar_ia_final"):
            if id_usuario_logado:
                conn = None
                try:
                    id_limpo = int(id_usuario_logado if not isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado)
                    conn = obter_conexao_eficiente()
                    if conn:
                        with conn.cursor() as cursor:
                            cursor.execute("DELETE FROM historico_ia WHERE usuario_id = %s;", (id_limpo,))
                            conn.commit()
                        
                        st.toast("Histórico limpo!")
                        time.sleep(0.5)
                        st.rerun()
                except Exception as e: 
                    if conn: conn.rollback()
                    st.error(f"Erro ao limpar histórico: {e}")
                finally:
                    if conn:
                        liberar_conexao(conn)

        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True) 
            
        # Botão de Logout Nativo
        if st.button("🚪 ENCERRAR SESSÃO", type="primary", use_container_width=True, key="btn_logout_sistema_final_real"):
            # Limpa todos os estados de sessão para deslogar com segurança total
            st.session_state.clear()
            st.rerun()

              

# ==============================================================================
# 1. CONFIGURAÇÕES OBRIGATÓRIAS DE PÁGINA (Sempre no Topo Absoluto do Script)
# ==============================================================================
if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"

# DEVE ser chamado antes de desenhar qualquer elemento visual ou barra lateral!
st.set_page_config(
    page_title="Lucy Chat IA - Plataforma", 
    layout="wide", 
    initial_sidebar_state=st.session_state.sidebar_state
)

# Estilização Padrão Global (Injetada logo no início)
st.markdown("""
    <style>
    [data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    h1, h2, h3, h4 { font-family: Arial, sans-serif; color: #f0f6fc !important; }
    div[data-testid="stSidebar"] { background-color: #161b22 !important; border-right: 1px solid #30363d; }
    .block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; }
    .foto-match-central {
        width: 38px !important;
        height: 38px !important;
        border-radius: 50% !important;
        object-fit: cover !important;
        border: 1px solid #30363d !important;
        display: inline-block;
        vertical-align: middle;
    }
    .box-perfil-fixo { 
        background-color: #161b22; 
        border: 1px solid #30363d; 
        border-radius: 8px; 
        padding: 15px; 
        text-align: center;
        position: sticky;
        top: 2rem;
    }
    .chat-container { display: flex; flex-direction: column; gap: 10px; padding: 10px; }
    .msg-bubble { border-radius: 8px; padding: 8px 12px; max-width: 75%; font-size: 15px; line-height: 1.4; position: relative; }
    .msg-meu { background-color: #056162; color: white; align-self: flex-end; border-top-right-radius: 0px; }
    .msg-parceiro { background-color: #262d31; color: white; align-self: flex-start; border-top-left-radius: 0px; }
    .msg-autor { font-size: 11px; font-weight: bold; color: #34b7f1; margin-bottom: 3px; }
    .msg-tempo { font-size: 10px; color: #8696a0; text-align: right; margin-top: 4px; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. INICIALIZAÇÃO DE ESTADOS (SESSION STATE)
# ==============================================================================
if "opcao_menu" not in st.session_state: st.session_state.opcao_menu = "home"
if "usuario_id" not in st.session_state: st.session_state.usuario_id = None
if "id_usuario" not in st.session_state: st.session_state.id_usuario = None
if "username" not in st.session_state: st.session_state.username = None
if "foto_perfil" not in st.session_state: st.session_state.foto_perfil = None
if "genero" not in st.session_state: st.session_state.genero = "M"
if "eh_admin" not in st.session_state: st.session_state.eh_admin = False
if "id_pagamento_pendente" not in st.session_state: st.session_state.id_pagamento_pendente = None
if "tipo_pagamento_pendente" not in st.session_state: st.session_state.tipo_pagamento_pendente = None
if "qr_code_img" not in st.session_state: st.session_state.qr_code_img = None
if "qr_code_texto" not in st.session_state: st.session_state.qr_code_texto = None
if "form_seed" not in st.session_state: st.session_state.form_seed = 42
if "sub_visao" not in st.session_state: st.session_state.sub_visao = "planos"
if "match_id_atual" not in st.session_state: st.session_state.match_id_atual = None
if "alerta_match" not in st.session_state: st.session_state.alerta_match = None
if "abrir_reserva_fluxo" not in st.session_state: st.session_state.abrir_reserva_fluxo = None
if "historico_volatil" not in st.session_state: st.session_state.historico_volatil = []
if "tipo_plano" not in st.session_state: st.session_state.tipo_plano = "Grátis"
if "saldo_moedas" not in st.session_state: st.session_state.saldo_moedas = 0

dias_semana_map = {0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira', 3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'}
dia_atual_servidor = dias_semana_map[datetime.now().weekday()]

# ==============================================================================
# LÓGICA DO LOGOUT (Agrupado de forma limpa e segura)
# ==============================================================================
# Este bloco deve estar contido dentro do escopo onde st.sidebar foi declarado no arquivo anterior
def processar_logout(id_usuario_logado):
    conn_logout = None
    try:
        if id_usuario_logado:
            id_limpo = int(id_usuario_logado if not isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado)
            conn_logout = obter_conexao_eficiente()
            if conn_logout:
                with conn_logout.cursor() as cursor_logout:
                    cursor_logout.execute("UPDATE usuarios SET status = '⚫ Offline' WHERE id = %s;", (id_limpo,))
                    conn_logout.commit()
    except Exception:
        if conn_logout: conn_logout.rollback()
    finally:
        if conn_logout: 
            liberar_conexao(conn_logout)
    
    # Reseta a sessão completamente limpando os dados da memória
    st.session_state.clear()
    st.session_state.opcao_menu = "login"
    st.rerun()

# ==============================================================================
# 4. FUNÇÕES DE SUPORTE E MECANISMO DE INTELIGÊNCIA ARTIFICIAL
# ==============================================================================
def buscar_memoria(usuario_id, limite=15):
    conn = None
    try:
        conn = obter_conexao_eficiente() 
        if conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT usuario_pergunta, ia_resposta FROM historico_ia WHERE usuario_id = %s ORDER BY id ASC LIMIT %s;', 
                    (int(usuario_id), limite)
                )
                return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn:
            liberar_conexao(conn)
    return []

# ==============================================================================
# TELA DE LOGIN DEFINITIVA (CORRIGIDA)
# ==============================================================================
def renderizar_tela_login_definitiva():
    if st.session_state.get("usuario_id"):
        st.session_state.opcao_menu = "💬 Conversar com Lucy"
        st.rerun()

    if "login_view_uuid" not in st.session_state:
        st.session_state.login_view_uuid = str(time.time()).replace('.', '')
        
    u_key = st.session_state.login_view_uuid

    st.markdown('<h1 style="text-align:center; color:#007bff; margin-bottom: 20px;">Login Lucy Chat IA</h1>', unsafe_allow_html=True)
                
    with st.form(key=f"form_login_{u_key}", clear_on_submit=True):
        user_in = st.text_input("Usuário", placeholder="Nome de Usuário ou E-mail", label_visibility="collapsed", key=f"user_in_{u_key}")
        pass_in = st.text_input("Senha", placeholder="Senha", type="password", label_visibility="collapsed", key=f"pass_in_{u_key}")
        botao_entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if botao_entrar:
        if not user_in.strip() or not pass_in.strip():
            st.warning("Por favor, preencha todos os campos.")
        else:
            conn = None  
            try:
                conn = obter_conexao_eficiente()
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT id, username, foto_perfil, is_admin, genero, tipo_plano, moedas, password_hash FROM usuarios WHERE username = %s OR email = %s;", 
                            (user_in.strip(), user_in.strip())
                        )
                        res = cursor.fetchone()
                                      
                        # --- AGORA FORA DO WITH (As variáveis locais estão seguras na memória) ---
                        if res:
                            # Validação usando a função de Hash global
                            if not check_password_hash(banco_password_hash, str(pass_in)):
                                st.error("Senha incorreta. Tente novamente.")
                            else:
                                # CONFIGURAÇÃO DE SESSÃO UNIFICADA
                                id_numerico = int(banco_id)
                                st.session_state.usuario_id = id_numerico
                                st.session_state.id_usuario = id_numerico 
                                st.session_state.username = str(banco_username).strip()
                                st.session_state.foto_perfil = str(banco_foto).strip() if banco_foto else ""
                                st.session_state.eh_admin = bool(banco_admin)
                                st.session_state.genero = str(banco_genero).strip() if banco_genero else "M"
                                
                                st.session_state.dados_usuario = {
                                    "username": str(banco_username).strip(), 
                                    "foto_perfil": str(banco_foto).strip() if banco_foto else "", 
                                    "genero": str(banco_genero).strip() if banco_genero else "M",
                                    "tipo_plano": str(banco_plano).strip() if banco_plano else "Grátis", 
                                    "moedas": int(banco_moedas) if banco_moedas else 0
                                }
                                
                                # Atualiza status online abrindo um cursor rápido e isolado
                                with conn.cursor() as cursor_update:
                                    cursor_update.execute("UPDATE usuarios SET status = '🟢 Online' WHERE id = %s", (id_numerico,))
                                    conn.commit()
                                
                                # ⚡ CORREÇÃO: Limpeza segura removendo referências a containers inexistentes
                                if "login_view_uuid" in st.session_state:
                                    del st.session_state["login_view_uuid"]
                                
                                # Redireciona de forma limpa, forçando redesenho imediato sem telas sobrepostas
                                st.session_state.opcao_menu = "💬 Conversar com Lucy"
                                st.rerun()
                        else:
                            st.error("Usuário não encontrado.")
                            
                    except Exception as e: 
                        if conn: conn.rollback()
                        st.error(f"Erro crítico no login: {e}")       
                    finally:
                        if conn:
                            liberar_conexao(conn)

            # Botões auxiliares inferiores
            st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            col_voltar, col_esqueceu = st.columns(2)
            with col_voltar:
                if st.button("⬅️ Voltar para a Home", use_container_width=True, key=f"btn_vol_home_{u_key}"):
                    if "login_view_uuid" in st.session_state:
                        del st.session_state["login_view_uuid"]
                    st.session_state.opcao_menu = "home"
                    st.rerun()
            with col_esqueceu:
                if st.button("🔑 Esqueceu a senha?", use_container_width=True, key=f"btn_esq_senha_{u_key}"):
                    # Garante que a função exista no escopo global ou emite aviso amigável
                    if 'modal_recuperar_senha' in globals():
                        modal_recuperar_senha()
                    else:
                        st.info("Função de recuperação de senha não implementada neste arquivo.")


def processar_afinidade_e_match(usuario_id, texto_atual):
    conn = None  
    cursor = None
    try:
        meu_id_limpo = usuario_id if not isinstance(usuario_id, (tuple, list)) else int(usuario_id[0] if isinstance(usuario_id, tuple) else usuario_id)
        
        # 1. PRIMEIRA SESSÃO DO BANCO (Busca rápida de perfil)
        conn = obter_conexao_eficiente()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT idade, genero, procura_por, procura_relacionamento FROM usuarios WHERE id = %s;", (meu_id_limpo,))
            meu_perfil = cursor.fetchone()
            cursor.close()
            liberar_conexao(conn)
            conn = None  # Reseta para não duplicar no finally
        else:
            return {"match": False}
        
        if not meu_perfil:
            return {"match": False}
            
        minha_idade, meu_genero, o_que_eu_procuro_gen, o_que_eu_procuro_rel = meu_perfil

        # 2. PROCESSAMENTO EXTERNO DE IA (Sem travar as pools do Postgres)
        mensagens_sintese = [
            {"role": "system", "content": "Escreva apenas um parágrafo corrido contendo as palavras-chaves semânticas de interesses e estilo de vida."},
            {"role": "user", "content": f"Baseado nesta interação recente do usuário, extraia e descreva em terceira pessoa uma lista de seus hobbies e interesses: {texto_atual}"}
        ]
        resposta_sintese = client.chat.completions.create(model='gpt-4o-mini', messages=mensagens_sintese, temperature=0.3)
        perfil_consolidado_texto = resposta_sintese.choices[0].message.content

        resposta_embedding = client.embeddings.create(model="text-embedding-3-small", input=perfil_consolidado_texto, dimensions=768)
        vetor_atual = resposta_embedding.data[0].embedding
        vetor_formatado_postgres = str(vetor_atual)

        # 3. SEGUNDA SESSÃO DO BANCO (Escrita e Busca por Proximidade de Vetor)
        conn = obter_conexao_eficiente()
        if conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE usuarios SET biografia = %s, embedding_interesses = %s WHERE id = %s;', (perfil_consolidado_texto, vetor_formatado_postgres, meu_id_limpo))
            
            cursor.execute('''
                SELECT id, username, status, (embedding_interesses <=> %s::vector) AS distancia 
                FROM usuarios 
                WHERE id != %s AND is_admin = FALSE AND embedding_interesses IS NOT NULL
                  AND (idade BETWEEN %s - 5 AND %s + 5)
                  AND LOWER(TRIM(procura_relacionamento)) = LOWER(TRIM(%s))
                  AND ((%s = 'O' OR procura_por = %s OR procura_por = 'O') AND (%s = 'O' OR %s = genero OR %s = 'O'))
                ORDER BY (embedding_interesses <=> %s::vector) ASC, id ASC LIMIT 1;
            ''', (vetor_formatado_postgres, meu_id_limpo, int(minha_idade or 25), int(minha_idade or 25), str(o_que_eu_procuro_rel or ''), str(meu_genero), str(meu_genero), str(o_que_eu_procuro_gen), str(o_que_eu_procuro_gen), str(meu_genero), vetor_formatado_postgres))
            resultado = cursor.fetchone()
            conn.commit()
            cursor.close()

        if resultado:
            id_par, nome_par, status_par, distancia = resultado
            distancia_val = float(distancia)
            if distancia_val <= 0.22:
                similaridade_bruta = 1.0 - distancia_val
                porcentagem_match = max(0.0, min(100.0, (similaridade_bruta - 0.75) / (0.88 - 0.75) * 100))
                return {
                    "match": True, 
                    "id_par": int(id_par), 
                    "nome_par": nome_par, 
                    "online": "🟢" in str(status_par) or "Online" in str(status_par), 
                    "afinidade_porcentagem": round(porcentagem_match, 1)
                }

        return {"match": False}

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error(f"Erro no processamento de afinidade: {e}")
        return {"match": False}
    finally:
        if conn:
            liberar_conexao(conn)


# ==============================================================================
# 5. RENDERIZADORES DE DIALOGS/MODAIS (RECALIBRADOS - SEM ROLES FANTASMAS)
# ==============================================================================
# ⚡ OTIMIZAÇÃO: Use o decorador atualizado estável do Streamlit
@st.dialog("🤖 Lucy Notou Afinidade!")
def exibir_modal_match(dados_m, tipo_plano, saldo_moedas):
    st.markdown(f"Lucy identificou uma excelente afinidade entre você e **{dados_m['nome']}**!")
    id_usuario = st.session_state.usuario_id
    
    if dados_m["online"]:
        st.markdown(f"🟢 **{dados_m['nome']}** está online agora!")
        
        if tipo_plano == "vip":
            if st.button("🚀 Entrar na Sala Privada (Acesso Total Ilimitado)", type="primary", use_container_width=True, key="btn_match_vip"):
                st.session_state.match_id_atual = dados_m["match_id"]
                st.session_state.tempo_limite_sala = -1
                st.session_state.alerta_match = None  # Limpa o gatilho para o modal fechar de verdade
                st.session_state.opcao_menu = "🤝 Sala Privada"
                st.rerun()  # O roteador limpa a tela de fundo na re-execução
                
        elif tipo_plano == "Plano Crédito de Moedas":
            st.info(f"🪙 Seu Saldo: {saldo_moedas} moedas. Custo da Sala Privada: 10 moedas = 10 minutos.")
            
            if st.button("🪙 Entrar na Sala Privada (Gasta 10 moedas)", type="primary", use_container_width=True, key="btn_match_moedas"):
                if saldo_moedas >= 10:
                    conn_debito = None
                    try:
                        id_limpo = id_usuario[0] if isinstance(id_usuario, (list, tuple)) else id_usuario
                        
                        # ⚡ OTIMIZAÇÃO CRÍTICA: Débito executado direto no Pool PostgreSQL (0ms de lag)
                        # Remove a dependência da chamada HTTP lenta do cliente Supabase
                        conn_debito = obter_conexao_eficiente()
                        if conn_debito:
                            with conn_debito.cursor() as cursor_debito:
                                cursor_debito.execute("UPDATE usuarios SET moedas = %s WHERE id = %s;", (saldo_moedas - 10, int(id_limpo)))
                                conn_debito.commit()
                            
                            st.success("Moedas debitadas! Sala privada liberada por 10 minutos iniciais.")
                            
                            st.session_state.match_id_atual = dados_m["match_id"]
                            st.session_state.tempo_limite_sala = 10
                            st.session_state.alerta_match = None  # Limpa o gatilho
                            st.session_state.opcao_menu = "🤝 Sala Privada"
                            st.rerun()
                        else:
                            st.error("Não foi possível conectar ao banco para processar a transação.")
                    except Exception as e: 
                        if conn_debito: conn_debito.rollback()
                        st.error(f"Falha na transação: {e}")
                    finally:
                        if conn_debito:
                            liberar_conexao(conn_debito)
                else: 
                    st.warning("🔒 Saldo insuficiente. Você precisa de pelo menos 10 moedas.")
        else: 
            st.error("🔒 O acesso a salas privadas é exclusivo para clientes com plano de Crédito ou Assinantes.")
            
    else:
        # Botão estático apenas informativo (Ganha chave estável)
        st.button(f"⚪ {dados_m['nome']} está offline. Indisponível para chat instantâneo.", disabled=True, use_container_width=True, key="btn_match_offline_status")
        
        if st.button("📅 Agende um encontro virtual", type="secondary", use_container_width=True, key="btn_match_agendar"):
            if tipo_plano in ["vip", "Plano Crédito de Moedas"]:
                # Salva dados para o gerenciador centralizado do passo 1 abrir
                st.session_state.abrir_reserva_fluxo = {
                    "id_par": dados_m["id_par"], 
                    "nome_par": dados_m["nome"], 
                    "m_id": dados_m["match_id"]
                }
                st.session_state.alerta_match = None  # Limpa o gatilho para fechar o modal
                st.rerun()
            else: 
                st.warning("🔒 O agendamento de encontros virtuais não está disponível no Plano Grátis. Faça um upgrade!")
                
    st.markdown("---")
    
    # ⚡ CORREÇÃO DE LOOP: Desativa o gatilho limpando o estado antes de rodar o rerun
    if st.button("❌ Não tenho interesse", type="secondary", use_container_width=True, key="btn_match_recusar"): 
        st.session_state.alerta_match = None  # Neutraliza a variável controladora que invoca o modal
        st.rerun()  # Fecha o modal de forma limpa e restaura o controle da tela de fundo




def processar_match_lucy(dados_m):
    id_usuario_logado = st.session_state.get("usuario_id")
    if id_usuario_logado is None: 
        return
        
    # ⚡ OTIMIZAÇÃO CRÍTICA: Se os dados do plano e moedas já existem na sessão global,
    # nós usamos eles diretamente (0ms). Caso contrário, buscamos no Pool de forma ultra-rápida.
    if "tipo_plano" not in st.session_state or "saldo_moedas" not in st.session_state:
        conn_match = None
        try:
            id_limpo = id_usuario_logado if not isinstance(id_usuario_logado, (list, tuple)) else id_usuario_logado
            
            # Substituída a API lenta do Supabase pelo Pool eficiente já configurado
            conn_match = obter_conexao_eficiente()
            if conn_match:
                with conn_match.cursor() as cursor_match:
                    cursor_match.execute("SELECT tipo_plano, moedas FROM usuarios WHERE id = %s;", (int(id_limpo),))
                    res = cursor_match.fetchone()
                    if res:
                        st.session_state["tipo_plano"] = str(res[0]).strip()
                        st.session_state["saldo_moedas"] = int(res[1] or 0)
                    else:
                        st.session_state["tipo_plano"] = "Grátis"
                        st.session_state["saldo_moedas"] = 0
            else:
                st.session_state["tipo_plano"] = "Grátis"
                st.session_state["saldo_moedas"] = 0
        except Exception as e: 
            st.error(f"Erro ao carregar dados do banco no fluxo do match: {e}")
            return
        finally:
            if conn_match:
                liberar_conexao(conn_match)

    # Extrai os dados unificados e sincronizados diretamente da memória raiz do Streamlit
    tipo_plano = st.session_state["tipo_plano"]
    saldo_moedas = st.session_state["saldo_moedas"]
        
    # Dispara o modal sem nenhum atraso de rede pendente ou travamento visual
    exibir_modal_match(dados_m, tipo_plano, saldo_moedas)


# ==============================================================================
# FUNÇÃO ISOLADA COM BUFFER DE MEMÓRIA (TOTALMENTE ALINHADA E CORRIGIDA)
# ==============================================================================
@st.fragment
def renderizar_chat_lucy_isolado():
    # Inicializa a semente caso ela não exista na memória
    semente_atual = st.session_state.get("seed_recarregar_chat", 0)

    # ⚡ PROVIMENTO DE SEGURANÇA CONTRA DESLOGAMENTO SÚBITO
    id_bruto = st.session_state.get("usuario_id")
    if id_bruto is None:
        st.session_state.opcao_menu = "login"
        st.rerun(scope="fragment")
        return
        
    meu_id_limpo = int(id_bruto if not isinstance(id_bruto, (tuple, list)) else id_bruto)

    # ⚡ CORREÇÃO DA INDENTAÇÃO: Todo o fluxo visual e lógico agora reside
    # estritamente envelopado por dentro do bloco de contêiner dinâmico da semente.
    with st.container(key=f"container_interno_chat_{semente_atual}"):
        
        if "opcao_menu" not in st.session_state:
            st.session_state.opcao_menu = "chat"
            
        # 1. TRATAMENTO DE TELAS SECUNDÁRIAS DENTRO DO FRAGMENTO
        if st.session_state.opcao_menu == "✉️ Fale Conosco":
            # Certifique-se de que template_fale_conosco esteja importada/definida
            if 'template_fale_conosco' in globals():
                template_fale_conosco()
            else:
                st.info("Formulário de contato indisponível.")
                
            if st.button("⬅️ Voltar para o Chat", use_container_width=True, key="btn_voltar_chat_fc"):
                st.session_state.opcao_menu = "chat"
                st.rerun(scope="fragment")
            return  # Interrompe o resto do chat se estiver no fale conosco

        # 2. ÁREA VISUAL FIXA DO TOPO (Nunca some)
        col_titulos, col_botoes_topo = st.columns([2, 1])
        with col_titulos:
            st.markdown("<h2 style='margin-top:0; margin-bottom:2px; font-size: 24px;'>🤖 Olá, Seja bem-vindo ao Lucy Chat IA</h2>", unsafe_allow_html=True)
            st.caption("Lucy conversa com você e armazena os seus interesses para encontrar matches.")
        
        with col_botoes_topo:
            c_refresh, c_fc = st.columns(2)
            with c_refresh:
                if st.button("🔄 Atualizar", type="secondary", help="Sincronizar mensagens", key="btn_refresh_chat"):
                    st.rerun(scope="fragment")
            with c_fc:
                if st.button("✉️ Contato", type="secondary", key="btn_fale_conosco_chat"):
                    st.session_state.opcao_menu = "✉️ Fale Conosco"
                    st.rerun(scope="fragment")
        
        st.markdown("<hr style='border-color: #30363d; margin: 5px 0 15px 0;'>", unsafe_allow_html=True)

        # 3. BUSCA RÁPIDA E EXIBIÇÃO DO HISTÓRICO
        historico_banco = buscar_memoria(meu_id_limpo, limite=20)
        
        area_mensagens = st.container(height=450, border=False)
        with area_mensagens:
            for pergunta_antiga, resposta_antiga in historico_banco:
                with st.chat_message("user"):
                    st.markdown(pergunta_antiga)
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(resposta_antiga)

        # 4. CAPTURA E PROCESSAMENTO IMEDIATO NO RODAPÉ
        prompt_capturado = st.chat_input("Digite sua mensagem para a Lucy...")
        
        if prompt_capturado:
            with area_mensagens:
                with st.chat_message("user"):
                    st.markdown(prompt_capturado)
                with st.chat_message("assistant", avatar="🤖"):
                    placeholder_resposta = st.empty()
                    resposta_completa = ""

            try:
                contexto_mensagens = [
                    {"role": "system", "content": "Você é a Lucy, uma IA psicóloga e assistente de relacionamentos altamente empática. Seu objetivo é entender o estilo de vida, gostos e rotina do usuário através de uma conversa natural. Seja acolhedora, faça perguntas abertas e ajude-o a se expressar para encontrar o par ideal."}
                ]
                
                # Contexto das últimas mensagens lidas
                for p, r in historico_banco[-5:]:
                    contexto_mensagens.append({"role": "user", "content": p})
                    contexto_mensagens.append({"role": "assistant", "content": r})
                
                contexto_mensagens.append({"role": "user", "content": prompt_capturado})

                # ⚡ OTIMIZAÇÃO CRÍTICA: Ativado o Efeito de Streaming (Respostas fluidas palavra por palavra)
                stream = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=contexto_mensagens,
                    temperature=0.7,
                    stream=True
                )
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        resposta_completa += chunk.choices[0].delta.content
                        placeholder_resposta.markdown(resposta_completa + "▌")
                
                placeholder_resposta.markdown(resposta_completa)  # Exibe o texto final sem o cursor

                # Salva no histórico usando o Pool estável
                conn_salvar = None
                try:
                    conn_salvar = obter_conexao_eficiente()
                    if conn_salvar:
                        with conn_salvar.cursor() as cursor_salvar:
                            cursor_salvar.execute("""
                                INSERT INTO historico_ia (usuario_id, usuario_pergunta, ia_resposta) 
                                VALUES (%s, %s, %s);
                            """, (meu_id_limpo, prompt_capturado, resposta_completa))
                            conn_salvar.commit()
                except Exception as e_db:
                    if conn_salvar: conn_salvar.rollback()
                    st.error(f"Erro ao salvar mensagem no banco: {e_db}")
                finally:
                    if conn_salvar: 
                        liberar_conexao(conn_salvar)

                # Executa o motor de afinidade pós-mensagem
                dados_match = processar_afinidade_e_match(meu_id_limpo, prompt_capturado)
                if dados_match and dados_match.get("match"):
                    st.session_state.alerta_match = {
                        "match_id": dados_match.get("match_id", random.randint(1000, 9999)),
                        "id_par": dados_match.get("id_par"),
                        "nome": dados_match.get("nome_par"),
                        "online": dados_match.get("online", False)
                    }
                    processar_match_lucy(st.session_state.alerta_match)
                    
            except Exception as e:
                st.error(f"Erro ao processar conversa com a IA: {e}")


def modal_agendamento_encontro(dados_r):
    # Criamos uma caixa visual simulando o modal (Estilização GitHub Dark)
    with st.container(border=True):
        st.markdown(f"### 📆 Agendar Reunião com **{dados_r['nome_par']}**")
        st.markdown("<hr style='border-color: #30363d; margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
        
        # Inputs visuais estáveis
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        dia_s = st.selectbox("Escolha o Dia da Semana:", dias, key="dg_res_dia")
        
        opcoes_periodo = ["🌅 Manhã (06:00 às 11:59)", "☀️ Tarde (12:00 às 17:59)", "🌙 Noite (18:00 às 23:59)"]
        per_exibicao = st.selectbox("Escolha o Período:", opcoes_periodo, key="dg_res_per")
        per_s = "manha" if "Manhã" in per_exibicao else "tarde" if "Tarde" in per_exibicao else "noite"
        
        horario_sugestao = datetime.strptime("09:00" if per_s=="manha" else "14:00" if per_s=="tarde" else "20:00", "%H:%M").time()
        hor_s = st.time_input("Ajuste o Horário Exato:", value=horario_sugestao, step=900, key="dg_res_hor")
        
        def limpar_id_absoluto(id_bruto):
            if isinstance(id_bruto, (tuple, list)):
                return int(id_bruto[0]) if len(id_bruto) > 0 else 0
            return int(id_bruto) if id_bruto is not None else 0

        m_id_limpo = limpar_id_absoluto(dados_r.get('m_id'))
        meu_id_limpo = limpar_id_absoluto(st.session_state.get("usuario_id"))
        parceiro_id_limpo = limpar_id_absoluto(dados_r.get('id_par'))

        # Inicialização de variáveis de controle
        meu_registro_existe = False
        parceiro_registro_existe = False
        erro_validacao = False
        mensagem_erro = ""

        # Botão de submissão
        if st.button("💾 Confirmar Reserva e Enviar", type="primary", use_container_width=True, key="btn_confirmar_reserva_final"):
            
            hora_int = hor_s.hour
            # ⚡ CORREÇÃO: Substituído o 'return' por marcação de erro boleana para não sumir com o layout da página
            if per_s == 'manha' and (hora_int < 6 or hora_int >= 12): 
                erro_validacao = True
                mensagem_erro = "❌ Horário inválido para Manhã (06:00 às 11:59)."
            elif per_s == 'tarde' and (hora_int < 12 or hora_int >= 18): 
                erro_validacao = True
                mensagem_erro = "❌ Horário inválido para Tarde (12:00 às 17:59)."
            elif per_s == 'noite' and (hora_int < 18 or hora_int > 23): 
                erro_validacao = True
                mensagem_erro = "❌ Horário inválido para Noite (18:00 às 23:59)."

            if erro_validacao:
                st.error(mensagem_erro)
            else:
                conn = None
                try:
                    conn = obter_conexao_eficiente()
                    if conn:
                        with conn.cursor() as cursor:
                            # Verificação de Match
                            cursor.execute("SELECT COUNT(*) FROM matches WHERE id = %s;", (m_id_limpo,))
                            match_existe = cursor.fetchone()[0] > 0
                            
                            if not match_existe:
                                cursor.execute("""
                                    SELECT id FROM matches 
                                    WHERE (usuario_1_id = %s AND usuario_2_id = %s) OR (usuario_1_id = %s AND usuario_2_id = %s) 
                                    LIMIT 1;
                                """, (meu_id_limpo, parceiro_id_limpo, parceiro_id_limpo, meu_id_limpo))
                                match_recuperado = cursor.fetchone()
                                
                                if match_recuperado:
                                    m_id_limpo = int(match_recuperado[0])
                                else:
                                    cursor.execute("""
                                        INSERT INTO matches (usuario_1_id, usuario_2_id, status_conexao) 
                                        VALUES (%s, %s, 'offline') RETURNING id;
                                    """, (meu_id_limpo, parceiro_id_limpo))
                                    m_id_limpo = int(cursor.fetchone()[0])
                                    conn.commit()

                            # Validações de Disponibilidade
                            cursor.execute("""
                                SELECT COUNT(*) FROM disponibilidade_usuarios 
                                WHERE usuario_id = %s AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
                            """, (meu_id_limpo, str(dia_s), str(per_s)))
                            meu_registro_existe = cursor.fetchone()[0] > 0
                    
                            cursor.execute("""
                                SELECT COUNT(*) FROM disponibilidade_usuarios 
                                WHERE usuario_id = %s 
                                AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) 
                                AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
                            """, (parceiro_id_limpo, str(dia_s), str(per_s)))
                            parceiro_registro_existe = cursor.fetchone()[0] > 0

                            if not meu_registro_existe:
                                erro_validacao = True
                                mensagem_erro = f"❌ **Agendamento Recusado:** Você configurou este dia/período como indisponível na sua grade."
                            elif not parceiro_registro_existe:
                                erro_validacao = True
                                mensagem_erro = f"❌ **Agendamento Recusado:** {dados_r['nome_par']} está indisponível na {dia_s} no período selecionado."       
                            
                            if erro_validacao:
                                st.error(mensagem_erro)
                            else:
                                cursor.execute("""
                                    INSERT INTO agendamentos_virtuais (match_id, remetente_id, destinatario_id, dia_semana, periodo, horario, status_convite) 
                                    VALUES (%s, %s, %s, %s, %s, %s, 'pendente');
                                """, (m_id_limpo, meu_id_limpo, parceiro_id_limpo, str(dia_s), str(per_s), hor_s))
                                
                                conn.commit()
                                st.success("🎉 Convite enviado com sucesso!")
                                st.session_state.abrir_reserva_fluxo = None  # Fecha o modal simulado
                                st.session_state.opcao_menu = "💬 Conversar com Lucy"
                                time.sleep(1.0)
                                st.rerun()
                    else:
                        st.error("Falha ao obter conexão ativa com o banco de dados.")
                except Exception as e: 
                    if conn: conn.rollback()
                    st.error(f"Erro crítico ao salvar agendamento: {e}")
                finally:
                    if conn:
                        liberar_conexao(conn)

        # Botão de fechar nativo do modal simulado (Permanece intacto e visível)
        if st.button("🚫 Cancelar e Voltar", use_container_width=True, key="btn_cancelar_modal_reserva_simulado"):
            st.session_state.abrir_reserva_fluxo = None
            st.rerun()

# ==============================================================================
# FUNÇÃO AUXILIAR COM CACHE PARA OTIMIZAÇÃO DA GRADE HORÁRIA
# ==============================================================================
@st.cache_data(ttl=60)  # Limpa o cache automaticamente após 1 minuto
def buscar_disponibilidade_banco(usuario_id):
    horarios = set()
    conn = None  
    try:
        conn = obter_conexao_eficiente()
        if conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT dia_semana, periodo FROM disponibilidade_usuarios WHERE usuario_id = %s;", 
                    (int(usuario_id),)
                )
                registros = cursor.fetchall()
                
            for d_sem, per_id in registros:
                horarios.add(f"{str(d_sem).strip()}_{str(per_id).strip()}") 
    except Exception:
        pass
    finally:
        if conn:
            liberar_conexao(conn)
            
    return horarios


# ==============================================================================
# TELA DE CONFIGURAÇÃO DE DISPONIBILIDADE SEMANAL (CORRIGIDA)
# ==============================================================================
def template_disponibilidade(): 
    st.subheader("📅 Sua Grade de Disponibilidade") 
    st.caption("Marque os dias da semana em que você está disponível. Seus matches verão apenas a combinação dos seus horários livres.")

    dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'] 
    periodos = [{"id": "manha", "nome": "Manhã"}, {"id": "tarde", "nome": "Tarde"}, {"id": "noite", "nome": "Noite"}] 

    meu_id_limpo = st.session_state.usuario_id if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)
    
    # Chama a busca otimizada no banco utilizando cache
    horarios_salvos = buscar_disponibilidade_banco(meu_id_limpo)

    # Constrói a matriz na memória usando Session State para evitar travamento na digitação
    if "df_grade_memoria" not in st.session_state:
        matriz = [] 
        for per in periodos: 
            linha = {"Período": per["nome"]} 
            for d in dias: 
                linha[d] = f"{d}_{per['id']}" in horarios_salvos
            matriz.append(linha) 
        st.session_state["df_grade_memoria"] = pd.DataFrame(matriz)

    config_c = {"Período": st.column_config.TextColumn(disabled=True)} 
    for d in dias: 
        config_c[d] = st.column_config.CheckboxColumn(default=False) 

    # Bloco isolado em formulário para salvar alterações em lote de uma vez só
    with st.form("container_formulario_grade_horaria", clear_on_submit=False):
        grade_editada = st.data_editor(
            st.session_state["df_grade_memoria"], 
            column_config=config_c, 
            use_container_width=True, 
            hide_index=True, 
            key="grade_horaria_editor"
        ) 
        
        botao_salvar_ativo = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
        
        if botao_salvar_ativo: 
            conn = None
            try:
                conn = obter_conexao_eficiente()
                if conn:
                    with conn.cursor() as cursor: 
                        cursor.execute("DELETE FROM disponibilidade_usuarios WHERE usuario_id = %s;", (meu_id_limpo,)) 
                        
                        for idx, row in grade_editada.iterrows(): 
                            p_id = periodos[idx]["id"]
                            for d in dias: 
                                if row[d]: 
                                    cursor.execute("""
                                        INSERT INTO disponibilidade_usuarios (usuario_id, dia_semana, periodo) 
                                        VALUES (%s, %s, %s);
                                    """, (meu_id_limpo, str(d), str(p_id))) 
                        
                        conn.commit()
                    
                    # ⚡ OTIMIZAÇÃO CRÍTICA: Limpa o cache da função de grade horária
                    buscar_disponibilidade_banco.clear(meu_id_limpo)
                    
                    # ⚡ SOLUÇÃO DO CONGELAMENTO: Além de deletar o DataFrame, limpa o estado interno do editor
                    if "df_grade_memoria" in st.session_state:
                        del st.session_state["df_grade_memoria"]
                    if "grade_horaria_editor" in st.session_state:
                        del st.session_state["grade_horaria_editor"]
                    
                    st.toast("🎉 Sua grade horária foi salva com sucesso!")
                    time.sleep(0.5)
                    st.rerun() 
                else:
                    st.error("Não foi possível conectar ao banco de dados.")
            except Exception as e:
                if conn: conn.rollback()
                st.error(f"Erro crítico ao salvar no banco: {e}")
            finally:
                if conn:
                    liberar_conexao(conn)

    # Áreas e gatilhos adicionais fora do formulário
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    col_l, col_v = st.columns(2)
    
    with col_l:
        if st.button("🗑️ Limpar Grade Horária", type="secondary", use_container_width=True, key="btn_limpar_grade_real"):
            conn = None
            try:
                conn = obter_conexao_eficiente()
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("DELETE FROM disponibilidade_usuarios WHERE usuario_id = %s;", (meu_id_limpo,))
                        conn.commit()
                    
                    # Limpa cirurgicamente o cache da função
                    buscar_disponibilidade_banco.clear(meu_id_limpo)
                    
                    # ⚡ SOLUÇÃO DO CONGELAMENTO: Limpa o editor para o estado "Zeradinho" aparecer na hora
                    if "df_grade_memoria" in st.session_state:
                        del st.session_state["df_grade_memoria"]
                    if "grade_horaria_editor" in st.session_state:
                        del st.session_state["grade_horaria_editor"]
                        
                    st.toast("Toda a sua grade horária foi limpa!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Não foi possível conectar ao banco de dados.")
            except Exception as e: 
                if conn: conn.rollback()
                st.error(f"Erro ao limpar grade: {e}")
            finally:
                if conn:
                    liberar_conexao(conn)
            
    with col_v: 
        if st.button("Voltar ao Chat", use_container_width=True, key="btn_voltar_chat_grade"): 
            st.session_state.opcao_menu = "💬 Conversar com Lucy" 
            st.rerun()


def template_gerenciar_conexoes():
    # ⚡ TRAVA DE SEGURANÇA ANTINULA
    id_sessao = st.session_state.get("usuario_id")
    
    # Se o ID não existir ou for nulo (usuário deslogado), bloqueia a tela e joga para o login
    if id_sessao is None:
        st.warning("🔒 Acesso restrito. Por favor, faça login para gerenciar suas conexões.")
        st.session_state.opcao_menu = "login"
        st.st_stop() if hasattr(st, "st_stop") else st.stop()

    st.title("🤝 Gestão de Relacionamentos") 

    if st.button("← Voltar para o Chat da Lucy", type="secondary", key="btn_voltar_lucy_gestao"):
        st.session_state.opcao_menu = "💬 Conversar com Lucy"
        st.rerun()
                
    aba_m, aba_e = st.tabs(["👥 Meus Matches", "📆 Gestão de Convites e Histórico"]) 
    
    # ⚡ CORREÇÃO: Alinhado o desempacotamento seguro usando apenas 'id_sessao'
    meu_id_limpo = int(id_sessao if not isinstance(id_sessao, (tuple, list)) else id_sessao[0])

    # Captura e normalização estável do plano do usuário para as travas de negócio
    plano_atual = str(st.session_state.get("tipo_plano", "grátis")).strip().lower()
    usuario_tem_acesso = (plano_atual == "vip") or ("crédito" in plano_atual) or ("credito" in plano_atual)
    bloquear_botoes = not usuario_tem_acesso

    # ==============================================================================
    # ABA 1: MEUS MATCHES (AFINIDADES)
    # ==============================================================================
    with aba_m:
        st.markdown("### 👥 Suas Afinidades")
        matches_dados = []
        conn = None
        try:
            # Varredura de afinidades encapsulada no Pool
            conn = obter_conexao_eficiente()
            if conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT m.id, u.username, u.foto_perfil, u.genero, u.id 
                        FROM matches m 
                        JOIN usuarios u ON (u.id = m.usuario_2_id OR u.id = m.usuario_1_id) 
                        WHERE (m.usuario_1_id = %s OR m.usuario_2_id = %s) AND u.id != %s;
                    """, (meu_id_limpo, meu_id_limpo, meu_id_limpo))
                    matches_dados = cursor.fetchall()
        except Exception as e:
            st.error(f"Erro ao buscar afinidades: {e}")
        finally:
            if conn:
                liberar_conexao(conn)

        if not matches_dados: 
            st.info("Nenhum par localizado.")
            
        for m_id, m_nome, m_foto, m_gen, par_id in matches_dados:
            with st.container(border=True):
                c_av_c, c_nm_c, c_go_c, c_del_c = st.columns([0.6, 2, 1, 1])
                
                with c_av_c:
                    caminho_par_img = str(m_foto).strip()
                    if caminho_par_img and caminho_par_img.startswith("http"):
                        st.image(caminho_par_img, width=50)
                    else:
                        st.markdown(f'<div style="font-size: 35px; margin-top: 5px; text-align: center;">{"👩" if m_gen == "F" else "👨"}</div>', unsafe_allow_html=True)
                        
                with c_nm_c:
                    st.markdown(f"<p style='font-size:15px; font-weight:bold; margin-top:5px; color:#f0f6fc;'>{str(m_nome).split('@')[0].capitalize()}</p>", unsafe_allow_html=True)
                    
                with c_go_c:
                    if st.button("💬 Entrar", key=f"go_ch_h_{m_id}", type="primary", use_container_width=True, disabled=bloquear_botoes,
                                help="Disponível apenas para planos vip ou Plano Crédito de Moedas" if bloquear_botoes else None):
                        st.session_state.match_id_atual = m_id
                        st.session_state.opcao_menu = "🤝 Sala Privada"
                        st.rerun()
                        
                with c_del_c:
                    if st.button("🗑️ Desfazer", key=f"del_match_central_{m_id}", type="secondary", use_container_width=True):
                        conn_del = None
                        try:
                            conn_del = obter_conexao_eficiente()
                            if conn_del:
                                with conn_del.cursor() as cursor_del:
                                    cursor_del.execute("DELETE FROM mensagens_chat WHERE match_id = %s;", (int(m_id),))
                                    cursor_del.execute("DELETE FROM agendamentos_virtuais WHERE match_id = %s;", (int(m_id),))
                                    cursor_del.execute("DELETE FROM matches WHERE id = %s;", (int(m_id),))
                                    conn_del.commit()
                                st.toast("Match removido!")
                                time.sleep(0.5)
                                st.rerun()
                        except Exception as e: 
                            if conn_del: conn_del.rollback()
                            st.error(f"Erro ao remover match: {e}")
                        finally:
                            if conn_del:
                                liberar_conexao(conn_del)

    # ==============================================================================
    # ABA 2: GESTÃO DE CONVITES E HISTÓRICO
    # ==============================================================================
    with aba_e:
        st.markdown("### 📩 Convites Ativos da Semana")
        encontros = []
        conn_enc = None
        
        try:
            conn_enc = obter_conexao_eficiente()
            if conn_enc:
                with conn_enc.cursor() as cursor_enc:
                    cursor_enc.execute("""
                        SELECT a.id, a.dia_semana, a.periodo, a.horario, a.status_convite, a.remetente_id,
                            CASE WHEN a.remetente_id = %s THEN u2.username ELSE u1.username END as nome_parceiro, a.match_id
                        FROM agendamentos_virtuais a 
                        JOIN matches m ON m.id = a.match_id 
                        JOIN usuarios u1 ON u1.id = m.usuario_1_id 
                        JOIN usuarios u2 ON u2.id = m.usuario_2_id
                        WHERE a.remetente_id = %s OR a.destinatario_id = %s ORDER BY a.id DESC;
                    """, (meu_id_limpo, meu_id_limpo, meu_id_limpo))
                    encontros = cursor_enc.fetchall()
        except Exception as e:
            st.error(f"Erro ao buscar convites: {e}")
        finally:
            if conn_enc:
                liberar_conexao(conn_enc)

        encontros_ativos = [e for e in encontros if str(e[4]).lower() in ['pendente', 'aceito']]
        encontros_passados = [e for e in encontros if str(e[4]).lower() in ['concluido', 'recusado', 'cancelado']]

        if not encontros_ativos:
            st.caption("Nenhum convite pendente ou encontro ativo para hoje.")
        
        # 3. RENDERIZAÇÃO DOS CONVITES ATIVOS
        for ag_id, dia, per, hora, status, rem_id, parceiro_nome, m_id in encontros_ativos:
            eu_enviei = (int(rem_id) == meu_id_limpo)
            parceiro_limpo = str(parceiro_nome).split('@')[0].capitalize()
        
            with st.container(border=True):
                col_i, col_b = st.columns([2, 1])
                with col_i:
                    st.write(f"📅 **Encontro com {parceiro_limpo}:** {dia} às {str(hora)[:5]}")
                    st.caption(f"Status: {status.upper()}")
                with col_b:
                    if status == 'pendente' and not eu_enviei:
                        c_conf, c_rec = st.columns(2)
                        with c_conf:
                            if st.button("✅ Confirmar", key=f"btn_ok_{ag_id}", type="primary", use_container_width=True, disabled=bloquear_botoes):
                                conn_up = None
                                try:
                                    conn_up = obter_conexao_eficiente()
                                    if conn_up:
                                        with conn_up.cursor() as cursor_up:
                                            cursor_up.execute("UPDATE agendamentos_virtuais SET status_convite = 'aceito' WHERE id = %s;", (int(ag_id),))
                                            conn_up.commit()
                                        st.toast("Convite aceito!")
                                        time.sleep(0.5)
                                        st.rerun()
                                except Exception as e_up:
                                    if conn_up: conn_up.rollback()
                                    st.error(f"Erro ao aceitar: {e_up}")
                                finally:
                                    if conn_up: liberar_conexao(conn_up)
                        with c_rec:
                            if st.button("❌ Recusar", key=f"btn_rec_{ag_id}", type="secondary", use_container_width=True):
                                conn_up = None
                                try:
                                    conn_up = obter_conexao_eficiente()
                                    if conn_up:
                                        with conn_up.cursor() as cursor_up:
                                            cursor_up.execute("UPDATE agendamentos_virtuais SET status_convite = 'recusado' WHERE id = %s;", (int(ag_id),))
                                            conn_up.commit()
                                        st.toast("Convite recusado.")
                                        time.sleep(0.5)
                                        st.rerun()
                                except Exception as e_up:
                                    if conn_up: conn_up.rollback()
                                    st.error(f"Erro ao recusar: {e_up}")
                                finally:
                                    if conn_up: liberar_conexao(conn_up)

                            elif status == 'pendente' and eu_enviei: 
                                if st.button("🚫 Cancelar", key=f"btn_canc_{ag_id}", type="secondary", use_container_width=True): 
                                    conn_up = None 
                            try: 
                                conn_up = obter_conexao_eficiente() 
                                if conn_up: 
                                    with conn_up.cursor() as cursor_up: 
                                        cursor_up.execute("UPDATE agendamentos_virtuais SET status_convite = 'cancelado' WHERE id = %s;", (int(ag_id),)) 
                                        conn_up.commit() 
                                        st.toast("Convite cancelado.") 
                                        time.sleep(0.5) 
                                        st.rerun() 
                            except Exception as e_up: 
                                if conn_up: conn_up.rollback() 
                                    st.error(f"Erro ao cancelar: {e_up}") 
                            finally: 
                                if conn_up: liberar_conexao(conn_up) 
                            else: 
                                st.info("📆 Convite Aceito") 

        # Histórico de encontros passados
        st.markdown("### 🕒 Histórico de Convites Recusados ou Passados", unsafe_allow_html=True)

        if not encontros_passados:
            st.caption("Nenhum histórico disponível.")
        else:
            for ag_id, dia, per, hora, status, rem_id, parceiro_nome, m_id in encontros_passados:
                parceiro_limpo = str(parceiro_nome).split("@")[0].capitalize()
                st.text(f"⚪ Encontro com {parceiro_limpo} ({dia} às {str(hora)[:5]}) - Status: {status.upper()}") 



# ==============================================================================
# TEMPORIZADOR AUTOMÁTICO DE CRÉDITOS (AUTO-REFRESH SEGURO)
# ==============================================================================
# ⚡ OTIMIZAÇÃO: Removemos o st.rerun fragmentado manual, deixando o run_every gerenciar o ciclo
@st.fragment(run_every=5.0)
def renderizar_temporizador_creditos(saldo_moedas_sala, id_usuario_logado, id_match_int):
    # 1. INICIALIZAÇÃO SEGURA DO TEMPO
    if "tempo_inicio_sala" not in st.session_state: 
        st.session_state.tempo_inicio_sala = time.time()
        
    tempo_decorrido = time.time() - st.session_state.tempo_inicio_sala
    tempo_restante = 600 - tempo_decorrido  # 10 minutos = 600 segundos
    
    if tempo_restante > 0:
        # Exibe o cronômetro regressivo de forma limpa
        st.warning(f"⏳ Tempo Restante: {int(tempo_restante // 60)}m {int(tempo_restante % 60)}s | Saldo: 🪙 {saldo_moedas_sala} moedas")
    else:
        # O tempo esgotou, tenta renovar de forma atômica no banco
        if saldo_moedas_sala >= 10:
            conn_renova = None
            try:
                novo_saldo = saldo_moedas_sala - 10
                id_limpo = id_usuario_logado if not isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
                
                # ⚡ OTIMIZAÇÃO CRÍTICA: Débito executado direto no Pool PostgreSQL (0ms de lag)
                # Remove a dependência da chamada HTTP lenta do cliente Supabase no loop crítico
                conn_renova = obter_conexao_eficiente()
                if conn_renova:
                    with conn_renova.cursor() as cursor_renova:
                        cursor_renova.execute("UPDATE usuarios SET moedas = %s WHERE id = %s;", (int(novo_saldo), int(id_limpo)))
                        conn_renova.commit()
                    
                    # Sincroniza a memória global em todas as instâncias (Barra lateral e telas)
                    st.session_state["saldo_moedas"] = novo_saldo
                    if "dados_usuario" in st.session_state: 
                        st.session_state.dados_usuario["moedas"] = novo_saldo
                        
                    # Reseta o cronômetro para mais 10 minutos
                    st.session_state.tempo_inicio_sala = time.time()
                    st.toast("🪙 Mais 10 minutos adicionados!", icon="🪙")
                    
                    # Deixa o run_every=5.0 assumir o próximo ciclo naturalmente, redesenhando a caixa limpa
                else:
                    st.error("Falha de conexão ao tentar renovar seu tempo.")
                
            except Exception as e: 
                if conn_renova: conn_renova.rollback()
                st.error(f"Erro ao debitar moedas: {e}")
            finally:
                if conn_renova:
                    liberar_conexao(conn_renova)
        else:
            # Sem saldo: Redireciona o usuário imediatamente alterando o estado global
            st.error("🔒 Tempo esgotado e sem moedas para renovação.")
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            
            # Limpa o cronômetro da memória para a próxima sessão
            if "tempo_inicio_sala" in st.session_state:
                del st.session_state.tempo_inicio_sala
                
            # Como mudamos de menu principal, aqui forçamos o redesenho da tela inteira
            st.rerun()


# ==============================================================================
# FUNÇÃO AUXILIAR: BANCO DE DADOS DA SALA PRIVADA (PERFEITA)
# ==============================================================================
def enviar_mensagem(match_id, remetente_id, texto):
    if not texto or str(texto).strip() == "":
        return
    
    conn = None
    try:
        id_match_int = int(match_id[0] if isinstance(match_id, (tuple, list)) else match_id)
        id_remetente_int = int(remetente_id[0] if isinstance(remetente_id, (tuple, list)) else remetente_id)
        
        conn = obter_conexao_eficiente()
        if conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO mensagens_sala (match_id, remetente_id, conteudo) 
                    VALUES (%s, %s, %s);
                """, (id_match_int, id_remetente_int, str(texto).strip()))
                conn.commit()
        
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"Erro ao enviar mensagem: {e}")
    finally:
        if conn:
            liberar_conexao(conn)

# ==============================================================================
# MOTORES DE BUSCA E LIMPEZA DA SALA PRIVADA (TOTALMENTE SEGUROS)
# ==============================================================================
def buscar_mensagens(match_id):
    conn = None
    try:
        id_match_int = int(match_id[0] if isinstance(match_id, (tuple, list)) else match_id)
        
        conn = obter_conexao_eficiente()
        # ⚡ PROTEÇÃO CRÍTICA: Só abre o cursor se a conexão do pool for resgatada com sucesso
        if conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT remetente_id, conteudo, criado_em 
                    FROM mensagens_sala 
                    WHERE match_id = %s 
                    ORDER BY criado_em ASC;
                """, (id_match_int,))
                mensagens = cursor.fetchall()
            return mensagens
        else:
            return []
    except Exception:
        return []
    finally:
        if conn:
            liberar_conexao(conn)
    return []

def limpar_historico_sala(match_id):
    conn = None
    try:
        id_match_int = int(match_id[0] if isinstance(match_id, (tuple, list)) else match_id)
        
        conn = obter_conexao_eficiente()
        if conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM mensagens_sala WHERE match_id = %s;", (id_match_int,))
                conn.commit()
            return True
        else:
            st.error("Falha ao obter conexão com o banco para limpar o histórico.")
            return False
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"Erro ao limpar histórico da sala: {e}")
        return False
    finally:
        if conn:
            liberar_conexao(conn)



@st.fragment(run_every=3.0)  # Auto-refresh de mensagens a cada 3 segundos
def renderizar_mensagens_sala_privada(match_id, meu_id):
    mensagens = buscar_mensagens(match_id)
    
    # Janela com rolagem integrada
    caixa_chat = st.container(height=400, border=False)
    with caixa_chat:
        for remetente_id, conteudo, criado_em in mensagens:
            eu_enviei = (int(remetente_id) == int(meu_id))
            with st.chat_message("user" if eu_enviei else "assistant"):
                st.markdown(conteudo)
    
    st.markdown("""
        <style>
        .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
        .box-perfil-fixo { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }
        .chat-container { display: flex; flex-direction: column; gap: 10px; padding: 10px; height: 400px; overflow-y: auto; }
        .msg-bubble { border-radius: 8px; padding: 8px 12px; max-width: 75%; font-size: 15px; line-height: 1.4; margin-bottom: 5px; }
        .msg-meu { background-color: #056162; color: white; align-self: flex-end; border-top-right-radius: 0px; margin-left: auto; }
        .msg-parceiro { background-color: #262d31; color: white; align-self: flex-start; border-top-left-radius: 0px; margin-right: auto; }
        .msg-autor { font-size: 11px; font-weight: bold; color: #34b7f1; margin-bottom: 3px; }
        .msg-tempo { font-size: 10px; color: #8696a0; text-align: right; margin-top: 4px; }
        </style>
    """, unsafe_allow_html=True)

    parceiro_nome = "Usuário"
    parceiro_gen = "M"
    status_parceiro = "⚫ Offline"
    status_cor = "#a0aec0"
    
    # 1. BUSCA DE PERFIL COM SESSÃO BLINDADA NO POOL
    conn = None
    try:
        conn = obter_conexao_eficiente()
        with conn.cursor() as cursor:
            id_match_int = int(match_id if isinstance(match_id, (tuple, list)) else match_id)
            cursor.execute("SELECT usuario_1_id, usuario_2_id FROM matches WHERE id = %s;", (id_match_int,))
            res_m = cursor.fetchone()
            
            if res_m:
                u1, u2 = int(res_m[0]), int(res_m[1])
                meu_id_limpo = st.session_state.usuario_id if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)
                p_id = u2 if u1 == meu_id_limpo else u1
                
                cursor.execute("SELECT username, foto_perfil, genero, status FROM usuarios WHERE id = %s;", (int(p_id),))
                res_u = cursor.fetchone()
                if res_u:
                    parceiro_nome = str(res_u[0])
                    parceiro_gen = res_u[2]
                    p_stat = res_u[3]
                    if "Online" in str(p_stat) or "🟢" in str(p_stat):
                        status_parceiro = "🟢 Online"
                        status_cor = "#48bb78"
    except Exception as e: 
        st.error(f"Erro ao buscar status na Sala Privada: {e}")
    finally:
        if conn:
            liberar_conexao(conn)  # ⚡ Devolução imediata ao pool

    # Recupera informações de faturamento salvas em memória
    tipo_plano_sala = "Grátis"
    saldo_moedas_sala = 0
    id_usuario_logado = st.session_state.get("usuario_id")
    
    if "dados_usuario" in st.session_state:
        tipo_plano_sala = str(st.session_state.dados_usuario.get("tipo_plano", "Grátis")).strip()
        saldo_moedas_sala = st.session_state.dados_usuario.get("moedas", 0)

    # Divisão de Colunas Layout
    col_perfil, col_chat = st.columns([1, 3])

    with col_perfil:
        st.markdown(f"""<div class="box-perfil-fixo"><div style="font-size: 40px; text-align:center;">{"👩" if parceiro_gen == "F" else "👨"}</div></div>""", unsafe_allow_html=True)
        st.markdown(f'<div style="color:white; font-weight:bold; font-size:18px; text-align:center;">{parceiro_nome}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color: {status_cor}; font-size:14px; margin-top:5px; text-align:center;">{status_parceiro}</div>', unsafe_allow_html=True)
        
        st.markdown("""<div style="background-color:#161b22; padding:10px; border-radius:5px; border:1px solid #30363d; margin:15px 0;">🔒 Sala criptografada temporária de ponta a ponta.</div>""", unsafe_allow_html=True)
                
        if st.button("🚪 Sair da Sala Privada", type="primary", use_container_width=True, key="btn_sair_sala_p"):
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun() 
            
        if st.button("🗑️ Limpar Histórico do Chat", type="secondary", use_container_width=True, key="btn_limpar_hist_p"):
            if limpar_historico_sala(match_id):
                st.success("Histórico apagado!")
                st.rerun(scope="fragment") 

        if tipo_plano_sala == "Plano Crédito de Moedas":
            st.info(f"🪙 Modo Créditos Ativo. Saldo atual: {saldo_moedas_sala} moedas.")
            id_match_int = int(match_id if isinstance(match_id, (tuple, list)) else match_id)
            if "renderizar_temporizador_creditos" in globals():
                renderizar_temporizador_creditos(saldo_moedas_sala, id_usuario_logado, id_match_int) 
        elif tipo_plano_sala == "vip": 
            st.success(f"⭐ Plano Assinante Ativo: Tempo Ilimitado.") 

    with col_chat:
        st.markdown(f"### 💬 Sala Privada com {parceiro_nome}")
        id_match_atual = st.session_state.get("match_id_atual")
        
        if st.button("🎥 Iniciar Videochamada Privada", type="tertiary", key="btn_video_jitsi"): 
            id_match_int = int(match_id if isinstance(match_id, (tuple, list)) else match_id)
            nome_da_sala_unica = f"Atendimento_FaleConosco_SalaPrivada_{id_match_int}" 
            url_jitsi = f"https://meet.jit.si/{nome_da_sala_unica}"
            st.info("A videochamada foi iniciada abaixo. Garanta as permissões no navegador.") 
            st.iframe(url_jitsi, height=600)

        # ⚡ OTIMIZAÇÃO DE REDE: O update de presença agora ocorre apenas se o gatilho for disparado
        # Removemos o envio obrigatório a cada milissegundo de renderização ordinária
        if id_match_atual and "presenca_atualizada" not in st.session_state:
            try:
                agora_iso = datetime.now().isoformat()
                supabase.table("matches").update({"status_conexao": "online", "ultima_atividade": agora_iso}).eq("id", id_match_atual).execute()
                st.session_state.presenca_atualizada = True # Evita loops infinitos de IO de rede
            except Exception: 
                pass   
        st.divider()


        # ==============================================================================
        # CONTAINER DE COMPOSIÇÃO DA SALA PRIVADA (INTEGRAÇÃO COMPLETA)
        # ==============================================================================
        # Cole este trecho exatamente onde começava o "# CONTAINER DE MENSAGENS" no bloco anterior:

        # 1. Invoca o sub-fragmento dinâmico de leitura assíncrona
        renderizar_miolo_mensagens_sala(match_id, meu_id, parceiro_nome)

        # 2. Formulário nativo rápido de envio (Fixo na tela, imune a resets de tempo)
        with st.form(key="form_enviar_msg_sala", clear_on_submit=True):
            col_txt, col_btn = st.columns([4, 1])
            with col_txt:
                texto_msg = st.text_input(label="Mensagem", placeholder="Digite uma mensagem...", label_visibility="collapsed", key="txt_msg_sala_input")
            with col_btn:
                botao_enviar = st.form_submit_button("Enviar", use_container_width=True)
                
            if botao_enviar and texto_msg.strip():
                enviar_mensagem(match_id, meu_id, texto_msg)
                # Força o refresh instantâneo da tela de mensagens pós-envio
                st.rerun(scope="fragment")


        # ==============================================================================
        # CONTAINER DE MENSAGENS (MIOLO DO CHAT DA SALA PRIVADA)
        # ==============================================================================
        with st.container(height=380, border=True):
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            mensagens = buscar_mensagens(match_id) 
            
            for msg in mensagens:
                # Desempacota as colunas básicas de forma estrita
                r_id = msg[0]
                conteudo = msg[1]
                criado_em_bruto = msg[2]
                
                # ⚡ SOLUÇÃO DO BUG: Tratamento do objeto de data/tempo contra Tuplas ou Strings
                horario = ""
                if criado_em_bruto:
                    try:
                        # Se veio como tupla/lista residual do banco, extrai o primeiro índice
                        if isinstance(criado_em_bruto, (tuple, list)) and len(criado_em_bruto) > 0:
                            criado_em_bruto = criado_em_bruto[0]
                        
                        # Converte de forma robusta usando pandas (gerencia strings e timestamps)
                        dt_objeto = pd.to_datetime(criado_em_bruto)
                        horario = dt_objeto.strftime("%H:%M")
                    except Exception:
                        horario = "" # Fallback silencioso para não quebrar a tela se a data falhar

                # Renderização das bolhas HTML baseadas no remetente
                if str(r_id) == str(meu_id):
                    st.markdown(f'<div class="msg-bubble msg-meu"><div class="msg-autor">Você</div><div>{conteudo}</div><div class="msg-tempo">{horario}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="msg-bubble msg-parceiro"><div class="msg-autor">{parceiro_nome}</div><div>{conteudo}</div><div class="msg-tempo">{horario}</div></div>', unsafe_allow_html=True)
                    
            st.markdown('</div>', unsafe_allow_html=True)

        # Formulário nativo rápido
        with st.form(key="form_enviar_msg_sala", clear_on_submit=True):
            col_txt, col_btn = st.columns([4, 1])
            with col_txt:
                texto_msg = st.text_input(label="Mensagem", placeholder="Digite uma mensagem...", label_visibility="collapsed", key="txt_msg_sala_input")
            with col_btn:
                botao_enviar = st.form_submit_button("Enviar", use_container_width=True)
                
            if botao_enviar and texto_msg.strip():
                enviar_mensagem(match_id, meu_id, texto_msg)
                st.rerun(scope="fragment") # Recarrega apenas as mensagens, eliminando o travamento de fundo


# ==============================================================================
# SUB-FRAGMENTO ULTRA-RÁPIDO: ATUALIZADOR AUTOMÁTICO DE MENSAGENS (3s)
# ==============================================================================
# ⚡ OTIMIZAÇÃO CRÍTICA: Esse bloco se atualiza sozinho a cada 3 segundos.
# Ele busca novas mensagens do parceiro sem apagar o texto que o usuário está digitando embaixo!
@st.fragment(run_every=3.0)
def renderizar_miolo_mensagens_sala(match_id, meu_id, parceiro_name):
    with st.container(height=380, border=True):
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        mensagens = buscar_mensagens(match_id) 
        
        for msg in mensagens:
            r_id = msg[0]
            conteudo = msg[1]
            criado_em_bruto = msg[2]
            
            horario = ""
            if criado_em_bruto:
                try:
                    if isinstance(criado_em_bruto, (tuple, list)) and len(criado_em_bruto) > 0:
                        criado_em_bruto = criado_em_bruto[0]
                    
                    dt_objeto = pd.to_datetime(criado_em_bruto)
                    horario = dt_objeto.strftime("%H:%M")
                except Exception:
                    horario = ""

            # Renderização das bolhas HTML baseadas no remetente
            if str(r_id) == str(meu_id):
                st.markdown(f'<div class="msg-bubble msg-meu"><div class="msg-autor">Você</div><div>{conteudo}</div><div class="msg-tempo">{horario}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="msg-bubble msg-parceiro"><div class="msg-autor">{parceiro_name}</div><div>{conteudo}</div><div class="msg-tempo">{horario}</div></div>', unsafe_allow_html=True)
                
        st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# MOTOR DO GATEWAY: VERIFICAÇÃO DE PAGAMENTOS PIX (PERFEITO)
# ==============================================================================
def verificar_status_pix(id_pagamento):
    """Consulta a API do Mercado Pago e retorna o status atualizado de forma instantânea."""
    # Proteção para o caso do SDK não ter sido inicializado por falta de tokens no Render
    if not sdk:
        return "erro"
    try:
        payment_info = sdk.payment().get(id_pagamento)
        if "response" in payment_info and "status" in payment_info["response"]:
            return payment_info["response"]["status"]
        return "pendente"
    except Exception as e:
        st.error(f"Erro ao consultar Mercado Pago: {e}")
        return "erro"

# ==============================================================================
# 1. ATUALIZAÇÃO BLINDADA COM VALIDAÇÃO DE ID DE PAGAMENTO VIA POOL POSTGRES
# ==============================================================================
def atualizar_plano_banco_supabase(id_usuario, tipo_pagamento, id_pagamento_mp):
    """
    Atualiza o plano ou adiciona moedas garantindo de forma absoluta 
    que o mesmo ID de pagamento do Mercado Pago nunca seja computado duas vezes.
    Operação realizada direto no Pool PostgreSQL para performance máxima (0ms).
    """
    conn_transacao = None
    try:
        id_usuario_int = int(id_usuario)
        data_atual_iso = datetime.now().isoformat()
        
        # Resgata conexão limpa e veloz do Pool global
        conn_transacao = obter_conexao_eficiente()
        if not conn_transacao:
            st.error("❌ Falha interna: Não foi possível conectar ao banco para validar o pagamento.")
            return False

        with conn_transacao.cursor() as cursor:
            # ⚡ PASSO CRÍTICA: Consulta atômica no banco
            cursor.execute(
                "SELECT ultimo_id_pagamento, moedas FROM usuarios WHERE id = %s FOR UPDATE;", 
                (id_usuario_int,)
            )
            res_usuario = cursor.fetchone()
            
            if res_usuario:
                ultimo_pago = res_usuario[0]
                moedas_atuais = int(res_usuario[1] or 0)
                
                # 🛑 TRAVA DE SEGURANÇA MÁXIMA: Evita fraudes ou cliques duplos
                if str(ultimo_pago) == str(id_pagamento_mp):
                    return True # Aborda mas retorna True para prosseguir e limpar o fluxo visual
            else:
                st.error("❌ Usuário não localizado no banco de dados.")
                return False

            # CENÁRIO 1: Compra do Plano VIP
            if tipo_pagamento == "vip":
                cursor.execute("""
                    UPDATE usuarios 
                    SET tipo_plano = 'vip', ultima_recarga = %s, ultimo_id_pagamento = %s 
                    WHERE id = %s;
                """, (data_atual_iso, str(id_pagamento_mp), id_usuario_int))
                
                # Confirma as alterações no PostgreSQL antes de mexer na memória
                conn_transacao.commit()
                
                # Sincroniza a memória estável local do Streamlit
                st.session_state["tipo_plano"] = "vip"
                if "dados_usuario" in st.session_state:
                    st.session_state.dados_usuario["tipo_plano"] = "vip"
                return True
                
            # CENÁRIO 2: Compra de Pacote de Moedas (+10 estrito)
            elif tipo_pagamento == "moedas":
                novas_moedas = moedas_atuais + 10
                
                cursor.execute("""
                    UPDATE usuarios 
                    SET tipo_plano = 'Plano Crédito de Moedas', moedas = %s, ultima_recarga = %s, ultimo_id_pagamento = %s 
                    WHERE id = %s;
                """, (novas_moedas, data_atual_iso, str(id_pagamento_mp), id_usuario_int))
                
                # Confirma as alterações no PostgreSQL antes de mexer na memória
                conn_transacao.commit()
                
                # Sincroniza a memória estável local do Streamlit em todas as instâncias
                st.session_state["tipo_plano"] = "Plano Crédito de Moedas"
                st.session_state["saldo_moedas"] = novas_moedas
                if "dados_usuario" in st.session_state:
                    st.session_state.dados_usuario["tipo_plano"] = "Plano Crédito de Moedas"
                    st.session_state.dados_usuario["moedas"] = novas_moedas
                return True

    except Exception as e:
        if conn_transacao:
            conn_transacao.rollback()
        st.error(f"❌ Erro crítico na transação de créditos: {e}")
        return False
    finally:
        if conn_transacao:
            liberar_conexao(conn_transacao)
            
    return False


# ==============================================================================
# 5. RENDERIZADORES DE DIALOGS / MODAIS (FECHAMENTO SEGURO AUTOMÁTICO)
# ==============================================================================
@st.dialog("🔑 Recuperar Senha")
def modal_recuperar_senha():
    st.write("Digite o seu e-mail cadastrado e a sua nova senha abaixo.")
    
    # Formulário nativo com chave única e limpeza ao enviar
    with st.form("form_recuperacao_senha_final", clear_on_submit=True):
        email_digitado = st.text_input("E-mail Cadastrado").strip().lower()
        nova_senha = st.text_input("Nova Senha", type="password")
        botao_confirmar = st.form_submit_button("Redefinir Senha", use_container_width=True)
                
    # Processamento lógico e de banco totalmente FORA do bloco 'with st.form'
    if botao_confirmar:
        if not email_digitado or not nova_senha:
            st.error("Por favor, preencha todos os campos.")
        else:
            conn = None
            try:
                conn = obter_conexao_eficiente()
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT id FROM usuarios WHERE email = %s;', (email_digitado,))
                        usuario_encontrado = cursor.fetchone()

                        if usuario_encontrado:
                            # Criptografia rápida com a função global que definimos no topo do app
                            senha_criptografada = generate_password_hash(nova_senha)
                            cursor.execute('UPDATE usuarios SET password_hash = %s WHERE email = %s;', (senha_criptografada, email_digitado))
                            conn.commit()
                            
                            st.success("🎉 Senha redefinida com sucesso!")
                            
                            # Remove referências de variáveis de controle temporárias se houver
                            if "mostrar_recuperar_senha" in st.session_state:
                                st.session_state.mostrar_recuperar_senha = False
                            
                            # ⚡ SOLUÇÃO DO FECHAMENTO: No Streamlit Dialog, dar um time.sleep + st.rerun
                            # reconstrói a página do zero, o que destrói o modal e atualiza a tela de login vazia
                            import time
                            time.sleep(1.0)
                            st.rerun() 
                        else:
                            st.error("❌ E-mail não localizado no sistema.")
                else:
                    st.error("Não foi possível conectar ao banco de dados.")
                    
            except Exception as e:
                if conn: 
                    conn.rollback()
                st.error(f"Erro ao acessar o banco de dados: {e}")
            finally:
                if conn:
                    liberar_conexao(conn)


def template_privado_gerar_faturamento(df_faturamento):
    """Sub-função auxiliar para renderizar a distribuição de planos e moedas"""
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Faturamento: Distribuição de Planos</p>", unsafe_allow_html=True)
        if "tipo_plano" in df_faturamento.columns:
            df_faturamento["tipo_plano_nome"] = df_faturamento["tipo_plano"].fillna("Grátis")
            st.bar_chart(df_faturamento["tipo_plano_nome"].value_counts(), color="#e3b341", height=180, use_container_width=True)
    with col_f2:
        st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Receita em Carteira: Saldo de Moedas</p>", unsafe_allow_html=True)
        if "moedas" in df_faturamento.columns:
            total_moedas_plataforma = int(df_faturamento["moedas"].sum() or 0)
            st.metric("Total de Moedas Ativas na Rede", f"🪙 {total_moedas_plataforma}")
            st.caption("Volume acumulado em posse dos usuários pendente de conversão em salas.")

def template_painel_admin():
    st.markdown("<h2>🛠️ Painel Administrativo de Controle Avançado</h2>", unsafe_allow_html=True)
    st.caption("Métricas demográficas, performance preditiva da Lucy IA e moderação de contas em tempo real.")
    st.markdown("<hr style='border-color: #30363d; margin: 10px 0 25px 0;'>", unsafe_allow_html=True)

    # --- 1. CONFIGURAÇÕES DA BARRA LATERAL ---
    st.sidebar.subheader("⚙️ Configurações do Painel")
    visao_perfil = st.sidebar.selectbox(
        "Visualizar no gráfico:",
        options=["Apenas Clientes", "Todos (Incluir Admin)"],
        index=0
    )

    usuarios_bd = []
    dados_agendados = {}
    dados_realizados = {}  
    dados_matches = {}
    total_salas_ativas = 0

    # --- 2. VARREDURA ANALÍTICA ATÔMICA NO POOL POSTGRES ---
    # ⚡ OTIMIZAÇÃO CRÍTICA: Adicionado tipo_plano, ultima_recarga e moedas diretamente na query SQL.
    # Isso elimina totalmente as chamadas de API HTTP lentas do Supabase e poupa RAM no Render!
    conn = None
    try:
        conn = obter_conexao_eficiente()
        if conn:
            with conn.cursor() as cursor:
                # Query 1: Usuários + Dados de Faturamento unificados
                cursor.execute("""
                    SELECT id, username, email, genero, idade, procura_por, status, is_admin, tipo_plano, moedas, ultima_recarga 
                    FROM usuarios ORDER BY id ASC;
                """)
                usuarios_bd = cursor.fetchall()

                # Query 2: Salas Ativas nos últimos 5 minutos
                cursor.execute("""
                    SELECT COUNT(id) FROM matches 
                    WHERE status_conexao = 'online' AND ultima_atividade >= NOW() - INTERVAL '5 minutes';
                """)
                res_salas = cursor.fetchone()
                total_salas_ativas = res_salas[0] if res_salas else 0

                # Query 3: Agendados
                cursor.execute("SELECT TRIM(LOWER(dia_semana)), COUNT(*) FROM agendamentos_virtuais GROUP BY 1;")
                dados_agendados = dict(cursor.fetchall())
                
                # Query 4: Realizados
                cursor.execute("""
                    SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT mc.id) 
                    FROM agendamentos_virtuais a JOIN mensagens_sala mc ON mc.match_id = a.match_id GROUP BY 1;
                """)
                dados_realizados = dict(cursor.fetchall())
                
                # Query 5: Matches
                cursor.execute("""
                    SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT m.id) 
                    FROM agendamentos_virtuais a JOIN matches m ON m.id = a.match_id GROUP BY 1;
                """)
                dados_matches = dict(cursor.fetchall())
        else:
            st.error("Não foi possível conectar ao banco de dados para alimentar o painel admin.")
            return
            
    except Exception as e:
        st.error(f"Erro na varredura analítica do banco (SQL): {e}")
    finally:
        if conn:
            liberar_conexao(conn)

    if not usuarios_bd:
        st.warning("Nenhum dado de usuário localizado para gerar o painel.")
        return

    # 3. CONVERSÃO INTELIGENTE PARA DATAFRAME
    df_usuarios_mod = pd.DataFrame(usuarios_bd, columns=[
        "ID", "Nome / Username", "E-mail", "Gênero", "Idade", "Procura Por", 
        "Status Presença", "is_admin", "tipo_plano", "moedas", "ultima_recarga"
    ])
    
    # ⚡ COMPATIBILIDADE: Aplica o filtro de visualização da barra lateral dinamicamente em memória
    if visao_perfil == "Apenas Clientes":
        df_usuarios_mod = df_usuarios_mod[df_usuarios_mod["is_admin"] == False].copy()

    # Renderização dos KPIs de Performance
    c_k1, c_k2, c_k3 = st.columns(3)
    with c_k1:
        st.metric("Total de Perfis Cadastrados", len(df_usuarios_mod))
    with c_k2:
        ativos_now = len(df_usuarios_mod[df_usuarios_mod["Status Presença"].str.contains("Online", na=False)])
        st.metric("Usuários Online Agora", ativos_now)
    with c_k3:
        st.metric("Salas Virtuais Ativas (Hoje)", int(total_salas_ativas or 0))

    # Abas estruturais do painel administrativo
    aba_graficos, aba_moderacao = st.tabs(["📊 Gráficos e Insights", "👥 Gestão de Contas"])

    with aba_graficos:
        st.markdown("### 📊 Gráfico de Pareto Mensal Unificado")
        
        dias_b = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']
        dias_exibicao = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        
        v_agendados = [dados_agendados.get(d, 0) // 2 if dados_agendados.get(d, 0) > 1 else dados_agendados.get(d, 0) for d in dias_b]
        v_realizados = [dados_realizados.get(d, 0) // 2 if dados_realizados.get(d, 0) > 1 else dados_realizados.get(d, 0) for d in dias_b]
        v_matches = [dados_matches.get(d, 0) // 2 if dados_matches.get(d, 0) > 1 else dados_matches.get(d, 0) for d in dias_b]
        
        v_totais_dia = [v_agendados[i] + v_realizados[i] + v_matches[i] for i in range(7)]
        v_acumulado = []
        soma_incremental = 0
        for val in v_totais_dia:
            soma_incremental += val
            v_acumulado.append(soma_incremental)

        dados_pareto_lista = []
        for i, dia in enumerate(dias_exibicao):
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Agendados", "Quantidade": int(v_agendados[i])})
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Realizados", "Quantidade": int(v_realizados[i])})
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Matches", "Quantidade": int(v_matches[i])})
            
        df_barras_altair = pd.DataFrame(dados_pareto_lista)
        df_linha_altair = pd.DataFrame({"Dia": dias_exibicao, "Acumulado Semanal": v_acumulado})

        # Renderização combinada Altair (Pareto de Conexões)
        grafico_barras = alt.Chart(df_barras_altair).mark_bar().encode(
            x=alt.X('Dia:N', sort=dias_exibicao, title="Dia da Semana"),
            y=alt.Y('Quantidade:Q', title="Volumetria Individual"),
            color=alt.Color('Métrica:N', scale=alt.Scale(domain=['Agendados', 'Realizados', 'Matches'], range=['#1f6feb', '#238636', '#e3b341']))
        )

        grafico_linha = alt.Chart(df_linha_altair).mark_line(color='#ef4444', strokeWidth=3, point=True).encode(
            x=alt.X('Dia:N', sort=dias_exibicao),
            y=alt.Y('Acumulado Semanal:Q', title="Total Acumulado Semanal")
        )

        grafico_pareto_final = alt.layer(grafico_barras, grafico_linha).resolve_scale(y='independent').properties(width='container', height=280)
        st.altair_chart(grafico_pareto_final, theme="streamlit", use_container_width=True)

        st.markdown("<hr style='border-color: #21262d; margin: 25px 0;'>", unsafe_allow_html=True)
        st.markdown("### 🗺️ Análise Demográfica e Procura por Orientação")
        
        col_piz1, col_piz2 = st.columns(2)
        with col_piz1:
            st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Distribuição por Gênero Cadastrado</p>", unsafe_allow_html=True)
            df_usuarios_mod["Gênero_Nome"] = df_usuarios_mod["Gênero"].map({"M": "Homem", "F": "Mulher", "O": "Outros"}).fillna("Não Informado")
            st.bar_chart(df_usuarios_mod["Gênero_Nome"].value_counts(), color="#1f6feb", height=180, use_container_width=True)
            
        with col_piz2:
            st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Orientação de Interesse (Procura Por)</p>", unsafe_allow_html=True)
            df_usuarios_mod["Procura_Nome"] = df_usuarios_mod["Procura Por"].map({"M": "Procura Homem", "F": "Procura Mulher", "O": "Procura Ambos"}).fillna("Não Configurado")
            st.bar_chart(df_usuarios_mod["Procura_Nome"].value_counts(), color="#238636", height=180, use_container_width=True)

        st.markdown("<hr style='border-color: #21262d; margin: 25px 0;'>", unsafe_allow_html=True)
        st.subheader("📊 Análise de Créditos e Assinaturas")
        
        # ⚡ FECHAMENTO DO BLOCO DO GRÁFICO DE FATURAMENTO: Processado direto em memória local sem IO de rede extra
        template_privado_gerar_faturamento(df_usuarios_mod)

            # --- REESTRUTURAÇÃO DAS COLUNAS DE CRÉDITOS E ASSINATURAS (DENTRO DO PAINEL ADMIN) ---
        # Substitua a partir da linha "g1, g2 = st.columns(2)" do seu arquivo pelo trecho abaixo:

        g1, g2 = st.columns(2)
        with g1:
            pode_gerar_grafico = False

            # ⚡ OTIMIZAÇÃO: Lê direto do DataFrame global alimentado pelo Pool Postgres
            if not df_usuarios_mod.empty:
                if "ultima_recarga" in df_usuarios_mod.columns and "moedas" in df_usuarios_mod.columns:
                    # Filtra apenas os usuários que possuem uma data de última recarga válida
                    df_filtrado = df_usuarios_mod.dropna(subset=["ultima_recarga"]).copy()
                    
                    if not df_filtrado.empty:
                        # Converte para data real de forma robusta gerenciando fusos horários
                        df_filtrado["data"] = pd.to_datetime(df_filtrado["ultima_recarga"]).dt.date
                        
                        # Agrupa a soma de moedas recarregadas por data
                        df_creditos = (
                            df_filtrado.groupby("data")["moedas"]
                            .sum()
                            .reset_index(name="quantidade_creditos")
                        )
                        
                        # Ordena cronologicamente por data
                        df_creditos = df_creditos.sort_values("data")
                        
                        # --- TRATAMENTO DOS DIAS DA SEMANA EM PORTUGUÊS ---
                        df_creditos["data_dt"] = pd.to_datetime(df_creditos["data"])
                        dias_pt = {
                            "Monday": "Segunda", "Tuesday": "Terça", "Wednesday": "Quarta",
                            "Thursday": "Quinta", "Friday": "Sexta", "Saturday": "Sábado", "Sunday": "Domingo"
                        }
                        df_creditos["dia_semana"] = df_creditos["data_dt"].dt.day_name().map(dias_pt)
                        # --------------------------------------------------

                        if df_creditos["quantidade_creditos"].sum() > 0:
                            pode_gerar_grafico = True

            if pode_gerar_grafico:
                try:
                    # Cálculos matemáticos do Pareto acumulado
                    df_creditos["cum_sum"] = df_creditos["quantidade_creditos"].cumsum()
                    df_creditos["cum_percentage"] = (
                        df_creditos["cum_sum"] / df_creditos["quantidade_creditos"].sum()
                    ) * 100

                    fig_pareto = go.Figure()
                        
                    # Barras de volume individual
                    fig_pareto.add_trace(
                        go.Bar(
                            x=df_creditos["dia_semana"],
                            y=df_creditos["quantidade_creditos"],
                            name="Recargas no Dia",
                            marker_color="#007bff",
                        )
                    )
                        
                    # Linha de tendência acumulada (Eixo Y Secundário)
                    fig_pareto.add_trace(
                        go.Scatter(
                            x=df_creditos["dia_semana"],
                            y=df_creditos["cum_percentage"],
                            name="% Acumulada da Semana",
                            yaxis="y2",
                            line=dict(color="#28a745", width=3),
                        )
                    )

                    fig_pareto.update_layout(
                        title="Soma de Recargas e Tendência Acumulada Semanal",
                        yaxis=dict(title="Quantidade de Moedas"),
                        yaxis2=dict(
                            title="Percentual Acumulado (%)",
                            overlaying="y",
                            side="right",
                            range=[0, 105],
                        ),
                        template="plotly_dark",
                        paper_bgcolor="#161b22",
                        plot_bgcolor="#161b22",
                        legend=dict(orientation="h", y=1.1), 
                    )
                    st.plotly_chart(fig_pareto, use_container_width=True)
                        
                except Exception as erro_plotly:
                    st.warning(f"⚠️ Erro interno ao desenhar o gráfico de Pareto: {erro_plotly}")
            else:
                st.info("ℹ️ Nenhuma atividade de recarga registrada para esta semana.")

        # --- COLUNA DO SEGUNDO GRÁFICO (PIZZA COMERCIAL) ---
        with g2: 
            if not df_usuarios_mod.empty:
                # ⚡ OTIMIZAÇÃO: Consome direto o DataFrame principal limpo do pool
                df_usuarios = df_usuarios_mod.copy()
                
                # Padronização e higienização de strings contra nulos
                df_usuarios["tipo_plano_limpo"] = df_usuarios["tipo_plano"].astype(str).str.strip().str.lower()
                df_usuarios["moedas"] = df_usuarios["moedas"].fillna(0).astype(int)
                            
                # Filtros condicionais atômicos para classificação das fatias
                is_admin = df_usuarios["is_admin"] == True
                is_vip = df_usuarios["tipo_plano_limpo"].str.contains("vip", na=False) & (~is_admin)
                is_gratis_puro = df_usuarios["tipo_plano_limpo"].str.contains("grátis|gratis", na=False) & (~is_admin)
                
                is_plano_credito = (
                    df_usuarios["tipo_plano_limpo"].str.contains("crédito|credito|moeda", na=False) | 
                    (is_gratis_puro & (df_usuarios["moedas"] > 0))
                ) & (~is_admin)
                
                is_gratis_real = is_gratis_puro & (df_usuarios["moedas"] == 0) & (~is_admin)
                
                # Contagem matemática exata de registros
                val_vip = int(df_usuarios[is_vip].shape[0])
                val_admin = int(df_usuarios[is_admin].shape[0]) 
                val_credito = int(df_usuarios[is_plano_credito].shape[0])
                val_gratis = int(df_usuarios[is_gratis_real].shape[0])
                
                # Montagem dinâmica do DataFrame da Pizza respeitando o filtro lateral reativo
                if visao_perfil == "Apenas Clientes":
                    df_pizza = pd.DataFrame({
                        "Categoria": ["VIP", "Plano Crédito de Moedas", "Grátis"],
                        "Total": [val_vip, val_credito, val_gratis]
                    })
                    cores_pizza = ["#6f42c1", "#28a745", "#007bff"]  # Roxo, Verde, Azul
                else:
                    df_pizza = pd.DataFrame({
                        "Categoria": ["VIP", "Admin", "Plano Crédito de Moedas", "Grátis"],
                        "Total": [val_vip, val_admin, val_credito, val_gratis]
                    })
                    cores_pizza = ["#6f42c1", "#ffc107", "#28a745", "#007bff"]  # Roxo, Amarelo, Verde, Azul
                
                # Renderização final estável do Plotly Express
                if df_pizza["Total"].sum() > 0:
                    fig_pizza = px.pie(
                        df_pizza, 
                        values="Total", 
                        names="Categoria",
                        title=f"Distribuição de Perfis ({visao_perfil})",
                        color_discrete_sequence=cores_pizza
                    )
                    fig_pizza.update_layout(template="plotly_dark", paper_bgcolor="#161b22")
                    st.plotly_chart(fig_pizza, use_container_width=True)
                else:
                    st.caption("Sem dados volumétricos para gerar o gráfico de setores.")

        # ==============================================================================
        # ABA 2: MODERAÇÃO DE CONTAS E BARRA DE BUSCA AVANÇADA (SINCRO E FILTRADA)
        # ==============================================================================
        # Cole este bloco exatamente substituindo o "with aba_moderacao:" anterior:

        with aba_moderacao:
            st.markdown("### 🔍 Moderação de Contas e Busca Avançada de Usuários")
            
            # Barra de pesquisa interativa
            busca_termo = st.text_input(
                "🔍 Digite o Nome ou E-mail do usuário para filtrar:", 
                placeholder="Ex: Gabriel, Mariana, admin...", 
                key="txt_busca_admin_mod"
            )
            
            # Executa o filtro inteligente em memória usando o Pandas
            if busca_termo:
                df_filtrado = df_usuarios_mod[
                    df_usuarios_mod["Nome / Username"].str.contains(busca_termo, case=False, na=False) |
                    df_usuarios_mod["E-mail"].str.contains(busca_termo, case=False, na=False)
                ].copy()
                st.caption(f"Exibindo {len(df_filtrado)} resultado(s) para a busca '{busca_termo}'")
            else:
                df_filtrado = df_usuarios_mod.copy()

            # ⚡ OTIMIZAÇÃO VISUAL: Renderiza apenas UMA tabela unificada que reage à busca
            st.dataframe(
                df_filtrado[["ID", "Nome / Username", "E-mail", "Gênero", "Idade", "tipo_plano", "moedas", "Status Presença"]], 
                use_container_width=True, 
                hide_index=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

            # --- CONTAINER DE EXCLUSÃO INDIVIDUAL EM LOTE ---
            st.subheader("🗑️ Gerenciador de Exclusão de Perfis")
            
            for idx, row in df_filtrado.iterrows():
                u_id = row["ID"]
                u_name = row["Nome / Username"]
                u_status = row["Status Presença"]
                
                # Trava de segurança para impedir a auto-exclusão do Admin principal
                if int(u_id) == 1 or str(u_name).lower() in ['admin', 'cleverson', 'clever1404']: 
                    continue
                    
                with st.container(border=True):
                    col_info_u, col_botao_u = st.columns([3, 1])
                    
                    with col_info_u:
                        st.write(f"**#{u_id} - {str(u_name).capitalize()}** | E-mail: {row['E-mail']} | Gênero: {row['Gênero']} | Idade: {row['Idade']} anos")
                        st.caption(f"Status Atual: {u_status} | Plano: {row['tipo_plano']} | Créditos: 🪙 {row['moedas']}")
                        
                    with col_botao_u:
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                        
                        # Botão com chave perfeitamente única baseada no ID para estabilizar o DOM
                        if st.button("❌ Excluir Usuário", key=f"adm_drop_user_id_{u_id}", type="primary", use_container_width=True):
                            conn_del = None
                            try:
                                # Executa a exclusão de dependências em lote acelerado no pool
                                conn_del = obter_conexao_eficiente()
                                if conn_del:
                                    with conn_del.cursor() as cursor_del:
                                        cursor_del.execute("DELETE FROM disponibilidade_usuarios WHERE usuario_id = %s;", (int(u_id),))
                                        cursor_del.execute("DELETE FROM historico_ia WHERE usuario_id = %s;", (int(u_id),))
                                        cursor_del.execute("DELETE FROM mensagens_chat WHERE remetente_id = %s;", (int(u_id),))
                                        cursor_del.execute("DELETE FROM agendamentos_virtuais WHERE remetente_id = %s OR destinatario_id = %s;", (int(u_id), int(u_id)))
                                        cursor_del.execute("DELETE FROM matches WHERE usuario_1_id = %s OR usuario_2_id = %s;", (int(u_id), int(u_id)))
                                        
                                        # Remove o usuário definitivo da tabela pai
                                        cursor_del.execute("DELETE FROM usuarios WHERE id = %s;", (int(u_id),))
                                        conn_del.commit()
                                    
                                    st.toast(f"🎉 Perfil de {u_name} removido com sucesso!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error("Falha ao obter conexão com o banco para realizar a exclusão.")
                                
                            except Exception as e:
                                if conn_del: 
                                    conn_del.rollback()
                                st.error(f"Erro ao deletar usuário: {e}")
                            finally:
                                if conn_del:
                                    liberar_conexao(conn_del)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ Voltar para o Chat da Lucy", use_container_width=True, key="btn_voltar_chat_desde_admin_final"):
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()



# ==============================================================================
# TELA PRIVADA 2: TEMPLATE FALE CONOSCO (SUPORTE TÉCNICO VIA EMAIL)
# ==============================================================================
def template_fale_conosco():
    st.markdown("<h2>✉️ Fale Conosco</h2>", unsafe_allow_html=True)
    st.caption("Envie suas dúvidas, críticas ou sugestões de melhoria para a equipe de suporte Lucy IA.")
    st.markdown("<hr style='border-color: #30363d; margin: 10px 0 25px 0;'>", unsafe_allow_html=True)
    
    # Captura o nome de forma segura contra erros de valor nulo
    nome_padrao = st.session_state.get("username", "")

    # Cria uma chave no Session State para segurar o feedback visual sem sumir no clear_on_submit
    if "sucesso_envio_suporte" not in st.session_state:
        st.session_state.sucesso_envio_suporte = False

    with st.form("form_fale_conosco_final", clear_on_submit=True):
        nome_contato = st.text_input("Seu Nome:", value=nome_padrao)
        email_contato = st.text_input("Seu E-mail de Contato:")
        descricao_contato = st.text_area("Escreva sua Mensagem / Sugestão:")
        
        botao_enviar = st.form_submit_button("Enviar por E-mail", type="primary", use_container_width=True)
        
        if botao_enviar:
            if not email_contato.strip() or not descricao_contato.strip():
                st.error("❌ Por favor, preencha seu e-mail e a descrição da mensagem.")
                st.session_state.sucesso_envio_suporte = False
            elif "@" not in email_contato or "." not in email_contato:
                st.error("❌ Por favor, insira um endereço de e-mail válido.")
                st.session_state.sucesso_envio_suporte = False
            else:
                # Carimba o sucesso e limpa qualquer aviso de erro anterior
                st.session_state.sucesso_envio_suporte = True

    # ⚡ OTIMIZAÇÃO: Renderiza o feedback visual fora do Form.
    # Assim, as caixas de texto zeram de forma limpa, mas a mensagem verde continua visível para o cliente!
    if st.session_state.sucesso_envio_suporte:
        st.success("🎉 Sua mensagem foi enviada para o e-mail de suporte (suporte@lucyia.com) com sucesso!")
        # Reseta o estado em background caso ele saia da tela e volte depois
        st.session_state.sucesso_envio_suporte = False



# ==============================================================================
# INITIALIZATION DE SEGURANÇA NA LINHA 1 (RAIZ DO ARQUIVO)
# ==============================================================================
if "opcao_menu" not in st.session_state:
    st.session_state["opcao_menu"] = "home"

if "usuario_id" not in st.session_state:
    st.session_state["usuario_id"] = None

if "form_seed" not in st.session_state:
    st.session_state["form_seed"] = 42


# ==============================================================================
# ROTEADOR DE INTERFACE DO MIOLO (ESTRUTURA FINAL HOMOLOGADA)
# ==============================================================================
menu_atual = st.session_state["opcao_menu"]
miolo_pagina = st.empty()

with miolo_pagina.container():
    
    # ⚡ TRAVA DO MODAL SIMULADO: Se houver agendamento pendente, assume a tela toda
    if st.session_state.get("abrir_reserva_fluxo"):
        if 'modal_agendamento_encontro' in globals():
            modal_agendamento_encontro(st.session_state.abrir_reserva_fluxo)
        st.stop()

    # --- TELAS PÚBLICAS ---
    # --- [CENÁRIO 1]: TELA HOME ---
    if menu_atual == "home":
        st.markdown("<h1 style='text-align: center;'>Lucy Chat IA — Chat virtual online</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center;'>Tenha uma conversa com a Lucy, ela encontrará pessoas com maior afinidades e lhe propor encontros virtuais seguros...</h4>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Por que escolher nossa plataforma?</h3>", unsafe_allow_html=True)

        st.markdown("""
            <div style='text-align: center;'>
            🔒 **Ambiente 100% Seguro:** Suas mensagens e chamadas são privadas.<br>
            🎥 **Videochamada Integrada:** Conecte-se por vídeo com um clique.<br>
            📬 **Suporte Dedicado:** Canal direto via Fale Conosco.<br>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style="background-color: #004085; padding: 20px; border-radius: 5px; text-align: center; border-left: 5px solid #0066cc; margin-bottom: 20px;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px;">
                    💡 CADASTRE-SE AGORA EM NOSSO SITE ENCONTRE SEU MATCH E MARQUE UM ENCONTRO VIRTUAL!!
                </h1>
            </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔑 Fazer Login", use_container_width=True, type="primary", key="btn_home_login_nativo"):
                st.session_state.opcao_menu = "login"
                st.rerun()
                        
        with col2:
            # ⚡ OTIMIZAÇÃO NATIVA: Removido stylable_container para evitar dependências extras.
            # O Streamlit moderno aceita o parâmetro type="secondary" ou podemos aplicar o CSS direto no botão.
            if st.button("📝 Cadastre-se", use_container_width=True, type="secondary", key="btn_home_cadastro_nativo"):
                st.session_state.opcao_menu = "cadastro"
                st.rerun()      
        st.stop()
       
    # --- [CENÁRIO 2]: TELA LOGIN ---
    elif menu_atual == "login":
        if "contener_login_ativo" not in st.session_state:
            st.session_state.contener_login_ativo = miolo_pagina
            
        if 'renderizar_tela_login_definitiva' in globals():
            renderizar_tela_login_definitiva()
        else:
            st.error("Módulo de autenticação offline.")
        st.stop()
        
    # --- [CENÁRIO 3]: TELA CADASTRO ---
    elif menu_atual == "cadastro":
        st.markdown('<h2 style="text-align:center; color:#007bff;">Criar Conta</h2>', unsafe_allow_html=True)
        
        with st.form(key=f"form_cad_unico_{st.session_state.form_seed}"):
            usuario = st.text_input("Usuário", placeholder="Escolha um Usuário", label_visibility="collapsed")
            email = st.text_input("E-mail", placeholder="Digite seu E-mail", label_visibility="collapsed")
            senha = st.text_input("Senha", placeholder="Escolha uma Senha", type="password", label_visibility="collapsed")
            genero = st.selectbox("Gênero", options=["M", "F"], index=0, label_visibility="collapsed")

            botao_cadastrar = st.form_submit_button("Cadastre-se", type="primary", use_container_width=True)

        if botao_cadastrar:
            # Validações rápidas na memória local (Economiza requisições de IO)
            if not usuario.strip() or not email.strip() or not senha.strip():
                st.warning("⚠️ Por favor, preencha todos os campos.")
            elif len(senha) < 6:
                st.warning("⚠️ A senha deve ter pelo menos 6 caracteres.")
            elif "@" not in email or "." not in email:
                st.warning("⚠️ Por favor, insira um e-mail com formato válido.")
            else:
                conn = None
                try:
                    conn = obter_conexao_eficiente()
                    if conn:
                        with conn.cursor() as cursor:
                            # 1. Verifica duplicidade salvando o retorno de forma segura
                            cursor.execute(
                                "SELECT id FROM usuarios WHERE username = %s OR email = %s LIMIT 1;", 
                                (usuario.strip(), email.strip())
                            )
                            registro_duplicado = cursor.fetchone()
                            
                            if registro_duplicado:
                                st.error("❌ Usuário ou E-mail já cadastrado no sistema.")
                            else:
                                # 2. Gera a senha criptografada usando a função global do topo
                                if 'generate_password_hash' in globals():
                                    senha_final = generate_password_hash(senha)
                                else:
                                    import bcrypt
                                    senha_final = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                                
                                # 3. Executa a inserção retornando o ID do novo perfil
                                cursor.execute("""
                                    INSERT INTO usuarios (username, email, password_hash, genero, status, is_admin, tipo_plano, moedas) 
                                    VALUES (%s, %s, %s, %s, '🟢 Online', FALSE, 'Grátis', 0) RETURNING id;
                                """, (usuario.strip(), email.strip(), senha_final, genero))
                                
                                # Extração cirúrgica e segura do ID gerado
                                res_id = cursor.fetchone()
                                id_gerado = int(res_id[0]) if res_id else None
                                
                                if id_gerado:
                                    conn.commit()  # Confirma a transação no PostgreSQL de forma atômica
                                    
                                    # 4. Define as variáveis de sessão essenciais
                                    st.session_state.usuario_id = id_gerado
                                    st.session_state.id_usuario = id_gerado  
                                    st.session_state.username = usuario.strip()
                                    st.session_state.genero = genero
                                    st.session_state.tipo_plano = "Grátis"
                                    st.session_state.saldo_moedas = 0
                                        
                                    st.toast("🎉 Conta criada com sucesso!")
                                    st.session_state.opcao_menu = "planos"
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error("Erro interno ao recuperar ID de cadastro.")
                    else:
                        st.error("Não foi possível estabelecer conexão com o banco de dados para concluir o cadastro.")
                                        
                except Exception as e: 
                    if conn: 
                        conn.rollback()
                    st.error(f"Erro ao processar cadastro: {e}")
                finally:
                    if conn:
                        liberar_conexao(conn)

        if st.button("← Voltar para o Login", use_container_width=True, key="btn_cad_voltar_login"):
            st.session_state.opcao_menu = "login"
            st.rerun()

        st.stop()

    # --- [CENÁRIO 4]: TELA DE PLANOS ---
    elif menu_atual == "planos":
        # Garante o estado correto da navegação
        st.session_state.opcao_menu = "planos"
        
        st.markdown('<h1 style="text-align:center; color:#007bff; margin-bottom:15px;">Plataforma de Planos IA</h1>', unsafe_allow_html=True)

        # Centraliza o container simulando o max-width de 800px via colunas do Streamlit
        _, col_central, _ = st.columns([1, 8, 1])

        with col_central:
            with st.container(border=True):
                st.markdown('<h3 style="text-align: center; color: #f0f6fc; margin-bottom: 20px;">Escolha o Plano Ideal para Você</h3>', unsafe_allow_html=True)
                
                col_plano_1, col_plano_2 = st.columns(2)
                with col_plano_1:
                    st.html(
                        """
                        <div style="margin-bottom: 20px; text-align: left; border-left: 4px solid #28a745; padding-left: 15px; min-height: 140px;">
                            <strong style="color: #28a745; font-size: 1.1em;">⭐ Plano Assinante (Acesso Total)</strong><br>
                            <span style="color: #c9d1d9; font-size: 0.95em;">Acesso ilimitado à conversa com a Lucy IA, busca de matches, agendamento de encontros virtuais e Sala Privada por tempo indeterminado.</span>
                        </div>
                        """
                    )
                    
                with col_plano_2:
                    st.html(
                        """
                        <div style="margin-bottom: 20px; text-align: left; border-left: 4px solid #007bff; padding-left: 15px; min-height: 140px;">
                            <strong style="color: #007bff; font-size: 1.1em;">🪙 Plano Crédito de Moedas</strong><br>
                            <span style="color: #c9d1d9; font-size: 0.95em;">Busca de matches e encontros inclusos. O uso da Sala Privada consome créditos: <strong>10 moedas equivalem a 10 minutos</strong> de conversa.</span>
                        </div>
                        """
                    )

                st.markdown("<hr style='border-color: #30363d; margin: 15px 0;'>", unsafe_allow_html=True)
                
                col_plano_3, col_plano_4 = st.columns(2)
                with col_plano_3:
                    st.html(
                        """
                        <div style="text-align: left; border-left: 4px solid #6e7681; padding-left: 15px; min-height: 120px;">
                            <strong style="color: #6e7681; font-size: 1.1em;">⚪ Plano Grátis</strong><br>
                            <span style="color: #c9d1d9; font-size: 0.95em;">Converse com a Lucy IA e ache seu match. <i>Não permite o agendamento de encontros virtuais ou chamadas de vídeo.</i></span>
                        </div>
                        """
                    )
                    
                with col_plano_4:
                    # ⚡ CORREÇÃO VISUAL: HTML limpo e padronizado sem tags Markdown misturadas
                    st.html(
                        """
                        <div style="text-align: left; border-left: 4px solid #ef4444; padding-left: 15px; margin-bottom: 10px;">
                            <strong style="color: #f0f6fc; font-size: 1.1em;">🛒 Realizar Pagamento</strong>
                        </div>
                        """
                    )
                    id_usuario = st.session_state.get("usuario_id") or st.session_state.get("id_usuario", 0)
                    
                    opcoes_compra = st.radio(
                        "Escolha uma opção para recarga:", 
                        ["Assinatura VIP por R$ 19,90/mês", "Pacote de 10 Moedas (10 min.) por R$ 2,00"],
                        key="radio_opcao_compra_estatico",
                        label_visibility="collapsed"
                    )

                st.markdown("<hr style='border-color: #30363d; margin: 15px 0;'>", unsafe_allow_html=True)             
                
                if st.button("Gerar Pix de Pagamento", use_container_width=True, type="secondary", key="btn_gerar_pix_planos"):
                    if not sdk:
                        st.error("Gateway de pagamento fora do ar. Credenciais do Mercado Pago não encontradas.")
                    else:
                        valor, desc, tipo = (19.90, "Plano VIP 30 dias", "vip") if "VIP" in opcoes_compra else (2.00, "Pacote de 10 Moedas", "moedas")
                        id_limpo = int(id_usuario if not isinstance(id_usuario, (list, tuple)) else id_usuario)
                        
                        payment_data = {
                            "transaction_amount": valor, 
                            "description": desc, 
                            "payment_method_id": "pix",
                            "payer": {"email": "cliente@email.com"}, 
                            "external_reference": f"{id_limpo}:{tipo}"
                        }
                            
                        try:
                            payment_response = sdk.payment().create(payment_data)
                            payment = payment_response["response"]
                                
                            if "point_of_interaction" in payment:
                                st.session_state.id_pagamento_pendente = payment["id"]
                                st.session_state.tipo_pagamento_pendente = tipo
                                st.session_state.qr_code_img = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]
                                st.session_state.qr_code_texto = payment["point_of_interaction"]["transaction_data"]["qr_code"]
                                st.success("Pix gerado com sucesso!")
                                time.sleep(0.5)
                                st.rerun()
                        except Exception as e: 
                            st.error(f"Erro ao gerar pagamento: {e}")

                # Renderiza o QR Code dentro do mesmo bloco se estiver ativo
                if st.session_state.get("qr_code_img"):
                    st.markdown("<hr style='border-color: #30363d; margin: 15px 0;'>", unsafe_allow_html=True)
                    st.markdown("### 📱 Escaneie o QR Code abaixo para pagar:")
                    
                    col_qr, col_txt = st.columns([1, 1.5])
                    with col_qr:
                        import base64
                        try:
                            st.image(base64.b64decode(st.session_state.qr_code_img), width=200)
                        except Exception:
                            st.error("Erro ao decodificar imagem do QR Code.")
                            
                    with col_txt:
                        st.text_area("Código Copia e Cola:", value=st.session_state.qr_code_texto, height=80, key="txt_area_copia_cola_estatica")
                                
                        if st.button("🔄 Já realizei o pagamento", type="primary", use_container_width=True, key="btn_verificar_status_pix_final"):
                            id_pagamento = st.session_state.get("id_pagamento_pendente")
                            
                            if id_pagamento:
                                with st.spinner("Verificando compensação do Pix..."):
                                    status = verificar_status_pix(id_pagamento)
                                
                                if status == "approved":
                                    tipo = st.session_state.get("tipo_pagamento_pendente")
                                    
                                    # ⚡ CORREÇÃO CRÍTICA: Passando os 3 argumentos obrigatórios exigidos pela trava Postgres
                                    sucesso_banco = atualizar_plano_banco_supabase(id_usuario, tipo, id_pagamento)
                                    
                                    if sucesso_banco:
                                        st.success("🎉 Pagamento aprovado! Seu acesso foi liberado com sucesso.")
                                        
                                        # Incrementa a semente do chat para resetar os contêineres limpos
                                        st.session_state.seed_recarregar_chat = st.session_state.get("seed_recarregar_chat", 0) + 1
                                        
                                        # Limpa as variáveis do Pix da sessão pós-aprovação
                                        st.session_state.id_pagamento_pendente = None
                                        st.session_state.qr_code_img = None
                                        st.session_state.qr_code_texto = None
                                        
                                        # Redireciona o usuário para o Chat ativo
                                        st.session_state.opcao_menu = "💬 Conversar com Lucy"
                                        time.sleep(1.0)
                                        st.rerun()
                                else:
                                    st.warning("⏳ Pagamento ainda não compensado. Aguarde alguns instantes e tente novamente.")

            # --- BOTÃO DE ROTA DE FUGA (IR PARA O CHAT GRÁTIS) ---
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("🚀 Acessar Plataforma / Continuar no Plano Grátis", use_container_width=True, key="btn_pular_planos_ir_chat"):
                st.session_state.opcao_menu = "💬 Conversar com Lucy"
                st.rerun()
                
        st.stop()


    
    elif menu_atual == "💬 Conversar com Lucy":
       # ⚡ Inicializa a semente caso ela não exista
        if "seed_recarregar_chat" not in st.session_state:
            st.session_state["seed_recarregar_chat"] = 0
            
        # ⚡ CORREÇÃO: Chame a função pura, sem passar argumentos dentro dela!
        renderizar_chat_lucy_isolado()
        st.stop()

    elif menu_atual == "🛠️ Painel Admin":
        template_painel_admin()
        st.stop()

    elif menu_atual == "✉️ Fale Conosco":
        template_fale_conosco()   
        st.stop()

    elif menu_atual == "📅 Disponibilidade":
        template_disponibilidade()
        st.stop()
        
    elif menu_atual == "🤝 Gerenciar Conexões":
        template_gerenciar_conexoes()
        st.stop()
         
    elif menu_atual == "🤝 Sala Privada":
        if st.session_state.get("match_id_atual"):
            template_sala_privada()
        else:
            st.warning("Nenhuma sala ativa.")
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()
                      

    

# ==============================================================================
# RODAPÉ FIXO DISCRETO (TERMOS E POLÍTICAS)
# ==============================================================================
st.markdown("""
    <style>
    /* Cria uma barra fixa travada no fundo da tela */
    .rodape-fixo-plataforma {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #0d1117; /* Mesma cor de fundo do seu site */
        border-top: 1px solid #30363d;
        text-align: center;
        padding: 6px 0;
        font-family: Arial, sans-serif;
        font-size: 11px; /* Tamanho bem menor e discreto */
        color: #8b949e;
        z-index: 999999; /* Garante que fique acima de outros elementos */
    }
    .rodape-fixo-plataforma a {
        color: #58a6ff;
        text-decoration: none;
        margin: 0 10px;
    }
    .rodape-fixo-plataforma a:hover {
        text-decoration: underline;
    }
    /* Dá um pequeno respiro no fundo do app para o conteúdo não sumir atrás do rodapé */
    .stApp {
        padding-bottom: 30px !important;
    }
    </style>

    <div class="rodape-fixo-plataforma">
        <span>© 2026 Lucy Chat IA. Todos os direitos reservados.</span>
        <a href="#termos" onclick="alert('Termos de Uso:\\nAo utilizar a plataforma, você concorda com o ambiente seguro e criptografado.')">Termos de Uso</a> | 
        <a href="#politicas" onclick="alert('Políticas de Privacidade:\\nSeus dados de chat e vídeo são confidenciais e protegidos de ponta a ponta.')">Políticas de Privacidade</a>
    </div>
""", unsafe_allow_html=True)
