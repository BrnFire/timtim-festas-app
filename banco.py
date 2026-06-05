from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Iterable

import pandas as pd
import re
import requests

__BCO_VERSION__ = "banco.py/ModeloB-2026-03-18"

# ==============================
# STREAMLIT SAFE IMPORT
# ==============================
try:
    import streamlit as st
except Exception:
    class _Dummy:
        def __getattr__(self, name):
            def _(*args, **kwargs):
                return None
            return _
    st = _Dummy()  # type: ignore

# ==============================
# SUPABASE REST WRAPPER
# ==============================
from supabase_rest import (
    table_select,
    table_insert,
    table_update,
    table_delete,
    table_upsert,
)

# ==============================
# HELPERS
# ==============================

def _tabela_from_nome_arquivo(nome: str) -> str:
    base = (nome or "").strip()
    if base.lower().endswith(".csv"):
        base = base[:-4]
    return base.lower()

def _normalize_txt(x: Any) -> Any:
    if isinstance(x, str):
        return " ".join(x.split()).strip()
    return x

def _is_duplicate_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "duplicate key value" in msg
        or "status_code=409" in msg
        or "23505" in msg
    )

# ==============================
# ENSURE COLS
# ==============================

def _ensure_columns(
    df: pd.DataFrame,
    colunas: Optional[List[str]],
    defaults: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:

    if defaults is None:
        defaults = {}

    if colunas is None:
        return df.reset_index(drop=True)

    for c in colunas:
        if c not in df.columns:
            df[c] = defaults.get(c, "")

    return df[colunas].reset_index(drop=True)


def _ensure_cols(df, cols, defaults=None):
    try:
        return _ensure_columns(df, cols, defaults)
    except TypeError:
        return _ensure_columns(df, cols)

# ==============================
# LOAD DATA
# ==============================

def carregar_dados(nome_arquivo_ou_tabela: str, colunas: List[str]) -> pd.DataFrame:
    tabela = _tabela_from_nome_arquivo(nome_arquivo_ou_tabela)

    try:
        dados = table_select(tabela)
        df = pd.DataFrame(dados if dados else [])
    except Exception as e:
        logging.exception("Erro ao carregar dados")
        st.error(f"Erro ao carregar dados de {tabela}: {e}")
        df = pd.DataFrame()

    return _ensure_columns(df, colunas)

# ==============================
# PREPARE DF
# ==============================

def _prepare_df_for_rest(df: pd.DataFrame) -> pd.DataFrame:
    from datetime import date, datetime

    out = df.copy()

    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
        elif out[col].dtype == object:
            out[col] = out[col].apply(
                lambda x: x.strftime("%Y-%m-%d")
                if isinstance(x, (date, datetime))
                else _normalize_txt(x)
            )

    out = out.where(pd.notnull(out), None)
    return out

# ==============================
# SAVE DATA
# ==============================

def salvar_dados(df: pd.DataFrame, nome_tabela: str) -> None:
    tabela = _tabela_from_nome_arquivo(nome_tabela)

    if df is None or df.empty:
        st.info(f"ℹ️ Nada para salvar em '{tabela}'.")
        return

    df = _prepare_df_for_rest(df)

    if "id" in df.columns:
        df = df.drop(columns=["id"])

    registros = df.to_dict(orient="records")

    # CHECKLIST → HISTÓRICO
    if tabela == "checklist":
        for reg in registros:
            try:
                table_insert(tabela, [reg])
            except Exception as e:
                st.error(f"Erro checklist: {e}")
                raise
        return

    # PADRÃO
    for reg in registros:
        try:
            table_upsert(tabela, [reg])
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            raise

# ==============================
# CRUD AUX
# ==============================

def inserir_um(tabela_ou_csv: str, registro: Dict[str, Any]) -> None:
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    reg = {k: _normalize_txt(v) for k, v in registro.items()}
    table_insert(tabela, [reg])


def atualizar_por_filtro(tabela_ou_csv: str, novos_dados: dict, filtro: dict) -> None:
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    table_update(tabela, filtro, novos_dados)


def deletar_por_filtro(tabela_ou_csv: str, filtro: Dict[str, Any]) -> None:
    tabela = _tabela_from_nome_arquivo(tabela_ou_csv)
    table_delete(tabela, filtro)

# ==============================
# DISTÂNCIA
# ==============================

def calcular_distancia_km(cep_origem, cep_destino):
    try:
        cep_origem = re.sub(r"\D", "", str(cep_origem))
        cep_destino = re.sub(r"\D", "", str(cep_destino))

        url = f"https://nominatim.openstreetmap.org/search?postalcode={cep_destino}&country=Brazil&format=json"

        r = requests.get(url, headers={"User-Agent": "App"})
        if r.status_code == 200 and r.json():
            destino = r.json()[0]
            lat2 = float(destino["lat"])
            lon2 = float(destino["lon"])
        else:
            return None

        # simplificado (sem geopy)
        return 0

    except:
        return None
