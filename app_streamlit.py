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
        conn.commit(); cursor.close()
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback(); cursor.close()
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
# FUNÇÃO ISOLADA COM FILA DE RENDERIZAÇÃO (MENSAGENS SEMPRE ACIMA DO INPUT)
# ==============================================================================
@st.fragment
def renderizar_chat_lucy_isolado():
    st.markdown("### 🤖 Conversar com Lucy")
    st.caption("Fale sobre sua rotina, hobbies e o que procura. Lucy usa IA para analisar seu perfil e encontrar pessoas compatíveis.")
    st.markdown("<hr style='border-color: #30363d; margin: 10px 0 20px 0;'>", unsafe_allow_html=True)

    meu_id_limpo = st.session_state.usuario_id if not isinstance(st.session_state.usuario_id, (tuple, list)) else int(st.session_state.usuario_id)

    # 1. Busca o histórico de mensagens do banco de dados
    historico_banco = buscar_memoria(meu_id_limpo, limite=20)
    
    # Captura o clique ou texto do input do rodapé IMEDIATAMENTE (Sem desenhar nada ainda)
    prompt = st.chat_input("Digite sua mensagem para a Lucy...")

    # 2. SE O USUÁRIO DIGITOU ALGO: Processa a inteligência artificial ANTES de renderizar a tela
    # Isso garante que a nova interação seja salva e apareça dentro da caixa de histórico acima
    if prompt:
        try:
            contexto_mensagens = [
                {"role": "system", "content": "Você é a Lucy, uma IA psicóloga e assistente de relacionamentos altamente empática. Seu objetivo é entender o estilo de vida, gostos e rotina do usuário através de uma conversa natural. Seja acolhedora, faça perguntas abertas e ajude-o a se expressar para encontrar o par ideal."}
            ]
            
            for p, r in historico_banco[-5:]:
                contexto_mensagens.append({"role": "user", "content": p})
                contexto_mensagens.append({"role": "assistant", "content": r})
            
            contexto_mensagens.append({"role": "user", "content": prompt})

            resposta_openai = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=contexto_mensagens,
                temperature=0.7
            )
            resposta_lucy = resposta_openai.choices[0].message.content

            # Salva no histórico de forma eficiente utilizando a conexão estável
            conn_salvar = obter_conexao_eficiente()
            cursor_salvar = conn_salvar.cursor()
            cursor_salvar.execute("""
                INSERT INTO historico_ia (usuario_id, usuario_pergunta, ia_resposta) 
                VALUES (%s, %s, %s);
            """, (meu_id_limpo, prompt, resposta_lucy))
            conn_salvar.commit()
            cursor_salvar.close()

            # Dispara o motor de afinidade
            dados_match = processar_afinidade_e_match(meu_id_limpo, prompt)
            if dados_match and dados_match.get("match"):
                st.session_state.alerta_match = {
                    "match_id": dados_match.get("match_id", random.randint(1000, 9999)),
                    "id_par": dados_match.get("id_par"),
                    "nome": dados_match.get("nome_par"),
                    "online": dados_match.get("online", False)
                }
                processar_match_lucy(st.session_state.alerta_match)

            # Recarrega imediatamente o fragmento para que a lista do passo 3 já inclua a nova mensagem
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar conversa com a IA: {e}")

    # 3. ÁREA VISUAL SUPERIOR: Desenha o histórico antigo + a nova mensagem (se houver)
    with st.container(height=480, border=False):
        for pergunta_antiga, resposta_antiga in historico_banco:
            with st.chat_message("user"):
                st.markdown(pergunta_antiga)
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(resposta_antiga)


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

    if st.button("💾 Confirmar Reserva e Enviar", type="primary", use_container_width=True, key="btn_confirmar_reserva_click"):
        try:
            conn = obter_conexao_eficiente()
            cursor = conn.cursor()
            
            # PROTEÇÃO CRÍTICA: Verifica se o match_id realmente existe na tabela 'matches' antes de tentar o INSERT
            cursor.execute("SELECT COUNT(*) FROM matches WHERE id = %s;", (m_id_limpo,))
            match_existe = cursor.fetchone()[0] > 0
            
            if not match_existe:
                # Caso o match_id original tenha sumido, tenta localizar ou criar um novo ID de vínculo estável
                cursor.execute("""
                    SELECT id FROM matches 
                    WHERE (usuario_1_id = %s AND usuario_2_id = %s) OR (usuario_1_id = %s AND usuario_2_id = %s) 
                    LIMIT 1;
                """, (meu_id_limpo, parceiro_id_limpo, parceiro_id_limpo, meu_id_limpo))
                match_recuperado = cursor.fetchone()
                
                if match_recuperado:
                    m_id_limpo = int(match_recuperado[0])
                else:
                    # Se não existir nenhuma linha de match entre os dois usuários, cria uma na hora
                    cursor.execute("""
                        INSERT INTO matches (usuario_1_id, usuario_2_id, status_conexao) 
                        VALUES (%s, %s, 'offline') RETURNING id;
                    """, (meu_id_limpo, parceiro_id_limpo))
                    m_id_limpo = int(cursor.fetchone()[0])
                    conn.commit()

            # Realiza as validações de disponibilidade padrão
            cursor.execute("""
                SELECT COUNT(*) FROM disponibilidade_usuarios 
                WHERE usuario_id = %s AND LOWER(TRIM(dia_semana)) = LOWER(TRIM(%s)) AND LOWER(TRIM(periodo)) = LOWER(TRIM(%s));
            """, (meu_id_limpo, str(dia_s), str(per_s)))
            meu_registro_existe = cursor.fetchone()[0] > 0
            
            cursor.execute("SELECT COUNT(*) FROM disponibilidade_usuarios WHERE usuario_id = %s;", (parceiro_id_limpo,))
            parceiro_tem_algum_horario = cursor_check.fetchone()[0] > 0 if 'cursor_check' in locals() else cursor.fetchone()[0] > 0
            
            cursor.close(); 
            
            # Validação simples de segurança horária
            hora_int = hor_s.hour
            if per_s == 'manha' and (hora_int < 6 or hora_int >= 12): 
                st.error("❌ Horário inválido para Manhã (06:00 às 11:59).")
            elif per_s == 'tarde' and (hora_int < 12 or hora_int >= 18): 
                st.error("❌ Horário inválido para Tarde (12:00 às 17:59).")
            elif per_s == 'noite' and (hora_int < 18 or hora_int > 23): 
                st.error("❌ Horário inválido para Noite (18:00 às 23:59).")
            else:
                # CORREÇÃO: Abre a conexão persistente e garante o mesmo nome em todas as linhas
                conn_salvar = obter_conexao_eficiente()
                cursor_salvar = conn_salvar.cursor()
                
                cursor_salvar.execute("""
                    INSERT INTO agendamentos_virtuais (match_id, remetente_id, destinatario_id, dia_semana, periodo, horario, status_convite) 
                    VALUES (%s, %s, %s, %s, %s, %s, 'pendente');
                """, (m_id_limpo, meu_id_limpo, parceiro_id_limpo, str(dia_s), str(per_s), hor_s))
                
                # Executa o commit e fecha o cursor usando a variável correta definida acima
                conn_salvar.commit()
                cursor_salvar.close()
                
                st.success("🎉 Convite enviado com sucesso!")
                st.session_state.abrir_reserva_fluxo = None
                time.sleep(1.2)
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

    st.title("🤝 Sala Privada de Conversa")
    
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
        
        if id_match_atual:
            try:
                agora_iso = datetime.now().isoformat()
                supabase.table("matches").update({"status_conexao": "online", "ultima_atividade": agora_iso}).eq("id", id_match_atual).execute()
            except Exception: pass
            
        st.divider()

        if st.button("🎥 Iniciar Videochamada Privada"): 
            id_match_int = match_id if isinstance(match_id, (tuple, list)) else int(match_id)
            url_jitsi = f"https://jit.si_{id_match_int}" 
            st.info("A videochamada foi iniciada abaixo. Garanta as permissões no navegador.") 
            st.iframe(url_jitsi, height=500) 

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
        
        if st.form_submit_button("Enviar para o Suporte", type="primary", use_container_width=True):
            if not email_contato or not descricao_contato: 
                st.error("❌ Por favor, preencha seu e-mail e a descrição da mensagem.") 
            else: 
                st.success("🎉 Sua mensagem foi enviada para o e-mail de suporte (suporte@lucyia.com) com sucesso!") 

    if st.button("← Voltar para o Chat Principal", type="secondary"): 
        st.session_state.opcao_menu = "💬 Conversar com Lucy" 
        st.rerun() 




# ==============================================================================
# MODAL DA LOJA DO APP (CORRIGIDO E FECHADO)
# ==============================================================================
@st.dialog("🛒 Loja do App")
def mostrar_popup_loja(id_usuario):
    opcoes_compra = st.radio("Escolha uma opção:", ["Assinatura VIP (R$ 19,90)", "10 Moedas (R$ 5,00)"])

    if st.button("Gerar Pix de Pagamento"):
        valor, desc, tipo = (19.90, "Plano VIP 30 dias", "vip") if "VIP" in opcoes_compra else (5.00, "Pacote de 10 Moedas", "moedas")
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
        
        if st.button("🔄 Já realizei o pagamento", type="primary"):
            st.toast("Verificando compensação do Pix...")
            st.session_state.abrir_popup_loja = False
            st.rerun()

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
            WHERE status_conexao = 'online' AND ultima_atividade >= NOW() - INTERVAL '5 minutes';
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

        cursor.close(); 
    except Exception as e:
        st.error(f"Erro na varredura analítica do banco: {e}")
        total_salas_ativas = 0

    if not usuarios_bd:
        st.warning("Nenhum dado de usuário localizado para gerar o painel.")
        return

    df_usuarios_mod = pd.DataFrame(usuarios_bd, columns=["ID", "Nome / Username", "E-mail", "Gênero", "Idade", "Procura Por", "Status Presença"])
    
    # Exibe Métricas Rápidas
    st.metric(label="Salas Privadas com Atividade Recente (5m)", value=int(total_salas_ativas))
    
    # Renderização da Tabela de Moderação
    st.markdown("### 👥 Tabela Geral de Usuários Cadastrados")
    st.dataframe(df_usuarios_mod, use_container_width=True, hide_index=True)
    
    # Gráfico Simples de Engajamento Semanal
    st.markdown("### 📊 Monitoramento de Interações Semanais")
    dias_semana_lista = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
    
    dados_grafico = []
    for d in dias_semana_lista:
        dados_grafico.append({
            "Dia": d.capitalize(),
            "Agendados": dados_agendados.get(d, 0),
            "Matches": dados_matches.get(d, 0),
            "Mensagens": dados_realizados.get(d, 0)
        })
    
    df_grafico = pd.DataFrame(dados_grafico)
    st.line_chart(df_grafico.set_index("Dia"), use_container_width=True)

    if st.button("← Voltar para o Chat", use_container_width=True, key="btn_voltar_admin"):
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

elif st.session_state.get("abrir_popup_loja"):
    if st.session_state.get("usuario_id"):
        mostrar_popup_loja(st.session_state.usuario_id)
    st.session_state.abrir_popup_loja = False

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
        with st.form("form_login"):
            user_in = st.text_input("Usuário", placeholder="Nome de Usuário ou E-mail", label_visibility="collapsed")
            pass_in = st.text_input("Senha", placeholder="Senha", type="password", label_visibility="collapsed")
                
            if st.form_submit_button("login", type="primary", use_container_width=True):
                try:
                    conn = obter_conexao_eficiente()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, username, foto_perfil, is_admin, genero, tipo_plano, moedas FROM usuarios WHERE username = %s OR email = %s;", (user_in, user_in))
                    res = cursor.fetchone()
                    if res:
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
                        conn.commit(); cursor.close(); 
                        st.session_state.opcao_menu = "💬 Conversar com Lucy"
                        st.rerun()
                    else:
                        st.error("Usuário não encontrado.")
                    cursor.close(); 
                except Exception as e: 
                    st.error(f"Erro: {e}")       

        col_voltar, col_esqueceu = st.columns(2)
        with col_voltar:
            if st.button("⬅️ Voltar para a Home", use_container_width=True):
                st.session_state.opcao_menu = "home"
                st.rerun()
        with col_esqueceu:
            # CORREÇÃO AQUI: Removemos o st.rerun() daqui de dentro. 
            # Agora o Streamlit consegue renderizar o modal sem sofrer interrupção imediata.
            if st.button("🔑 Esqueceu a senha?", use_container_width=True):
                modal_recuperar_senha()

            

    elif menu_atual == "cadastro":
        st.html('<h2 style="text-align:center; color:#007bff;">Criar Conta</h2>')
        with st.form(key=f"form_cad_unico_{st.session_state.form_seed}"):
            usuario = st.text_input("Usuário", placeholder="Escolha um Usuário", label_visibility="collapsed")
            email = st.text_input("E-mail", placeholder="Digite seu E-mail", label_visibility="collapsed")
            senha = st.text_input("Senha", placeholder="Escolha uma Senha", type="password", label_visibility="collapsed")
            genero = st.selectbox("Gênero", options=["M", "F"], index=0, label_visibility="collapsed")
                
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
            
            # Botão para ir para a loja (Troca a tela inteira)
            if st.button("🛒 Ir para a Loja de Moedas e Assinaturas", type="primary", use_container_width=True):
                id_usuario = st.session_state.get("id_usuario", "usuario_teste")
                mostrar_popup_loja(id_usuario)

            if st.button("← Voltar para o Login", use_container_width=True):
                st.session_state.opcao_menu = "login"
                st.rerun() 
                
      

    # --- TELAS PRIVADAS (Com Barra Lateral de Usuário Logado) ---
    elif menu_atual in ["💬 Conversar com Lucy", "📅 Disponibilidade", "🤝 Gerenciar Conexões", "🤝 Sala Privada", "🛠️ Painel Admin"]:
        
        # Desenha a barra lateral UMA ÚNICA VEZ para o ecossistema privado
        #with st.sidebar: 

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


            avatar_html = ""
            # ==========================================================================
            # --- PERFIL DO USUÁRIO & AVATAR NATIVO (ULTRA RÁPIDO) ---
            # ==========================================================================
            caminho_minha_foto = str(st.session_state.get("foto_perfil", "")).strip().lstrip('/')
                
            # Centralização visual usando colunas nativas para o componente do avatar
            col_avatar_centro, _ = st.columns([1, 2])
            with col_avatar_centro:
                if caminho_minha_foto and os.path.exists("/static/uploads/perfis/user_{id_do_usuario}.jpg"):
                    # O st.image lê o caminho do arquivo direto no servidor de forma instantânea
                    st.image("/static/uploads/perfis/user_{id_do_usuario}.jpg", width=65)
                else:
                    # Fallback simples usando texto/emoji nativo caso não tenha imagem cadastrada
                    st.markdown('<div style="font-size: 50px; text-align:center; padding-bottom:10px;">👩</div>', unsafe_allow_html=True)

            # Extração limpa do nome do usuário antes do '@'
            username_atual = st.session_state.get("username", "Usuário")
            nome_usuario_puro = str(username_atual).split('@')[0].capitalize()

            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 15px; margin-top: -10px;">
                    <h3 style="margin: 0; font-size: 16px; font-weight: bold; color: #f0f6fc;">{nome_usuario_puro}</h3>
                    <p style="color: #48bb78; font-weight: bold; font-size: 12px; margin: 3px 0 0 0;">🟢 Online</p>
                </div>
            """, unsafe_allow_html=True)

            # ==========================================================================
            # --- CONSULTA 1: PLANO E SALDO DE MOEDAS REAL (PROCESSO CACHED ULTRA RÁPIDO) ---
            # ==========================================================================
            tipo_plano = "Grátis"
            saldo_moedas = 0
            id_usuario_logado = st.session_state.get("usuario_id")

            if id_usuario_logado is not None:
                try:
                    # Carrega o registro direto da memória cache otimizada
                    registro_banco = carregar_plano_e_moedas_cached(id_usuario_logado)
                    
                    # Captura o plano e força uma string limpa
                    plano_bruto = str(registro_banco.get("tipo_plano", "Grátis")).strip()
                    
                    # Normalização para evitar problemas de acentuação (Crédito vs Credito)
                    plano_norm = unicodedata.normalize('NFKD', plano_bruto).encode('ASCII', 'ignore').decode('utf-8').lower()
                    
                    if "credito" in plano_norm or "moedas" in plano_norm:
                        tipo_plano = "Plano Crédito de Moedas"
                    elif "vip" in plano_norm or "assinante" in plano_norm:
                        tipo_plano = "vip"
                    else:
                        tipo_plano = "Grátis"
                        
                    saldo_moedas = int(registro_banco.get("moedas", 0) or 0)
                        
                except Exception as e:
                    st.error(f"Erro ao mapear cache de saldo: {e}")
            else:
                st.warning("⚠️ Usuário não identificado na sessão.")

            # Sincroniza de forma idêntica os estados globais da aplicação
            st.session_state["tipo_plano"] = tipo_plano
            st.session_state["saldo_moedas"] = saldo_moedas

            st.caption(f"Plano: **{tipo_plano}** | Saldo: 🪙 **{saldo_moedas} moedas**")
                        

            # ==========================================================================
            # --- COMPONENTE: ALTERAR FOTO DE PERFIL ---
            # ==========================================================================
            st.caption("📷 Enviar nova foto de perfil:")
            f_nova = st.file_uploader("Alterar Foto", type=["png","jpg","jpeg"], key="side_f_up", label_visibility="collapsed") 
            
            if f_nova and id_usuario_logado: 
                id_limpo = id_usuario_logado if isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
                
                # 1. Garante que a pasta física exista no servidor
                if not os.path.exists(UPLOAD_FOLDER): 
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True) 
                
                # 2. Salva o arquivo de imagem no disco do contêiner
                c_completo = os.path.join(UPLOAD_FOLDER, f"user_{id_limpo}.jpg") 
                with open(c_completo, "wb") as f: 
                    f.write(f_nova.getbuffer())
                
                # 3. Define o caminho padrão com a barra inicial para gravação
                caminho_banco = f"/{c_completo}"
                
                try:
                    # 4. Grava o novo caminho no banco de dados de forma estável
                    conn_foto = obter_conexao_eficiente()
                    cursor_foto = conn_foto.cursor() 
                    cursor_foto.execute("UPDATE usuarios SET foto_perfil = %s WHERE id = %s;", (caminho_banco, int(id_limpo))) 
                    conn_foto.commit()
                    cursor_foto.close()
                    
                    # 5. Atualiza a memória da sessão atual para atualizar a interface
                    st.session_state.foto_perfil = caminho_banco
                    
                    # 6. Limpa o cache da barra lateral para forçar a releitura imediata
                    st.cache_data.clear()
                    
                    st.toast("📷 Foto de perfil atualizada com sucesso!")
                    time.sleep(1)
                    st.rerun() 
                    
                except Exception as e:
                    st.error(f"Erro ao salvar caminho da foto no banco: {e}")

                    
                try:
                    conn = obter_conexao_eficiente()
                    cursor = conn.cursor() 
                    cursor.execute("UPDATE usuarios SET foto_perfil = %s WHERE id = %s", (f"/{c_completo}", int(id_limpo))) 
                    conn.commit()
                    cursor.close()
                   
                    st.session_state.foto_perfil = f"/{c_completo}"
                    st.rerun() 
                except Exception as e:
                    st.error(f"Erro ao salvar foto: {e}")

                st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)    
                
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
                    
            if st.button("Ir para a Loja 🛒", type="secondary", use_container_width=True, key="btn_ir_loja"):
                st.session_state.abrir_popup_loja = True
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
            # --- BOTÃO: ENCERRAR SESSÃO (LOGOUT) ---
            # ==========================================================================
            if st.button("🚪 ENCERRAR SESSÃO", type="primary", use_container_width=True, key="btn_logout_sistema"):
                if id_usuario_logado:
                    try:
                        id_limpo = id_usuario_logado if isinstance(id_usuario_logado, (tuple, list)) else id_usuario_logado
                        conn_logout = conectar_supabase()
                        cursor_logout = conn_logout.cursor()
                        cursor_logout.execute("UPDATE usuarios SET status = '⚫ Offline' WHERE id = %s;", (int(id_limpo),))
                        conn_logout.commit()
                        cursor_logout.close()
                       
                    except Exception: 
                        pass
                    
                # Limpeza completa dos estados de login
                st.session_state.usuario_id = None
                st.session_state.username = None
                st.session_state.opcao_menu = "login"
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

    # ==============================================================================
    # FALLBACK DE SEGURANÇA SEGURO (FIM DO ARQUIVO)
    # ==============================================================================
    else:
        # Se o menu atual não corresponder a nenhuma tela, redefine para a home 
        # e renderiza o layout visual imediatamente, quebrando loops de st.rerun()
        st.session_state.opcao_menu = "home"
        #template_home()