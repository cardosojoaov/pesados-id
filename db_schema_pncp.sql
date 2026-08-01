-- Estrutura de banco de dados para o Pipeline PNCP

-- 1. Tabela de transações (compras do PNCP)
CREATE TABLE IF NOT EXISTS transacao_pncp (
    id SERIAL PRIMARY KEY,
    cnpj_orgao VARCHAR(20) NOT NULL,
    ano_compra INTEGER NOT NULL,
    sequencial_compra INTEGER NOT NULL,
    numero_item INTEGER NOT NULL,
    municipio VARCHAR(100),
    uf VARCHAR(2),
    orgao VARCHAR(255),
    fornecedor_original VARCHAR(255),
    quantidade DECIMAL(10,2),
    valor_unitario DECIMAL(15,2),
    data_homologacao DATE,
    descricao_original TEXT,
    url_origem TEXT,
    categoria_sigla VARCHAR(50),
    situacao VARCHAR(50),
    tipo_registro VARCHAR(50), -- LOCACAO, PECAS_MANUTENCAO, COMPRA_NOVA, INDEFINIDO
    fornecedor_normalizado VARCHAR(255),
    marca_deduzida VARCHAR(100),
    maquina_marca VARCHAR(100), -- Extraido da frota
    maquina_modelo VARCHAR(100), -- Extraido da frota
    maquina_ano INTEGER, -- Extraido da frota
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cnpj_orgao, ano_compra, sequencial_compra, numero_item)
);

-- 2. Tabela de parâmetros por categoria (Limites para COMPRA_NOVA)
CREATE TABLE IF NOT EXISTS pncp_parametros (
    id SERIAL PRIMARY KEY,
    categoria_sigla VARCHAR(50) UNIQUE NOT NULL,
    valor_unitario_min DECIMAL(15,2) NOT NULL,
    valor_unitario_max DECIMAL(15,2) NOT NULL,
    quantidade_max INTEGER NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inserir alguns exemplos baseados na especificação
INSERT INTO pncp_parametros (categoria_sigla, valor_unitario_min, valor_unitario_max, quantidade_max)
VALUES 
    ('retroescavadeira', 150000, 900000, 10),
    ('escavadeira', 300000, 1500000, 10),
    ('minicarregadeira', 100000, 400000, 10)
ON CONFLICT (categoria_sigla) DO NOTHING;

-- 3. Tabela de normalização de fornecedores
CREATE TABLE IF NOT EXISTS fornecedor_normalizacao (
    id SERIAL PRIMARY KEY,
    palavra_chave VARCHAR(100) UNIQUE NOT NULL,
    nome_normalizado VARCHAR(255) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE
);

-- Inserir os exemplos da especificação
INSERT INTO fornecedor_normalizacao (palavra_chave, nome_normalizado)
VALUES 
    ('BAMAQ', 'BAMAQ'),
    ('BANDEIRANTES', 'BAMAQ'),
    ('BRASIF', 'BRASIF'),
    ('VALENCE', 'VALENCE'),
    ('TRIAMA', 'TRIAMA NORTE'),
    ('CENTRO OESTE', 'CENTRO OESTE'),
    ('XCMG', 'XCMG BRASIL')
ON CONFLICT (palavra_chave) DO NOTHING;

-- 4. Tabela de dedução de Marca pelo Dealer
CREATE TABLE IF NOT EXISTS dealer_marca (
    id SERIAL PRIMARY KEY,
    fornecedor_normalizado VARCHAR(255) NOT NULL,
    marca VARCHAR(100) NOT NULL,
    confianca VARCHAR(50) DEFAULT 'confirmado', -- confirmado, presumido
    data_inicio_vigencia DATE DEFAULT CURRENT_DATE,
    data_fim_vigencia DATE,
    UNIQUE (fornecedor_normalizado, marca)
);

-- Inserir os exemplos da especificação (usando NOT EXISTS já que a tabela não tem UNIQUE constraint)
INSERT INTO dealer_marca (fornecedor_normalizado, marca, confianca, data_inicio_vigencia)
SELECT * FROM (VALUES 
    ('VALENCE', 'JCB', 'confirmado', CURRENT_DATE),
    ('XCMG BRASIL', 'XCMG', 'confirmado', CURRENT_DATE),
    ('BAMAQ', 'NEW HOLLAND', 'presumido', CURRENT_DATE),
    ('BRASIF', 'CASE', 'presumido', CURRENT_DATE)
) AS t(f, m, c, d)
WHERE NOT EXISTS (
    SELECT 1 FROM dealer_marca dm 
    WHERE dm.fornecedor_normalizado = t.f AND dm.marca = t.m
);

-- 5. View Inteligente de Consolidação (Faz a ponte com o Backend)
DROP VIEW IF EXISTS view_vendas_maquinas_reais CASCADE;

CREATE VIEW view_vendas_maquinas_reais AS
SELECT 
    id,
    municipio,
    uf,
    orgao,
    fornecedor_original,
    fornecedor_normalizado,
    marca_deduzida,
    quantidade,
    valor_unitario,
    (quantidade * valor_unitario) AS valor_total,
    data_homologacao,
    descricao_original,
    url_origem,
    CASE 
        WHEN categoria_sigla ILIKE 'retroescavadeira%' THEN 'BHL'
        WHEN categoria_sigla ILIKE 'escavadeira%' THEN 'EXC'
        WHEN categoria_sigla ILIKE 'pá carregadeira%' THEN 'WLS'
        WHEN categoria_sigla ILIKE 'rolo compactador%' THEN 'CPTN'
        WHEN categoria_sigla ILIKE 'minicarregadeira%' THEN 'SSL'
        WHEN categoria_sigla ILIKE 'manipulador telescópico%' THEN 'TH'
        ELSE UPPER(categoria_sigla)
    END AS categoria_sigla,
    'Governo' AS comprador_tipo
FROM transacao_pncp
WHERE situacao = 'HOMOLOGADO' 
  AND tipo_registro = 'COMPRA_NOVA';

