import pandas as pd
import os
from supabase_rest import (
    table_select, table_insert, table_update, table_delete
)

# ==========================================================
# 🔧 CONFIGURAÇÃO DE MODO
# ==========================================================
# Use MODO_APP="online" para Supabase
# ou MODO_APP="local" para usar os CSV
MODO = os.getenv("MODO_APP", "online").lower()


# ==========================================================
# 📥 FUNÇÃO: CARREGAR DADOS
# ==========================================================
def carregar_dados(nome_tabela, colunas):
    """
    Carrega dados do Supabase (modo online)
    ou do CSV local (modo local).
    """
    try:
        if MODO == "online":
            dados = table_select(nome_tabela)
            df = pd.DataFrame(dados)
        else:
            df = pd.read_csv(nome_tabela, encoding="utf-8-sig")

    except Exception as e:
        print(f"[ERRO] Falha ao carregar '{nome_tabela}': {e}")
        df = pd.DataFrame(columns=colunas)

    # Garante que todas as colunas existam
    for c in colunas:
        if c not in df.columns:
            df[c] = ""

    df = df.reindex(columns=colunas).reset_index(drop=True)
    return df


# ==========================================================
# 💾 FUNÇÃO: SALVAR DADOS
# ==========================================================
def salvar_dados(df, nome_tabela):
    """
    Salva dados no Supabase (modo online)
    ou em CSV local (modo local).
    """
    try:
        if MODO == "online":
            registros = df.to_dict(orient="records")

            # Deleta registros antigos (para evitar duplicar)
            try:
                table_delete(nome_tabela, {})
            except Exception as e:
                print(f"[AVISO] Não foi possível limpar '{nome_tabela}': {e}")

            if registros:
                table_insert(nome_tabela, registros)
                print(f"[OK] {len(registros)} registros enviados para '{nome_tabela}'")
            else:
                print(f"[INFO] Nenhum registro para salvar em '{nome_tabela}'")

        else:
            df.to_csv(nome_tabela, index=False, encoding="utf-8-sig")
            print(f"[OK] Dados salvos localmente em '{nome_tabela}'")

    except Exception as e:
        print(f"[ERRO] Falha ao salvar '{nome_tabela}': {e}")


# ==========================================================
# ✏️ FUNÇÃO OPCIONAL: ATUALIZAR REGISTRO ESPECÍFICO
# ==========================================================
def atualizar_registro(nome_tabela, filtro, novos_valores):
    """
    Atualiza registros específicos no Supabase.
    Exemplo:
        atualizar_registro("clientes", {"id": 3}, {"telefone": "(11) 98888-7777"})
    """
    try:
        if MODO == "online":
            table_update(nome_tabela, where=filtro, values=novos_valores)
            print(f"[OK] Registro atualizado em '{nome_tabela}'")
        else:
            print("[AVISO] Atualização individual só é suportada no modo online.")
    except Exception as e:
        print(f"[ERRO] Falha ao atualizar '{nome_tabela}': {e}")

