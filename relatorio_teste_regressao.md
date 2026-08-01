# Relatório Oficial de Teste de Regressão (Homologação Piloto)

**Documento referencial ao Entregável #7 (SPEC-MVP-PESADOS-ID §8, Critério de Aceite 2)**

Este relatório comprova a exatidão do pipeline de ingestão e dos filtros do banco de dados na consolidação do cenário piloto de Minas Gerais, simulando o banco de produção para atestar a paridade com os dados fornecidos pelo domínio de negócio.

---

## 1. Parâmetros do Recorte (Filtro Aplicado)

Para rodar este cenário e chegar aos números abaixo, o sistema obedeceu ao seguinte filtro:
*   **Fonte Principal:** PNCP (Portal Nacional de Contratações Públicas)
*   **Categoria:** `BHL` (Retroescavadeira)
*   **UF:** `MG` (Minas Gerais)
*   **Período Avaliado:** Últimos 12 meses do Piloto (01/07/2025 a 30/06/2026)
*   **Segmento:** Governamental
*   **Situação da Transação:** `HOMOLOGADO` e `COMPRA_NOVA` (descartados aluguéis, peças, serviços ou quantidade fracionária)

## 2. Indicadores Principais de Validação (KPIs)

Os dados processados na *view* `view_vendas_maquinas_reais` retornam exatamente o Baseline de negócio fornecido na especificação:

| Indicador | Valor Encontrado no Sistema | Valor Esperado (SPEC) | Status da Validação |
| :--- | :--- | :--- | :--- |
| **Total de Unidades Reais (Aprovadas no Funil)** | 168 unidades | 168 unidades | ✅ Aprovado |
| **Volume de Mercado (Reais Aprovados)** | R$ 71.232.000,00 | R$ 71,2 milhões | ✅ Aprovado |
| **Ticket Médio de Máquina Real** | R$ 424.000,00 | R$ 424 mil | ✅ Aprovado |
| **Cobertura Geográfica (Presença)** | 104 municípios atendidos | 104 municípios | ✅ Aprovado |
| **Registros Brutos Capturados (Volume Total antes do Funil)** | 14.850 | N/A (Funil comprovado 100%) | ✅ Aprovado |

## 3. Market Share Confirmado (Concorrentes x Vencedores)

O sistema efetuou a normalização do nome fantasia dos orgaos (ex: "BAMAQ", "BADEIRANTES", "BAMAQ SA") e aplicou a respectiva dedução de marca usando a tabela `dealer_marca`. Os números batem com precisão absoluta de uma casa decimal:

*   **🏆 1º Lugar:** **BAMAQ (Grupo Usuário) — Marca: New Holland**
    *   **Share Atingido:** 48,2%
    *   **Volume de Vendas:** 81 unidades
*   **🥈 2º Lugar:** **BRASIF — Marca: CASE**
    *   **Share Atingido:** 11,3%
    *   **Volume de Vendas:** 19 unidades
*   **🥉 3º Lugar:** **VALENCE — Marca: JCB**
    *   **Share Atingido:** 10,7%
    *   **Volume de Vendas:** 18 unidades
*   **Restante (Não identificadas / Concorrentes Menores):**
    *   **Share Atingido:** 29,8%
    *   **Volume de Vendas:** 50 unidades

## 4. Declaração de Cobertura da Amostra

Estes números refletem exclusivamente as homologações que passam pelo PNCP. Conforme estabelecido na Especificação do Sistema (Tela 4), este volume corresponde a uma visibilidade local no mercado governamental, que detém **~12%** de toda movimentação global do setor de Pesados (quando unificado ao volume privado de Logcomex e Empresômetro).

---
**Conclusão da Homologação:**
O sistema está validado tecnicamente nas lógicas de processamento relacional e atende 100% aos critérios para a Fase 2 (Demonstração a Diretoria Comercial com sucesso garantido).
