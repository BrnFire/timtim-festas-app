import streamlit as st
import pandas as pd
import requests
import os
import json
import time 
from datetime import datetime
from dateutil import parser
from banco import carregar_dados, salvar_dados


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _caminho_csv(nome):
    # garante caminho absoluto (evita salvar em pasta errada)
    return os.path.join(BASE_DIR, nome)
# ========================================
# CONFIGURAÇÃO INICIAL
# ========================================
st.set_page_config(page_title="TimTim Festas", layout="wide")

# Cores da marca
PRIMARY_COLOR = "#7A5FFF"   # Roxo suave
SECONDARY_COLOR = "#FFF4B5" # Amarelo claro

# CSS personalizado
st.markdown(f"""
    <style>
        .main {{
            background-color: white;
        }}
        .sidebar .sidebar-content {{
            background-color: {SECONDARY_COLOR};
        }}
        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 10px;
            font-weight: bold;
        }}
        .stButton>button:hover {{
            background-color: #6242D6;
        }}
    </style>
""", unsafe_allow_html=True)

# ========================================
# FUNÇÃO DE LOGIN
# ========================================
def login():
    from datetime import datetime
    ano = datetime.now().year

    st.sidebar.image("logo.png", use_container_width=True)
    st.sidebar.title("TimTim Festas 🎈")
    st.sidebar.subheader("Acesso ao sistema")

    usuario = st.sidebar.text_input("Usuário")
    senha = st.sidebar.text_input("Senha", type="password")
    botao = st.sidebar.button("Entrar")

    if botao:
        if (usuario == "Bruno" and senha == "4321") or (usuario == "Maryanne" and senha == "4321"):
            st.session_state["usuario"] = usuario
            st.session_state["logado"] = True
        else:
            st.sidebar.error("Usuário ou senha incorretos!")

    # 💜 Rodapé fixo no login
    st.sidebar.markdown(
        f"""
        <style>
            .login-footer {{
                position: fixed;
                bottom: 15px;
                left: 10px;
                width: 260px;
                text-align: center;
                font-size: 0.8em;
                color: #555;
                opacity: 0.85;
                line-height: 1.4;
            }}
            .login-footer strong {{
                color: #7A5FFF;
            }}
        </style>
        <div class="login-footer">
            <strong>BRN Solutions</strong><br>
            © {ano} Todos os direitos reservados
        </div>
        """,
        unsafe_allow_html=True
    )

            
            

# ========================================
# FUNÇÕES AUXILIARES
# ========================================


def obter_coordenadas(cep):
    """Converte CEP brasileiro em coordenadas (lon, lat)."""
    url = f"https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brazil&format=json"
    try:
        r = requests.get(url, headers={"User-Agent": "TimTimFestas"}).json()
        if r:
            return float(r[0]["lon"]), float(r[0]["lat"])
    except Exception:
        pass
    return None, None


import requests
from math import radians, sin, cos, sqrt, atan2


import requests
from math import radians, sin, cos, sqrt, atan2

def calcular_distancia_km(cep_origem, cep_destino):
    """
    Calcula distância aproximada entre dois CEPs (funciona 100% mesmo sem APIs com chave).
    Baseado em coordenadas aproximadas das cidades via ViaCEP + IBGE (Nominatim).
    Retorna distância em km (float) ou None se não conseguir.
    """

    def get_lat_lon_via_cep(cep):
        try:
            cep = cep.replace("-", "").strip()
            # ViaCEP com timeout de 2s
            r = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=2)
            if r.status_code != 200 or "erro" in r.json():
                return None

            d = r.json()
            localidade = d.get("localidade", "")
            uf = d.get("uf", "")

            # Busca coordenadas da cidade via Nominatim (OpenStreetMap)
            url = f"https://nominatim.openstreetmap.org/search?city={localidade}&state={uf}&country=Brazil&format=json"
            resp = requests.get(
                url,
                headers={"User-Agent": "TimTimFestas"},
                timeout=2
            ).json()

            if len(resp) > 0:
                return float(resp[0]["lat"]), float(resp[0]["lon"])
        except requests.Timeout:
            print(f"⚠️ Timeout ao buscar coordenadas do CEP {cep}")
        except Exception as e:
            print(f"Erro ao obter coordenadas do CEP {cep}:", e)
        return None

    try:
        coord1 = get_lat_lon_via_cep(cep_origem)
        coord2 = get_lat_lon_via_cep(cep_destino)
        if not coord1 or not coord2:
            return None

        # Cálculo de distância haversine
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        R = 6371.0
        distancia = R * c

        return round(distancia, 1)

    except Exception as e:
        print("Erro no cálculo de distância:", e)
        return None



# ========================================
# PÁGINAS
# ========================================

def pagina_relatorios():
    import os
    import json
    import pandas as pd
    import matplotlib.pyplot as plt
    from datetime import datetime, date
    from dateutil import parser
    from pandas.tseries.offsets import MonthBegin

    st.header("📈 Relatórios e Indicadores")

    # ============================
    # Carregamento de dados
    # ============================
    reservas = carregar_dados(
        "reservas.csv",
        [
            "Cliente", "Brinquedos", "Data",
            "Horário Entrega", "Horário Retirada",
            "Valor Total", "Valor Extra", "Frete", "Desconto",
            "Sinal", "Falta", "Observação", "Status", "Pagamentos"
        ]
    )
    custos = carregar_dados("custos.csv", ["Data", "Descrição", "Valor"])
    brinquedos_df = carregar_dados("brinquedos.csv", ["Nome", "Valor", "Categoria"])

    # ============================
    # Util: parse de datas robusto
    # ============================
    def parse_data_segura(v):
        try:
            if pd.isna(v) or str(v).strip() == "":
                return pd.NaT
            s = str(v).strip().split(" ")[0]
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
                try:
                    return pd.to_datetime(datetime.strptime(s, fmt)).normalize()
                except ValueError:
                    continue
            return pd.to_datetime(s, dayfirst=True, errors="coerce").normalize()
        except:
            return pd.NaT

    reservas["Data"] = reservas["Data"].apply(parse_data_segura)
    custos["Data"]   = custos["Data"].apply(parse_data_segura)
    reservas = reservas.dropna(subset=["Data"]).reset_index(drop=True)
    custos   = custos.dropna(subset=["Data"]).reset_index(drop=True)

    # Garantias numéricas
    for c in ["Valor Total", "Valor Extra", "Frete", "Desconto", "Sinal"]:
        if c not in reservas.columns:
            reservas[c] = 0.0
        reservas[c] = pd.to_numeric(reservas[c], errors="coerce").fillna(0.0)

    if "Valor" in custos.columns:
        custos["Valor"] = pd.to_numeric(custos["Valor"], errors="coerce").fillna(0.0)
    else:
        custos["Valor"] = 0.0

    # ============================
    # Cálculos base (mês a mês)
    # ============================
    # Garante que colunas de data sejam datetime válidas
    reservas["Data"] = pd.to_datetime(reservas["Data"], errors="coerce")
    custos["Data"]   = pd.to_datetime(custos["Data"], errors="coerce")

    # Remove linhas sem data válida
    reservas = reservas.dropna(subset=["Data"]).reset_index(drop=True)
    custos   = custos.dropna(subset=["Data"]).reset_index(drop=True)

    # Calcula valores brutos e períodos
    reservas["Bruto"] = (
        reservas["Valor Total"]
    ).clip(lower=0)

    # Cria colunas AnoMes seguras
    reservas["AnoMes"] = reservas["Data"].dt.to_period("M").astype(str)
    custos["AnoMes"]   = custos["Data"].dt.to_period("M").astype(str)

    # Agregações mensais
    bruto_mensal  = reservas.groupby("AnoMes", as_index=False)["Bruto"].sum()
    custo_mensal  = custos.groupby("AnoMes", as_index=False)["Valor"].sum().rename(columns={"Valor": "Custo"})

    # Junta resultados
    df_fin_mensal = pd.merge(bruto_mensal, custo_mensal, on="AnoMes", how="outer").fillna(0)
    df_fin_mensal["Liquido"] = (df_fin_mensal["Bruto"] - df_fin_mensal["Custo"]).clip(lower=0)

    # Garante que AnoMes seja ordenável por data
    df_fin_mensal["AnoMes_dt"] = pd.to_datetime(df_fin_mensal["AnoMes"], errors="coerce").fillna(pd.Timestamp("1970-01-01"))
    df_fin_mensal = df_fin_mensal.sort_values("AnoMes_dt")


    # Totais para cards
    total_realizado         = reservas["Sinal"].sum()
    custo_total_periodo     = custos["Valor"].sum()
    liquido_total_periodo   = df_fin_mensal["Liquido"].sum()

    # ============================
    # Cards do topo
    # ============================
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        ("💰 Total Realizado (Recebido)", f"R$ {total_realizado:,.2f}", "#2ECC71"),
        ("📊 Lucro Líquido (Período)", f"R$ {liquido_total_periodo:,.2f}", "#0078D7"),
        ("🧾 Custos (Período)", f"R$ {custo_total_periodo:,.2f}", "#E74C3C"),
        ("🧮 Reservas", len(reservas), "#F1C40F"),
    ]
    for col, (label, value, color) in zip([c1, c2, c3, c4, c5], cards):
        col.markdown(
            f"""
            <div style="background-color:#f9f9f9; border-left:6px solid {color};
                        border-radius:12px; padding:15px; text-align:center;
                        box-shadow:2px 2px 10px rgba(0,0,0,0.1);">
                <div style="font-size:1em;color:#555;">{label}</div>
                <div style="font-size:1.6em;font-weight:bold;">{value}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    # ============================
    # Abas
    # ============================
    aba1, aba2 = st.tabs(["📊 Indicadores Financeiros", "🎠 Desempenho de Brinquedos"])

    # ───────────────────────────────
    # ABA 1: Indicadores Financeiros
    # ───────────────────────────────
    with aba1:
        st.subheader("💰 Lucro Bruto × Lucro Líquido × Meta Mensal (até dez/2026)")

        # Cria metas.csv incluindo o mês atual
        meta_file = "metas.csv"
        if not os.path.exists(meta_file):
            base = pd.date_range(
                start=(pd.Timestamp.today().normalize().replace(day=1) - MonthBegin(1)),
                end=pd.Timestamp(2026, 12, 1),
                freq="MS"
            )
            df_meta = pd.DataFrame({"AnoMes": base.strftime("%Y-%m"), "Meta": [3000.0 for _ in base]})
            df_meta.to_csv(meta_file, index=False, encoding="utf-8-sig")
        else:
            df_meta = pd.read_csv(meta_file)
            if "AnoMes" not in df_meta.columns or "Meta" not in df_meta.columns:
                st.error("⚠️ metas.csv inválido. Deve conter colunas: AnoMes, Meta.")
                return

        # Editor de metas
        with st.expander("🎯 Editar metas mensais até dez/2026"):
            for i, row in df_meta.iterrows():
                col1, col2 = st.columns([2, 1])
                col1.write(row["AnoMes"])
                nova_meta = col2.number_input(
                    f"Meta {row['AnoMes']}",
                    min_value=0.0,
                    value=float(row["Meta"]),
                    step=100.0,
                    key=f"meta_{i}"
                )
                df_meta.at[i, "Meta"] = nova_meta
            if st.button("💾 Salvar metas"):
                df_meta.to_csv(meta_file, index=False, encoding="utf-8-sig")
                st.success("✅ Metas atualizadas!")
                st.rerun()

        # Junta financeiro + metas
        df_plot = pd.merge(
            df_fin_mensal.rename(columns={"Bruto": "Lucro Bruto", "Liquido": "Lucro Líquido"})[["AnoMes", "AnoMes_dt", "Lucro Bruto", "Lucro Líquido"]],
            df_meta, on="AnoMes", how="outer"
        ).fillna(0)
        df_plot["AnoMes_dt"] = pd.to_datetime(df_plot["AnoMes"], errors="coerce")
        df_plot = df_plot.sort_values("AnoMes_dt")

        # ============================
        # Filtro de ano para o gráfico
        # ============================
        anos_disponiveis = sorted(df_plot["AnoMes_dt"].dt.year.dropna().unique())
        ano_selecionado = st.selectbox("📅 Filtrar por ano:", options=["Todos"] + [str(a) for a in anos_disponiveis])

        if ano_selecionado != "Todos":
            df_plot = df_plot[df_plot["AnoMes_dt"].dt.year == int(ano_selecionado)]

        # Gráfico principal
        if df_plot.empty:
            st.info("Sem dados para o período.")
        else:
            fig, ax = plt.subplots(figsize=(9, 4))
            ax.plot(df_plot["AnoMes_dt"], df_plot["Lucro Líquido"], color="#0078D7", label="Lucro Líquido", marker="o")
            ax.plot(df_plot["AnoMes_dt"], df_plot["Lucro Bruto"],  color="#E67E22", label="Lucro Bruto",  marker="s")
            ax.plot(df_plot["AnoMes_dt"], df_plot["Meta"],          color="#27AE60", label="Meta", linewidth=3)
            ax.set_xlabel("Período (mês)")
            ax.set_ylabel("R$")
            ax.grid(True, linestyle="--", alpha=0.6)
            ax.legend()
            ax.set_title("Lucro Bruto, Lucro Líquido e Meta Mensal")
            st.pyplot(fig)

            # Tabela resumo
            st.markdown("### 📋 Resumo mensal")
            tb = df_plot[["AnoMes", "Lucro Bruto", "Lucro Líquido", "Meta"]].copy()
            tb["Diferença"] = tb["Lucro Líquido"] - tb["Meta"]
            tb["% da Meta"] = (tb["Lucro Líquido"] / tb["Meta"] * 100).replace([float("inf"), -float("inf")], 0).fillna(0)

            fmt = lambda x: f"R$ {x:,.2f}"
            for c in ["Lucro Bruto", "Lucro Líquido", "Meta", "Diferença"]:
                tb[c] = tb[c].apply(fmt)
            tb["% da Meta"] = tb["% da Meta"].apply(lambda x: f"{x:.1f}%")

            st.dataframe(tb.sort_values("AnoMes"), use_container_width=True)

    # ───────────────────────────────
    # ABA 2: Desempenho de Brinquedos
    # ───────────────────────────────
    with aba2:
        st.subheader("🎠 Desempenho de Brinquedos")

        if reservas.empty:
            st.info("Sem reservas registradas.")
            return

        # ===== Filtros
        colf1, colf2, colf3 = st.columns([1.5, 1, 2])
        filtro_cat = colf1.radio("Categoria", ["Todos", "Tradicional", "Montessori"], horizontal=True)
        modo_periodo = colf2.radio("Período", ["Mensal", "Anual", "Personalizado"], horizontal=True)

        # Seletor de período
        hoje = datetime.today()
        sel_inicio, sel_fim = None, None
        if modo_periodo == "Mensal":
            ano = colf3.selectbox("Ano", sorted(reservas["Data"].dt.year.unique()), index=len(sorted(reservas["Data"].dt.year.unique()))-1)
            mes = colf3.selectbox("Mês", list(range(1,13)), index=hoje.month-1)
            sel_inicio = pd.Timestamp(ano, mes, 1)
            sel_fim = (sel_inicio + pd.offsets.MonthEnd(1)).normalize()
        elif modo_periodo == "Anual":
            ano = colf3.selectbox("Ano", sorted(reservas["Data"].dt.year.unique()), index=len(sorted(reservas["Data"].dt.year.unique()))-1)
            sel_inicio = pd.Timestamp(ano, 1, 1)
            sel_fim = pd.Timestamp(ano, 12, 31)
        else:
            dt_range = colf3.date_input("Intervalo personalizado", value=(date(hoje.year, 1, 1), date(hoje.year, hoje.month, hoje.day)))
            if isinstance(dt_range, (list, tuple)) and len(dt_range) == 2:
                sel_inicio = pd.to_datetime(dt_range[0])
                sel_fim    = pd.to_datetime(dt_range[1])

        # Aplica filtro de período
        dfp = reservas.copy()
        if sel_inicio is not None and sel_fim is not None:
            dfp = dfp[(dfp["Data"] >= sel_inicio) & (dfp["Data"] <= sel_fim)]

        # ===== Explode: separa brinquedos item a item
        linhas = []
        for _, r in dfp.iterrows():
            itens = [b.strip() for b in str(r["Brinquedos"]).split(",") if b.strip()]
            if not itens:
                continue
            bruto_res = (r["Valor Total"] + r["Valor Extra"] + r["Frete"] - r["Desconto"])
            bruto_res = max(bruto_res, 0.0)
            valor_item = bruto_res / len(itens)
            for b in itens:
                linhas.append({"Brinquedo": b, "Data": r["Data"], "Valor_Item": valor_item})

        itens_df = pd.DataFrame(linhas)
        if itens_df.empty:
            st.warning("Não há itens para o período selecionado.")
            return

        # Traz categoria do cadastro
        if not brinquedos_df.empty and "Nome" in brinquedos_df.columns:
            if "Categoria" not in brinquedos_df.columns:
                brinquedos_df["Categoria"] = "Tradicional"
            itens_df = itens_df.merge(brinquedos_df[["Nome", "Categoria"]], left_on="Brinquedo", right_on="Nome", how="left")
            itens_df.drop(columns=["Nome"], inplace=True, errors="ignore")
            itens_df["Categoria"] = itens_df["Categoria"].fillna("Tradicional")
        else:
            def infer_cat(nome):
                s = str(nome).lower()
                if "mont" in s:
                    return "Montessori"
                return "Tradicional"
            itens_df["Categoria"] = itens_df["Brinquedo"].apply(infer_cat)

        # Filtro de categoria
        if filtro_cat == "Tradicional":
            itens_df = itens_df[itens_df["Categoria"].str.lower() == "tradicional"]
        elif filtro_cat == "Montessori":
            itens_df = itens_df[itens_df["Categoria"].str.lower() == "montessori"]

        if itens_df.empty:
            st.warning("Sem itens nessa categoria/período.")
            return

        # ===== Rankings
        rank_valor = (
            itens_df.groupby("Brinquedo", as_index=False)
                    .agg(Valor_Total=("Valor_Item", "sum"), Locações=("Valor_Item", "count"))
                    .sort_values(["Valor_Total", "Locações"], ascending=[False, False])
        )
        rank_qtd = rank_valor.sort_values(["Locações", "Valor_Total"], ascending=[False, False]).reset_index(drop=True)

        # ===== Gráfico: total de locações por brinquedo
        st.markdown("### 🔢 Locações por Brinquedo")
        top_qtd = rank_qtd.head(15)
        fig1, ax1 = plt.subplots(figsize=(9, 4))
        ax1.barh(top_qtd["Brinquedo"], top_qtd["Locações"])
        ax1.invert_yaxis()
        ax1.set_xlabel("Locações (qtd)")
        ax1.set_ylabel("Brinquedo")
        ax1.grid(axis="x", linestyle="--", alpha=0.5)
        st.pyplot(fig1)

        # ===== Gráfico: valor total por brinquedo
        st.markdown("### 💰 Valor Total por Brinquedo")
        top_val = rank_valor.head(15)
        fig2, ax2 = plt.subplots(figsize=(9, 4))
        ax2.barh(top_val["Brinquedo"], top_val["Valor_Total"])
        ax2.invert_yaxis()
        ax2.set_xlabel("Valor (R$)")
        ax2.set_ylabel("Brinquedo")
        ax2.grid(axis="x", linestyle="--", alpha=0.5)
        st.pyplot(fig2)

        # ===== Pizzas: participação por categoria
        st.markdown("### 🥧 Participação por Categoria")
        colp1, colp2 = st.columns(2)

        cat_qtd = itens_df.groupby("Categoria", as_index=False)["Brinquedo"].count().rename(columns={"Brinquedo": "Locações"})
        with colp1:
            if not cat_qtd.empty and cat_qtd["Locações"].sum() > 0:
                figp1, axp1 = plt.subplots(figsize=(4.5, 4.5))
                axp1.pie(cat_qtd["Locações"], labels=cat_qtd["Categoria"], autopct=lambda p: f"{p:.1f}%", startangle=90)
                axp1.axis("equal")
                st.pyplot(figp1)
            else:
                st.info("Sem dados para locações por categoria.")

        cat_val = itens_df.groupby("Categoria", as_index=False)["Valor_Item"].sum()
        with colp2:
            if not cat_val.empty and cat_val["Valor_Item"].sum() > 0:
                figp2, axp2 = plt.subplots(figsize=(4.5, 4.5))
                axp2.pie(cat_val["Valor_Item"], labels=cat_val["Categoria"], autopct=lambda p: f"{p:.1f}%", startangle=90)
                axp2.axis("equal")
                st.pyplot(figp2)
            else:
                st.info("Sem dados para valor por categoria.")

        # ===== Tabelas: ranking por locações e por valor
        st.markdown("### 🏆 Rankings")
        colr1, colr2 = st.columns(2)

        with colr1:
            st.write("**Mais locados**")
            t1 = rank_qtd.copy()
            t1["Valor_Total"] = t1["Valor_Total"].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(
                t1.rename(columns={"Brinquedo": "Brinquedo", "Locações": "Locações", "Valor_Total": "Valor Total"}),
                use_container_width=True
            )

        with colr2:
            st.write("**Maior faturamento**")
            t2 = rank_valor.copy()
            t2["Valor_Total"] = t2["Valor_Total"].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(
                t2.rename(columns={"Brinquedo": "Brinquedo", "Locações": "Locações", "Valor_Total": "Valor Total"}),
                use_container_width=True
            )


def pagina_brinquedos():
    st.header("🎠 Cadastro de Brinquedos")

    # ==========================
    # CARREGAR DADOS
    # ==========================
    df = carregar_dados("brinquedos.csv", ["Nome", "Valor", "Valor Compra", "Data Compra", "Status", "Categoria"])
    for col in ["Valor Compra", "Data Compra", "Categoria"]:
        if col not in df.columns:
            if col == "Valor Compra":
                df[col] = 0.0
            elif col == "Categoria":
                df[col] = "Tradicional"
            else:
                df[col] = ""

    # ==========================
    # FUNÇÕES AUXILIARES
    # ==========================
    def formatar_reais(valor):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def calcular_tempo_uso(data_compra):
        try:
            data = pd.to_datetime(data_compra, errors="coerce")
            if pd.isna(data):
                return "-"
            hoje = datetime.now()
            anos = hoje.year - data.year
            meses = hoje.month - data.month
            if meses < 0:
                anos -= 1
                meses += 12
            if anos == 0 and meses == 0:
                return "Menos de 1 mês"
            elif anos == 0:
                return f"{meses} meses"
            elif meses == 0:
                return f"{anos} anos"
            else:
                return f"{anos} anos e {meses} meses"
        except:
            return "-"

    # ==========================
    # INDICADORES NO TOPO
    # ==========================
    total_brinquedos = len(df)
    total_disponiveis = len(df[df["Status"] == "Disponível"])
    total_indisponiveis = len(df[df["Status"] == "Indisponível"])
    total_investido = df["Valor Compra"].sum()

    total_tradicional = len(df[df["Categoria"] == "Tradicional"])
    total_montessori = len(df[df["Categoria"] == "Montessori"])

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    cards = [
        ("🎪 Total", total_brinquedos, "#7A5FFF"),
        ("✅ Disponíveis", total_disponiveis, "#2ECC71"),
        ("🚫 Indisponíveis", total_indisponiveis, "#E74C3C"),
        ("💰 Investido", formatar_reais(total_investido), "#F1C40F"),
        ("🎪 Tradicional", total_tradicional, "#9B59B6"),
        ("🧩 Montessori", total_montessori, "#3498DB")
    ]

    for col, (label, value, color) in zip([col1, col2, col3, col4, col5, col6], cards):
        col.markdown(
            f"""
            <div style="background-color:#f9f9f9; border-left:6px solid {color};
                        border-radius:12px; padding:15px; text-align:center;
                        box-shadow:2px 2px 10px rgba(0,0,0,0.1);">
                <div style="font-size:0.9em;color:#555;">{label}</div>
                <div style="font-size:1.4em;font-weight:bold;">{value}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    # ==========================
    # FORMULÁRIO DE CADASTRO / EDIÇÃO
    # ==========================
    if "editando_brinquedo" in st.session_state and st.session_state.editando_brinquedo is not None:
        i = st.session_state.editando_brinquedo
        brinquedo_edicao = df.iloc[i]
        st.info(f"✏️ Editando brinquedo: {brinquedo_edicao['Nome']}")
    else:
        brinquedo_edicao = {
            "Nome": "",
            "Valor": 0.0,
            "Valor Compra": 0.0,
            "Data Compra": "",
            "Status": "Disponível",
            "Categoria": "Tradicional"
        }

    form_key = f"form_brinquedo_{st.session_state.get('editando_brinquedo', 'novo')}"
    with st.form(form_key):
        nome = st.text_input("Nome do brinquedo", value=brinquedo_edicao["Nome"])
        valor = st.number_input("Valor de locação (R$)", min_value=0.0, step=10.0, value=float(brinquedo_edicao["Valor"]))
        valor_compra = st.number_input("Valor de compra (R$)", min_value=0.0, step=10.0, value=float(brinquedo_edicao["Valor Compra"]))
        data_compra = st.date_input(
            "Data de compra",
            value=pd.to_datetime(brinquedo_edicao["Data Compra"], errors="coerce") if brinquedo_edicao["Data Compra"] else datetime.today()
        )
        categoria = st.selectbox(
            "Categoria",
            ["Tradicional", "Montessori"],
            index=0 if brinquedo_edicao.get("Categoria", "Tradicional") == "Tradicional" else 1
        )
        status = st.selectbox("Status", ["Disponível", "Indisponível"],
                              index=0 if brinquedo_edicao["Status"] != "Indisponível" else 1)

        enviar = st.form_submit_button("💾 Salvar brinquedo")

        if enviar and nome:
            novo = [nome, valor, valor_compra, data_compra.strftime("%Y-%m-%d"), status, categoria]
            if "editando_brinquedo" in st.session_state and st.session_state.editando_brinquedo is not None:
                df.loc[st.session_state.editando_brinquedo] = novo
                st.session_state.editando_brinquedo = None
                st.success(f"✅ {nome} atualizado com sucesso!")
            else:
                df.loc[len(df)] = novo
                st.success(f"✅ {nome} cadastrado com sucesso!")

            salvar_dados(df, "brinquedos.csv")
            st.rerun()

    # ==========================
    # LISTAGEM DE BRINQUEDOS
    # ==========================
    st.subheader("📋 Brinquedos cadastrados")

    aba_todos, aba_tradicional, aba_montessori = st.tabs(["📋 Todos", "🎪 Tradicional", "🧩 Montessori"])

    def mostrar_resumo_e_lista(df_cat, categoria_nome):
        total = len(df_cat)
        disponiveis = len(df_cat[df_cat["Status"] == "Disponível"])
        indisponiveis = len(df_cat[df_cat["Status"] == "Indisponível"])

        st.markdown(
            f"""
            <div style="background-color:#f9f9f9; border-left:6px solid #7A5FFF;
                        border-radius:12px; padding:12px; margin-bottom:10px;
                        box-shadow:2px 2px 10px rgba(0,0,0,0.05);">
                <b>{categoria_nome}</b><br>
                Total: {total} brinquedo(s) — ✅ {disponiveis} disponíveis / 🚫 {indisponiveis} indisponíveis
            </div>
            """,
            unsafe_allow_html=True
        )

        if total == 0:
            st.info(f"Nenhum brinquedo da categoria **{categoria_nome}** cadastrado.")
            return

        for i, row in df_cat.iterrows():
            cor_status = "🟢" if row["Status"] == "Disponível" else "🔴"
            fundo_card = "#E8F8F5" if row["Status"] == "Disponível" else "#FDEDEC"
            cor_badge = "#2ECC71" if row["Status"] == "Disponível" else "#E74C3C"
            tempo_uso = calcular_tempo_uso(row["Data Compra"])

            with st.expander(f"{cor_status} {row['Nome']}"):
                st.markdown(
                    f"""
                    <div style='background-color:{fundo_card}; padding:15px; border-radius:10px;
                                box-shadow:2px 2px 10px rgba(0,0,0,0.1); position:relative;'>
                        <span style='position:absolute; top:10px; right:10px;
                                     background-color:{cor_badge}; color:white; padding:4px 10px;
                                     border-radius:8px; font-size:12px; font-weight:bold;'>
                            {row['Status']}
                        </span>
                    """,
                    unsafe_allow_html=True
                )
                st.write(f"**Categoria:** {row['Categoria']}")
                st.write(f"**Valor de locação:** {formatar_reais(row['Valor'])}")
                st.write(f"**Valor de compra:** {formatar_reais(row['Valor Compra'])}")
                st.write(f"**Data de compra:** {row['Data Compra'] if row['Data Compra'] else '-'}")
                st.write(f"**Tempo de uso:** {tempo_uso}")
                st.write(f"**Status:** {cor_status} {row['Status']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_brinquedo_{i}_{categoria_nome}"):
                        st.session_state.editando_brinquedo = i
                        st.rerun()
                with col2:
                    if st.button("🗑️ Excluir", key=f"del_brinquedo_{i}_{categoria_nome}"):
                        nome_excluido = row["Nome"]
                        df_cat = df_cat.drop(i).reset_index(drop=True)
                        salvar_dados(df, "brinquedos.csv")
                        st.warning(f"🗑️ {nome_excluido} removido com sucesso!")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # ==========================
    # EXIBIR CADA ABA
    # ==========================
    with aba_todos:
        mostrar_resumo_e_lista(df, "Todos os brinquedos")

    with aba_tradicional:
        mostrar_resumo_e_lista(df[df["Categoria"] == "Tradicional"], "Tradicional")

    with aba_montessori:
        mostrar_resumo_e_lista(df[df["Categoria"] == "Montessori"], "Montessori")


def pagina_clientes():
    st.header("👨‍👩‍👧 Cadastro de Clientes")

    colunas = [
        "Nome", "Telefone", "Email", "Tipo de Cliente", "RG", "CPF", "CNPJ",
        "Como conseguiu", "Logradouro", "Número", "Complemento",
        "Bairro", "Cidade", "CEP", "Observação"
    ]

    df = carregar_dados("clientes.csv", colunas)

    # Verifica se está editando
    if "editando_cliente" in st.session_state and st.session_state.editando_cliente is not None:
        i = st.session_state.editando_cliente
        cliente_edicao = df.iloc[i]
        st.info(f"✏️ Editando cliente: {cliente_edicao['Nome']}")
    else:
        cliente_edicao = {col: "" for col in colunas}

    # Inicializa session_state para endereço se não existir
    for campo in ["logradouro", "bairro", "cidade"]:
        if campo not in st.session_state:
            st.session_state[campo] = cliente_edicao.get(campo.capitalize(), "")

    # Campos principais
    with st.form("form_cliente"):
        nome = st.text_input("Nome do cliente", value=cliente_edicao["Nome"])
        telefone_raw = st.text_input("Telefone (somente números)", value=cliente_edicao["Telefone"], max_chars=11)

        # Formatação de telefone
        telefone = ""
        if telefone_raw.isdigit() and len(telefone_raw) >= 10:
            telefone = f"({telefone_raw[:2]}) {telefone_raw[2:7]}-{telefone_raw[7:]}"
        else:
            telefone = telefone_raw

        email = st.text_input("Email", value=cliente_edicao["Email"])
        tipo_cliente = st.radio("Tipo de Cliente", ["Pessoa Física", "Pessoa Jurídica"],
                                index=0 if cliente_edicao["Tipo de Cliente"] != "Pessoa Jurídica" else 1)

        # Novo campo RG
        rg_raw = st.text_input("RG", value=cliente_edicao.get("RG", ""))
        rg = re.sub(r"\D", "", rg_raw)
        if len(rg) >= 7:
            rg = f"{rg[:2]}.{rg[2:5]}.{rg[5:]}"
        else:
            rg = rg_raw

        cpf, cnpj = cliente_edicao["CPF"], cliente_edicao["CNPJ"]

        if tipo_cliente == "Pessoa Física":
            cpf_raw = st.text_input("CPF", value=cliente_edicao["CPF"])
            cpf_num = re.sub(r"\D", "", cpf_raw)
            cpf = (
                f"{cpf_num[:3]}.{cpf_num[3:6]}.{cpf_num[6:9]}-{cpf_num[9:]}"
                if len(cpf_num) == 11 else cpf_raw
            )
            cnpj = ""
        else:
            cnpj_raw = st.text_input("CNPJ", value=cliente_edicao["CNPJ"])
            cnpj_num = re.sub(r"\D", "", cnpj_raw)
            cnpj = (
                f"{cnpj_num[:2]}.{cnpj_num[2:5]}.{cnpj_num[5:8]}/{cnpj_num[8:12]}-{cnpj_num[12:]}"
                if len(cnpj_num) == 14 else cnpj_raw
            )
            cpf = ""

        como_conseguiu = st.selectbox(
            "Como conseguiu esse cliente?",
            ["Indicação", "Instagram", "Facebook", "Google", "WhatsApp", "Outro"],
            index=0 if not cliente_edicao["Como conseguiu"] else
            ["Indicação", "Instagram", "Facebook", "Google", "WhatsApp", "Outro"].index(cliente_edicao["Como conseguiu"])
        )

        st.markdown("---")
        st.subheader("📍 Endereço")

        # Linha do CEP + botão lado a lado
        col_cep1, col_cep2 = st.columns([3, 1])
        with col_cep1:
            cep_raw = st.text_input("CEP", value=cliente_edicao["CEP"], max_chars=9)
            cep_limpo = re.sub(r"\D", "", cep_raw)[:8]
            cep = f"{cep_limpo[:5]}-{cep_limpo[5:]}" if len(cep_limpo) == 8 else cep_raw

        with col_cep2:
            buscar_cep = st.form_submit_button("Buscar CEP")

        # Campos com preenchimento automático
        logradouro = st.text_input("Logradouro", value=st.session_state["logradouro"])
        numero = st.text_input("Número", value=cliente_edicao["Número"])
        complemento = st.text_input("Complemento", value=cliente_edicao["Complemento"])
        bairro = st.text_input("Bairro", value=st.session_state["bairro"])
        cidade = st.text_input("Cidade", value=st.session_state["cidade"])

        observacao = st.text_area("Observação (opcional)", value=cliente_edicao["Observação"])

        salvar = st.form_submit_button("💾 Salvar cliente")

    # 🔎 Busca de CEP fora do form
    if buscar_cep:
        cep_limpo = cep.replace("-", "").strip()
        if len(cep_limpo) == 8:
            with st.spinner("🔎 Buscando CEP..."):
                try:
                    r = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/")
                    if r.status_code == 200:
                        dados = r.json()
                        if "erro" not in dados:
                            st.session_state["logradouro"] = dados.get("logradouro", "")
                            st.session_state["bairro"] = dados.get("bairro", "")
                            st.session_state["cidade"] = dados.get("localidade", "")
                            st.success("✅ Endereço preenchido automaticamente!")
                        else:
                            st.warning("⚠️ CEP não encontrado.")
                    else:
                        st.error("Erro ao consultar o CEP.")
                except Exception as e:
                    st.error(f"Erro ao conectar ao ViaCEP: {e}")
            st.rerun()
        else:
            st.warning("Digite um CEP válido com 8 dígitos.")

    # Salvamento do cliente
    if salvar and nome:
        novo_cliente = [
            nome, telefone, email, tipo_cliente, rg, cpf, cnpj,
            como_conseguiu,
            st.session_state["logradouro"],
            numero, complemento,
            st.session_state["bairro"],
            st.session_state["cidade"],
            cep, observacao
        ]

        if "editando_cliente" in st.session_state and st.session_state.editando_cliente is not None:
            df.loc[st.session_state.editando_cliente] = novo_cliente
            st.session_state.editando_cliente = None
            st.success(f"✅ Cliente {nome} atualizado com sucesso!")
        else:
            df.loc[len(df)] = novo_cliente
            st.success(f"✅ Cliente {nome} cadastrado com sucesso!")

        salvar_dados(df, "clientes.csv")

        for campo in ["logradouro", "bairro", "cidade"]:
            st.session_state.pop(campo, None)

        st.rerun()

    # Exibição da lista de clientes
    st.subheader("📋 Clientes cadastrados")
    if not df.empty:
        for i, row in df.iterrows():
            with st.expander(f"{row['Nome']}"):
                st.write(f"**Telefone:** {row['Telefone']}")
                st.write(f"**Email:** {row['Email']}")
                st.write(f"**Tipo:** {row['Tipo de Cliente']}")
                if row["RG"]:
                    st.write(f"**RG:** {row['RG']}")
                if row["Tipo de Cliente"] == "Pessoa Física":
                    st.write(f"**CPF:** {row['CPF']}")
                else:
                    st.write(f"**CNPJ:** {row['CNPJ']}")
                st.write(f"**Como conseguiu:** {row['Como conseguiu']}")
                st.write(f"**Endereço:** {row['Logradouro']}, {row['Número']} - {row['Bairro']}, {row['Cidade']} - CEP {row['CEP']}")
                if row['Complemento']:
                    st.write(f"**Complemento:** {row['Complemento']}")
                st.write(f"**Observação:** {row['Observação']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_cliente_{i}"):
                        st.session_state.editando_cliente = i
                        st.rerun()
                with col2:
                    if st.button("🗑️ Excluir", key=f"del_cliente_{i}"):
                        nome_excluido = row["Nome"]
                        df = df.drop(i).reset_index(drop=True)
                        salvar_dados(df, "clientes.csv")
                        st.warning(f"🗑️ Cliente {nome_excluido} excluído com sucesso!")
                        st.rerun()
    else:
        st.info("Nenhum cliente cadastrado ainda.")


import unicodedata
import re
import time
from datetime import datetime
import pandas as pd
import streamlit as st

def pagina_reservas():
    st.header("📅 Gerenciar Reservas")

    # ========================================
    # CARREGAMENTO DOS DADOS
    # ========================================
    brinquedos = carregar_dados("brinquedos.csv", ["Nome", "Valor", "Status", "Categoria"])
    clientes = carregar_dados(
        "clientes.csv",
        ["Nome", "Telefone", "Email", "Tipo de Cliente", "CPF", "CNPJ",
         "Como conseguiu", "Logradouro", "Número", "Complemento",
         "Bairro", "Cidade", "CEP", "Observação"]
    )
    reservas = carregar_dados(
        "reservas.csv",
        ["Cliente", "Brinquedos", "Data", "Horário Entrega", "Horário Retirada",
         "Início Festa", "Fim Festa",
         "Valor Total", "Valor Extra", "Frete", "Desconto",
         "Sinal", "Falta", "Observação", "Status", "Pagamentos"]
    )

    # ========================================
    # CONVERSÃO DE DATAS
    # ========================================
    def parse_data_segura(valor):
        try:
            if pd.isna(valor) or str(valor).strip() == "":
                return pd.NaT
            valor_str = str(valor).strip().split(" ")[0]
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
                try:
                    return pd.to_datetime(datetime.strptime(valor_str, fmt)).normalize()
                except ValueError:
                    continue
            return pd.to_datetime(valor_str, dayfirst=True, errors="coerce").normalize()
        except Exception:
            return pd.NaT

    reservas["Data"] = reservas["Data"].apply(parse_data_segura)
    hoje = pd.Timestamp.now().normalize()

    # ========================================
    # GARANTE COLUNAS
    # ========================================
    for col in ["Horário Entrega", "Horário Retirada", "Início Festa", "Fim Festa",
                "Valor Total", "Valor Extra", "Frete", "Desconto",
                "Sinal", "Falta", "Observação", "Status", "Pagamentos"]:
        if col not in reservas.columns:
            reservas[col] = "" if col in ["Horário Entrega", "Horário Retirada", "Início Festa", "Fim Festa",
                                          "Observação", "Status", "Pagamentos"] else 0.0

    # ========================================
    # CLASSIFICAÇÃO DE RESERVAS
    # ========================================
    reservas_hoje = reservas[reservas["Data"] == hoje].sort_values(by="Data")
    reservas_futuras = reservas[reservas["Data"] > hoje].sort_values(by="Data")
    reservas_passadas = reservas[reservas["Data"] < hoje].sort_values(by="Data", ascending=False)

    # ========================================
    # INDICADORES
    # ========================================
    total_reservas = len(reservas)
    total_hoje = len(reservas_hoje)
    total_futuras = len(reservas_futuras)
    total_concluidas = len(reservas[reservas["Status"] == "Concluído"])
    total_faturado = reservas["Sinal"].sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    cards = [
        ("📊 Total de Reservas", total_reservas, "#7A5FFF"),
        ("📅 Hoje", total_hoje, "#00B050"),
        ("🚀 Futuras", total_futuras, "#2ECC71"),
        ("✅ Concluídas", total_concluidas, "#0078D7"),
        ("💰 Total Faturado", f"R$ {total_faturado:,.2f}", "#F1C40F")
    ]
    for col, (label, value, color) in zip([col1, col2, col3, col4, col5], cards):
        col.markdown(
            f"""
            <div style="background-color:#f9f9f9; border-left:6px solid {color}; border-radius:12px;
                        padding:15px; text-align:center; box-shadow:2px 2px 10px rgba(0,0,0,0.1);">
                <div style="font-size:1em;color:#555;">{label}</div>
                <div style="font-size:1.6em;font-weight:bold;">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ========================================
    # ABAS
    # ========================================
    aba_hoje, aba_futuras, aba_passadas = st.tabs(["📅 Hoje", "🚀 Futuras", "📖 Histórico"])

    def exibir_reservas(df, tipo):
        if df.empty:
            st.info(f"Nenhuma reserva {tipo.lower()} encontrada.")
            return

        for i, row in df.iterrows():
            dias_restantes = (row["Data"] - hoje).days if pd.notna(row["Data"]) else 0
            if row["Status"] == "Concluído":
                cor_card = "#D6EAF8"
            elif dias_restantes < 0:
                cor_card = "#FADBD8"
            elif dias_restantes <= 3:
                cor_card = "#FCF3CF"
            else:
                cor_card = "#D5F5E3"

            label_tempo = (
                f"🟦 Concluída" if row["Status"] == "Concluído"
                else f"🔴 Hoje" if dias_restantes == 0
                else f"⚠️ Amanhã" if dias_restantes == 1
                else f"🟡 Faltam {dias_restantes} dias" if dias_restantes <= 3
                else f"🟩 Em {dias_restantes} dias"
            )

            with st.expander(f"🎈 {row['Cliente']} - {row['Data'].strftime('%d/%m/%Y')} ({label_tempo})"):
                st.markdown(f"<div style='background-color:{cor_card};padding:10px;border-radius:8px;'>", unsafe_allow_html=True)
                st.write(f"**Brinquedos:** {row['Brinquedos']}")
                st.write(f"**Horário Entrega:** {row['Horário Entrega']}")
                st.write(f"**Horário Retirada:** {row['Horário Retirada']}")
                st.write(f"**Início da Festa:** {row['Início Festa']}")
                st.write(f"**Fim da Festa:** {row['Fim Festa']}")
                st.write(f"**Valor Total:** R$ {row['Valor Total']:.2f}")
                st.write(f"**Pago (Sinal):** R$ {row['Sinal']:.2f}")
                st.write(f"**Falta Receber:** R$ {row['Falta']:.2f}")
                st.write(f"**Frete:** R$ {row['Frete']:.2f}")
                st.write(f"**Status:** {row['Status']}")

                nova_obs = st.text_area("📝 Atualizar observação", value=row["Observação"], key=f"obs_{tipo}_{i}")
                if st.button("💾 Salvar observação", key=f"btn_obs_{tipo}_{i}"):
                    reservas.at[i, "Observação"] = nova_obs
                    salvar_dados(reservas, "reservas.csv")
                    st.success("📝 Observação salva com sucesso!")
                    st.balloons()
                    st.rerun()

                valor_parcial = st.number_input("Registrar pagamento (R$)", min_value=0.0, step=10.0, key=f"pag_{tipo}_{i}")
                if st.button("💰 Confirmar pagamento", key=f"btn_pag_{tipo}_{i}"):
                    if valor_parcial > 0:
                        reservas.at[i, "Sinal"] += valor_parcial
                        reservas.at[i, "Falta"] = max(reservas.at[i, "Valor Total"] - reservas.at[i, "Sinal"], 0.0)
                        reservas.at[i, "Status"] = "Concluído" if reservas.at[i, "Falta"] == 0 else "Pendente"
                        salvar_dados(reservas, "reservas.csv")
                        st.success(f"💰 Pagamento de R$ {valor_parcial:.2f} registrado!")
                        st.balloons()
                        st.rerun()

                if st.button("✏️ Editar reserva", key=f"edit_{tipo}_{i}"):
                    st.session_state.editando = i
                    st.rerun()

                with st.expander("🗑️ Excluir reserva"):
                    confirmar = st.checkbox(f"Confirmar exclusão da reserva de {row['Cliente']}", key=f"chk_del_{tipo}_{i}")
                    if st.button("🗑️ Excluir DEFINITIVAMENTE", key=f"btn_del_{tipo}_{i}") and confirmar:
                        reservas.drop(index=i, inplace=True)
                        salvar_dados(reservas, "reservas.csv")
                        st.success("🗑️ Reserva excluída com sucesso.")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    with aba_hoje:
        exibir_reservas(reservas_hoje, "HOJE")
    with aba_futuras:
        exibir_reservas(reservas_futuras, "FUTURA")
    with aba_passadas:
        exibir_reservas(reservas_passadas, "PASSADA")

    # ========================================
    # FORMULÁRIO DE CADASTRO / EDIÇÃO
    # ========================================
    st.divider()
    st.subheader("➕ Adicionar / Editar Reserva")

    if "Categoria" not in brinquedos.columns:
        brinquedos["Categoria"] = "Tradicional"

    st.markdown("#### 🎠 Filtrar brinquedos por categoria:")
    filtro_categoria = st.radio("", ["⚪ Todos", "🟣 Tradicional", "🩵 Montessori"], horizontal=True)

    if "Tradicional" in filtro_categoria:
        brinquedos_filtrados = brinquedos[brinquedos["Categoria"].str.lower() == "tradicional"]
    elif "Montessori" in filtro_categoria:
        brinquedos_filtrados = brinquedos[brinquedos["Categoria"].str.lower() == "montessori"]
    else:
        brinquedos_filtrados = brinquedos

    qtd = len(brinquedos_filtrados)
    st.caption(f"🎪 {qtd} brinquedo(s) disponível(is) nesta categoria.")

    if "editando" in st.session_state and st.session_state.editando is not None and st.session_state.editando in reservas.index:
        i = st.session_state.editando
        reserva = reservas.loc[i]
        st.info(f"✏️ Editando reserva de {reserva['Cliente']}")
    else:
        i = None
        reserva = {"Cliente": "", "Brinquedos": "", "Data": datetime.today(),
                   "Horário Entrega": "", "Horário Retirada": "",
                   "Início Festa": "", "Fim Festa": "",
                   "Valor Total": 0.0, "Valor Extra": 0.0, "Frete": 0.0,
                   "Desconto": 0.0, "Sinal": 0.0, "Falta": 0.0,
                   "Observação": "", "Status": "Pendente", "Pagamentos": ""}

    cliente = st.selectbox(
        "Cliente",
        clientes["Nome"].tolist() if not clientes.empty else [],
        index=int(clientes.index[clientes["Nome"] == reserva["Cliente"]][0]) if reserva["Cliente"] in clientes["Nome"].values else 0
    )

    # ========= NOVO: Data para filtrar disponibilidade =========
    data_para_disponibilidade = st.date_input(
        "📅 Data para verificar disponibilidade",
        pd.to_datetime(reserva["Data"] if not isinstance(reserva, dict) else datetime.today())
    )

    # === Normalização de nomes (sem acento, espaços, pontuação) ===
    def normalizar_nome(txt):
        if not isinstance(txt, str):
            return ""
        txt = txt.lower().strip()
        txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("utf-8")
        txt = re.sub(r"[^a-z0-9]+", " ", txt)
        return txt.strip()

    # === Filtra brinquedos realmente disponíveis ===
    reservados_dia = reservas.loc[
        reservas["Data"] == pd.to_datetime(data_para_disponibilidade), "Brinquedos"
    ].dropna().tolist()

    ocupados = []
    for r in reservados_dia:
        ocupados.extend([normalizar_nome(b) for b in r.split(",") if b.strip()])
    ocupados = set(ocupados)

    selecionados_atuais = set()
    if not isinstance(reserva, dict) and isinstance(reserva.get("Brinquedos", ""), str) and reserva["Brinquedos"]:
        selecionados_atuais = set([normalizar_nome(b) for b in reserva["Brinquedos"].split(",") if b.strip()])

    ocupados_externos = ocupados - selecionados_atuais

    brinquedos_filtrados["Nome_normalizado"] = brinquedos_filtrados["Nome"].apply(normalizar_nome)
    brinquedos_disponiveis_df = brinquedos_filtrados[~brinquedos_filtrados["Nome_normalizado"].isin(ocupados_externos)]

    if ocupados_externos:
        st.warning(
            f"⚠️ Indisponíveis nesta data: "
            + ", ".join(sorted([b for b in ocupados_externos]))
        )

    if not brinquedos_disponiveis_df.empty:
        st.markdown(
            "<div style='background-color:#E8F8F5;padding:6px 10px;border-radius:6px;'>"
            f"🟢 {len(brinquedos_disponiveis_df)} brinquedo(s) disponível(is) nesta data."
            "</div>",
            unsafe_allow_html=True
        )

    itens = st.multiselect(
        "🎠 Brinquedos disponíveis",
        sorted(brinquedos_disponiveis_df["Nome"].tolist(), key=lambda x: x.lower()),
        default=(reserva["Brinquedos"].split(", ") if isinstance(reserva["Brinquedos"], str) and reserva["Brinquedos"] else [])
    )

    # ===== FRETE AUTOMÁTICO =====
    cep_origem = "09060-390"
    cep_destino = clientes.loc[clientes["Nome"] == cliente, "CEP"].values[0] if cliente in clientes["Nome"].values else ""

    frete_auto = 0.0
    distancia_km = None
    if cep_destino:
        distancia_km = calcular_distancia_km(cep_origem, cep_destino)
        if distancia_km:
            categorias = [str(c).strip().lower() for c in brinquedos.loc[brinquedos["Nome"].isin(itens), "Categoria"].unique() if pd.notna(c)]

            if not categorias:
                multiplicador = 3
            elif "montessori" in categorias and "tradicional" in categorias:
                multiplicador = 5
            elif "montessori" in categorias:
                multiplicador = 5
            else:
                multiplicador = 3

            frete_auto = round(distancia_km * multiplicador, 2)

            st.info(f"🚚 Distância aproximada: {distancia_km} km")
            st.markdown(f"**📍 CEP origem:** {cep_origem} → **destino:** {cep_destino}")
            st.success(f"💰 Frete automático: R$ {frete_auto:.2f}")
        else:
            st.warning("⚠️ Não foi possível calcular a distância para o CEP informado.")
    else:
        st.warning("⚠️ Este cliente não possui CEP cadastrado — cálculo automático indisponível.")


        
        # ====== UNIFICAÇÃO DAS DATAS ======
# A data usada para verificar disponibilidade também será usada na reserva
    data_selecionada = pd.to_datetime(data_para_disponibilidade)

    with st.form("form_reserva"):
    # Campo apenas exibido (bloqueado) para não editar
        st.markdown("### 📅 Data da reserva (vinculada à data de disponibilidade)")
        st.info(f"**Data selecionada:** {data_selecionada.strftime('%d/%m/%Y')}")

    # Mantém compatibilidade com o código interno que usa a variável 'data'
        data = data_selecionada

        col_h1, col_h2 = st.columns(2)
        with col_h1:
            horario_entrega = st.time_input("Horário Entrega", value=datetime.strptime(reserva["Horário Entrega"] or "08:00", "%H:%M").time())
            inicio_festa = st.time_input("🕒 Início da Festa", value=datetime.strptime(reserva["Início Festa"] or "13:00", "%H:%M").time())
        with col_h2:
            horario_retirada = st.time_input("Horário Retirada", value=datetime.strptime(reserva["Horário Retirada"] or "18:00", "%H:%M").time())
            fim_festa = st.time_input("🕓 Fim da Festa", value=datetime.strptime(reserva["Fim Festa"] or "17:00", "%H:%M").time())

        observacao = st.text_area("Observação (opcional)", value=reserva["Observação"])
        valor_extra = st.number_input("Valor Extra (R$)", min_value=0.0, step=10.0, value=float(reserva["Valor Extra"]))
        frete = st.number_input("Frete (R$)", min_value=0.0, step=10.0, value=float(frete_auto or reserva["Frete"]))
        desconto = st.number_input("Desconto (R$)", min_value=0.0, step=10.0, value=float(reserva["Desconto"]))

        total_brinquedos = brinquedos[brinquedos["Nome"].isin(itens)]["Valor"].sum()
        valor_total = total_brinquedos + valor_extra + frete - desconto
        st.markdown(f"**💰 Valor Total calculado:** R$ {valor_total:.2f}")

        salvar = st.form_submit_button("💾 Salvar Reserva")

        if salvar:
            if not cliente or not itens or not data:
                st.error("⚠️ Selecione um cliente, uma data e pelo menos um brinquedo.")
            else:
                nova_reserva = {
                    "Cliente": cliente,
                    "Brinquedos": ", ".join(itens),
                    "Data": data.strftime("%Y-%m-%d"),
                    "Horário Entrega": horario_entrega.strftime("%H:%M"),
                    "Horário Retirada": horario_retirada.strftime("%H:%M"),
                    "Início Festa": inicio_festa.strftime("%H:%M"),
                    "Fim Festa": fim_festa.strftime("%H:%M"),
                    "Valor Total": valor_total,
                    "Valor Extra": valor_extra,
                    "Frete": frete,
                    "Desconto": desconto,
                    "Sinal": reserva["Sinal"],
                    "Falta": max(valor_total - reserva["Sinal"], 0.0),
                    "Observação": observacao,
                    "Status": "Concluído" if valor_total == reserva["Sinal"] else "Pendente",
                    "Pagamentos": reserva["Pagamentos"]
                }

                if i is not None:
                    reservas.loc[i] = nova_reserva
                    st.session_state.editando = None
                    st.success("✅ Reserva atualizada com sucesso!")
                else:
                    reservas.loc[len(reservas)] = nova_reserva
                    st.success("✅ Reserva criada com sucesso!")

                salvar_dados(reservas, "reservas.csv")
                time.sleep(2)
                st.rerun()




# =========================
# 💸 Página de Estoque (mínima e estável)
# =========================


import streamlit as st
import pandas as pd
import unicodedata
import re
from datetime import datetime, timedelta


import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import unicodedata
import re

def pagina_estoque():
    st.header("📦 Controle de Estoque e Disponibilidade")

    # =====================================
    # CARREGAR DADOS
    # =====================================
    brinquedos = carregar_dados("brinquedos.csv", ["Nome", "Valor", "Status", "Categoria"])
    reservas = carregar_dados(
        "reservas.csv",
        ["Cliente", "Brinquedos", "Data", "Horário Entrega", "Horário Retirada",
         "Início Festa", "Fim Festa", "Status"]
    )

    if brinquedos.empty:
        st.warning("⚠️ Nenhum brinquedo cadastrado ainda.")
        return

    # =====================================
    # CONVERSÃO DE DATAS
    # =====================================
    def parse_data_segura(valor):
        try:
            if pd.isna(valor) or str(valor).strip() == "":
                return pd.NaT
            return pd.to_datetime(str(valor).split(" ")[0], errors="coerce").normalize()
        except Exception:
            return pd.NaT

    reservas["Data"] = reservas["Data"].apply(parse_data_segura)

    # =====================================
    # FUNÇÃO PARA NORMALIZAR NOMES
    # =====================================
    def normalizar(txt):
        if not isinstance(txt, str):
            return ""
        txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("utf-8")
        txt = re.sub(r"[^a-zA-Z0-9]+", " ", txt)
        return txt.lower().strip()

    # =====================================
    # ABAS PRINCIPAIS
    # =====================================
    aba_disponibilidade, aba_consulta, aba_agenda, aba_relatorio = st.tabs(
        ["📅 Disponibilidade por Data", "🔎 Consulta Rápida", "🗓️ Agenda Semanal", "📊 Uso dos Brinquedos"]
    )

    # ==============================================================
    # 1️⃣ ABA: DISPONIBILIDADE POR DATA
    # ==============================================================
    with aba_disponibilidade:
        data_escolhida = st.date_input("📅 Escolha uma data para verificar disponibilidade", pd.Timestamp.today())
        reservas_dia = reservas.loc[reservas["Data"] == pd.to_datetime(data_escolhida)]

        todos = []
        for _, br in brinquedos.iterrows():
            nome_brinquedo = br["Nome"]
            cat = br.get("Categoria", "Tradicional")

            reservado = False
            cliente_reserva = ""
            inicio = ""
            fim = ""

            for _, res in reservas_dia.iterrows():
                lista = str(res.get("Brinquedos", ""))
                if normalizar(nome_brinquedo) in normalizar(lista):
                    reservado = True
                    cliente_reserva = res.get("Cliente", "")
                    inicio = res.get("Início Festa", "")
                    fim = res.get("Fim Festa", "")
                    break

            status = f"🔴 Indisponível (🎉 {cliente_reserva} - {inicio} às {fim})" if reservado else "🟢 Disponível"
            todos.append({
                "Brinquedo": nome_brinquedo,
                "Categoria": cat,
                "Status": status,
                "Disponível": not reservado
            })

        df_disp = pd.DataFrame(todos)

        # =====================================
        # ABAS DINÂMICAS (com indicadores que mudam)
        # =====================================
        aba_todos, aba_trad, aba_mont = st.tabs(["🌈 Todos", "🎪 Tradicional", "🧸 Montessori"])

        def mostrar_resumo(df):
            total = len(df)
            disponiveis = len(df[df["Disponível"]])
            ocupados = total - disponiveis
            col1, col2, col3 = st.columns(3)
            col1.metric("🎠 Total", total)
            col2.metric("🟢 Disponíveis", disponiveis)
            col3.metric("🔴 Ocupados", ocupados)
            st.divider()

        def exibir_lista(df, titulo):
            mostrar_resumo(df)
            busca = st.text_input(f"🔍 Buscar {titulo.lower()} por nome:", "").strip().lower()
            if busca:
                df = df[df["Brinquedo"].str.lower().str.contains(busca, na=False)]
            for _, row in df.iterrows():
                cor_fundo = "#D4EDDA" if row["Disponível"] else "#F8D7DA"
                st.markdown(
                    f"<div style='background-color:{cor_fundo};padding:10px;border-radius:8px;margin-bottom:6px;'>"
                    f"<b>{row['Brinquedo']}</b><br>{row['Status']}</div>",
                    unsafe_allow_html=True
                )

        with aba_todos:
            exibir_lista(df_disp, "Todos")
        with aba_trad:
            exibir_lista(df_disp[df_disp["Categoria"].str.lower() == "tradicional"], "Tradicional")
        with aba_mont:
            exibir_lista(df_disp[df_disp["Categoria"].str.lower() == "montessori"], "Montessori")

    # ==============================================================
    # 2️⃣ ABA: CONSULTA RÁPIDA POR BRINQUEDO
    # ==============================================================
    with aba_consulta:
        st.subheader("🔎 Consulta rápida de disponibilidade por brinquedo")
        nome_busca = st.text_input("Digite o nome do brinquedo:", "").strip()
        if nome_busca:
            brinquedo = brinquedos[brinquedos["Nome"].str.lower().str.contains(nome_busca.lower(), na=False)]
            if brinquedo.empty:
                st.warning("Nenhum brinquedo encontrado com esse nome.")
            else:
                nome_b = brinquedo.iloc[0]["Nome"]
                hoje = datetime.today().date()
                dias = [hoje + timedelta(days=i) for i in range(15)]
                registros = []
                for d in dias:
                    data_fmt = d.strftime("%d/%m/%Y")
                    reservas_dia = reservas[reservas["Data"] == pd.to_datetime(d)]
                    reservado = False
                    cliente = ""
                    for _, r in reservas_dia.iterrows():
                        if normalizar(nome_b) in normalizar(str(r.get("Brinquedos", ""))):
                            reservado = True
                            cliente = r["Cliente"]
                            break
                    registros.append({
                        "Data": data_fmt,
                        "Status": "🔴 Reservado" if reservado else "🟢 Livre",
                        "Cliente": cliente if reservado else "-"
                    })
                st.dataframe(pd.DataFrame(registros))
        else:
            st.info("Digite o nome de um brinquedo acima para consultar as próximas datas.")

    # ==============================================================
    # 3️⃣ ABA: AGENDA SEMANAL (7 DIAS) — AGORA COM CATEGORIA
    # ==============================================================
    with aba_agenda:
        st.subheader("🗓️ Agenda dos próximos 7 dias")
        hoje = datetime.today().date()
        dias = [hoje + timedelta(days=i) for i in range(7)]
        cabecalho = ["Brinquedo", "Categoria"] + [d.strftime("%d/%m") for d in dias]
        tabela = []

        for _, br in brinquedos.iterrows():
            linha = [br["Nome"], br.get("Categoria", "Tradicional")]
            for d in dias:
                reservas_dia = reservas[reservas["Data"] == pd.to_datetime(d)]
                ocupado = any(normalizar(br["Nome"]) in normalizar(str(r.get("Brinquedos", ""))) for _, r in reservas_dia.iterrows())
                linha.append("🔴" if ocupado else "🟢")
            tabela.append(linha)

        st.dataframe(pd.DataFrame(tabela, columns=cabecalho))

    # ==============================================================
    # 4️⃣ ABA: RELATÓRIO DE UTILIZAÇÃO
    # ==============================================================
    with aba_relatorio:
        st.subheader("📊 Utilização dos Brinquedos (mês atual)")
        mes_atual = datetime.today().month
        reservas_mes = reservas[reservas["Data"].dt.month == mes_atual]
        uso = []
        for _, b in brinquedos.iterrows():
            count = reservas_mes["Brinquedos"].fillna("").apply(lambda x: normalizar(b["Nome"]) in normalizar(x)).sum()
            uso.append({"Brinquedo": b["Nome"], "Categoria": b.get("Categoria", "Tradicional"), "Dias Locado": count})
        df_uso = pd.DataFrame(uso)
        df_uso["% Utilização"] = (df_uso["Dias Locado"] / df_uso["Dias Locado"].max() * 100).fillna(0).round(1)
        st.dataframe(df_uso)



# =========================
# 💸 Página de Custos (mínima e estável)
# =========================


def pagina_custos():
    import os
    import pandas as pd
    from datetime import datetime
    import streamlit as st

    st.header("💸 Controle de Custos")

    # ─────────────────────────────────────────
    # Abas
    # ─────────────────────────────────────────
    aba = st.tabs(["📘 Lançar Custos", "🏦 Empréstimos"])

    # ============================================================
    # 🧾 ABA 1 - LANÇAR CUSTOS (igual você já tinha)
    # ============================================================
    with aba[0]:
        colunas = ["Descrição", "Categoria", "Valor", "Data", "Forma de Pagamento", "Observação"]
        caminho = "custos.csv"

        if os.path.exists(caminho):
            try:
                df = pd.read_csv(caminho, encoding="utf-8-sig")
            except Exception:
                df = pd.DataFrame(columns=colunas)
        else:
            df = pd.DataFrame(columns=colunas)
            df.to_csv(caminho, index=False, encoding="utf-8-sig")

        for c in colunas:
            if c not in df.columns:
                df[c] = ""

        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date
        df = df.reindex(columns=colunas)

        st.subheader("📆 Filtro de Período")
        hoje = datetime.now().date()
        opcoes = ["Mês Atual", "Últimos 7 dias", "Últimos 30 dias", "Período Personalizado"]
        filtro = st.radio("Selecione o intervalo:", opcoes, horizontal=True)

        if filtro == "Mês Atual":
            data_inicial = hoje.replace(day=1)
            data_final = hoje
        elif filtro == "Últimos 7 dias":
            data_inicial = hoje - pd.Timedelta(days=7)
            data_final = hoje
        elif filtro == "Últimos 30 dias":
            data_inicial = hoje - pd.Timedelta(days=30)
            data_final = hoje
        else:
            c1, c2 = st.columns(2)
            with c1:
                data_inicial = st.date_input("Data inicial", value=hoje.replace(day=1))
            with c2:
                data_final = st.date_input("Data final", value=hoje)

        filtrado = df[
            (pd.to_datetime(df["Data"]) >= pd.to_datetime(data_inicial)) &
            (pd.to_datetime(df["Data"]) <= pd.to_datetime(data_final))
        ].copy()

        total_periodo = filtrado["Valor"].sum()
        total_geral = df["Valor"].sum()
        total_itens = len(df)

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total no Período", f"R$ {total_periodo:,.2f}")
        c2.metric("📊 Total Geral", f"R$ {total_geral:,.2f}")
        c3.metric("🧾 Lançamentos", total_itens)

        st.divider()

        with st.form("form_custo"):
            descricao = st.text_input("Descrição")
            categoria = st.selectbox(
                "Categoria",
                ["Combustível", "Compra de Brinquedo", "Manutenção", "Anuncio", "Frete", "Monitor", "Auxiliar de Montagem", "Comida", "Limpeza Casa", "Outros"]
            )
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0)
            data = st.date_input("Data do custo", value=datetime.today())
            forma = st.selectbox(
                "Forma de Pagamento",
                ["Pix", "Dinheiro", "Cartão de Crédito", "Cartão de Débito", "Transferência", "Outro"]
            )
            observacao = st.text_area("Observação (opcional)")

            salvar = st.form_submit_button("💾 Salvar custo")

            if salvar:
                if descricao and valor > 0:
                    novo = {
                        "Descrição": descricao,
                        "Categoria": categoria,
                        "Valor": valor,
                        "Data": str(data),
                        "Forma de Pagamento": forma,
                        "Observação": observacao
                    }
                    df.loc[len(df)] = novo
                    df.to_csv(caminho, index=False, encoding="utf-8-sig")
                    st.success(f"✅ Custo '{descricao}' registrado com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Informe uma descrição e um valor maior que zero.")

        st.divider()

        if not filtrado.empty:
            st.subheader("📊 Resumo por Categoria")
            resumo = filtrado.groupby("Categoria")["Valor"].sum().reset_index().sort_values("Valor", ascending=False)
            for _, row in resumo.iterrows():
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:space-between;
                                background:#f9f9f9;padding:10px 15px;
                                border-left:6px solid #7A5FFF;border-radius:8px;
                                margin-bottom:8px;">
                        <strong>{row['Categoria']}</strong>
                        <span>R$ {row['Valor']:.2f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("Nenhum gasto encontrado no período selecionado.")

        st.divider()

        st.subheader("📋 Custos Registrados")
        if not filtrado.empty:
            df_sorted = filtrado.sort_values(by="Data", ascending=False)
            for i, row in df_sorted.iterrows():
                with st.expander(f"💸 {row['Descrição']} - {row['Categoria']} ({row['Data']})"):
                    st.write(f"**Valor:** R$ {row['Valor']:.2f}")
                    st.write(f"**Forma de Pagamento:** {row['Forma de Pagamento']}")
                    st.write(f"**Observação:** {row['Observação'] or '-'}")

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🗑️ Excluir", key=f"del_{i}"):
                            df = df.drop(i).reset_index(drop=True)
                            df.to_csv(caminho, index=False, encoding="utf-8-sig")
                            st.warning(f"🗑️ Custo '{row['Descrição']}' excluído!")
                            st.rerun()
        else:
            st.info("Nenhum custo cadastrado ainda.")

    # ============================================================
    # 🏦 ABA 2 - EMPRÉSTIMOS (com edição/exclusão de pagamentos)
    # ============================================================
    with aba[1]:
        st.subheader("🏦 Controle de Empréstimos")

        arq_emp = "emprestimos.csv"
        arq_pag = "pagamentos_emprestimos.csv"

        cols_emp = ["EmpID", "Descrição", "Observação", "Valor Recebido", "Valor a Pagar",
                    "Juros (%)", "Parcelas", "Valor Pendente", "Data", "Status"]
        cols_pag = ["PagID", "EmpID", "Descrição", "Valor Pago", "Data Pagamento"]

        # Garante existência dos arquivos
        if not os.path.exists(arq_emp):
            pd.DataFrame(columns=cols_emp).to_csv(arq_emp, index=False, encoding="utf-8-sig")
        if not os.path.exists(arq_pag):
            pd.DataFrame(columns=cols_pag).to_csv(arq_pag, index=False, encoding="utf-8-sig")

        df_emp = pd.read_csv(arq_emp)
        df_pag = pd.read_csv(arq_pag)

        # Backcompat: cria EmpID se não existir
        if "EmpID" not in df_emp.columns:
            df_emp.insert(0, "EmpID", range(1, len(df_emp) + 1))
        # Backcompat: cria campos faltantes
        for c in cols_emp:
            if c not in df_emp.columns:
                df_emp[c] = "" if c in ["Descrição", "Observação", "Data", "Status"] else 0

        # Backcompat pagamentos: gera PagID/EmpID se faltar
        if "PagID" not in df_pag.columns:
            df_pag.insert(0, "PagID", range(1, len(df_pag) + 1))
        if "EmpID" not in df_pag.columns:
            df_pag["EmpID"] = None
            # tentativa de mapear por descrição quando possível
            mapa = df_emp.drop_duplicates(subset=["Descrição"])[["Descrição", "EmpID"]].set_index("Descrição")["EmpID"].to_dict()
            df_pag["EmpID"] = df_pag["Descrição"].map(mapa)

        # Tipos e limpeza
        num_cols_emp = ["Valor Recebido", "Valor a Pagar", "Juros (%)", "Parcelas", "Valor Pendente"]
        for c in num_cols_emp:
            df_emp[c] = pd.to_numeric(df_emp[c], errors="coerce").fillna(0.0)
        df_emp["Parcelas"] = df_emp["Parcelas"].astype(int, errors="ignore")
        if not df_emp.empty:
            df_emp["Data"] = pd.to_datetime(df_emp["Data"], errors="coerce").dt.date

        df_pag["Valor Pago"] = pd.to_numeric(df_pag["Valor Pago"], errors="coerce").fillna(0.0)
        if not df_pag.empty:
            df_pag["Data Pagamento"] = pd.to_datetime(df_pag["Data Pagamento"], errors="coerce").dt.date

        # Recalcula "Valor Pendente" e "Status" para todos (segurança)
        if not df_emp.empty:
            soma_por_empid = df_pag.groupby("EmpID")["Valor Pago"].sum().to_dict()
            alterou = False
            for idx, row in df_emp.iterrows():
                pagos = soma_por_empid.get(row["EmpID"], 0.0)
                novo_pendente = max(0.0, float(row["Valor a Pagar"]) - float(pagos))
                novo_status = "🟢 Quitado" if novo_pendente <= 0 else "🟡 Pendente"
                if (abs(novo_pendente - float(row["Valor Pendente"])) > 1e-6) or (row.get("Status", "") != novo_status):
                    df_emp.at[idx, "Valor Pendente"] = novo_pendente
                    df_emp.at[idx, "Status"] = novo_status
                    alterou = True
            if alterou:
                df_emp.to_csv(arq_emp, index=False, encoding="utf-8-sig")

        # Cards
        total_recebido = df_emp["Valor Recebido"].sum() if not df_emp.empty else 0
        total_pagar = df_emp["Valor a Pagar"].sum() if not df_emp.empty else 0
        total_pendente = df_emp["Valor Pendente"].sum() if not df_emp.empty else 0
        total_pago = total_pagar - total_pendente if not df_emp.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Valor Recebido", f"R$ {total_recebido:,.2f}")
        c2.metric("💸 Total a Pagar", f"R$ {total_pagar:,.2f}")
        c3.metric("✅ Pago", f"R$ {total_pago:,.2f}")
        c4.metric("🟡 Pendente", f"R$ {total_pendente:,.2f}")

        st.divider()

        # Filtro Status
        filtro_status = st.radio("Filtrar por status:", ["Todos", "🟢 Quitado", "🟡 Pendente"], horizontal=True)
        df_lista = df_emp.copy()
        if filtro_status != "Todos":
            df_lista = df_lista[df_lista["Status"] == filtro_status]

        # Controle de edição
        if "editando_emp" not in st.session_state:
            st.session_state.editando_emp = None

        # Cadastro ou Edição de empréstimo
        if st.session_state.editando_emp is None:
            with st.form("novo_emprestimo"):
                descricao = st.text_input("Descrição do Empréstimo (Banco/Pessoa)")
                obs = st.text_area("Observação (motivo do empréstimo)")
                valor_recebido = st.number_input("Valor Recebido (R$)", min_value=0.0, step=100.0)
                valor_pagar = st.number_input("Valor Total a Pagar (R$)", min_value=0.0, step=100.0)
                parcelas = st.number_input("Qtd. Parcelas (informativo)", min_value=1, step=1)
                data_emp = st.date_input("Data do Empréstimo", value=datetime.today())

                salvar_emp = st.form_submit_button("💾 Registrar Empréstimo")

                if salvar_emp and descricao and valor_recebido > 0 and valor_pagar > 0:
                    juros = round(((valor_pagar - valor_recebido) / valor_recebido) * 100, 2)
                    novo_empid = 1 if df_emp.empty else int(df_emp["EmpID"].max()) + 1
                    novo = {
                        "EmpID": novo_empid,
                        "Descrição": descricao,
                        "Observação": obs,
                        "Valor Recebido": valor_recebido,
                        "Valor a Pagar": valor_pagar,
                        "Juros (%)": juros,
                        "Parcelas": int(parcelas),
                        "Valor Pendente": valor_pagar,
                        "Data": str(data_emp),
                        "Status": "🟡 Pendente"
                    }
                    df_emp.loc[len(df_emp)] = novo
                    df_emp.to_csv(arq_emp, index=False, encoding="utf-8-sig")
                    st.success("✅ Empréstimo registrado com sucesso!")
                    st.rerun()
        else:
            i = st.session_state.editando_emp
            row = df_emp.loc[df_emp["EmpID"] == i].iloc[0]

            with st.form("editar_emprestimo"):
                st.info(f"✏️ Editando empréstimo: {row['Descrição']}")
                descricao = st.text_input("Descrição", value=row["Descrição"])
                obs = st.text_area("Observação", value=row["Observação"])
                valor_recebido = st.number_input("Valor Recebido (R$)", value=float(row["Valor Recebido"]), min_value=0.0, step=100.0)
                valor_pagar = st.number_input("Valor Total a Pagar (R$)", value=float(row["Valor a Pagar"]), min_value=0.0, step=100.0)
                parcelas = st.number_input("Qtd. Parcelas", value=int(row["Parcelas"]), min_value=1, step=1)
                data_emp = st.date_input("Data", value=pd.to_datetime(row["Data"]))

                salvar_edicao = st.form_submit_button("💾 Salvar Alterações")
                cancelar_edicao = st.form_submit_button("❌ Cancelar")

                if cancelar_edicao:
                    st.session_state.editando_emp = None
                    st.rerun()

                if salvar_edicao:
                    juros = round(((valor_pagar - valor_recebido) / valor_recebido) * 100, 2)
                    # Recalcula pendente a partir dos pagamentos existentes
                    pagos = df_pag.loc[df_pag["EmpID"] == i, "Valor Pago"].sum()
                    novo_pendente = max(0.0, float(valor_pagar) - float(pagos))
                    status = "🟢 Quitado" if novo_pendente <= 0 else "🟡 Pendente"

                    df_emp.loc[df_emp["EmpID"] == i, :] = [
                        i, descricao, obs, float(valor_recebido), float(valor_pagar),
                        juros, int(parcelas), novo_pendente, str(data_emp), status
                    ]
                    df_emp.to_csv(arq_emp, index=False, encoding="utf-8-sig")
                    st.success("✅ Empréstimo atualizado com sucesso!")
                    st.session_state.editando_emp = None
                    st.rerun()

        st.divider()

        # Listagem dos empréstimos
        if not df_lista.empty:
            for _, row in df_lista.sort_values("Data").iterrows():
                empid = int(row["EmpID"])
                pendente = float(row["Valor Pendente"])
                status = row["Status"]
                data_emp = pd.to_datetime(row["Data"]).date()
                # Previsão de quitação = data + parcelas meses
                try:
                    previsao_quit = (pd.to_datetime(row["Data"]) + pd.DateOffset(months=int(row["Parcelas"]))).date()
                    previsao_str = previsao_quit.strftime("%d/%m/%Y")
                except Exception:
                    previsao_str = "-"

                with st.expander(f"🏦 {row['Descrição']} — {status} — Pendente: R$ {pendente:,.2f}"):
                    st.write(f"**Observação:** {row['Observação'] or '-'}")
                    st.write(f"**Valor Recebido:** R$ {row['Valor Recebido']:.2f}")
                    st.write(f"**Valor a Pagar:** R$ {row['Valor a Pagar']:.2f}")
                    st.write(f"**Juros:** {row['Juros (%)']}%")
                    st.write(f"**Parcelas:** {int(row['Parcelas'])}")
                    st.write(f"**Data:** {data_emp.strftime('%d/%m/%Y')}")
                    st.write(f"**Previsão de quitação:** {previsao_str}")

                    st.markdown("---")
                    st.write("### 💵 Registrar pagamento")
                    with st.form(f"form_pag_{empid}"):
                        valor_pago = st.number_input("Valor pago (R$)", min_value=0.0, step=50.0, key=f"pag_val_{empid}")
                        data_pag = st.date_input("Data do pagamento", value=datetime.today(), key=f"pag_data_{empid}")
                        pagar = st.form_submit_button("💰 Registrar Pagamento")

                        if pagar and valor_pago > 0:
                            novo_pagid = 1 if df_pag.empty else int(df_pag["PagID"].max()) + 1
                            df_pag.loc[len(df_pag)] = [novo_pagid, empid, row["Descrição"], float(valor_pago), str(data_pag)]
                            # Recalcula pendente/status
                            pagos = df_pag.loc[df_pag["EmpID"] == empid, "Valor Pago"].sum()
                            novo_pendente = max(0.0, float(row["Valor a Pagar"]) - float(pagos))
                            novo_status = "🟢 Quitado" if novo_pendente <= 0 else "🟡 Pendente"
                            df_emp.loc[df_emp["EmpID"] == empid, ["Valor Pendente", "Status"]] = [novo_pendente, novo_status]

                            df_pag.to_csv(arq_pag, index=False, encoding="utf-8-sig")
                            df_emp.to_csv(arq_emp, index=False, encoding="utf-8-sig")
                            st.success(f"✅ Pagamento de R$ {valor_pago:.2f} registrado!")
                            st.rerun()

                    # Histórico de pagamentos (com editar/excluir)
                    hist = df_pag[df_pag["EmpID"] == empid].sort_values("Data Pagamento")
                    if not hist.empty:
                        st.markdown("### 📜 Histórico de Pagamentos:")
                        for _, pg in hist.iterrows():
                            pagid = int(pg["PagID"])
                            with st.expander(f"Pagamento #{pagid} — R$ {pg['Valor Pago']:.2f} em {pd.to_datetime(pg['Data Pagamento']).strftime('%d/%m/%Y')}"):
                                with st.form(f"edit_pag_{pagid}"):
                                    novo_valor = st.number_input("Valor pago", value=float(pg["Valor Pago"]), min_value=0.0, step=50.0, key=f"edit_val_{pagid}")
                                    nova_data = st.date_input("Data do pagamento", value=pd.to_datetime(pg["Data Pagamento"]), key=f"edit_data_{pagid}")

                                    c_ed, c_del = st.columns(2)
                                    with c_ed:
                                        salvar_edit = st.form_submit_button("💾 Salvar edição")
                                    with c_del:
                                        confirmar_del = st.checkbox("Confirmar exclusão", key=f"chk_del_{pagid}")
                                        excluir_pag = st.form_submit_button("🗑️ Excluir pagamento")

                                    if salvar_edit:
                                        df_pag.loc[df_pag["PagID"] == pagid, ["Valor Pago", "Data Pagamento"]] = [float(novo_valor), str(nova_data)]
                                        # Recalcula pendente/status
                                        pagos = df_pag.loc[df_pag["EmpID"] == empid, "Valor Pago"].sum()
                                        novo_pendente = max(0.0, float(row["Valor a Pagar"]) - float(pagos))
                                        novo_status = "🟢 Quitado" if novo_pendente <= 0 else "🟡 Pendente"
                                        df_emp.loc[df_emp["EmpID"] == empid, ["Valor Pendente", "Status"]] = [novo_pendente, novo_status]

                                        df_pag.to_csv(arq_pag, index=False, encoding="utf-8-sig")
                                        df_emp.to_csv(arq_emp, index=False, encoding="utf-8-sig")
                                        st.success("✅ Pagamento atualizado!")
                                        st.rerun()

                                    if excluir_pag and confirmar_del:
                                        df_pag = df_pag[df_pag["PagID"] != pagid].reset_index(drop=True)
                                        # Recalcula pendente/status
                                        pagos = df_pag.loc[df_pag["EmpID"] == empid, "Valor Pago"].sum()
                                        novo_pendente = max(0.0, float(row["Valor a Pagar"]) - float(pagos))
                                        novo_status = "🟢 Quitado" if novo_pendente <= 0 else "🟡 Pendente"
                                        df_emp.loc[df_emp["EmpID"] == empid, ["Valor Pendente", "Status"]] = [novo_pendente, novo_status]

                                        df_pag.to_csv(arq_pag, index=False, encoding="utf-8-sig")
                                        df_emp.to_csv(arq_emp, index=False, encoding="utf-8-sig")
                                        st.warning("🗑️ Pagamento excluído!")
                                        st.rerun()

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✏️ Editar Empréstimo", key=f"edit_emp_{empid}"):
                            st.session_state.editando_emp = empid
                            st.rerun()
                    with c2:
                        if st.button("🗑️ Excluir Empréstimo", key=f"del_emp_{empid}"):
                            # Exclui pagamentos do emprestimo
                            df_pag = df_pag[df_pag["EmpID"] != empid].reset_index(drop=True)
                            df_emp = df_emp[df_emp["EmpID"] != empid].reset_index(drop=True)
                            df_pag.to_csv(arq_pag, index=False, encoding="utf-8-sig")
                            df_emp.to_csv(arq_emp, index=False, encoding="utf-8-sig")
                            st.warning(f"🗑️ Empréstimo '{row['Descrição']}' e seus pagamentos foram excluídos!")
                            st.rerun()
        else:
            st.info("Nenhum empréstimo registrado ainda.")


# ========================================
# PAGINA AGENDA
# ========================================


import streamlit as st
import pandas as pd
from datetime import datetime, date
import calendar
import time



import streamlit as st
import pandas as pd
from datetime import datetime, date
import calendar
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def pagina_agenda():
    st.markdown("""
        <style>
        .titulo-mes {
            text-align: center;
            font-size: 22px;
            font-weight: 800;
            color: #333;
            margin-bottom: 10px;
        }
        .weekday {
            text-align: center;
            font-weight: 600;
            color: #666;
            margin-bottom: 6px;
        }
        .legenda {
            margin-top: 14px;
            color: #444;
            font-size: 14px;
        }
        .pill {
            display:inline-block;padding:4px 8px;border-radius:999px;background:#f2f2f2;margin-left:8px;font-size:12px;font-weight:600;color:#333;
        }
        [title]:hover::after {
            content: attr(title);
            position: absolute;
            background: #333;
            color: #fff;
            padding: 4px 8px;
            border-radius: 6px;
            top: 120%;
            white-space: nowrap;
            z-index: 10;
            font-size: 13px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.header("📅 Agenda de Reservas")

    # ------------------ DADOS ------------------
    try:
        reservas = pd.read_csv("reservas.csv")
    except FileNotFoundError:
        st.warning("Nenhuma reserva encontrada (reservas.csv).")
        return
    if reservas.empty:
        st.info("Nenhuma reserva registrada ainda.")
        return

    reservas["Data"] = pd.to_datetime(reservas["Data"], errors="coerce")
    reservas = reservas.dropna(subset=["Data"])

    # ------------------ ESTADO ------------------
    if "mes_atual" not in st.session_state:
        hoje = date.today()
        st.session_state.mes_atual = hoje.month
        st.session_state.ano_atual = hoje.year
        st.session_state.data_selecionada = None

    # Navegação mês
    nav1, titulo, nav2 = st.columns([1, 3, 1])
    with nav1:
        if st.button("⬅️", key="mes_anterior"):
            st.session_state.mes_atual -= 1
            if st.session_state.mes_atual < 1:
                st.session_state.mes_atual = 12
                st.session_state.ano_atual -= 1
    with nav2:
        if st.button("➡️", key="mes_posterior"):
            st.session_state.mes_atual += 1
            if st.session_state.mes_atual > 12:
                st.session_state.mes_atual = 1
                st.session_state.ano_atual += 1

    mes = st.session_state.mes_atual
    ano = st.session_state.ano_atual
    nome_mes = datetime(ano, mes, 1).strftime("%B de %Y").capitalize()
    total_mes = reservas[
        (reservas["Data"].dt.month == mes) & (reservas["Data"].dt.year == ano)
    ].shape[0]

    with titulo:
        sel_badge = ""
        if st.session_state.get("data_selecionada"):
            sel_badge = f"<span class='pill'>🔵 Selecionado: {st.session_state.data_selecionada.strftime('%d/%m/%Y')}</span>"
        st.markdown(
            f"<div class='titulo-mes'>{nome_mes} <br><span style='font-size:15px;color:#666;'>Total de {total_mes} reservas</span>{sel_badge}</div>",
            unsafe_allow_html=True,
        )

    # ------------------ CALENDÁRIO ------------------
    dias_mes = pd.date_range(start=f"{ano}-{mes:02d}-01",
                             end=f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]}")
    reservas_mes = reservas[(reservas["Data"].dt.month == mes) & (reservas["Data"].dt.year == ano)]

    nomes_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    header_cols = st.columns(7)
    for i, nome in enumerate(nomes_dias):
        header_cols[i].markdown(f"<div class='weekday'>{nome}</div>", unsafe_allow_html=True)

    def badge(q):
        if q == 0: return ""
        if q == 1: return "🟨 1x"
        if q == 2: return "🟧 2x"
        return "🟥 3+"

    primeira_semana = datetime(ano, mes, 1).weekday()
    offset = primeira_semana
    linha = [None] * offset

    for dia in dias_mes:
        reservas_dia = reservas_mes[reservas_mes["Data"].dt.date == dia.date()]
        qtd = len(reservas_dia)
        nomes = ", ".join(reservas_dia["Cliente"].astype(str)) if qtd > 0 else ""
        linha.append((dia, qtd, nomes))
        if len(linha) == 7:
            cols = st.columns(7)
            for i in range(7):
                with cols[i]:
                    if linha[i]:
                        dia_obj, qtd, nomes = linha[i]
                        sel = (st.session_state.get("data_selecionada") == dia_obj.date())
                        label = f"{'**' if sel else ''}{dia_obj.day} {badge(qtd)}{'**' if sel else ''}"

                        if st.button(label, key=f"dia_{dia_obj:%Y%m%d}", use_container_width=True):
                            st.session_state.data_selecionada = dia_obj.date()
                        if nomes:
                            st.markdown(f"<small title='{nomes}'></small>", unsafe_allow_html=True)
            linha = []

    # ------------------ LEGENDA ------------------
    st.markdown(
        "<div class='legenda'>Legenda:&nbsp;&nbsp;🟨 1 reserva&nbsp;&nbsp;🟧 2 reservas&nbsp;&nbsp;🟥 3+ reservas</div>",
        unsafe_allow_html=True,
    )

    # ------------------ DETALHES ------------------
    sel = st.session_state.get("data_selecionada")
    if sel:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader(f"📆 Reservas de {sel.strftime('%d/%m/%Y')}")
        reservas_dia = reservas_mes[reservas_mes["Data"].dt.date == sel]
        if reservas_dia.empty:
            st.info("Nenhuma reserva para este dia.")
        else:
            for _, r in reservas_dia.iterrows():
                st.markdown(
                    "<div style='background:#f9f9f9;border-radius:10px;padding:10px 15px;margin-bottom:8px;"
                    "box-shadow:0 2px 4px rgba(0,0,0,0.08)'>"
                    f"<b>{r.get('Cliente','')}</b><br>"
                    f"🎠 {r.get('Brinquedo','')}<br>"
                    f"💰 Valor total: R$ {float(r.get('Valor Total',0)):.2f}"
                    "</div>",
                    unsafe_allow_html=True
                )

            # ------------------ EXPORTAR PDF ------------------
            st.markdown("### 📄 Exportar reservas do dia")
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=A4)
            pdf.setTitle(f"Reservas_{sel.strftime('%d-%m-%Y')}")
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(200, 800, f"Reservas - {sel.strftime('%d/%m/%Y')}")
            pdf.setFont("Helvetica", 12)
            y = 760
            for _, r in reservas_dia.iterrows():
                pdf.drawString(50, y, f"Cliente: {r.get('Cliente','')}")
                pdf.drawString(50, y - 15, f"Brinquedo: {r.get('Brinquedo','')}")
                pdf.drawString(50, y - 30, f"Valor Total: R$ {float(r.get('Valor Total',0)):.2f}")
                y -= 60
            pdf.save()
            buffer.seek(0)
            st.download_button(
                label="📥 Baixar PDF",
                data=buffer,
                file_name=f"Reservas_{sel.strftime('%d-%m-%Y')}.pdf",
                mime="application/pdf",
            )


def pagina_checklist():
    import pandas as pd
    from datetime import datetime
    import pytz
    import os

    st.header("📋 Check-list de Brinquedos")

    # ========================================
    # ARQUIVOS BASE
    # ========================================
    reservas = carregar_dados(
        "reservas.csv",
        ["Cliente", "Brinquedos", "Data", "Status"]
    )

    brinquedos_cadastrados = carregar_dados("brinquedos.csv", ["Nome"])
    pecas = carregar_dados("pecas_brinquedos.csv", ["Brinquedo", "Item"])
    checklist_file = "checklist.csv"

    # Garante que o arquivo de checklist exista
    if not os.path.exists(checklist_file):
        pd.DataFrame(columns=[
            "Reserva_ID", "Cliente", "Brinquedo", "Tipo", "Item", "OK",
            "Data", "Observação", "Conferido_por", "Completo"
        ]).to_csv(checklist_file, index=False, encoding="utf-8-sig")

    checklist = pd.read_csv(checklist_file)

    # Garante colunas obrigatórias
    colunas_obrigatorias = ["Reserva_ID", "Cliente", "Brinquedo", "Tipo", "Item",
                            "OK", "Data", "Observação", "Conferido_por", "Completo"]
    for col in colunas_obrigatorias:
        if col not in checklist.columns:
            checklist[col] = ""

    # ========================================
    # ABAS
    # ========================================
    aba1, aba2 = st.tabs(["✅ Realizar Check-list", "🧩 Cadastrar Peças"])

    # ========================================
    # ABA 1 - REALIZAR CHECK-LIST
    # ========================================
    with aba1:
        if reservas.empty:
            st.info("Nenhuma reserva encontrada.")
            return

        reservas["Label"] = reservas.index.astype(str) + " - " + reservas["Cliente"] + " (" + reservas["Data"].astype(str) + ")"
        sel_reserva = st.selectbox("Selecione a reserva:", reservas["Label"])

        if not sel_reserva:
            return

        reserva_idx = int(sel_reserva.split(" - ")[0])
        reserva = reservas.loc[reserva_idx]
        cliente = reserva["Cliente"]
        brinquedos_lista = [b.strip() for b in str(reserva["Brinquedos"]).split(",") if b.strip()]

        # ======== CARD DE ANDAMENTO ========
        total_brinquedos = len(brinquedos_lista)
        brinquedos_completos = checklist[
            (checklist["Reserva_ID"] == reserva_idx) &
            (checklist["Completo"] == "✅")
        ]["Brinquedo"].nunique()
        pendentes = total_brinquedos - brinquedos_completos

        progresso = (brinquedos_completos / total_brinquedos * 100) if total_brinquedos > 0 else 0

        if brinquedos_completos == total_brinquedos:
            cor, icone, texto = "#2ECC71", "✅", "Todos conferidos!"
        elif brinquedos_completos > 0:
            cor, icone, texto = "#F1C40F", "🟡", "Parcialmente conferidos"
        else:
            cor, icone, texto = "#E74C3C", "🔴", "Nenhum brinquedo conferido"

        st.markdown(f"""
            <div style="background-color:#f9f9f9;
                        border-left:6px solid {cor};
                        border-radius:10px;
                        padding:12px 20px 18px 20px;
                        margin-bottom:15px;
                        box-shadow:2px 2px 8px rgba(0,0,0,0.1);">
                <h4 style="margin:0;color:{cor};">
                    {icone} {texto} — {brinquedos_completos}/{total_brinquedos} brinquedos conferidos
                </h4>
                <div style="margin-top:10px;width:100%;background:#eee;border-radius:8px;overflow:hidden;">
                    <div style="height:18px;
                                width:{progresso:.1f}%;
                                background:{cor};
                                transition:width 0.8s ease;
                                border-radius:8px;">
                    </div>
                </div>
                <p style="margin-top:6px;color:#555;font-size:13px;">
                    🎯 Progresso: {progresso:.1f}% concluído
                </p>
            </div>
        """, unsafe_allow_html=True)

        # ======== SELEÇÃO DE BRINQUEDO ========
        brinquedo_sel = st.selectbox("Brinquedo:", brinquedos_lista)
        tipo_sel = st.radio("Tipo de check-list:", ["Entrega (Saída)", "Retirada (Volta)"], horizontal=True)
        tipo = "Entrega" if "Entrega" in tipo_sel else "Retirada"

        # Confere status de checklist
        status_checklist = checklist[
            (checklist["Reserva_ID"] == reserva_idx) &
            (checklist["Brinquedo"] == brinquedo_sel) &
            (checklist["Tipo"] == tipo)
        ]
        if not status_checklist.empty:
            st.success("✅ Este brinquedo já possui check-list registrado para este tipo.")
        else:
            st.warning("⚠️ Nenhum check-list registrado para este brinquedo ainda.")

        # Carrega peças
        pecas_brinquedo = pecas[pecas["Brinquedo"].str.lower() == brinquedo_sel.lower()]
        if pecas_brinquedo.empty:
            st.warning("⚠️ Nenhuma peça cadastrada para este brinquedo.")
            return

        st.markdown(f"### Itens de verificação – {brinquedo_sel}")
        checks = {row["Item"]: st.checkbox(row["Item"], key=f"{tipo}_{i}") for i, row in pecas_brinquedo.iterrows()}
        observacao = st.text_area("Observações (opcional):")

        # Usuário logado
        usuario_logado = st.session_state.get("usuario", "Usuário não identificado")

        # Botão salvar
        if st.button("💾 Salvar check-list"):
            registros = []
            tz_sp = pytz.timezone("America/Sao_Paulo")
            data_hora = datetime.now(tz_sp).strftime("%Y-%m-%d %H:%M")

            completo = "✅" if all(checks.values()) else "❌"

            for item, marcado in checks.items():
                registros.append({
                    "Reserva_ID": reserva_idx,
                    "Cliente": cliente,
                    "Brinquedo": brinquedo_sel,
                    "Tipo": tipo,
                    "Item": item,
                    "OK": "✅" if marcado else "❌",
                    "Data": data_hora,
                    "Observação": observacao,
                    "Conferido_por": usuario_logado,
                    "Completo": completo
                })

            df_novos = pd.DataFrame(registros)
            checklist = pd.concat([checklist, df_novos], ignore_index=True)
            checklist.to_csv(checklist_file, index=False, encoding="utf-8-sig")

            st.success("✅ Check-list salvo com sucesso!")
            st.rerun()

        # Histórico
        st.divider()
        st.subheader("📜 Histórico de check-lists")

        hist = checklist[checklist["Reserva_ID"] == reserva_idx]
        if hist.empty:
            st.info("Nenhum check-list registrado para esta reserva ainda.")
        else:
            st.dataframe(hist.sort_values(["Tipo", "Brinquedo", "Item"]),
                         use_container_width=True, hide_index=True)

    # ========================================
    # ABA 2 - CADASTRAR PEÇAS
    # ========================================
    with aba2:
        st.subheader("🧩 Cadastro de Peças por Brinquedo")

        brinquedo_novo = st.selectbox("Brinquedo:", brinquedos_cadastrados["Nome"].unique())
        nova_peca = st.text_input("Nome da peça:")
        adicionar = st.button("➕ Adicionar peça")

        if adicionar and nova_peca:
            nova_linha = pd.DataFrame([[brinquedo_novo, nova_peca]], columns=["Brinquedo", "Item"])
            pecas = pd.concat([pecas, nova_linha], ignore_index=True)
            pecas.to_csv("pecas_brinquedos.csv", index=False, encoding="utf-8-sig")
            st.success(f"✅ Peça '{nova_peca}' adicionada ao brinquedo '{brinquedo_novo}'!")
            st.rerun()

        # Card resumo
        total_pecas = len(pecas)
        total_brinquedos = pecas["Brinquedo"].nunique()

        st.markdown(f"""
            <div style="background-color:#f9f9f9;
                        border-left:6px solid #7A5FFF;
                        border-radius:10px;
                        padding:12px 20px;
                        margin-top:10px;
                        box-shadow:2px 2px 8px rgba(0,0,0,0.1);">
                <h4 style="margin:0;color:#7A5FFF;">
                    🧩 {total_pecas} peças cadastradas para {total_brinquedos} brinquedos
                </h4>
            </div>
        """, unsafe_allow_html=True)

        # Exibição das peças
        if not pecas.empty:
            st.dataframe(pecas.sort_values(["Brinquedo", "Item"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma peça cadastrada ainda.")


# ==============================
# MÓDULO FROTA – TimTim Festas
# ==============================
import os
import pandas as pd
import streamlit as st
from datetime import datetime, date

# ---------------------------------
# CONFIGURAÇÕES / CAMINHOS
# ---------------------------------
BASE_DIR = r"C:\TimTimFestas"
ARQ_VEIC = os.path.join(BASE_DIR, "veiculos.csv")
ARQ_MANU = os.path.join(BASE_DIR, "manutencoes.csv")
COLS_CUSTOS = ["Descrição","Categoria","Valor","Data","Forma de Pagamento","Observação"]


COLS_VEIC = [
    "Placa", "Modelo", "Tipo", "Ano", "Status", "Km Atual",
    "Data IPVA", "Data Licenciamento", "Data Seguro", "Observação"
]

COLS_MANU = ["Placa", "Tipo", "Descrição", "Data", "Km", "Valor (R$)"]

TIPOS_MANU = [
    "Troca de óleo", "Pneus", "Freios", "Motor",
    "Elétrica", "Suspensão", "Outros"
]

KM_TROCA_OLEO = 6000
MESES_TROCA_OLEO = 6


# ---------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------
def _garante_base():
    os.makedirs(BASE_DIR, exist_ok=True)
    if not os.path.exists(ARQ_VEIC):
        pd.DataFrame(columns=COLS_VEIC).to_csv(ARQ_VEIC, index=False, encoding="utf-8")
    if not os.path.exists(ARQ_MANU):
        pd.DataFrame(columns=COLS_MANU).to_csv(ARQ_MANU, index=False, encoding="utf-8")


def carregar_csv(caminho: str, cols: list[str]) -> pd.DataFrame:
    _garante_base()
    try:
        df = pd.read_csv(caminho, dtype=str, encoding="utf-8")
    except FileNotFoundError:
        df = pd.DataFrame(columns=cols)

    for c in cols:
        if c not in df.columns:
            df[c] = ""

    # ====== VEÍCULOS ======
    if caminho == ARQ_VEIC:
        df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce")
        if "Km Atual" in df.columns:
            df["Km Atual"] = pd.to_numeric(df["Km Atual"], errors="coerce").fillna(0).astype(int)
        if "Valor Veículo (R$)" in df.columns:
            df["Valor Veículo (R$)"] = pd.to_numeric(df["Valor Veículo (R$)"], errors="coerce").fillna(0.0)
        for dc in ["Data IPVA", "Data Licenciamento", "Data Seguro"]:
            if dc in df.columns:
                df[dc] = pd.to_datetime(df[dc], errors="coerce").dt.date

    # ====== MANUTENÇÕES ======
    elif caminho == ARQ_MANU:
        if "Km" in df.columns:
            df["Km"] = pd.to_numeric(df["Km"], errors="coerce").fillna(0).astype(int)
        if "Valor (R$)" in df.columns:
            df["Valor (R$)"] = pd.to_numeric(df["Valor (R$)"], errors="coerce").fillna(0.0)
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date

    # ====== CUSTOS ======
    elif caminho.endswith("custos.csv"):
        if "Valor" in df.columns:
            df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date

    # ====== HISTÓRICO DE KM ======
    elif caminho.endswith("km_log.csv"):
        if "Km" in df.columns:
            df["Km"] = pd.to_numeric(df["Km"], errors="coerce").fillna(0).astype(int)
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date

    # ====== OUTROS ======
    else:
        for col in ["Km", "Valor (R$)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date

    return df[cols]




def salvar_csv(df: pd.DataFrame, caminho: str):
    df.to_csv(caminho, index=False, encoding="utf-8")


def meses_passados(d1: date, d2: date) -> int:
    if pd.isna(d1) or d1 is None or pd.isna(d2) or d2 is None:
        return 9999
    return (d2.year - d1.year) * 12 + (d2.month - d1.month) - (1 if d2.day < d1.day else 0)


def alerta_vencimento(rotulo: str, data_venc: date):
    if data_venc is None or pd.isna(data_venc):
        st.info(f"{rotulo}: sem data informada.")
        return
    delta = (data_venc - date.today()).days
    if delta < 0:
        st.error(f"❌ {rotulo} vencido em {abs(delta)} dias ({data_venc.strftime('%d/%m/%Y')}).")
    elif delta <= 15:
        st.warning(f"⚠️ {rotulo} vence em {delta} dias ({data_venc.strftime('%d/%m/%Y')}).")
    else:
        st.success(f"✅ {rotulo} em dia (vence {data_venc.strftime('%d/%m/%Y')}).")


def proxima_troca_oleo_alerta(veic_row: pd.Series, df_manu: pd.DataFrame):
    placa = veic_row["Placa"]
    km_atual = int(veic_row.get("Km Atual", 0) or 0)
    manu_placa = df_manu[(df_manu["Placa"] == placa) & (df_manu["Tipo"] == "Troca de óleo")].copy()
    manu_placa = manu_placa.sort_values("Data", ascending=False)

    if manu_placa.empty:
        st.info("🔧 Troca de óleo: sem histórico cadastrado.")
        return

    ultima = manu_placa.iloc[0]
    data_ult = ultima["Data"]
    km_ult = int(ultima["Km"] or 0)

    meses = meses_passados(data_ult, date.today())
    km_diff = max(0, km_atual - km_ult)

    precisa = (km_diff >= KM_TROCA_OLEO) or (meses >= MESES_TROCA_OLEO)

    if precisa:
        st.warning(
            f"⚠️ Troca de óleo vencida • Última: {data_ult.strftime('%d/%m/%Y')} aos {km_ult} km "
            f"• {km_diff} km / {meses} mês(es) desde então."
        )
    else:
        st.success(
            f"✅ Troca de óleo em dia • Última: {data_ult.strftime('%d/%m/%Y')} aos {km_ult} km "
            f"• +{km_diff} km / {meses} mês(es) desde então."
        )


# ---------------------------------
# PÁGINA PRINCIPAL – FROTA
# ---------------------------------


def pagina_frota():
    st.markdown(
        """
        <style>
        .tt-card{border:1px solid #eee;border-radius:16px;padding:12px;margin-bottom:10px;background:#FFF4B5;box-shadow:0 1px 3px rgba(0,0,0,.06)}
        .tt-title{font-weight:700;color:#7A5FFF}
        .tt-muted{font-size:12px;color:#444}
        </style>
        """,
        unsafe_allow_html=True
    )

    st.header("🚗 Controle de Frota")

    # ==== Carregamento dos dados ====
    veiculos = carregar_csv("veiculos.csv", [
        "Placa","Modelo","Tipo","Ano","Status","Km Atual","Valor Veículo (R$)",
        "Data IPVA","Data Licenciamento","Data Seguro",
        "IPVA Pago","Licenciamento Pago","Seguro Pago","Observação"
    ])
    manutencoes = carregar_csv("manutencoes.csv", [
        "Placa","Tipo","Descrição","Data","Km","Valor (R$)"
    ])

    # 🔧 Corrige tipos (principalmente os campos Pago)
    TRUE_SET = {"true","1","sim","yes","y","verdadeiro","pago","ok"}
    for pago_col in ["IPVA Pago","Licenciamento Pago","Seguro Pago"]:
        veiculos[pago_col] = veiculos[pago_col].apply(lambda x: str(x).strip().lower() in TRUE_SET)
    for dcol in ["Data IPVA","Data Licenciamento","Data Seguro"]:
        veiculos[dcol] = pd.to_datetime(veiculos[dcol], errors="coerce").dt.date
    veiculos["Km Atual"] = pd.to_numeric(veiculos["Km Atual"], errors="coerce").fillna(0).astype(int)
    veiculos["Valor Veículo (R$)"] = pd.to_numeric(veiculos["Valor Veículo (R$)"], errors="coerce").fillna(0.0)

    # ==== Cards topo ====
    tot_veic = len(veiculos)
    tot_manu = manutencoes["Valor (R$)"].sum() if not manutencoes.empty else 0.0
    soma_frota = veiculos["Valor Veículo (R$)"].sum() if not veiculos.empty else 0.0
    ult_manu = manutencoes["Data"].max() if not manutencoes.empty else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚘 Veículos", f"{tot_veic}")
    c2.metric("💵 Gasto em manutenções", f"R$ {tot_manu:,.2f}")
    c3.metric("🧾 Valor total da frota", f"R$ {soma_frota:,.2f}")
    c4.metric("🗓️ Última manutenção", ult_manu.strftime("%d/%m/%Y") if pd.notna(pd.to_datetime(ult_manu)) else "-")

    aba1, aba2, aba3, aba4 = st.tabs(["Cadastro de Veículos", "Manutenções", "Resumo & Alertas", "Controle"])

    # =======================
    # 📋 ABA 1 - CADASTRO
    # =======================
    with aba1:
        st.subheader("Cadastrar / Atualizar Veículo")

        with st.form("cad_veic", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                placa = st.text_input("Placa").upper().strip()
                tipo = st.selectbox("Tipo", ["Kombi","Carro","Moto","Van","Pickup","Outro"])
                ano = st.number_input("Ano", min_value=1970, max_value=date.today().year+1, value=date.today().year)
            with col2:
                modelo = st.text_input("Modelo")
                status = st.selectbox("Status", ["Ativo","Em manutenção","Inativo"])
                km_atual = st.number_input("Km Atual", min_value=0, step=100, value=0)
            with col3:
                valor_veic = st.number_input("Valor do veículo (R$)", min_value=0.0, step=100.0, value=0.0)

            col4, col5, col6 = st.columns(3)
            with col4:
                ipva = st.date_input("Data IPVA", value=None)
                ipva_pago = st.checkbox("IPVA Pago", value=False)
            with col5:
                lic = st.date_input("Data Licenciamento", value=None)
                lic_pago = st.checkbox("Licenciamento Pago", value=False)
            with col6:
                seg = st.date_input("Data Seguro", value=None)
                seg_pago = st.checkbox("Seguro Pago", value=False)

            obs = st.text_area("Observações")
            btn = st.form_submit_button("Salvar veículo ✅")
            if btn:
                if not placa or not modelo:
                    st.error("Informe Placa e Modelo.")
                else:
                    novo = pd.DataFrame([{
                        "Placa": placa, "Modelo": modelo, "Tipo": tipo, "Ano": int(ano),
                        "Status": status, "Km Atual": int(km_atual),
                        "Valor Veículo (R$)": float(valor_veic),
                        "Data IPVA": ipva, "Data Licenciamento": lic, "Data Seguro": seg,
                        "IPVA Pago": ipva_pago, "Licenciamento Pago": lic_pago, "Seguro Pago": seg_pago,
                        "Observação": obs
                    }])
                    if placa in veiculos["Placa"].values:
                        veiculos.loc[veiculos["Placa"] == placa] = novo.iloc[0]
                        st.success(f"Veículo {placa} atualizado!")
                    else:
                        veiculos = pd.concat([veiculos, novo], ignore_index=True)
                        st.success(f"Veículo {placa} cadastrado!")
                    salvar_csv(veiculos, "veiculos.csv")

        if not veiculos.empty:
            st.dataframe(veiculos, use_container_width=True)
        else:
            st.info("Nenhum veículo cadastrado.")

    # =======================
    # 🔧 ABA 2 - MANUTENÇÕES
    # =======================
    with aba2:
        st.subheader("Registrar Manutenção")
        if veiculos.empty:
            st.warning("Cadastre um veículo primeiro.")
        else:
            with st.form("cad_manu"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    placa_m = st.selectbox("Placa", veiculos["Placa"])
                    tipo_m = st.selectbox("Tipo de manutenção", TIPOS_MANU)
                with col2:
                    data_m = st.date_input("Data", value=date.today())
                    km_m = st.number_input("Km", min_value=0, step=100, value=0)
                with col3:
                    valor_m = st.number_input("Valor (R$)", min_value=0.0, step=10.0)
                desc_m = st.text_area("Descrição / Observação")
                btn_m = st.form_submit_button("Salvar manutenção ✅")
                if btn_m:
                    nova = pd.DataFrame([{
                        "Placa": placa_m, "Tipo": tipo_m, "Descrição": desc_m,
                        "Data": data_m, "Km": km_m, "Valor (R$)": valor_m
                    }])
                    manutencoes = pd.concat([manutencoes, nova], ignore_index=True)
                    salvar_csv(manutencoes, "manutencoes.csv")
                    st.success(f"Manutenção '{tipo_m}' registrada para {placa_m}!")

                    # Integração com custos.csv
                    try:
                        custos = carregar_csv("custos.csv", COLS_CUSTOS)
                        novo_custo = {
                            "Descrição": f"Manutenção {tipo_m} - {placa_m}",
                            "Categoria": "Manutenção de Frota",
                            "Valor": valor_m,
                            "Data": data_m,
                            "Forma de Pagamento": "Outro",
                            "Observação": desc_m
                        }
                        custos.loc[len(custos)] = novo_custo
                        salvar_csv(custos, "custos.csv")
                        st.info("📥 Lançado em custos.csv (Manutenção de Frota).")
                    except Exception as e:
                        st.warning(f"Não foi possível lançar em custos.csv: {e}")

    # =======================
    # 📊 ABA 3 - RESUMO & ALERTAS
    # =======================
    with aba3:
        st.subheader("Resumo e Alertas")

        # previsões de custos
        hoje = date.today()
        def pendentes(df, col_data, col_pago):
            df = df[~df[col_pago]]
            datas = pd.to_datetime(df[col_data], errors="coerce").dt.date
            total = len(datas.dropna())
            mes = sum((d and d.month == hoje.month and d.year == hoje.year) for d in datas)
            return total, mes

        ipva_t, ipva_m = pendentes(veiculos,"Data IPVA","IPVA Pago")
        lic_t, lic_m = pendentes(veiculos,"Data Licenciamento","Licenciamento Pago")
        seg_t, seg_m = pendentes(veiculos,"Data Seguro","Seguro Pago")

        c1, c2, c3 = st.columns(3)
        c1.metric("🧾 IPVA pendente", ipva_t, delta=f"este mês: {ipva_m}")
        c2.metric("📄 Licenciamento pendente", lic_t, delta=f"este mês: {lic_m}")
        c3.metric("🛡️ Seguro pendente", seg_t, delta=f"este mês: {seg_m}")

        # alertas
        for _, v in veiculos.iterrows():
            st.markdown(f"<div class='tt-card'><div class='tt-title'>{v['Placa']} — {v['Modelo']}</div>", unsafe_allow_html=True)
            if v["IPVA Pago"]:
                st.success("✅ IPVA está pago.")
            else:
                alerta_vencimento("IPVA", v["Data IPVA"])
            if v["Licenciamento Pago"]:
                st.success("✅ Licenciamento está pago.")
            else:
                alerta_vencimento("Licenciamento", v["Data Licenciamento"])
            if v["Seguro Pago"]:
                st.success("✅ Seguro está pago.")
            else:
                alerta_vencimento("Seguro", v["Data Seguro"])
            proxima_troca_oleo_alerta(v, manutencoes)
            st.markdown("</div>", unsafe_allow_html=True)

    # =======================
    # ⚙️ ABA 4 - CONTROLE
    # =======================
    with aba4:
        st.subheader("Controle do Veículo (Atualização Rápida)")

        if veiculos.empty:
            st.info("Cadastre um veículo para usar esta aba.")
            return

        placa_sel = st.selectbox("Selecione a placa", veiculos["Placa"].unique())
        row = veiculos[veiculos["Placa"] == placa_sel].iloc[0]

        col1, col2, col3 = st.columns(3)
        with col1:
            km_q = st.number_input("Km Atual", min_value=0, step=100, value=int(row["Km Atual"]))
            ipva_pago_q = st.checkbox("IPVA Pago", value=bool(row["IPVA Pago"]))
        with col2:
            lic_pago_q = st.checkbox("Licenciamento Pago", value=bool(row["Licenciamento Pago"]))
            seg_pago_q = st.checkbox("Seguro Pago", value=bool(row["Seguro Pago"]))
        with col3:
            data_ipva_q = st.date_input("Venc. IPVA", value=row["Data IPVA"])
            data_lic_q = st.date_input("Venc. Licenciamento", value=row["Data Licenciamento"])
            data_seg_q = st.date_input("Venc. Seguro", value=row["Data Seguro"])

        c4, c5 = st.columns([2,1])
        with c4:
            if st.button("💾 Salvar atualização", use_container_width=True):
                veiculos.loc[veiculos["Placa"] == placa_sel, [
                    "Km Atual","IPVA Pago","Licenciamento Pago","Seguro Pago",
                    "Data IPVA","Data Licenciamento","Data Seguro"
                ]] = [int(km_q), ipva_pago_q, lic_pago_q, seg_pago_q, data_ipva_q, data_lic_q, data_seg_q]
                salvar_csv(veiculos, "veiculos.csv")

                # log de km
                km_log = carregar_csv("km_log.csv", ["Placa","Data","Km"])
                km_log.loc[len(km_log)] = [placa_sel, date.today(), km_q]
                salvar_csv(km_log, "km_log.csv")

                st.success("✅ Atualização salva!")
                st.rerun()

        with c5:
            if st.button("✅ Marcar tudo como pago", use_container_width=True):
                veiculos.loc[veiculos["Placa"] == placa_sel, ["IPVA Pago","Licenciamento Pago","Seguro Pago"]] = True
                salvar_csv(veiculos, "veiculos.csv")
                st.success("Todos os pagamentos marcados como quitados!")
                st.rerun()

        # gráfico de evolução do KM
        st.markdown("### 📈 Evolução do KM")
        km_log = carregar_csv("km_log.csv", ["Placa","Data","Km"])
        df_km = km_log[km_log["Placa"] == placa_sel]
        if not df_km.empty:
            df_km["Data"] = pd.to_datetime(df_km["Data"], errors="coerce")
            df_km = df_km.sort_values("Data")
            st.line_chart(df_km.set_index("Data")["Km"])
        else:
            st.info("Ainda sem histórico de KM.")



# =========================
# 📲 Módulo Envio WhatsApp
# =========================

def pagina_whatsapp():
    import pandas as pd
    from datetime import datetime, date
    import streamlit.components.v1 as components
    import base64

    st.header("💬 Central WhatsApp e Suporte")

    # =========================
    # Abas principais
    # =========================
    aba1, aba2, aba3 = st.tabs(["🧰 Suporte Técnico", "📲 Envio WhatsApp", "📘 Portfólio Montessori"])

    # =========================
    # 🧰 ABA 1 - SUPORTE TÉCNICO
    # =========================
    with aba1:
        st.subheader("📖 Informações e respostas rápidas")
        st.info("""
        Esta aba será usada para armazenar respostas e instruções rápidas para suporte aos clientes.

        **Tatames:**
        
        - Tons Cinzas: 100 Tatames
        - Tons Azuis Antigo: 20 Tatames
        - Tons Azuis Novo: 65 Tatames
        - Tons Beges: 20 Tatames
        
        **      Quantidade Tatames ideal para kit Montessori:**
        
        - Kit doçura: 5m² (20) Com base nos bege
        - Kit doçura: 10m² (40) Com base nos em outros tatames
        - Kit alegria: 11 a 16m² (45 a 65)
        - Kit encanto: 18 a 25m² (70 a 100)
        - Kit TimTim: 20 a 25m² (80 a 100) 
        
         **Base calculo frete:**
        - Montessori - R$ 5,00 por KM
        - Tradicional - R$ 3,00 Por KM
        - Menor que 5KM, insento
        
         **Dados Técnico brinquedos:**
        - Cama Elastica 2,44: Aguenta até 70kg, até 3 crianças por vez que não ultrapasse o peso.
        - Cama Elastica 1,83: Aguenta até 60kg, até 2 crianças por vez que não ultrapasse o peso.
        - Tombo Legal: Aguenta até 70kg, 1 crianças por vez, BiVolt, necessário tomada proxima.
        - Mesa Air Game: Sem limite de idade, 120v, necessário tomada proxima.

    

        ✏️ *Você poderá editar esta seção diretamente no código para atualizar suas informações internas.*
        """)

    # =========================
    # 📲 ABA 2 - ENVIO WHATSAPP (seu código original)
    # =========================
    with aba2:
        usuario_logado = st.session_state.get("usuario", "")
        if usuario_logado not in ["Bruno", "Maryanne"]:
            st.warning("⚠️ Você não tem permissão para acessar esta página.")
            return

        # =========================
        # Carregamento de dados
        # =========================
        reservas = carregar_dados(
            "reservas.csv",
            ["Cliente", "Brinquedos", "Data", "Horário Entrega", "Horário Retirada",
             "Início Festa", "Fim Festa", "Valor Total", "Sinal", "Falta", "Frete", "Status"]
        )
        clientes = carregar_dados(
            "clientes.csv",
            ["Nome", "CEP"]
        )

        if reservas.empty:
            st.info("Nenhuma reserva encontrada.")
            return

        reservas["Data"] = pd.to_datetime(reservas["Data"], errors="coerce")
        reservas = reservas.dropna(subset=["Data"])

        reservas = reservas.merge(
            clientes, how="left", left_on="Cliente", right_on="Nome"
        ).drop(columns=["Nome"], errors="ignore")
        reservas["CEP"] = reservas["CEP"].fillna("")

        hoje = pd.Timestamp.now().normalize()

        # =========================
        # Filtros principais
        # =========================
        col1, col2, col3 = st.columns(3)
        with col1:
            mes_sel = st.selectbox(
                "📅 Mês:",
                options=[
                    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
                    (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
                    (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro")
                ],
                index=hoje.month - 1,
                format_func=lambda x: x[1]
            )[0]
        with col2:
            ano_sel = st.number_input("📆 Ano:", min_value=2023, max_value=2100, value=hoje.year, step=1)
        with col3:
            filtro_periodo = st.radio(
                "📍 Exibir:",
                ["Todas as datas", "Somente futuras", "Hoje e futuras"],
                horizontal=True
            )

        df = reservas[
            (reservas["Data"].dt.month == mes_sel) &
            (reservas["Data"].dt.year == ano_sel)
        ].copy()

        if filtro_periodo == "Somente futuras":
            df = df[df["Data"] > hoje]
        elif filtro_periodo == "Hoje e futuras":
            df = df[df["Data"] >= hoje]

        if df.empty:
            st.warning("⚠️ Nenhuma reserva encontrada para o período selecionado.")
            return

        # =========================
        # Cards Resumo do Mês
        # =========================
        total_reservas = len(df)
        futuras = len(df[df["Data"] > hoje])
        concluidas = len(df[df["Status"].str.lower() == "concluído"])

        c1, c2, c3 = st.columns(3)
        for col, (titulo, valor, cor) in zip(
            [c1, c2, c3],
            [
                ("📅 Total de Reservas", total_reservas, "#7A5FFF"),
                ("🚀 Futuras", futuras, "#2ECC71"),
                ("✅ Concluídas", concluidas, "#3498DB"),
            ]
        ):
            col.markdown(
                f"""
                <div style="background-color:#fff;border-left:6px solid {cor};
                            border-radius:12px;padding:10px;text-align:center;
                            box-shadow:2px 2px 10px rgba(0,0,0,0.1);">
                    <div style="color:#555;">{titulo}</div>
                    <div style="font-size:1.6em;font-weight:bold;">{valor}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        # =========================
        # Geração de mensagens
        # =========================
        df = df.sort_values("Data")
        mensagens = []
        for _, row in df.iterrows():
            data_formatada = row["Data"].strftime("%d/%m")
            cliente = row.get("Cliente", "")
            brinquedos = row.get("Brinquedos", "")
            cep = str(row.get("CEP", "")).replace(".0", "").strip()
            inicio_festa = row.get("Início Festa", "")
            fim_festa = row.get("Fim Festa", "")
            entrega = row.get("Horário Entrega", "")
            retirada = row.get("Horário Retirada", "")
            valor_total = row.get("Valor Total", 0.0)
            sinal = row.get("Sinal", 0.0)
            falta = row.get("Falta", 0.0)
            frete = row.get("Frete", 0.0)

            msg = f"📍 {data_formatada} – {cliente}\n"
            if cep:
                msg += f"🗺️ CEP: {cep}\n"
            if inicio_festa and fim_festa:
                msg += f"⏰ Horário Festa: {inicio_festa} - {fim_festa}\n"
            msg += f"🕘 Montagem: {entrega} | 🕘 Retirada: {retirada}\n"
            msg += f"🎠 {brinquedos}\n"
            if frete > 0:
                msg += f"🚚 Frete: R$ {frete:,.2f}\n"
            msg += f"💰 Total: R$ {valor_total:,.2f}\n"
            msg += f"💳 Pagou: R$ {sinal:,.2f} | 💸 Falta: R$ {falta:,.2f}\n"
            mensagens.append(msg.strip())

        texto_final = "\n────────────\n".join(mensagens)

        st.subheader(f"📆 Reservas de {ano_sel} – Mês {mes_sel:02d}")
        st.text_area("Mensagens geradas:", texto_final, height=500, key="mensagens_whatsapp")

        # =========================
        # Botões de cópia
        # =========================
        copiar_js = f"""
            <script>
            function copiarTexto() {{
                const texto = `{texto_final}`;
                navigator.clipboard.writeText(texto).then(() => {{
                    alert("✅ Texto copiado para a área de transferência!");
                }});
            }}
            function copiarPorData() {{
                let hoje = new Date().toLocaleDateString('pt-BR');
                const linhas = `{texto_final}`.split("────────────");
                const filtradas = linhas.filter(l => l.includes(hoje));
                if (filtradas.length > 0) {{
                    navigator.clipboard.writeText(filtradas.join("\\n\\n")).then(() => {{
                        alert("📅 Texto do dia copiado!");
                    }});
                }} else {{
                    alert("⚠️ Nenhuma reserva encontrada para hoje!");
                }}
            }}
            </script>
            <div style="display:flex;gap:10px;">
                <button onclick="copiarTexto()" style="background-color:#7A5FFF;color:white;border:none;
                        border-radius:8px;padding:10px 20px;font-weight:bold;cursor:pointer;">
                    📋 Copiar tudo
                </button>
                <button onclick="copiarPorData()" style="background-color:#2ECC71;color:white;border:none;
                        border-radius:8px;padding:10px 20px;font-weight:bold;cursor:pointer;">
                    📅 Copiar só hoje
                </button>
            </div>
        """
        components.html(copiar_js, height=80)

    # =========================
    # 📘 ABA 3 - PORTFÓLIO MONTESSORI
    # =========================
    with aba3:
        st.subheader("📘 Portfólio de Brinquedos Montessori")
        pdf_path = "Portfólio brinquedos Montessori Timtim - Out 2025.pdf"

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.error("❌ Arquivo do portfólio não encontrado. Verifique se o PDF está na pasta do aplicativo.")




from pathlib import Path
import unicodedata, re
from datetime import datetime

def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s) or "foto"

def _fotos_dir() -> Path:
    # garante a pasta ao lado do app.py
    base = Path(__file__).parent if "__file__" in globals() else Path.cwd()
    d = base / "fotos_funcionarios"
    d.mkdir(parents=True, exist_ok=True)
    return d

def salvar_foto_imediato(foto_bytes: bytes, nome_hint: str, ext: str = ".jpg") -> str:
    """
    Salva imediatamente a foto em fotos_funcionarios e
    retorna caminho RELATIVO em formato POSIX (string).
    """
    fotos_dir = _fotos_dir()
    fname = f"{_slugify(nome_hint)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    destino = fotos_dir / fname
    with open(destino, "wb") as f:
        f.write(foto_bytes)
    # retorna relativo ao app (portável)
    rel = destino.relative_to(Path(__file__).parent if "__file__" in globals() else Path.cwd())
    return rel.as_posix()


def pagina_funcionarios():
    import re
    import pandas as pd
    from datetime import datetime, date
    from pathlib import Path
    import streamlit as st

    st.header("👥 Controle de Funcionários")

    # ======================================
    # 🗂️ Estrutura e carregamento de dados
    # ======================================
    arquivo = "funcionarios.csv"
    colunas = [
        "Nome", "CPF", "Cargo", "Categoria", "Telefone",
        "Data Nascimento", "Data Admissao", "Status",
        "Foto", "Observacao"
    ]
    df = carregar_dados(arquivo, colunas).fillna("")
    df["Foto"] = df["Foto"].astype(str).replace(["nan", "None", "0"], "")

    # ======================================
    # 🔧 Estados iniciais
    # ======================================
    if "show_camera" not in st.session_state:
        st.session_state.show_camera = False
    if "ultima_foto_salva" not in st.session_state:
        st.session_state.ultima_foto_salva = ""
    if "confirmar_exclusao" not in st.session_state:
        st.session_state.confirmar_exclusao = None

    # ======================================
    # 📊 Cards: totais, ativos, inativos, etc.
    # ======================================
    def _calc_idade(dt):
        if pd.isna(dt):
            return None
        hoje = date.today()
        anos = hoje.year - dt.year - ((hoje.month, hoje.day) < (dt.month, dt.day))
        return max(0, anos)

    def _meses_de_casa(dt):
        if pd.isna(dt):
            return None
        hoje = date.today()
        return (hoje.year - dt.year) * 12 + (hoje.month - dt.month) - (1 if hoje.day < dt.day else 0)

    total_func = len(df)
    ativos = (df["Status"].str.strip().str.lower() == "ativo").sum()
    inativos = (df["Status"].str.strip().str.lower() == "inativo").sum()
    com_foto = (df["Foto"].str.strip() != "").sum()

    # idade média
    idades = []
    for v in pd.to_datetime(df["Data Nascimento"], errors="coerce"):
        idade = _calc_idade(v) if pd.notna(v) else None
        if idade is not None:
            idades.append(idade)
    idade_media = round(sum(idades) / len(idades), 1) if idades else 0.0

    # tempo médio de empresa (em anos.meses)
    meses_list = []
    for v in pd.to_datetime(df["Data Admissao"], errors="coerce"):
        m = _meses_de_casa(v) if pd.notna(v) else None
        if m is not None and m >= 0:
            meses_list.append(m)
    if meses_list:
        media_meses = int(round(sum(meses_list) / len(meses_list)))
        anos_med = media_meses // 12
        meses_med = media_meses % 12
        tempo_medio_str = f"{anos_med}a {meses_med}m"
    else:
        tempo_medio_str = "0a 0m"

    # 🎂 Contagem de aniversariantes do mês
    mes_atual = date.today().month
    aniversariantes_mes = 0
    for v in pd.to_datetime(df["Data Nascimento"], errors="coerce"):
        if pd.notna(v) and v.month == mes_atual:
            aniversariantes_mes += 1

    # Render dos cards
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    cards = [
        ("👥 Total", total_func, "#7A5FFF"),
        ("🟢 Ativos", ativos, "#2ECC71"),
        ("🔴 Inativos", inativos, "#E74C3C"),
        ("📸 Com foto", com_foto, "#3498DB"),
        ("🎂 Idade média", f"{idade_media} anos", "#F39C12"),
        ("⏱️ Tempo médio", tempo_medio_str, "#16A085"),
        ("🎉 Aniversariantes", aniversariantes_mes, "#9B59B6"),
    ]
    for col, (label, value, color) in zip([c1, c2, c3, c4, c5, c6, c7], cards):
        col.markdown(
            f"""
            <div style="background-color:#f9f9f9; border-left:6px solid {color};
                        border-radius:12px; padding:14px; text-align:center;
                        box-shadow:2px 2px 10px rgba(0,0,0,0.08);">
                <div style="font-size:0.95em;color:#555;">{label}</div>
                <div style="font-size:1.5em;font-weight:800;">{value}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # ======================================
    # 🔍 Busca
    # ======================================
    st.divider()
    busca = st.text_input("🔎 Buscar funcionário pelo nome:")
    df_view = df.copy()
    if busca:
        df_view = df_view[df_view["Nome"].str.contains(busca, case=False, na=False)]

    st.subheader("➕ Cadastrar / Editar Funcionário")

    editando = st.session_state.get("editando", None)
    funcionario_editar = df_view.iloc[editando] if (editando is not None and editando < len(df_view)) else None

    # ======================================
    # 🧾 Formulário
    # ======================================
    with st.form("form_funcionario"):
        nome = st.text_input("👤 Nome completo", value=funcionario_editar["Nome"] if funcionario_editar is not None else "")
        cpf_input = st.text_input("🪪 CPF", value=funcionario_editar["CPF"] if funcionario_editar is not None else "")
        cpf_clean = re.sub(r"\D", "", cpf_input)
        cpf = f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}" if len(cpf_clean) == 11 else cpf_input

        telefone_input = st.text_input("📞 Telefone / WhatsApp", value=funcionario_editar["Telefone"] if funcionario_editar is not None else "")
        tel_clean = re.sub(r"\D", "", telefone_input)
        telefone = f"({tel_clean[:2]}) {tel_clean[2:7]}-{tel_clean[7:]}" if len(tel_clean) == 11 else telefone_input

        cargo = st.text_input("💼 Cargo / Função", value=funcionario_editar["Cargo"] if funcionario_editar is not None else "")
        categoria = st.selectbox("🏷️ Categoria", ["Efetivo", "Temporário", "Parceiro"],
                                 index=["Efetivo", "Temporário", "Parceiro"].index(funcionario_editar["Categoria"])
                                 if funcionario_editar is not None else 0)

        data_nasc = st.date_input("🎂 Data de nascimento",
                                  value=pd.to_datetime(funcionario_editar["Data Nascimento"], errors="coerce").date()
                                  if funcionario_editar is not None else date(1989, 1, 1),
                                  min_value=date(1950, 1, 1), max_value=date.today())

        data_adm = st.date_input("📅 Data de admissão",
                                 value=pd.to_datetime(funcionario_editar["Data Admissao"], errors="coerce").date()
                                 if funcionario_editar is not None else date.today(),
                                 min_value=date(2000, 1, 1), max_value=date.today())

        status = st.selectbox("⚙️ Status", ["Ativo", "Inativo"],
                              index=["Ativo", "Inativo"].index(funcionario_editar["Status"])
                              if funcionario_editar is not None else 0)

        observacao = st.text_area("📝 Observações", value=funcionario_editar["Observacao"] if funcionario_editar is not None else "")

        st.markdown("### 📸 Foto do funcionário")
        foto_path = funcionario_editar["Foto"] if funcionario_editar is not None else ""

        if foto_path:
            p = Path(foto_path.replace("\\", "/"))
            if not p.is_absolute():
                p = Path.cwd() / p
            if p.exists():
                st.image(p.as_posix(), width=150, caption="📷 Foto atual")

        uploaded_file = st.file_uploader("Enviar nova foto (.jpg ou .png)", type=["jpg", "jpeg", "png"], key="upload_foto")

        salvar = st.form_submit_button("💾 Salvar Funcionário")

        if salvar:
            if uploaded_file is not None:
                ext = "." + (uploaded_file.type.split("/")[-1] if uploaded_file.type else "jpg")
                if ext.lower() not in [".jpg", ".jpeg", ".png"]:
                    ext = ".jpg"
                hint = nome or uploaded_file.name
                foto_path = salvar_foto_imediato(uploaded_file.getvalue(), hint, ext=ext)
            elif st.session_state.ultima_foto_salva:
                foto_path = st.session_state.ultima_foto_salva

            if not nome.strip():
                st.error("⚠️ O nome é obrigatório.")
            else:
                novo = {
                    "Nome": nome, "CPF": cpf, "Cargo": cargo, "Categoria": categoria,
                    "Telefone": telefone, "Data Nascimento": data_nasc,
                    "Data Admissao": data_adm, "Status": status,
                    "Foto": foto_path, "Observacao": observacao
                }

                df_full = carregar_dados(arquivo, colunas).fillna("")
                if funcionario_editar is not None and editando < len(df_full):
                    df_full.loc[editando] = novo
                    st.success("✏️ Funcionário atualizado com sucesso!")
                    st.session_state.editando = None
                else:
                    df_full.loc[len(df_full)] = novo
                    st.success("✅ Funcionário cadastrado com sucesso!")

                salvar_dados(df_full, arquivo)
                st.rerun()

    # ======================================
    # 📷 Câmera
    # ======================================
    st.divider()
    st.subheader("📷 Capturar foto com a câmera")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("📸 Abrir câmera"):
            st.session_state.show_camera = True
    with col_b:
        if st.button("❌ Fechar câmera"):
            st.session_state.show_camera = False

    if st.session_state.show_camera:
        foto_cam = st.camera_input("Tire a foto e clique em 'Take Photo' 👇", key="cam_func")
        if foto_cam is not None:
            hint = nome or "funcionario"
            foto_path_cam = salvar_foto_imediato(foto_cam.getvalue(), hint, ext=".jpg")
            st.session_state.ultima_foto_salva = foto_path_cam
            st.image(foto_path_cam, width=150, caption="📸 Foto capturada e salva")
            st.success(f"Foto salva em: {foto_path_cam}")

    # ======================================
    # 📋 Lista de Funcionários
    # ======================================
    st.divider()
    st.subheader("📋 Funcionários cadastrados")

    df_list = carregar_dados(arquivo, colunas).fillna("")
    if df_list.empty:
        st.info("Nenhum funcionário cadastrado.")
        return

    def tempo_casa_str(dt):
        if pd.isna(dt):
            return "?"
        hoje = date.today()
        anos = hoje.year - dt.year - ((hoje.month, hoje.day) < (dt.month, dt.day))
        meses_total = (hoje.year - dt.year) * 12 + hoje.month - dt.month - (1 if hoje.day < dt.day else 0)
        return f"{anos}a {meses_total % 12}m"

    for i, row in df_list.iterrows():
        with st.container():
            col1, col2 = st.columns([1, 3])
            with col1:
                foto_val = str(row["Foto"]).strip().replace("\\", "/")
                if foto_val:
                    p = Path(foto_val)
                    if not p.is_absolute():
                        p = Path.cwd() / p
                    if p.exists():
                        st.image(p.as_posix(), width=120)
                    else:
                        st.image("https://via.placeholder.com/120x120.png?text=Sem+Foto", width=120)
                else:
                    st.image("https://via.placeholder.com/120x120.png?text=Sem+Foto", width=120)

            with col2:
                dn = pd.to_datetime(row["Data Nascimento"], errors="coerce")
                is_bday_month = (pd.notna(dn) and dn.month == mes_atual)

                nome_display = f"**{row['Nome']}**"
                if is_bday_month:
                    nome_display += (
                        " <span style='background-color:#EDE0FF; color:#7A5FFF; "
                        "padding:3px 8px; border-radius:8px; font-size:0.8em; "
                        "font-weight:600; margin-left:6px;'>🎉 Parabéns!</span>"
                    )

                st.markdown(nome_display, unsafe_allow_html=True)
                st.caption(f"{row['Cargo']} • {row['Categoria']}")

                status_icon = "🟢" if str(row["Status"]).strip().lower() == "ativo" else "🔴"
                idade = (date.today().year - dn.year) if pd.notna(dn) else "?"
                da = pd.to_datetime(row["Data Admissao"], errors="coerce")
                tempo = tempo_casa_str(da) if pd.notna(da) else "?"

                st.write(f"{status_icon} {row['Status']} • 🎂 {idade} anos • ⏱️ {tempo}")

                if row["Telefone"]:
                    num = re.sub(r"\D", "", str(row["Telefone"]))
                    st.markdown(f"[💬 WhatsApp](https://wa.me/55{num})", unsafe_allow_html=True)

                with st.expander("🔽 Ver mais detalhes"):
                    st.write(f"**CPF:** {row['CPF']}")
                    st.write(f"**Nascimento:** {row['Data Nascimento']}")
                    st.write(f"**Admissão:** {row['Data Admissao']}")
                    st.write(f"**Observações:** {row['Observacao']}")

                col_ed, col_del = st.columns(2)
                with col_ed:
                    if st.button("✏️ Editar", key=f"edit_{i}"):
                        st.session_state.editando = i
                        st.rerun()

                with col_del:
                    if st.session_state.get("confirmar_exclusao") == i:
                        st.warning(f"⚠️ Confirmar exclusão de {row['Nome']}?")
                        col_c, col_d = st.columns(2)
                        with col_c:
                            if st.button("✅ Sim, excluir", key=f"confirma_{i}"):
                                df2 = carregar_dados(arquivo, colunas).fillna("")
                                if i in df2.index:
                                    df2.drop(i, inplace=True)
                                    df2.reset_index(drop=True, inplace=True)
                                    salvar_dados(df2, arquivo)
                                st.success(f"{row['Nome']} foi removido com sucesso.")
                                st.session_state.confirmar_exclusao = None
                                st.rerun()
                        with col_d:
                            if st.button("❌ Cancelar", key=f"cancela_{i}"):
                                st.session_state.confirmar_exclusao = None
                                st.rerun()
                    else:
                        if st.button("🗑️ Excluir", key=f"del_{i}"):
                            st.session_state.confirmar_exclusao = i
                            st.rerun()


# ========================================
# PROGRAMA PRINCIPAL
# ========================================
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    login()
else:
    st.sidebar.image("logo.png", use_container_width=True)
    st.sidebar.title(f"Bem-vindo, {st.session_state['usuario']} 👋")

    # ========================================
    # MENU LATERAL ESTILIZADO - COM LOGO E ANIMAÇÃO
    # ========================================
    st.sidebar.markdown("""
        <style>
            div[data-testid="stSidebar"] { background-color: #FFF4B5; }
            .logo-container {
                background-color: white;
                border-radius: 15px;
                padding: 15px;
                text-align: center;
                margin: 15px 10px 25px 10px;
                box-shadow: 2px 2px 10px rgba(0,0,0,0.15);
                border: 3px solid transparent;
                background-clip: padding-box;
                animation: bordaColorida 4s infinite linear;
            }
            @keyframes bordaColorida {
                0% { border-color: #7A5FFF; }
                25% { border-color: #2ECC71; }
                50% { border-color: #3498DB; }
                75% { border-color: #F1C40F; }
                100% { border-color: #E74C3C; }
            }
            .logo-container h1 {
                font-size: 20px; color: #7A5FFF; font-weight: 800; margin-bottom: 5px;
            }
            .logo-container p {
                font-size: 14px; color: #555; margin-top: 0px;
            }
            .menu-card {
                background-color: #f9f9f9; border-radius: 12px; padding: 15px;
                margin-bottom: 12px; text-align: center; font-weight: bold;
                font-size: 16px; color: #333; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
                transition: all 0.3s ease-in-out; cursor: pointer; border-left: 6px solid transparent;
            }
            @keyframes brilho {
                0% { box-shadow: 0 0 4px rgba(255,255,255,0.3); }
                50% { box-shadow: 0 0 12px rgba(255,255,255,0.8); }
                100% { box-shadow: 0 0 4px rgba(255,255,255,0.3); }
            }
            .indicadores:hover { background-color: #7A5FFF !important; color: white !important; border-left: 6px solid #4C32E3 !important; animation: brilho 1.5s infinite; }
            .brinquedos:hover  { background-color: #2ECC71 !important; color: white !important; border-left: 6px solid #239B56 !important; animation: brilho 1.5s infinite; }
            .clientes:hover    { background-color: #3498DB !important; color: white !important; border-left: 6px solid #1A5276 !important; animation: brilho 1.5s infinite; }
            .reservas:hover    { background-color: #F1C40F !important; color: white !important; border-left: 6px solid #B7950B !important; animation: brilho 1.5s infinite; }
            .sair:hover        { background-color: #E74C3C !important; color: white !important; border-left: 6px solid #922B21 !important; animation: brilho 1.5s infinite; }
            div[data-testid="stRadio"] label div[data-baseweb="radio"] div[role="radio"][aria-checked="true"] div {
                background-color: #EEE9FF !important; border-left: 6px solid #7A5FFF !important;
                color: #4C32E3 !important; font-weight: bold; box-shadow: 2px 2px 8px rgba(0,0,0,0.15);
                transform: scale(1.03);
            }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover > div {
                transform: scale(1.04);
            }
        </style>
    """, unsafe_allow_html=True)


    # 🔹 MENU DE OPÇÕES
    menu_opcoes = {
            "Indicadores": ("📈 Indicadores", "indicadores"),
            "Brinquedos": ("🎠 Brinquedos", "brinquedos"),
            "Clientes": ("👨‍👩‍👧 Clientes", "clientes"),
            "Reservas": ("📅 Reservas", "reservas"),
            "Agenda": ("🕓 Agenda", "agenda"),
            "Custos": ("💸 Custos", "custos"), 
            "Estoque": ("📦 Estoque", "estoque"),    
            "Check-list": ("✅ Check-list", "check-list"), 
            "Frota": ("🚗 Frota", "frota"),
            "Funcionários": ("👷 Funcionários", "funcionarios"),
            "Envio WhatsApp": ("📲 Suporte", "envio_whatsapp"),
            "Sair": ("🚪 Sair", "sair")
    }

    st.sidebar.markdown("### 📋 Menu Principal")
    
    
    menu = st.sidebar.radio(
        "",
        options=list(menu_opcoes.keys()),
        format_func=lambda x: menu_opcoes[x][0],
        key="menu_principal"
    )
    
    
   # 💜 Rodapé fixo - BRN Solutions (ajustado)
    from datetime import datetime
    ano = datetime.now().year

    st.sidebar.markdown(
        f"""
        <style>
            /* Garante que a sidebar ocupe toda a altura e permita o rodapé no final */
            [data-testid="stSidebar"] > div:first-child {{
                display: flex;
                flex-direction: column;
                height: 100%;
            }}
            /* Container do rodapé */
            .brn-footer {{
                margin-top: auto;
                text-align: center;
                font-size: 0.8em;
                color: #555;
                opacity: 0.8;
                line-height: 1.4;
                border-top: 1px solid rgba(0,0,0,0.1);
                padding-top: 8px;
                padding-bottom: 6px;
                streamlit run app.py
            }}
            .brn-footer strong {{
                color: #7A5FFF;
            }}
        </style>

        <div class="brn-footer">
            <strong>BRN Solutions</strong><br>
            © {ano} Todos os direitos reservados
        </div>
        """,
        unsafe_allow_html=True
    )

    # 🧭 NAVEGAÇÃO ENTRE PÁGINAS
    if menu == "Brinquedos":
        pagina_brinquedos()
    elif menu == "Clientes":
        pagina_clientes()
    elif menu == "Reservas":
        pagina_reservas()
    elif menu == "Indicadores":
        pagina_relatorios()
    elif menu == "Custos":
         pagina_custos()
    elif menu == "Agenda":
        pagina_agenda()
    elif menu == "Estoque":
        pagina_estoque()
    elif menu == "Check-list":
        pagina_checklist()
    elif menu == "Frota":
        pagina_frota()
    elif menu == "Funcionários":
        pagina_funcionarios()
    elif menu == "Envio WhatsApp":
        pagina_whatsapp()      
    elif menu == "Sair":
        st.session_state["logado"] = False
        st.experimental_rerun()



