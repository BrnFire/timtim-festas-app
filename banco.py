# banco.py — Camada de I/O no Supabase via REST (sem SDK)
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

import pandas as pd
import re
import requests

# Usa streamlit se existir; senão, cria um "dummy" pra não quebrar em testes locais
try:
    import streamlit as st
except Exception:
    class _Dummy:
        def __getattr__(self, name):
            def _(*args, **kwargs):
                return None
            return _
    st = _Dummy()  # type: ignore

# Importa o wrapper REST que você criou
from supabase_rest import (
    table_select,
    table_insert,
    table_update,
    table_delete,
    table_upsert,
)

# ===================================================
# HELPERS DE NOME DE TABELA / CHUNKS
# ===================================================

def _tabela_from_nome_arquivo(nome: str) -> str:
    """
    Converte 'reservas.csv' -> 'reservas'.
    Mantém o nome se já vier sem .csv.
    """
    base = (nome or "").strip()
    if base.lower().endswith(".csv"):
        base = base[:-4]
    return base.lower()


def _chunked(iterable: List[Dict[str, Any]], size: int = 500):
    """Gera blocos (chunks) para upload em lotes."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


# ===================================================
# ENSURE COLUMNS (com defaults)
# ===================================================

def _ensure_columns(
    df: pd.DataFrame,
    colunas: Optional[List[str]],
    defaults: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Garante colunas obrigatórias e aplica valores padrão se especificados.
    Compatível com chamadas como _ensure_columns(df, cols, defaults={"valor": 0.0})
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
# PRINCIPAIS FUNÇÕES DE I/O (USANDO supabase_rest)
# ===================================================

def carregar_dados(nome_arquivo_ou_tabela: str, colunas: List[str]) -> pd.DataFrame:
    """
    Lê dados de uma tabela do Supabase via REST e retorna um DataFrame
    com as colunas especificadas. Sempre retorna um DataFrame válido.
    """
    tabela = _tabela_from_nome_arquivo(nome_arquivo_ou_tabela)
    df = pd.DataFrame(columns=colunas)

    try:
        dados = table_select(tabela)  # SELECT * FROM tabela
        if dados:
            df = pd.DataFrame(dados)
        else:
            st.warning(f"⚠️ Nenhum dado retornado da tabela '{tabela}'.")
    except Exception as e:
        logging.exception("Erro ao carregar dados da tabela %s", tabela)
        st.error(f"❌ Erro ao carregar dados da tabela '{tabela}': {e}")

    return _ensure_columns(df, colunas)


def salvar_dados(arg1, arg2):
    """
    Salva um DataFrame no Supabase, convertendo tudo para JSON válido.
    Compatível com sua tabela atual.
    """

    from datetime import date, datetime

    # Detecta os argumentos (mesma compatibilidade antiga)
    if isinstance(arg1, str):
        nome_tabela = arg1
        df = arg2
    else:
        df = arg1
        nome_tabela = arg2

    if df is None or df.empty:
        print(f"⚠️ Nenhum dado para salvar na tabela '{nome_tabela}'.")
        return

    tabela = _tabela_from_nome_arquivo(nome_tabela)

    df = df.copy()

    # ============================
    # 1) Normalizar DATAS (colunas text no Supabase!)
    # ============================
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")

        elif df[col].dtype == "object":
            df[col] = df[col].apply(
                lambda x: x.strftime("%Y-%m-%d")
                if isinstance(x, (date, datetime))
                else x
            )

    # ============================
    # 2) Normalizar NÚMEROS (float8 no Supabase!)
    # ============================
    numeric_cols = [
        "valor_total", "valor_extra", "frete",
        "desconto", "sinal", "falta"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].replace(",", ".", regex=True)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # ============================
    # 3) Campos que são LISTA/OBJETO → converter para string válida
    # ============================
    if "pagamentos" in df.columns:
        df["pagamentos"] = df["pagamentos"].apply(
            lambda x: str(x) if x not in (None, "", [], {}) else ""
        )

    # ============================
    # 4) Remover NaN/NaT → None
    # ============================
    df = df.where(pd.notnull(df), None)

    registros = df.to_dict("records")

    # ============================
    # 5) Enviar via UPSERT em blocos
    # ============================
    try:
        for chunk in _chunked(registros, 500):
            

            table_upsert(tabela, chunk)

        print(f"✅ Tabela '{tabela}' atualizada com {len(registros)} linha(s).")

    except Exception as e:
        st.error(f"❌ Erro ao salvar dados na tabela '{tabela}': {e}")
        raise




# ===================================================
# FUNÇÕES AUXILIARES (INSERIR / ATUALIZAR / DELETAR)
# ===================================================

def inserir_um(tabela_ou_csv: str, registro: Dict[str, Any]) -> None:
    """Insere uma única linha na tabela informada."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        table_insert(tabela, [registro])
        st.toast("✅ Registro inserido com sucesso.", icon="💾")
    except Exception as e:
        logging.exception("Erro em inserir_um(%s)", tabela)
        st.error(f"❌ Erro ao inserir em '{tabela}': {e}")
        raise


def atualizar_um(tabela_ou_csv: str, filtro: Dict[str, Any], campos: Dict[str, Any]) -> None:
    """Atualiza registros que casam com 'filtro'."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        table_update(tabela, filtro, campos)
        st.toast("🔄 Atualizado!", icon="✅")
    except Exception as e:
        logging.exception("Erro em atualizar_um(%s)", tabela)
        st.error(f"❌ Erro ao atualizar '{tabela}': {e}")
        raise
def atualizar_por_filtro(tabela_ou_csv: str, novos_dados: dict, filtro: dict) -> None:
    """
    Atualiza registros conforme filtro (WHERE).
    Mantém compatibilidade com chamadas antigas do app.
    """
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        # table_update(tabela, where=filtro, values=novos_dados)
        table_update(tabela, filtro, novos_dados)
        st.toast("🔄 Registro atualizado!", icon="✅")
    except Exception as e:
        logging.exception("Erro em atualizar_por_filtro(%s)", tabela)
        st.error(f"❌ Erro ao atualizar '{tabela}': {e}")
        raise


def deletar_por_filtro(tabela_ou_csv: str, filtro: Dict[str, Any]) -> None:
    """Deleta registros que casem com o filtro informado."""
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    try:
        table_delete(tabela, filtro)
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
    Calcula a distância aproximada (em km) entre dois CEPs usando a API
    Nominatim (OpenStreetMap). Retorna None se não for possível calcular.
    """
    try:
        cep_origem = re.sub(r"\D", "", str(cep_origem))
        cep_destino = re.sub(r"\D", "", str(cep_destino))

        if not cep_origem or not cep_destino:
            return None

        def obter_coords(cep):
            url = (
                "https://nominatim.openstreetmap.org/search"
                f"?postalcode={cep}&country=Brazil&format=json"
            )
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
