-- 1. Garante que a extensão pgvector está ativa no banco
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Cria a tabela estruturada para os vetores do Gemini
CREATE TABLE IF NOT EXISTS embeddings_gemini (
    id SERIAL PRIMARY KEY,
    texto_original TEXT NOT NULL,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- O text-embedding-004 gera exatamente 768 números (dimensões)
    vetor vector(768) NOT NULL 
);