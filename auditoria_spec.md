# Auditoria Técnica — SPEC vs Código Fonte

Realizei um confronto rigoroso e linha-a-linha entre a especificação (`SPEC-MVP-PESADOS-ID.md`) e os arquivos do projeto. A lógica de negócio está fantástica, mas encontrei **inconsistências técnicas estruturais** e **entregáveis faltando** que impediriam o MVP de rodar em produção.

Abaixo, o relatório detalhado do que está **Errado** e do que está **Faltando**:

---

## ❌ 1. O Que Está ERRADO (Bugs e Inconsistências)

### 1.1 BUG CRÍTICO no Banco de Dados (Crash no Pipeline)
*   **A Regra (§6. Modelo de Dados):** A tabela `transacao` deve suportar os campos da Frota Instalada.
*   **O Erro:** O script SQL que está no `README-v2.md` (passo 4) **não possui** as colunas `marca`, `modelo` e `ano`. Porém, o script `ingestion_pipeline-v2.py` (linha 525) tenta inserir obrigatoriamente esses dados com um `INSERT INTO transacao (..., marca, modelo, ano)`.
*   **Consequência:** Ao rodar o pipeline conectado ao Supabase, a biblioteca `psycopg2` vai estourar um erro fatal de coluna inexistente e a ingestão vai falhar sempre.

### 1.2 Frontend Gráfico Improvisado (Saindo da Stack)
*   **A Regra (§2. Stack Recomendada):** Foi sugerido (e consta no seu `package.json` atual) a biblioteca **Recharts** para construção interativa dos gráficos de market share.
*   **O Erro:** O arquivo `App.jsx` não tem nenhum `import { BarChart, ... } from 'recharts'`. Os gráficos de barra de Market Share e do funil foram feitos "na mão" (provavelmente usando divs do tailwind).
*   **Consequência:** Fica difícil escalar o front-end, adicionar *tooltips* interativos e manter responsividade nas telas menores.

---

## ⚠️ 2. O Que Está FALTANDO (Critérios de Aceite não cumpridos)

### 2.1 Migrations Versionadas (Entregável §10.2)
*   **A Regra:** "Migrations do banco versionadas".
*   **O que falta:** O SQL está apenas dentro do `README-v2.md`. Profissionalmente, é preciso criar um diretório (ex: `supabase/migrations/`) e separar o script estrutural (ex: `001_schema_inicial.sql`) e a carga inicial (ex: `002_seed_parametros.sql`).

### 2.2 Garantia de Responsividade 390px (Critério §8.8)
*   **A Regra:** "Responsivo — testado de verdade em 390px de largura, sem overflow horizontal."
*   **O que falta:** Ao exibir dados densos (ex: A tabela da *Tela 1* com 9 colunas), se você não encapsular a tabela com uma `div` de classe `overflow-x-auto` do Tailwind, ela vai estourar a tela do celular do cliente, causando rolagem horizontal na página inteira (o que destrói a usabilidade). Preciso confirmar as classes do seu `App.jsx`.

### 2.3 Deploy e URL de Staging (Entregável §10.5)
*   **A Regra:** "Front-end publicado em URL de staging".
*   **O que falta:** O código atual está pronto para localhost. Faltam os arquivos de configuração para a nuvem. Sugiro gerarmos um `Dockerfile` e um `fly.toml` (para a API Python/FastAPI), além de avisar o Vite que o front-end irá rodar numa plataforma como Cloudflare Pages.

---

## ✅ O Que Está CERTO e Aprovado

Para sua tranquilidade, as partes mais complexas do projeto estão **perfeitas**:
*   O Rate Limit (Sleep) da API do PNCP (0.3 a 0.4s) está correto.
*   O Filtro Dinâmico de Categorias (`qtd_max`, `valor_min`) conectado ao banco está correto.
*   A Regex de Frota (extraindo marcas de manutenção) está fantástica.
*   O Tema Visual (Regra do Amarelo e Color Scheme Light) está 100% aplicado via CSS.
*   O Mock Fallback que imita o banco caso caia garante as demonstrações ao vivo.

---

### Quer que eu crie um plano de ação e corrija esses pontos automaticamente para você?
Posso consertar o schema do SQL, ajustar as tabelas do `App.jsx` para responsividade e criar as migrations agora mesmo.
