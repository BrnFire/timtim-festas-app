# banco.py — Camada de I/O no Supabase para o app TimTim Festas
from __future__ import annotations

import os
import math
import time
import logging
from typing import List, Optional, Dict, Any

import pandas as pd
import re
import requests

try:
    import streamlit as st
except Exception:
    # fallback leve para rodar fora do Streamlit (ex.: testes locais)
    class _Dummy:
        def __getattr__(self, name):
            def _(*args, **kwargs):
                return None
            return _
    st = _Dummy()  # type: ignore


# === Corrige SSL local (rede corporativa) ===
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass
# ============================================



from supabase import create_client, Client

SUPABASE_URL_DEFAULT = "https://hmrqsjdlixeazdfhrqqh.supabase.co"
SUPABASE_KEY_DEFAULT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhtcnFzamRsaXhlYXpkZmhycXFoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MTIyMTcwNSwiZXhwIjoyMDc2Nzk3NzA1fQ.o4M5Ku9Glbg8gCMTFSNCDkgKedn4-ZJWKzeY7IAEKXA"

_SB: Client | None = None


def _get_supabase_client() -> Client:
    """
    Cria o client do Supabase.
    1º tenta pegar de st.secrets
    2º tenta variáveis de ambiente
    3º usa os defaults acima.
    """
    url = None
    key = None

    # 1) st.secrets (quando estiver no Streamlit Cloud)
    try:
        if hasattr(st, "secrets") and "supabase" in st.secrets:
            url = st.secrets["supabase"].get("url")
            key = st.secrets["supabase"].get("key")
    except Exception:
        pass

    # 2) variáveis de ambiente (para rodar local com segurança)
    if not url:
        url = os.getenv("SUPABASE_URL", SUPABASE_URL_DEFAULT)
    if not key:
        key = os.getenv("SUPABASE_KEY", SUPABASE_KEY_DEFAULT)

    # 3) cria o client — 🔴 sem verify / options aqui
    return create_client(url, key)


def sb() -> Client:
    """Retorna sempre o mesmo client (cache em memória)."""
    global _SB
    if _SB is None:
        _SB = _get_supabase_client()
    return _SB



# ===================================================
# HELPERS
# ===================================================
def _tabela_from_nome_arquivo(nome: str) -> str:
    """Converte 'reservas.csv' -> 'reservas'. Mantém nome se já vier sem .csv"""
    base = (nome or "").strip()
    if base.lower().endswith(".csv"):
        base = base[:-4]
    return base.lower()


def _chunked(iterable: List[Dict[str, Any]], size: int = 500):
    """Gera blocos (chunks) para upload em lotes."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]


def _ensure_columns(df: pd.DataFrame, colunas: Optional[List[str]], defaults: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Garante colunas obrigatórias e aplica valores padrão se especificados.
    Compatível com chamadas como _ensure_columns(df, cols, defaults={"valor":0.0})
    """
    if defaults is None:
        defaults = {}

    if colunas is None:
        return df.reset_index(drop=True)

    for c in colunas:
        if c not in df.columns:
            df[c] = defaults.get(c, "")
    return df[colunas].reset_index(drop=True)


# ===================================================
# PRINCIPAIS FUNÇÕES DE I/O
# ===================================================
def carregar_dados(nome_arquivo_ou_tabela: str, colunas: list[str]):
    """
    Lê dados de uma tabela do Supabase e retorna um DataFrame com as colunas especificadas.
    Sempre retorna um DataFrame válido (mesmo que vazio).
    """
    tabela = _tabela_from_nome_arquivo(nome_arquivo_ou_tabela)
    df = pd.DataFrame(columns=colunas)

    try:
        response = sb().table(tabela).select("*").execute()

        # Compatibilidade entre versões do SDK
        data = None
        if hasattr(response, "data"):
            data = response.data
        elif isinstance(response, dict) and "data" in response:
            data = response["data"]
        elif isinstance(response, dict) and "results" in response:
            data = response["results"]

        if data:
            df = pd.DataFrame(data)
        else:
            st.warning(f"⚠️ Nenhum dado retornado da tabela '{tabela}'.")

    except Exception as e:
        st.error(f"❌ Erro ao carregar dados da tabela '{tabela}': {e}")

    return _ensure_columns(df, colunas)


# ===================================================
# ✅ SALVAR DADOS (SEM DUPLICAR REGISTROS)
# ===================================================

# --- SUBSTITUA APENAS ESTA FUNÇÃO NO SEU banco.py ---
def salvar_dados(df, nome_tabela: str):
    """
    Salva o DataFrame no Supabase evitando duplicação.
    Usa UPSERT quando encontra uma chave de conflito, senão faz
    DELETE ALL + INSERT.
    """
    import pandas as pd
    from datetime import date, datetime

    if df is None or df.empty:
        print(f"⚠️ Nenhum dado para salvar na tabela '{nome_tabela}'.")
        return

    # 1) Normaliza datas/NaN
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
        elif df[col].dtype == "object":
            df[col] = df[col].apply(
                lambda x: x.strftime("%Y-%m-%d") if isinstance(x, (date, datetime)) else x
            )
    df = df.where(pd.notnull(df), None)

    tabela = _tabela_from_nome_arquivo(nome_tabela).lower()
    registros = df.to_dict(orient="records")

    # usa o client global (sb()), que já não tem verify
    sup = sb()

    # ===== escolha da conflict_key (seu código antigo aqui, só mantido) =====
    lower_cols = [c.lower() for c in df.columns]

    def tem_col(nome):
        return nome in lower_cols and df[df.columns[lower_cols.index(nome)]].notnull().any()

    conflict_key = None
    if tabela == "reservas" and tem_col("id_cliente"):
        conflict_key = "id_cliente"
    elif tabela == "clientes":
        if tem_col("id_cliente"):
            conflict_key = "id_cliente"
        elif tem_col("cpf"):
            conflict_key = "cpf"
        elif tem_col("nome"):
            conflict_key = "nome"
    elif tabela == "brinquedos":
        if tem_col("id_brinquedo"):
            conflict_key = "id_brinquedo"
        elif tem_col("nome"):
            conflict_key = "nome"
    elif tabela == "custos":
        if tem_col("id_custo"):
            conflict_key = "id_custo"
    elif tabela == "emprestimos":
        if tem_col("id_emprestimo"):
            conflict_key = "id_emprestimo"
    elif tabela == "pagamentos_emprestimos":
        if tem_col("id_pagamento"):
            conflict_key = "id_pagamento"
    # (demais tabelas continuam como estavam, se você tiver)

    # 3) Tenta UPSERT se tiver conflict_key
    if conflict_key:
        try:
            sup.table(tabela).upsert(registros, on_conflict=conflict_key).execute()
            print(f"✅ UPSERT em '{tabela}' por '{conflict_key}': {len(registros)} linhas.")
            return
        except Exception as e:
            print(f"⚠️ Falha no UPSERT por '{conflict_key}' em '{tabela}': {e}. Fallback para DELETE ALL + INSERT.")

    # 4) Fallback: apaga tudo e insere de novo
    try:
        sup.table(tabela).delete().neq("id", 0).execute()
    except Exception as e:
        print(f"⚠️ Não deu pra limpar '{tabela}' antes de inserir: {e} (vamos inserir mesmo assim).")

    if registros:
        sup.table(tabela).insert(registros).execute()
    print(f"✅ Tabela '{tabela}' regravada: {len(registros)} linhas.")




# ===================================================
# FUNÇÕES AUXILIARES
# ===================================================
def atualizar_um(tabela_ou_csv: str, filtro: Dict[str, Any], campos: Dict[str, Any]) -> None:
    """Atualiza registros que casam com 'filtro'."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        q = sb().table(tabela).update(campos)
        for k, v in filtro.items():
            q = q.eq(k, v)
        q.execute()
        st.toast("🔄 Atualizado!", icon="✅")
    except Exception as e:
        logging.exception("Erro em atualizar_um(%s)", tabela)
        st.error(f"❌ Erro ao atualizar '{tabela}': {e}")
        raise


def inserir_um(tabela_ou_csv: str, registro: Dict[str, Any]) -> None:
    """Insere um único registro (dict)."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        sb().table(tabela).insert(registro).execute()
        st.toast("➕ Registro inserido.", icon="✅")
    except Exception as e:
        logging.exception("Erro em inserir_um(%s)", tabela)
        st.error(f"❌ Erro ao inserir em '{tabela}': {e}")
        raise


def deletar_por_filtro(tabela_ou_csv: str, filtro: Dict[str, Any]) -> None:
    """Deleta registros que casem com o filtro informado."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        q = sb().table(tabela).delete()
        for k, v in filtro.items():
            q = q.eq(k, v)
        q.execute()
        st.toast("🗑️ Registro(s) excluído(s).", icon="✅")
    except Exception as e:
        logging.exception("Erro em deletar_por_filtro(%s)", tabela)
        st.error(f"❌ Erro ao excluir em '{tabela}': {e}")
        raise


# ===================================================
# FUNÇÃO EXTRA — DISTÂNCIA ENTRE CEPs
# ===================================================
def calcular_distancia_km(cep_origem, cep_destino):
    """
    Calcula a distância aproximada (em km) entre dois CEPs usando a API Nominatim (OpenStreetMap).
    Retorna None se não for possível calcular.
    """
    try:
        cep_origem = re.sub(r"\D", "", str(cep_origem))
        cep_destino = re.sub(r"\D", "", str(cep_destino))

        if not cep_origem or not cep_destino:
            return None

        def obter_coords(cep):
            url = f"https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brazil&format=json"
            r = requests.get(url, headers={"User-Agent": "TimTimFestasApp"})
            if r.status_code == 200 and r.json():
                dados = r.json()[0]
                return float(dados["lat"]), float(dados["lon"])
            return None

        origem = obter_coords(cep_origem)
        destino = obter_coords(cep_destino)
        if not origem or not destino:
            return None

        from geopy.distance import geodesic
        return round(geodesic(origem, destino).km, 1)

    except Exception as e:
        print(f"Erro ao calcular distância: {e}")
        return None

# ===================================================
# ✅ COMPATIBILIDADE — Alias para função antiga
# ===================================================
def _ensure_cols(df, cols, defaults=None):
    """
    Compatibilidade com versões antigas do app.
    Redireciona para _ensure_columns com suporte a defaults.
    """
    try:
        return _ensure_columns(df, cols, defaults)
    except TypeError:
        # fallback para chamadas antigas sem defaults
        return _ensure_columns(df, cols)
    
# ============================================================
# Funções auxiliares do banco (Supabase) — sem duplicação
# ============================================================

def inserir_um(tabela_ou_csv: str, registro: dict):
    """Insere uma única linha no Supabase."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        sb().table(tabela).insert(registro).execute()
        st.toast("✅ Registro inserido com sucesso.", icon="💾")
    except Exception as e:
        logging.exception(f"Erro em inserir_um({tabela})")
        st.error(f"❌ Erro ao inserir em '{tabela}': {e}")
        raise


def atualizar_por_filtro(tabela_ou_csv: str, novos_dados: dict, filtro: dict):
    """Atualiza registros conforme filtro (WHERE)."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        query = sb().table(tabela).update(novos_dados)
        for campo, valor in filtro.items():
            query = query.eq(campo, valor)
        query.execute()
        st.toast("🔄 Registro atualizado!", icon="✅")
    except Exception as e:
        logging.exception(f"Erro em atualizar_por_filtro({tabela})")
        st.error(f"❌ Erro ao atualizar '{tabela}': {e}")
        raise


def deletar_por_filtro(tabela_ou_csv: str, filtro: dict):
    """Deleta registros conforme filtro (WHERE)."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        query = sb().table(tabela).delete()
        for campo, valor in filtro.items():
            query = query.eq(campo, valor)
        query.execute()
        st.toast("🗑️ Registro excluído!", icon="✅")
    except Exception as e:
        logging.exception(f"Erro em deletar_por_filtro({tabela})")
        st.error(f"❌ Erro ao excluir em '{tabela}': {e}")
        raise
