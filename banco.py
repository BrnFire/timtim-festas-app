import os
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
# Função genérica para carregar dados (Supabase + Local)
# ======================================================
def carregar_dados(nome_arquivo, colunas):
    """
    Carrega dados de uma tabela Supabase com fallback local em CSV.
    O nome_arquivo é algo como 'reservas.csv' ou 'clientes.csv'.
    """
    nome_tabela = os.path.splitext(os.path.basename(nome_arquivo))[0]
    caminho_abs = os.path.join(os.getcwd(), nome_arquivo)

    try:
        # 🔹 Primeiro tenta buscar do Supabase
        print(f"Tentando carregar '{nome_tabela}' do Supabase...")
        df = table_select(nome_tabela)
        if df is not None and not df.empty:
            print(f"✅ Dados carregados de {nome_tabela} (Supabase)")
            return df
        else:
            print(f"⚠️ Tabela '{nome_tabela}' vazia no Supabase.")
    except Exception as e:
        print(f"Erro ao conectar ao Supabase: {e}")

    # 🔹 Se falhar, tenta carregar do CSV local
    try:
        if os.path.exists(caminho_abs):
            df = pd.read_csv(caminho_abs)
            print(f"📁 Dados carregados de '{nome_arquivo}' (local).")
        else:
            df = pd.DataFrame(columns=colunas)
            df.to_csv(caminho_abs, index=False, encoding="utf-8-sig")
            print(f"🆕 Arquivo '{nome_arquivo}' criado localmente.")
        return df
    except Exception as e:
        print(f"Erro ao carregar dados de '{nome_arquivo}': {e}")
        return pd.DataFrame(columns=colunas)

# ======================================================
# Função genérica para salvar dados (Supabase + Local)
# ======================================================
def salvar_dados(df, nome_arquivo):
    """
    Salva os dados no Supabase e também mantém um backup local.
    O nome_arquivo é algo como 'reservas.csv' ou 'clientes.csv'.
    """
    import pandas as pd
    import os

    nome_tabela = os.path.splitext(os.path.basename(nome_arquivo))[0]
    caminho_abs = os.path.join(os.getcwd(), nome_arquivo)

    # -------------------------------
    # 🟣 1. Tenta salvar no Supabase
    # -------------------------------
    try:
        print(f"Tentando salvar '{nome_tabela}' no Supabase...")

        # Antes de sobrescrever, limpa a tabela
        supabase.table(nome_tabela).delete().neq("id", 0).execute()

        # Insere novamente todos os registros
        registros = df.to_dict(orient="records")
        if registros:
            supabase.table(nome_tabela).insert(registros).execute()

        print(f"✅ Dados salvos na tabela '{nome_tabela}' do Supabase.")
    except Exception as e:
        print(f"⚠️ Erro ao salvar no Supabase: {e}")

    # -------------------------------
    # 💾 2. Backup local (CSV)
    # -------------------------------
    try:
        df.to_csv(caminho_abs, index=False, encoding="utf-8-sig")
        print(f"📁 Backup local atualizado: {nome_arquivo}")
    except Exception as e:
        print(f"⚠️ Erro ao salvar backup local '{nome_arquivo}': {e}")

