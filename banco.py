# banco.py — Camada de I/O no Supabase via REST (sem SDK)
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Iterable

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


def _chunked(iterable: List[Dict[str, Any]], size: int = 500) -> Iterable[List[Dict[str, Any]]]:
    """Gera blocos (chunks) para upload em lotes."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


# ===================================================
# NORMALIZAÇÃO E DETECÇÃO DE ERROS
# ===================================================

def _normalize_txt(x: Any) -> Any:
    """Normaliza texto para evitar variações: trim + collapse spaces."""
    if isinstance(x, str):
        x = " ".join(x.split()).strip()
        return x
    return x


def _is_duplicate_error(err: Exception) -> bool:
    """
    Heurística para detectar violação de UNIQUE por mensagem do Postgres/PostgREST.
    Tipicamente contém: 409 / 23505 / 'duplicate key value'.
    """
    msg = str(err) if err else ""
    msg_low = msg.lower()
    return (
        "duplicate key value" in msg_low
        or "status_code=409" in msg_low
        or " 409 " in msg_low
        or "23505" in msg_low
        or '"code":"23505"' in msg_low
        or "'code': '23505'" in msg_low
    )


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


def _prepare_df_for_rest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza um DataFrame para envio via REST:
    - converte datetimes para string
    - troca NaN por None
    - normaliza textos
    - não mexe em 'id' (exceto remoção opcional mais abaixo)
    """
    from datetime import date, datetime as _dt

    out = df.copy()

    # Datas → string (YYYY-MM-DD)
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
        elif out[col].dtype == object:
            out[col] = out[col].apply(
                lambda x: x.strftime("%Y-%m-%d")
                if isinstance(x, (date, _dt))
                else _normalize_txt(x)
            )

    # Remove NaN → None
    out = out.where(pd.notnull(out), None)
    return out


def salvar_dados(df: pd.DataFrame, nome_tabela: str) -> None:
    """
    Salva dados no Supabase.
    - pecas_brinquedos: insere 1 a 1 e ignora duplicadas (evita 409 com índice funcional).
    - checklist: UPSERT usando on_conflict = (reserva_id, brinquedo_norm, tipo_norm, item_norm).
                 Fallback: delete + insert do recorte quando on_conflict não for suportado.
    - demais tabelas: upsert linha a linha padrão.
    """
    tabela = _tabela_from_nome_arquivo(nome_tabela)
    if df is None or df.empty:
        st.info(f"ℹ️ Nada para salvar em '{tabela}'.")
        return

    df = _prepare_df_for_rest(df)

    # Evita conflitos com 'id'
    if "id" in df.columns:
        df = df.drop(columns=["id"])

    registros = df.to_dict(orient="records")

    # ============= Estratégia específica: PECAS_BRINQUEDOS =============
    if tabela == "pecas_brinquedos":
        inseridos = 0
        ignorados = 0
        for reg in registros:
            b = _normalize_txt(reg.get("Brinquedo", ""))
            i = _normalize_txt(reg.get("Item", ""))
            if not b or not i:
                continue
            try:
                table_insert(tabela, [{"Brinquedo": b, "Item": i}])
                inseridos += 1
            except Exception as e:
                if _is_duplicate_error(e):
                    ignorados += 1
                    continue
                st.error(f"❌ Erro ao salvar peça {reg}: {e}")
                logging.exception("Erro salvar_dados pecas_brinquedos")
                raise
        st.toast(f"💾 Peças salvas: {inseridos}. Duplicadas ignoradas: {ignorados}.", icon="✅")
        return

    # ============= Estratégia específica: CHECKLIST =============
    if tabela == "checklist":
        ok_count = 0
        fallback_count = 0
        for reg in registros:
            # Normaliza os campos textuais base (o Postgres vai gerar *_norm sozinho)
            reg = {k: _normalize_txt(v) for k, v in reg.items()}

            # 1) Tenta upsert com alvo de conflito correto (campos gerados)
            try:
                # Seu wrapper supabase_rest.table_upsert precisa aceitar
