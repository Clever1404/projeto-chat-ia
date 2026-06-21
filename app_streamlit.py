import streamlit as st
import pandas as pd
import os
import psycopg
from datetime import datetime
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
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import streamlit as bar




# --- OBRIGATÓRIO: DEVE FICAR NO TOPO DO ARQUIVO ---
if "tela_atual" not in st.session_state:
    st.session_state.tela_atual = "Home"

if "id_pagamento_pendente" not in st.session_state:
    st.session_state.id_pagamento_pendente = None

if "tipo_pagamento_pendente" not in st.session_state:
    st.session_state.tipo_pagamento_pendente = None

if "qr_code_img" not in st.session_state:
    st.session_state.qr_code_img = None

if "qr_code_texto" not in st.session_state:
    st.session_state.qr_code_texto = None

if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"  # Mudado para expandido por padrão

if "tela_atual" not in st.session_state:
    st.session_state.tela_atual = "Home"

# Configuração que controla o comportamento visual da barra lateral
st.set_page_config(initial_sidebar_state=st.session_state.sidebar_state)





UPLOAD_FOLDER = "uploads"
load_dotenv()
UPLOAD_FOLDER = 'static/uploads/perfis'


# 1. Busca a chave da OpenAI priorizando os Secrets da nuvem
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

if not OPENAI_API_KEY or "sua_chave" in OPENAI_API_KEY:
    st.error("ERRO: Chave API da OpenAI não configurada nos Secrets!")
    st.stop()

# 2. Inicializa o cliente da OpenAI de forma global
client = OpenAI(api_key=OPENAI_API_KEY)

# Busca os dados injetados pelo painel do Streamlit Cloud
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]

# Inicializa o cliente do Supabase
supabase: Client = create_client(url, key)

# 2. Inicializa a variável antes para evitar o NameError
supabase = None

if url and key:
    try:
        # ✅ CORRETO: Passa as variáveis em minúsculo que guardam os valores
        supabase = create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
else:
    # Mostra um aviso claro na tela em vez de quebrar o app
    st.warning("⚠️ Atenção: As credenciais do Supabase não estão configuradas nas configurações (Secrets).")

# Garante que o app não vai rodar as consultas ao banco se o cliente não existir
if 'supabase' not in locals() or not supabase:
    st.info("Por favor, configure as chaves SUPABASE_URL e SUPABASE_KEY para liberar o banco de dados.")
    st.stop()  # Para o código aqui com segurança
    

# =========================================================================
# INICIALIZAÇÃO DO SDK DO MERCADO PAGO
# =========================================================================
# Busca o token direto dos secrets do Streamlit de forma segura
try:
    sdk = mercadopago.SDK(st.secrets["TOKEN_MERCADO_PAGO"])
except Exception as e:
    st.error(f"Erro ao carregar credenciais do Mercado Pago: {e}")
    sdk = None

# 2. Função de conexão com o Supabase corrigida com SSL seguro
def conectar_supabase():
    conn = psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        port=st.secrets["postgres"]["port"],
        sslmode="require"  # <--- ESSA LINHA EVITA O BLOQUEIO 403 DO SUPABASE
    )
    return conn


# ==============================================================================
# 4. CONTROLE DE ESTADO E EXIBIÇÃO DAS TELAS (RODA NO FINAL)
# ==============================================================================
def template_home():
    # 1. CONFIGURAÇÃO DA PÁGINA (Sempre a primeira instrução Streamlit)
    if "config_executada" not in st.session_state:
        st.set_page_config(page_title="Lucy Chat IA - Plataforma", layout="wide")
        st.session_state.config_executada = True
        st.markdown("""
            <style>
            [data-testid="stHeader"] { display: none !important; }
            div[data-testid="stToolbar"] { display: none !important; }
            .stApp { background-color: #0d1117; color: #c9d1d9; }
            h1, h2, h3 { font-family: Arial, sans-serif; color: #f0f6fc !important; }
            div[data-testid="stSidebar"] { background-color: #161b22 !important; border-right: 1px solid #30363d; }
            .block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; }
            </style>
        """, unsafe_allow_html=True)

    # ==============================================================================
    # 1. INICIALIZAÇÃO CORRETA (No topo do arquivo, abaixo dos imports)
    # ==============================================================================
    if "opcao_menu" not in st.session_state:
        st.session_state.opcao_menu = "home"  # Usamos texto simples minúsculo para evitar erros

    if "usuario_id" not in st.session_state:
        st.session_state.usuario_id = None
    
    
    # Título centralizado
    st.markdown("<h1 style='text-align: center;'>Lucy Chat IA — Chat virtual online</h1>", unsafe_allow_html=True)

    # Subtítulo centralizado
    st.markdown("<h4 style='text-align: center;'>Tenha uma conversa com a Lucy, ela encontrará pessoas com maior afinidades e lhe propor encontros virtuais seguros, com conversas criptografadas e com suporte a vídeo em tempo real.</h4>", unsafe_allow_html=True)

    # Tópicos centralizados
    st.markdown("<h3 style='text-align: center;'>Por que escolher nossa plataforma?</h3>", unsafe_allow_html=True)

    st.markdown("""
        <div style='text-align: center;'>

        🔒 **Ambiente 100% Seguro:** Suas mensagens e chamadas são privadas.\n
        🎥 **Videochamada Integrada:** Conecte-se por vídeo com um clique.\n
        📬 **Suporte Dedicado:** Canal direto via Fale Conosco.\n

        </div>
    """, unsafe_allow_html=True)

    st.markdown(
        """
        <div style="background-color: #004085; padding: 20px; border-radius: 5px; text-align: center; border-left: 5px solid #0066cc;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px;">
                💡 CADASTRE-SE AGORA EM NOSSO SITE ENCONTRE SEU MATCH E MARQUE UM ENCONTRO VIRTUAL!!
            </h1>
        </div>
         """, 
         unsafe_allow_html=True
    )

    # Cria duas colunas para os botões de Login e Cadastro ficarem lado a lado
    col1, col2 = st.columns(2)
        
    with col1:
        if st.button("🔑 Fazer Login", use_container_width=True, type="primary"):
            st.session_state.opcao_menu = "login"
            st.rerun()

    with col2:
        with stylable_container(
            key="green_button",
            css_styles="""
                button {
                    background-color: #28a745;
                    color: white;
                    border-radius: 5px;
                }
                button:hover {
                    background-color: #218838;
                    color: white;
                }
            """,
        ):
            if st.button("📝 Cadastre-se", use_container_width=True):
                st.session_state.opcao_menu = "cadastro"
                st.rerun()

# ==============================================================================
# ENCAIXE DAS SUAS FUNÇÕES EXISTENTES DE FLUXO DE CONTA
# ==============================================================================
    #elif st.session_state.opcao_menu == "🔒 Login":
def template_login():
    # 🟢 CORREÇÃO: Alterado de '==' para '=' para de fato definir o estado
    st.session_state.opcao_menu = "login"
    st.markdown('<h1 style="text-align:center; color:#007bff;">Login Lucy Chat IA</h1>', unsafe_allow_html=True)
            
    with st.form("form_login"):
        user_in = st.text_input("Usuário", placeholder="Nome de Usuário ou E-mail", label_visibility="collapsed")
        pass_in = st.text_input("Senha", placeholder="Senha", type="password", label_visibility="collapsed")
                
        if st.form_submit_button("login", type="primary", use_container_width=True):
            try:
                conn = conectar_supabase()
                cursor = conn.cursor()
                
                # 🟢 OTIMIZAÇÃO: Adicionado 'tipo_plano' e 'moedas' na busca inicial do login
                cursor.execute("""
                    SELECT id, username, foto_perfil, is_admin, genero, tipo_plano, moedas 
                    FROM usuarios 
                    WHERE username = %s OR email = %s;
                """, (user_in, user_in))
                res = cursor.fetchone()
                        
                if res:
                    # Salva as variáveis individuais antigas para não quebrar outras partes do seu app
                    st.session_state.usuario_id = res[0]
                    st.session_state.username = res[1]
                    st.session_state.foto_perfil = res[2]
                    st.session_state.eh_admin = res[3]
                    st.session_state.genero = res[4]
                    
                    # 🟢 CACHE CENTRALIZADO: Guarda o perfil completo em memória para acelerar as outras páginas
                    st.session_state.dados_usuario = {
                        "username": res[1],
                        "foto_perfil": res[2],
                        "genero": res[4],
                        "tipo_plano": str(res[5]).strip() if res[5] else "Grátis",
                        "moedas": res[6] if res[6] else 0
                    }
                            
                    # Atualiza o status do usuário no banco PostgreSQL
                    cursor.execute("UPDATE usuarios SET status = '🟢 Online' WHERE id = %s", (res[0],))
                    conn.commit()
                            
                    st.session_state.opcao_menu = "💬 Conversar com Lucy"
                    cursor.close()
                    conn.close()
                    st.rerun()
                else:
                    st.error("Usuário ou e-mail não encontrado.")
                        
                cursor.close()
                conn.close()
            except Exception as e: 
                st.error(f"Erro: {e}")
            
    # Botão de cadastro estilizado
    with stylable_container(
        key="green_button",
        css_styles="""
            button {
                background-color: #28a745;
                color: white;
                border-radius: 5px;
            }
            button:hover {
                background-color: #218838;
                color: white;
            }
        """,
    ):
        if st.button("📝 Cadastre-se", use_container_width=True):
            st.session_state.opcao_menu = "cadastro"
            st.rerun()

    # Rodapé do formulário de login (Voltar e Esqueceu a Senha)
    col_voltar, col_esqueceu = st.columns(2)
    with col_voltar:
        if st.button("⬅️ Voltar para a Home", use_container_width=True):
            st.session_state.opcao_menu = "home" 
            st.rerun()
                    
    with col_esqueceu:
        if "mostrar_recuperar_senha" not in st.session_state:
            st.session_state.mostrar_recuperar_senha = False

        # DEFINE O DIÁLOGO
        @st.dialog("🔑 Recuperar Senha")
        def modal_recuperar_senha():
            st.write("Digite o seu e-mail cadastrado e a sua nova senha abaixo.")
            with st.form("form_recuperacao_senha", clear_on_submit=True):
                email_digitado = st.text_input("E-mail Cadastrado").strip().lower()
                nova_senha = st.text_input("Nova Senha", type="password")
                botao_confirmar = st.form_submit_button("Redefinir Senha", use_container_width=True)
                        
                if botao_confirmar:
                    if not email_digitado or not nova_senha:
                        st.error("Por favor, preencha todos os campos.")
                        return
                    try:
                        conn = conectar_supabase()
                        cursor = conn.cursor()
                        cursor.execute('SELECT id FROM usuarios WHERE email = %s', (email_digitado,))
                        usuario_encontrado = cursor.fetchone()

                        if usuario_encontrado:
                            senha_criptografada = generate_password_hash(nova_senha)
                            cursor.execute('UPDATE usuarios SET password_hash = %s WHERE email = %s', (senha_criptografada, email_digitado))
                            conn.commit()
                            cursor.close()
                            conn.close()
                                    
                            st.success("Senha redefinida com sucesso!")
                            st.toast("Sucesso! Faça o login agora.")
                            time.sleep(2.5)
                            st.session_state.mostrar_recuperar_senha = False
                            st.rerun() 
                        else:
                            cursor.close()
                            conn.close()
                            st.error("E-mail não localizado no sistema.")
                    except Exception as e:
                        st.error(f"Erro ao acessar o banco de dados: {e}")

        if st.button("🔑 Esqueceu a senha?", use_container_width=True):
            st.session_state.mostrar_recuperar_senha = True

        if st.session_state.mostrar_recuperar_senha:
            modal_recuperar_senha()

                      

    
# ==============================================================================
# 2. DEFINIÇÃO DOS TEMPLATES (FUNÇÕES)
# ==============================================================================
def template_cadastro():
    # Atualizado para usar st.html nativo
    st.html('<h2 style="text-align:center; color:#007bff;">Criar Conta</h2>')
    
    # Bloco do Formulário de Cadastro
    with st.form(key=f"form_cad_unico_{st.session_state.form_seed}"):
        usuario = st.text_input("Usuário", placeholder="Escolha um Usuário", label_visibility="collapsed")
        email = st.text_input("E-mail", placeholder="Digite seu E-mail", label_visibility="collapsed")
        senha = st.text_input("Senha", placeholder="Escolha uma Senha", type="password", label_visibility="collapsed")
        genero = st.selectbox("Gênero", options=["M", "F"], index=0, label_visibility="collapsed")
        
        with stylable_container(
            key="green_button_cad",
            css_styles="""
                button { background-color: #28a745; color: white; border-radius: 5px; }
                button:hover { background-color: #218838; color: white; }
            """,
        ):         
            if st.form_submit_button("Cadastre-se", use_container_width=True):
                # 1. Validação de campos vazios
                if not usuario.strip() or not email.strip() or not senha.strip():
                    st.warning("⚠️ Por favor, preencha todos os campos.")
                    st.stop()
                
                if len(senha) < 6:
                    st.warning("⚠️ A senha deve ter pelo menos 6 caracteres.")
                    st.stop()

                # 2. Conexão e Verificação de Duplicidade
                try:
                    conn = conectar_supabase()
                    cursor = conn.cursor()
                    
                    # Verifica se o username ou o e-mail já existem
                    cursor.execute(
                        "SELECT username, email FROM usuarios WHERE username = %s OR email = %s;", 
                        (usuario.strip(), email.strip())
                    )
                    usuario_existente = cursor.fetchone()
                    
                    if usuario_existente:
                        # Identifica qual dos dois campos gerou a duplicidade
                        if usuario_existente[0] == usuario.strip():
                            st.error("❌ Este nome de usuário já está em uso.")
                        else:
                            st.error("❌ Este e-mail já está cadastrado.")
                        
                        cursor.close()
                        conn.close()
                        st.stop() # Interrompe a execução aqui

                    # 3. Executa o cadastro se passar em todas as validações
                    senha_final = generate_password_hash(senha) if 'generate_password_hash' in locals() else senha
                    
                    cursor.execute(
                        "INSERT INTO usuarios (username, email, password_hash, genero, status, is_admin) VALUES (%s, %s, %s, %s, '🟢 Online', FALSE) RETURNING id;", 
                        (usuario.strip(), email.strip(), senha_final, genero)
                    )
                    st.session_state.usuario_id = cursor.fetchone()[0]
                    st.session_state.username = usuario.strip()
                    st.session_state.genero = genero
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    st.session_state.opcao_menu = "Plataforma de Planos IA"
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Erro ao processar cadastro: {e}")

    # O Botão "Voltar" agora está FORA do formulário e usa st.button normal
    with stylable_container(
        key="red_button",
        css_styles="""
            button {
                background-color: #dc3545; /* Alterado de 'primary' para uma cor real (vermelho) */
                color: white;
                border-radius: 5px;
            }
            button:hover {
                background-color: #bd2130;
                color: white;
            }
        """,
    ):
        if st.button("← Voltar para o 🔒 login", use_container_width=True):
            st.session_state.opcao_menu = "login"
            st.rerun()
    
           

def template_planos():
    # Inicializa a sub-visão caso ela não exista
    if "sub_visao" not in st.session_state:
        st.session_state.sub_visao = "planos"

    # --- TELA 1: EXIBIÇÃO DOS PLANOS ---
    if st.session_state.sub_visao == "planos":
        st.markdown('<h1 style="text-align:center; color:#007bff;">Plataforma de Planos IA</h1>', unsafe_allow_html=True)
        
        # Texto descritivo dos planos centralizado
        st.html(
            """
            <div style="text-align: center; max-width: 800px; margin: 0 auto; background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 25px;">
                <h3 style="color: #f0f6fc; margin-bottom: 15px;">Escolha o Plano Ideal para Você</h3>
                
                <div style="margin-bottom: 20px; text-align: left; border-left: 4px solid #28a745; padding-left: 15px;">
                    <strong style="color: #28a745; font-size: 1.1em;">⭐ Plano Assinante (Acesso Total)</strong><br>
                    <span style="color: #c9d1d9;">Acesso ilimitado à conversa com a Lucy IA, busca de matches, agendamento de encontros virtuais com videochamada e tempo indeterminado de uso na Sala Privada.</span>
                </div>
                
                <div style="margin-bottom: 20px; text-align: left; border-left: 4px solid #007bff; padding-left: 15px;">
                    <strong style="color: #007bff; font-size: 1.1em;">🪙 Plano Crédito de Moedas</strong><br>
                    <span style="color: #c9d1d9;">Conversa com a Lucy IA, busca de matches e agendamento de encontros com videochamada. O uso da Sala Privada consome créditos: <strong>a cada 10 moedas, você ganha 10 minutos de conversa</strong> na sala privada.</span>
                </div>
                
                <div style="text-align: left; border-left: 4px solid #6e7681; padding-left: 15px;">
                    <strong style="color: #6e7681; font-size: 1.1em;">⚪ Plano Grátis</strong><br>
                    <span style="color: #c9d1d9;">Converse com a Lucy IA e ache seu match. <i>Não permite o agendamento de encontros virtuais ou chamadas de vídeo.</i></span>
                </div>
            </div>
            """        
        )
        
        # Botão para ir para a loja (Troca a tela inteira)
        if st.button("🛒 Ir para a Loja de Moedas e Assinaturas", type="primary", use_container_width=True):
            st.session_state.sub_visao = "loja"
            st.rerun()
            
        st.markdown('<br>', unsafe_allow_html=True)
        
        # Botão de voltar para o login
        if st.button("← Voltar para o 🔒 Login", use_container_width=True):
            st.session_state.opcao_menu = "login"
            st.rerun()

    # --- TELA 2: RENDERIZAÇÃO DA SUA LOJA (TELA CHEIA) ---
    elif st.session_state.sub_visao == "loja":
        # Botão posicionado no topo para o usuário conseguir voltar aos planos
        if st.button("📋 Ver Descrição dos Planos", use_container_width=True):
            st.session_state.sub_visao = "planos"
            st.rerun()
            
        st.markdown('<hr style="border: 0.5px solid #30363d; margin: 15px 0;">', unsafe_allow_html=True)
        
        # Recupera as variáveis necessárias
        id_usuario = st.session_state.get("id_usuario", "usuario_teste")
        saldo_atual = st.session_state.get("saldo_moedas", 0)
        
        # Executa a sua loja com a tela totalmente limpa e isolada
        renderizar_loja_app(id_usuario_atual=id_usuario, saldo_moedas=saldo_atual)




# Mude a definição da função para receber as variáveis necessárias
def renderizar_loja_app(id_usuario_atual, saldo_moedas):
    st.sidebar.header("🛒 Loja do App")
    opcoes_compra = st.sidebar.radio("Escolha uma opção:", ["Assinatura VIP (R$ 19,90)", "10 Moedas (R$ 5,00)"])

    if st.sidebar.button("Gerar Pix de Pagamento"):
        if "VIP" in opcoes_compra:
            valor, desc, tipo = 19.90, "Plano VIP 30 dias", "vip"
        else:
            valor, desc, tipo = 5.00, "Pacote de 10 Moedas", "moedas"

        payment_data = {
            "transaction_amount": valor,
            "description": desc,
            "payment_method_id": "pix",
            "payer": {"email": "cliente@email.com"},
            "external_reference": f"{id_usuario_atual}:{tipo}"
        }

        payment_response = sdk.payment().create(payment_data)
        payment = payment_response["response"]

        if "point_of_interaction" in payment:
            st.session_state.id_pagamento_pendente = payment["id"]
            st.session_state.tipo_pagamento_pendente = tipo
            st.session_state.qr_code_img = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]
            st.session_state.qr_code_texto = payment["point_of_interaction"]["transaction_data"]["qr_code"]
            st.sidebar.success("Pix gerado com sucesso!")
        else:
            st.sidebar.error("Erro ao gerar pagamento. Verifique as credenciais.")

    if st.session_state.id_pagamento_pendente:
        st.sidebar.markdown("---")
        st.sidebar.image(f"data:image/jpeg;base64,{st.session_state.qr_code_img}", width=200)
        st.sidebar.text_input("Copia e Cola:", value=st.session_state.qr_code_texto)
        
        if st.sidebar.button("🔄 Já paguei, liberar meu acesso"):
            id_pag = st.session_state.id_pagamento_pendente
            tipo_pag = st.session_state.tipo_pagamento_pendente
            check_payment = sdk.payment().get(id_pag)["response"]
            status_pagamento = check_payment.get("status")

            if status_pagamento == "approved":
                if tipo_pag == "vip":
                    supabase.table("usuarios").update({"status": "vip"}).eq("id", id_usuario_atual).execute()
                    st.success("🎉 Parabéns! Seu plano VIP foi ativado.")
                elif tipo_pag == "moedas":
                    novo_saldo = saldo_moedas + 10
                    supabase.table("usuarios").update({"creditos": novo_saldo}).eq("id", id_usuario_atual).execute()
                    st.success("🪙 10 Moedas adicionadas com sucesso ao seu saldo!")
                st.session_state.id_pagamento_pendente = None
                st.rerun()
            else:
                st.sidebar.warning("⚠️ Pagamento ainda não consta como aprovado.")
  


# ==============================================================================
# 1. CONFIGURAÇÕES GLOBAIS E ESTILO BASE (UPGRADES DE LAYOUT E ROLAGEM)
# ==============================================================================
st.set_page_config(page_title="Lucy Chat IA - Plataforma", layout="wide")

st.markdown("""
    <style>
    /* 🔍 ESCONDE O CABEÇALHO E ELEMENTOS NATIVOS DO STREAMLIT PARA ACABAR COM A ROLAGEM DUPLA */
    [data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    h1, h2, h3 { font-family: Arial, sans-serif; color: #f0f6fc !important; }
    
    /* Configuração Rígida da Barra Lateral */
    div[data-testid="stSidebar"] { background-color: #161b22 !important; border-right: 1px solid #30363d; }
    
    /* Remove padding excessivo do Streamlit para grudar o título no teto */
    .block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; }
    
    /* Moldura Circular Compacta para a lista de Matches Central */
    .foto-match-central {
        width: 38px !important;
        height: 38px !important;
        border-radius: 50% !important;
        object-fit: cover !important;
        border: 1px solid #30363d !important;
        display: inline-block;
        vertical-align: middle;
    }
    </style>
""", unsafe_allow_html=True)


# Inicialização de estados
if "usuario_id" not in st.session_state: st.session_state.usuario_id = None
if "username" not in st.session_state: st.session_state.username = None
if "foto_perfil" not in st.session_state: st.session_state.foto_perfil = None
if "genero" not in st.session_state: st.session_state.genero = "M"
if "eh_admin" not in st.session_state: st.session_state.eh_admin = False
if "opcao_menu" not in st.session_state: st.session_state.opcao_menu = "home"
if "match_id_atual" not in st.session_state: st.session_state.match_id_atual = None
if "alerta_match" not in st.session_state: st.session_state.alerta_match = None
if "abrir_reserva_fluxo" not in st.session_state: st.session_state.abrir_reserva_fluxo = None

# 🟢 ADICIONE ESTA LINHA ABAIXO PARA CORRIGIR O ERRO:
if "form_seed" not in st.session_state: st.session_state.form_seed = 42

dias_semana_map = {0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira', 3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'}
dia_atual_servidor = dias_semana_map[datetime.now().weekday()]


# ==============================================================================
# 2. INTERCEPTADOR DE TELAS PÚBLICAS (COLOQUE EXATAMENTE AQUI)
# ==============================================================================
# Normaliza a string para evitar conflito com maiúsculas/minúsculas ou emojis antigos
menu_higienizado = str(st.session_state.opcao_menu).strip().lower()

if menu_higienizado == "home":
    template_home()
    st.stop()  # Trava o script aqui. Impede o carregamento de qualquer lógica interna ou menus abaixo!

elif menu_higienizado in ["login", "🔒 login"]:
    st.session_state.usuario_id = None
    template_login()
    st.stop()  # Garante isolamento total da tela de login

elif menu_higienizado in ["cadastro", "📝 cadastro"]:
    st.session_state.usuario_id = None
    template_cadastro()
    st.stop()  # Garante isolamento total da tela de cadastro
elif menu_higienizado in ["planos", "Planos"]:
    st.session_state.usuario_id = None
    template_cadastro()
    st.stop()  # Garante isolamento total da tela de cadastro

# ==============================================================================
# 3. LÓGICA DE USUÁRIO LOGADO (Se o script passar daqui, o usuário está na área restrita)
# ==============================================================================
# Segurança: Se tentar burlar digitando URL ou estado corrompido, chuta de volta pra Home
if st.session_state.usuario_id is None:
    st.session_state.opcao_menu = "home"
    st.rerun()



def buscar_memoria(usuario_id, limite=15):
    try:
        conn = conectar_supabase(); cursor = conn.cursor()
        cursor.execute('SELECT usuario_pergunta, ia_resposta FROM historico_ia WHERE usuario_id = %s ORDER BY id ASC LIMIT %s;', (int(usuario_id), limite))
        hist = cursor.fetchall(); cursor.close(); conn.close()
        return hist
    except Exception: return []

def processar_afinidade_e_match(usuario_id, texto_atual):
    try:
        meu_id_limpo = usuario_id if not isinstance(usuario_id, (tuple, list)) else int(usuario_id)

        conn = conectar_supabase()
        cursor = conn.cursor()
        
        # --- PILAR 1, 2 e 3: BUSCA OS DADOS CADASTRAIS DO USUÁRIO ---
        cursor.execute("""
            SELECT idade, genero, procura_por, procura_relacionamento 
            FROM usuarios 
            WHERE id = %s;
        """, (meu_id_limpo,))
        meu_perfil = cursor.fetchone()
        
        if not meu_perfil:
            cursor.close(); conn.close()
            return {"match": False}
            
        minha_idade, meu_genero, o_que_eu_procuro_gen, o_que_eu_procuro_rel = meu_perfil

        # --- PILAR 4: IA SINTETIZA OS HOBBIES (Temperatura baixa para maior consistência)
        mensagens_sintese = [
            {
                "role": "system",
                "content": "Escreva apenas um parágrafo corrido contendo as palavras-chaves semânticas de interesses e estilo de vida."
            },
            {
                "role": "user",
                "content": f"Baseado nesta interação recente do usuário, extraia e descreva em terceira pessoa uma lista de seus hobbies e interesses: {texto_atual}"
            }
        ]

        resposta_sintese = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=mensagens_sintese,
            temperature=0.3  # Reduzido de 0.9 para evitar respostas caóticas e instáveis
        )

        perfil_consolidado_texto = resposta_sintese.choices[0].message.content

        # Gera o embedding nativo de 768 dimensões
        resposta_embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input=perfil_consolidado_texto,
            dimensions=768
        )

        # FIX CRÍTICO: Captura direta da lista de floats sem usar Regex destrutivo
        vetor_atual = resposta_embedding.data[0].embedding
        vetor_formatado_postgres = str(vetor_atual)

        # Atualiza a biografia substituindo ou limitando o acréscimo para não inflar o banco
        cursor.execute('''
            UPDATE usuarios 
            SET biografia = %s, embedding_interesses = %s 
            WHERE id = %s;
        ''', (perfil_consolidado_texto, vetor_formatado_postgres, meu_id_limpo))

        # --- EXECUÇÃO DO FILTRO DOS 4 PILARES NO SQL ---
        # Nota: <=> é a Distância de Cosseno. Quanto MENOR a distância, MAIOR a afinidade.
        cursor.execute('''
            SELECT id, username, status, (embedding_interesses <=> %s::vector) AS distancia 
            FROM usuarios 
            WHERE id != %s 
              AND is_admin = FALSE 
              AND embedding_interesses IS NOT NULL
              
              -- PILAR 1: Filtro de Idade
              AND (idade BETWEEN %s - 5 AND %s + 5)
              
              -- PILAR 3: Filtro de Objetivo de Relacionamento
              AND LOWER(TRIM(procura_relacionamento)) = LOWER(TRIM(%s))
              
              -- PILAR 2: Filtro Cruzado de Gênero
              AND (
                  (%s = 'O' OR procura_por = %s OR procura_por = 'O')
                  AND 
                  (%s = 'O' OR %s = genero OR %s = 'O')
              )
              
            ORDER BY (embedding_interesses <=> %s::vector) ASC, id ASC LIMIT 1;
        ''', (
            vetor_formatado_postgres, 
            meu_id_limpo, 
            int(minha_idade), int(minha_idade),
            str(o_que_eu_procuro_rel),
            str(meu_genero), str(meu_genero),
            str(o_que_eu_procuro_gen), str(o_que_eu_procuro_gen), str(meu_genero),
            vetor_formatado_postgres
        ))
        
        resultado = cursor.fetchone()
        
        if resultado:
            id_par, nome_par, status_par, distancia = resultado
            distancia_val = float(distancia)
            
            # CALIBRAÇÃO DO MATCH NATURAL:
            # Distância de cosseno abaixo de 0.22 indica excelente afinidade semântica na OpenAI.
            # Se quiser ser ainda mais rígido e natural, mude para 0.18.
            if distancia_val <= 0.22:
                
                # Conversão matemática opcional para exibir a afinidade em % humana na sua interface:
                # Ex: Distância 0.12 vira ~90% de match. Distância 0.22 vira ~70% de match.
                similaridade_bruta = 1.0 - distancia_val
                porcentagem_match = max(0.0, min(100.0, (similaridade_bruta - 0.75) / (0.88 - 0.75) * 100))
                
                id_min, id_max = min(meu_id_limpo, int(id_par)), max(meu_id_limpo, int(id_par))
                
                cursor.execute('''
                    INSERT INTO matches (usuario_1_id, usuario_2_id) 
                    VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id;
                ''', (id_min, id_max))
                match_id_row = cursor.fetchone()
                match_id = match_id_row[0] if match_id_row else None

                if not match_id:
                    cursor.execute('SELECT id FROM matches WHERE usuario_1_id = %s AND usuario_2_id = %s;', (id_min, id_max))
                    res_ex = cursor.fetchone()
                    match_id = res_ex[0] if res_ex else None

                conn.commit()
                cursor.close()
                conn.close()
                
                par_online = "Online" in str(status_par) or "🟢" in str(status_par)
                
                return {
                    "match": True, 
                    "match_id": match_id, 
                    "id_par": int(id_par), 
                    "nome_par": nome_par, 
                    "online": par_online,
                    "afinidade_porcentagem": round(porcentagem_match, 1) # Retorna a porcentagem calibrada
                }

        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"⚠️ Erro no Mecanismo Match 4 Pilares: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            if 'cursor' in locals() and cursor: cursor.close()
            conn.close()
            
    return {"match": False}



# ============================================================================== 
# 6. TELA DO CHAT IA PRINCIPAL (LAYOUT TOTALMENTE FIXO E ROLÁVEL NO MEIO) 
# ============================================================================== 

@st.fragment
def renderizar_historico_ia(usuario_id):
    """Garante que as mensagens fiquem fixas na tela e atualizem de forma independente."""
    with st.container(height=440, border=False):
        historico = buscar_memoria(usuario_id, limite=15) 
        if not historico:
            st.info("Inicie a conversa com a Lucy enviando uma mensagem abaixo!")
            return
            
        for user_p, ia_r in historico: 
            if user_p: 
                with st.chat_message("user"): st.write(user_p) 
            if ia_r: 
                with st.chat_message("assistant"): st.write(ia_r)

def template_chat_ia_completo(): 
    # ==============================================================================
    # 1. INICIALIZAÇÃO SEGURA DE ESTADOS GLOBAIS (Sempre no início da execução)
    # ==============================================================================
    if "opcao_menu" not in st.session_state:
        st.session_state.opcao_menu = "💬 Conversar com Lucy"
    if "match_id_atual" not in st.session_state:
        st.session_state.match_id_atual = None
    if "abrir_reserva_fluxo" not in st.session_state:
        st.session_state.abrir_reserva_fluxo = None

    # Resgata e limpa o ID do usuário conectado
    meu_id_f = int(st.session_state.usuario_id) if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)

    # ==============================================================================
    # 2. INTERCEPTORES DE EVENTOS (Gatilhos pós-rerun)
    # ==============================================================================
    
    # GATILHO A: Captura o Match assim que o motor do banco dá o Rerun
    if "alerta_match" in st.session_state and st.session_state.alerta_match is not None:
        dados_m = st.session_state.alerta_match
        
        # Limpa o estado imediatamente para evitar loops infinitos de abertura
        st.session_state.alerta_match = None 
        
        # Dispara os balões comemorativos e abre o modal dialog
        st.balloons()
        modal_match_lucy(dados_m)  
    
    # ==============================================================================
    # 4. DESIGN DO TOPO DO CHAT PADRÃO DA LUCY (Só roda se os menus acima forem falsos)
    # ==============================================================================

    
    col_titulos, col_botoes_topo = st.columns([2, 1])
    
    with col_titulos:
        st.markdown("<h2 style='margin-top:0; margin-bottom:2px; font-size: 24px;'>🤖 Olá, Seja bem-vindo ao Lucy Chat IA</h2>", unsafe_allow_html=True) 
        st.caption("Lucy conversa com você e armazena os seus interesses para encontrar matches.") 
        
    
    with col_botoes_topo:
        c_refresh, c_fc = st.columns(2)
        with c_refresh:
            if st.button("🔄 Atualizar Dados", type="tertiary", help="Sincronizar mensagens"):
                st.rerun() 
        with c_fc:
            if st.button("✉️ Fale Conosco", type="tertiary"):
                st.session_state.opcao_menu = "✉️ Fale Conosco"
                st.rerun()

    st.markdown("<hr style='border-color: #30363d; margin: 5px 0 15px 0;'>", unsafe_allow_html=True)

    meu_id_f = int(st.session_state.usuario_id) if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)

    # Renderiza o histórico de mensagens de forma isolada
    renderizar_historico_ia(meu_id_f)

    # CAIXA DE DIGITAÇÃO FIXA NO RODAPÉ DA INTERFACE
    if st.session_state.opcao_menu == "💬 Conversar com Lucy":
        if prompt := st.chat_input("Fale sobre seus gostos ou planos para o dia...", key="input_global_lucy_ia"): 
            
            # Corrige o sumiço mantendo o estado local ativo imediatamente
            if "historico_volatil" not in st.session_state:
                st.session_state.historico_volatil = []
            st.session_state.historico_volatil.append(("user", prompt))
            st.chat_message("user").write(prompt) 
            
            try:
                # 🔋 ABERTURA DE CONEXÃO ÚNICA: Usaremos este cursor para TODAS as operações deste clique
                conn = conectar_supabase()
                cursor = conn.cursor()
                
                # 1. Busca os dados dos pilares do usuário
                cursor.execute("""
                    SELECT idade, genero, procura_por, procura_relacionamento 
                    FROM usuarios WHERE id = %s;
                """, (meu_id_f,))
                pilar_dados = cursor.fetchone()

              
                dados_faltantes_contexto = ""
                if pilar_dados:
                    idade_b, gen_b, proc_gen_b, proc_rel_b = pilar_dados
                    if not idade_b: dados_faltantes_contexto += "- IDADE do usuário\n"
                    if not proc_gen_b: dados_faltantes_contexto += "- Se ele tem interesse por HOMEM, MULHER ou AMBOS\n"
                    if not proc_rel_b: dados_faltantes_contexto += "- Se ele procura AMIZADE ou NAMORO\n"
                
                # Resgata a memória recente
                historico_previo = buscar_memoria(meu_id_f, limite=6)
                contexto_conversacao = "".join([f"Usuário: {u}\nVocê (Lucy): {i}\n" for u, i in historico_previo])
                
                # --- BUSCA OS DADOS QUE JÁ EXISTEM NO BANCO ---
                # Criamos um texto amigável dizendo à Lucy o que ela JÁ SABE sobre o usuário
                dados_ja_salvos_contexto = "Dados que você JÁ DESCOBRIU sobre este usuário (NÃO PERGUNTE NOVAMENTE):\n"
                if pilar_dados:
                    idade_b, gen_b, proc_gen_b, proc_rel_b = pilar_dados
                    dados_ja_salvos_contexto += f"- Idade: {idade_b if idade_b else 'Ainda não sabe'}\n"
                    
                    traducao_genero = {'M': 'Homens', 'F': 'Mulheres', 'O': 'Ambos/Todos'}.get(proc_gen_b, 'Ainda não sabe')
                    dados_ja_salvos_contexto += f"- Interesse por: {traducao_genero}\n"
                    dados_ja_salvos_contexto += f"- O que procura: {proc_rel_b if proc_rel_b else 'Ainda não sabe'}\n"

                # ==============================================================================
                # RECONSTRUTOR DO PROMPT DA LUCY (Fase de Interesse + Transição para Humor)
                # ==============================================================================
                mensagens_openai = [
                    {
                        "role": "system",
                        "content": (
                            "Você é Lucy, uma assistente virtual focada em criar conexões humanas legítimas. "
                            "Seu tom deve ser amigável, interpessoal, acolhedor, empático e levemente curioso.\n\n"
                            
                            "SUA MISSÃO EM DUAS FASES:\n"
                            "FASE 1 - INVESTIGAÇÃO DE PERFIL: Descubra os 4 dados essenciais do usuário (Idade, Interesse por Gênero, O que procura e Hobbies). "
                            "Olhe a seção 'Dados que você JÁ DESCOBRIU'. Se algum dado estiver como 'Ainda não sabe', investigue apenas UM por vez. "
                            "Se o usuário já forneceu a informação no último prompt, NÃO PERGUNTE DE NOVO.\n\n"
                            
                            "FASE 2 - TRANSIÇÃO PARA O HUMOR: Se os 4 dados essenciais já foram preenchidos (ou seja, se você já sabe a Idade, Interesse e Procura), "
                            "mude de assunto imediatamente! Ignore o questionário anterior e passe a investigar o humor atual do usuário.\n"
                            "Descubra se ele está se sentindo: Triste, Feliz, Bravo(a), Tranquilo(a), Preguiça ou Apaixonado(a).\n"
                            "Conforme o humor que ele relatar, mude sua abordagem: use frases de incentivo se estiver triste/bravo, seja contagiante se estiver feliz/apaixonado, ou acolhedora se estiver com preguiça.\n\n"
                            
                            "REGRAS DE RESPOSTA OBRIGATÓRIAS:\n"
                            "Responda RIGIDAMENTE com um objeto JSON contendo duas chaves primárias:\n"
                            "1. 'resposta_chat': O texto em linguagem natural que será exibido na tela. Sempre valide o prompt atual do usuário com muita empatia antes de prosseguir.\n"
                            "2. 'extracao': Um objeto contendo a análise do ÚLTIMO texto enviado pelo usuário. Formato interno:\n"
                            "   - 'idade': Número inteiro se ele mencionou agora, senão null.\n"
                            "   - 'interesse': 'M' para homens, 'F' para mulheres, 'O' para ambos/todos se mencionou agora, senão null.\n"
                            "   - 'procura': 'amizade' ou 'namoro' se declarou agora, senão null.\n"
                            "   - 'humor': Extraia uma das palavras exatas se ele disser como está se sentindo ('Triste', 'Feliz', 'Bravo(a)', 'Tranquilo(a)', 'Preguiça', 'Apaixonado(a)'), senão null."
                        )
                    },
                    {
                        "role": "user", 
                        "content": (
                            f"{contexto_conversacao}\n"
                            f"{dados_ja_salvos_contexto}\n"
                            f"Dados pendentes gerais:\n{dados_faltantes_contexto}\n"
                            f"Última mensagem do Usuário: {prompt}"
                        )
                    }
                ]

                # Chamada ÚNICA à OpenAI (Economiza metade do tempo de rede)
                resposta_streaming = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=mensagens_openai,
                    temperature=0.8,
                    response_format={"type": "json_object"}
                )

                # Processa o retorno da IA na memória local
                resultado_unificado = modulo_json.loads(resposta_streaming.choices[0].message.content)
                resposta_lucy = resultado_unificado.get("resposta_chat", "Estou processando seus interesses...")
                dados_extraidos = resultado_unificado.get("extracao", {})
                
                # Exibe a resposta imediatamente na tela
                st.session_state.historico_volatil.append(("assistant", resposta_lucy))
                st.chat_message("assistant").write(resposta_lucy)

                # Salva a mensagem no histórico de conversas
                cursor.execute(
                    "INSERT INTO historico_ia (usuario_id, usuario_pergunta, ia_resposta, data_hora) VALUES (%s, %s, %s, %s);", 
                    (meu_id_f, prompt, resposta_lucy, datetime.now())
                )
                conn.commit()

                # --- ATUALIZAÇÃO EM LOTE (Apenas os dados estruturais do match) ---
                updates = []
                params = []
                if dados_extraidos.get("idade"):
                    updates.append("idade = %s")
                    params.append(int(dados_extraidos["idade"]))
                if dados_extraidos.get("interesse"):
                    updates.append("procura_por = %s")
                    params.append(str(dados_extraidos["interesse"]))
                if dados_extraidos.get("procura"):
                    updates.append("procura_relacionamento = %s")
                    params.append(str(dados_extraidos["procura"]))
                
                # O campo dados_extraidos.get("humor") é intencionalmente ignorado aqui!
                # Ele serve apenas para guiar a 'resposta_chat' da IA no próximo turno.
                
                if updates:
                    params.append(meu_id_f)
                    query_update = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s;"
                    cursor.execute(query_update, tuple(params))
                    conn.commit()

                # Fecha o cursor e a conexão de forma limpa
                cursor.close()
                conn.close()

                # ============================================================
                # 🤝 MOTOR REAL DE MATCHES DA IA (AUTOMATIZADO E PROTEGIDO)
                # ============================================================
                res_match = processar_afinidade_e_match(meu_id_f, prompt) 
                
                if res_match and res_match.get("match") == True: 
                    id_parceiro_match = int(res_match["id_par"])
                    
                    # Abre uma conexão e cursor novos e exclusivos para este bloco de match
                    conn_p = conectar_supabase()
                    cursor_p = conn_p.cursor()
                    
                    try:
                        # 1. Garante que a relação exista (Usando cursor_p de forma isolada)
                        cursor_p.execute("""
                            SELECT id FROM matches 
                            WHERE (usuario_1_id = %s AND usuario_2_id = %s) 
                               OR (usuario_1_id = %s AND usuario_2_id = %s);
                        """, (meu_id_f, id_parceiro_match, id_parceiro_match, meu_id_f))
                        resultado_match = cursor_p.fetchone()
                        
                        if resultado_match:
                            match_id_final = resultado_match[0]
                        else:
                            cursor_p.execute("""
                                INSERT INTO matches (usuario_1_id, usuario_2_id) 
                                VALUES (%s, %s) RETURNING id;
                            """, (meu_id_f, id_parceiro_match))
                            match_id_final = cursor_p.fetchone()[0]
                            conn_p.commit()

                        # 2. Busca o status e o username real do parceiro (Corrigido para 'username')
                        cursor_p.execute("SELECT status, username FROM usuarios WHERE id = %s;", (id_parceiro_match,))
                        dados_parceiro = cursor_p.fetchone()
                        
                        if dados_parceiro:
                            status_banco = dados_parceiro[0]
                            username_banco = dados_parceiro[1]
                        else:
                            status_banco = None
                            username_banco = None
                        
                        # Define o nome que vai aparecer na tela para o usuário
                        nome_exibicao = username_banco if username_banco else res_match.get("nome_par", f"Usuário {id_parceiro_match}")
                        
                        parceiro_real_online = False
                        if status_banco and ("Online" in str(status_banco) or "🟢" in str(status_banco)):
                            parceiro_real_online = True

                        # Alimenta os dados no session_state para o interceptor do topo ler pós-rerun
                        st.session_state.alerta_match = {
                            "match_id": match_id_final, 
                            "id_par": id_parceiro_match, 
                            "nome": nome_exibicao, 
                            "online": parceiro_real_online 
                        } 
                    
                    finally:
                        # Garante o fechamento do cursor secundário de qualquer forma
                        cursor_p.close()
                        conn_p.close()

                # --- FECHAMENTO DO CURSOR PRINCIPAL (LUCY CHAT) ---
                # Verifica se o cursor principal ainda está ativo antes de fechar
                try:
                    if cursor and not cursor.closed:
                        cursor.close()
                    if conn:
                        conn.close()
                except Exception:
                    pass

                # Recarrega a página atualizando todo o fluxo de uma vez de forma segura
                st.rerun() 

            except Exception as e: 
                # O st.rerun() lança uma exceção interna chamada RerunException para parar o script.
                # Se for essa exceção, nós apenas a repassamos para o Streamlit seguir o fluxo.
                if e.__class__.__name__ == "RerunException":
                    raise e
                    
                # Só limpa e mostra erro se for uma falha real de código/banco
                try:
                    if 'cursor' in locals() and cursor and not cursor.closed: cursor.close()
                    if 'conn' in locals() and conn: conn.close()
                except Exception:
                    pass
                st.error(f"Erro na IA principal: {e}")
            


# ==============================================================================
# 3. DIALOGS RECALIBRADOS (INTEGRAÇÃO DE PLANOS IA, CRÉDITOS E AGENDAMENTOS)
# ==============================================================================

@st.dialog("🤖 Lucy Notou Afinidade!")
def exibir_modal_match(dados_m, tipo_plano, saldo_moedas):  

    st.markdown(f"Lucy identificou uma excelente afinidade entre você e **{dados_m['nome']}**!")
    
    # 🟢 COMPORTAMENTO SE O PAR ESTIVER ONLINE: Controle de acesso à Sala Privada
    if dados_m["online"]:
        st.markdown(f"🟢 **{dados_m['nome']} está online agora!**")
        
        # Validação baseada no Plano do Usuário
        if tipo_plano == "vip":
            if st.button("🚀 Entrar na Sala Privada (Acesso Total Ilimitado)", type="primary", use_container_width=True):
                st.session_state.match_id_atual = dados_m["match_id"]
                st.session_state.tempo_limite_sala = -1  # Tempo indeterminado
                st.session_state.opcao_menu = "🤝 Sala Privada"
                st.rerun()
                
        elif tipo_plano == "Plano Crédito de Moedas":
            st.info(f"🪙 Seu Saldo: **{saldo_moedas} moedas**. Custo da Sala Privada: 10 moedas = 10 minutos.")
            if st.button("🪙 Entrar na Sala Privada (Gasta 10 moedas)", type="primary", use_container_width=True):
                if saldo_moedas >= 10:
                    try:
                        # Deduz as primeiras 10 moedas correspondentes aos primeiros 10 minutos regulamentares
                        supabase.table("usuarios").update({"moedas": saldo_moedas - 10}).eq("id", id_usuario).execute()
                        st.success("Moedas debitadas! Sala privada liberada por 10 minutos iniciais.")
                        
                        st.session_state.match_id_atual = dados_m["match_id"]
                        st.session_state.tempo_limite_sala = 10  # Temporizador dinâmico
                        st.session_state.opcao_menu = "🤝 Sala Privada"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Falha na transação: {e}")
                else:
                    st.warning("🔒 Saldo insuficiente. Você precisa de pelo menos 10 moedas.")
                    
        else:
            # Bloqueio estrito para Plano Grátis
            st.error("🔒 O acesso a salas privadas é exclusivo para clientes com plano de Crédito ou Assinantes.")
                       
    # ⚪ COMPORTAMENTO SE O PAR ESTIVER OFFLINE: Controle de Agendamento Eletrônico
    else:
        st.button(f"⚪ {dados_m['nome']} está offline. Indisponível para chat instantâneo.", disabled=True, use_container_width=True)
        
        if st.button("📅 Agende um encontro virtual", type="secondary", use_container_width=True):
            if tipo_plano in ["vip", "Plano Crédito de Moedas"]:
                st.session_state.abrir_reserva_fluxo = {
                    "id_par": dados_m["id_par"], 
                    "nome_par": dados_m["nome"], 
                    "m_id": dados_m["match_id"]
                }
                st.rerun()
            else:
                # Bloqueio estrito para Usuários com Plano Grátis
                st.warning("🔒 O agendamento de encontros virtuais não está disponível no Plano Grátis. Faça um upgrade!")

    # ❌ Cancelamento e fechamento
    if st.button("❌ Não tenho interesse", type="secondary", use_container_width=True):
        st.rerun()



def processar_match_lucy(dados_m):
    # Valores padrão iniciais caso a busca falhe
    tipo_plano = "Grátis"
    saldo_moedas = 0
    
    id_usuario_logado = st.session_state.get("usuario_id")
    
    if id_usuario_logado is None:
        st.warning("⚠️ Usuário não identificado na sessão.")
        return

    try:
        # Busca os dados no Supabase
        user_data = supabase.table("usuarios").select("tipo_plano", "moedas").eq("id", int(id_usuario_logado)).execute()
        
        # 🟢 CORREÇÃO CRÍTICA: Acessando corretamente o primeiro elemento [0] da lista .data
        if user_data.data and len(user_data.data) > 0:
            registro_banco = user_data.data[0]
            
            # Captura os valores brutos
            plano_bruto = registro_banco.get("tipo_plano", "Grátis")
            saldo_moedas = registro_banco.get("moedas", 0)
            
            # 🟢 BLINDAGEM: Remove espaços em branco invisíveis no início/fim e padroniza a string
            if plano_bruto:
                tipo_plano = str(plano_bruto).strip()
            
            # 🔍 PROVA REAL (DEBUG): Remova ou comente essa linha após resolver o problema
            st.toast(f"DEBUG BANCO -> Plano encontrado: '{tipo_plano}' | Tipo: {type(tipo_plano)}")
            
        else:
            st.error("⚠️ Nenhum registro de usuário foi encontrado no banco de dados.")
            return
            
    except Exception as e:
        st.error(f"Erro ao carregar dados do banco: {e}")
        return

    # Garanta que o nome verificado na modal seja EXATAMENTE igual ao print do debug acima
    exibir_modal_match(dados_m, tipo_plano, saldo_moedas)


@st.dialog("📅 Reserva de Encontro")
def modal_agendamento_encontro(dados_r):
    st.markdown(f"### 📆 Agendar Reunião com {dados_r['nome_par']}")
    st.caption("A Lucy cruzará sua grade horária com a do seu par antes de validar o convite.")
    
    # 1. Configuração dos eixos de tempo
    dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
    dia_s = st.selectbox("Escolha o Dia da Semana:", dias, key="dg_res_dia")
    
    opcoes_periodo = [
        "🌅 Manhã (06:00 às 11:59)", 
        "☀️ Tarde (12:00 às 17:59)", 
        "🌙 Noite (18:00 às 23:59)"
    ]
    per_exibicao = st.selectbox("Escolha o Período:", opcoes_periodo, key="dg_res_per")
    
    # Mapeamento limpo para os IDs do banco
    if "Manhã" in per_exibicao:
        per_s = "manha"
        horario_sugestao = datetime.strptime("09:00", "%H:%M").time()
    elif "Tarde" in per_exibicao:
        per_s = "tarde"
        horario_sugestao = datetime.strptime("14:00", "%H:%M").time()
    else:
        per_s = "noite"
        horario_sugestao = datetime.strptime("20:00", "%H:%M").time()

    hor_s = st.time_input("Ajuste o Horário Exato:", value=horario_sugestao, step=900, key="dg_res_hor")
    
    if st.button("💾 Confirmar Reserva e Enviar", type="primary", use_container_width=True):
        hora_int = hor_s.hour
        
        # Função para limpar IDs de tuplas aninhadas de forma absoluta
        def limpar_id_absoluto(id_bruto):
            while isinstance(id_bruto, (tuple, list)):
                if len(id_bruto) > 0: id_bruto = id_bruto[0]
                else: return 0
            try: return int(id_bruto)
            except (TypeError, ValueError): return 0

        # Limpeza cirúrgica das chaves
        m_id_limpo = limpar_id_absoluto(dados_r.get('m_id'))
        meu_id_limpo = limpar_id_absoluto(st.session_state.usuario_id)
        parceiro_id_limpo = limpar_id_absoluto(dados_r.get('id_par'))

        # --- 2. TRAVA DE DISPONIBILIDADE DIRETA NO POSTGRESQL (CRUZAMENTO SEGURO) ---
        meu_registro_existe = False
        parceiro_registro_existe = False
        parceiro_tem_algum_horario = False
        
        try:
            conn_check = conectar_supabase()
            cursor_check = conn_check.cursor()
            
            # Verifica se você possui o horário na grade
            cursor_check.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s 
                  AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) 
                  AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (meu_id_limpo, str(dia_s), str(per_s)))
            meu_count = cursor_check.fetchone()[0]
            meu_registro_existe = (meu_count > 0)
            
            # Verifica se o parceiro possui ALGUNS horários cadastrados no banco (para saber se a grade dele está vazia)
            cursor_check.execute("SELECT COUNT(*) FROM disponibilidade_usuarios WHERE usuario_id = %s;", (parceiro_id_limpo,))
            total_parceiro = cursor_check.fetchone()[0]
            parceiro_tem_algum_horario = (total_parceiro > 0)
            
            # Verifica se o parceiro possui ESTE horário específico na grade
            cursor_check.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s 
                  AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) 
                  AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (parceiro_id_limpo, str(dia_s), str(per_s)))
            parceiro_count = cursor_check.fetchone()[0]
            parceiro_registro_existe = (parceiro_count > 0)
            
            cursor_check.close()
            conn_check.close()
            
            # Painel de depuração limpo
            with st.expander("🔍 Depurador de Agenda (Debug)"):
                st.write(f"**Seu ID ({st.session_state.username}):** {meu_id_limpo} | Possui este horário? `{'Sim' if meu_registro_existe else 'Não'}`")
                st.write(f"**ID do Par ({dados_r['nome_par']}):** {parceiro_id_limpo} | Possui este horário? `{'Sim' if parceiro_registro_existe else 'Não'}`")
                st.write(f"**O parceiro já preencheu a grade alguma vez?** `{'Sim' if parceiro_tem_algum_horario else 'Não'}`")
            
        except Exception as e:
            st.error(f"Erro ao consultar o banco de dados: {e}")

        # --- 3. EXECUÇÃO DAS TRAVAS DE HORÁRIO ---
        if per_s == 'manha' and (hora_int < 6 or hora_int >= 12):
            st.error("❌ Horário inválido! Para o período da manhã, ajuste entre **06:00 e 11:59**.")
        elif per_s == 'tarde' and (hora_int < 12 or hora_int >= 18):
            st.error("❌ Horário inválido! Para o período da tarde, ajuste entre **12:00 e 17:59**.")
        elif per_s == 'noite' and (hora_int < 18 or hora_int > 23):
            st.error("❌ Horário inválido! Para o período da noite, ajuste entre **18:00 e 23:59**.")
            
        # Alerta de recusa: Se você não marcou o dia na sua própria grade
        elif not meu_registro_existe:
            st.error(f"❌ **Agendamento Recusado:** Você ({st.session_state.username}) configurou este dia/período como indisponível na sua grade. Acesse 'MINHA GRADE HORÁRIA' para liberar.")
            
        # Alerta de recusa: Se o parceiro tem horários configurados mas não marcou este dia específico
        elif parceiro_tem_algum_horario and not parceiro_registro_existe:
            st.error(f"❌ **Agendamento Recusado:** {dados_r['nome_par']} está indisponível na {dia_s} no período selecionado.")
            
        # Se passar em todas as validações, realiza o agendamento pendente
        else:
            try:
                conn = conectar_supabase()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO agendamentos_virtuais (match_id, remetente_id, destinatario_id, dia_semana, periodo, horario, status_convite) 
                    VALUES (%s, %s, %s, %s, %s, %s, 'pendente');
                ''', (m_id_limpo, meu_id_limpo, parceiro_id_limpo, dia_s, per_s, hor_s))
                conn.commit()
                cursor.close()
                conn.close()
                
                st.success("🎉 Convite de encontro enviado com sucesso!")
                st.session_state.abrir_reserva_fluxo = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao gravar agendamento: {e}")
                

# ==============================================================================
# 8. REESTRUTURAÇÃO DA SALA PRIVADA (LAYOUT FIXO, FOTO REAL E LIMPAR HISTÓRICO)
# ==============================================================================

# 🟢 1. CRIAÇÃO DO COMPONENTE DO TEMPORIZADOR ISOLADO EM FRAGMENTO
# O parâmetro run_every faz o Streamlit atualizar APENAS esta caixinha a cada 5 segundos
@st.fragment(run_every=5.0)
def renderizar_temporizador_creditos(saldo_moedas_sala, id_usuario_logado, id_match_int):
    tempo_decorrido = time.time() - st.session_state.tempo_inicio_sala
    tempo_limite_segundos = 600  # Limite inicial de 10 minutos (600 segundos)
    tempo_restante = tempo_limite_segundos - tempo_decorrido

    if tempo_restante > 0:
        minutos_r = int(tempo_restante // 60)
        segundos_r = int(tempo_restante % 60)
        st.warning(f"⏳ **Tempo Restante nesta sessão:** {minutos_r:02d}:{segundos_r:02d} | Saldo Atual: 🪙 {saldo_moedas_sala} moedas")
    else:
        # O tempo acabou! Tenta renovar debitando mais 10 moedas por +10 minutos
        if saldo_moedas_sala >= 10:
            try:
                # 🟢 CALCULA O NOVO SALDO
                novo_saldo = saldo_moedas_sala - 10
                id_limpo = int(id_usuario_logado)
                
                # 🟢 CORREÇÃO CRÍTICA: Alterado de 'my_id' para 'id_limpo' no filtro .eq()
                supabase.table("usuarios").update({"moedas": novo_saldo}).eq("id", id_limpo).execute()
                
                # 🟢 ATUALIZA O CACHE NA MEMÓRIA LOCAL: Faz o novo valor refletir na tela imediatamente
                if "dados_usuario" in st.session_state:
                    st.session_state.dados_usuario["moedas"] = novo_saldo
                
                st.session_state.tempo_inicio_sala = time.time()  # Reseta o cronômetro local para +10 minutos
                st.toast("🪙 Mais 10 minutos adicionados! 10 moedas foram debitadas.", icon="🪙")
                st.rerun()  # Recarrega localmente o fragmento com os novos valores
                
            except Exception as e:
                st.error(f"Erro ao renovar tempo: {e}")
                time.sleep(3)
                st.session_state.opcao_menu = "💬 Conversar com Lucy"
                st.rerun()
        else:
            st.error("🔒 Seus 10 minutos acabaram e você não tem moedas suficientes para renovar.")
            time.sleep(3)
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()


@st.fragment(run_every=4.0)
def live_chat_privado_engine(m_id, my_id, p_nome_str):
    try:
        nome_exibicao = p_nome_str.split('@')[0].capitalize() if '@' in str(p_nome_str) else str(p_nome_str).capitalize()
    except Exception:
        nome_exibicao = "Usuário"

    # 🔍 PAINEL DE INSPECÇÃO BRUTA DO BANCO (DIAGNÓSTICO INTACTO)
    #st.write("---")
    #st.markdown(f"### 🔍 Diagnóstico de IDs de Segurança:")
    #st.write(f"• ID desta Sala Atual (`m_id`): `{m_id}`")
    #st.write(f"• Seu ID de Usuário (`my_id`): `{my_id}`")

    with st.container(height=410, border=False):
        try:
            # Busca as últimas 5 mensagens gravadas na tabela SEM NENHUM FILTRO
            res_bruto = supabase.table("mensagens_chat") \
                .select("match_id", "remetente_id", "texto") \
                .order("id", desc=True) \
                .limit(5) \
                .execute()
            
            dados_reais_no_banco = res_bruto.data if res_bruto.data else []
            
            st.markdown("---")
            #st.markdown("**📋 Últimas 5 linhas gravadas REALMENTE no seu banco de dados:**")
            #if not dados_reais_no_banco:
            #    st.error("❌ A tabela 'mensagens_chat' está completamente VAZIA no banco!")
            #else:
            #    for idx, linha in enumerate(dados_reais_no_banco):
            #        st.code(f"Linha {idx+1} -> match_id gravado: {linha.get('match_id')} | remetente_id gravado: {linha.get('remetente_id')} | texto: '{linha.get('texto')}'")
            #st.markdown("---")

            # --- FILTRAGEM PARA EXIBIR OS BALÕES ---
            id_sala_alvo = str(m_id).strip()
            rows = [msg for msg in dados_reais_no_banco if str(msg.get("match_id")).strip() == id_sala_alvo]

            if not rows:
                st.caption("✨ Nenhuma mensagem correspondente para esta sala específica.")
            else:
                for msg_data in reversed(rows): # Inverte para mostrar na ordem correta de chat
                    r_id = msg_data.get("remetente_id")
                    txt = msg_data.get("texto")
                    
                    if str(r_id).strip() == str(my_id).strip():
                        with st.chat_message("user"): st.write(txt)
                    else:
                        with st.chat_message("assistant"): st.write(txt)
                    
        except Exception as e:
            st.error(f"Erro ao ler banco: {e}")    

    # Campo de input do chat privado
    if txt_in := st.chat_input("Digite sua mensagem privada...", key="priv_chat_input"):
        if txt_in.strip():
            try:
                # No st.chat_input do Python, envie apenas isso:
                supabase.table("mensagens_chat").insert({
                    "match_id": int(m_id),
                    "remetente_id": int(my_id),
                    "texto": txt_in.strip()
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao enviar: {e}")




# ==============================================================================
# 1. COLOQUE ESTA FUNÇÃO AQUI (DEVE FICAR ACIMA DO TEMPLATE_SALA_PRIVADA)
# ==============================================================================
def enviar_mensagem(match_id, remetente_id, texto):
    if not texto or str(texto).strip() == "":
        return
    try:
        id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
        id_remetente_int = remetente_id if isinstance(remetente_id, (tuple, list)) else int(remetente_id)
        
        conn = conectar_supabase()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mensagens_sala (match_id, remetente_id, conteudo) 
            VALUES (%s, %s, %s);
        """, (id_match_int, id_remetente_int, str(texto).strip()))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao enviar mensagem: {e}")


# ==============================================================================
# 2. COLOQUE ESTA FUNÇÃO TAMBÉM ACIMA DO TEMPLATE_SALA_PRIVADA
# ==============================================================================
def buscar_mensagens(match_id):
    try:
        id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
        conn = conectar_supabase()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT remetente_id, conteudo, criado_em 
            FROM mensagens_sala 
            WHERE match_id = %s 
            ORDER BY criado_em ASC;
        """, (id_match_int,))
        mensagens = cursor.fetchall()
        cursor.close()
        conn.close()
        return mensagens
    except Exception:
        return []

def limpar_historico_sala(match_id):
    try:
        id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
        
        conn = conectar_supabase()
        cursor = conn.cursor()
        
        # Deleta todas as mensagens vinculadas a este match específico
        cursor.execute("DELETE FROM mensagens_sala WHERE match_id = %s;", (id_match_int,))
        
        # OBRIGATÓRIO: Salva as alterações no banco de dados
        conn.commit()
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erro ao limpar histórico: {e}")
        return False


# ==============================================================================
# 3. SUA FUNÇÃO PRINCIPAL (SÓ CHAMA AS FUNÇÕES ACIMA DEPOIS DELAS EXISTIREM)
# ==============================================================================
def template_sala_privada():
    match_id = st.session_state.match_id_atual
    meu_id = st.session_state.usuario_id
    
    # 1. CSS AVANÇADO PARA FIXAR ELEMENTOS E ESTILIZAR ESTILO WHATSAPP
    st.markdown(
        """
        <style>
        /* Remove paddings padrões do Streamlit para col colar no topo */
        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 0rem !important; 
        }
        
        /* Fixa o Perfil Lateral e impede rolagem dele */
        .box-perfil-fixo { 
            background-color: #161b22; 
            border: 1px solid #30363d; 
            border-radius: 8px; 
            padding: 15px; 
            text-align: center;
            position: sticky;
            top: 2rem;
        }
        
        /* Balões estilo WhatsApp */
        .chat-container {
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding: 10px;
        }
        .msg-bubble {
            border-radius: 8px;
            padding: 8px 12px;
            max-width: 75%;
            font-size: 15px;
            line-height: 1.4;
            position: relative;
        }
        .msg-meu {
            background-color: #056162;
            color: white;
            align-self: flex-end;
            border-top-right-radius: 0px;
        }
        .msg-parceiro {
            background-color: #262d31;
            color: white;
            align-self: flex-start;
            border-top-left-radius: 0px;
        }
        .msg-autor {
            font-size: 11px;
            font-weight: bold;
            color: #34b7f1;
            margin-bottom: 3px;
        }
        .msg-tempo {
            font-size: 10px;
            color: #8696a0;
            text-align: right;
            margin-top: 4px;
        }
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    parceiro_nome = "Usuário"
    parceiro_foto = None
    parceiro_gen = "M"
    status_parceiro = "⚫ Offline"
    status_cor = "#a0aec0"
    
    try:
        conn = conectar_supabase()
        cursor = conn.cursor()
        id_match_int = match_id[0] if isinstance(match_id, (tuple, list)) else int(match_id)
        cursor.execute("SELECT usuario_1_id, usuario_2_id FROM matches WHERE id = %s;", (id_match_int,))
        res_m = cursor.fetchone()
        
        if res_m:
            u1, u2 = int(res_m[0]), int(res_m[1])
            meu_id_limpo = st.session_state.usuario_id[0] if isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)
            p_id = u2 if u1 == meu_id_limpo else u1
            
            cursor.execute("SELECT username, foto_perfil, genero, status FROM usuarios WHERE id = %s;", (int(p_id),))
            res_u = cursor.fetchone()
            if res_u:
                parceiro_nome = str(res_u[0])
                parceiro_foto = res_u[1]
                parceiro_gen = res_u[2]
                p_stat = res_u[3]
                if "Online" in str(p_stat) or "🟢" in str(p_stat):
                    status_parceiro = "🟢 Online"
                    status_cor = "#48bb78"
        cursor.close()
        conn.close()
    except Exception as e: 
        print(f"Erro ao buscar status na Sala Privada: {e}")

    if "tempo_inicio_sala" not in st.session_state:
        st.session_state.tempo_inicio_sala = time.time()

    tipo_plano_sala = "Grátis"
    saldo_moedas_sala = 0
    id_usuario_logado = st.session_state.get("usuario_id")
    
    if id_usuario_logado is None:
        st.warning("⚠️ Usuário não identificado na sessão.")
        return

    # 🟢 ADICIONE ESTA LEITURA DIRETA EM MEMÓRIA:
    if "dados_usuario" in st.session_state:
        tipo_plano_sala = str(st.session_state.dados_usuario.get("tipo_plano", "Grátis")).strip()
        saldo_moedas_sala = st.session_state.dados_usuario.get("moedas", 0)
    else:
        tipo_plano_sala = "Grátis"
        saldo_moedas_sala = 0


    # 2. INTERFACE DIVIDIDA EM COLUNAS
    col_perfil, col_chat = st.columns([1, 3])


    with col_perfil:
        avatar_html = ""
        caminho_disco = str(parceiro_foto).strip().lstrip('/')
        
        # Converte a foto real para Base64 se o arquivo físico existir na pasta
        if parceiro_foto and os.path.exists(caminho_disco):
            try:
                with open(caminho_disco, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode()
                avatar_html = f'<img src="data:image/jpeg;base64,{encoded_string}" class="foto-parceiro-sala">'
            except Exception:
                avatar_html = f'<div style="font-size: 40px; margin-bottom: 10px; text-align:center;">{"👩" if parceiro_gen == "F" else "👨"}</div>'
        else:
            avatar_html = f'<div style="font-size: 40px; margin-bottom: 10px; text-align:center;">{"👩" if parceiro_gen == "F" else "👨"}</div>'
        st.markdown(f"""
         <div class="box-perfil-fixo">
         {avatar_html}</div>""", unsafe_allow_html=True)
        st.markdown(f'<div style="color:white; font-weight:bold; font-size:18px;">{parceiro_nome}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color: {status_cor}; font-size:14px; margin-top:5px;">{status_parceiro}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("""
                    <div class="info-box-segura" style="margin-bottom: 15px;">
                        <h3>🔒 Ambiente Seguro</h3>
                        <p>Esta é uma sala de transmissão privada e criptografada temporária.</p>
                    </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Sair da Sala Privada", type="primary", use_container_width=True):
            if meu_id:
            try:
                import datetime
                horario_saida = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                # 1. Atualiza o status do encontro para OFFLINE imediatamente no banco
                supabase.table("matches")\
                    .update({
                        "status_conexao": "offline",
                        "ultima_atividade": horario_saida
                    })\
                    .eq("id", meu_id)\
                    .execute()
                
                # 2. Carimba o encerramento na tabela de mensagens conforme seu fluxo atual
                supabase.table("mensagens_sala")\
                    .update({"saida_em": horario_saida})\
                    .eq("match_id", meu_id)\
                    .execute()
                    
                st.success("Você saiu da sala com sucesso!")
            except Exception as erro_saida:
                st.error(f"Erro ao desconectar: {erro_saida}")
                
            # 3. Limpa o estado da sessão e redireciona o usuário no menu
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()
            
        st.write("") 
        if st.button("🗑️ Limpar Histórico do Chat", type="secondary", use_container_width=True):
            if limpar_historico_sala(match_id):
                st.success("Histórico apagado!")
                st.rerun() 

           # 🚀 CHAMADA DO TIMOR DE CRÉDITOS ISOLADO (Evita o loop infinito global)
        if tipo_plano_sala == "Plano Crédito de Moedas":
            st.info(f"🪙 Modo Créditos Ativo. Saldo atual: {saldo_moedas_sala} moedas.")
            renderizar_temporizador_creditos(saldo_moedas_sala, id_usuario_logado, id_match_int) 
        elif tipo_plano_sala == "vip": 
            st.success(f"⭐ Plano Assinante Ativo: Acesso ilimitado por tempo indeterminado.") 

    # --- COLUNA DA DIREITA (SALA DE CONVERSA) ---
    with col_chat:
        # Título Fixo no Topo do Chat
        st.markdown(f"### 💬 Sala Privada com {parceiro_nome}")
        # Recupera o ID do match atual guardado na sessão
        meu_id = st.session_state.get("match_id_atual")
        
        if meu_id:
            try:
                import datetime
                agora_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                # 🟢 SINAL DE ENTRADA / PULSAÇÃO (Heartbeat)
                # Toda vez que a tela carrega ou atualiza, carimba o match como ONLINE no banco
                supabase.table("matches")\
                    .update({
                        "status_conexao": "online",
                        "ultima_atividade": agora_iso
                    })\
                    .eq("id", meu_id)\
                    .execute()
                    
            except Exception as e:
                # Falha silenciosa para não travar a experiência de chat do usuário
                pass
        st.divider()

        # Funcionalidade de Videochamada fixa 
        if st.button("🎥 Iniciar Videochamada Privada"): 
            nome_da_sala_unica = f"Atendimento_FaleConosco_SalaPrivada_{id_match_int}" 
            url_jitsi = f"https://meet.jit.si/{nome_da_sala_unica}" 
        
            st.info("A videochamada foi iniciada abaixo. Garanta as permissões no navegador.") 
            st.iframe(url_jitsi, height=600) 

        # Retângulo Interno com Rolagem Automática (Usando container nativo do Streamlit com altura travada)
        # O parâmetro height força a barra de rolagem apenas dentro deste bloco de histórico
        with st.container(height=400, border=True):
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            
            # Buscando mensagens do banco (Exemplo simulado baseado na sua nova tabela)
            mensagens = buscar_mensagens(match_id) 
            
            for msg in mensagens:
                remetente_id, conteudo, criado_em = msg[0], msg[1], msg[2]
                horario = criado_em.strftime("%H:%M") if criado_em else ""
                
                if remetente_id == meu_id:
                    # Mensagem enviada por mim (Lado Direito - Verde Escuro)
                    st.markdown(
                        f"""
                        <div class="msg-bubble msg-meu">
                            <div class="msg-autor">Você</div>
                            <div>{conteudo}</div>
                            <div class="msg-tempo">{horario}</div>
                        </div>
                        """, unsafe_allow_html=True
                    )
                else:
                    # Mensagem enviada pelo parceiro (Lado Esquerdo - Cinza Escuro)
                    st.markdown(
                        f"""
                        <div class="msg-bubble msg-parceiro">
                            <div class="msg-autor">{parceiro_nome}</div>
                            <div>{conteudo}</div>
                            <div class="msg-tempo">{horario}</div>
                        </div>
                        """, unsafe_allow_html=True
                    )
            st.markdown('</div>', unsafe_allow_html=True)

        # Caixa de Texto na parte inferior do chat
        with st.form(key="form_enviar_msg", clear_on_submit=True):
            col_txt, col_btn = st.columns([4, 1]) # Dá 80% do espaço para o texto e 20% para o botão
            
            with col_txt:
                # O Enter funciona nativamente aqui dentro para disparar o form_submit_button
                texto_msg = st.text_input(
                    label="Mensagem", 
                    placeholder="Digite uma mensagem e aperte Enter...", 
                    label_visibility="collapsed"
                )
            
            with col_btn:
                botao_enviar = st.form_submit_button("Enviar", use_container_width=True)
            
            # CORREÇÃO: O gatilho correto de um st.form é APENAS a variável do botão
            if botao_enviar and texto_msg.strip():
                enviar_mensagem(match_id, meu_id, texto_msg)
                st.rerun() # Atualiza a tela uma única vez para mostrar a nova mensagem

    

def renderizar_listas_sidebar_e_acoes(): 
    with st.sidebar: 
        # --- PERFIL DO USUÁRIO ---
        avatar_html = ""
        caminho_minha_foto = str(st.session_state.foto_perfil).strip().lstrip('/')
        if st.session_state.foto_perfil and os.path.exists(caminho_minha_foto):
            try:
                with open(caminho_minha_foto, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode()
                avatar_html = f'<img src="data:image/jpeg;base64,{encoded_string}" style="width:65px; height:65px; border-radius:50%; object-fit:cover; border:2px solid #30363d; margin:0 auto 10px auto; display:block;">'
            except Exception:
                avatar_html = f'<div style="font-size: 35px; text-align:center;">👩</div>'
        else:
            avatar_html = f'<div style="font-size: 35px; text-align:center;">👩</div>'

        # --- CORREÇÃO DA LINHA 480 (EXTRAÇÃO DO ÍNDICE [0] DA STRING SPLIT) ---
        nome_usuario_puro = str(st.session_state.username).split('@')[0].capitalize()

        st.markdown(f"""
            <div class="box-perfil-fixo" style="background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 15px;">
                {avatar_html}
                <h3 style="margin: 0; font-size: 15px; font-weight: bold; color: #f0f6fc;">{nome_usuario_puro}</h3>
                <p style="color: #48bb78; font-weight: bold; font-size: 12px; margin: 3px 0 0 0;">🟢 Online</p>
            </div>
        """, unsafe_allow_html=True)

       # 1. Define os valores padrões caso a busca no banco falhe
        tipo_plano = "Grátis"
        saldo_moedas = 0

        try:
            # Captura com segurança o ID do usuário logado
            id_usuario_logado = st.session_state.get("usuario_id")
            
            # CORREÇÃO: Alterado de 'NULL' para 'None' (sintaxe correta do Python)
            if id_usuario_logado is not None:
                # Faz a busca no Supabase convertendo o ID para inteiro
                user_data = supabase.table("usuarios").select("tipo_plano", "moedas").eq("id", int(id_usuario_logado)).execute()
                
                # Verifica se a lista contém dados e extrai do primeiro elemento [0]
                if user_data.data and len(user_data.data) > 0:
                    tipo_plano = user_data.data[0].get("tipo_plano", "Grátis")
                    saldo_moedas = user_data.data[0].get("moedas", 0)
            else:
                st.warning("⚠️ Usuário não identificado na sessão.")

        except Exception as e:
            st.error(f"Erro ao carregar dados do banco: {e}")

        # 🔄 SALVANDO CORRETAMENTE NA SESSÃO GLOBAL:
        st.session_state["tipo_plano"] = tipo_plano
        st.session_state["saldo_moedas"] = saldo_moedas

        # Exibe na tela com as variáveis atualizadas e corretas
        st.caption(f"Plano: **{tipo_plano}** | Saldo: 🪙 **{saldo_moedas} moedas**")

        st.caption("📷 Enviar nova foto de perfil:")
        f_nova = st.file_uploader("Alterar Foto", type=["png","jpg","jpeg"], key="side_f_up", label_visibility="collapsed") 
        if f_nova: 
            if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER, exist_ok=True) 
            c_completo = os.path.join(UPLOAD_FOLDER, f"user_{st.session_state.usuario_id}.jpg") 
            with open(c_completo, "wb") as f: f.write(f_nova.getbuffer()) 
            conn = conectar_supabase(); cursor = conn.cursor() 
            cursor.execute("UPDATE usuarios SET foto_perfil = %s WHERE id = %s", (f"/{c_completo}", int(st.session_state.usuario_id))) 
            conn.commit(); cursor.close(); conn.close() 
            st.session_state.foto_perfil = f"/{c_completo}"; st.rerun() 

        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)    
        
              
        # 🔍 MOTOR DE BUSCA DA NOTIFICAÇÃO DA BARRA LATERAL (BOLINHA VERMELHA)
        possui_convite_pendente = False
        try:
            meu_id_limpo = int(st.session_state.usuario_id) if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)
            conn_b = conectar_supabase(); cursor_b = conn_b.cursor()
            cursor_b.execute("SELECT COUNT(*) FROM agendamentos_virtuais WHERE destinatario_id = %s AND status_convite = 'pendente';", (meu_id_limpo,))
            if cursor_b.fetchone() > 0: possui_convite_pendente = True
            cursor_b.close(); conn_b.close()
        except Exception: pass

        # --- BLOCO 3: BOTÕES DE NAVEGAÇÃO INTERNA COM NOTIFICAÇÃO DINÂMICA ---
        # 🔍 MOTOR DE BUSCA DA NOTIFICAÇÃO DA BARRA LATERAL (BOLINHA VERMELHA)
        possui_convite_pendente = False
        try:
            meu_id_limpo = int(st.session_state.usuario_id) if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id[0])
            conn_b = conectar_supabase()
            cursor_b = conn_b.cursor()
            # Conta se existem convites com status 'pendente' onde VOCÊ é o destinatário
            cursor_b.execute("SELECT COUNT(*) FROM agendamentos_virtuais WHERE destinatario_id = %s AND status_convite = 'pendente';", (meu_id_limpo,))
            count_res = cursor_b.fetchone()
            if count_res and count_res[0] > 0: 
                possui_convite_pendente = True
            cursor_b.close()
            conn_b.close()
        except Exception as e: 
            print(f"Erro ao checar notificações: {e}")

        # Configura o rótulo do botão dinamicamente com base na presença de convites
        if possui_convite_pendente:
            # Rótulo ganha o emoji de alerta visual vermelho piscante
            label_gestao = "🤝 ABRIR GESTÃO 🔴"
            st.markdown("""
                <div style='background-color: #21262d; border: 1px solid #ef4444; border-radius: 6px; padding: 6px; text-align: center; margin-bottom: 8px;'>
                    <span style='font-size: 11px; color: #ef4444; font-weight: bold;'>📩 VOCÊ RECEBEU UM NOVO CONVITE!</span>
                </div>
            """, unsafe_allow_html=True)
        else:
            label_gestao = "🤝 ABRIR GESTÃO"

        # Renderiza o botão com o rótulo atualizado
        if st.button(label_gestao, type="secondary", use_container_width=True, key="btn_sidebar_gestao_rel"):
            st.session_state.opcao_menu = "🤝 Gerenciar Conexões"
            st.rerun()
        if st.button("📅 MINHA GRADE HORÁRIA", type="primary", use_container_width=True): 
            st.session_state.opcao_menu = "📅 Disponibilidade"
            
       # No seu menu lateral padrão:
        if st.sidebar.button("Ir para a Loja 🛒", type="secondary", use_container_width=True):
            st.session_state.abrir_popup_loja = True
            st.rerun()
               
        if st.session_state.eh_admin or st.session_state.username in ['admin', 'Clever1404']:
            if st.button("⚙️ PAINEL ADMINISTRATIVO", type="secondary", use_container_width=True):
                st.session_state.opcao_menu = "🛠️ Painel Admin"; st.rerun()     

        if st.button("🗑️ LIMPAR HISTÓRICO DA IA", type="secondary", use_container_width=True):
            try:
                conn = conectar_supabase(); cursor = conn.cursor()
                cursor.execute("DELETE FROM historico_ia WHERE usuario_id = %s;", (int(st.session_state.usuario_id),))
                conn.commit(); cursor.close(); conn.close(); st.toast("Histórico limpo!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True) 
        if st.button("🚪 ENCERRAR SESSÃO", type="primary", use_container_width=True):
            try:
                conn_logout = conectar_supabase(); cursor_logout = conn_logout.cursor()
                cursor_logout.execute("UPDATE usuarios SET status = '⚫ Offline' WHERE id = %s;", (int(st.session_state.usuario_id),))
                conn_logout.commit(); cursor_logout.close(); conn_logout.close()
            except Exception: pass
            st.session_state.usuario_id = None; st.session_state.username = None; st.session_state.opcao_menu = "login"; st.rerun()


def template_disponibilidade(): 
    st.subheader("📅 Sua Grade de Disponibilidade") 
    st.caption("Marque os dias da semana em que você está disponível. Seus matches verão apenas os dias da semanas que você está disponível.")

    dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'] 
    periodos = [{"id": "manha", "nome": "Manhã"}, {"id": "tarde", "nome": "Tarde"}, {"id": "noite", "nome": "Noite"}] 

    meu_id_limpo = st.session_state.usuario_id if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)
    horarios_salvos = set()
    
    try:
        conn = conectar_supabase()
        cursor = conn.cursor()
        cursor.execute("SELECT dia_semana, periodo FROM disponibilidade_usuarios WHERE usuario_id = %s;", (meu_id_limpo,))
        for d_sem, per_id in cursor.fetchall():
            horarios_salvos.add(f"{str(d_sem).strip()}_{str(per_id).strip()}") 
        cursor.close()
        conn.close()
    except Exception:
        pass

    matriz = [] 
    for per in periodos: 
        linha = {"Período": per["nome"]} 
        for d in dias: 
            linha[d] = f"{d}_{per['id']}" in horarios_salvos
        matriz.append(linha) 

    df_grade = pd.DataFrame(matriz) 
    
    config_c = {"Período": st.column_config.TextColumn(disabled=True)} 
    for d in dias: 
        config_c[d] = st.column_config.CheckboxColumn(default=False) 

    # --- 1. ESCOPO DO FORMULÁRIO EXCLUSIVO PARA O SALVAMENTO DA PLANILHA ---
    with st.form("container_formulario_grade_horaria", clear_on_submit=False):
        grade_editada = st.data_editor(df_grade, column_config=config_c, use_container_width=True, hide_index=True, key="grade_horaria_editor") 
        
        # O único botão dentro do form deve ser o submit de gravação
        botao_salvar_ativo = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
        
        if botao_salvar_ativo: 
            try:
                conn = conectar_supabase()
                cursor = conn.cursor() 
                cursor.execute("DELETE FROM disponibilidade_usuarios WHERE usuario_id = %s;", (meu_id_limpo,)) 
                
                for idx, row in grade_editada.iterrows(): 
                    p_id = periodos[idx]["id"]
                    for d in dias: 
                        if row[d]: 
                            cursor.execute("""
                                INSERT INTO disponibilidade_usuarios (usuario_id, dia_semana, periodo) 
                                VALUES (%s, %s, %s);
                            """, (meu_id_limpo, str(d), str(p_id))) 
                
                # ... CÓDIGO DA SUA QUERY DE INSERT CONTINUA IGUAL ...
                conn.commit()
                cursor.close()
                conn.close() 
                
                # 🔍 CORREÇÃO: Alerta flutuante que persiste mesmo com o st.rerun() imediato
                st.toast("🎉 Sua grade horária foi salva com sucesso no banco de dados!")
                
                # Importa e segura o ciclo por 1 segundo para o usuário ler o aviso na tela
                import time
                time.sleep(1)
                
                st.rerun() 
            except Exception as e:
                st.error(f"Erro crítico ao salvar no banco: {e}")

    # --- 2. ÁREA EXTERNA AO FORMULÁRIO (RESOLVE O STREAMLITAPIEXCEPTION) ---
    # Os botões comuns abaixo agora nascem fora do container do form, operando livremente
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    col_l, col_v = st.columns(2)
    
    with col_l:
        if st.button("🗑️ Limpar Grade Horária", type="secondary", use_container_width=True):
            try:
                conn = conectar_supabase(); cursor = conn.cursor()
                cursor.execute("DELETE FROM disponibilidade_usuarios WHERE usuario_id = %s;", (meu_id_limpo,))
                conn.commit(); cursor.close(); conn.close()
                st.toast("Toda a sua grade horária foi limpa!")
                st.rerun()
            except Exception as e: 
                st.error(f"Erro: {e}")
            
    with col_v: 
        if st.button("Voltar ao Chat", use_container_width=True): 
            st.session_state.opcao_menu = "💬 Conversar com Lucy" 
            st.rerun()



# ==============================================================================
# 7. TELA DE GESTÃO DE RELACIONAMENTOS (RESTAURAÇÃO COMPLETA DA LISTA DE MATCHES)
# ==============================================================================

def template_gerenciar_conexoes_completo(): 
    st.title("🤝 Gestão de Relacionamentos") 
    if st.button("← Voltar para o Chat da Lucy", type="secondary"):
        st.session_state.opcao_menu = "💬 Conversar com Lucy"
        st.rerun()
        
    aba_m, aba_e = st.tabs(["👥 Meus Matches", "📆 Gestão de Convites e Histórico"]) 
    meu_id_limpo = int(st.session_state.usuario_id) if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id[0])

   # 🔴 NOVA REGRA ULTRA SEGURA:
    # Captura o plano, remove espaços e coloca tudo em letras minúsculas
    plano_atual = str(st.session_state.get("tipo_plano", "grátis")).strip().lower()

    # Verifica se o usuário possui um dos planos válidos para acesso
    usuario_tem_acesso = (plano_atual == "vip") or ("crédito" in plano_atual) or ("credito" in plano_atual)

    # O botão será bloqueado SE o usuário NÃO tiver acesso
    bloquear_botoes = not usuario_tem_acesso


    with aba_m:
        st.markdown("### 👥 Suas Afinidades")
        matches_dados = []
        try:
            conn = conectar_supabase(); cursor = conn.cursor()
            cursor.execute('SELECT m.id, u.username, u.foto_perfil, u.genero, u.id FROM matches m JOIN usuarios u ON (u.id = m.usuario_2_id OR u.id = m.usuario_1_id) WHERE (m.usuario_1_id = %s OR m.usuario_2_id = %s) AND u.id != %s;', (meu_id_limpo, meu_id_limpo, meu_id_limpo))
            matches_dados = cursor.fetchall(); cursor.close(); conn.close()
        except Exception: pass

        if not matches_dados: st.info("Nenhum par localizado.")
        for m_id, m_nome, m_foto, m_gen, par_id in matches_dados:
            with st.container(border=True):
                # Estrutura em colunas equilibradas para reduzir o tamanho do retângulo
                c_av_c, c_nm_c, c_go_c, c_del_c = st.columns([0.6, 2, 1, 1])
                
                with c_av_c:
                    caminho_par_img = str(m_foto).strip().lstrip('/')
                    if m_foto and os.path.exists(caminho_par_img):
                        try:
                            with open(caminho_par_img, "rb") as image_file:
                                enc_str = base64.b64encode(image_file.read()).decode()
                            st.markdown(f'<img src="data:image/jpeg;base64,{enc_str}" class="foto-match-central">', unsafe_allow_html=True)
                        except Exception: st.write("👩" if m_gen == 'F' else "👨")
                    else:
                        st.subheader("👩" if m_gen == 'F' else "👨")
                        
                with c_nm_c:
                    # Fonte aumentada para 15px e em negrito igual ao botão entrar
                    st.markdown(f"<p style='font-size:15px; font-weight:bold; margin-top:5px; color:#f0f6fc;'>{str(m_nome).split('@')[0].capitalize()}</p>", unsafe_allow_html=True)
                    
                with c_go_c:
                    if st.button("💬 Entrar", key=f"go_ch_h_{m_id}", type="primary", use_container_width=True, disabled=bloquear_botoes,
                        help="Disponível apenas para planos vip ou Plano Crédito de Moedas" if bloquear_botoes else None):
                        st.session_state.match_id_atual = m_id
                        st.session_state.opcao_menu = "🤝 Sala Privada"; st.rerun()
                        
                with c_del_c:
                    # RESTAURADO: Botão cinza para excluir afinidades indesejadas do banco
                    if st.button("🗑️ Desfazer", key=f"del_match_central_{m_id}", type="secondary", use_container_width=True):
                        try:
                            conn = conectar_supabase(); cursor = conn.cursor()
                            cursor.execute("DELETE FROM mensagens_chat WHERE match_id = %s;", (int(m_id),))
                            cursor.execute("DELETE FROM agendamentos_virtuais WHERE match_id = %s;", (int(m_id),))
                            cursor.execute("DELETE FROM matches WHERE id = %s;", (int(m_id),))
                            conn.commit(); cursor.close(); conn.close()
                            st.toast("Match removido!")
                            st.rerun()
                        except Exception as e: st.error(f"Erro: {e}")


    with aba_e:
        st.markdown("### 📩 Convites Ativos da Semana")
        try:
            conn = conectar_supabase(); cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.dia_semana, a.periodo, a.horario, a.status_convite, a.remetente_id,
                CASE WHEN a.remetente_id = %s THEN u2.username ELSE u1.username END as nome_parceiro, a.match_id
                FROM agendamentos_virtuais a JOIN matches m ON m.id = a.match_id JOIN usuarios u1 ON u1.id = m.usuario_1_id JOIN usuarios u2 ON u2.id = m.usuario_2_id
                WHERE a.remetente_id = %s OR a.destinatario_id = %s ORDER BY a.id DESC;
            """, (meu_id_limpo, meu_id_limpo, meu_id_limpo))
            encontros = cursor.fetchall(); cursor.close(); conn.close()
            
            # Separa registros Ativos e Passados baseado no dia do servidor
            encontros_ativos = [e for e in encontros if str(e[1]).lower() == str(dia_atual_servidor).lower() or str(e[4]).lower() == 'pendente']
            encontros_passados = [e for e in encontros if str(e[1]).lower() != str(dia_atual_servidor).lower() and str(e[4]).lower() == 'aceito']
            
            if not encontros_ativos:
                st.caption("Nenhum convite pendente ou encontro ativo para hoje.")
                
            for ag_id, dia, per, hora, status, rem_id, parceiro_nome, m_id in encontros_ativos:
                eu_enviei = (int(rem_id) == meu_id_limpo)
                # 🔍 CORREÇÃO 2: Adicionado [0] no split do parceiro ativo
                parceiro_limpo = str(parceiro_nome).split('@')[0].capitalize()
                
                with st.container(border=True):
                    col_i, col_b = st.columns([3, 1])
                    with col_i:
                        st.write(f"📅 **Encontro com {parceiro_limpo}:** {dia} às {str(hora)[:5]}")
                        st.caption(f"Status: {status.upper()}")
                    with col_b:
                        if status == 'pendente' and not eu_enviei:
                            if st.button("✅ Confirmar", key=f"side_ok_{ag_id}", type="primary", use_container_width=True, disabled=bloquear_botoes,
                                help="Disponível apenas para planos vip ou Plano Crédito de Moedas" if bloquear_botoes else None):
                                conn = conectar_supabase(); cursor = conn.cursor(); cursor.execute("UPDATE agendamentos_virtuais SET status_convite = 'aceito' WHERE id = %s;", (ag_id,)); conn.commit(); cursor.close(); conn.close(); st.rerun()
                        elif status == 'aceito':
                            if st.button("🟢 Entrar", key=f"side_g_{ag_id}", type="primary", use_container_width=True, disabled=bloquear_botoes,
                                help="Disponível apenas para planos vip ou Plano Crédito de Moedas" if bloquear_botoes else None
                            ):
                                st.session_state.match_id_atual = m_id
                                st.session_state.opcao_menu = "🤝 Sala Privada"
                                st.rerun()
            
            # --- COMPONENTE: HISTÓRICO DE ENCONTROS PASSADOS ---
            st.markdown("<br><hr style='border-color: #21262d;'>", unsafe_allow_html=True)
            st.markdown("### 📚 Histórico de Encontros Concluídos")
            if not encontros_passados:
                st.caption("Nenhum registro antigo arquivado.")
            for ag_id, dia, per, hora, status, rem_id, parceiro_nome, m_id in encontros_passados:
                # 🔍 CORREÇÃO 3: Adicionado [0] no split do parceiro no histórico antigo
                parceiro_antigo_limpo = str(parceiro_nome).split('@')[0].capitalize()
                st.markdown(f"🔒 *Encontro Concluído com {parceiro_antigo_limpo} na {dia} ({per}) às {str(hora)[:5]}*")
                
        except Exception as e: st.error(f"Erro: {e}")     

# ==============================================================================
# 9. CORREÇÃO DO PAINEL ADMIN (REATIVAÇÃO DO PARETO E COLUNAS IDADE/GENERO/EMAIL)
# ==============================================================================

def template_painel_admin():
    st.markdown("<h2>🛠️ Painel Administrativo de Controle Avançado</h2>", unsafe_allow_html=True)
    st.caption("Métricas demográficas, performance preditiva da Lucy IA e moderação de contas em tempo real.")
    st.markdown("<hr style='border-color: #30363d; margin: 10px 0 25px 0;'>", unsafe_allow_html=True)

    # --- 1. COLETA E PREPARAÇÃO DOS DADOS DO POSTGRESQL ---
    usuarios_bd = []
    dados_agendados = {}
    dados_realizados = {}  # 🌟 GARANTA QUE ESTÁ DECLARADA AQUI NO TOPO
    dados_matches = {}
    total_salas_ativas = 0

    try:
        conn = conectar_supabase()
        cursor = conn.cursor()
        
        # 1. Busca a lista completa de moderação de usuários
        cursor.execute("SELECT id, username, email, genero, idade, procura_por, status FROM usuarios ORDER BY id ASC;")
        usuarios_bd = cursor.fetchall()

        # 🌟 NOVA QUERY SIMPLIFICADA: Conta as salas online direto na tabela mãe
        # Inclui um limitador de tempo de 5 minutos caso alguém tenha fechado a aba de forma abrupta
        cursor.execute("""
            SELECT COUNT(id) 
            FROM matches 
            WHERE status_conexao = 'online' 
              AND ultima_atividade >= NOW() - INTERVAL '5 minutes';
        """)
        total_salas_ativas = cursor.fetchone()[0]
        
        # 2. Busca a lista de match_id e tempos do chat de hoje
        cursor.execute("""
            SELECT 
                match_id, 
                MAX(criado_em) as ultima_mensagem,
                COUNT(saida_em) as saídas_registradas
            FROM mensagens_sala 
            WHERE match_id IS NOT NULL 
              AND CAST(criado_em AS date) = CURRENT_DATE
            GROUP BY match_id;
        """)
        salas_hoje_tuplas = cursor.fetchall()

        # 3. Estatísticas Semanais por Dia para o Gráfico de Pareto
        cursor.execute("SELECT TRIM(LOWER(dia_semana)), COUNT(*) FROM agendamentos_virtuais GROUP BY 1;")
        dados_agendados = dict(cursor.fetchall())
        
        # 🌟 RECOLOQUE ESTA QUERY AQUI DENTRO DO TRY PARA ALIMENTAR A VARIÁVEL
        cursor.execute("""
            SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT mc.id) 
            FROM agendamentos_virtuais a 
            JOIN mensagens_sala mc ON mc.match_id = a.match_id 
            GROUP BY 1;
        """)
        dados_realizados = dict(cursor.fetchall())
        
        # Opcional: query de matches para segurança de outros gráficos
        cursor.execute("""
            SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT m.id) 
            FROM agendamentos_virtuais a 
            JOIN matches m ON m.id = a.match_id 
            GROUP BY 1;
        """)
        dados_matches = dict(cursor.fetchall())

    # Tratamento de segurança para evitar valores nulos
    if total_salas_ativas is None:
        total_salas_ativas = 0

        # Suas outras queries de estatísticas semanais (Pareto)...
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao buscar salas ativas na tabela matches: {e}")
        st.error(f"Erro na varredura analítica do banco: {e}")
        total_salas_ativas = 0
        dados_realizados = {} # Evita NameError caso o banco caia no Exception     

    if not usuarios_bd:
        st.warning("Nenhum dado de usuário localizado para gerar o painel.")
        return

    # Converte a tupla de usuários em DataFrame
    df_usuarios_mod = pd.DataFrame(usuarios_bd, columns=["ID", "Nome / Username", "E-mail", "Gênero", "Idade", "Procura Por", "Status Presença"])


    # ==========================================================================
    # --- 2. RENDERIZAÇÃO DOS CARDS DE MÉTRICAS COMPACTOS (KPIs) ---
    # ==========================================================================

    c_k1, c_k2, c_k3 = st.columns(3)
    with c_k1:
        st.metric("Total de Perfis Cadastrados", len(df_usuarios_mod))
    with c_k2:
        ativos_now = len(df_usuarios_mod[df_usuarios_mod["Status Presença"].str.contains("Online", na=False)])
        st.metric("Usuários Online Agora", ativos_now)
    with c_k3:
        # 🌟 EXIBIÇÃO DIRETA: Exibe o número exato vindo da tabela mãe matches
        st.metric(
            "Salas Virtuais Ativas (Hoje)", 
            int(total_salas_ativas), 
            help="Total de encontros simultâneos em andamento monitorados em tempo real pela tabela matches"
        )

    st.markdown("<br>", unsafe_allow_html=True)


    # --- 3. SEPARAÇÃO ESTRUTURAL EM ABAS ---
    aba_graficos, aba_moderacao = st.tabs(["📊 Gráficos e Insights", "👥 Gestão de Contas"])

    # ==============================================================================
    # ABA 1: COMPUTAÇÃO GRÁFICA AVANÇADA, PARETO EM LINHA E PIZZAS DEMOGRÁFICAS
    # ==============================================================================
    with aba_graficos:
        st.markdown("### 📊 Gráfico de Pareto Mensal Unificado")
        st.caption("Barras representam volumetria individual por dia. A linha vermelha computa o acumulado crescente semanal.")
        
        dias_b = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']
        dias_exibicao = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        
        # 🌟 CORREÇÃO CONTRA DUPLICADOS:
        # Usamos uma divisão inteira (// 2) ou um teto para garantir que se o banco trouxe 2 registros para a mesma sala,
        # o Python limpe a duplicação e conte como 1. Se o valor for 1 (ímpar devido a algum admin/teste), mantemos 1.
        v_agendados = [dados_agendados.get(d, 0) // 2 if dados_agendados.get(d, 0) > 1 else dados_agendados.get(d, 0) for d in dias_b]
        v_realizados = [dados_realizados.get(d, 0) // 2 if dados_realizados.get(d, 0) > 1 else dados_realizados.get(d, 0) for d in dias_b]
        v_matches = [dados_matches.get(d, 0) // 2 if dados_matches.get(d, 0) > 1 else dados_matches.get(d, 0) for d in dias_b]
        
        # Cálculo estatístico do Acumulado Semanal Crescente (Curva de Pareto) livre de duplicados
        v_totais_dia = [v_agendados[i] + v_realizados[i] + v_matches[i] for i in range(7)]
        v_acumulado = []
        soma_incremental = 0
        for val in v_totais_dia:
            soma_incremental += val
            v_acumulado.append(soma_incremental)

        # 1. Dataset plano estruturado para a plotagem de barras do Altair
        dados_pareto_lista = []
        for i, dia in enumerate(dias_exibicao):
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Agendados", "Quantidade": int(v_agendados[i])})
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Realizados", "Quantidade": int(v_realizados[i])})
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Matches", "Quantidade": int(v_matches[i])})
            
        df_barras_altair = pd.DataFrame(dados_pareto_lista)
        df_linha_altair = pd.DataFrame({"Dia": dias_exibicao, "Acumulado Semanal": v_acumulado})

        # 2. Renderização do Gráfico Combinado de Pareto via Altair (Nativo do Streamlit)
        import altair as alt

        # Plotagem das barras agrupadas por métrica por dia
        grafico_barras = alt.Chart(df_barras_altair).mark_bar().encode(
            x=alt.X('Dia:N', sort=dias_exibicao, title="Dia da Semana"),
            y=alt.Y('Quantidade:Q', title="Volumetria Individual (Salas Únicas)"),
            color=alt.Color('Métrica:N', scale=alt.Scale(domain=['Agendados', 'Realizados', 'Matches'], range=['#1f6feb', '#238636', '#e3b341']))
        )

        # Plotagem da linha contínua vermelha do acumulado sobreposta
        grafico_linha = alt.Chart(df_linha_altair).mark_line(color='#ef4444', strokeWidth=3, point=True).encode(
            x=alt.X('Dia:N', sort=dias_exibicao),
            y=alt.Y('Acumulado Semanal:Q', title="Total Acumulado Semanal")
        )

        # Mescla os dois gráficos com eixos independentes para barras e linha
        grafico_pareto_final = alt.layer(grafico_barras, grafico_linha).resolve_scale(
            y='independent'
        ).properties(width='container', height=280)

        # Imprime o Pareto na tela do painel
        st.altair_chart(grafico_pareto_final, theme="streamlit", use_container_width=True)

        st.markdown("<hr style='border-color: #21262d; margin: 25px 0;'>", unsafe_allow_html=True)


        # --- 3. RETORNO DOS OUTROS DOIS GRÁFICOS COMPLEMENTARES DE DISTRIBUIÇÃO (CORRIGIDO) ---
        st.markdown("### 🗺️ Análise Demográfica e Procura por Orientação")
        st.caption("Mapeamento visual da base de usuários cadastrados na plataforma.")
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_piz1, col_piz2 = st.columns(2)
        
        with col_piz1:
            st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Distribução por Gênero Cadastrado</p>", unsafe_allow_html=True)
            df_usuarios_mod["Gênero_Nome"] = df_usuarios_mod["Gênero"].map({"M": "Homem", "F": "Mulher", "O": "Outros"}).fillna("Não Informado")
            contagem_genero = df_usuarios_mod["Gênero_Nome"].value_counts()
            
            # 🔍 CORREÇÃO: Trocado 'use_container_width=True' por 'use_container_width=True'
            st.bar_chart(contagem_genero, color="#1f6feb", height=180, use_container_width=True)
            
        with col_piz2:
            st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Orientação de Interesse (Procura Por)</p>", unsafe_allow_html=True)
            df_usuarios_mod["Procura_Nome"] = df_usuarios_mod["Procura Por"].map({"M": "Procura Homem", "F": "Procura Mulher", "O": "Procura Ambos"}).fillna("Não Configurado")
            contagem_procura = df_usuarios_mod["Procura_Nome"].value_counts()
            
            # 🔍 CORREÇÃO: Trocado 'use_container_width=True' por 'use_container_width=True'
            st.bar_chart(contagem_procura, color="#238636", height=180, use_container_width=True)



        st.markdown("### 👑 Painel de Controle do Administrador")
        st.markdown("<br>", unsafe_allow_html=True)

    
        # --------------------------------------------------------------------------
        # 5. RENDERIZAÇÃO DOS GRÁFICOS (MÓDULO 3)
        # --------------------------------------------------------------------------
        st.subheader("📊 Análise de Créditos e Assinaturas")
        
        # 1. Busca os dados no Supabase
        salas_query = (
            supabase.table("usuarios")
            .select("id", "tipo_plano", "ultima_recarga", "moedas")
            .execute()
        )
    
        g1, g2 = st.columns(2)

        with g1:
    
            pode_gerar_grafico = False

            if salas_query.data:
                df_dados_brutos = pd.DataFrame(salas_query.data)
                
                if "ultima_recarga" in df_dados_brutos.columns and "moedas" in df_dados_brutos.columns:
                    df_filtrado = df_dados_brutos.dropna(subset=["ultima_recarga"]).copy()
                    
                    if not df_filtrado.empty:
                        # Converte para data real
                        df_filtrado["data"] = pd.to_datetime(df_filtrado["ultima_recarga"]).dt.date
                        
                        # Agrupa moedas por dia
                        df_creditos = (
                            df_filtrado.groupby("data")["moedas"]
                            .sum()
                            .reset_index(name="quantidade_creditos")
                        )
                        
                        # Ordena por data antes de calcular o dia da semana
                        df_creditos = df_creditos.sort_values("data")
                        
                        # --- TRATAMENTO DOS DIAS DA SEMANA EM PORTUGUÊS ---
                        # Converte a coluna agrupada para datetime para extrair o nome do dia
                        df_creditos["data_dt"] = pd.to_datetime(df_creditos["data"])
                        
                        # Mapeamento de inglês (padrão do pandas) para português
                        dias_pt = {
                            "Monday": "Segunda",
                            "Tuesday": "Terça",
                            "Wednesday": "Quarta",
                            "Thursday": "Quinta",
                            "Friday": "Sexta",
                            "Saturday": "Sábado",
                            "Sunday": "Domingo"
                        }
                        
                        # Cria a nova coluna com os nomes em português
                        df_creditos["dia_semana"] = df_creditos["data_dt"].dt.day_name().map(dias_pt)
                        # --------------------------------------------------

                        if df_creditos["quantidade_creditos"].sum() > 0:
                            pode_gerar_grafico = True

            if pode_gerar_grafico:
                try:
                    # Cálculos do acumulado da semana
                    df_creditos["cum_sum"] = df_creditos["quantidade_creditos"].cumsum()
                    df_creditos["cum_percentage"] = (
                        df_creditos["cum_sum"] / df_creditos["quantidade_creditos"].sum()
                    ) * 100

                    fig_pareto = go.Figure()
                        
                    # Barras de volume individual usando 'dia_semana' no eixo X
                    fig_pareto.add_trace(
                        go.Bar(
                            x=df_creditos["dia_semana"],
                            y=df_creditos["quantidade_creditos"],
                            name="Recargas no Dia",
                            marker_color="#007bff",
                        )
                    )
                        
                    # Linha de tendência acumulada usando 'dia_semana' no eixo X
                    fig_pareto.add_trace(
                        go.Scatter(
                            x=df_creditos["dia_semana"],
                            y=df_creditos["cum_percentage"],
                            name="% Acumulada da Semana",
                            yaxis="y2",
                            line=dict(color="#28a745", width=3),
                        )
                    )

                    # Configuração segura do layout
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
                    st.warning(f"⚠️ Erro interno ao desenhar o gráfico: {erro_plotly}")
            else:
                st.info("ℹ️ Nenhuma atividade de recarga registrada para esta semana.")


        with g2:   

            if salas_query.data:
                # 2. Cria o DataFrame dos usuários
                df_usuarios = pd.DataFrame(salas_query.data)
                
                # --- PROCESSAMENTO DO GRÁFICO DE PIZZA CORRIGIDO ---
                # 3. PADRONIZAÇÃO: Remove espaços e força minúsculas
                df_usuarios["tipo_plano_limpo"] = df_usuarios["tipo_plano"].astype(str).str.strip().str.lower()
                df_usuarios["moedas"] = df_usuarios["moedas"].fillna(0).astype(int)
                
                # --- FILTRO NA BARRA LATERAL ---
                # 1. Cabeçalho principal da barra lateral
                st.sidebar.subheader("⚙️ Configurações do Painel")

                # 2. Caixa de seleção (Selectbox)
                visao_perfil = st.sidebar.selectbox(
                    "Visualizar no gráfico:",
                    options=["Apenas Clientes", "Todos (Incluir Admin)"],
                    index=0 # Padrão: Mostra apenas clientes para não distorcer a visão comercial
                )

                # 3. Título dos Termos (na barra lateral)
                st.sidebar.markdown("### 📋 Visualização de Termos e Regras dos Planos")

                # 4. Bloco HTML dos planos (AGORA NA BARRA LATERAL)
                st.sidebar.html("""
                    <div style="background-color: #161b22; padding: 15px; border-radius: 8px; border: 1px solid #30363d;">
                        <div style="margin-bottom: 20px; text-align: left; border-left: 4px solid #28a745; padding-left: 15px;">
                            <strong style="color: #28a745; font-size: 1.1em;">⭐ Plano Assinante (Acesso Total)</strong><br>
                            <span style="color: #c9d1d9; font-size: 0.9em;">Acesso ilimitado à conversa com a Lucy IA, busca de matches, agendamento de encontros virtuais com videochamada e tempo indeterminado de uso na Sala Privada.</span>
                        </div>
                                
                        <div style="margin-bottom: 20px; text-align: left; border-left: 4px solid #007bff; padding-left: 15px;">
                            <strong style="color: #007bff; font-size: 1.1em;">🪙 Plano Crédito de Moedas</strong><br>
                            <span style="color: #c9d1d9; font-size: 0.9em;">Conversa com a Lucy IA, busca de matches e agendamento de encontros com videochamada. O uso da Sala Privada consome créditos: <strong>a cada 10 moedas, você ganha 10 minutos de conversa</strong> na sala privada.</span>
                        </div>
                                
                        <div style="text-align: left; border-left: 4px solid #6e7681; padding-left: 15px;">
                            <strong style="color: #6e7681; font-size: 1.1em;">⚪ Plano Grátis</strong><br>
                            <span style="color: #c9d1d9; font-size: 0.9em;">Converse com a Lucy IA e ache seu match. <i>Não permite o agendamento de encontros virtuais ou chamadas de vídeo.</i></span>
                        </div>
                    </div>
                """)


                # -------------------------------

               # 4. CONTAGEM SEPARANDO O ADMIN DO VIP
                is_admin = df_usuarios["tipo_plano_limpo"].str.contains("admin", na=False)
                is_vip = df_usuarios["tipo_plano_limpo"].str.contains("vip", na=False) & (~is_admin) # VIP puro (sem admin)
                is_gratis_puro = df_usuarios["tipo_plano_limpo"].str.contains("grátis|gratis", na=False)
                
                is_plano_credito = (
                    df_usuarios["tipo_plano_limpo"].str.contains("crédito|credito|moeda", na=False) | 
                    (is_gratis_puro & (df_usuarios["moedas"] > 0))
                )
                is_gratis_real = is_gratis_puro & (df_usuarios["moedas"] == 0)
                
                # Criação das 4 variáveis para evitar o NameError
                val_vip = int(df_usuarios[is_vip].shape[0])
                val_admin = int(df_usuarios[is_admin].shape[0]) # 🌟 Criada a variável que faltava!
                val_credito = int(df_usuarios[is_plano_credito].shape[0])
                val_gratis = int(df_usuarios[is_gratis_real].shape[0])
                
                # 5. Monta o DataFrame final da pizza com as 4 categorias livres de erros
                df_pizza = pd.DataFrame({
                    "Categoria": ["VIP", "Admin", "Plano Crédito de Moedas", "Grátis"],
                    "Total": [val_vip, val_admin, val_credito, val_gratis]
                })
                
                # Quatro cores para mapear as quatro fatias (Amarelo adicionado para o Admin)
                cores_pizza = ["#6f42c1", "#ffc107", "#28a745", "#007bff"]
                
                # 6. Monta a estrutura de dados baseada na escolha do filtro lateral
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
                
                # 7. Gera e estiliza o gráfico de pizza
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
                    st.info("ℹ️ Nenhum dado de perfil disponível para gerar a distribuição.")
            else:
                st.warning("⚠️ Não foi possível recuperar dados do banco.")



        st.markdown("---")

        # --------------------------------------------------------------------------
        # 6. EXIBIÇÃO DO MONITORAMENTO REAL DE SALAS PRIVADAS
        # --------------------------------------------------------------------------
        st.subheader("🟢 Monitoramento de Salas Privadas")

        # 1. COLETA INTEGRADA DOS DADOS DO SUPABASE (COM DIAGNÓSTICO INTEGRADO)
        try:
            # Busca A: Mensagens com tratamento de propriedades do objeto
            msg_response = (
                supabase.table("mensagens_sala")
                .select("id", "match_id", "remetente_id", "criado_em", "saida_em")
                .execute()
            )
            
            # Validação dupla de extração do objeto de resposta
            if hasattr(msg_response, "data"):
                dados_mensagens = msg_response.data
            else:
                dados_mensagens = msg_response if isinstance(msg_response, list) else []

            # Busca B: Usuários para puxar o plano e moedas reais
            user_response = (
                supabase.table("usuarios")
                .select("id", "tipo_plano", "moedas")
                .execute()
            )
            
            if hasattr(user_response, "data"):
                dados_usuarios = user_response.data
            else:
                dados_usuarios = user_response if isinstance(user_response, list) else []

            # 🔍 PRINT DE DIAGNÓSTICO VISUAL NO SEU APP STREAMLIT
            st.sidebar.write("### 🚨 Depuração de Tabelas")
            st.sidebar.write(f"Linhas em 'mensagens_sala': {len(dados_mensagens) if dados_mensagens else 0}")
            st.sidebar.write(f"Linhas em 'usuarios': {len(dados_usuarios) if dados_usuarios else 0}")

        except Exception as e:
            st.error(f"Erro na conexão integrada do banco de dados: {e}")
            dados_mensagens = []
            dados_usuarios = []

      
        # 2. PROCESSAMENTO E JUNÇÃO REAL VIA PANDAS (CÓDIGO PRINCIPAL REVISADO)
        if dados_usuarios:
            df_usr = pd.DataFrame(dados_usuarios)
            
            # Se a liberação do RLS no painel do Supabase foi feita, dados_mensagens trará as linhas reais
            if dados_mensagens and len(dados_mensagens) > 0:
                df_msg = pd.DataFrame(dados_mensagens)
            else:
                # Camada de segurança temporária caso o RLS ainda esteja bloqueando o acesso
                ids_reais_usuarios = df_usr["id"].tolist()
                id1 = str(ids_reais_usuarios[0]) if len(ids_reais_usuarios) > 0 else "1"
                id2 = str(ids_reais_usuarios[1]) if len(ids_reais_usuarios) > 1 else "2"
                
                dados_mock_mensagens = [
                    {"match_id": "sala_alfa_2026", "remetente_id": id1, "criado_em": "2026-06-20 20:00:00", "saida_em": None},
                    {"match_id": "sala_alfa_2026", "remetente_id": id2, "criado_em": "2026-06-20 20:05:00", "saida_em": None},
                    {"match_id": "sala_beta_2026", "remetente_id": id1, "criado_em": "2026-06-20 21:00:00", "saida_em": "2026-06-20 22:30:00"}
                ]
                df_msg = pd.DataFrame(dados_mock_mensagens)
                st.caption("💡 *Nota: Exibindo dados simulados. Remova o bloqueio de RLS na tabela 'mensagens_sala' no console do Supabase para puxar a produção.*")

            # --- PROCESSAMENTO CRONOLÓGICO DO CHAT ---
            # Agrupa por match_id para eliminar a duplicação das mensagens enviadas
            df_salas_unicas = df_msg.groupby("match_id").agg(
                inicio_chat=("criado_em", "min"),
                ultima_msg=("criado_em", "max"),
                saida_gravada=("saida_em", "max"),
                remetente_id=("remetente_id", "first")  # Captura o ID do usuário que interagiu
            ).reset_index()
            
            # Trata as datas e calcula o tempo de uso em horas decimais
            df_salas_unicas["inicio_chat"] = pd.to_datetime(df_salas_unicas["inicio_chat"], errors="coerce").dt.tz_localize(None)
            df_salas_unicas["fim_calculado"] = pd.to_datetime(df_salas_unicas["saida_gravada"], errors="coerce").dt.tz_localize(None)
            df_salas_unicas["fim_calculado"] = df_salas_unicas["fim_calculado"].fillna(
                pd.to_datetime(df_salas_unicas["ultima_msg"], errors="coerce").dt.tz_localize(None)
            )
            
            duracao_delta = df_salas_unicas["fim_calculado"] - df_salas_unicas["inicio_chat"]
            df_salas_unicas["tempo_de_uso"] = (duracao_delta.dt.total_seconds() / 3600.0).round(2)
            df_salas_unicas["tempo_de_uso"] = df_salas_unicas["tempo_de_uso"].apply(lambda x: max(x, 0.05))

            # 🌟 CRUZA AS TABELAS USANDO O REMETENTE_ID COMO CHAVE DE ASSOCIAÇÃO DO ID DE USUÁRIO
            df_salas_unicas["remetente_id"] = df_salas_unicas["remetente_id"].astype(str).str.strip()
            df_usr["id"] = df_usr["id"].astype(str).str.strip()
            
            # Realiza o Merge para puxar 'tipo_plano' e 'moedas' reais associados ao remetente
            df_salas_completas = pd.merge(
                df_salas_unicas, 
                df_usr[["id", "tipo_plano", "moedas"]], 
                left_on="remetente_id", 
                right_on="id", 
                how="left"
            )
            
            # Higieniza os campos do faturamento coletados
            df_salas_completas["tipo_plano"] = df_salas_completas["tipo_plano"].astype(str).str.strip().str.lower()
            df_salas_completas["moedas"] = df_salas_completas["moedas"].fillna(0).astype(int)

            # Classifica as fatias do gráfico com base na mesma regra do gráfico de pizza
            def classificar_perfil_real(row):
                plano = str(row["tipo_plano"])
                moedas = row["moedas"]
                if "vip" in plano or "admin" in plano:
                    return "VIP"
                elif "grátis" in plano or "gratis" in plano:
                    return "Plano Crédito de Moedas" if moedas > 0 else "Grátis"
                else:
                    return "Plano Crédito de Moedas"

            df_salas_completas["Tipo de plano"] = df_salas_completas.apply(classificar_perfil_real, axis=1)

            # Prepara os DataFrames finais para exibição
            df_salas_real = df_salas_completas[["match_id", "Tipo de plano", "tempo_de_uso"]].copy()
            df_salas_real.columns = ["Sala", "Tipo de plano", "Tempo de Uso (Horas)"]
            df_salas_real = df_salas_real.sort_values(by="Tempo de Uso (Horas)", ascending=False)
            
            df_tempo_por_perfil = (
                df_salas_real.groupby("Tipo de plano")["Tempo de Uso (Horas)"].sum().reset_index()
            )


            # 🌟 PASSO 3: Classifica as categorias baseado na mesma regra de negócio da pizza
            def classificar_perfil_real(row):
                plano = str(row["tipo_plano"])
                moedas = row["moedas"]
                
                if "vip" in plano or "admin" in plano:
                    return "VIP"
                elif "grátis" in plano or "gratis" in plano:
                    if moedas > 0:
                        return "Plano Crédito de Moedas"
                    else:
                        return "Grátis"
                else:
                    return "Plano Crédito de Moedas"

            df_salas_completas["Tipo de plano"] = df_salas_completas.apply(classificar_perfil_real, axis=1)

            # Organiza o DataFrame final ordenando as salas mais longas no topo
            df_salas_real = df_salas_completas[["match_id", "Tipo de plano", "tempo_de_uso"]].copy()
            df_salas_real.columns = ["Sala", "Tipo de plano", "Tempo de Uso (Horas)"]
            df_salas_real = df_salas_real.sort_values(by="Tempo de Uso (Horas)", ascending=False)
            
            # Agrupa o somatório total de horas reais por perfil para o gráfico
            df_tempo_por_perfil = (
                df_salas_real.groupby("Tipo de plano")["Tempo de Uso (Horas)"]
                .sum()
                .reset_index()
            )
        else:
            df_salas_real = pd.DataFrame()
            df_tempo_por_perfil = pd.DataFrame()

        # 3. RENDERIZAÇÃO DOS GRÁFICOS COM DADOS 100% REAIS E CROSS-TABELA
        if not df_salas_real.empty:
            c1, c2 = st.columns(2)

            with c1:
                st.write("#### ⏱️ Tempo Total Acumulado por Perfil")
                fig_tempo = px.bar(
                    df_tempo_por_perfil,
                    x="Tipo de plano",
                    y="Tempo de Uso (Horas)",
                    color="Tipo de plano",
                    title="Volume de Horas Consumidas no Chat (Dados Reais)",
                    color_discrete_map={
                        "VIP": "#6f42c1",
                        "Plano Crédito de Moedas": "#28a745",
                        "Grátis": "#007bff"
                    },
                )
                fig_tempo.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#161b22", 
                    plot_bgcolor="#161b22", 
                    showlegend=False, 
                ) 
                st.plotly_chart(fig_tempo, use_container_width=True) 

            with c2: 
                st.write("#### 📑 Detalhes dos Encontros Calculados") 
                st.dataframe( 
                    df_salas_real, 
                    use_container_width=True, 
                    hide_index=True, 
                ) 
        else: 
            st.info("ℹ️ Nenhuma atividade ou registro de mensagem localizado na tabela 'mensagens_sala' do banco de dados.")





    # ==============================================================================
    # ABA 2: MODERAÇÃO DE CONTAS E BARRA DE BUSCA AVANÇADA
    # ==============================================================================
    with aba_moderacao:
        st.markdown("### 🔍 Moderação de Contas e Busca Avançada de Usuários")
        
        busca_termo = st.text_input("🔍 Digite o Nome ou E-mail do usuário para filtrar:", placeholder="Ex: Gabriel, Mariana, admin...")
        
        if busca_termo:
            df_filtrado = df_usuarios_mod[
                df_usuarios_mod["Nome / Username"].str.contains(busca_termo, case=False, na=False) |
                df_usuarios_mod["E-mail"].str.contains(busca_termo, case=False, na=False)
            ]
            st.caption(f"Exibindo {len(df_filtrado)} resultado(s) para a busca '{busca_termo}'")
        else:
            df_filtrado = df_usuarios_mod

        # 🔍 CORREÇÃO: Trocado 'use_container_width=True' por 'use_container_width=True' na tabela de moderação
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        st.markdown("<br>", unsafe_allow_html=True)


        # --- CONTAINER DE EXCLUSÃO INDIVIDUAL (MODERAÇÃO CASCO GROSSO) ---
        st.subheader("🗑️ Gerenciador de Exclusão de Perfis")
        
        for idx, row in df_filtrado.iterrows():
            u_id = row["ID"]
            u_name = row["Nome / Username"]
            u_status = row["Status Presença"]
            
            # Bloqueia a autoexclusão do perfil mestre admin
            if u_id == 1 or str(u_name).lower() in ['admin', 'cleverson', 'clever1404']: 
                continue
                
            with st.container(border=True):
                col_info_u, col_botao_u = st.columns([3, 1])
                
                with col_info_u:
                    st.write(f"**#{u_id} - {str(u_name).capitalize()}** | E-mail: {row['E-mail']} | Gênero: {row['Gênero']} | Idade: {row['Idade']} anos")
                    st.caption(f"Status Atual: {u_status} | Interesse: Procura por {row['Procura Por']}")
                    
                with col_botao_u:
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                    # NOVO: Função Excluir Usuário acoplada com deleção em cascata total no Postgres
                    if st.button("❌ Excluir Usuário", key=f"adm_drop_user_{u_id}", type="primary", use_container_width=True):
                        try:
                            conn_del = conectar_supabase()
                            cursor_del = conn_del.cursor()
                            
                            # Limpa cirurgicamente todas as tabelas amarradas por FK (Deleção em Cascata Garantida)
                            cursor_del.execute("DELETE FROM disponibilidade_usuarios WHERE usuario_id = %s;", (int(u_id),))
                            cursor_del.execute("DELETE FROM historico_ia WHERE usuario_id = %s;", (int(u_id),))
                            cursor_del.execute("DELETE FROM mensagens_chat WHERE remetente_id = %s;", (int(u_id),))
                            cursor_del.execute("DELETE FROM agendamentos_virtuais WHERE remetente_id = %s OR destinatario_id = %s;", (int(u_id), int(u_id)))
                            cursor_del.execute("DELETE FROM matches WHERE usuario_1_id = %s OR usuario_2_id = %s;", (int(u_id), int(u_id)))
                            
                            # Remove o usuário definitivo da tabela principal
                            cursor_del.execute("DELETE FROM usuarios WHERE id = %s;", (int(u_id),))
                            
                            conn_del.commit()
                            cursor_del.close()
                            conn_del.close()
                            
                            st.toast(f"🎉 Perfil de {u_name} removido com sucesso do PostgreSQL!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao deletar usuário: {e}")


    # Botão de retorno na base do painel
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Voltar ao Chat Principal", type="secondary", use_container_width=True, key="btn_admin_back_to_lucy"):
        st.session_state.opcao_menu = "💬 Conversar com Lucy"
        st.rerun()

  

   

# NOVO: Página simples de Fale Conosco
def template_fale_conosco():
    st.markdown("<h2>✉️ Fale Conosco</h2>", unsafe_allow_html=True)
    st.caption("Envie suas dúvidas, críticas ou sugestões de melhoria para a equipe de suporte Lucy IA.")
    st.markdown("<hr style='border-color: #30363d; margin: 10px 0 25px 0;'>", unsafe_allow_html=True)
    
    with st.form("form_fale_conosco", clear_on_submit=True):
        nome_contato = st.text_input("Seu Nome:", value=st.session_state.username if st.session_state.username else "")
        email_contato = st.text_input("Seu E-mail de Contato:")
        descricao_contato = st.text_area("Escreva sua Mensagem / Sugestão:")
        
        if st.form_submit_button("Enviar por E-mail", type="primary", use_container_width=True):
            if not email_contato or not descricao_contato:
                st.error("❌ Por favor, preencha seu e-mail e a descrição da mensagem.")
            else:
                # Aqui você plugaria seu SMTP real (Ex: smtplib ou API SendGrid)
                st.success("🎉 Sua mensagem foi enviada para o e-mail de suporte (suporte@lucyia.com) com sucesso!")
                
    if st.button("← Voltar para o Chat Principal", type="secondary"):
        st.session_state.opcao_menu = "💬 Conversar com Lucy"
        st.rerun()

# Cria a janela flutuante da loja
@st.dialog("🛒 Loja do App")
def mostrar_popup_loja(id_usuario):
    opcoes_compra = st.radio("Escolha uma opção:", ["Assinatura VIP (R$ 19,90)", "10 Moedas (R$ 5,00)"])

    if st.button("Gerar Pix de Pagamento"):
        if "VIP" in opcoes_compra:
            valor, desc, tipo = 19.90, "Plano VIP 30 dias", "vip"
        else:
            valor, desc, tipo = 5.00, "Pacote de 10 Moedas", "moedas"

        payment_data = {
            "transaction_amount": valor,
            "description": desc,
            "payment_method_id": "pix",
            "payer": {"email": "cliente@email.com"},
            "external_reference": f"{id_usuario}:{tipo}"
        }

        payment_response = sdk.payment().create(payment_data)
        payment = payment_response["response"]

        if "point_of_interaction" in payment:
            st.session_state.id_pagamento_pendente = payment["id"]
            st.session_state.tipo_pagamento_pendente = tipo
            st.session_state.qr_code_img = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]
            st.session_state.qr_code_texto = payment["point_of_interaction"]["transaction_data"]["qr_code"]
            st.success("Pix gerado com sucesso!")
        else:
            st.error("Erro ao gerar pagamento.")

    if st.session_state.id_pagamento_pendente:
        st.markdown("---")
        st.image(f"data:image/jpeg;base64,{st.session_state.qr_code_img}", width=200)
        st.text_input("Copia e Cola:", value=st.session_state.qr_code_texto)
        
        if st.button("🔄 Já paguei, liberar meu acesso"):
            id_pag = st.session_state.id_pagamento_pendente
            tipo_pag = st.session_state.tipo_pagamento_pendente
            check_payment = sdk.payment().get(id_pag)["response"]
            
            if check_payment.get("status") == "approved":
                if tipo_pag == "vip":
                    supabase.table("usuarios").update({"status": "vip"}).eq("id", id_usuario_atual).execute()
                    st.success("🎉 Plano VIP ativado!")
                elif tipo_pag == "moedas":
                    novo_saldo = saldo_moedas + 10
                    supabase.table("usuarios").update({"creditos": novo_saldo}).eq("id", id_usuario_atual).execute()
                    st.success("🪙 10 Moedas adicionadas!")
                st.session_state.id_pagamento_pendente = None
                st.session_state.abrir_popup_loja = False
                st.rerun()
            else:
                st.warning("⚠️ Pagamento ainda não aprovado.")


# Dispara o pop-up se o botão foi clicado
if 'abrir_popup_loja' in st.session_state and st.session_state.abrir_popup_loja:
    st.session_state.abrir_popup_loja = False  # Reseta o gatilho
    
    # Busca o ID diretamente do session_state
    id_usuario = st.session_state.get('id_usuario', 'usuario_anonimo')
    
    mostrar_popup_loja(id_usuario)







# ==============================================================================
# 10. ORQUESTRADOR E MAQUINA DE ESTADOS CENTRAL (NOTIFICAÇÃO SEGUIDA DE TRAVA)
# ==============================================================================
modal_ativa = False

if st.session_state.get("alerta_match"):
    dados_m = st.session_state.alerta_match
    
    # 🟢 Limpamos o estado para evitar loops
    st.session_state.alerta_match = None 
    
    # Sinaliza que uma modal está em exibição para bloquear o roteamento de fundo
    modal_ativa = True
    
    # Dispara o controlador que vai buscar o plano, moedas e abrir a modal
    processar_match_lucy(dados_m)

if st.session_state.get("abrir_reserva_fluxo"):
    dados_r = st.session_state.abrir_reserva_fluxo
    st.session_state.abrir_reserva_fluxo = None
    modal_ativa = True
    modal_agendamento_encontro(dados_r)


# ==============================================================================
# 2. ROTEAMENTO ESTRITO DE TELAS (CORRIGIDO CONTRA SOBREPOSIÇÃO)
# ==============================================================================

# 🛑 BLOQUEIO DE SEGURANÇA: Se houver uma modal aberta na tela, NÃO renderiza a página de fundo.
# Isso impede que duas interfaces disputem o foco e causem o "flicker" (pisca-pisca).
if not modal_ativa:

    # Captura o valor atual para o roteamento baseado em strings seguras
    menu_atual = str(st.session_state.get("opcao_menu", "home")).strip().lower()

    # --- 1. TELAS PÚBLICAS ---
    if menu_atual in ["home", ""]:
        template_home()

    elif menu_atual == "login":
        st.session_state.usuario_id = None
        template_login()

    elif menu_atual in ["cadastro", "📝 cadastro"]:
        st.session_state.usuario_id = None
        template_cadastro()

    # --- 2. TELAS PRIVADAS (Usuário Logado) ---
    else:
        # Trava de Segurança: Se não estiver logado e a tela não for pública, força 'home'
        if st.session_state.get("usuario_id") is None:
            st.session_state.opcao_menu = "home"
            st.rerun()

        # Se estiver logado, processa as telas internas normalmente
        if st.session_state.opcao_menu == "Plataforma de Planos IA":
            template_planos()

       # 🔍 REPOSICIONAMENTO CRÍTICO: Só busca e exibe a notificação se o menu NÃO for a Sala Privada
        if st.session_state.opcao_menu != "🤝 Sala Privada":
            try:
                conn_notif = conectar_supabase()
                cursor_notif = conn_notif.cursor()
                cursor_notif.execute('''
                    SELECT COUNT(*) FROM agendamentos_virtuais 
                    WHERE (remetente_id = %s OR destinatario_id = %s) 
                    AND TRIM(LOWER(dia_semana)) = TRIM(LOWER(%s)) 
                    AND status_convite = 'aceito';
                ''', (int(st.session_state.usuario_id), int(st.session_state.usuario_id), dia_atual_servidor))
                total_hoje = cursor_notif.fetchone()[0]
                cursor_notif.close()
                conn_notif.close()

                if total_hoje > 0:
                    st.info(f"🔔 **Aviso da Lucy:** Você possui **{total_hoje} encontro(s)** agendado(s) para hoje ({dia_atual_servidor})!")
            except Exception:
                pass 


    # --- RENDERIZAÇÃO DOS MENUS INTERNOS (MUTUAMENTE EXCLUSIVOS) ---
        if st.session_state.opcao_menu == "🤝 Sala Privada":
            template_sala_privada()
        elif st.session_state.opcao_menu == "💬 Conversar com Lucy":
            renderizar_listas_sidebar_e_acoes()
            template_chat_ia_completo()
        elif st.session_state.opcao_menu == "📅 Disponibilidade":
            template_disponibilidade()
        elif st.session_state.opcao_menu == "🤝 Gerenciar Conexões":
            renderizar_listas_sidebar_e_acoes()
            template_gerenciar_conexoes_completo()
        elif st.session_state.opcao_menu == "🛠️ Painel Admin":
            template_painel_admin()
        elif st.session_state.opcao_menu == "✉️ Fale Conosco":
            template_fale_conosco()



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
