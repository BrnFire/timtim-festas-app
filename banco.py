# banco.py — Camada de I/O no Supabase via REST (sem SDK)
from __future__ import annotations

import logging
import os
import json
import re
from datetime import date, datetime
from typing import Dict, Any, List, Optional

import pandas as pd
import requests

# Usa streamlit se existir; senão, cria um "dummy" pra não quebrar em testes locais
try:
    import streamlit as st
except Exception:  # pragma: no cover
    class _Dummy:
        def __getattr__(self, name):
            def _(*args, **kwargs):
                return None
            return _
    st = _Dummy()  # type: ignore

# Importa o wrapper REST já existente no projeto
from supabase_rest import (
    table_select,
    table_insert,
    table_update,
    table_delete,
    table_upsert,   # >>> garanta que aceita on_conflict="id"
)

# ===================================================
# CONFIG — tabelas nas quais sincronizamos deleções
# ===================================================

# Por padrão, SOMENTE pre_reservas fará deleção de IDs ausentes no df.
# Você pode sobrescrever via variável de ambiente, ex.: SYNC_DELETE_TABLES=pre_reservas,reservas
_env_whitelist = os.getenv("SYNC_DELETE_TABLES", "pre_reservas")
SYNC_DELETE_TABLES: set[str] = set(
    [t.strip().lower() for t in _env_whitelist.split(",") if t.strip()]
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
# NORMALIZAÇÃO
# ===================================================

def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Converte datas para ISO (yyyy-mm-dd) e NaN -> None."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
        elif df[col].dtype == object:
            df[col] = df[col].apply(
                lambda x: x.strftime("%Y-%m-%d")
                if isinstance(x, (date, datetime))
                else x
            )
    # NaN -> None
    df = df.where(pd.notnull(df), None)
    return df

def _stringify_or_none(v: Any) -> Optional[str]:
    """Transforma valores 'vazios' em None; do contrário, string."""
    if v in (None, "", "None", "nan", "NaN"):
        return None
    try:
        s = str(v)
        return None if s.strip() == "" else s
    except Exception:
        return None

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
            # aviso leve (não quebra telas)
            st.warning(f"⚠️ Nenhum dado retornado da tabela '{tabela}'.")
    except Exception as e:
        logging.exception("Erro ao carregar dados da tabela %s", tabela)
        st.error(f"❌ Erro ao carregar dados da tabela '{tabela}': {e}")

    return _ensure_columns(df, colunas)

def salvar_dados(df: pd.DataFrame, nome_tabela: str) -> None:
    """
    Sincroniza o conteúdo do DataFrame com a tabela do Supabase.

    Regras:
    - Se a tabela tiver coluna 'id':
        * Normaliza datas e NaN.
        * Padroniza 'id' como string (ou None).
        * Dedup por 'id' (mantém a última).
        * (Opcional) Deleção: se tabela estiver em SYNC_DELETE_TABLES,
          deleta IDs existentes no banco que não estão no df.
        * UPSERT em lote por 'id' (on_conflict='id') para TODOS os registros com id.
        * (Opcional) INSERT apenas para registros SEM id (se existirem).
    - Se NÃO tiver 'id':
        * Mantém comportamento simples (upsert/insert em lote), sem deletar.
    """
    tabela = _tabela_from_nome_arquivo(nome_tabela)
    df = _normalize_dataframe(df)

    tem_id = "id" in df.columns

    if tem_id:
        # padroniza id
        df["id"] = df["id"].apply(_stringify_or_none)
        # dedup por id (mantém a última) — None não se deduplica (pandas considera NaN únicos)
        df = df.drop_duplicates(subset=["id"], keep="last")

    # -----------------------
    # Sem 'id' -> compatibilidade
    # -----------------------
    if not tem_id:
        registros = df.to_dict(orient="records")
        for chunk in _chunked(registros, 500):
            # upsert genérico (sem on_conflict)
            table_upsert(tabela, chunk)
        st.toast(f"💾 {len(registros)} registro(s) salvos em '{tabela}'.", icon="✅")
        return

    # -----------------------
    # Com 'id' -> sync + upsert por id
    # -----------------------
    # 1) Buscar somente IDs do banco (menos payload)
    try:
        atuais = table_select(tabela)  # ideal: table_select(tabela, columns=['id'])
        df_atuais = pd.DataFrame(atuais) if atuais else pd.DataFrame(columns=["id"])
        if "id" not in df_atuais.columns:
            df_atuais["id"] = None
        df_atuais["id"] = df_atuais["id"].apply(_stringify_or_none)
    except Exception as e:
        logging.exception("Erro ao ler '%s' para sincronização: %s", tabela, e)
        st.error(f"❌ Erro ao ler '{tabela}' para salvar: {e}")
        return

    ids_no_banco = set([x for x in df_atuais["id"].dropna().tolist()])
    ids_no_df    = set([x for x in df["id"].dropna().tolist()])

    # 2) EXCLUSÕES (somente para tabelas em whitelist)
    deletados = 0
    if tabela in SYNC_DELETE_TABLES:
        ids_para_deletar = sorted(ids_no_banco - ids_no_df)
        for pid in ids_para_deletar:
            try:
                table_delete(tabela, {"id": pid})
                deletados += 1
            except Exception as e:
                logging.exception("Erro ao deletar id=%s em %s: %s", pid, tabela, e)
                st.error(f"❌ Erro ao deletar id={pid} em '{tabela}': {e}")

    # 3) UPSERT em lote por 'id' (SEM inserts duplicados)
    #    - todos os registros COM id vão em upsert com on_conflict='id'
    with_id_df = df[df["id"].notna()].copy()
    sem_id_df  = df[df["id"].isna()].copy()

    atualizados_ou_inseridos = 0

    if not with_id_df.empty:
        registros_id = with_id_df.to_dict(orient="records")
        for chunk in _chunked(registros_id, 500):
            # >>> GARANTA no supabase_rest.table_upsert que on_conflict vira '?on_conflict=id'
            table_upsert(tabela, chunk, on_conflict="id")
            atualizados_ou_inseridos += len(chunk)

    # 4) (Opcional) INSERT de registros SEM id (se ocorrer no seu fluxo)
    #    — para pré-reservas isso normalmente não acontece via UI.
    if not sem_id_df.empty:
        registros_sem_id = sem_id_df.to_dict(orient="records")
        for chunk in _chunked(registros_sem_id, 500):
            table_insert(tabela, chunk)
            atualizados_ou_inseridos += len(chunk)

    # 5) Feedback
    st.toast(
        f"💾 {tabela}: {atualizados_ou_inseridos} upsert/insert, {deletados} excluído(s).",
        icon="✅"
    )

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

        try:
            from geopy.distance import geodesic
        except Exception:
            return None  # se geopy não estiver instalado

        return round(geodesic(origem, destino).km, 1)

    except Exception as e:  # pragma: no cover
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
