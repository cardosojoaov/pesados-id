import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

response = supabase.table("view_vendas_maquinas_reais").select("*").eq("uf", "MG").eq("categoria_sigla", "BHL").execute()

data = response.data
total_unidades = sum(r["quantidade"] for r in data if r.get("quantidade"))
total_reais = sum(r["valor_total"] for r in data if r.get("valor_total"))
municipios = set(r["municipio"] for r in data if r.get("municipio"))
total_municipios = len(municipios)
ticket_medio = total_reais / total_unidades if total_unidades > 0 else 0

print(f"Unidades: {total_unidades}")
print(f"Reais: {total_reais}")
print(f"Municipios: {total_municipios}")
print(f"Ticket Medio: {ticket_medio}")
