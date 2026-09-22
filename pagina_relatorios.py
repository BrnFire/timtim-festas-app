# ==============================================================
# MÓDULO RELATÓRIOS E INDICADORES – TimTim Festas
# Arquivo independente. Mantém o nome pagina_relatorios().
#
# CORREÇÕES APLICADAS:
#   [1] Cards e gráficos agora usam a MESMA base (valor_total = bruto)
#       -> Sinal (já entrou) e Total (tudo que vai entrar) separados
#   [2] Lucro negativo aparece como negativo (sem clip(lower=0))
#   [3] Fim da dupla contagem: valor_total JÁ inclui extra+frete-desconto
#   [4] ano_sel agora filtra de verdade os gráficos
#   [5] return dentro da aba trocado por if/else (não aborta a página)
#   [6] Editor de metas só renderiza o ano selecionado (12 campos, não 36)
#   [7] Gráficos em Plotly (interativo, sem vazamento de memória)
#
# NOVOS INDICADORES:
#   - Comparativo com período anterior (sobre o bruto)
#   - Ticket médio mensal e anual
#   - Margem por categoria (Montessori x Tradicional)
#   - Origem do cliente (como_conseguiu)
#   - Projeção do mês corrente vs. meta
#   - Payback por brinquedo
#
# RATEIO: mantido IGUAL entre os itens da reserva (divisão simples),
#         pois nem todo brinquedo tem valor de locação individual.
#
# INSTALAÇÃO:
#   1) Salve como  relatorios.py  na mesma pasta do app.py
#   2) No app.py troque o import (ver final do arquivo)
#   3) Reinicie o Streamlit no terminal
# ==============================================================

VERSAO_MODULO = "v2"

import re
import calendar
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY = True
except ImportError:
    PLOTLY = False

from banco import carregar_dados, salvar_dados

# --------------------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------------------
CORES = {
    "roxo": "#7A5FFF",
    "verde": "#2ECC71",
    "vermelho": "#E74C3C",
    "azul": "#3498DB",
    "amarelo": "#F1C40F",
    "laranja": "#E67E22",
    "cinza": "#95A5A6",
    "rosa": "#E91E63",
}

META_PADRAO = 3000.0
ANO_INICIO_METAS = 2024
ANO_FIM_METAS = 2027

MESES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}

DIAS_PT = {
    0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta",
    4: "Sexta", 5: "Sábado", 6: "Domingo"
}

STATUS_IGNORADOS = {"cancelada", "cancelado", "recusada", "recusado"}

COLS_RESERVAS = [
    "id", "cliente", "brinquedos", "data",
    "valor_total", "valor_extra", "frete", "desconto",
    "sinal", "falta", "status"
]
COLS_CUSTOS = ["data", "descricao", "categoria", "valor"]
COLS_BRINQUEDOS = ["nome", "valor", "categoria", "valor_compra", "data_compra"]
COLS_CLIENTES = ["nome", "como_conseguiu", "cidade"]
COLS_METAS = ["anomes", "meta"]


# ==============================================================
# HELPERS
# ==============================================================
def _s(v, padrao=""):
    if v is None:
        return padrao
    try:
        if pd.isna(v):
            return padrao
    except (TypeError, ValueError):
        pass
    txt = str(v).strip()
    return padrao if txt.lower() in {"none", "nan", "nat"} else txt


def _num(serie):
    return pd.to_numeric(serie, errors="coerce").fillna(0.0)


def _rs(v):
    """Formata em Real brasileiro: 1234.5 -> 'R$ 1.234,50'"""
    try:
        txt = f"{float(v):,.2f}"
    except (TypeError, ValueError):
        txt = "0,00"
    return "R$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v, casas=1):
    try:
        return f"{float(v):.{casas}f}%"
    except (TypeError, ValueError):
        return "0,0%"


def parse_data_segura(v):
    try:
        if pd.isna(v) or str(v).strip() == "":
            return pd.NaT
        s = str(v).split(" ")[0]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return pd.to_datetime(datetime.strptime(s, fmt)).normalize()
            except ValueError:
                continue
        return pd.to_datetime(s, dayfirst=True, errors="coerce").normalize()
    except Exception:
        return pd.NaT


def _rotulo_mes(anomes: str) -> str:
    """'2026-09' -> 'Set/26'"""
    try:
        d = pd.to_datetime(anomes, format="%Y-%m")
        return f"{MESES_PT[d.month]}/{d.strftime('%y')}"
    except Exception:
        return str(anomes)


def _delta_pct(atual, anterior):
    """Variação percentual segura."""
    if anterior is None or anterior == 0:
        return None
    return (atual - anterior) / abs(anterior) * 100


def card(col, titulo, valor, cor, rodape=""):
    extra = (f"<div style='font-size:.78em;color:#777;margin-top:4px;'>{rodape}</div>"
             if rodape else "")
    col.markdown(
        f"""<div style="background:#f9f9f9;border-left:6px solid {cor};
             border-radius:10px;padding:14px;text-align:center;
             box-shadow:2px 2px 10px rgba(0,0,0,0.08);min-height:100px;">
             <div style="font-size:.88em;color:#555;">{titulo}</div>
             <div style="font-size:1.35em;font-weight:800;color:#222;">{valor}</div>
             {extra}</div>""",
        unsafe_allow_html=True
    )


def card_delta(col, titulo, valor, cor, delta, sufixo="vs. período anterior"):
    """Card com comparativo percentual."""
    if delta is None:
        rodape = "<span style='color:#999;'>sem base de comparação</span>"
    elif delta > 0.5:
        rodape = f"<span style='color:#2ECC71;font-weight:700;'>▲ {_pct(delta)}</span> {sufixo}"
    elif delta < -0.5:
        rodape = f"<span style='color:#E74C3C;font-weight:700;'>▼ {_pct(abs(delta))}</span> {sufixo}"
    else:
        rodape = f"<span style='color:#888;'>≈ estável</span> {sufixo}"
    card(col, titulo, valor, cor, rodape)


# ==============================================================
# CARGA E PREPARO DOS DADOS
# ==============================================================
@st.cache_data(ttl=120, show_spinner=False)
def _carregar_tudo():
    """Carrega e normaliza todas as bases de uma vez."""
    def _seguro(tabela, cols):
        try:
            df = carregar_dados(tabela, cols)
            return df.copy() if df is not None else pd.DataFrame(columns=cols)
        except Exception:
            return pd.DataFrame(columns=cols)

    reservas = _seguro("reservas", COLS_RESERVAS)
    custos = _seguro("custos", COLS_CUSTOS)
    brinquedos = _seguro("brinquedos", COLS_BRINQUEDOS)
    clientes = _seguro("clientes", COLS_CLIENTES)

    # ---------- RESERVAS ----------
    if not reservas.empty:
        reservas["data"] = reservas["data"].apply(parse_data_segura)
        reservas = reservas.dropna(subset=["data"])
        for c in ["valor_total", "valor_extra", "frete", "desconto", "sinal", "falta"]:
            if c not in reservas.columns:
                reservas[c] = 0.0
            reservas[c] = _num(reservas[c])
        reservas["status"] = reservas["status"].apply(_s)
        reservas = reservas[~reservas["status"].str.lower().isin(STATUS_IGNORADOS)]

        # [3] CORREÇÃO DA DUPLA CONTAGEM
        # valor_total JÁ inclui brinquedos + extra + frete - desconto
        reservas["bruto"] = reservas["valor_total"].clip(lower=0)

        # Se 'falta' estiver zerada/ausente, deriva de bruto - sinal
        reservas["recebido"] = reservas["sinal"].clip(lower=0)
        derivado = (reservas["bruto"] - reservas["recebido"]).clip(lower=0)
        reservas["a_receber"] = reservas["falta"].where(reservas["falta"] > 0, derivado)

        reservas["anomes"] = reservas["data"].dt.to_period("M").astype(str)
        reservas["ano"] = reservas["data"].dt.year
        reservas["mes"] = reservas["data"].dt.month
        reservas["dow"] = reservas["data"].dt.dayofweek

    # ---------- CUSTOS ----------
    if not custos.empty:
        custos["data"] = custos["data"].apply(parse_data_segura)
        custos = custos.dropna(subset=["data"])
        custos["valor"] = _num(custos.get("valor", 0))
        if "categoria" not in custos.columns:
            custos["categoria"] = "Outros"
        custos["categoria"] = custos["categoria"].apply(lambda x: _s(x, "Outros"))
        custos["anomes"] = custos["data"].dt.to_period("M").astype(str)
        custos["ano"] = custos["data"].dt.year

    # ---------- BRINQUEDOS ----------
    if not brinquedos.empty:
        brinquedos["nome"] = brinquedos["nome"].apply(_s)
        brinquedos["categoria"] = brinquedos["categoria"].apply(
            lambda x: _s(x, "Tradicional") or "Tradicional")
        for c in ["valor", "valor_compra"]:
            if c not in brinquedos.columns:
                brinquedos[c] = 0.0
            brinquedos[c] = _num(brinquedos[c])
        if "data_compra" in brinquedos.columns:
            brinquedos["data_compra"] = brinquedos["data_compra"].apply(parse_data_segura)

    # ---------- CLIENTES ----------
    if not clientes.empty:
        clientes["nome"] = clientes["nome"].apply(_s)
        clientes["como_conseguiu"] = clientes["como_conseguiu"].apply(
            lambda x: _s(x, "Não informado") or "Não informado")

    return reservas, custos, brinquedos, clientes


def consolidar_mensal(reservas: pd.DataFrame, custos: pd.DataFrame) -> pd.DataFrame:
    """
    Consolidado mês a mês.
    [2] CORREÇÃO: líquido pode ser NEGATIVO (sem clip).
    """
    partes = []
    if not reservas.empty:
        r = reservas.groupby("anomes", as_index=False).agg(
            bruto=("bruto", "sum"),
            recebido=("recebido", "sum"),
            a_receber=("a_receber", "sum"),
            reservas=("bruto", "count"),
        )
        partes.append(r)
    if not custos.empty:
        c = custos.groupby("anomes", as_index=False).agg(custo=("valor", "sum"))
        partes.append(c)

    if not partes:
        return pd.DataFrame(columns=["anomes", "bruto", "recebido", "a_receber",
                                     "reservas", "custo", "liquido", "margem", "ticket"])

    df = partes[0]
    for p in partes[1:]:
        df = pd.merge(df, p, on="anomes", how="outer")
    df = df.fillna(0)

    for c in ["bruto", "recebido", "a_receber", "reservas", "custo"]:
        if c not in df.columns:
            df[c] = 0.0

    df["liquido"] = df["bruto"] - df["custo"]            # [2] pode ser negativo
    df["margem"] = df.apply(
        lambda r: (r["liquido"] / r["bruto"] * 100) if r["bruto"] > 0 else 0.0, axis=1)
    df["ticket"] = df.apply(
        lambda r: (r["bruto"] / r["reservas"]) if r["reservas"] > 0 else 0.0, axis=1)
    df["rotulo"] = df["anomes"].apply(_rotulo_mes)
    df["data_plot"] = pd.to_datetime(df["anomes"], format="%Y-%m", errors="coerce")
    return df.sort_values("data_plot").reset_index(drop=True)


def explodir_itens(reservas: pd.DataFrame, brinquedos: pd.DataFrame) -> pd.DataFrame:
    """
    Uma linha por brinquedo de cada reserva.
    RATEIO IGUAL entre os itens (mantido a pedido — nem todo item tem valor próprio).
    [3] usa 'bruto' (valor_total), sem somar extra/frete de novo.
    """
    if reservas.empty:
        return pd.DataFrame(columns=["brinquedo", "data", "anomes", "ano",
                                     "valor_item", "categoria", "cliente"])

    linhas = []
    for _, r in reservas.iterrows():
        itens = [b.strip() for b in str(r.get("brinquedos", "")).split(",") if b.strip()]
        if not itens:
            continue
        valor_item = float(r["bruto"]) / len(itens)      # rateio igual
        for b in itens:
            linhas.append({
                "brinquedo": b,
                "data": r["data"],
                "anomes": r["anomes"],
                "ano": r["ano"],
                "valor_item": valor_item,
                "cliente": _s(r.get("cliente")),
            })

    df = pd.DataFrame(linhas)
    if df.empty:
        return df

    if not brinquedos.empty:
        cat = brinquedos[["nome", "categoria"]].drop_duplicates(subset=["nome"])
        df = df.merge(cat, left_on="brinquedo", right_on="nome", how="left")
        df.drop(columns=["nome"], inplace=True, errors="ignore")
    if "categoria" not in df.columns:
        df["categoria"] = "Tradicional"
    df["categoria"] = df["categoria"].fillna("Tradicional")
    df["valor_item"] = _num(df["valor_item"])
    return df


# ==============================================================
# GRÁFICOS (Plotly — [7] interativo e sem vazar memória)
# ==============================================================
def _sem_plotly():
    st.warning("📊 Plotly não instalado. Rode: `pip install plotly` para os gráficos interativos.")


def grafico_linha_financeiro(df: pd.DataFrame, df_meta: pd.DataFrame, titulo: str):
    if not PLOTLY:
        _sem_plotly()
        st.line_chart(df.set_index("rotulo")[["bruto", "liquido"]])
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["rotulo"], y=df["bruto"], name="Faturamento Bruto",
        mode="lines+markers", line=dict(color=CORES["azul"], width=3),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Bruto: R$ %{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=df["rotulo"], y=df["liquido"], name="Lucro Líquido",
        mode="lines+markers", line=dict(color=CORES["verde"], width=3),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Líquido: R$ %{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=df["rotulo"], y=df["custo"], name="Custos",
        mode="lines+markers", line=dict(color=CORES["vermelho"], width=2, dash="dot"),
        marker=dict(size=6),
        hovertemplate="<b>%{x}</b><br>Custos: R$ %{y:,.2f}<extra></extra>"))

    if df_meta is not None and not df_meta.empty:
        m = df.merge(df_meta, on="anomes", how="left")
        fig.add_trace(go.Scatter(
            x=m["rotulo"], y=m["meta"], name="Meta",
            mode="lines", line=dict(color=CORES["laranja"], width=2, dash="dash"),
            hovertemplate="<b>%{x}</b><br>Meta: R$ %{y:,.2f}<extra></extra>"))

    # [2] linha do zero, já que o líquido pode ser negativo
    fig.add_hline(y=0, line_color="#999", line_width=1)
    fig.update_layout(
        title=titulo, height=430, hovermode="x unified",
        yaxis_title="R$", xaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=70, b=10), plot_bgcolor="#FAFAFA",
    )
    fig.update_yaxes(gridcolor="#EEE", zeroline=True, zerolinecolor="#BBB")
    st.plotly_chart(fig, use_container_width=True)


def grafico_barras_margem(df: pd.DataFrame):
    if not PLOTLY:
        _sem_plotly()
        return
    cores = [CORES["verde"] if v >= 0 else CORES["vermelho"] for v in df["liquido"]]
    fig = go.Figure(go.Bar(
        x=df["rotulo"], y=df["liquido"], marker_color=cores,
        text=[_rs(v) for v in df["liquido"]], textposition="outside",
        hovertemplate="<b>%{x}</b><br>Líquido: R$ %{y:,.2f}<extra></extra>"))
    fig.add_hline(y=0, line_color="#666", line_width=1.5)
    fig.update_layout(
        title="Lucro Líquido por Mês (vermelho = prejuízo)",
        height=380, yaxis_title="R$", margin=dict(l=10, r=10, t=60, b=10),
        plot_bgcolor="#FAFAFA", showlegend=False)
    fig.update_yaxes(gridcolor="#EEE")
    st.plotly_chart(fig, use_container_width=True)


def grafico_barras_h(df, col_cat, col_val, titulo, cor, eixo="", moeda=False):
    if not PLOTLY:
        _sem_plotly()
        st.bar_chart(df.set_index(col_cat)[col_val])
        return
    d = df.sort_values(col_val, ascending=True)
    textos = [_rs(v) if moeda else f"{int(v)}" for v in d[col_val]]
    fmt = "R$ %{x:,.2f}" if moeda else "%{x}"
    fig = go.Figure(go.Bar(
        x=d[col_val], y=d[col_cat], orientation="h", marker_color=cor,
        text=textos, textposition="outside",
        hovertemplate="<b>%{y}</b><br>" + fmt + "<extra></extra>"))
    fig.update_layout(
        title=titulo, height=max(320, 26 * len(d) + 110),
        xaxis_title=eixo, margin=dict(l=10, r=60, t=60, b=10),
        plot_bgcolor="#FAFAFA", showlegend=False)
    fig.update_xaxes(gridcolor="#EEE")
    st.plotly_chart(fig, use_container_width=True)


def grafico_pizza(df, col_cat, col_val, titulo, moeda=True):
    if not PLOTLY:
        _sem_plotly()
        return
    fmt = "R$ %{value:,.2f}" if moeda else "%{value}"
    fig = go.Figure(go.Pie(
        labels=df[col_cat], values=df[col_val], hole=0.45,
        marker=dict(colors=[CORES["roxo"], CORES["verde"], CORES["azul"],
                            CORES["amarelo"], CORES["laranja"], CORES["rosa"],
                            CORES["cinza"], CORES["vermelho"]]),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>" + fmt + "<br>%{percent}<extra></extra>"))
    fig.update_layout(title=titulo, height=400, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ==============================================================
# PÁGINA PRINCIPAL
# ==============================================================
def pagina_relatorios():
    st.header("📈 Relatórios e Indicadores")
    st.caption(f"Módulo {VERSAO_MODULO} · gráficos interativos · "
               "Bruto = valor total da reserva | Sinal = já recebido")

    with st.spinner("Carregando dados..."):
        reservas, custos, brinquedos, clientes = _carregar_tudo()

    if reservas.empty and custos.empty:
        st.warning("Ainda não há dados suficientes para montar os indicadores.")
        return

    mensal = consolidar_mensal(reservas, custos)
    itens = explodir_itens(reservas, brinquedos)

    hoje = pd.Timestamp.now()
    anomes_atual = hoje.to_period("M").strftime("%Y-%m")

    # ==========================================================
    # FILTRO DE PERÍODO
    # ==========================================================
    st.markdown("#### 📅 Período dos indicadores")
    fc1, fc2 = st.columns([2, 2])
    with fc1:
        tipo_periodo = st.radio(
            "Visualização:", ["Mês atual", "Selecionar mês", "Ano atual", "Tudo"],
            horizontal=True, key="rel_tipo_periodo", label_visibility="collapsed"
        )

    mes_sel = None
    with fc2:
        if tipo_periodo == "Selecionar mês":
            disp = sorted(mensal["anomes"].unique(), reverse=True)
            if disp:
                mes_sel = st.selectbox("Mês:", disp, format_func=_rotulo_mes,
                                       key="rel_mes_sel", label_visibility="collapsed")

    # ---------- Recorte atual e ANTERIOR (para o comparativo) ----------
    def _fatiar(df, col_anomes="anomes", col_ano="ano"):
        if df.empty:
            return df, df
        if tipo_periodo == "Mês atual":
            atual = df[df[col_anomes] == anomes_atual]
            ant_mes = (hoje.to_period("M") - 1).strftime("%Y-%m")
            anterior = df[df[col_anomes] == ant_mes]
        elif tipo_periodo == "Selecionar mês" and mes_sel:
            atual = df[df[col_anomes] == mes_sel]
            ant_mes = (pd.Period(mes_sel, freq="M") - 1).strftime("%Y-%m")
            anterior = df[df[col_anomes] == ant_mes]
        elif tipo_periodo == "Ano atual":
            atual = df[df[col_ano] == hoje.year]
            anterior = df[df[col_ano] == hoje.year - 1]
        else:
            atual = df
            anterior = df.iloc[0:0]
        return atual, anterior

    res_at, res_ant = _fatiar(reservas)
    cus_at, cus_ant = _fatiar(custos)
    itens_at, _ = _fatiar(itens)

    rotulo_periodo = {
        "Mês atual": f"{MESES_PT[hoje.month]}/{hoje.year}",
        "Selecionar mês": _rotulo_mes(mes_sel) if mes_sel else "-",
        "Ano atual": str(hoje.year),
        "Tudo": "Histórico completo",
    }[tipo_periodo]

    sufixo_comp = {
        "Mês atual": "vs. mês anterior",
        "Selecionar mês": "vs. mês anterior",
        "Ano atual": "vs. ano anterior",
        "Tudo": "",
    }[tipo_periodo]

    # ==========================================================
    # CARDS PRINCIPAIS
    # ==========================================================
    bruto = float(res_at["bruto"].sum()) if not res_at.empty else 0.0
    recebido = float(res_at["recebido"].sum()) if not res_at.empty else 0.0
    a_receber = float(res_at["a_receber"].sum()) if not res_at.empty else 0.0
    custo_tot = float(cus_at["valor"].sum()) if not cus_at.empty else 0.0
    liquido = bruto - custo_tot                      # [2] pode ser negativo
    qtd = len(res_at)
    ticket = bruto / qtd if qtd else 0.0
    margem = (liquido / bruto * 100) if bruto > 0 else 0.0

    bruto_ant = float(res_ant["bruto"].sum()) if not res_ant.empty else 0.0
    custo_ant = float(cus_ant["valor"].sum()) if not cus_ant.empty else 0.0
    qtd_ant = len(res_ant)
    ticket_ant = bruto_ant / qtd_ant if qtd_ant else 0.0

    st.markdown(f"##### 💼 {rotulo_periodo}")

    l1c1, l1c2, l1c3, l1c4 = st.columns(4)
    # [1] Sinal e Total agora são cards SEPARADOS e explícitos
    card_delta(l1c1, "📊 Total do Período<br><small>(tudo que vai entrar)</small>",
               _rs(bruto), CORES["azul"], _delta_pct(bruto, bruto_ant), sufixo_comp)
    card(l1c2, "💰 Sinal Recebido<br><small>(já entrou no caixa)</small>",
         _rs(recebido), CORES["verde"],
         f"{_pct(recebido / bruto * 100) if bruto else '0,0%'} do total")
    card(l1c3, "⏳ A Receber<br><small>(falta entrar)</small>",
         _rs(a_receber), CORES["laranja"],
         f"{qtd} reserva(s) no período")
    card_delta(l1c4, "📉 Custos Totais", _rs(custo_tot), CORES["vermelho"],
               _delta_pct(custo_tot, custo_ant), sufixo_comp)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    l2c1, l2c2, l2c3, l2c4 = st.columns(4)
    cor_liq = CORES["verde"] if liquido >= 0 else CORES["vermelho"]
    icone_liq = "📈" if liquido >= 0 else "🔻"
    card(l2c1, f"{icone_liq} Lucro Líquido<br><small>(bruto − custos)</small>",
         _rs(liquido), cor_liq,
         "prejuízo no período" if liquido < 0 else "resultado positivo")
    card(l2c2, "📐 Margem Líquida", _pct(margem),
         CORES["roxo"] if margem >= 0 else CORES["vermelho"],
         "lucro sobre o faturamento")
    card_delta(l2c3, "🎟️ Reservas", f"{qtd}", CORES["amarelo"],
               _delta_pct(qtd, qtd_ant), sufixo_comp)
    card_delta(l2c4, "🎯 Ticket Médio", _rs(ticket), CORES["rosa"],
               _delta_pct(ticket, ticket_ant), sufixo_comp)

    if liquido < 0:
        st.error(f"🔻 **Prejuízo de {_rs(abs(liquido))}** em {rotulo_periodo} — "
                 f"os custos superaram o faturamento.")

    st.divider()

    # ==========================================================
    # ABAS
    # ==========================================================
    ab_fin, ab_proj, ab_brinq, ab_cat, ab_orig, ab_pay = st.tabs([
        "📊 Financeiro", "🎯 Projeção & Metas", "🎠 Brinquedos",
        "🏷️ Categorias", "📣 Origem", "💵 Payback"
    ])

    # ----------------------------------------------------------
    # ABA 1 — FINANCEIRO
    # ----------------------------------------------------------
    with ab_fin:
        if mensal.empty:
            st.info("Sem dados mensais consolidados.")
        else:
            anos_disp = sorted(mensal["data_plot"].dt.year.dropna().unique().astype(int))
            c1, c2 = st.columns([1, 3])
            with c1:
                # [4] o ano agora FILTRA de verdade
                opcoes_ano = ["Todos"] + [str(a) for a in anos_disp]
                idx_pad = len(opcoes_ano) - 1
                ano_sel = st.selectbox("Ano:", opcoes_ano, index=idx_pad, key="rel_ano_fin")

            if ano_sel == "Todos":
                df_graf = mensal.copy()
                titulo = "Evolução financeira — histórico completo"
            else:
                df_graf = mensal[mensal["data_plot"].dt.year == int(ano_sel)].copy()
                titulo = f"Evolução financeira — {ano_sel}"

            if df_graf.empty:
                st.info("Sem dados para o ano selecionado.")
            else:
                df_meta = _obter_metas()
                grafico_linha_financeiro(df_graf, df_meta, titulo)
                grafico_barras_margem(df_graf)

                # ----- Margem % por mês -----
                if PLOTLY:
                    fig = go.Figure(go.Scatter(
                        x=df_graf["rotulo"], y=df_graf["margem"],
                        mode="lines+markers", line=dict(color=CORES["roxo"], width=3),
                        marker=dict(size=8), fill="tozeroy",
                        fillcolor="rgba(122,95,255,.12)",
                        hovertemplate="<b>%{x}</b><br>Margem: %{y:.1f}%<extra></extra>"))
                    fig.add_hline(y=0, line_color="#666", line_width=1)
                    fig.update_layout(
                        title="Margem Líquida (%) por Mês", height=330,
                        yaxis_title="%", margin=dict(l=10, r=10, t=60, b=10),
                        plot_bgcolor="#FAFAFA", showlegend=False)
                    fig.update_yaxes(gridcolor="#EEE")
                    st.plotly_chart(fig, use_container_width=True)

                # ----- Ticket médio mensal -----
                st.markdown("##### 🎯 Ticket Médio Mensal")
                if PLOTLY:
                    fig = go.Figure(go.Bar(
                        x=df_graf["rotulo"], y=df_graf["ticket"],
                        marker_color=CORES["rosa"],
                        text=[_rs(v) for v in df_graf["ticket"]],
                        textposition="outside",
                        hovertemplate="<b>%{x}</b><br>Ticket: R$ %{y:,.2f}<extra></extra>"))
                    media_t = df_graf["ticket"].replace(0, pd.NA).mean()
                    if pd.notna(media_t):
                        fig.add_hline(y=media_t, line_dash="dash",
                                      line_color=CORES["roxo"],
                                      annotation_text=f"Média: {_rs(media_t)}")
                    fig.update_layout(height=350, yaxis_title="R$",
                                      margin=dict(l=10, r=10, t=40, b=10),
                                      plot_bgcolor="#FAFAFA", showlegend=False)
                    fig.update_yaxes(gridcolor="#EEE")
                    st.plotly_chart(fig, use_container_width=True)

                # ----- Ticket médio ANUAL -----
                st.markdown("##### 📆 Ticket Médio Anual")
                if not reservas.empty:
                    anual = reservas.groupby("ano", as_index=False).agg(
                        bruto=("bruto", "sum"), qtd=("bruto", "count"))
                    anual["ticket"] = anual["bruto"] / anual["qtd"]
                    anual["ano_txt"] = anual["ano"].astype(str)
                    tab = anual[["ano_txt", "qtd", "bruto", "ticket"]].copy()
                    tab.columns = ["Ano", "Reservas", "Faturamento", "Ticket Médio"]
                    tab["Faturamento"] = tab["Faturamento"].apply(_rs)
                    tab["Ticket Médio"] = tab["Ticket Médio"].apply(_rs)
                    st.dataframe(tab, use_container_width=True, hide_index=True)

                # ----- Tabela consolidada -----
                with st.expander("📋 Tabela mensal detalhada"):
                    t = df_graf[["rotulo", "reservas", "bruto", "recebido",
                                 "a_receber", "custo", "liquido", "margem", "ticket"]].copy()
                    t.columns = ["Mês", "Reservas", "Bruto", "Recebido",
                                 "A Receber", "Custos", "Líquido", "Margem %", "Ticket"]
                    for c in ["Bruto", "Recebido", "A Receber", "Custos", "Líquido", "Ticket"]:
                        t[c] = t[c].apply(_rs)
                    t["Margem %"] = t["Margem %"].apply(lambda v: _pct(v))
                    st.dataframe(t, use_container_width=True, hide_index=True)

                # ----- Custos por categoria -----
                if not cus_at.empty:
                    st.markdown("##### 📉 Custos por Categoria no período")
                    cc = cus_at.groupby("categoria", as_index=False)["valor"].sum()
                    cc = cc.sort_values("valor", ascending=False)
                    g1, g2 = st.columns([3, 2])
                    with g1:
                        grafico_barras_h(cc.head(12), "categoria", "valor",
                                         "Onde o dinheiro está saindo",
                                         CORES["vermelho"], "R$", moeda=True)
                    with g2:
                        grafico_pizza(cc.head(8), "categoria", "valor",
                                      "Distribuição dos custos")

    # ----------------------------------------------------------
    # ABA 2 — PROJEÇÃO & METAS
    # ----------------------------------------------------------
    with ab_proj:
        st.subheader("🎯 Projeção do Mês Corrente")

        mes_ini = hoje.replace(day=1).normalize()
        _, ult_dia = calendar.monthrange(hoje.year, hoje.month)
        mes_fim = hoje.replace(day=ult_dia).normalize()
        dias_no_mes = ult_dia
        dia_hoje = hoje.day
        dias_restantes = dias_no_mes - dia_hoje

        if reservas.empty:
            st.info("Sem reservas para projetar.")
        else:
            mes_todo = reservas[reservas["anomes"] == anomes_atual]
            realizado = mes_todo[mes_todo["data"] <= hoje.normalize()]
            futuro = mes_todo[mes_todo["data"] > hoje.normalize()]

            bruto_real = float(realizado["bruto"].sum())
            bruto_fut = float(futuro["bruto"].sum())
            bruto_conf = bruto_real + bruto_fut       # já contratado

            # Projeção por ritmo diário do que já aconteceu
            ritmo = bruto_real / dia_hoje if dia_hoje else 0
            proj_ritmo = ritmo * dias_no_mes
            # Cenário realista: o maior entre já contratado e ritmo
            projecao = max(bruto_conf, proj_ritmo)

            custo_mes = float(custos[custos["anomes"] == anomes_atual]["valor"].sum()) \
                if not custos.empty else 0.0

            df_meta = _obter_metas()
            meta_mes = META_PADRAO
            if df_meta is not None and not df_meta.empty:
                linha = df_meta[df_meta["anomes"] == anomes_atual]
                if not linha.empty:
                    meta_mes = float(linha.iloc[0]["meta"])

            p1, p2, p3, p4 = st.columns(4)
            card(p1, "✅ Já Realizado<br><small>(eventos até hoje)</small>",
                 _rs(bruto_real), CORES["verde"],
                 f"{len(realizado)} evento(s) · dia {dia_hoje}/{dias_no_mes}")
            card(p2, "📅 Já Contratado<br><small>(eventos futuros do mês)</small>",
                 _rs(bruto_fut), CORES["azul"],
                 f"{len(futuro)} evento(s) · {dias_restantes} dia(s) restante(s)")
            card(p3, "🔮 Projeção do Mês", _rs(projecao), CORES["roxo"],
                 f"ritmo atual: {_rs(proj_ritmo)}")
            atingido = (projecao / meta_mes * 100) if meta_mes else 0
            cor_meta = (CORES["verde"] if atingido >= 100
                        else CORES["amarelo"] if atingido >= 70 else CORES["vermelho"])
            card(p4, "🎯 Meta do Mês", _rs(meta_mes), cor_meta,
                 f"projeção atinge {_pct(atingido)}")

            # Barra de progresso
            prog = min(atingido, 100)
            falta_meta = max(meta_mes - projecao, 0)
            st.markdown(
                f"""<div style="margin:18px 0 6px 0;background:#eee;border-radius:10px;
                     overflow:hidden;height:26px;">
                     <div style="height:26px;width:{prog:.1f}%;background:{cor_meta};
                          transition:width .8s ease;border-radius:10px;"></div></div>
                     <p style="color:#555;font-size:14px;">
                     🎯 <b>{_pct(atingido)}</b> da meta projetada
                     {'— faltam <b>' + _rs(falta_meta) + '</b> para bater' if falta_meta > 0
                      else '— <b>meta batida!</b> 🎉'}</p>""",
                unsafe_allow_html=True)

            liq_proj = projecao - custo_mes
            st.caption(f"Custos do mês até agora: {_rs(custo_mes)} · "
                       f"Líquido projetado: **{_rs(liq_proj)}**")

            if bruto_fut > 0:
                with st.expander(f"📅 {len(futuro)} evento(s) ainda por realizar neste mês"):
                    f = futuro[["data", "cliente", "bruto", "recebido", "a_receber"]].copy()
                    f = f.sort_values("data")
                    f["data"] = f["data"].dt.strftime("%d/%m (%a)")
                    f.columns = ["Data", "Cliente", "Valor", "Recebido", "A Receber"]
                    for c in ["Valor", "Recebido", "A Receber"]:
                        f[c] = f[c].apply(_rs)
                    st.dataframe(f, use_container_width=True, hide_index=True)

        st.divider()

        # ----- Editor de metas [6] só o ano escolhido -----
        st.subheader("🎯 Metas Mensais")
        df_meta = _obter_metas()
        anos_meta = sorted({int(a[:4]) for a in df_meta["anomes"] if len(str(a)) >= 4})
        if not anos_meta:
            anos_meta = [hoje.year]
        idx_ano = anos_meta.index(hoje.year) if hoje.year in anos_meta else len(anos_meta) - 1
        ano_meta = st.selectbox("Ano das metas:", anos_meta, index=idx_ano, key="rel_ano_meta")

        sub = df_meta[df_meta["anomes"].str.startswith(str(ano_meta))].copy()
        sub = sub.sort_values("anomes").reset_index(drop=True)

        with st.form("form_metas"):
            st.caption(f"Editando as metas de {ano_meta} — 12 meses.")
            novos = {}
            linhas_cols = st.columns(3)
            for i, row in sub.iterrows():
                col = linhas_cols[i % 3]
                anomes = _s(row["anomes"])
                try:
                    mnum = int(anomes[5:7])
                    rotulo = f"{MESES_PT[mnum]}/{anomes[2:4]}"
                except Exception:
                    rotulo = anomes
                try:
                    val = float(row["meta"])
                except (TypeError, ValueError):
                    val = META_PADRAO
                novos[anomes] = col.number_input(
                    rotulo, min_value=0.0, value=val, step=100.0,
                    key=f"rel_meta_{anomes}")

            if st.form_submit_button("💾 Salvar metas do ano"):
                try:
                    completo = df_meta.copy()
                    for anomes, val in novos.items():
                        completo.loc[completo["anomes"] == anomes, "meta"] = float(val)
                    completo = completo.drop_duplicates(subset=["anomes"], keep="last")
                    salvar_dados(completo, "metas")
                    st.cache_data.clear()
                    st.success("✅ Metas atualizadas!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar metas: {e}")

        # ----- Realizado x Meta do ano -----
        if not mensal.empty and PLOTLY:
            comp = mensal[mensal["data_plot"].dt.year == ano_meta].merge(
                df_meta, on="anomes", how="right")
            comp = comp[comp["anomes"].str.startswith(str(ano_meta))].copy()
            comp["rotulo"] = comp["anomes"].apply(_rotulo_mes)
            comp["bruto"] = _num(comp.get("bruto", 0))
            comp["meta"] = _num(comp["meta"])
            comp = comp.sort_values("anomes")

            fig = go.Figure()
            fig.add_trace(go.Bar(x=comp["rotulo"], y=comp["meta"], name="Meta",
                                 marker_color="rgba(230,126,34,.35)"))
            fig.add_trace(go.Bar(x=comp["rotulo"], y=comp["bruto"], name="Realizado",
                                 marker_color=CORES["azul"]))
            fig.update_layout(
                title=f"Realizado × Meta — {ano_meta}", barmode="overlay",
                height=380, yaxis_title="R$",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                margin=dict(l=10, r=10, t=70, b=10), plot_bgcolor="#FAFAFA")
            fig.update_yaxes(gridcolor="#EEE")
            st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------------
    # ABA 3 — BRINQUEDOS  [5] sem return que aborta
    # ----------------------------------------------------------
    with ab_brinq:
        st.subheader("🎠 Desempenho de Brinquedos")
        st.caption("Rateio igual do valor da reserva entre os itens "
                   "(nem todo brinquedo tem valor de locação individual).")

        if itens_at.empty:
            st.info("Sem dados de brinquedos no período selecionado.")
        else:
            rank = (itens_at.groupby("brinquedo", as_index=False)
                    .agg(locacoes=("valor_item", "count"),
                         valor=("valor_item", "sum"))
                    .sort_values("locacoes", ascending=False))

            b1, b2, b3 = st.columns(3)
            card(b1, "🎪 Itens Locados", f"{int(rank['locacoes'].sum())}", CORES["roxo"])
            card(b2, "🎠 Modelos Diferentes", f"{len(rank)}", CORES["azul"])
            mais = rank.iloc[0] if not rank.empty else None
            card(b3, "🏆 Mais Locado",
                 f"{mais['brinquedo'][:22]}" if mais is not None else "-",
                 CORES["verde"],
                 f"{int(mais['locacoes'])} locações" if mais is not None else "")

            st.markdown("")
            # ✅ Mantido apenas o ranking por LOCAÇÕES (removido o por valor)
            grafico_barras_h(rank.head(15), "brinquedo", "locacoes",
                             "🔢 Top 15 Brinquedos por Locações",
                             CORES["verde"], "Locações", moeda=False)

            # ----- Nunca locados -----
            if not brinquedos.empty:
                locados = set(rank["brinquedo"].str.strip().str.lower())
                parados = brinquedos[~brinquedos["nome"].str.strip().str.lower().isin(locados)]
                if not parados.empty:
                    with st.expander(f"💤 {len(parados)} brinquedo(s) sem locação no período"):
                        p = parados[["nome", "categoria", "valor_compra"]].copy()
                        p.columns = ["Brinquedo", "Categoria", "Valor de Compra"]
                        p["Valor de Compra"] = p["Valor de Compra"].apply(_rs)
                        st.dataframe(p, use_container_width=True, hide_index=True)

            with st.expander("📋 Ranking completo"):
                t = rank.copy()
                t["valor"] = t["valor"].apply(_rs)
                t.columns = ["Brinquedo", "Locações", "Receita Rateada"]
                st.dataframe(t, use_container_width=True, hide_index=True)

            # ----- Sazonalidade -----
            st.divider()
            st.markdown("##### 📆 Quando as festas acontecem")
            if not res_at.empty and PLOTLY:
                s1, s2 = st.columns(2)
                with s1:
                    dow = res_at.groupby("dow", as_index=False).agg(qtd=("bruto", "count"))
                    dow["dia"] = dow["dow"].map(DIAS_PT)
                    dow = dow.sort_values("dow")
                    fig = go.Figure(go.Bar(
                        x=dow["dia"], y=dow["qtd"], marker_color=CORES["amarelo"],
                        text=dow["qtd"], textposition="outside",
                        hovertemplate="<b>%{x}</b><br>%{y} reserva(s)<extra></extra>"))
                    fig.update_layout(title="Por dia da semana", height=330,
                                      margin=dict(l=10, r=10, t=60, b=10),
                                      plot_bgcolor="#FAFAFA", showlegend=False)
                    fig.update_yaxes(gridcolor="#EEE")
                    st.plotly_chart(fig, use_container_width=True)
                with s2:
                    mm = reservas.groupby("mes", as_index=False).agg(qtd=("bruto", "count"))
                    mm["mes_txt"] = mm["mes"].map(MESES_PT)
                    mm = mm.sort_values("mes")
                    fig = go.Figure(go.Bar(
                        x=mm["mes_txt"], y=mm["qtd"], marker_color=CORES["laranja"],
                        text=mm["qtd"], textposition="outside",
                        hovertemplate="<b>%{x}</b><br>%{y} reserva(s)<extra></extra>"))
                    fig.update_layout(title="Por mês (histórico completo)", height=330,
                                      margin=dict(l=10, r=10, t=60, b=10),
                                      plot_bgcolor="#FAFAFA", showlegend=False)
                    fig.update_yaxes(gridcolor="#EEE")
                    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------------
    # ABA 4 — MARGEM POR CATEGORIA
    # ----------------------------------------------------------
    with ab_cat:
        st.subheader("🏷️ Margem por Categoria")
        st.caption("Receita por categoria via rateio. Os custos gerais são distribuídos "
                   "proporcionalmente à receita de cada categoria.")

        if itens_at.empty:
            st.info("Sem dados de categoria no período.")
        else:
            cat = (itens_at.groupby("categoria", as_index=False)
                   .agg(receita=("valor_item", "sum"),
                        locacoes=("valor_item", "count")))
            total_rec = cat["receita"].sum()

            if total_rec <= 0:
                st.info("Sem receita registrada no período.")
            else:
                cat["participacao"] = cat["receita"] / total_rec * 100
                # Rateio dos custos proporcional à receita
                cat["custo_rateado"] = cat["receita"] / total_rec * custo_tot
                cat["liquido"] = cat["receita"] - cat["custo_rateado"]
                cat["margem"] = cat.apply(
                    lambda r: (r["liquido"] / r["receita"] * 100) if r["receita"] > 0 else 0,
                    axis=1)
                cat["ticket_item"] = cat["receita"] / cat["locacoes"]
                cat = cat.sort_values("receita", ascending=False)

                cols = st.columns(len(cat))
                for col, (_, r) in zip(cols, cat.iterrows()):
                    cor = CORES["azul"] if _s(r["categoria"]).lower() == "montessori" \
                        else CORES["roxo"]
                    card(col, f"🏷️ {r['categoria']}", _rs(r["receita"]), cor,
                         f"{_pct(r['participacao'])} da receita · "
                         f"margem {_pct(r['margem'])}")

                st.markdown("")
                g1, g2 = st.columns(2)
                with g1:
                    grafico_pizza(cat, "categoria", "receita",
                                  "Participação na receita")
                with g2:
                    if PLOTLY:
                        fig = go.Figure()
                        fig.add_trace(go.Bar(x=cat["categoria"], y=cat["receita"],
                                             name="Receita", marker_color=CORES["azul"]))
                        fig.add_trace(go.Bar(x=cat["categoria"], y=cat["custo_rateado"],
                                             name="Custo rateado",
                                             marker_color=CORES["vermelho"]))
                        fig.add_trace(go.Bar(x=cat["categoria"], y=cat["liquido"],
                                             name="Líquido", marker_color=CORES["verde"]))
                        fig.update_layout(
                            title="Receita × Custo × Líquido", barmode="group",
                            height=400, yaxis_title="R$",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                            margin=dict(l=10, r=10, t=70, b=10), plot_bgcolor="#FAFAFA")
                        fig.update_yaxes(gridcolor="#EEE")
                        st.plotly_chart(fig, use_container_width=True)

                t = cat[["categoria", "locacoes", "receita", "ticket_item",
                         "custo_rateado", "liquido", "margem"]].copy()
                t.columns = ["Categoria", "Locações", "Receita", "Receita/Item",
                             "Custo Rateado", "Líquido", "Margem %"]
                for c in ["Receita", "Receita/Item", "Custo Rateado", "Líquido"]:
                    t[c] = t[c].apply(_rs)
                t["Margem %"] = t["Margem %"].apply(_pct)
                st.dataframe(t, use_container_width=True, hide_index=True)

                # Evolução da participação por categoria
                if PLOTLY and len(itens["categoria"].unique()) > 1:
                    st.markdown("##### 📈 Evolução por categoria")
                    ev = (itens.groupby(["anomes", "categoria"], as_index=False)
                          .agg(receita=("valor_item", "sum")))
                    ev["rotulo"] = ev["anomes"].apply(_rotulo_mes)
                    ev = ev.sort_values("anomes")
                    fig = px.area(ev, x="rotulo", y="receita", color="categoria",
                                  color_discrete_sequence=[CORES["roxo"], CORES["azul"],
                                                           CORES["verde"]])
                    fig.update_layout(height=380, yaxis_title="R$", xaxis_title="",
                                      margin=dict(l=10, r=10, t=30, b=10),
                                      plot_bgcolor="#FAFAFA")
                    fig.update_yaxes(gridcolor="#EEE")
                    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------------
    # ABA 5 — ORIGEM DO CLIENTE
    # ----------------------------------------------------------
    with ab_orig:
        st.subheader("📣 Origem dos Clientes")
        st.caption("Baseado no campo 'Como conseguiu esse cliente?' do cadastro. "
                   "Mostra de onde vem o faturamento — e onde vale investir.")

        if clientes.empty or res_at.empty:
            st.info("Sem dados de origem. Preencha 'Como conseguiu' no cadastro de clientes.")
        else:
            mapa = dict(zip(clientes["nome"].str.strip().str.lower(),
                            clientes["como_conseguiu"]))
            base = res_at.copy()
            base["origem"] = base["cliente"].apply(
                lambda c: mapa.get(_s(c).strip().lower(), "Não informado"))

            org = (base.groupby("origem", as_index=False)
                   .agg(reservas=("bruto", "count"),
                        receita=("bruto", "sum"),
                        clientes_unicos=("cliente", "nunique")))
            org["ticket"] = org["receita"] / org["reservas"]
            org = org.sort_values("receita", ascending=False)

            total_org = org["receita"].sum()
            if total_org > 0:
                org["participacao"] = org["receita"] / total_org * 100

                top = org.iloc[0]
                melhor_ticket = org.sort_values("ticket", ascending=False).iloc[0]

                o1, o2, o3 = st.columns(3)
                card(o1, "🏆 Maior Origem", _s(top["origem"]), CORES["roxo"],
                     f"{_rs(top['receita'])} · {_pct(top['participacao'])}")
                card(o2, "💎 Melhor Ticket", _s(melhor_ticket["origem"]), CORES["rosa"],
                     f"{_rs(melhor_ticket['ticket'])} por reserva")
                card(o3, "👥 Clientes no Período",
                     f"{int(org['clientes_unicos'].sum())}", CORES["azul"],
                     f"{int(org['reservas'].sum())} reserva(s)")

                st.markdown("")
                g1, g2 = st.columns(2)
                with g1:
                    grafico_pizza(org, "origem", "receita", "Receita por origem")
                with g2:
                    grafico_barras_h(org, "origem", "reservas",
                                     "Nº de reservas por origem",
                                     CORES["amarelo"], "Reservas", moeda=False)

                t = org[["origem", "clientes_unicos", "reservas", "receita",
                         "ticket", "participacao"]].copy()
                t.columns = ["Origem", "Clientes", "Reservas", "Receita",
                             "Ticket Médio", "% da Receita"]
                t["Receita"] = t["Receita"].apply(_rs)
                t["Ticket Médio"] = t["Ticket Médio"].apply(_rs)
                t["% da Receita"] = t["% da Receita"].apply(_pct)
                st.dataframe(t, use_container_width=True, hide_index=True)

                nao_inf = org[org["origem"] == "Não informado"]
                if not nao_inf.empty:
                    p = float(nao_inf.iloc[0]["participacao"])
                    if p > 20:
                        st.warning(f"⚠️ {_pct(p)} da receita vem de clientes sem origem "
                                   "cadastrada. Preencher esse campo melhora muito "
                                   "a leitura de onde investir.")

            # ----- Novos x Recorrentes -----
            st.divider()
            st.markdown("##### 🔁 Clientes Novos × Recorrentes")
            if not reservas.empty:
                ordenado = reservas.sort_values("data")
                primeira = ordenado.groupby(
                    ordenado["cliente"].str.strip().str.lower())["data"].min()
                base2 = res_at.copy()
                base2["_k"] = base2["cliente"].str.strip().str.lower()
                base2["primeira"] = base2["_k"].map(primeira)
                base2["tipo"] = base2.apply(
                    lambda r: "Novo" if r["data"] == r["primeira"] else "Recorrente",
                    axis=1)

                nr = base2.groupby("tipo", as_index=False).agg(
                    reservas=("bruto", "count"), receita=("bruto", "sum"))
                if not nr.empty:
                    tot_r = nr["reservas"].sum()
                    n1, n2 = st.columns(2)
                    for col, tipo, cor in [(n1, "Novo", CORES["verde"]),
                                           (n2, "Recorrente", CORES["roxo"])]:
                        linha = nr[nr["tipo"] == tipo]
                        qtd_t = int(linha.iloc[0]["reservas"]) if not linha.empty else 0
                        rec_t = float(linha.iloc[0]["receita"]) if not linha.empty else 0.0
                        pct_t = (qtd_t / tot_r * 100) if tot_r else 0
                        icone = "🆕" if tipo == "Novo" else "🔁"
                        card(col, f"{icone} {tipo}s", f"{qtd_t}", cor,
                             f"{_pct(pct_t)} das reservas · {_rs(rec_t)}")

                    rec_linha = nr[nr["tipo"] == "Recorrente"]
                    if not rec_linha.empty:
                        taxa = int(rec_linha.iloc[0]["reservas"]) / tot_r * 100
                        if taxa >= 30:
                            st.success(f"🎉 Taxa de recompra de {_pct(taxa)} — "
                                       "boa fidelização!")
                        else:
                            st.info(f"📌 Taxa de recompra de {_pct(taxa)}. "
                                    "Campanhas de aniversário podem aumentar esse número.")

    # ----------------------------------------------------------
    # ABA 6 — PAYBACK POR BRINQUEDO
    # ----------------------------------------------------------
    with ab_pay:
        st.subheader("💵 Payback por Brinquedo")
        st.caption("Quanto cada brinquedo já rendeu (receita rateada) frente ao valor "
                   "de compra. Usa o histórico COMPLETO, não o filtro de período.")

        if brinquedos.empty:
            st.info("Cadastre brinquedos com valor de compra para ver o payback.")
        elif itens.empty:
            st.info("Sem locações registradas para calcular o retorno.")
        else:
            rec_total = (itens.groupby("brinquedo", as_index=False)
                         .agg(receita=("valor_item", "sum"),
                              locacoes=("valor_item", "count"),
                              primeira=("data", "min"),
                              ultima=("data", "max")))

            pb = brinquedos.copy()
            pb["_k"] = pb["nome"].str.strip().str.lower()
            rec_total["_k"] = rec_total["brinquedo"].str.strip().str.lower()
            pb = pb.merge(rec_total.drop(columns=["brinquedo"]), on="_k", how="left")
            pb["receita"] = _num(pb["receita"])
            pb["locacoes"] = _num(pb["locacoes"])

            pb["saldo"] = pb["receita"] - pb["valor_compra"]
            pb["pago"] = pb["saldo"] >= 0
            pb["retorno_pct"] = pb.apply(
                lambda r: (r["receita"] / r["valor_compra"] * 100)
                if r["valor_compra"] > 0 else 0.0, axis=1)
            pb["receita_locacao"] = pb.apply(
                lambda r: (r["receita"] / r["locacoes"]) if r["locacoes"] > 0 else 0.0,
                axis=1)
            pb["falta_pagar"] = (pb["valor_compra"] - pb["receita"]).clip(lower=0)
            pb["locacoes_faltam"] = pb.apply(
                lambda r: (r["falta_pagar"] / r["receita_locacao"])
                if r["receita_locacao"] > 0 and r["falta_pagar"] > 0 else 0, axis=1)

            # Meses desde a compra
            def _meses(d):
                d = pd.to_datetime(d, errors="coerce")
                if pd.isna(d):
                    return None
                return max(1, (hoje.year - d.year) * 12 + (hoje.month - d.month))
            if "data_compra" in pb.columns:
                pb["meses_casa"] = pb["data_compra"].apply(_meses)
            else:
                pb["meses_casa"] = None

            com_valor = pb[pb["valor_compra"] > 0]
            investido = float(com_valor["valor_compra"].sum())
            retornado = float(com_valor["receita"].sum())
            pagos = int(com_valor["pago"].sum())
            a_pagar = int(len(com_valor) - pagos)

            k1, k2, k3, k4 = st.columns(4)
            card(k1, "💸 Total Investido", _rs(investido), CORES["vermelho"],
                 f"{len(com_valor)} brinquedo(s) com valor")
            card(k2, "💰 Já Retornado", _rs(retornado), CORES["verde"],
                 f"{_pct(retornado / investido * 100) if investido else '0,0%'} do investido")
            card(k3, "✅ Já se Pagaram", f"{pagos}", CORES["azul"],
                 f"de {len(com_valor)} brinquedo(s)")
            card(k4, "⏳ Ainda Pagando", f"{a_pagar}", CORES["laranja"],
                 f"faltam {_rs(com_valor['falta_pagar'].sum())}")

            st.markdown("")

            if PLOTLY and not com_valor.empty:
                d = com_valor.sort_values("retorno_pct", ascending=True).tail(20)
                cores_b = [CORES["verde"] if v >= 100
                           else CORES["amarelo"] if v >= 50
                           else CORES["vermelho"] for v in d["retorno_pct"]]
                fig = go.Figure(go.Bar(
                    x=d["retorno_pct"], y=d["nome"], orientation="h",
                    marker_color=cores_b,
                    text=[_pct(v) for v in d["retorno_pct"]], textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Retorno: %{x:.1f}%<extra></extra>"))
                fig.add_vline(x=100, line_dash="dash", line_color="#333",
                              annotation_text="Payback (100%)")
                fig.update_layout(
                    title="Retorno sobre o Investimento por Brinquedo",
                    height=max(360, 26 * len(d) + 120), xaxis_title="% do valor de compra",
                    margin=dict(l=10, r=70, t=60, b=10), plot_bgcolor="#FAFAFA",
                    showlegend=False)
                fig.update_xaxes(gridcolor="#EEE")
                st.plotly_chart(fig, use_container_width=True)

            f1, f2 = st.columns([1, 2])
            filtro_pb = f1.radio("Mostrar:", ["Todos", "Já se pagaram", "Ainda pagando"],
                                 key="rel_filtro_pb")
            vis = pb.copy()
            if filtro_pb == "Já se pagaram":
                vis = vis[vis["pago"] & (vis["valor_compra"] > 0)]
            elif filtro_pb == "Ainda pagando":
                vis = vis[~vis["pago"] & (vis["valor_compra"] > 0)]

            vis = vis.sort_values("retorno_pct", ascending=False)
            t = vis[["nome", "categoria", "valor_compra", "locacoes", "receita",
                     "receita_locacao", "retorno_pct", "falta_pagar",
                     "locacoes_faltam", "meses_casa"]].copy()
            t.columns = ["Brinquedo", "Categoria", "Compra", "Locações", "Receita",
                         "Receita/Locação", "Retorno %", "Falta Pagar",
                         "Locações p/ Pagar", "Meses de Casa"]
            for c in ["Compra", "Receita", "Receita/Locação", "Falta Pagar"]:
                t[c] = t[c].apply(_rs)
            t["Retorno %"] = t["Retorno %"].apply(_pct)
            t["Locações"] = t["Locações"].apply(lambda v: int(v))
            t["Locações p/ Pagar"] = t["Locações p/ Pagar"].apply(
                lambda v: "—" if v <= 0 else f"~{int(v) + 1}")
            t["Meses de Casa"] = t["Meses de Casa"].apply(
                lambda v: "—" if pd.isna(v) or v is None else f"{int(v)}m")
            st.dataframe(t, use_container_width=True, hide_index=True)

            sem_valor = int((pb["valor_compra"] <= 0).sum())
            if sem_valor:
                st.caption(f"ℹ️ {sem_valor} brinquedo(s) sem valor de compra cadastrado "
                           "ficam de fora do cálculo de payback.")

    # ---------- Rodapé ----------
    st.divider()
    with st.expander("ℹ️ Como os números são calculados"):
        st.markdown("""
| Indicador | Definição |
|---|---|
| **Total do Período** | Soma de `valor_total` das reservas (já inclui extra + frete − desconto) |
| **Sinal Recebido** | Soma de `sinal` — o que efetivamente entrou no caixa |
| **A Receber** | Soma de `falta` — o que ainda vai entrar |
| **Custos** | Soma dos lançamentos da tabela de custos no período |
| **Lucro Líquido** | Total do Período − Custos (**pode ser negativo**) |
| **Margem Líquida** | Líquido ÷ Total do Período |
| **Ticket Médio** | Total do Período ÷ nº de reservas |
| **Projeção** | Maior valor entre o já contratado no mês e o ritmo diário projetado |
| **Receita por brinquedo** | Valor da reserva **dividido igualmente** entre os itens |
| **Payback** | Receita rateada acumulada ÷ valor de compra |

Reservas com status cancelado ou recusado são **excluídas** de todos os cálculos.
        """)


# ==============================================================
# METAS
# ==============================================================
def _obter_metas() -> pd.DataFrame:
    """Carrega metas; cria a base se não existir. Sempre cobre todos os meses."""
    try:
        df = carregar_dados("metas", COLS_METAS)
    except Exception:
        df = pd.DataFrame(columns=COLS_METAS)

    if df is None:
        df = pd.DataFrame(columns=COLS_METAS)
    df = df.copy()

    base = pd.date_range(start=f"{ANO_INICIO_METAS}-01-01",
                         end=f"{ANO_FIM_METAS}-12-01", freq="MS")
    completo = pd.DataFrame({"anomes": base.strftime("%Y-%m")})

    if df.empty:
        completo["meta"] = META_PADRAO
        try:
            salvar_dados(completo, "metas")
        except Exception:
            pass
        return completo

    df["anomes"] = df["anomes"].astype(str).str[:7]
    df["meta"] = _num(df["meta"]).replace(0, META_PADRAO)
    df = df.drop_duplicates(subset=["anomes"], keep="last")

    out = completo.merge(df, on="anomes", how="left")
    out["meta"] = out["meta"].fillna(META_PADRAO)
    return out


# ==============================================================
# COMO INTEGRAR NO app.py
# ==============================================================
# 1) Apague (ou comente) a função pagina_relatorios() antiga do app.py
#
# 2) Adicione no topo, junto dos outros imports:
#
#       from relatorios import pagina_relatorios
#
# 3) Nada mais muda! O menu e o elif já existentes continuam funcionando,
#    porque o nome da função é o mesmo.
#
# 4) Pare o Streamlit (Ctrl+C) e rode de novo: streamlit run app.py
# ==============================================================
