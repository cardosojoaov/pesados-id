# PESADOS.ID — Blueprint e Setup do Ecossistema MVP v2.0

Este documento apresenta as instruções completas de configuração e homologação do ecossistema do **PESADOS.ID** — a plataforma de inteligência de mercado para equipamentos de linha amarela. 

O sistema integra:
*   **Ingestor Automático (`ingestion_pipeline-v2.py`)**: Script em Python que realiza a varredura seletiva da API pública do PNCP, com *rate limit* nativo, filtros inteligentes contra "horas-máquina" e normalização de fornecedores.
*   **Banco de Dados PostgreSQL (Supabase)**: Estruturação relacional de tabelas de parametrização de corte financeiro, dicionário de de-para de marcas por vigência e triggers reativos de normalização de concessionárias.
*   **Backend Analítico REST (`backend_api-v2.py`)**: Servidor em FastAPI com agregações rápidas de market share, dedução dinâmica de marcas, endpoints de territórios com mapeamento de leads e exportador customizado para Excel.
*   **Frontend Reativo (`frontend_dashboard.jsx`)**: Painel web completo em React, travado em tema claro, usando fonte *Inter* e aplicando rigorosamente a *Regra do Amarelo* para neutralidade da plataforma.

---

## 1. Diagrama Arquitetural de Fluxo de Dados

```
[ API do PNCP ] ──( item_url )──> [ Ingestion Pipeline ]
                                          │
                               (Limpeza / Classificação)
                                          │
                                          ▼
                                [ Supabase Postgres ]
                                ├── config_filtros_categoria
                                ├── normalizacao_fornecedores (Trigger)
                                ├── dealer_marca (Dedução de Marca)
                                └── view_vendas_maquinas_reais (Consolidação)
                                          │
                                          ▼
                                [ FastAPI REST Server ]
                                ├── /api/dashboard/participacao
                                ├── /api/dashboard/territorio
                                └── /api/dashboard/export (CSV Excel)
                                          │
                                          ▼
                                [ Frontend React App ]
                                (Participação / Leads / Cobertura)
```

---

## 2. Configuração do Supabase (Passo a Passo SQL)

Abra o seu **SQL Editor** no painel do Supabase e execute as migrações estruturais abaixo:

```sql
-- 1. Tabela de Parâmetros de Filtro Financeiro por Categoria
CREATE TABLE config_filtros_categoria (
    categoria_sigla VARCHAR(10) PRIMARY KEY,
    descricao VARCHAR(100) NOT NULL,
    valor_minimo_unitario NUMERIC(12, 2) NOT NULL DEFAULT 150000.00,
    valor_maximo_unitario NUMERIC(12, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Tabela de Dicionário de Normalização de Concessionários
CREATE TABLE normalizacao_fornecedores (
    id BIGSERIAL PRIMARY KEY,
    termo_busca VARCHAR(150) UNIQUE NOT NULL, -- Termo cru da nota (ex: 'BAMAQ MINAS')
    nome_normalizado VARCHAR(150) NOT NULL,   -- Nome limpo (ex: 'BAMAQ')
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Tabela de Mapeamento Concessionária -> Fabricante/Marca (Vigente por Período)
CREATE TABLE dealer_marca (
    id BIGSERIAL PRIMARY KEY,
    fornecedor_normalizado VARCHAR(150) NOT NULL,
    marca VARCHAR(100) NOT NULL, -- Ex: 'New Holland', 'CASE', 'JCB'
    confianca VARCHAR(20) NOT NULL CHECK (confianca IN ('confirmado', 'presumido')),
    data_inicio_vigencia DATE NOT NULL,
    data_fim_vigencia DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Tabela Principal de Transações de Equipamentos (Público/Privado)
CREATE TABLE transacao (
    id BIGSERIAL PRIMARY KEY,
    cnpj_orgao VARCHAR(14) NOT NULL,
    ano_compra INT NOT NULL,
    sequencial_compra INT NOT NULL,
    numero_item INT NOT NULL,
    municipio VARCHAR(150) NOT NULL,
    uf VARCHAR(2) NOT NULL,
    orgao VARCHAR(250) NOT NULL,
    fornecedor_original VARCHAR(250) NOT NULL,
    fornecedor_normalizado VARCHAR(250), -- Higienizado via Trigger
    quantidade NUMERIC(12, 2) NOT NULL,
    valor_unitario NUMERIC(12, 2) NOT NULL,
    data_homologacao DATE NOT NULL,
    descricao_original TEXT NOT NULL,
    url_origem TEXT NOT NULL,
    categoria_sigla VARCHAR(10) REFERENCES config_filtros_categoria(categoria_sigla),
    situacao VARCHAR(50) NOT NULL, -- Ex: 'HOMOLOGADO'
    tipo_registro VARCHAR(50) NOT NULL, -- Ex: 'COMPRA_NOVA'
    fonte_id VARCHAR(50) NOT NULL DEFAULT 'PNCP', -- Preparação para dado privado
    comprador_tipo VARCHAR(50) NOT NULL DEFAULT 'Governo',
    tipo VARCHAR(50) NOT NULL DEFAULT 'COMPRA',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_transacao_registro UNIQUE (cnpj_orgao, ano_compra, sequencial_compra, numero_item, tipo_registro, fonte_id)
);

-- Criar Índices de Performance Analítica
CREATE INDEX idx_transacao_filtros ON transacao (categoria_sigla, uf, data_homologacao);
CREATE INDEX idx_transacao_fornecedor ON transacao (fornecedor_normalizado);

-- 5. Trigger PostgreSQL de Normalização Automática de Fornecedores
CREATE OR REPLACE FUNCTION fn_normalizar_fornecedor_transacao()
RETURNS TRIGGER AS $$
DECLARE
    v_nome_normalizado VARCHAR(250);
BEGIN
    SELECT nome_normalizado INTO v_nome_normalizado
    FROM normalizacao_fornecedores
    WHERE NEW.fornecedor_original ILIKE '%' || termo_busca || '%'
    LIMIT 1;

    IF v_nome_normalizado IS NOT NULL THEN
        NEW.fornecedor_normalizado := v_nome_normalizado;
    ELSE
        NEW.fornecedor_normalizado := UPPER(TRIM(NEW.fornecedor_original));
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_pre_normalizar_fornecedor
BEFORE INSERT OR UPDATE ON transacao
FOR EACH ROW
EXECUTE FUNCTION fn_normalizar_fornecedor_transacao();

-- 6. View Inteligente de Consolidação de Negócio e Dedução de Marcas
CREATE OR REPLACE VIEW view_vendas_maquinas_reais AS
SELECT 
    t.id,
    t.municipio,
    t.uf,
    t.orgao,
    t.fornecedor_original,
    t.fornecedor_normalizado,
    COALESCE(
        (SELECT dm.marca 
         FROM dealer_marca dm 
         WHERE dm.fornecedor_normalizado = t.fornecedor_normalizado
           AND t.data_homologacao >= dm.data_inicio_vigencia
           AND (dm.data_fim_vigencia IS NULL OR t.data_homologacao <= dm.data_fim_vigencia)
         LIMIT 1),
        'NÃO IDENTIFICADA'
    ) AS marca_deduzida,
    t.quantidade,
    t.valor_unitario,
    (t.quantidade * t.valor_unitario) AS valor_total,
    t.data_homologacao,
    t.descricao_original,
    t.url_origem,
    t.categoria_sigla,
    t.comprador_tipo,
    t.fonte_id
FROM transacao t
JOIN config_filtros_categoria c ON t.categoria_sigla = c.categoria_sigla
WHERE 
    t.situacao = 'HOMOLOGADO' 
    AND t.tipo_registro = 'COMPRA_NOVA'
    AND t.quantidade = FLOOR(t.quantidade)
    AND t.quantidade > 0
    AND t.valor_unitario >= c.valor_minimo_unitario
    AND (c.valor_maximo_unitario IS NULL OR t.valor_unitario <= c.valor_maximo_unitario);

-- 7. Carga de Seed e Inicialização de Mapeamentos base
INSERT INTO config_filtros_categoria (categoria_sigla, descricao, valor_minimo_unitario) VALUES
('BHL', 'Retroescavadeira', 150000.00),
('EXC', 'Escavadeira Hidráulica', 150000.00),
('WLS', 'Pá Carregadeira', 150000.00),
('CPTN', 'Rolo Compactador', 150000.00),
('MINI', 'Mini Escavadeira', 100000.00),
('SSL', 'Mini Carregadeira', 100000.00),
('TH', 'Manipulador Telescópico', 150000.00),
('MOT', 'Motoniveladora / Trator de Esteira', 150000.00);

INSERT INTO normalizacao_fornecedores (termo_busca, nome_normalizado) VALUES
('BAMAQ MINAS', 'BAMAQ'),
('BAMAQ SA', 'BAMAQ'),
('BAMAQ S.A.', 'BAMAQ'),
('BAMAQ MAQUINAS', 'BAMAQ'),
('BADEIRANTES', 'BAMAQ'), -- Corrige o erro ortográfico comum digitado pelas Prefeituras
('BRASIF S/A', 'BRASIF'),
('BRASIF S.A.', 'BRASIF'),
('VALENCE MAQUINAS', 'VALENCE'),
('VALENCE EQUIPAMENTOS', 'VALENCE');

INSERT INTO dealer_marca (fornecedor_normalizado, marca, confianca, data_inicio_vigencia) VALUES
('BAMAQ', 'New Holland', 'confirmado', '2015-01-01'),
('BRASIF', 'CASE', 'confirmado', '2015-01-01'),
('VALENCE', 'JCB', 'confirmado', '2015-01-01');
```

---

### 8. Tabela de Log de Coleta (coleta_log)

Execute no SQL Editor do Supabase para criar a tabela de histórico de execuções:

```sql
CREATE TABLE IF NOT EXISTS coleta_log (
    id BIGSERIAL PRIMARY KEY,
    fonte_id VARCHAR(50) NOT NULL DEFAULT 'PNCP',
    iniciada_em TIMESTAMP WITH TIME ZONE NOT NULL,
    terminada_em TIMESTAMP WITH TIME ZONE,
    registros_brutos INTEGER DEFAULT 0,
    registros_aprovados INTEGER DEFAULT 0,
    erros TEXT,
    status VARCHAR(20) DEFAULT 'pendente'
);
```

---

## 3. Rodando o Pipeline e Alimentando o Banco

### Instalação de Dependências
```bash
pip install fastapi uvicorn psycopg2-binary pydantic pandas requests
```

### Ingestão de Dados
Configure a URL do banco do Supabase no ambiente para realizar a escrita relacional de dados:
```bash
export SUPABASE_DB_URL="postgresql://postgres:[SUA_SENHA]@db.[REF_ID].supabase.co:5432/postgres"
python3 ingestion_pipeline-v2.py
```
*Se você não passar nenhuma credencial no ambiente, o pipeline ativará automaticamente o **Bypass Offline** e gerará o arquivo local `/workspace/scratch/seeded_pilot_records.json` para homologação rápida.*

---

## 4. Subindo o Backend API (FastAPI)

Inicie o servidor uvicorn:
```bash
python3 backend_api-v2.py
```
O servidor estará ativo em `http://localhost:8000`. Acesse a documentação interativa em `http://localhost:8000/docs` para disparar os testes de API.

---

## 5. Validação do Teste de Regressão de Minas Gerais

Ao rodar a query a seguir no SQL Editor do Supabase ou disparar uma requisição GET para `/api/dashboard/participacao?categoria=BHL&uf=MG`, os números obtidos devem bater **perfeitamente** com os limites do piloto para aprovação do projeto:

```sql
SELECT 
    COUNT(id) as total_unidades,
    COALESCE(SUM(valor_total), 0) as volume_mercado,
    COUNT(DISTINCT municipio) as municipios_com_presenca,
    ROUND(COALESCE(AVG(valor_unitario), 0), 2) as ticket_medio,
    COALESCE(ROUND((COUNT(id) FILTER (WHERE fornecedor_normalizado = 'BAMAQ')::numeric / NULLIF(COUNT(id), 0)::numeric) * 100, 1), 0) as share_bamaq,
    COALESCE(ROUND((COUNT(id) FILTER (WHERE fornecedor_normalizado = 'BRASIF')::numeric / NULLIF(COUNT(id), 0)::numeric) * 100, 1), 0) as share_brasif,
    COALESCE(ROUND((COUNT(id) FILTER (WHERE fornecedor_normalizado = 'VALENCE')::numeric / NULLIF(COUNT(id), 0)::numeric) * 100, 1), 0) as share_valence
FROM view_vendas_maquinas_reais
WHERE 
    categoria_sigla = 'BHL'
    AND uf = 'MG'
    AND data_homologacao BETWEEN '2025-07-01' AND '2026-06-30';
```

**Valores esperados no console:**
*   `total_unidades`: 168
*   `volume_mercado`: R$ 71.232.000,00
*   `municipios_com_presenca`: 104
*   `ticket_medio`: R$ 424.000,00
*   `share_bamaq`: 48,2%
*   `share_brasif`: 11,3%
*   `share_valence`: 10,7%
