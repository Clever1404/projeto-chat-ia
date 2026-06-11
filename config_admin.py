import os
import streamlit as st
import psycopg

# --- SEU MÉTODO DE CONEXÃO PADRÃO ---
# Certifique-se de que a função obter_conexao() está acessível neste arquivo.
# Caso não esteja, use a linha abaixo descomentada:
# DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
# def obter_conexao(): return psycopg.connect(DB_URL)

st.title("👑 Painel de Gerenciamento de Privilégios")
st.markdown("Use esta ferramenta para adicionar suporte a administradores no banco de dados e promover usuários.")

# Entrada interativa do nome do usuário
seu_usuario = st.text_input("Username do usuário a ser promovido:", value="Clever1404", key="admin_user_input")

if st.button("🚀 Executar Atualização e Promover", type="primary"):
    if not seu_usuario.strip():
        st.warning("Por favor, digite um nome de usuário válido.")
    else:
        try:
            # Conecta ao PostgreSQL usando sua função utilitária
            conn = obter_conexao()
            cursor = conn.cursor()

            # 1. Garante que a coluna is_admin existe na tabela usuarios
            try:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;")
                conn.commit()
                st.success("🆕 Coluna 'is_admin' criada com sucesso na tabela `usuarios`!")
            except psycopg.errors.DuplicateColumn:
                conn.rollback() # Limpa o estado da transação se a coluna já existir
                st.info("ℹ️ A coluna 'is_admin' já existe no banco de dados.")

            # 2. Descobre o nome real das colunas da tabela no PostgreSQL
            cursor.execute('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'usuarios';
            ''')
            colunas = [linha[0] for linha in cursor.fetchall()]
            
            with st.expander("🔍 Detalhes Estruturais do Banco"):
                st.write("As colunas mapeadas na sua tabela são:", colunas)

            # 3. Define o usuário administrador usando marcadores %s do Postgres
            houve_atualizacao = True
            if 'username' in colunas:
                cursor.execute("UPDATE usuarios SET is_admin = TRUE WHERE username = %s;", (seu_usuario,))
            elif 'usuario' in colunas:
                cursor.execute("UPDATE usuarios SET is_admin = TRUE WHERE usuario = %s;", (seu_usuario,))
            elif 'nome' in colunas:
                cursor.execute("UPDATE usuarios SET is_admin = TRUE WHERE nome = %s;", (seu_usuario,))
            else:
                st.warning("⚠️ Nenhuma coluna de texto conhecida (username, usuario, nome) encontrada. Promovendo o ID 1...")
                cursor.execute("UPDATE usuarios SET is_admin = TRUE WHERE id = 1;")
                houve_atualizacao = False

            conn.commit()
            
            if houve_atualizacao:
                st.success(f"👑 Usuário **'{seu_usuario}'** promovido a Administrador com sucesso!")
            else:
                st.success("👑 ID 1 foi promovido a Administrador padrão.")

            cursor.close()
            conn.close()

        except Exception as e:
            st.error(f"❌ Erro ao atualizar o banco de dados: {e}")
            if 'conn' in locals() and conn:
                conn.close()
