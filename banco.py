import pandas as pd
from supabase import create_client
from supabase_rest import table_select

# ----------------------------------------
# CONFIGURAÇÃO SUPABASE
# ----------------------------------------
SUPABASE_URL = "https://hmrqsjdlixeazdfhrqqh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhtcnFzamRsaXhlYXpkZmhycXFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEyMjE3MDUsImV4cCI6MjA3Njc5NzcwNX0.rM9fob3HIEl2YoL7lB7Tj7vUb21B9EzR1zLSR7VLwTM"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ======================================================
# 🔹 Carregar dados diretamente do Supabase
# ======================================================
def carregar_dados(nome_arquivo, colunas=None):
    """
    Carrega dados de uma tabela Supabase (sem CSV local).
    Exemplo: carregar_dados("reservas.csv", ["Cliente", "Data", ...])
    """
    nome_tabela = nome_arquivo.replace(".csv", "")
    try:
        df = table_select(nome_tabela)
        if df is None or df.empty:
            print(f"⚠️ Tabela '{nome_tabela}' vazia.")
            if colunas:
                return pd.DataFrame(columns=colunas)
            return pd.DataFrame()
        print(f"✅ Dados carregados da tabela '{nome_tabela}' ({len(df)} registros).")
        return df
    except Exception as e:
        print(f"❌ Erro ao carregar '{nome_tabela}' do Supabase: {e}")
        if colunas:
            return pd.DataFrame(columns=colunas)
        return pd.DataFrame()


# ======================================================
# 🔹 Salvar dados apenas no Supabase
# ======================================================
def salvar_dados(df, nome_arquivo):
    """
    Salva os dados diretamente no Supabase (sem backup local).
    Exemplo: salvar_dados(df, "clientes.csv")
    """
    nome_tabela = nome_arquivo.replace(".csv", "")
    try:
        print(f"Tentando salvar '{nome_tabela}' no Supabase...")

        # Remove todos os registros da tabela antes de inserir novamente
        supabase.table(nome_tabela).delete().neq("id", 0).execute()

        registros = df.to_dict(orient="records")
        if registros:
            supabase.table(nome_tabela).insert(registros).execute()

        print(f"✅ Dados salvos na tabela '{nome_tabela}' ({len(df)} registros).")
    except Exception as e:
        print(f"❌ Erro ao salvar '{nome_tabela}' no Supabase: {e}")
