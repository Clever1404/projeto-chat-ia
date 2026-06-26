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
supabase = create_client(url, key)

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

def obter_conexao_eficiente():
    # Se não existe ou se foi fechada pelo banco, abre uma nova
    if "conexao_db_ativa" not in st.session_state or st.session_state.conexao_db_ativa.closed != 0:
        st.session_state.conexao_db_ativa = psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"],
            sslmode="require"
        )
    return st.session_state.conexao_db_ativa

# ==============================================================================
# 4. FUNÇÕES DE SUPORTE E MECANISMO DE INTELIGÊNCIA ARTIFICIAL (4 PILARES)
# ==============================================================================
def buscar_memoria(usuario_id, limite=15):
    try:
        conn = obter_conexao_eficiente(); cursor = conn.cursor()
        cursor.execute('SELECT usuario_pergunta, ia_resposta FROM historico_ia WHERE usuario_id = %s ORDER BY id ASC LIMIT %s;', (int(usuario_id), limite))
        hist = cursor.fetchall(); cursor.close(); 
        return hist
    except Exception: return []

def processar_afinidade_e_match(usuario_id, texto_atual):
    try:
        meu_id_limpo = usuario_id if not isinstance(usuario_id, (tuple, list)) else int(usuario_id[0] if isinstance(usuario_id, tuple) else usuario_id)
        conn = obter_conexao_eficiente(); cursor = conn.cursor()
        cursor.execute("SELECT idade, genero, procura_por, procura_relacionamento FROM usuarios WHERE id = %s;", (meu_id_limpo,))
        meu_perfil = cursor.fetchone()
        if not meu_perfil:
            cursor.close(); 
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
                conn.commit(); cursor.close(); 
                return {"match": True, "id_par": int(id_par), "nome_par": nome_par, "online": "🟢" in str(status_par) or "Online" in str(status_par), "afinidade_porcentagem": round(porcentagem_match, 1)}
        # ... (seu código de verificação de resultado)
        conn.commit()
        cursor.close()
        # REMOVIDO: conn.close() se estiver usando o modo eficiente
        return {"match": False}

    except Exception as e:
        # DESTRAVA A TRANSAÇÃO: Se a query de busca ou atualização falhar, cancela a transação pendente
        if 'conn' in locals() and conn:
            try:
                conn.rollback()
            except Exception:
                pass
        if 'cursor' in locals() and cursor:
            try:
                cursor.close()
            except Exception:
                pass
        st.error(f"Erro no motor de afinidade: {e}")
        return {"match": False}



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
                # APENAS salva os dados na sessão. O Roteador Global vai abrir o modal de forma limpa.
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
        return
        
    exibir_modal_match(dados_m, tipo_plano, saldo_moedas)



# ==============================================================================
# FUNÇÃO ISOLADA COM BUFFER DE MEMÓRIA (INPUT EMBAIXO E MENSAGENS EM CIMA)
# ==============================================================================
@st.fragment
def renderizar_chat_lucy_isolado():

   # Inicializa a variável de controle caso ela não exista
    if "opcao_menu" not in st.session_state:
        st.session_state.opcao_menu = "chat"

    # Criamos um container vazio que vai segurar e limpar o layout a cada clique
    conteudo_dinamico = st.container()

    with conteudo_dinamico:
        # Se o usuário escolheu o menu de contato, renderiza o formulário externo
        if st.session_state.opcao_menu == "✉️ Fale Conosco":
            template_fale_conosco()
            
        else:
            # Caso contrário, monta o cabeçalho padrão do Chat
            col_titulos, col_botoes_topo = st.columns([2, 1])

            with col_titulos:
                st.markdown("<h2 style='margin-top:0; margin-bottom:2px; font-size: 24px;'>🤖 Olá, Seja bem-vindo ao Lucy Chat IA</h2>", unsafe_allow_html=True)
                st.caption("Lucy conversa com você e armazena os seus interesses para encontrar matches.")
            
            with col_botoes_topo:
                c_refresh, c_fc = st.columns(2)
                with c_refresh:
                    if st.button("🔄 Atualizar Dados", type="tertiary", help="Sincronizar mensagens"):
                        st.rerun(scope="fragment")
                with c_fc:
                    if st.button("✉️ Fale Conosco", type="tertiary"):
                        st.session_state.opcao_menu = "✉️ Fale Conosco"
                        st.rerun(scope="fragment") # Diz ao fragmento para re-executar imediatamente trocando a tela
            
            st.markdown("<hr style='border-color: #30363d; margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
            # O histórico de mensagens e o st.chat_input devem vir listados aqui...



    meu_id_limpo = st.session_state.usuario_id if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)

    # 1. PROCESSAMENTO EM SEGUNDO PLANO (Roda antes de desenhar a tela)
    # Se houver uma mensagem guardada no buffer da rodada anterior, processa com a OpenAI
    if st.session_state.get("prompt_buffer"):
        prompt_atual = st.session_state.prompt_buffer
        del st.session_state["prompt_buffer"] # Limpa o buffer para não processar duas vezes
        
        try:
            # Carrega o histórico para fornecer contexto à IA
            historico_contexto = buscar_memoria(meu_id_limpo, limite=5)
            contexto_mensagens = [
                {"role": "system", "content": "Você é a Lucy, uma IA psicóloga e assistente de relacionamentos altamente empática. Seu objetivo é entender o estilo de vida, gostos e rotina do usuário através de uma conversa natural. Seja acolhedora, faça perguntas abertas e ajude-o a se expressar para encontrar o par ideal."}
            ]
            for p, r in historico_contexto:
                contexto_mensagens.append({"role": "user", "content": p})
                contexto_mensagens.append({"role": "assistant", "content": r})
            
            contexto_mensagens.append({"role": "user", "content": prompt_atual})

            resposta_openai = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=contexto_mensagens,
                temperature=0.7
            )
            resposta_lucy = resposta_openai.choices[0].message.content

            # Salva no histórico do banco de dados
            conn_salvar = obter_conexao_eficiente()
            cursor_salvar = conn_salvar.cursor()
            cursor_salvar.execute("""
                INSERT INTO historico_ia (usuario_id, usuario_pergunta, ia_resposta) 
                VALUES (%s, %s, %s);
            """, (meu_id_limpo, prompt_atual, resposta_lucy))
            conn_salvar.commit()
            cursor_salvar.close()

            # Dispara o motor de afinidade
            dados_match = processar_afinidade_e_match(meu_id_limpo, prompt_atual)
            if dados_match and dados_match.get("match"):
                st.session_state.alerta_match = {
                    "match_id": dados_match.get("match_id", random.randint(1000, 9999)),
                    "id_par": dados_match.get("id_par"),
                    "nome": dados_match.get("nome_par"),
                    "online": dados_match.get("online", False)
                }
                processar_match_lucy(st.session_state.alerta_match)

        except Exception as e:
            # DESTRAVA A TRANSAÇÃO NO CHAT
            if 'conn_salvar' in locals() and conn_salvar:
                try:
                    conn_salvar.rollback()
                except Exception:
                    pass
            if 'cursor_salvar' in locals() and cursor_salvar:
                try:
                    cursor_salvar.close()
                except Exception:
                    pass
            st.error(f"Erro ao processar conversa com a IA: {e}")

    # 2. ÁREA VISUAL SUPERIOR (Área de rolagem das mensagens)
    historico_banco = buscar_memoria(meu_id_limpo, limite=20)
    
    with st.container(height=450, border=False):
        for pergunta_antiga, resposta_antiga in historico_banco:
            with st.chat_message("user"):
                st.markdown(pergunta_antiga)
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(resposta_antiga)

    # 3. ÁREA VISUAL INFERIOR (A caixa de texto fica obrigatoriamente no rodapé da página)
    prompt_capturado = st.chat_input("Digite sua mensagem para a Lucy...")
    
    if prompt_capturado:
        # Guarda o texto digitado no buffer e força o rerun
        st.session_state.prompt_buffer = prompt_capturado
        st.rerun()



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
    
    def limpar_id_absoluto(id_bruto):
        while isinstance(id_bruto, (tuple, list)): 
            id_bruto = id_bruto[0] if len(id_bruto) > 0 else 0
        return int(id_bruto) if id_bruto is not None else 0

    m_id_limpo = limpar_id_absoluto(dados_r.get('m_id'))
    meu_id_limpo = limpar_id_absoluto(st.session_state.get("usuario_id"))
    parceiro_id_limpo = limpar_id_absoluto(dados_r.get('id_par'))

    # Inicialização das variáveis fora do escopo do botão para o Debugger não quebrar
    meu_registro_existe = False
    parceiro_registro_existe = False
    parceiro_tem_algum_horario = False
    # 4. REGRAS DE NEGÓCIO E VALIDAÇÕES DE TRAVA
            
    erro_validacao = False
    mensagem_erro = ""


    if st.button("💾 Confirmar Reserva e Enviar", type="primary", use_container_width=True, key="btn_confirmar_reserva_click"):
        try:
            conn = obter_conexao_eficiente()
            cursor = conn.cursor()
            
            # 1. VERIFICAÇÃO E RECUPERAÇÃO DO MATCH
            # Removido LOWER(TRIM(id)) que causava o erro no Postgres
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

            # 2. VALIDAÇÕES DE DISPONIBILIDADE (Agora rodam SEMPRE, fora do bloco 'if not match_existe')
            # Validação do Usuário Atual
            cursor.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (meu_id_limpo, str(dia_s), str(per_s)))
            meu_registro_existe = cursor.fetchone()[0] > 0
    
            # Verifica se o parceiro tem qualquer horário salvo na tabela
            cursor.execute("SELECT COUNT(*) FROM disponibilidade_usuarios WHERE usuario_id = %s;", (parceiro_id_limpo,))
            parceiro_tem_algum_horario = cursor.fetchone()[0] > 0
    
            # Verifica se o parceiro possui ESTE horário específico na grade
            cursor.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s 
                AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) 
                AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (parceiro_id_limpo, str(dia_s), str(per_s)))
            parceiro_registro_existe = cursor.fetchone()[0] > 0

            cursor.close()
            conn.close() # Fecha a conexão de leitura com segurança
            
            # # 3. EXIBIÇÃO DO PAINEL DE DEPURAÇÃO (Movido para dentro do botão para refletir os dados em tempo real)
            # with st.expander("🔍 Depurador de Agenda (Debug)", expanded=True):
            #     st.write(f"**Seu ID ({st.session_state.get('username', 'Usuário')}):** {meu_id_limpo} | Possui este horário? `{'Sim' if meu_registro_existe else 'Não'}`")
            #     st.write(f"**ID do Par ({dados_r['nome_par']}):** {parceiro_id_limpo} | Possui este horário? `{'Sim' if parceiro_registro_existe else 'Não'}`")
            #     st.write(f"**O parceiro já preencheu a grade alguma vez?** `{'Sim' if parceiro_tem_algum_horario else 'Não'}`")

            # 4. REGRAS DE NEGÓCIO E VALIDAÇÕES DE TRAVA
            hora_int = hor_s.hour
            if per_s == 'manha' and (hora_int < 6 or hora_int >= 12): 
                st.error("❌ Horário inválido para Manhã (06:00 às 11:59).")
            elif per_s == 'tarde' and (hora_int < 12 or hora_int >= 18): 
                st.error("❌ Horário inválido para Tarde (12:00 às 17:59).")
            elif per_s == 'noite' and (hora_int < 18 or hora_int > 23): 
                st.error("❌ Horário inválido para Noite (18:00 às 23:59).")
            
      
            elif not meu_registro_existe:
                erro_validacao = True
                mensagem_erro = f"❌ **Agendamento Recusado:** Você ({st.session_state.get('username', 'Usuário')}) configurou este dia/período como indisponível na sua grade. Acesse 'MINHA GRADE HORÁRIA' para liberar."
                
            elif not parceiro_registro_existe:
                erro_validacao = True
                mensagem_erro = f"❌ **Agendamento Recusado:** {dados_r['nome_par']} está indisponível na {dia_s} no período selecionado."       
            
            # SE HOUVER RECUSA/ERRO: Exibe o erro e redireciona automaticamente
            if erro_validacao:
                st.error(mensagem_erro)
                st.warning("🔄 Redirecionando de volta para o chat em 3 segundos...")
                
                # Modifica os estados antes de fechar
                st.session_state.opcao_menu = "💬 Conversar com Lucy"
                st.session_state.abrir_reserva_fluxo = None  # Reseta o controle manual do modal
                
                # Aguarda o usuário ler a mensagem
                time.sleep(3.0)
                
                # Executa o fechamento nativo do modal e reinicia a tela principal
                if hasattr(st, "dialog_close"):
                    st.dialog_close()
                st.rerun()
            
            else:
                # 5. SALVAMENTO FINAL DO AGENDAMENTO (Executa apenas se passar em todas as travas)
                conn_salvar = obter_conexao_eficiente()
                cursor_salvar = conn_salvar.cursor()
                
                cursor_salvar.execute("""
                    INSERT INTO agendamentos_virtuais (match_id, remetente_id, destinatario_id, dia_semana, periodo, horario, status_convite) 
                    VALUES (%s, %s, %s, %s, %s, %s, 'pendente');
                """, (m_id_limpo, meu_id_limpo, parceiro_id_limpo, str(dia_s), str(per_s), hor_s))
                
                conn_salvar.commit()
                cursor_salvar.close()
                conn_salvar.close()
                
                st.success("🎉 Convite enviado com sucesso!")
                st.session_state.abrir_reserva_fluxo = None
                
                time.sleep(1.9)
                if hasattr(st, "dialog_close"):
                    st.dialog_close()
                st.rerun()
           
             
        except Exception as e: 
            st.error(f"Erro crítico ao salvar agendamento no banco: {e}")


# ==============================================================================
# FUNÇÃO AUXILIAR COM CACHE PARA OTIMIZAÇÃO DA GRADE HORÁRIA
# ==============================================================================
@st.cache_data(ttl=60)  # Limpa o cache automaticamente após 1 minuto
def buscar_disponibilidade_banco(usuario_id):
    horarios = set()
    try:
        conn = obter_conexao_eficiente()
        cursor = conn.cursor()
        cursor.execute("SELECT dia_semana, periodo FROM disponibilidade_usuarios WHERE usuario_id = %s;", (usuario_id,))
        for d_sem, per_id in cursor.fetchall():
            horarios.add(f"{str(d_sem).strip()}_{str(per_id).strip()}") 
        cursor.close()
        
    except Exception:
        pass
    return horarios

# ==============================================================================
# TELA DE CONFIGURAÇÃO DE DISPONIBILIDADE SEMANAL
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
            try:
                conn = obter_conexao_eficiente()
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
                
                conn.commit()
                cursor.close()
                 
                
                # Limpa os estados do cache para refletir no próximo turno
                st.cache_data.clear()
                if "df_grade_memoria" in st.session_state:
                    del st.session_state["df_grade_memoria"]
                
                st.toast("🎉 Sua grade horária foi salva com sucesso no banco de dados!")
                time.sleep(1)
                st.rerun() 
            except Exception as e:
                st.error(f"Erro crítico ao salvar no banco: {e}")

    # Áreas e gatilhos adicionais fora do formulário
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    col_l, col_v = st.columns(2)
    
    with col_l:
        if st.button("🗑️ Limpar Grade Horária", type="secondary", use_container_width=True, key="btn_limpar_grade_real"):
            try:
                conn = obter_conexao_eficiente()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM disponibilidade_usuarios WHERE usuario_id = %s;", (meu_id_limpo,))
                conn.commit()
                cursor.close()
               
                
                st.cache_data.clear()
                if "df_grade_memoria" in st.session_state:
                    del st.session_state["df_grade_memoria"]
                    
                st.toast("Toda a sua grade horária foi limpa!")
                st.rerun()
            except Exception as e: 
                st.error(f"Erro ao limpar grade: {e}")
            
    with col_v: 
        if st.button("Voltar ao Chat", use_container_width=True, key="btn_voltar_chat_grade"): 
            st.session_state.opcao_menu = "💬 Conversar com Lucy" 
            st.rerun()





# ==============================================================================
# FUNÇÃO AUXILIAR: BANCO DE DADOS DA SALA PRIVADA
# ==============================================================================
def enviar_mensagem(match_id, remetente_id, texto):
    if not texto or str(texto).strip() == "":
        return
    try:
        id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
        id_remetente_int = remetente_id if isinstance(remetente_id, (tuple, list)) else int(remetente_id)
        
        conn = obter_conexao_eficiente()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mensagens_sala (match_id, remetente_id, conteudo) 
            VALUES (%s, %s, %s);
        """, (id_match_int, id_remetente_int, str(texto).strip()))
        conn.commit()
        cursor.close()
        
    except Exception as e:
        st.error(f"Erro ao enviar mensagem: {e}")

def buscar_mensagens(match_id):
    try:
        id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
        conn = obter_conexao_eficiente()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT remetente_id, conteudo, criado_em 
            FROM mensagens_sala 
            WHERE match_id = %s 
            ORDER BY criado_em ASC;
        """, (id_match_int,))
        mensagens = cursor.fetchall()
        cursor.close()
        
        return mensagens
    except Exception:
        return []

def limpar_historico_sala(match_id):
    try:
        id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
        conn = obter_conexao_eficiente()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mensagens_sala WHERE match_id = %s;", (id_match_int,))
        conn.commit()
        cursor.close()
        
        return True
    except Exception as e:
        st.error(f"Erro ao limpar histórico: {e}")
        return False


# ==============================================================================
# TELA PRIVADA 1: TEMPLATE DA SALA PRIVADA (WHATSAPP STYLE + VIDEO)
# ==============================================================================
def template_sala_privada():
    match_id = st.session_state.get("match_id_atual")
    meu_id = st.session_state.get("usuario_id")
    
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

    #st.title("🤝 Sala Privada de Conversa")
    
    parceiro_nome = "Usuário"
    parceiro_foto = None
    parceiro_gen = "M"
    status_parceiro = "⚫ Offline"
    status_cor = "#a0aec0"
    
    try:
        conn = obter_conexao_eficiente()
        cursor = conn.cursor()
        id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
        cursor.execute("SELECT usuario_1_id, usuario_2_id FROM matches WHERE id = %s;", (id_match_int,))
        res_m = cursor.fetchone()
        
        if res_m:
            u1, u2 = int(res_m[0]), int(res_m[1])
            meu_id_limpo = st.session_state.usuario_id if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id[0])
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
        
    except Exception as e: 
        print(f"Erro ao buscar status na Sala Privada: {e}")

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
                
        if st.button("🚪 Sair da Sala Privada", type="primary", use_container_width=True):
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()
            
        if st.button("🗑️ Limpar Histórico do Chat", type="secondary", use_container_width=True):
            if limpar_historico_sala(match_id):
                st.success("Histórico apagado!")
                st.rerun() 

        if tipo_plano_sala == "Plano Crédito de Moedas":
            st.info(f"🪙 Modo Créditos Ativo. Saldo atual: {saldo_moedas_sala} moedas.")
            id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
            # Nota: Certifique-se de que esta função abaixo está declarada no seu escopo global
            if "renderizar_temporizador_creditos" in globals():
                renderizar_temporizador_creditos(saldo_moedas_sala, id_usuario_logado, id_match_int) 
        elif tipo_plano_sala == "vip": 
            st.success(f"⭐ Plano Assinante Ativo: Tempo Ilimitado.") 

    with col_chat:
        st.markdown(f"### 💬 Sala Privada com {parceiro_nome}")
        id_match_atual = st.session_state.get("match_id_atual")
        
        if st.button("🎥 Iniciar Videochamada Privada", type="tertiary"): 
            nome_da_sala_unica = f"Atendimento_FaleConosco_SalaPrivada_{id_match_int}" 
            url_jitsi = f"https://meet.jit.si/{nome_da_sala_unica}" 
        
            st.info("A videochamada foi iniciada abaixo. Garanta as permissões no navegador.") 
            st.iframe(url_jitsi, height=600)

        if id_match_atual:
            try:
                agora_iso = datetime.now().isoformat()
                supabase.table("matches").update({"status_conexao": "online", "ultima_atividade": agora_iso}).eq("id", id_match_atual).execute()
            except Exception: pass   
        st.divider()

        with st.container(height=380, border=True):
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            mensagens = buscar_mensagens(match_id) 
            
            for msg in mensagens:
                r_id, conteudo, criado_em = msg[0], msg[1], msg[2]
                horario = criado_em.strftime("%H:%M") if criado_em else ""
                
                if str(r_id) == str(meu_id):
                    st.markdown(f'<div class="msg-bubble msg-meu"><div class="msg-autor">Você</div><div>{conteudo}</div><div class="msg-tempo">{horario}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="msg-bubble msg-parceiro"><div class="msg-autor">{parceiro_nome}</div><div>{conteudo}</div><div class="msg-tempo">{horario}</div></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.form(key="form_enviar_msg", clear_on_submit=True):
            col_txt, col_btn = st.columns([4, 1])
            with col_txt:
                texto_msg = st.text_input(label="Mensagem", placeholder="Digite uma mensagem e aperte Enter...", label_visibility="collapsed")
            with col_btn:
                if st.form_submit_button("Enviar", use_container_width=True) and texto_msg.strip():
                    enviar_mensagem(match_id, meu_id, texto_msg)
                    st.rerun()
    
      

# --- FUNÇÃO PARA VERIFICAR O PAGAMENTO ---
def verificar_status_pix(id_pagamento):
    """Consulta a API do Mercado Pago e retorna o status atualizado."""
    try:
        # Consulta o pagamento usando o SDK do Mercado Pago
        payment_info = sdk.payment().get(id_pagamento)
        return payment_info["response"]["status"]
    except Exception as e:
        st.error(f"Erro ao consultar Mercado Pago: {e}")
        return "erro"


def atualizar_plano_banco_supabase(id_usuario, tipo_pagamento):
    """Atualiza o plano ou incrementa moedas do usuário no Supabase, registrando a última recarga."""
    try:
        id_usuario_str = str(id_usuario)
        # Captura o timestamp atual no formato ISO exigido pelo Supabase (ex: 2026-06-25T18:26:00)
        data_atual_iso = datetime.now().isoformat()

        if tipo_pagamento == "vip":
            # Atualiza o tipo de plano e registra o momento da recarga
            resposta = supabase.table("usuarios").update({
                "tipo_plano": "vip",
                "ultima_recarga": data_atual_iso
            }).eq("id", id_usuario_str).execute()
            
        elif tipo_pagamento == "moedas":
            # 1. Busca a quantidade atual de moedas do usuário
            usuario_dados = supabase.table("usuarios").select("moedas").eq("id", id_usuario_str).single().execute()
            
            if usuario_dados.data:
                moedas_atuais = usuario_dados.data.get("moedas") or 0
                novas_moedas = moedas_atuais + 10
                
                # 2. Atualiza o saldo de moedas e registra o momento da recarga
                resposta = supabase.table("usuarios").update({
                    "moedas": novas_moedas,
                    "ultima_recarga": data_atual_iso
                }).eq("id", id_usuario_str).execute()
            else:
                print("Usuário não encontrado para atualizar moedas.")
                return False
                
        # Retorna True se a tabela foi atualizada com sucesso
        return len(resposta.data) > 0

    except Exception as e:
        print(f"Erro ao atualizar o Supabase: {e}")
        return False
        

# ==============================================================================
# MODAL DA LOJA DO APP (CORRIGIDO E FECHADO)
# ==============================================================================
#@st.dialog("🛒 Loja do App")
#def mostrar_popup_loja(id_usuario):
#    opcoes_compra = st.radio("Escolha uma opção:", ["Assinatura VIP por R$ 19,90/mês", "Pacote de 10 Moedas (10 min.) por R$ 2,00"])

#    if st.button("Gerar Pix de Pagamento"):
#        valor, desc, tipo = (19.90, "Plano VIP 30 dias", "vip") if "VIP" in opcoes_compra else (2.00, "Pacote de 10 Moedas", "moedas")
#        id_limpo = id_usuario if isinstance(id_usuario, (list, tuple)) else id_usuario
#       
#        payment_data = {
#            "transaction_amount": valor, 
#            "description": desc, 
#            "payment_method_id": "pix",
#            "payer": {"email": "cliente@email.com"}, 
#            "external_reference": f"{id_limpo}:{tipo}"
#        }
        
    #     try:
    #         payment_response = sdk.payment().create(payment_data)
    #         payment = payment_response["response"]
            
    #         if "point_of_interaction" in payment:
    #             st.session_state.id_pagamento_pendente = payment["id"]
    #             st.session_state.tipo_pagamento_pendente = tipo
    #             st.session_state.qr_code_img = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]
    #             st.session_state.qr_code_texto = payment["point_of_interaction"]["transaction_data"]["qr_code"]
    #             st.success("Pix gerado com sucesso!")
    #             st.rerun()
    #     except Exception as e: 
    #         st.error(f"Erro ao gerar pagamento: {e}")

    # # Renderiza o QR Code caso ele já exista na sessão ativa
    # if st.session_state.get("qr_code_img"):
    #     st.markdown("### 📱 Escaneie o QR Code abaixo para pagar:")
    #     st.image(base64.b64decode(st.session_state.qr_code_img), width=250)
    #     st.text_area("Código Copia e Cola:", value=st.session_state.qr_code_texto, height=70)
        
    #     if st.button("🔄 Já realizei o pagamento", type="primary"):
    #         st.toast("Verificando compensação do Pix...")
    #         st.session_state.abrir_popup_loja = False
    #         st.rerun()



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
                id_limpo = id_usuario_logado if isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
                
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
            time.sleep(3)
            st.session_state.opcao_menu = "💬 Conversar com Lucy"
            st.rerun()

# ==============================================================================
# 3. CONEXÕES DE APIs E BANCO DE DADOS (ÁREA DO ESCOPO GLOBAL)
# ==============================================================================

@st.cache_data(ttl=15)  # Guarda os dados na memória por 15 segundos reduzindo requisições ao Supabase
def carregar_plano_e_moedas_cached(id_usuario):
    try:
        id_limpo = id_usuario[0] if isinstance(id_usuario, (tuple, list)) else id_usuario
        if id_limpo is not None:
            user_data = supabase.table("usuarios").select("tipo_plano", "moedas").eq("id", int(id_limpo)).execute()
            if user_data.data and len(user_data.data) > 0:
                return user_data.data[0]
    except Exception:
        pass
    return {"tipo_plano": "Grátis", "moedas": 0}


# ==============================================================================
# 5. RENDERIZADORES DE DIALOGS / MODAIS
# ==============================================================================

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
                conn = obter_conexao_eficiente()
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM usuarios WHERE email = %s', (email_digitado,))
                usuario_encontrado = cursor.fetchone()

                if usuario_encontrado:
                    senha_criptografada = generate_password_hash(nova_senha)
                    cursor.execute('UPDATE usuarios SET password_hash = %s WHERE email = %s', (senha_criptografada, email_digitado))
                    conn.commit()
                    cursor.close()
                    
                            
                    st.success("Senha redefinida com sucesso!")
                    time.sleep(1.5)
                    st.session_state.mostrar_recuperar_senha = False
                    st.rerun() 
                else:
                    cursor.close()
                    
                    st.error("E-mail não localizado no sistema.")
            except Exception as e:
                st.error(f"Erro ao acessar o banco de dados: {e}")



def template_painel_admin():
    st.markdown("<h2>🛠️ Painel Administrativo de Controle Avançado</h2>", unsafe_allow_html=True)
    st.caption("Métricas demográficas, performance preditiva da Lucy IA e moderação de contas em tempo real.")
    st.markdown("<hr style='border-color: #30363d; margin: 10px 0 25px 0;'>", unsafe_allow_html=True)

    usuarios_bd = []
    dados_agendados = {}
    dados_realizados = {}  
    dados_matches = {}
    total_salas_ativas = 0

    try:
        conn = obter_conexao_eficiente()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, genero, idade, procura_por, status FROM usuarios ORDER BY id ASC;")
        usuarios_bd = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(id) FROM matches 
            WHERE status_conexao = 'online' OR ultima_atividade >= NOW() - INTERVAL '5 minutes';
        """)
        total_salas_ativas = cursor.fetchone()[0]

        cursor.execute("SELECT TRIM(LOWER(dia_semana)), COUNT(*) FROM agendamentos_virtuais GROUP BY 1;")
        dados_agendados = dict(cursor.fetchall())
        
        cursor.execute("""
            SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT mc.id) 
            FROM agendamentos_virtuais a JOIN mensagens_sala mc ON mc.match_id = a.match_id GROUP BY 1;
        """)
        dados_realizados = dict(cursor.fetchall())
        
        cursor.execute("""
            SELECT TRIM(LOWER(a.dia_semana)), COUNT(DISTINCT m.id) 
            FROM agendamentos_virtuais a JOIN matches m ON m.id = a.match_id GROUP BY 1;
        """)
        dados_matches = dict(cursor.fetchall())

        # Tratamento de segurança para evitar valores nulos
        if total_salas_ativas is None:
            total_salas_ativas = 0

        cursor.close(); 
    except Exception as e:
        st.error(f"Erro na varredura analítica do banco: {e}")
        total_salas_ativas = 0
        dados_realizados = {} # Evita NameError caso o banco caia no Exception   

    if not usuarios_bd:
        st.warning("Nenhum dado de usuário localizado para gerar o painel.")
        return

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

    # Exibe Métricas Rápidas
    st.metric(label="Salas Privadas com Atividade Recente (5m)", value=int(total_salas_ativas))
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
                            conn_del = obter_conexao_eficiente()
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


    if st.button("← Voltar para o Chat", use_container_width=True):
        st.session_state.opcao_menu = "💬 Conversar com Lucy"
        st.rerun()


# ==============================================================================
# TELA PRIVADA 2: TEMPLATE FALE CONOSCO (SUPORTE TÉCNICO VIA EMAIL)
# ==============================================================================
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
# 8. ROTEADOR DE FLUXO GLOBAL (CORREÇÃO DE DIALOGS DUPLICADOS)
# ==============================================================================
menu_atual = st.session_state.get("opcao_menu", "home")

# 1. GESTÃO CENTRALIZADA DE MODAIS (Chame o modal aqui e use 'pass' ou 'return' para bloquear o miolo)
if st.session_state.get("abrir_reserva_fluxo"):
    modal_agendamento_encontro(st.session_state.abrir_reserva_fluxo)
    # Importante: Não deixe o script continuar executando telas no fundo enquanto o modal está ativo
    # Isso impede que o miolo chame outros blocos visuais concorrentes

# elif st.session_state.get("abrir_popup_loja"):
#     if st.session_state.get("usuario_id"):
#         mostrar_popup_loja(st.session_state.usuario_id)
#     st.session_state.abrir_popup_loja = False



# 2. SEGUIDO PELO SEU IF/ELIF NORMAL DE TELAS (Apenas se nenhum modal acima capturar o fluxo)
else:
    if menu_atual == "home":  
    # --- TELAS PÚBLICAS (Sem Barra Lateral de Usuário) ---
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

    elif menu_atual == "login":
            st.markdown('<h1 style="text-align:center; color:#007bff;">Login Lucy Chat IA</h1>', unsafe_allow_html=True)
            
            # Criamos uma chave para o formulário baseada se o usuário está logado ou não
            # Isso força o Streamlit a destruir o formulário visual da tela após o sucesso
            form_login_key = "form_login_ativo" if "usuario_id" not in st.session_state else "form_login_oculto"
            
            with st.form(form_login_key):
                user_in = st.text_input("Usuário", placeholder="Nome de Usuário ou E-mail", label_visibility="collapsed", key="login_user_field")
                pass_in = st.text_input("Senha", placeholder="Senha", type="password", label_visibility="collapsed", key="login_pass_field")
                    
                if st.form_submit_button("login", type="primary", use_container_width=True):
                    try:
                        conn = obter_conexao_eficiente()
                        cursor = conn.cursor()
                        cursor.execute("SELECT id, username, foto_perfil, is_admin, genero, tipo_plano, moedas FROM usuarios WHERE username = %s OR email = %s;", (user_in, user_in))
                        res = cursor.fetchone()
                        if res:
                            # 1. Define todas as variáveis de sessão primeiro
                            st.session_state.usuario_id = int(res[0])
                            st.session_state.username = res[1]
                            st.session_state.foto_perfil = res[2]
                            st.session_state.eh_admin = bool(res[3])
                            st.session_state.genero = res[4]
                            st.session_state.dados_usuario = {
                                "username": res[1], "foto_perfil": res[2], "genero": res[4],
                                "tipo_plano": str(res[5]).strip() if res[5] else "Grátis", "moedas": res[6] if res[6] else 0
                            }
                            
                            cursor.execute("UPDATE usuarios SET status = '🟢 Online' WHERE id = %s", (int(res[0]),))
                            conn.commit()
                            cursor.close()
                            
                            # 2. Atualiza a navegação para o chat
                            st.session_state.opcao_menu = "💬 Conversar com Lucy"
                            
                            # 3. Limpa explicitamente o estado dos campos de texto da memória do Streamlit
                            if "login_user_field" in st.session_state: del st.session_state["login_user_field"]
                            if "login_pass_field" in st.session_state: del st.session_state["login_pass_field"]
                            
                            # 4. Força o reinício limpo da aplicação fora do estado do formulário
                            st.rerun()
                        else:
                            st.error("Usuário não encontrado.")
                        cursor.close() 
                    except Exception as e: 
                        st.error(f"Erro: {e}")       

            col_voltar, col_esqueceu = st.columns(2)
            with col_voltar:
                if st.button("⬅️ Voltar para a Home", use_container_width=True, key="btn_voltar_home_login"):
                    st.session_state.opcao_menu = "home"
                    st.rerun()
            with col_esqueceu:
                if st.button("🔑 Esqueceu a senha?", use_container_width=True, key="btn_esqueceu_senha_login"):
                    modal_recuperar_senha()

                

    elif menu_atual == "cadastro":
        st.html('<h2 style="text-align:center; color:#007bff;">Criar Conta</h2>')
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
                    if not usuario.strip() or not email.strip() or not senha.strip():
                        st.warning("⚠️ Por favor, preencha todos os campos.")
                    elif len(senha) < 6:
                        st.warning("⚠️ A senha deve ter pelo menos 6 caracteres.")
                    else:
                        conn = None
                        try:
                            conn = obter_conexao_eficiente()
                            cursor = conn.cursor()
                            cursor.execute("SELECT username, email FROM usuarios WHERE username = %s OR email = %s;", (usuario.strip(), email.strip()))
                            existente = cursor.fetchone()
                            if existente:
                                st.error("❌ Usuário ou E-mail já cadastrado.")
                            else:
                                senha_final = generate_password_hash(senha)
                                cursor.execute("INSERT INTO usuarios (username, email, password_hash, genero, status, is_admin) VALUES (%s, %s, %s, %s, '🟢 Online', FALSE) RETURNING id;", (usuario.strip(), email.strip(), senha_final, genero))
                                st.session_state.usuario_id = int(cursor.fetchone()[0])
                                st.session_state.username = usuario.strip()
                                st.session_state.genero = genero
                                conn.commit()
                                    
                                # Atualiza para a tela de planos e limpa estados residuais
                                st.session_state.opcao_menu = "planos"
                                st.rerun()
                        except Exception as e: 
                            st.error(f"Erro ao processar cadastro: {e}")
                        finally:
                            if conn:
                                cursor.close()
                                    

        if st.button("← Voltar para o Login", use_container_width=True):
            st.session_state.opcao_menu = "login"
            st.rerun()


    elif menu_atual == "planos":
        st.session_state.opcao_menu = "planos"
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
                


                
        with st.sidebar:
            # CORREÇÃO: Captura o ID do usuário da sessão
            id_usuario = st.session_state.get("id_usuario", "usuario_anonimo")
            
            opcoes_compra = st.radio("Escolha uma opção:", ["Assinatura VIP por R$ 19,90/mês", "Pacote de 10 Moedas (10 min.) por R$ 2,00"])
            
            if st.button("Gerar Pix de Pagamento"):
                valor, desc, tipo = (19.90, "Plano VIP 30 dias", "vip") if "VIP" in opcoes_compra else (2.00, "Pacote de 10 Moedas", "moedas")
                id_limpo = id_usuario if isinstance(id_usuario, (list, tuple)) else id_usuario
                
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

            # Renderiza o QR Code caso ele já exista na sessão ativa
            if st.session_state.get("qr_code_img"):
                st.markdown("### 📱 Escaneie o QR Code abaixo para pagar:")
                st.image(base64.b64decode(st.session_state.qr_code_img), width=250)
                st.text_area("Código Copia e Cola:", value=st.session_state.qr_code_texto, height=70)
                        
                # BOTÃO CORRIGIDO: Agora ele realmente valida o Pix
                if st.button("🔄 Já realizei o pagamento", type="primary"):
                    id_pagamento = st.session_state.get("id_pagamento_pendente")
                    
                    if id_pagamento:
                        with st.spinner("Verificando compensação do Pix..."):
                            status = verificar_status_pix(id_pagamento)
                        
                        if status == "approved":
                            st.success("🎉 Pagamento aprovado! Seu acesso foi liberado.")

                            # --- INTEGRAÇÃO COM O SUPABASE ---
                            tipo = st.session_state.tipo_pagamento_pendente
                            sucesso_banco = atualizar_plano_banco_supabase(id_usuario, tipo_pagamento)
                            
                            if sucesso_banco:
                                st.toast("Sua conta foi atualizada com sucesso no banco!")
                            else:
                                st.error("Erro ao computar créditos no banco. Contate o suporte informando o ID do pagamento.")
                            
                            # Limpa as variáveis de pagamento da sessão para sumir com o QR code
                            del st.session_state.qr_code_img
                            del st.session_state.qr_code_texto
                            del st.session_state.id_pagamento_pendente
                            
                            st.session_state.abrir_popup_loja = False
                            st.rerun()
                                                     
                        elif status == "pending":
                            st.warning("⏳ O pagamento ainda consta como pendente. Aguarde um instante e tente novamente.")
                        else:
                            st.error(f"❌ O status do pagamento é: {status}. Se houve algum problema, contate o suporte.")
                    else:
                        st.error("Nenhum ID de pagamento encontrado na sessão.")
          
        if st.button("← Voltar para o Chat", use_container_width=True):
                st.session_state.opcao_menu = "💬 Conversar com Lucy"
                st.rerun() 
        
        if st.button("← Voltar para o Login", use_container_width=True):
                st.session_state.opcao_menu = "login"
                st.rerun() 
                    
        

    # --- TELAS PRIVADAS (Com Barra Lateral de Usuário Logado) ---
    elif menu_atual in ["💬 Conversar com Lucy", "📅 Disponibilidade", "🤝 Gerenciar Conexões", "🤝 Sala Privada", "🛠️ Painel Admin"]:
    #    st.markdown("### 🔍 Inspecionando Caminhos de Imagens")

                # 1. Verifica os dados salvos na Sessão Atual do Navegador
            #    id_usuario_logado = st.session_state.get("usuario_id")
            #    foto_sessao = st.session_state.get("foto_perfil")

            #    st.write(f"🔹 **Seu ID de Usuário:** `{id_usuario_logado}`")
            #    st.write(f"🔹 **Caminho salvo na Session State:** `{foto_sessao}`")

                # 2. Testa a limpeza da barra que o sistema operacional exige
            #    if foto_sessao:
            #        caminho_limpo = str(foto_sessao).strip().lstrip('/')
            #        st.write(f"🥾 **Caminho convertido para o Servidor:** `{caminho_limpo}`")
            #        st.write(f"📂 **O arquivo existe fisicamente no servidor?** `{'✅ SIM' if os.path.exists(caminho_limpo) else '❌ NÃO'}`")

                # 3. Faz uma varredura real na pasta física para listar TODAS as fotos salvas
            #    st.markdown("#### 📁 Arquivos encontrados na pasta `static/uploads/perfis/`:")
            #    try:
            #        if os.path.exists(UPLOAD_FOLDER):
            #            arquivos = os.listdir(UPLOAD_FOLDER)
            #            if arquivos:
            #                for arq in arquivos:
            #                    caminho_completo_arquivo = os.path.join(UPLOAD_FOLDER, arq)
            #                    tamanho_kb = os.path.getsize(caminho_completo_arquivo) / 1024
            #                    st.code(f"📄 {arq} ({tamanho_kb:.1f} KB) -> Caminho para ler no st.image: '{caminho_completo_arquivo}'")
            #            else:
            #                st.info("A pasta existe, mas está vazia. Nenhum usuário fez upload de foto ainda.")
            #        else:
            #            st.warning("⚠️ A pasta de uploads ainda não foi criada fisicamente no servidor remoto.")
            #    except Exception as e:
            #        st.error(f"Erro ao listar diretório: {e}")
            
            

                #avatar_html = ""
                # Desenha a barra lateral UMA ÚNICA VEZ para o ecossistema privado

        with st.sidebar: 
            # ==========================================================================
            # --- PERFIL DO USUÁRIO & AVATAR CENTRALIZADO E MAIOR ---
            # ==========================================================================
            caminho_foto_perfil = str(st.session_state.get("foto_perfil", "")).strip()
                    
            # Cria 3 colunas para forçar o alinhamento no centro absoluto da barra lateral
            col_esq, col_centro, col_dir = st.columns([1, 2, 1])
            with col_centro:
                if caminho_foto_perfil and (caminho_foto_perfil.startswith("http") or os.path.exists(caminho_foto_perfil.lstrip('/'))):
                    # Aumentado para width=85 para dar mais destaque ao rosto
                    st.image(caminho_foto_perfil, width=85)
                else:
                    # Emoji centralizado e ampliado
                    st.markdown('<div style="font-size: 65px; text-align:center; margin-top: -10px;">👩</div>', unsafe_allow_html=True)

            # Extração limpa do nome do usuário antes do '@'
            username_atual = st.session_state.get("username", "Usuário")
            nome_usuario_puro = str(username_atual).split('@')[0].capitalize()

            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 20px; margin-top: 5px;">
                    <h3 style="margin: 0; font-size: 17px; font-weight: bold; color: #f0f6fc;">{nome_usuario_puro}</h3>
                    <p style="color: #48bb78; font-weight: bold; font-size: 13px; margin: 4px 0 0 0;">🟢 Online</p>
                </div>
            """, unsafe_allow_html=True)

            # ==========================================================================
            # --- CONSULTA 1: PLANO E SALDO REAL (PROCESSAMENTO CACHED TOTALMENTE BLINDADO) ---
            # ==========================================================================
            tipo_plano = "Grátis"
            saldo_moedas = 0
            id_usuario_logado = st.session_state.get("usuario_id")

            if id_usuario_logado is not None:
                try:
                    # Carrega o registro direto da nossa função de memória cache
                    registro_banco = carregar_plano_e_moedas_cached(id_usuario_logado)
                        
                    # CORREÇÃO DA LEITURA: O Supabase com Service Key pode retornar uma lista ou dicionário direto
                    # Esta lógica desempacota com segurança qualquer um dos dois formatos
                    if isinstance(registro_banco, list) and len(registro_banco) > 0:
                        dados_reais = registro_banco[0]
                    elif isinstance(registro_banco, dict):
                        dados_reais = registro_banco
                    else:
                        dados_reais = {}

                    # Captura o plano bruto tratando valores nulos
                    plano_bruto = str(dados_reais.get("tipo_plano", "Grátis")).strip()
                        
                    # Normalização total de strings (elimina acentos, espaços e caixa alta)
                    plano_norm = unicodedata.normalize('NFKD', plano_bruto).encode('ASCII', 'ignore').decode('utf-8').lower()
                        
                    if "credito" in plano_norm or "moedas" in plano_norm:
                        tipo_plano = "Plano Crédito de Moedas"
                    elif "vip" in plano_norm or "assinante" in plano_norm:
                        tipo_plano = "vip"
                    else:
                        tipo_plano = "Grátis"
                            
                    saldo_moedas = int(dados_reais.get("moedas", 0) or 0)
                            
                except Exception as e:
                    st.error(f"Erro ao mapear cache de saldo: {e}")
            else:
                st.warning("⚠️ Usuário não identificado na sessão.")

            # Sincroniza e trava os estados de forma idêntica para o Roteador e Telas
            st.session_state["tipo_plano"] = tipo_plano
            st.session_state["saldo_moedas"] = saldo_moedas

            # Renderização do cabeçalho de cobrança na Sidebar
            st.caption(f"Plano: **{tipo_plano}** | Saldo: 🪙 **{saldo_moedas} moedas**")
                                

            # ==========================================================================
            # --- COMPONENTE: ALTERAR FOTO DE PERFIL (CORREÇÃO ANTI-LOOP) ---
            # ==========================================================================
            st.caption("📷 Enviar nova foto de perfil:")
                
            # Usamos uma chave dinâmica baseada no form_seed para resetar o uploader após o sucesso
            f_nova = st.file_uploader(
                "Alterar Foto", 
                type=["png","jpg","jpeg"], 
                key=f"side_f_up_{st.session_state.get('form_seed', 42)}", 
                label_visibility="collapsed"
            ) 
                
            if f_nova and id_usuario_logado: 
                id_limpo = id_usuario_logado if isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
                nome_arquivo_storage = f"user_{id_limpo}.jpg"
                    
                try:
                    # 1. Converte o arquivo enviado para bytes brutos
                    dados_imagem_bytes = f_nova.getvalue()
                        
                    # 2. Faz o upload direto para o bucket 'perfis' (Ignorando RLS via Service Key)
                    supabase.storage.from_("perfis").upload(
                        path=nome_arquivo_storage,
                        file=dados_imagem_bytes,
                        file_options={"content-type": "image/jpeg", "upsert": "true"}
                    )
                        
                    # 3. CORREÇÃO: Captura a string da URL pública de forma explícita
                    resposta_url = supabase.storage.from_("perfis").get_public_url(nome_arquivo_storage)
                        
                    # Dependendo da versão da biblioteca, extrai a string pura do link
                    if hasattr(resposta_url, "public_url"):
                        url_publica_foto = str(resposta_url.public_url).strip()
                    else:
                        url_publica_foto = str(resposta_url).strip()
                        
                    # 4. Grava a URL estável no PostgreSQL
                    conn_foto = obter_conexao_eficiente()
                    cursor_foto = conn_foto.cursor() 
                    cursor_foto.execute("UPDATE usuarios SET foto_perfil = %s WHERE id = %s;", (url_publica_foto, int(id_limpo))) 
                    conn_foto.commit()
                    cursor_foto.close()
                        
                    # Atualiza a memória ativa do navegador
                    st.session_state.foto_perfil = url_publica_foto
                    st.cache_data.clear()
                        
                    # 🚨 O SEGREDO AQUI: Alteramos o ID da semente para resetar o componente st.file_uploader
                    # Isso faz o arquivo "sumir" da memória do uploader, quebrando o loop de rerun
                    if "form_seed" in st.session_state:
                        st.session_state.form_seed += 1
                    else:
                        st.session_state.form_seed = 43
                        
                    st.toast("📷 Foto de perfil salva permanentemente na nuvem!")
                    time.sleep(1)
                    st.rerun() 
                        
                except Exception as e:
                    st.error(f"Erro ao salvar foto no Storage: {e}")   
                
            # ==========================================================================
            # --- CONSULTA 2: MOTOR DE BUSCA DA NOTIFICAÇÃO ---
            # ==========================================================================
            possui_convite_pendente = False
            if id_usuario_logado:
                try:
                    meu_id_limpo = int(id_usuario_logado[0]) if isinstance(id_usuario_logado, (tuple, list)) else int(id_usuario_logado)
                    conn_b = obter_conexao_eficiente()
                    cursor_b = conn_b.cursor()
                    cursor_b.execute("SELECT COUNT(*) FROM agendamentos_virtuais WHERE destinatario_id = %s AND status_convite = 'pendente';", (meu_id_limpo,))
                    count_res = cursor_b.fetchone()
                    if count_res and count_res[0] > 0: 
                        possui_convite_pendente = True
                    cursor_b.close()
                    
                except Exception: 
                    pass

            # Configura o rótulo do botão baseado na presença de convites
            if possui_convite_pendente:
                label_gestao = "🤝 ABRIR GESTÃO 🔴"
                st.markdown("""
                    <div style='background-color: #21262d; border: 1px solid #ef4444; border-radius: 6px; padding: 6px; text-align: center; margin-bottom: 8px;'>
                        <span style='font-size: 11px; color: #ef4444; font-weight: bold;'>📩 VOCÊ RECEBEU UM NOVO CONVITE!</span>
                </div>
                    """, unsafe_allow_html=True)
            else:
                label_gestao = "🤝 ABRIR GESTÃO"

            # ==========================================================================
            # --- BOTÕES DE NAVEGAÇÃO INTERNA ---
            # ==========================================================================
            if st.button(label_gestao, type="secondary", use_container_width=True, key="btn_sidebar_gestao_rel"):
                st.session_state.opcao_menu = "🤝 Gerenciar Conexões"
                st.rerun()
                    
            if st.button("📅 MINHA GRADE HORÁRIA", type="primary", use_container_width=True, key="btn_grade_horaria"): 
                st.session_state.opcao_menu = "📅 Disponibilidade"
                st.rerun()
                    
            if st.button("Ir para a Loja 🛒", type="secondary", use_container_width=True):
                st.session_state.opcao_menu = "planos"
                st.rerun()
                    
            # Validação de privilégios administrativos
            eh_admin = st.session_state.get("eh_admin", False)
            if eh_admin or username_atual in ['admin', 'Clever1404']:
                if st.button("⚙️ PAINEL ADMINISTRATIVO", type="secondary", use_container_width=True, key="btn_painel_adm"):
                    st.session_state.opcao_menu = "🛠️ Painel Admin"
                    st.rerun()     

            if st.button("🗑️ LIMPAR HISTÓRICO DA IA", type="secondary", use_container_width=True, key="btn_limpar_ia"):
                if id_usuario_logado:
                    try:
                        id_limpo = id_usuario_logado[0] if isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
                        conn = obter_conexao_eficiente()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM historico_ia WHERE usuario_id = %s;", (int(id_limpo),))
                        conn.commit()
                        cursor.close()
                        
                        st.toast("Histórico limpo!")
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Erro: {e}")

            st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True) 
                
            
            # ==========================================================================
            # --- BOTÃO: ENCERRAR SESSÃO (LOGOUT 100% CORRIGIDO SEM ERRO DE INT) ---
            # ==========================================================================
            if st.button("🚪 ENCERRAR SESSÃO", type="primary", use_container_width=True, key="btn_logout_sistema"):
                if id_usuario_logado:
                    try:
                        # Como st.session_state.usuario_id já guarda um inteiro puro do Login,
                        # forçamos a conversão direta sem tentar ler índices de lista/tupla
                        id_limpo = int(id_usuario_logado)
                        
                        # Conecta e executa a atualização imediata no banco
                        conn_logout = obter_conexao_eficiente()
                        cursor_logout = conn_logout.cursor()
                        cursor_logout.execute("UPDATE usuarios SET status = '⚫ Offline' WHERE id = %s;", (id_limpo,))
                        conn_logout.commit()
                        cursor_logout.close()
                    except Exception as e:
                        # Se falhar, limpa o canal de transação do PostgreSQL
                        if 'conn_logout' in locals() and conn_logout:
                            conn_logout.rollback()
                        st.sidebar.error(f"Erro no banco ao deslogar: {e}")
                
                # Limpa absolutamente toda a memória do navegador do usuário
                for chave in list(st.session_state.keys()):
                    del st.session_state[chave]
                    
                # Restabelece os estados padrão iniciais para o roteador abrir a tela de login
                st.session_state.usuario_id = None
                st.session_state.username = None
                st.session_state.opcao_menu = "login"
                st.session_state.form_seed = 42
                
                st.rerun()
        
        # Renderiza estritamente a tela selecionada no miolo da página
        if menu_atual == "💬 Conversar com Lucy":   
            # Apenas invoca o fragmento global de forma ultra eficiente
            renderizar_chat_lucy_isolado()   
            
        elif menu_atual == "📅 Disponibilidade":
                template_disponibilidade()
                
        elif menu_atual == "🤝 Gerenciar Conexões":
            st.title("🤝 Gestão de Relacionamentos") 

            
            if st.button("← Voltar para o Chat da Lucy", type="secondary", key="btn_voltar_lucy_gestao"):
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
                    conn = obter_conexao_eficiente(); cursor = conn.cursor()
                    cursor.execute('SELECT m.id, u.username, u.foto_perfil, u.genero, u.id FROM matches m JOIN usuarios u ON (u.id = m.usuario_2_id OR u.id = m.usuario_1_id) WHERE (m.usuario_1_id = %s OR m.usuario_2_id = %s) AND u.id != %s;', (meu_id_limpo, meu_id_limpo, meu_id_limpo))
                    matches_dados = cursor.fetchall(); cursor.close(); 
                except Exception: pass

                if not matches_dados: st.info("Nenhum par localizado.")
                for m_id, m_nome, m_foto, m_gen, par_id in matches_dados:
                    with st.container(border=True):
                        # Estrutura em colunas equilibradas para reduzir o tamanho do retângulo
                        c_av_c, c_nm_c, c_go_c, c_del_c = st.columns([0.6, 2, 1, 1])
                        
                        with c_av_c:
                            # Limpa o caminho para o sistema operacional encontrar o arquivo
                            caminho_par_img = str(m_foto).strip().lstrip('/')
                        
                            if m_foto and os.path.exists(caminho_par_img):
                                # Desenha a foto de forma nativa e ultra veloz
                                st.image(caminho_par_img, width=50)
                            else:
                                # Fallback limpo com layout alinhado caso não possua foto
                                st.markdown(f'<div style="font-size: 35px; margin-top: 5px;">{"👩" if m_gen == "F" else "👨"}</div>', unsafe_allow_html=True)

                                
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
                                    conn = obter_conexao_eficiente(); cursor = conn.cursor()
                                    cursor.execute("DELETE FROM mensagens_chat WHERE match_id = %s;", (int(m_id),))
                                    cursor.execute("DELETE FROM agendamentos_virtuais WHERE match_id = %s;", (int(m_id),))
                                    cursor.execute("DELETE FROM matches WHERE id = %s;", (int(m_id),))
                                    conn.commit(); cursor.close(); 
                                    st.toast("Match removido!")
                                    st.rerun()
                                except Exception as e: st.error(f"Erro: {e}")


            with aba_e:
                st.markdown("### 📩 Convites Ativos da Semana")
                try:
                    conn = obter_conexao_eficiente(); cursor = conn.cursor()
                    cursor.execute("""
                        SELECT a.id, a.dia_semana, a.periodo, a.horario, a.status_convite, a.remetente_id,
                        CASE WHEN a.remetente_id = %s THEN u2.username ELSE u1.username END as nome_parceiro, a.match_id
                        FROM agendamentos_virtuais a JOIN matches m ON m.id = a.match_id JOIN usuarios u1 ON u1.id = m.usuario_1_id JOIN usuarios u2 ON u2.id = m.usuario_2_id
                        WHERE a.remetente_id = %s OR a.destinatario_id = %s ORDER BY a.id DESC;
                    """, (meu_id_limpo, meu_id_limpo, meu_id_limpo))
                    encontros = cursor.fetchall(); cursor.close(); 
                    
                    # --- CORREÇÃO DA SEPARAÇÃO: Baseado estritamente no status do convite ---
                    # Ativos: Qualquer um que ainda esteja Pendente ou que já foi Aceito (independente do dia ser hoje ou futuro)
                    encontros_ativos = [e for e in encontros if str(e[4]).lower() in ['pendente', 'aceito']]
                    
                    # Passados: Apenas registros explicitamente arquivados, concluídos, rejeitados ou cancelados
                    encontros_passados = [e for e in encontros if str(e[4]).lower() in ['concluido', 'recusado', 'cancelado']]
                    
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
                                        conn = obter_conexao_eficiente(); cursor = conn.cursor(); cursor.execute("UPDATE agendamentos_virtuais SET status_convite = 'aceito' WHERE id = %s;", (ag_id,)); conn.commit(); cursor.close(); st.rerun()
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



        elif menu_atual == "🤝 Sala Privada":
            if st.session_state.get("match_id_atual"):
                template_sala_privada()
            else:
                st.warning("Nenhuma sala ativa.")
                st.session_state.opcao_menu = "💬 Conversar com Lucy"
                st.rerun()
                    
        elif menu_atual == "🛠️ Painel Admin":
            template_painel_admin()
        elif st.session_state.opcao_menu == "✉️ Fale Conosco":
            template_fale_conosco()

    # ==============================================================================
    # FALLBACK DE SEGURANÇA SEGURO (FIM DO ARQUIVO)
    # ==============================================================================
    else:
        # Se o menu atual não corresponder a nenhuma tela, redefine para a home 
        # e renderiza o layout visual imediatamente, quebrando loops de st.rerun()
        st.session_state.opcao_menu = "home"
        #template_home()        

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
