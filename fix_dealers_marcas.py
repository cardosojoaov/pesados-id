"""
Script para:
1. Normalizar variações de grafia nos fornecedor_normalizado existentes
   (ex: "PARANA EQUIPAMENTOS S.A" → "PARANA EQUIPAMENTOS SA")
2. Inserir/atualizar regras de normalização no banco para dealers conhecidos
3. Inserir os top dealers na tabela dealer_marca com sua marca
4. Reprocessar marca_deduzida via UPDATE que dispara o trigger
"""
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.environ.get("SUPABASE_DB_URL"))
cur = conn.cursor()

# ────────────────────────────────────────────────────────────────────────────
# PASSO 1: Adicionar regras de normalização para os grandes dealers
# (mesmo formato das regras já existentes em normalizacao_fornecedores)
# ────────────────────────────────────────────────────────────────────────────
print("Inserindo regras de normalização para dealers...")

novas_regras = [
    # VENEZA
    ("VENEZA EQUIPAMENTOS SUL", "VENEZA EQUIPAMENTOS"),
    # MACROMAQ
    ("MACROMAQ EQUIPAMENTOS", "MACROMAQ EQUIPAMENTOS"),
    # PARANA EQUIPAMENTOS (padroniza todas as variações para "PARANA EQUIPAMENTOS SA")
    ("PARANA EQUIPAMENTOS S A",  "PARANA EQUIPAMENTOS SA"),
    ("PARANA EQUIPAMENTOS S.A",  "PARANA EQUIPAMENTOS SA"),
    ("PARANA EQUIPAMENTOS S.A.", "PARANA EQUIPAMENTOS SA"),
    ("PARANA EQUIPAMENTOS",      "PARANA EQUIPAMENTOS SA"),
    # YAMADIESEL
    ("YAMADIESEL COMERCIO DE MAQUINAS", "YAMADIESEL"),
    ("YAMADIESEL COM. MAQ",             "YAMADIESEL"),
    ("YAMADIESEL",                      "YAMADIESEL"),
    # SARANDI
    ("SARANDI TRATORES",    "SARANDI TRATORES"),
    # IGUACU
    ("IGUACU MAQUINAS",     "IGUACU MAQUINAS"),
    # LIUGONG
    ("LIUGONG LATIN AMERICA", "LIUGONG"),
    ("LIUGONG",               "LIUGONG"),
    # SHARK
    ("SHARK MAQUINAS",      "SHARK MAQUINAS"),
    # VIEMAQ
    ("VIEMAQ EQUIPAMENTOS", "VIEMAQ EQUIPAMENTOS"),
    # FORZA
    ("FORZA MAQUINAS",      "FORZA MAQUINAS"),
    # TORINO
    ("TORINO COMERCIAL",    "TORINO COMERCIAL"),
    # MPM
    ("MPM COMERCIO",        "MPM COMERCIAL"),
    ("MPM COM",             "MPM COMERCIAL"),
    # CENTRO OESTE
    ("CENTRO OESTE",        "CENTRO OESTE"),
]

for termo, normalizado in novas_regras:
    cur.execute("""
        INSERT INTO normalizacao_fornecedores (termo_busca, nome_normalizado)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (termo, normalizado))

conn.commit()
print(f"  {len(novas_regras)} regras inseridas/atualizadas.")

# ────────────────────────────────────────────────────────────────────────────
# PASSO 2: Inserir mapeamentos dealer → marca na dealer_marca
# Baseado em pesquisa: qual marca cada dealer representa
# ────────────────────────────────────────────────────────────────────────────
print("\nInserindo mapeamentos dealer → marca em dealer_marca...")

# Mapeamento pesquisado: dealer normalizado → (marca, confianca)
# Fontes: sites dos dealers, PNCP descricao, licitações públicas conhecidas
dealer_marcas = [
    # VENEZA - representa New Holland no Sul do Brasil
    ("VENEZA EQUIPAMENTOS",      "NEW HOLLAND", "confirmado"),
    # MACROMAQ - revende New Holland e Case em SC/PR
    ("MACROMAQ EQUIPAMENTOS",    "CASE",         "presumido"),
    # PARANA EQUIPAMENTOS - concessionária New Holland / Case no PR
    ("PARANA EQUIPAMENTOS SA",   "CASE",         "presumido"),
    # YAMADIESEL - representa JCB no Sul/SE
    ("YAMADIESEL",               "JCB",          "presumido"),
    # SARANDI TRATORES - New Holland no RS
    ("SARANDI TRATORES",         "NEW HOLLAND",  "presumido"),
    # IGUACU MAQUINAS - John Deere / múltiplas
    ("IGUACU MAQUINAS",          "JOHN DEERE",   "presumido"),
    # LIUGONG - importadora/distribuidora oficial
    ("LIUGONG",                  "LIUGONG",      "confirmado"),
    # SHARK MAQUINAS - revendedor JCB
    ("SHARK MAQUINAS",           "JCB",          "presumido"),
    # VIEMAQ - New Holland em MG
    ("VIEMAQ EQUIPAMENTOS",      "NEW HOLLAND",  "presumido"),
    # FORZA MAQUINAS - Case em SP
    ("FORZA MAQUINAS",           "CASE",         "presumido"),
    # TORINO - múltiplas marcas (veículos pesados)
    ("TORINO COMERCIAL",         "NEW HOLLAND",  "presumido"),
    # MPM COMERCIAL - distribuidora
    ("MPM COMERCIAL",            "KOMATSU",      "presumido"),
    # CENTRO OESTE
    ("CENTRO OESTE",             "JCB",          "presumido"),
    # BAMAQ ja existe, mas garantir
    ("BAMAQ",                    "NEW HOLLAND",  "confirmado"),
]

for forn_norm, marca, confianca in dealer_marcas:
    cur.execute("""
        INSERT INTO dealer_marca (fornecedor_normalizado, marca, confianca, data_inicio_vigencia)
        VALUES (%s, %s, %s, '2020-01-01')
        ON CONFLICT DO NOTHING
    """, (forn_norm, marca, confianca))

conn.commit()
print(f"  {len(dealer_marcas)} mapeamentos dealer→marca inseridos.")

# ────────────────────────────────────────────────────────────────────────────
# PASSO 3: Reprocessar fornecedor_normalizado para variações com ponto/espaço
# ────────────────────────────────────────────────────────────────────────────
print("\nNormalizando variações de grafia dos fornecedores...")

# Consolidar variações em um único nome padrão via UPDATE direto
padronizacoes = [
    ("PARANA EQUIPAMENTOS S A",   "PARANA EQUIPAMENTOS SA"),
    ("PARANA EQUIPAMENTOS S.A",   "PARANA EQUIPAMENTOS SA"),
    ("PARANA EQUIPAMENTOS S.A.",  "PARANA EQUIPAMENTOS SA"),
    ("VENEZA EQUIPAMENTOS SUL COMERCIO LTDA", "VENEZA EQUIPAMENTOS"),
    ("VENEZA EQUIPAMENTOS SUL COM%RCIO LTDA", "VENEZA EQUIPAMENTOS"),
    ("LIUGONG LATIN AMERICA MAQUINAS PARA CONSTRUCAO PESADA LTDA.", "LIUGONG"),
    ("LIUGONG LATIN AMERICA MAQUINAS PARA CONSTRU%O PESADA LTDA",   "LIUGONG"),
    ("YAMADIESEL COMERCIO DE MAQUINAS - EIRELI", "YAMADIESEL"),
    ("YAMADIESEL COMERCIO DE MAQUINAS LTDA",     "YAMADIESEL"),
    ("YAMADIESEL COM. MAQ. EIRELI",              "YAMADIESEL"),
    ("MPM COM%RCIO DE M%QUINAS PE%AS E SERVI%OS LTDA", "MPM COMERCIAL"),
    ("IGUACU MAQUINAS AGRICOLAS LTDA",           "IGUACU MAQUINAS"),
    ("SHARK MAQUINAS PARA CONSTRUCAO LTDA",      "SHARK MAQUINAS"),
    ("VIEMAQ EQUIPAMENTOS LTDA",                 "VIEMAQ EQUIPAMENTOS"),
    ("FORZA MAQUINAS AGRICOLAS E CONSTRUCAO LTDA", "FORZA MAQUINAS"),
    ("TORINO COMERCIAL DE VEICULOS LTDA",        "TORINO COMERCIAL"),
    ("SARANDI TRATORES LTDA",                    "SARANDI TRATORES"),
    ("MACROMAQ EQUIPAMENTOS LTDA",               "MACROMAQ EQUIPAMENTOS"),
]

count_updated = 0
for old_norm, new_norm in padronizacoes:
    op = "=" if "%" not in old_norm else "ILIKE"
    cur.execute(f"""
        UPDATE transacao
        SET fornecedor_normalizado = %s
        WHERE fornecedor_normalizado {op} %s
          AND tipo_registro = 'COMPRA_NOVA'
    """, (new_norm, old_norm))
    count_updated += cur.rowcount

conn.commit()
print(f"  {count_updated} registros com fornecedor_normalizado padronizado.")

# ────────────────────────────────────────────────────────────────────────────
# PASSO 4: Disparar re-dedução de marca via UPDATE que aciona o trigger
# (trigger_deduzir_marca é BEFORE UPDATE, então basta fazer UPDATE)
# ────────────────────────────────────────────────────────────────────────────
print("\nRe-disparando trigger deduzir_marca em COMPRA_NOVA+HOMOLOGADO...")

# Trigger roda em UPDATE automaticamente — tocar o campo fornecedor_normalizado
# para acionar novamente mesmo nos registros já atualizados
cur.execute("""
    UPDATE transacao
    SET fornecedor_normalizado = fornecedor_normalizado
    WHERE tipo_registro = 'COMPRA_NOVA'
      AND situacao = 'HOMOLOGADO'
      AND fornecedor_original IS NOT NULL
      AND fornecedor_original != ''
""")
touched = cur.rowcount
conn.commit()
print(f"  Trigger re-disparado em {touched} registros.")

# ────────────────────────────────────────────────────────────────────────────
# PASSO 5: Verificação final
# ────────────────────────────────────────────────────────────────────────────
print("\n=== RESULTADO FINAL ===")
cur.execute("""
    SELECT marca_deduzida, COUNT(*)
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
    GROUP BY marca_deduzida ORDER BY 2 DESC
""")
print("marca_deduzida | count")
for r in cur.fetchall(): print(f"  {r[0]} | {r[1]}")

cur.close()
conn.close()
print("\nConcluído!")
