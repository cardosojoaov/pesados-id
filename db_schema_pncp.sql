-- Estrutura de banco de dados para a Solução PESADOS.ID (Fase 4+)
-- Preparado para Multi-fontes (PNCP, Empresômetro, Logcomex)

-- 1. Fonte de Dados
CREATE TABLE IF NOT EXISTS fonte (
    id VARCHAR(50) PRIMARY KEY, -- 'PNCP', 'EMPRESOMETRO', 'LOGCOMEX'
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    ativo BOOLEAN DEFAULT TRUE
);
INSERT INTO fonte (id, nome) VALUES ('PNCP', 'Portal Nacional de Contratações Públicas') ON CONFLICT DO NOTHING;

-- 2. Tabela de parâmetros por categoria (Limites para COMPRA_NOVA)
CREATE TABLE IF NOT EXISTS config_filtros_categoria (
    categoria_sigla VARCHAR(50) PRIMARY KEY,
    descricao VARCHAR(255) NOT NULL,
    valor_minimo_unitario DECIMAL(15,2) NOT NULL,
    valor_maximo_unitario DECIMAL(15,2),
    qtd_max INTEGER NOT NULL DEFAULT 10,
    ativo BOOLEAN DEFAULT TRUE,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO config_filtros_categoria (categoria_sigla, descricao, valor_minimo_unitario, valor_maximo_unitario, qtd_max)
VALUES 
    ('BHL', 'Retroescavadeira', 150000, 900000, 10),
    ('EXC', 'Escavadeira Hidráulica', 300000, 1500000, 10),
    ('WLS', 'Pá Carregadeira', 150000, 1000000, 10),
    ('CPTN', 'Rolo Compactador', 150000, 800000, 10),
    ('MINI', 'Mini Escavadeira', 100000, 250000, 10),
    ('SSL', 'Mini Carregadeira', 100000, 250000, 10),
    ('TH', 'Manipulador Telescópico', 150000, 800000, 10),
    ('MOT', 'Motoniveladora / Trator de Esteira', 150000, 2500000, 10)
ON CONFLICT (categoria_sigla) DO NOTHING;

-- 3. Tabela de normalização de fornecedores (Usada para Admin / Ingestão)
CREATE TABLE IF NOT EXISTS normalizacao_fornecedores (
    id SERIAL PRIMARY KEY,
    termo_busca VARCHAR(100) UNIQUE NOT NULL,
    nome_normalizado VARCHAR(255) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE
);

INSERT INTO normalizacao_fornecedores (termo_busca, nome_normalizado)
VALUES 
    ('BAMAQ', 'BAMAQ'),
    ('BANDEIRANTES', 'BAMAQ'),
    ('BRASIF', 'BRASIF'),
    ('VALENCE', 'VALENCE'),
    ('TRIAMA', 'TRIAMA NORTE'),
    ('CENTRO OESTE', 'CENTRO OESTE'),
    ('XCMG', 'XCMG BRASIL')
ON CONFLICT (termo_busca) DO NOTHING;

-- 4. Tabela de dedução de Marca pelo Dealer (Dealer -> Marca)
CREATE TABLE IF NOT EXISTS dealer_marca (
    id SERIAL PRIMARY KEY,
    fornecedor_normalizado VARCHAR(255) NOT NULL,
    marca VARCHAR(100) NOT NULL,
    confianca VARCHAR(50) DEFAULT 'confirmado', -- confirmado, presumido
    data_inicio_vigencia DATE DEFAULT CURRENT_DATE,
    data_fim_vigencia DATE,
    UNIQUE (fornecedor_normalizado, marca)
);

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

-- 5. Tabela de Transações Central Unificada
CREATE TABLE IF NOT EXISTS transacao (
    id SERIAL PRIMARY KEY,
    fonte_id VARCHAR(50) REFERENCES fonte(id),
    cnpj_orgao VARCHAR(20),
    ano_compra INTEGER,
    sequencial_compra INTEGER,
    numero_item INTEGER,
    municipio VARCHAR(100),
    uf VARCHAR(2),
    orgao VARCHAR(255),
    fornecedor_original VARCHAR(255),
    fornecedor_normalizado VARCHAR(255),
    marca_deduzida VARCHAR(100),
    quantidade DECIMAL(10,2),
    valor_unitario DECIMAL(15,2),
    data_homologacao DATE,
    descricao_original TEXT,
    url_origem TEXT,
    categoria_sigla VARCHAR(50) REFERENCES config_filtros_categoria(categoria_sigla),
    situacao VARCHAR(50),
    tipo_registro VARCHAR(50), -- LOCACAO, PECAS_MANUTENCAO, COMPRA_NOVA, INDEFINIDO
    comprador_tipo VARCHAR(50), -- Governo, Privado
    tipo VARCHAR(50), -- COMPRA, VENDA
    marca VARCHAR(100), -- Extraído da Frota
    modelo VARCHAR(100), -- Extraído da Frota
    ano VARCHAR(20), -- Extraído da Frota
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cnpj_orgao, ano_compra, sequencial_compra, numero_item, tipo_registro, fonte_id)
);

-- Migração de compatibilidade caso a tabela transacao já existisse previamente
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS fonte_id VARCHAR(50);
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS fornecedor_normalizado VARCHAR(255);
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS marca_deduzida VARCHAR(100);
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS comprador_tipo VARCHAR(50);
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS tipo VARCHAR(50);
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS marca VARCHAR(100);
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);
ALTER TABLE transacao ADD COLUMN IF NOT EXISTS ano VARCHAR(20);

-- Trigger para dedução automática da marca baseada no fornecedor_normalizado
CREATE OR REPLACE FUNCTION deduzir_marca()
RETURNS trigger AS $$
BEGIN
    IF NEW.fornecedor_normalizado IS NOT NULL AND (NEW.marca_deduzida IS NULL OR NEW.marca_deduzida = '' OR NEW.marca_deduzida = 'NÃO SE APLICA') THEN
        SELECT marca INTO NEW.marca_deduzida
        FROM dealer_marca
        WHERE fornecedor_normalizado = NEW.fornecedor_normalizado
          AND (data_fim_vigencia IS NULL OR CURRENT_DATE <= data_fim_vigencia)
        ORDER BY CASE WHEN confianca = 'confirmado' THEN 1 ELSE 2 END
        LIMIT 1;
        
        IF NEW.marca_deduzida IS NULL THEN
            NEW.marca_deduzida := 'NÃO IDENTIFICADA';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_deduzir_marca ON transacao;
CREATE TRIGGER trigger_deduzir_marca
BEFORE INSERT OR UPDATE ON transacao
FOR EACH ROW
EXECUTE FUNCTION deduzir_marca();

-- 6. Log de Coletas (Transações Automatizadas)
CREATE TABLE IF NOT EXISTS coleta_log (
    id SERIAL PRIMARY KEY,
    fonte_id VARCHAR(50) REFERENCES fonte(id),
    iniciada_em TIMESTAMP,
    terminada_em TIMESTAMP,
    registros_brutos INTEGER,
    registros_aprovados INTEGER,
    erros TEXT,
    status VARCHAR(50)
);

-- 7. View Inteligente de Consolidação (Mantém retrocompatibilidade)
DROP VIEW IF EXISTS view_vendas_maquinas_reais CASCADE;

CREATE OR REPLACE VIEW view_vendas_maquinas_reais AS
SELECT 
    t.id,
    t.municipio,
    t.uf,
    t.orgao,
    t.fornecedor_original,
    t.fornecedor_normalizado,
    t.marca_deduzida,
    t.quantidade,
    t.valor_unitario,
    (t.quantidade * t.valor_unitario) AS valor_total,
    t.data_homologacao,
    t.descricao_original,
    t.url_origem,
    t.categoria_sigla,
    t.comprador_tipo
FROM transacao t
LEFT JOIN config_filtros_categoria c ON t.categoria_sigla = c.categoria_sigla
WHERE UPPER(t.situacao) = 'HOMOLOGADO' 
  AND t.tipo_registro = 'COMPRA_NOVA'
  AND (t.fonte_id = 'PNCP' OR t.fonte_id IS NULL)
  AND (c.categoria_sigla IS NULL OR (
      t.valor_unitario >= c.valor_minimo_unitario
      AND (c.valor_maximo_unitario IS NULL OR t.valor_unitario <= c.valor_maximo_unitario)
      AND t.quantidade <= c.qtd_max
  ));
