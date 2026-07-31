# PESADOS.ID — ESPECIFICAÇÃO TÉCNICA DO MVP
### Documento mestre para desenvolvimento
**BPA Ventures · v1.0 · 27/07/2026**

---

## 0. LEIA ISTO PRIMEIRO

**O que é o produto:** plataforma de inteligência de mercado para equipamento pesado (linha amarela). Máquina pesada não tem emplacamento no Brasil — logo, nenhum fabricante ou concessionária sabe a própria participação de mercado. A plataforma reconstrói esse share cruzando fontes públicas e privadas.

**O que é este MVP:** uma aplicação web que ingere dados de compra pública (PNCP), normaliza, deduz marca por concessionária e apresenta share por marca/dealer/região/período, com metodologia e cobertura declaradas.

**O que este MVP NÃO é:** não é a plataforma completa. As camadas de dado privado (nota fiscal e importação) estão em negociação comercial e **não devem ser implementadas agora** — apenas preparadas por contrato de interface (ver §7).

**Princípio inegociável do produto:** *honestidade sobre cobertura*. Todo número exibido carrega a fonte, o recorte e a fatia de mercado que enxerga. O produto compete com relatórios setoriais opacos; a credibilidade É o diferencial. Nunca arredondar amostra para censo, nunca esconder limite.

---

## 1. ESCOPO DO MVP

### 1.1 Dentro do escopo
- Pipeline de ingestão do PNCP (coleta, classificação, limpeza, normalização)
- Banco de dados com modelo preparado para múltiplas fontes
- Painel web autenticado com 4 telas (§5)
- Motor de dedução de marca via tabela de-para fornecedor→marca (editável)
- Exportação CSV/XLSX
- Declaração de cobertura visível em toda tela

### 1.2 Fora do escopo (não construir)
- Ingestão de NF-e / Empresômetro (fonte não contratada)
- Ingestão de importação / Logcomex (fonte não contratada)
- Multi-tenant com billing/assinatura (venda é consultiva no início)
- App mobile nativo (responsivo basta)
- Alertas por e-mail/push (v2)
- API pública para cliente (v2)

### 1.3 Definição de pronto
O MVP está pronto quando um diretor comercial de OEM consegue, sozinho, responder: *"qual meu share de retroescavadeira em Minas Gerais nos últimos 12 meses, contra quais concorrentes, em quais municípios eu não apareço?"* — e ver de onde veio cada número.

---

## 2. STACK RECOMENDADA

Sugestão, não imposição. O dev pode propor alternativa justificando.

| Camada | Escolha | Motivo |
|---|---|---|
| Banco | **PostgreSQL** (Supabase ou Neon) | Volume cresce rápido (nacional = centenas de milhares de linhas); precisa de agregação eficiente. Não usar Airtable/planilha aqui. |
| Ingestão | **Python 3.11+** (requests, pandas, psycopg) | Scripts de referência já existem em Python (§4.1) |
| Agendamento | Cron / GitHub Actions / Supabase Edge Function | Coleta diária ou semanal |
| API | **FastAPI** (Python) ou rotas do Supabase | Mesma linguagem da ingestão reduz atrito |
| Front | **React + Vite**, Tailwind, Recharts | Interatividade de filtros e gráficos justifica React |
| Auth | Supabase Auth (e-mail/senha) | MVP com poucos usuários |
| Deploy | Cloudflare Pages (front) + Fly.io/Render (API) | Padrão já usado na BPA |

**Fonte tipográfica obrigatória: Inter.** Não substituir.

---

## 3. IDENTIDADE VISUAL

```css
--obsidiana:  #111111   /* texto, barras primárias */
--off-white:  #F8F6F1   /* fundo da aplicação */
--branco:     #FFFFFF   /* cards */
--sinal:      #E8B21C   /* amarelo — SOMENTE acento funcional */
--ink-70:     #37373a   /* texto secundário */
--ink-45:     #6c6a63   /* labels */
--ink-25:     #a9a69c   /* texto terciário */
--linha:      #e4e0d5   /* bordas */
--positivo:   #1f7a4d   /* variação positiva */
--negativo:   #b3261e   /* variação negativa */
--alerta:     #9a5b1a   /* entrante, atenção */
```

**Regra do amarelo:** usar apenas em número que mudou, alerta e destaque de marca do usuário. Nunca como cor de fundo ou identidade dominante — a plataforma precisa parecer neutra (vende o número que diz quem está ganhando; não pode ter camisa de marca).

**Regra de tema:** travar tema claro. Incluir `<meta name="color-scheme" content="light">` e `color-scheme: light only` no `:root`. Alguns webviews forçam dark mode e quebram o layout.

**Referência visual pronta:** os arquivos `plataforma-pesados-id.html` e `index.html` (anexos do projeto) contêm o mockup navegável e a landing page. Usar como referência de layout, espaçamento e hierarquia — **mas os dados neles são ilustrativos**.

---

## 4. PIPELINE DE DADOS — PNCP

### 4.1 Scripts de referência existentes
Já validados em produção, entregar ao dev como ponto de partida:
- `pncp_v4_share_e_frota.py` — coleta e classificação
- `pncp_v5_limpeza_share.py` — filtro de máquina real
- `pncp_v6_normalizacao.py` — normalização de fornecedor

O dev deve **refatorar isto em serviço agendado com escrita no banco**, não rodar como notebook.

### 4.2 Coleta
**Endpoint que funciona (o único):**
```
GET https://pncp.gov.br/api/search/
  ?q={termo}&tipos_documento=edital&ordenacao=-data
  &pagina={n}&tam_pagina=100&status=todos&ufs={UF}

Headers obrigatórios:
  User-Agent: Mozilla/5.0 (...) Chrome/120.0 Safari/537.36
  Referer: https://pncp.gov.br/app/editais
```
Retorna `{items, total}`. Cada item traz `item_url` = `/compras/{cnpj}/{ano}/{seq}`.

**Detalhamento:**
```
GET https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens
GET .../itens/{numeroItem}/resultados
```

**Termos de busca (por categoria):** retroescavadeira, escavadeira hidráulica, pá carregadeira, motoniveladora, rolo compactador, trator de esteira, minicarregadeira, manipulador telescópico.

### 4.3 Armadilhas confirmadas — respeitar todas
1. `/contratacoes/publicacao` limita janela a 1 ano → HTTP 422. **Não usar esse endpoint.**
2. O termo do produto está no **item**, não no `objetoCompra`. Varrer por objeto retorna zero ou 3.000 falsos positivos.
3. O endpoint `resultados` **não retorna marca**. Marca vem por dedução (§4.5).
4. Contrato de serviço contamina a base: "hora-máquina de retroescavadeira" aparece como aquisição, com quantidades como 250,60 e fornecedores que são construtoras.
5. Razão social vem suja: **BAMAQ apareceu em 14 grafias diferentes**, incluindo erro de digitação do próprio órgão ("BADEIRANTES").
6. Rate limit: manter `sleep` de 0,3–0,4s entre chamadas.

### 4.4 Regras de classificação e limpeza

**Classificar cada registro em 4 tipos** (regex sobre a descrição):
```
LOCACAO           → LOCA[ÇC][ÃA]O|ALUGUEL|HORA\s*M[ÁA]QUINA|COM\s*OPERADOR
PECAS_MANUTENCAO  → PE[ÇC]A|MANUTEN|REVIS[ÃA]O|PNEU|REPARO|TURBINA|FILTRO|[ÓO]LEO|BATERIA
COMPRA_NOVA       → AQUISI[ÇC][ÃA]O|COMPRA|ZERO\s*HORA|NOVA\s*DE\s*F[ÁA]BRICA|NOVO
INDEFINIDO        → nenhum dos acima
```

**Filtro de máquina real** (aplicar sobre COMPRA_NOVA + situação HOMOLOGADO):
```
valor_unitario_homologado ENTRE 150.000 E 900.000
E quantidade_homologada <= 10
```
Estes limites devem ser **configuráveis por categoria** (escavadeira grande passa de R$ 900 mil; minicarregadeira fica abaixo de R$ 150 mil). Guardar em tabela de parâmetros, não hardcoded.

**Normalização de fornecedor:** aplicar match por palavra-chave ANTES de qualquer agregação.
```
BAMAQ|BANDEIRANTES → "BAMAQ"
BRASIF             → "BRASIF"
VALENCE            → "VALENCE"
TRIAMA             → "TRIAMA NORTE"
CENTRO\s*OESTE     → "CENTRO OESTE"
XCMG               → "XCMG BRASIL"
... (lista completa no script v6)
```
A tabela de normalização deve ser **editável pela interface admin** — novos dealers aparecem o tempo todo.

### 4.5 Dedução de marca (crítico)
A API não entrega marca. Como concessionária é exclusiva por marca, o **fornecedor entrega a marca**:
```
VALENCE → JCB
XCMG BRASIL → XCMG (venda direta, sem dealer)
BAMAQ → [a preencher]
BRASIF → [a preencher]
...
```
**Requisito:** tabela `dealer_marca` editável na interface admin, com campo de confiança (confirmado / presumido) e data de vigência (dealer troca de marca).

Quando a marca não for dedutível, exibir `NÃO IDENTIFICADA` — **nunca chutar**. A porcentagem de registros sem marca é um número que aparece na tela de cobertura.

### 4.6 Frota instalada (segunda fonte, mesmo pipeline)
Registros classificados como `PECAS_MANUTENCAO` frequentemente citam a marca da máquina no texto ("revisão da retroescavadeira New Holland B95B ano 2018"). Extrair marca, modelo e ano por regex + dicionário de marcas. Isso alimenta a tela de Frota Instalada e serve como **validação cruzada independente** do share de venda.

---

## 5. TELAS DO MVP

Layout de referência: `plataforma-pesados-id.html` (anexo).

### Estrutura comum a todas
- Barra superior: logo, identificação da conta, marca do usuário
- **Barra de filtros global:** Categoria · UF/Região · Período · Segmento (governo/privado)
- **Rodapé de cobertura, sempre visível:** *"Fonte: PNCP · X processos analisados · cobertura estimada Y% da compra pública · período Z"*

### Tela 1 — Participação
- 4 KPIs: seu share, mercado total (unidades), ticket médio, municípios com presença / total
- Barra horizontal: share por marca, com variação vs período anterior; marca do usuário destacada em amarelo
- Barra horizontal: share por concessionária (útil quando o de-para de marca está incompleto)
- Tabela detalhada exportável: município, órgão, fornecedor, marca, quantidade, valor unitário, data

### Tela 2 — Território
- Ranking de regiões/municípios por volume, com share do usuário em cada
- Destaque para municípios com compra registrada e **zero** presença do usuário (oportunidade)
- Mapa é desejável, não obrigatório no MVP (lista ordenada resolve)

### Tela 3 — Frota Instalada
- Share por marca da frota identificada via licitação de peças
- Lista: município, marca, modelo, ano estimado, última manutenção registrada
- Nota metodológica explícita: *"reconstruída a partir de licitações de peça e manutenção"*

### Tela 4 — Metodologia e Cobertura
**Esta tela é obrigatória e é diferencial de produto.** Deve conter:
- Fonte de cada camada de dado
- Funil de processamento com números reais: registros brutos → classificados → com adjudicação → aprovados no filtro
- Cobertura declarada por categoria e por UF
- Limitações conhecidas, escritas em português claro
- Data da última atualização

### Tela Admin (interna, não para cliente)
- Editar tabela de normalização de fornecedores
- Editar de-para dealer→marca
- Editar parâmetros de filtro por categoria
- Disparar coleta manual e ver log da última execução
- Revisar registros marcados como `INDEFINIDO` ou `NÃO IDENTIFICADA`

---

## 6. MODELO DE DADOS (sugestão)

```sql
-- Fonte de cada registro (preparado para múltiplas fontes)
fonte (
  id, nome,               -- 'PNCP', 'NFE', 'IMPORTACAO'
  tipo,                   -- 'publica' | 'privada'
  cobertura_estimada,     -- % declarado
  ultima_atualizacao
)

-- Transação normalizada — o coração do modelo
transacao (
  id,
  fonte_id            REFERENCES fonte,
  id_externo,                 -- id do PNCP, ou id da NF quando existir
  data_transacao      DATE,
  tipo                TEXT,   -- COMPRA_NOVA | PECAS | LOCACAO | INDEFINIDO
  categoria_id        REFERENCES categoria,
  comprador_nome      TEXT,
  comprador_cnpj      TEXT,
  comprador_tipo      TEXT,   -- GOVERNO | CONSTRUTORA | LOCADORA | MINERADORA | AGRO
  municipio           TEXT,
  uf                  CHAR(2),
  fornecedor_bruto    TEXT,   -- razão social como veio (auditoria)
  fornecedor_id       REFERENCES fornecedor,
  marca_id            REFERENCES marca,
  marca_origem        TEXT,   -- 'dealer' | 'texto' | 'declarada' | null
  modelo              TEXT,
  quantidade          NUMERIC,
  valor_unitario      NUMERIC,
  valor_total         NUMERIC,
  situacao            TEXT,   -- HOMOLOGADO | SEM_RESULTADO
  descricao_original  TEXT,   -- sempre guardar o texto cru
  url_origem          TEXT    -- rastreabilidade até o documento
)

fornecedor (
  id, nome_normalizado, cnpj, grafias_conhecidas TEXT[]
)

marca (
  id, nome, fabricante, pais_origem, importador BOOLEAN
)

dealer_marca (
  fornecedor_id, marca_id,
  confianca TEXT,          -- 'confirmado' | 'presumido'
  vigencia_inicio, vigencia_fim
)

categoria (
  id, nome,                -- 'Retroescavadeira'
  sigla,                   -- 'BHL' (padrão do setor: BHL, EXC, WLS, CPTN, MINI, SSL, TH)
  termos_busca TEXT[],
  ncm TEXT[],
  valor_min, valor_max, qtd_max   -- parâmetros do filtro
)

coleta_log (
  id, fonte_id, iniciada_em, terminada_em,
  registros_brutos, registros_aprovados, erros, status
)
```

**Requisito de auditoria:** toda transação guarda `descricao_original` e `url_origem`. Se um cliente questionar um número, é preciso chegar ao documento de origem em um clique.

**Taxonomia do setor (usar estas siglas):** BHL retroescavadeira · EXC escavadeira · WLS carregadeira · CPTN rolo compactador · MINI mini escavadeira · SSL mini carregadeira · TH manipulador telescópico. Segmentos: Construção, Locação, Agricultura, Governo, Indústria, Mineração, Florestal.

---

## 7. PREPARAÇÃO PARA FONTES PRIVADAS (não implementar agora)

Duas fontes estão em negociação. O dev **não deve construir a ingestão**, mas deve garantir que o modelo aceite:

**Fonte NF-e (Empresômetro):** dado transacional privado, entregue como planilha mensal de dezenas de milhares de linhas, mal filtrada. Semeada por CNPJ. Trará comprador privado (construtora, locadora, mineradora). Mapeia para o mesmo `transacao`, com `fonte_id` diferente e `comprador_tipo` preenchido.

**Fonte Importação (Logcomex):** importador (CNPJ/razão), NCM, país de origem, FOB, UF de desembaraço, quantidade, marca/modelo quando disponível. Defasagem de 30 dias. Mapeia para `transacao` com `tipo = IMPORTACAO`.

**Requisito de arquitetura:** o motor de agregação deve calcular share **por combinação de fontes selecionadas**, e a cobertura declarada muda conforme as fontes ativas. Nunca somar cegamente fontes que se sobrepõem — a mesma máquina pode aparecer na importação e depois na venda. Prever campo de deduplicação e, no MVP, manter as fontes em visões separadas.

---

## 8. CRITÉRIOS DE ACEITE

O MVP é aprovado quando:

1. **Ingestão** — coleta agendada roda sozinha, popula o banco, registra log com contagens e não duplica registros em execuções repetidas.
2. **Reprodução do piloto** — filtrando retroescavadeira + MG + período do piloto, o sistema reproduz os números já validados: **168 unidades, R$ 71,2 milhões, 104 municípios, ticket médio R$ 424 mil**; share BAMAQ 48,2% · BRASIF 11,3% · VALENCE 10,7%. *Este é o teste de regressão principal.*
3. **Normalização** — nenhum grupo aparece duplicado por grafia. Teste: buscar "BAMAQ" e confirmar consolidação das 14 variações.
4. **Filtro de serviço** — nenhum registro com quantidade fracionária ou valor unitário abaixo de R$ 150 mil aparece como venda de máquina.
5. **Rastreabilidade** — qualquer linha da tabela permite abrir o documento de origem no PNCP.
6. **Cobertura visível** — nenhuma tela exibe número sem a declaração de fonte e cobertura.
7. **Admin funcional** — editar o de-para dealer→marca reflete no share em tempo real, sem redeploy.
8. **Responsivo** — testado de verdade em 390px de largura, sem overflow horizontal. Validar com Playwright/Chromium, não só no navegador redimensionado.
9. **Exportação** — CSV e XLSX íntegros, com as mesmas colunas da tela.

---

## 9. PLANO DE TESTE

**Teste de dado (o mais importante).** Rodar a ingestão e comparar com o piloto já validado (critério 2). Divergência acima de 5% precisa de explicação antes do aceite.

**Teste de sujeira.** Injetar propositalmente: contrato de hora-máquina, licitação de peças, fornecedor com grafia nova, item sem resultado publicado. O sistema deve classificar corretamente ou marcar para revisão — nunca contar como venda.

**Teste de carga.** Rodar coleta nacional (27 UFs, 8 categorias). Estimativa: 200–500 mil registros brutos. A agregação da tela principal deve responder em menos de 2 segundos.

**Teste de regressão de coleta.** Rodar a ingestão duas vezes seguidas e confirmar que a segunda não duplica nem altera contagens.

**Teste de interface.** Fluxo completo em 390px e em desktop: filtrar → ler share → exportar → abrir documento de origem.

---

## 10. ENTREGÁVEIS

1. Repositório Git com README de setup (variáveis de ambiente, migrations, seed)
2. Migrations do banco versionadas
3. Serviço de ingestão com agendamento configurado
4. API documentada (OpenAPI/Swagger)
5. Front-end publicado em URL de staging
6. Painel admin funcional
7. Relatório do teste de regressão (critério 2) com os números obtidos
8. Documentação de como adicionar uma nova categoria e uma nova fonte

---

## 11. FASEAMENTO SUGERIDO

| Fase | Entrega | Aceite |
|---|---|---|
| 1 | Banco + ingestão PNCP + normalização + de-para | Reproduz os 168 registros do piloto via SQL |
| 2 | API + Tela 1 (Participação) + filtros | Diretor consegue ver share de retro/MG sozinho |
| 3 | Telas 2, 3 e 4 + exportação | Fluxo completo navegável |
| 4 | Admin + coleta nacional + responsivo | Todos os critérios de §8 |

Fases 1 e 2 já constituem produto demonstrável para cliente. Priorizar.

---

## 12. CONTEXTO DE NEGÓCIO (para o dev entender as decisões)

- **Por que a tela de metodologia importa tanto:** o comprador é um diretor que conhece o mercado dele. Ele vai testar o número contra o que já sabe. Se encontrar erro escondido, perdemos o cliente. Se o limite estiver declarado antes dele perguntar, ganhamos credibilidade.
- **Por que o de-para é editável:** essa informação não existe em base nenhuma. Está no conhecimento de quem viveu o setor. O sistema precisa absorver conhecimento humano, não só dado automático.
- **Por que a taxonomia BHL/EXC/WLS:** é o padrão que o setor já usa nos relatórios de associação. Falar a língua do cliente reduz atrito de adoção a zero.
- **Por que compra pública sendo que o alvo é o privado:** a compra pública é ~12% do mercado, mas é o único dado aberto, granular e gratuito. Ele prova o método e sustenta a primeira venda enquanto as fontes privadas são contratadas.
- **Achado que vende:** a XCMG vende direto para prefeituras a R$ 300 mil, 31% abaixo da média de mercado, e já aparece na frota instalada de 16 municípios em MG — sem constar em nenhuma estatística de associação, porque importador raramente é associado. A plataforma torna visível quem é invisível.

---

## 13. CONTATO E DECISÕES

Dúvidas de escopo ou de regra de negócio devem ser levadas ao Davi antes de implementar solução alternativa. Especialmente:
- Mudança de stack
- Qualquer decisão que envolva "chutar" dado faltante
- Alteração dos parâmetros de filtro de máquina real
