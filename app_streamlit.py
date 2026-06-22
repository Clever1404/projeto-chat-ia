import streamlit as st
import pandas as pd
import os
import psycopg
from datetime import datetime, timezone
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

# ==============================================================================
# 1. CONFIGURAÇÕES OBRIGATÓRIAS DE PÁGINA (Sempre no Topo Absoluto)
# ==============================================================================
if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"

st.set_page_config(
    page_title="Lucy Chat IA - Plataforma", 
    layout="wide", 
    initial_sidebar_state=st.session_state.sidebar_state
)

# Estilização Padrão Global (Sem rolagem dupla)
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
# 3. CONEXÕES DE APIs E BANCO DE DADOS
# ==============================================================================
UPLOAD_FOLDER = 'static/uploads/perfis'
load_dotenv()

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
if not OPENAI_API_KEY or "sua_chave" in OPENAI_API_KEY:
    st.error("ERRO: Chave API da OpenAI não configurada nos Secrets!")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

url: str = st.secrets.get("SUPABASE_URL")
key: str = st.secrets.get("SUPABASE_KEY")
supabase = None

if url and key:
    try:
        supabase = create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase Client: {e}")
else:
    st.warning("⚠️ Atenção: As credenciais do Supabase não estão configuradas nos Secrets.")

try:
    sdk = mercadopago.SDK(st.secrets["TOKEN_MERCADO_PAGO"])
except Exception as e:
    st.error(f"Erro ao carregar credenciais do Mercado Pago: {e}")
    sdk = None

def conectar_supabase():
    conn = psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        port=st.secrets["postgres"]["port"],
        sslmode="require" 
    )
    return conn

# ==============================================================================
# 4. FUNÇÕES DE SUPORTE E MECANISMO DE INTELIGÊNCIA ARTIFICIAL (4 PILARES)
# ==============================================================================
def buscar_memoria(usuario_id, limite=15):
    try:
        conn = conectar_supabase(); cursor = conn.cursor()
        cursor.execute('SELECT usuario_pergunta, ia_resposta FROM historico_ia WHERE usuario_id = %s ORDER BY id ASC LIMIT %s;', (int(usuario_id), limite))
        hist = cursor.fetchall(); cursor.close(); conn.close()
        return hist
    except Exception: return []

def processar_afinidade_e_match(usuario_id, texto_atual):
    try:
        meu_id_limpo = usuario_id if not isinstance(usuario_id, (tuple, list)) else int(usuario_id[0] if isinstance(usuario_id, tuple) else usuario_id)
        conn = conectar_supabase(); cursor = conn.cursor()
        cursor.execute("SELECT idade, genero, procura_por, procura_relacionamento FROM usuarios WHERE id = %s;", (meu_id_limpo,))
        meu_perfil = cursor.fetchone()
        if not meu_perfil:
            cursor.close(); conn.close()
            return {"match": False}
        minha_idade, meu_genero, o_que_eu_procuro_gen, o_que_eu_procuro_rel = meu_perfil

        mensagens_sintese = [
            {"role": "system", "content": "Escreva apenas um parágrafo corrido contendo as palavras-chaves semânticas de interesses e estilo de vida."},
            {"role": "user", "content": f"Baseado nesta interação recente do usuário, extraia e descreva em terceira pessoa uma lista de seus hobbies e interesses: {texto_atual}"}
        ]
        resposta_sintese = client.chat.completions.create(model='gpt-4o-mini', messages=mensagens_sintese, temperature=0.3)
        perfil_consolidado_texto = resposta_sintese.choices[0].message.content

        resposta_embedding = client.embeddings.create(model="text-embedding-3-small", input=perfil_consolidado_texto, dimensions=768)
        vetor_atual = resposta_embedding.data[0].embedding
        vetor_formatado_postgres = str(vetor_atual)

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
        
        if resultado:
            id_par, nome_par, status_par, distancia = resultado
            distancia_val = float(distancia)
            if distancia_val <= 0.22:
                similaridade_bruta = 1.0 - distancia_val
                porcentagem_match = max(0.0, min(100.0, (similaridade_bruta - 0.75) / (0.88 - 0.75) * 100))
                conn.commit(); cursor.close(); conn.close()
                return {"match": True, "id_par": int(id_par), "nome_par": nome_par, "online": "🟢" in str(status_par) or "Online" in str(status_par), "afinidade_porcentagem": round(porcentagem_match, 1)}
        conn.commit(); cursor.close(); conn.close()
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback(); cursor.close(); conn.close()
    return {"match": False}

# ==============================================================================
# FUNÇÕES DE GERENCIAMENTO DE MENSAGENS E HISTÓRICO DA SALA PRIVADA
# ==============================================================================
def enviar_mensagem(match_id, remetente_id, texto):
    if not texto or str(texto).strip() == "": 
        return
    try:
        id_match_int = match_id[0] if isinstance(match_id, (tuple, list)) else int(match_id)
        id_remetente_int = remetente_id[0] if isinstance(remetente_id, (tuple, list)) else int(remetente_id)
        
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

def buscar_mensagens(match_id):
    try:
        id_match_int = match_id[0] if isinstance(match_id, (tuple, list)) else int(match_id)
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
        id_match_int = match_id[0] if isinstance(match_id, (tuple, list)) else int(match_id)
        conn = conectar_supabase()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mensagens_sala WHERE match_id = %s;", (id_match_int,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e: 
        st.error(f"Erro ao limpar histórico: {e}")
        return False

# ==============================================================================
# 5. RENDERIZADORES DE DIALOGS/MODAIS (RECALIBRADOS)
# ==============================================================================
@st.dialog("🤖 Lucy Notou Afinidade!")
def exibir_modal_match(dados_m, tipo_plano, saldo_moedas):
    st.markdown(f"Lucy identificou uma excelente afinidade entre você e {dados_m['nome']}!")
    id_usuario = st.session_state.usuario_id
    
    if dados_m["online"]:
        st.markdown(f"🟢 {dados_m['nome']} está online agora!")
        if tipo_plano == "vip":
            if st.button("🚀 Entrar na Sala Privada (Acesso Total Ilimitado)", type="primary", use_container_width=True):
                st.session_state.match_id_atual = dados_m["match_id"]
                st.session_state.tempo_limite_sala = -1
                st.session_state.opcao_menu = "🤝 Sala Privada"
                st.rerun()
        elif tipo_plano == "Plano Crédito de Moedas":
            st.info(f"🪙 Seu Saldo: {saldo_moedas} moedas. Custo da Sala Privada: 10 moedas = 10 minutos.")
            if st.button("🪙 Entrar na Sala Privada (Gasta 10 moedas)", type="primary", use_container_width=True):
                if saldo_moedas >= 10:
                    try:
                        id_limpo = id_usuario[0] if isinstance(id_usuario, (list, tuple)) else id_usuario
                        supabase.table("usuarios").update({"moedas": saldo_moedas - 10}).eq("id", int(id_limpo)).execute()
                        st.success("Moedas debitadas! Sala privada liberada por 10 minutos iniciais.")
                        st.session_state.match_id_atual = dados_m["match_id"]
                        st.session_state.tempo_limite_sala = 10
                        st.session_state.opcao_menu = "🤝 Sala Privada"
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Falha na transação: {e}")
                else: 
                    st.warning("🔒 Saldo insuficiente. Você precisa de pelo menos 10 moedas.")
        else: 
            st.error("🔒 O acesso a salas privadas é exclusivo para clientes com plano de Crédito ou Assinantes.")
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
                st.warning("🔒 O agendamento de encontros virtuais não está disponível no Plano Grátis. Faça um upgrade!")
                
    if st.button("❌ Não tenho interesse", type="secondary", use_container_width=True): 
        st.rerun()

def processar_match_lucy(dados_m):
    tipo_plano, saldo_moedas = "Grátis", 0
    id_usuario_logado = st.session_state.get("usuario_id")
    if id_usuario_logado is None: 
        return
    try:
        id_limpo = id_usuario_logado if isinstance(id_usuario_logado, (list, tuple)) else id_usuario_logado
        user_data = supabase.table("usuarios").select("tipo_plano", "moedas").eq("id", int(id_limpo)).execute()
        if user_data.data:
            registro_banco = user_data.data[0]
            tipo_plano = str(registro_banco.get("tipo_plano", "Grátis")).strip()
            saldo_moedas = registro_banco.get("moedas", 0)
    except Exception as e: 
        st.error(f"Erro ao carregar dados do banco: {e}")
        return  # 🟢 FIX: O bloco 'except' agora possui conteúdo e encerra a função com segurança
        
    exibir_modal_match(dados_m, tipo_plano, saldo_moedas)

@st.dialog("📅 Reserva de Encontro")
def modal_agendamento_encontro(dados_r):
    st.markdown(f"### 📆 Agendar Reunião com {dados_r['nome_par']}")
    dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
    dia_s = st.selectbox("Escolha o Dia da Semana:", dias, key="dg_res_dia")
    opcoes_periodo = ["🌅 Manhã (06:00 às 11:59)", "☀️ Tarde (12:00 às 17:59)", "🌙 Noite (18:00 às 23:59)"]
    per_exibicao = st.selectbox("Escolha o Período:", opcoes_periodo, key="dg_res_per")
    per_s = "manha" if "Manhã" in per_exibicao else "tarde" if "Tarde" in per_exibicao else "noite"
    
    horario_sugestao = datetime.strptime("09:00" if per_s=="manha" else "14:00" if per_s=="tarde" else "20:00", "%H:%M").time()
    hor_s = st.time_input("Ajuste o Horário Exato:", value=horario_sugestao, step=900, key="dg_res_hor")
    
    if st.button("💾 Confirmar Reserva e Enviar", type="primary", use_container_width=True):
        def limpar_id_absoluto(id_bruto):
            while isinstance(id_bruto, (tuple, list)): 
                id_bruto = id_bruto[0] if len(id_bruto)>0 else 0
            return int(id_bruto)
            
        m_id_limpo = limpar_id_absoluto(dados_r.get('m_id'))
        meu_id_limpo = limpar_id_absoluto(st.session_state.usuario_id)
        parceiro_id_limpo = limpar_id_absoluto(dados_r.get('id_par'))
        
        try:
            conn_check = conectar_supabase()
            cursor_check = conn_check.cursor()
            
            # Correção sintática: Trocado COUNT() por COUNT(*) nas queries SQL
            cursor_check.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (meu_id_limpo, str(dia_s), str(per_s)))
            meu_registro_existe = cursor_check.fetchone()[0] > 0
            
            cursor_check.execute("SELECT COUNT(*) FROM disponibilidade_usuarios WHERE usuario_id = %s;", (parceiro_id_limpo,))
            parceiro_tem_algum_horario = cursor_check.fetchone()[0] > 0
            
            cursor_check.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (parceiro_id_limpo, str(dia_s), str(per_s)))
            parceiro_registro_existe = cursor_check.fetchone()[0] > 0
            
            cursor_check.close()
            conn_check.close()
            
            hora_int = hor_s.hour
            if per_s == 'manha' and (hora_int < 6 or hora_int >= 12): 
                st.error("❌ Horário inválido para Manhã (06:00 às 11:59).")
            elif per_s == 'tarde' and (hora_int < 12 or hora_int >= 18): 
                st.error("❌ Horário inválido para Tarde (12:00 às 17:59).")
            elif per_s == 'noite' and (hora_int < 18 or hora_int > 23): 
                st.error("❌ Horário inválido para Noite (18:00 às 23:59).")
            elif not meu_registro_existe: 
                st.error("❌ Você marcou este horário como indisponível na sua própria grade.")
            elif parceiro_tem_algum_horario and not parceiro_registro_existe: 
                st.error(f"❌ {dados_r['nome_par']} configurou este horário como indisponível.")
            else:
                conn = conectar_supabase()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agendamentos_virtuais (match_id, remetente_id, destinatario_id, dia_semana, periodo, horario, status_convite) 
                    VALUES (%s, %s, %s, %s, %s, %s, 'pendente');
                """, (m_id_limpo, meu_id_limpo, parceiro_id_limpo, dia_s, per_s, hor_s))
                conn.commit()
                cursor.close()
                conn.close()
                
                st.success("🎉 Convite enviado!")
                st.session_state.abrir_reserva_fluxo = None
                st.rerun()
        except Exception as e: 

# ==============================================================================
# MODAL DA LOJA DO APP (LINHA 391)
# ==============================================================================
@st.dialog("🛒 Loja do App")
def mostrar_popup_loja(id_usuario):
    opcoes_compra = st.radio("Escolha uma opção:", ["Assinatura VIP (R$ 19,90)", "10 Moedas (R$ 5,00)"])
    
    if st.button("Gerar Pix de Pagamento"):
        valor, desc, tipo = (19.90, "Plano VIP 30 dias", "vip") if "VIP" in opcoes_compra else (5.00, "Pacote de 10 Moedas", "moedas")
        id_limpo = id_usuario[0] if isinstance(id_usuario, (list, tuple)) else id_usuario
        
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
                st.rerun()
        except Exception as e: 
            st.error(f"Erro ao gerar pagamento: {e}")
            
    if st.session_state.id_pagamento_pendente:
        st.markdown("---")
        st.image(f"data:image/jpeg;base64,{st.session_state.qr_code_img}", width=200)
        st.text_input("Copia e Cola:", value=st.session_state.qr_code_texto)
        
        if st.button("🔄 Já paguei, liberar meu acesso"):
            try:
                check_payment = sdk.payment().get(st.session_state.id_pagamento_pendente)["response"]
                
                if check_payment.get("status") == "approved":
                    id_limpo = id_usuario[0] if isinstance(id_usuario, (list, tuple)) else id_usuario
                    
                    if st.session_state.tipo_pagamento_pendente == "vip":
                        supabase.table("usuarios").update({"tipo_plano": "vip"}).eq("id", int(id_limpo)).execute()
                    else:
                        saldo_atual = st.session_state.get("saldo_moedas", 0)
                        supabase.table("usuarios").update({"moedas": saldo_atual + 10}).eq("id", int(id_limpo)).execute()
                        
                    st.session_state.id_pagamento_pendente = None
                    st.session_state.abrir_popup_loja = False
                    st.success("🎉 Creditado com sucesso!")
                    st.rerun()
                else: 
                    st.warning("⚠️ Pagamento ainda não aprovado.")
            except Exception as e: 
                st.error(f"Erro: {e}")

@st.fragment(run_every=5.0)
def renderizar_temporizador_creditos(saldo_moedas_sala, id_usuario_logado, id_match_int):
    if "tempo_inicio_sala" not in st.session_state: 
        st.session_state.tempo_inicio_sala = time.time()
        
    tempo_decorrido = time.time() - st.session_state.tempo_inicio_sala
    tempo_restante = 600 - tempo_decorrido
    
    if tempo_restante > 0:
        st.warning(f"⏳ Tempo Restante: {int(tempo_restante // 60)}m {int(tempo_restante % 60)}s | Saldo: 🪙 {saldo_moedas_sala} moedas")
    else:
        if saldo_moedas_sala >= 10:
            try:
                novo_saldo = saldo_moedas_sala - 10
                id_limpo = id_usuario_logado[0] if isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
                
                supabase.table("usuarios").update({"moedas": novo_saldo}).eq("id", int(id_limpo)).execute()
                
                if "dados_usuario" in st.session_state: 
                    st.session_state.dados_usuario["moedas"] = novo_saldo
                    
                st.session_state.tempo_inicio_sala = time.time()
                st.toast("🪙 Mais 10 minutos adicionados!", icon="🪙")
                st.rerun()
            except Exception as e: 
                st.error(f"Erro: {e}")
        else:
            st.error("🔒 Tempo esgotado e sem saldo.")
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()

# ==============================================================================
# 6. TEMPLATES / TELAS DO SISTEMA
# ==============================================================================
def template_home():
    st.markdown("Lucy Chat IA — Chat virtual online", unsafe_allow_html=True)
    st.markdown("Conversa com afinidades baseadas em IA e encontros virtuais criptografados de ponta a ponta.", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Fazer Login", use_container_width=True, type="primary"):
            st.session_state.opcao_menu = "login"
            st.rerun()
            
    with col2:
        with stylable_container(
            key="green_button", 
            css_styles="button { background-color: #28a745; color: white; }"
        ):
            if st.button("📝 Cadastre-se", use_container_width=True):
                st.session_state.opcao_menu = "cadastro"
                st.rerun()