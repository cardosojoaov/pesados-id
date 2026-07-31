#!/usr/bin/env python3
"""
PESADOS.ID — Script de Teste e Diagnóstico de Conexão com o Supabase
BPA Ventures · v1.0 · 2026

Este script valida a conexão com o banco de dados PostgreSQL do Supabase,
verifica se a estrutura de tabelas, triggers e views do PESADOS.ID foi
criada corretamente e exibe um relatório completo de integridade no terminal.
"""

import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Tentar importar o driver psycopg2
try:
    import psycopg2
except ImportError:
    print("❌ Erro: O pacote 'psycopg2' não está instalado.")
    print("👉 Instale rodando: pip install psycopg2-binary")
    sys.exit(1)

def load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"\''))

def run_diagnostics():
    load_env_file()
    # 1. Recuperar string de conexão das variáveis de ambiente
    db_url = os.environ.get("SUPABASE_DB_URL")
    
    print("=" * 60)
    print("     PESADOS.ID — DIAGNÓSTICO DE BANCO DE DADOS SUPABASE     ")
    print("=" * 60)
    
    if not db_url:
        print("⚠️  Aviso: A variável de ambiente 'SUPABASE_DB_URL' não está configurada.")
        print("Insira a sua Connection String (URI) do Supabase para realizar o teste.")
        print("Formatos recomendados:")
        print(" - Conexão Direta (Porta 5432): postgresql://postgres:[senha]@db.[ref].supabase.co:5432/postgres")
        print(" - Transaction Pooler (Porta 6543): postgresql://postgres.[ref]:[senha]@aws-0-[regiao].pooler.supabase.com:6543/postgres?sslmode=require&prepare_threshold=0")
        print("-" * 60)
        
        try:
            db_url = input("Digite a Connection String do Supabase: ").strip()
        except KeyboardInterrupt:
            print("\n\n❌ Teste cancelado pelo usuário.")
            sys.exit(1)
            
        if not db_url:
            print("❌ Erro: Nenhuma Connection String foi informada.")
            sys.exit(1)
            
    print("\n⚡ Conectando ao banco de dados...")
    
    try:
        # Tenta abrir a conexão
        conn = psycopg2.connect(db_url, connect_timeout=10)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Testar query simples
        cur.execute("SELECT version();")
        db_version = cur.fetchone()[0]
        print("✅ Conexão estabelecida com sucesso!")
        print(f"🖥️  Versão do PostgreSQL: {db_version}\n")
        
    except psycopg2.OperationalError as e:
        print("❌ Falha crítica de conexão!")
        print("\nCausa provável:")
        print(" 1. A senha informada na Connection String está incorreta.")
        print(" 2. O host ou a referência do projeto está errada.")
        print(" 3. Se estiver usando o Transaction Pooler (porta 6543), certifique-se de incluir '?sslmode=require&prepare_threshold=0' no final da URI.")
        print("-" * 60)
        print(f"Detalhes do erro:\n{e}")
        sys.exit(1)
        
    # Checklist de objetos do banco de dados do MVP
    diagnosticos = [
        {"nome": "Tabela 'config_filtros_categoria'", "tipo": "table", "query": "SELECT COUNT(*) FROM config_filtros_categoria;"},
        {"nome": "Tabela 'normalizacao_fornecedores'", "tipo": "table", "query": "SELECT COUNT(*) FROM normalizacao_fornecedores;"},
        {"nome": "Tabela 'dealer_marca'", "tipo": "table", "query": "SELECT COUNT(*) FROM dealer_marca;"},
        {"nome": "Tabela 'transacao'", "tipo": "table", "query": "SELECT COUNT(*) FROM transacao;"},
        {"nome": "Tabela 'coleta_log'", "tipo": "table", "query": "SELECT COUNT(*) FROM coleta_log;"},
        {"nome": "View 'view_vendas_maquinas_reais'", "tipo": "view", "query": "SELECT COUNT(*) FROM view_vendas_maquinas_reais;"}
    ]
    
    print("-" * 60)
    print("📋 VERIFICANDO ESTRUTURA DO BANCO (PESADOS.ID)...")
    print("-" * 60)
    
    erros_encontrados = 0
    tabelas_vazias = []
    
    for item in diagnosticos:
        try:
            cur.execute(item["query"])
            count = cur.fetchone()[0]
            print(f"✅ {item['nome']}: OK (Contém {count} registros)")
            
            if count == 0 and item["tipo"] == "table":
                tabelas_vazias.append(item["nome"])
                
        except psycopg2.errors.UndefinedTable:
            print(f"❌ {item['nome']}: NÃO ENCONTRADA! (Execute as migrations do README-v2.md)")
            erros_encontrados += 1
        except Exception as e:
            print(f"❌ {item['nome']}: ERRO ao consultar. Detalhes: {e}")
            erros_encontrados += 1
            
    print("-" * 60)
    
    # Validação do Trigger de Normalização
    print("⚙️  Verificando Trigger de Normalização...")
    try:
        cur.execute("""
            SELECT trigger_name 
            FROM information_schema.triggers 
            WHERE trigger_name = 'tg_pre_normalizar_fornecedor';
        """)
        trigger_exists = cur.fetchone()
        if trigger_exists:
            print("✅ Trigger 'tg_pre_normalizar_fornecedor' está ativo.")
        else:
            print("❌ Trigger de normalização automática não encontrado!")
            erros_encontrados += 1
    except Exception as e:
        print(f"⚠️  Erro ao verificar Triggers: {e}")
        
    print("-" * 60)
    
    # Resumo Geral do Diagnóstico
    if erros_encontrados == 0:
        print("🎉 EXCELENTE! Toda a estrutura física do banco está intacta e pronta.")
        
        if tabelas_vazias:
            print("\n⚠️  Atenção para Ingestão de Dados:")
            for tab in tabelas_vazias:
                print(f" - A {tab} está vazia. Rode o pipeline de ingestão ou o script de Seed para validar o piloto.")
            print("\n👉 Para testar o cálculo de market share de Minas Gerais com dados reais ou simulados,")
            print("   rode o script Python de ingestão (ingestion_pipeline-v2.py) ou execute o script SQL de Seed.")
        else:
            print("\n🚀 O banco de dados está populado e pronto para servir os dashboards!")
            
            # Executar simulação rápida de Minas Gerais
            try:
                cur.execute("""
                    SELECT COUNT(*) FROM view_vendas_maquinas_reais 
                    WHERE categoria_sigla = 'BHL' AND uf = 'MG';
                """)
                bhl_mg = cur.fetchone()[0]
                print(f"💡 Info de Mercado: Atualmente existem {bhl_mg} registros de Retroescavadeira em MG ativos na View.")
            except Exception:
                pass
    else:
        print(f"❌ O diagnóstico encontrou {erros_encontrados} inconsistência(s) na estrutura do banco.")
        print("👉 Abra o editor SQL do Supabase e execute as migrations descritas no seu 'README-v2.md'.")
        
    print("=" * 60)
    
    # Fechar conexões de forma segura
    cur.close()
    conn.close()

if __name__ == "__main__":
    run_diagnostics()
