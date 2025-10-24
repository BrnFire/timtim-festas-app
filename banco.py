import pandas as pd
from supabase import create_client
from supabase_rest import table_select

# ======================================================
# ⚙️ CONFIGURAÇÃO SUPABASE
# ======================================================
SUPABASE_URL = "https://hmrqsjdlixeazdfhrqqh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhtcnFzamRsaXhlYXpkZmhycXFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEyMjE3MDUsImV4cCI6MjA3Njc5NzcwNX0.rM9fob3HIEl2YoL7lB7Tj7vUb21B9EzR1zLSR7VLwTM"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ======================================================
# 🔹 CARREGAR DADOS (somente Supabase)
# ======================================================
def carregar_dados(nome_arquivo, colunas=None):
    """
    Carrega dados diretamente da tabela Supabase.
    Exemplo:
        df = carregar_dados("reservas.csv", ["Cliente", "Data", "Status"])
    """
    nome_tabela = nome_arquivo.replace(".csv", "")
    try:
        df = table_select(nome_tabela)
        if df is None or df.empty:
            print(f"⚠️ Tabela '{nome_tabela}' vazia no Supabase.")
            return pd.DataFrame(columns=colunas or [])
        print(f"✅ Dados carregados da tabela '{nome_tabela}' ({len(df)} registros).")
        return df
    except Exception as e:
        print(f"❌ Erro ao carregar '{nome_tabela}' do Supabase: {e}")
        return pd.DataFrame(columns=colunas or [])


# ======================================================
# 🔹 SALVAR DADOS (somente Supabase)
# ======================================================
def salvar_dados(df, nome_arquivo):
    """
    Salva os dados diretamente na tabela do Supabase.
    Exemplo:
        salvar_dados(df, "clientes.csv")
    """
    nome_tabela = nome_arquivo.replace(".csv", "")
    try:
        print(f"Tentando salvar '{nome_tabela}' no Supabase...")

        # Remove todos os registros existentes antes de inserir novos
        supabase.table(nome_tabela).delete().neq("id", 0).execute()

        # Insere novamente os registros atuais
        registros = df.to_dict(orient="records")
        if registros:
            supabase.table(nome_tabela).insert(registros).execute()

        print(f"✅ Dados salvos com sucesso na tabela '{nome_tabela}' ({len(df)} registros).")
    except Exception as e:
        print(f"❌ Erro ao salvar '{nome_tabela}' no Supabase: {e}")
