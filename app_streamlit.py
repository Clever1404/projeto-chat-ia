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
    st.session_state.opcao_menu == "login"
    st.markdown('<h1 style="text-align:center; color:#007bff;">Login Lucy Chat IA</h1>', unsafe_allow_html=True)
            
    with st.form("form_login"):
        user_in = st.text_input("Usuário", placeholder="Nome de Usuário ou E-mail", label_visibility="collapsed")
        pass_in = st.text_input("Senha", placeholder="Senha", type="password", label_visibility="collapsed")
                
        if st.form_submit_button("login", type="primary", use_container_width=True):
            try:
                conn = conectar_supabase()
                cursor = conn.cursor()
                cursor.execute("SELECT id, username, foto_perfil, is_admin, genero FROM usuarios WHERE username = %s OR email = %s;", (user_in, user_in))
                res = cursor.fetchone()
                        
                if res:
                    # Salva os dados na sessão
                    st.session_state.usuario_id = res[0]
                    st.session_state.username = res[1]
                    st.session_state.foto_perfil = res[2]
                    st.session_state.eh_admin = res[3]
                    st.session_state.genero = res[4]
                            
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
            st.session_state.opcao_menu = "home"  # Deve ser igual ao topo
            st.rerun()
                    
    with col_esqueceu:
        # Inicializa o estado para controlar a abertura do modal
        if "mostrar_recuperar_senha" not in st.session_state:
            st.session_state.mostrar_recuperar_senha = False

        # DEFINE O DIÁLOGO (Apenas decora a função)
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
    
    st.markdown('<h1 style="text-align:center; color:#007bff;">Plataforma de Planos IA</h1>', unsafe_allow_html=True)
    
    
    # --- TEXTO DESCRITIVO DOS PLANOS CENTRALIZADO ---
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
    
    if st.button("← Voltar para o 🔒 Login", use_container_width=True):
        st.session_state.opcao_menu = "login"  # o nome correto do seu menu de chat
        st.rerun()

    if "id_pagamento_pendente" not in st.session_state:
        st.session_state.id_pagamento_pendente = None
    if "tipo_pagamento_pendente" not in st.session_state:
        st.session_state.tipo_pagamento_pendente = None

    # --- Seu código complementar de exibição de planos continua aqui ---
    # =========================================================================
    # SEÇÃO DE COMPRAS (MERCADO PAGO)
    # =========================================================================
    st.sidebar.header("🛒 Loja do App")

    opcoes_compra = st.sidebar.radio("Escolha uma opção:", ["Assinatura VIP (R$ 19,90)", "10 Moedas (R$ 5,00)"])

    if st.sidebar.button("Gerar Pix de Pagamento"):
        # Configura o valor e descrição baseado na escolha do menu lateral
        if "VIP" in opcoes_compra:
            valor, desc, tipo = 19.90, "Plano VIP 30 dias", "vip"
        else:
            valor, desc, tipo = 5.00, "Pacote de 10 Moedas", "moedas"

        payment_data = {
            "transaction_amount": valor,
            "description": desc,
            "payment_method_id": "pix",
            "payer": {"email": "cliente@email.com"},
            # Correção: Alterado de id_usuario para id_usuario_atual na linha abaixo
            "external_reference": f"{id_usuario_atual}:{tipo}"
        }

        # Criando o Pix na API do Mercado Pago
        payment_response = sdk.payment().create(payment_data)
        payment = payment_response["response"]

        if "point_of_interaction" in payment:
            # Salva o ID do pagamento gerado para checar depois
            st.session_state.id_pagamento_pendente = payment["id"]
            st.session_state.tipo_pagamento_pendente = tipo
            
            # Dados para exibição do Pix
            st.session_state.qr_code_img = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]
            st.session_state.qr_code_texto = payment["point_of_interaction"]["transaction_data"]["qr_code"]
            st.sidebar.success("Pix gerado com sucesso!")
        else:
            st.sidebar.error("Erro ao gerar pagamento. Verifique as credenciais.")

    # Exibe o Pix gerado se ele existir na sessão atual
    if st.session_state.id_pagamento_pendente:
        st.sidebar.markdown("---")
        st.sidebar.image(f"data:image/jpeg;base64,{st.session_state.qr_code_img}", width=200)
        st.sidebar.text_input("Copia e Cola:", value=st.session_state.qr_code_texto)
        
        # BOTÃO CHAVE: O usuário clica após pagar para o código validar na hora
        if st.sidebar.button("🔄 Já paguei, liberar meu acesso"):
            # Consulta o status do pagamento direto na API do Mercado Pago
            id_pag = st.session_state.id_pagamento_pendente
            tipo_pag = st.session_state.tipo_pagamento_pendente
            
            check_payment = sdk.payment().get(id_pag)["response"]
            status_pagamento = check_payment.get("status")

            if status_pagamento == "approved":
                if tipo_pag == "vip":
                    # Atualiza para VIP no Supabase
                    # Correção: Alterado de id_usuario para id_usuario_atual na linha abaixo
                    supabase.table("usuarios").update({"status": "vip"}).eq("id", id_usuario_atual).execute()
                    st.success("🎉 Parabéns! Seu plano VIP foi ativado.")
                elif tipo_pag == "moedas":
                    # Soma as novas moedas no Supabase
                    novo_saldo = saldo_moedas + 10
                    # Correção: Alterado de id_usuario para id_usuario_atual na linha abaixo
                    supabase.table("usuarios").update({"creditos": novo_saldo}).eq("id", id_usuario_atual).execute()
                    st.success("🪙 10 Moedas adicionadas com sucesso ao seu saldo!")
                
                # Limpa as variáveis de pagamento pendente da tela
                st.session_state.id_pagamento_pendente = None
                st.rerun()
            else:
                st.sidebar.warning("⚠️ Pagamento ainda não consta como aprovado. Aguarde alguns instantes e tente novamente.")
     



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
def modal_match_lucy(dados_m):
    # 🔍 SINCRONIZAÇÃO DE PERMISSÕES DO USUÁRIO EM TEMPO REAL
    id_usuario = st.session_state.get("usuario_id", None)
    saldo_moedas = 0
    tipo_plano = "Grátis"
    
    if id_usuario:
        try:
            # Garante dados frescos do banco de dados
            user_query = supabase.table("usuarios").select("moedas", "tipo_plano").eq("id", id_usuario).execute()
            if user_query.data and len(user_query.data) > 0:
                saldo_moedas = user_query.data[0].get("moedas", 0)
                tipo_plano = user_query.data[0].get("tipo_plano", "Grátis")
        except Exception:
            pass

    st.markdown(f"Lucy identificou uma excelente afinidade entre você e **{dados_m['nome']}**!")
    
    # 🟢 COMPORTAMENTO SE O PAR ESTIVER ONLINE: Controle de acesso à Sala Privada
    if dados_m["online"]:
        st.markdown(f"🟢 **{dados_m['nome']} está online agora!**")
        
        # Validação baseada no Plano do Usuário
        if tipo_plano == "Assinante":
            if st.button("🚀 Entrar na Sala Privada (Acesso Total Ilimitado)", type="primary", use_container_width=True):
                st.session_state.match_id_atual = dados_m["match_id"]
                st.session_state.tempo_limite_sala = -1  # Tempo indeterminado
                st.session_state.opcao_menu = "🤝 Sala Privada"
                st.rerun()
                
        elif tipo_plano == "Crédito":
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
            if tipo_plano in ["Assinante", "Crédito"]:
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
        
        def limpar_id_absoluto(id_bruto):
            while isinstance(id_bruto, (tuple, list)):
                if len(id_bruto) > 0: id_bruto = id_bruto[0]
                else: return 0
            try: return int(id_bruto)
            except (TypeError, ValueError): return 0

        m_id_limpo = limpar_id_absoluto(dados_r.get('m_id'))
        meu_id_limpo = limpar_id_absoluto(st.session_state.usuario_id)
        parceiro_id_limpo = limpar_id_absoluto(dados_r.get('id_par'))

        # --- 2. TRAVA DE DISPONIBILIDADE DIRETA NO POSTGRESQL ---
        meu_registro_existe = False
        parceiro_registro_existe = False
        parceiro_tem_algum_horario = False
        
        try:
            conn_check = conectar_supabase()
            cursor_check = conn_check.cursor()
            
            cursor_check.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s 
                  AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) 
                  AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (meu_id_limpo, str(dia_s), str(per_s)))
            meu_registro_existe = (cursor_check.fetchone()[0] > 0)
            
            cursor_check.execute("SELECT COUNT(*) FROM disponibilidade_usuarios WHERE usuario_id = %s;", (parceiro_id_limpo,))
            parceiro_tem_algum_horario = (cursor_check.fetchone()[0] > 0)
            
            cursor_check.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s 
                  AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) 
                  AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (parceiro_id_limpo, str(dia_s), str(per_s)))
            parceiro_registro_existe = (cursor_check.fetchone()[0] > 0)
            
            cursor_check.close()
            conn_check.close()
            
        except Exception as e:
            st.error(f"Erro ao consultar disponibilidade: {e}")

        # --- 3. EXECUÇÃO DAS TRAVAS E PERSISTÊNCIA COMPLETA ---
        if per_s == 'manha' and (hora_int < 6 or hora_int >= 12):
            st.error("❌ Horário inválido! Para o período da manhã, ajuste entre **06:00 e 11:59**.")
        elif per_s == 'tarde' and (hora_int < 12 or hora_int >= 18):
            st.error("❌ Horário inválido! Para o período da tarde, ajuste entre **12:00 e 17:59**.")
        elif per_s == 'noite' and (hora_int < 18 or hora_int > 23):
            st.error("❌ Horário inválido! Para o período da noite, ajuste entre **18:00 e 23:59**.")
            
        elif not meu_registro_existe:
            st.error(f"❌ **Agendamento Recusado:** Você ({st.session_state.username}) configurou este dia/período como indisponível.")
            
        elif os_tem_horarios := (parceiro_tem_algum_horario and not parceiro_registro_existe):
            st.error(f"❌ **Agendamento Recusado:** {dados_r['nome_par']} está indisponível na {dia_s} no período selecionado.")
            
        else:
            try:
                # Gravação atômica da agenda finalizada com sucesso no banco de dados relacional
                conn = conectar_supabase()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO agendamentos_virtuais (
                        match_id, remetente_id, destinatario_id, dia_semana, periodo, horario_exato, status_convite
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'aceito');
                ''', (m_id_limpo, meu_id_limpo, parceiro_id_limpo, str(dia_s), str(per_s), str(hor_s)))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                st.success(f"🎉 Encontro agendado com sucesso para {dia_s} às {hor_s}!")
                st.session_state.abrir_reserva_fluxo = None
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar agendamento no banco: {e}")
                

# ==============================================================================
# 8. REESTRUTURAÇÃO DA SALA PRIVADA (LAYOUT FIXO, FOTO REAL E LIMPAR HISTÓRICO)
# ==============================================================================

def template_sala_privada():
    match_id = st.session_state.match_id_atual
    
    st.markdown("""
        <style>
        .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
        .box-perfil-fixo { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; margin-bottom: 15px; text-align: center; }
        .foto-parceiro-sala { width: 70px !important; height: 70px !important; border-radius: 50% !important; object-fit: cover !important; border: 2px solid #30363d !important; margin: 0 auto 10px auto; display: block; }
        </style>
    """, unsafe_allow_html=True)
    
    # Inicialização limpa de variáveis
    parceiro_nome = "Usuário"
    parceiro_foto = None
    parceiro_gen = "M"
    status_parceiro = "⚫ Offline"
    status_cor = "#a0aec0"
    
    try:
        conn = conectar_supabase()
        cursor = conn.cursor()
        
        # Garante ID como inteiro puro
        id_match_int = match_id[0] if isinstance(match_id, (tuple, list)) else int(match_id)
        cursor.execute("SELECT usuario_1_id, usuario_2_id FROM matches WHERE id = %s;", (id_match_int,))
        res_m = cursor.fetchone()
        
        if res_m:
            u1, u2 = int(res_m[0]), int(res_m[1])
            meu_id_limpo = st.session_state.usuario_id[0] if isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)
            
            # Identifica quem é o parceiro de conversa humana
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

    # --- DIVISÃO DA TELA EM COLUNAS ---
    col_lateral_fixa, col_chat_principal = st.columns([1, 2.8])
    
    with col_lateral_fixa:
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
            
        # 🔍 RETÂNGULO DO PERFIL FIXADO (Nome e string split tratados sem quebras)
        nome_exibicao_parceiro = parceiro_nome.split('@')[0].capitalize()
        st.markdown(f"""
            <div class="box-perfil-fixo">
                {avatar_html}
                <h3 style="margin: 0; font-size: 16px; font-weight: bold; color: #f0f6fc;">{nome_exibicao_parceiro}</h3>
                <p style="color: {status_cor}; font-weight: bold; font-size: 13px; margin: 5px 0 0 0;">{status_parceiro}</p>
            </div>
        """, unsafe_allow_html=True)
            
        st.markdown("""
            <div class="info-box-segura" style="margin-bottom: 15px;">
                <h3>🔒 Ambiente Seguro</h3>
                <p>Esta é uma sala de transmissão privada e criptografada temporária. Suas mensagens serão armazenadas de forma segura nesta sessão de encontro.</p>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Sair da Sala Privada", type="primary", use_container_width=True):
            st.session_state.match_id_atual = None
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()
            
        if st.button("🗑️ Limpar Histórico do Chat", type="secondary", use_container_width=True):
            try:
                conn = conectar_supabase(); cursor = conn.cursor()
                cursor.execute("DELETE FROM mensagens_chat WHERE match_id = %s;", (int(id_match_int),))
                conn.commit(); cursor.close(); conn.close()
                st.toast("Histórico da sala privada limpo com sucesso!")
                st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    with col_chat_principal:
        st.markdown(f"## 💬 Chat Privado — ID #{id_match_int}")
        st.caption("Aproveite o seu encontro virtual reservado.")
        st.markdown("<hr style='border-color: #30363d; margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
        st.title("💬 Chat Privado com Suporte a Vídeo")

               # Nova funcionalidade: Botão para iniciar a videochamada
        if st.button("🎥 Iniciar Videochamada Privada"):
            nome_da_sala_unica = f"Atendimento_FaleConosco_SalaPrivada_{id_match_int}"
            
            # URL 100% CORRIGIDA COM A BARRA E O DOMÍNIO CORRETO:
            url_jitsi = f"https://meet.jit.si/{nome_da_sala_unica}"
            
            st.info("A videochamada foi iniciada abaixo. Dê permissão de câmera/microfone no seu navegador.")

            # Comando nativo corrigido e sem o parâmetro inválido
            st.iframe(url_jitsi, height=600)
            

        # 📥 MOTOR FRAGMENTADO AS SÍNCRONO REATIVO (ATUALIZA A CADA 2 SEGUNDOS)
        @st.fragment(run_every=2)
        def live_chat_privado_engine(m_id, my_id, p_nome_str):
            # Tratamento seguro do nome
            try:
                nome_exibicao = p_nome_str.split('@')[0].capitalize()
            except Exception:
                nome_exibicao = str(p_nome_str).capitalize()

            with st.container(height=410, border=False):
                try:
                    conn = conectar_supabase()
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT remetente_id, texto, data_envio FROM mensagens_chat WHERE match_id = %s ORDER BY data_envio ASC;', 
                        (int(m_id),)
                    )
                    rows = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    # ==============================================================================
                    # GERENCIAMENTO DE TEMPO EM TEMPO REAL (SALA PRIVADA)
                    # ==============================================================================
                    # Inicializa o marcador de tempo se ele não existir na sessão
                    if "tempo_inicio_sala" not in st.session_state:
                        import time
                        st.session_state.tempo_inicio_sala = time.time()

                    # Busca o plano do usuário atualizado para aplicar as regras
                    tipo_plano_sala = "Grátis"
                    saldo_moedas_sala = 0
                    try:
                        user_data = supabase.table("usuarios").select("tipo_plano", "moedas").eq("id", int(my_id)).execute()
                        if user_data.data and len(user_data.data) > 0:
                            tipo_plano_sala = user_data.data[0].get("tipo_plano", "Grátis")
                            saldo_moedas_sala = user_data.data[0].get("moedas", 0)
                    except Exception:
                        pass

                    # Lógica de controle do Timer para usuários do plano de Crédito
                    if tipo_plano_sala == "Crédito":
                        import time
                        tempo_decorrido = time.time() - st.session_state.tempo_inicio_sala
                        
                        # Limite inicial de 10 minutos (600 segundos)
                        tempo_limite_segundos = 600 
                        tempo_restante = tempo_limite_segundos - tempo_decorrido

                        if tempo_restante > 0:
                            minutos_r = int(tempo_restante // 60)
                            segundos_r = int(tempo_restante % 60)
                            # Exibe um contador visual no topo do chat privado
                            st.warning(f"⏳ **Tempo Restante nesta sessão:** {minutos_r:02d}:{segundos_r:02d} | Saldo Atual: 🪙 {saldo_moedas_sala} moedas")
                            
                            # Executa um auto-refresh a cada 5 segundos para atualizar o cronômetro sem travar o input de texto
                            st.fragment(lambda: time.sleep(5) or st.rerun())()
                        else:
                            # O tempo acabou! Tenta renovar debitando mais 10 moedas por +10 minutos
                            if saldo_moedas_sala >= 10:
                                try:
                                    supabase.table("usuarios").update({"moedas": saldo_moedas_sala - 10}).eq("id", int(my_id)).execute()
                                    st.session_state.tempo_inicio_sala = time.time() # Reseta o cronômetro para mais 10 minutos
                                    st.toast("🪙 Mais 10 minutos adicionados! 10 moedas foram debitadas do seu saldo.", icon="🪙")
                                    st.rerun()
                                except Exception:
                                    st.error("Erro ao renovar tempo. Encerrando sala...")
                                    st.session_state.opcao_menu = "Plataforma de Planos IA"
                                    st.rerun()
                            else:
                                # Se não houver saldo suficiente, expulsa da sala imediatamente
                                st.error("🔒 Seus 10 minutos acabaram e você não tem moedas suficientes para renovar.")
                                time.sleep(3)
                                st.session_state.opcao_menu = "Plataforma de Planos IA"
                                st.rerun()
                                
                    elif tipo_plano_sala == "Assinante":
                        st.success(f"⭐ **Plano Assinante Ativo:** Você possui acesso ilimitado por tempo indeterminado nesta sala.")

                    # ==============================================================================
                    # RENDERIZAÇÃO E HISTÓRICO DE MENSAGENS (SEU CÓDIGO ORIGINAL)
                    # ==============================================================================
                    for r_id, txt, dt in rows:
                        # Tratamento seguro contra valores None/Nulos na data
                        if dt is not None:
                            hora_f = dt.strftime("%H:%M")
                        else:
                            hora_f = "--:--"  # Fallback caso a data antiga esteja nula
                        
                        if int(r_id) == int(my_id):
                            with st.chat_message("user"):
                                st.write(txt)
                                st.caption(f"Você — {hora_f}")
                        else:
                            with st.chat_message("assistant"):
                                st.write(txt)
                                st.caption(f"{nome_exibicao} — {hora_f}")
                except Exception as e:
                    st.error(f"Erro ao ler banco: {e}")

            if st.session_state.opcao_menu == "🤝 Sala Privada":
                if txt_in := st.chat_input("Digite sua mensagem privada...", key="priv_chat_input"):
                    if txt_in.strip():
                        try:
                            conn = conectar_supabase()
                            conn.autocommit = True 
                            cursor = conn.cursor()
                            
                            cursor.execute(
                                'INSERT INTO mensagens_chat (match_id, remetente_id, texto, data_envio) VALUES (%s, %s, %s, NOW());', 
                                (int(m_id), int(my_id), txt_in.strip())
                            )
                            
                            conn.commit() 
                            cursor.close()
                            conn.close()
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao enviar: {e}")

            # --- EXECUÇÃO DO MOTOR DE CHAT DE FORMA LIMPA ---
            live_sala_id = match_id[0] if isinstance(match_id, (tuple, list)) else int(match_id)
            meu_id_sala = st.session_state.usuario_id[0] if isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)

            live_chat_privado_engine(live_sala_id, meu_id_sala, parceiro_nome)



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
            user_data = supabase.table("usuarios").select("tipo_plano", "moedas").eq("id", int(my_id)).execute()
            if user_data.data and len(user_data.data) > 0:
                # CORREÇÃO: Remova o "_sala" do final dos nomes das variáveis
                tipo_plano = user_data.data[0].get("tipo_plano", "Grátis")
                saldo_moedas = user_data.data[0].get("moedas", 0)
        except Exception:
            pass

        # Agora o texto vai exibir os dados atualizados que vieram do Supabase
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
            st.session_state.opcao_menu = "📅 Disponibilidade"; st.rerun() 

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
                    if st.button("💬 Entrar", key=f"go_ch_h_{m_id}", type="primary", use_container_width=True):
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
                            if st.button("✅ Confirmar", key=f"side_ok_{ag_id}", type="primary", use_container_width=True):
                                conn = conectar_supabase(); cursor = conn.cursor(); cursor.execute("UPDATE agendamentos_virtuais SET status_convite = 'aceito' WHERE id = %s;", (ag_id,)); conn.commit(); cursor.close(); conn.close(); st.rerun()
                        elif status == 'aceito':
                            if st.button("🟢 Entrar", key=f"side_g_{ag_id}", type="primary", use_container_width=True):
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
    dados_realizados = {}
    dados_matches = {}
    total_salas_ativas = 0

    try:
        conn = conectar_supabase()
        cursor = conn.cursor()
        
        # Busca a lista completa de moderação de usuários
        cursor.execute("SELECT id, username, email, genero, idade, procura_por, status FROM usuarios ORDER BY id ASC;")
        usuarios_bd = cursor.fetchall()
        
        # Contador Real de Salas Virtuais Online Simultâneas (Encontros confirmados ocorrendo HOJE)
        cursor.execute("""
            SELECT COUNT(DISTINCT match_id) FROM agendamentos_virtuais 
            WHERE status_convite = 'aceito' 
              AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s));
        """, (dia_atual_servidor,))
        total_salas_ativas = cursor.fetchone()[0]

        # Estatísticas Semanais por Dia para o Gráfico de Pareto
        cursor.execute("SELECT TRIM(LOWER(dia_semana)), COUNT(*) FROM agendamentos_virtuais GROUP BY 1;")
        dados_agendados = dict(cursor.fetchall())
        
        cursor.execute("""
            SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT mc.id) 
            FROM agendamentos_virtuais a 
            JOIN mensagens_chat mc ON mc.match_id = a.match_id 
            GROUP BY 1;
        """)
        dados_realizados = dict(cursor.fetchall())
        
        cursor.execute("""
            SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT m.id) 
            FROM agendamentos_virtuais a 
            JOIN matches m ON m.id = a.match_id 
            GROUP BY 1;
        """)
        dados_matches = dict(cursor.fetchall())

        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro na varredura analítica do banco: {e}")

    if not usuarios_bd:
        st.warning("Nenhum dado de usuário localizado para gerar o painel.")
        return

    # Converte a tupla de usuários em DataFrame para facilitar as plotagens de Pizza e buscas
    df_usuarios_mod = pd.DataFrame(usuarios_bd, columns=["ID", "Nome / Username", "E-mail", "Gênero", "Idade", "Procura Por", "Status Presença"])

    # --- 2. RENDERIZAÇÃO DOS CARDS DE MÉTRICAS COMPACTOS (KPIs) ---
    c_k1, c_k2, c_k3 = st.columns(3)
    with c_k1:
        st.metric("Total de Perfis Cadastrados", len(df_usuarios_mod))
    with c_k2:
        ativos_now = len(df_usuarios_mod[df_usuarios_mod["Status Presença"].str.contains("Online", na=False)])
        st.metric("Usuários Online Agora", ativos_now)
    with c_k3:
        # Contador de salas humanas ativas online requisitado
        st.metric("Salas Virtuais Ativas (Hoje)", total_salas_ativas, help="Total de salas de encontros confirmados abertas para transmissão hoje")

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
        
        # Coleta das volumetrias individuais mapeadas das queries do banco de dados
        v_agendados = [dados_agendados.get(d, 0) for d in dias_b]
        v_realizados = [dados_realizados.get(d, 0) for d in dias_b]
        v_matches = [dados_matches.get(d, 0) for d in dias_b]
        
        # Cálculo estatístico do Acumulado Semanal Crescente (Curva de Pareto)
        v_totais_dia = [v_agendados[i] + v_realizados[i] + v_matches[i] for i in range(7)]
        v_acumulado = []
        soma_incremental = 0
        for val in v_totais_dia:
            soma_incremental += val
            v_acumulado.append(soma_incremental)

        # 1. Dataset plano estruturado para a plotagem de barras do Altair
        dados_pareto_lista = []
        for i, dia in enumerate(dias_exibicao):
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Agendados", "Quantidade": v_agendados[i]})
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Realizados", "Quantidade": v_realizados[i]})
            dados_pareto_lista.append({"Dia": dia, "Métrica": "Matches", "Quantidade": v_matches[i]})
            
        df_barras_altair = pd.DataFrame(dados_pareto_lista)
        df_linha_altair = pd.DataFrame({"Dia": dias_exibicao, "Acumulado Semanal": v_acumulado})

        # 2. Renderização do Gráfico Combinado de Pareto via Altair (Nativo do Streamlit)
        import altair as alt

        # Plotagem das barras agrupadas por métrica por dia
        grafico_barras = alt.Chart(df_barras_altair).mark_bar().encode(
            x=alt.X('Dia:N', sort=dias_exibicao, title="Dia da Semana"),
            y=alt.Y('Quantidade:Q', title="Volumetria Individual"),
            color=alt.Color('Métrica:N', scale=alt.Scale(domain=['Agendados', 'Realizados', 'Matches'], range=['#1f6feb', '#238636', '#e3b341']))
        )

        # Plotagem da linha contínua vermelha do acumulado sobreposta
        grafico_linha = alt.Chart(df_linha_altair).mark_line(color='#ef4444', strokeWidth=3, point=True).encode(
            x=alt.X('Dia:N', sort=dias_exibicao),
            y=alt.Y('Acumulado Semanal:Q', title="Total Acumulado")
        )

        # Mescla os dois gráficos com eixos independentes para barras e linha
        grafico_pareto_final = alt.layer(grafico_barras, grafico_linha).resolve_scale(
            y='independent'
        ).properties(width='container', height=280)

        # Imprime o Pareto na tela do painel
        st.altair_chart(grafico_pareto_final, theme="streamlit")

        st.markdown("<hr style='border-color: #21262d; margin: 25px 0;'>", unsafe_allow_html=True)
        
        # --- 3. RETORNO DOS OUTROS DOIS GRÁFICOS COMPLEMENTARES DE DISTRIBUIÇÃO ---
        st.markdown("### 🗺️ Análise Demográfica e Procura por Orientação")
        st.caption("Mapeamento visual da base de usuários cadastrados na plataforma.")
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_piz1, col_piz2 = st.columns(2)
        
        with col_piz1:
            st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Distribução por Gênero Cadastrado</p>", unsafe_allow_html=True)
            df_usuarios_mod["Gênero_Nome"] = df_usuarios_mod["Gênero"].map({"M": "Homem", "F": "Mulher", "O": "Outros"}).fillna("Não Informado")
            contagem_genero = df_usuarios_mod["Gênero_Nome"].value_counts()
            
            st.bar_chart(contagem_genero, color="#1f6feb", height=180, use_container_width=True)
            
        with col_piz2:
            st.markdown("<p style='font-size:14px; font-weight:bold; text-align:center; color:#f0f6fc;'>Orientação de Interesse (Procura Por)</p>", unsafe_allow_html=True)
            df_usuarios_mod["Procura_Nome"] = df_usuarios_mod["Procura Por"].map({"M": "Procura Homem", "F": "Procura Mulher", "O": "Procura Ambos"}).fillna("Não Configurado")
            contagem_procura = df_usuarios_mod["Procura_Nome"].value_counts()
            
            st.bar_chart(contagem_procura, color="#238636", height=180, use_container_width=True)


        st.markdown("### 👑 Painel de Controle do Administrador")
        st.markdown("<br>", unsafe_allow_html=True)

        # Configuração inicial do Streamlit (opcional, remova se já tiver no topo do seu código)
        st.set_page_config(layout="wide")

        # --------------------------------------------------------------------------
        # MÓDULO 1: CONSULTA DE DADOS REAIS NO SUPABASE
        # --------------------------------------------------------------------------
        try:
            # Busca os dados reais da sua tabela 'usuarios'
            usuarios_query = (
                supabase.table("usuarios")
                .select("id", "tipo_plano", "moedas", "ultima_recarga")
                .execute()
            )

            if usuarios_query.data:
                df_users = pd.DataFrame(usuarios_query.data)

                # Trata e padroniza a coluna de data para o formato Ano-Mês-Dia
                df_users["ultima_recarga"] = pd.to_datetime(
                    df_users["ultima_recarga"]
                ).dt.strftime("%Y-%m-%d")
            else:
                # Cria colunas vazias de segurança caso não retorne nada
                df_users = pd.DataFrame(
                    columns=["id", "tipo_plano", "moedas", "ultima_recarga"]
                )

        except Exception as e:
            st.error(f"Erro ao carregar dados do Supabase: {e}")
            st.stop()


        # --------------------------------------------------------------------------
        # MÓDULO 2: PROCESSAMENTO E AGREGAÇÃO DOS DADOS REAIS
        # --------------------------------------------------------------------------
        try:
            if not df_users.empty:
                # --- CÁLCULO PARA O GRÁFICO DE PIZZA (Distribuição de Usuários) ---
                # Assinantes: quem não usa o plano gratuito
                total_assinantes = int(
                    df_users[df_users["tipo_plano"] != "gratis"].shape
                )

                # Com Créditos: usuários do plano grátis que têm moedas > 0
                total_credito = int(
                    df_users[
                        (df_users["tipo_plano"] == "gratis") & (df_users["moedas"] > 0)
                    ].shape
                )

                # Sem Assinatura: usuários do plano grátis com 0 moedas
                total_gratis = int(
                    df_users[
                        (df_users["tipo_plano"] == "gratis")
                        & (df_users["moedas"] == 0)
                    ].shape
                )

                # --- CÁLCULO PARA O GRÁFICO DE PARETO (Volume Real de Moedas por Data) ---
                # Agrupa a tabela real somando as moedas de quem recarregou na mesma data
                df_creditos = (
                    df_users.groupby("ultima_recarga")["moedas"]
                    .sum()
                    .reset_index()
                )
                df_creditos.columns = ["data", "quantidade_creditos"]

                # Filtra apenas os últimos 7 dias com movimentação para o gráfico não poluir
                df_creditos = df_creditos.sort_values(by="data", ascending=False).head(
                    7
                )

            else:
                # Fallbacks de segurança se a tabela estiver completamente vazia
                total_assinantes, total_credito, total_gratis = 0, 0, 0
                df_creditos = pd.DataFrame(
                    columns=["data", "quantidade_creditos"]
                )

        except Exception as e:
            st.error(f"Erro ao processar métricas reais: {e}")
            total_assinantes, total_credito, total_gratis = 0, 0, 0
            df_creditos = pd.DataFrame(
                columns=["data", "quantidade_creditos"]
            )


        # --------------------------------------------------------------------------
        # MÓDULO 3: GRÁFICOS (PARETO, ACUMULADO E DISTRIBUIÇÃO)
        # --------------------------------------------------------------------------
        st.subheader("📊 Análise de Créditos e Assinaturas")
        g1, g2 = st.columns(2)

        with g1:
            # Cálculo de Pareto e Linha Acumulada
            df_creditos = df_creditos.sort_values(
                by="quantidade_creditos", ascending=False
            )
            df_creditos["cum_sum"] = df_creditos["quantidade_creditos"].cumsum()
            df_creditos["cum_percentage"] = (
                df_creditos["cum_sum"] / df_creditos["quantidade_creditos"].sum()
            ) * 100

            # Montagem do Gráfico Combinado (Pareto + Linha Semanal)
            fig_pareto = go.Figure()
            fig_pareto.add_trace(
                go.Bar(
                    x=df_creditos["data"],
                    y=df_creditos["quantidade_creditos"],
                    name="Créditos por Dia",
                    marker_color="#007bff",
                )
            )
            fig_pareto.add_trace(
                go.Scatter(
                    x=df_creditos["data"],
                    y=df_creditos["cum_percentage"],
                    name="% Acumulada",
                    yaxis="y2",
                    line=dict(color="#28a745", width=3),
                )
            )

            fig_pareto.update_layout(
                title="Consumo de Créditos (Pareto & Tendência Semanal)",
                yaxis=dict(title="Quantidade de Créditos"),
                yaxis2=dict(
                    title="Percentual Acumulado (%)",
                    overlaying="y",
                    side="right",
                    range=[0, 105],
                ),
                template="plotly_dark",
                paper_bgcolor="#161b22",
                plot_bgcolor="#161b22",
            )
            st.plotly_chart(fig_pareto, use_container_width=True)

        with g2:
            # Gráfico de Distribuição de Planos
            df_pizza = pd.DataFrame(
                {
                    "Categoria": ["Assinantes", "Com Créditos", "Sem Assinatura"],
                    "Total": [total_assinantes, total_credito, total_gratis],
                }
            )

            cores_pizza = ["#28a745", "#007bff", "#6e7681"]

            fig_pizza = px.pie(
                df_pizza,
                values="Total",
                names="Categoria",
                title="Distribuição de Tipos de Usuários",
                color_discrete_sequence=cores_pizza,
            )

            fig_pizza.update_layout(
                template="plotly_dark",
                paper_bgcolor="#161b22",
            )
            st.plotly_chart(fig_pizza, use_container_width=True)

        st.markdown("---")

        # --------------------------------------------------------------------------
        # MÓDULO 4: MONITORAMENTO DE SALAS EM TEMPO REAL
        # --------------------------------------------------------------------------
        st.subheader("🎥 Monitoramento de Salas Privadas em Tempo Real")
        # Procura essa estrutura por volta da linha 2165 do seu arquivo:
        if salas_ativas:
            st.write("### 🟢 Salas Privadas Ativas")
            for sala in salas_ativas:
                with st.container():
                    st.markdown(f"""
                    <div style="background-color: #161b22; padding: 15px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 10px;">
                        <span style="color: #28a745; font-weight: bold;">● EM USO</span> | 
                        <strong>{sala['sala']}</strong> | 
                        Usuário Ativo: <code>{sala['usuario']}</code> | 
                        Tempo de Duração: <span style="color: #ffc107;">{sala['tempo_uso']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            st.dataframe(salas_ativas) 

        else:
            # Mensagem adicionada para quando não houver encontros ativos
            st.info("ℹ️ Nenhuma sala privada ativa ou agendamento ocorrendo no momento.")    

        st.markdown("---")

        # --------------------------------------------------------------------------
        # MÓDULO 5: VISUALIZAÇÃO DOS CARDÁPIOS DE PLANOS
        # --------------------------------------------------------------------------
        st.subheader("📋 Visualização de Termos e Regras dos Planos")
        
        st.html("""
        <div style="background-color: #161b22; padding: 20px; border-radius: 8px; border: 1px solid #30363d;">
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

        # Exibição do DataFrame de moderação com largura completa
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
                    # Função Excluir Usuário acoplada com deleção em cascata total no Postgres
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


# ==============================================================================
# 10. ORQUESTRADOR E MAQUINA DE ESTADOS CENTRAL (NOTIFICAÇÃO SEGUIDA DE TRAVA)
# ==============================================================================
if st.session_state.alerta_match:
    dados_m = st.session_state.alerta_match
    st.session_state.alerta_match = None
    modal_match_lucy(dados_m)

if st.session_state.abrir_reserva_fluxo:
    dados_r = st.session_state.abrir_reserva_fluxo
    st.session_state.abrir_reserva_fluxo = None
    modal_agendamento_encontro(dados_r)


    
    # ==============================================================================
# 2. ROTEAMENTO ESTRITO DE TELAS (Substitua o seu bloco antigo por este)
# ==============================================================================

# Captura o valor atual para o roteamento baseado em strings seguras
menu_atual = str(st.session_state.opcao_menu).strip().lower()

# --- 1. TELAS PÚBLICAS ---
if menu_atual == "home":
    template_home()

elif menu_atual == "login" or menu_atual == "login":
    st.session_state.usuario_id = None
    template_login()

elif menu_atual == "cadastro" or menu_atual == "📝 cadastro":
    st.session_state.usuario_id = None
    template_cadastro()

# --- 2. TELAS PRIVADAS (Usuário Logado) ---
else:
    # Trava de Segurança: Se não estiver logado e a tela não for pública, força 'home'
    if st.session_state.usuario_id is None:
        st.session_state.opcao_menu = "home"
        st.rerun()

    # Se estiver logado, processa as telas internas normalmente
    if st.session_state.opcao_menu == "Plataforma de Planos IA":
        template_planos()
        
    # [Mantenha aqui o seu bloco existente de buscar e exibir notificações]
    # ... (Seu código de busca no banco com cursor_notif) ...

    # --- RENDERIZAÇÃO DOS MENUS INTERNOS ---
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
