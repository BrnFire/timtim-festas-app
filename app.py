import streamlit as st
import pandas as pd
import requests
import os
import json
import time 
from datetime import datetime
from dateutil import parser
from banco import carregar_dados, salvar_dados
from banco import _ensure_cols

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
    import pandas as pd
    import matplotlib.pyplot as plt
    from datetime import datetime, date
    import streamlit as st
    from pandas.tseries.offsets import MonthBegin

    st.header("📈 Relatórios e Indicadores")

    # =========================
    # 📦 Carregamento de dados
    # =========================
    reservas = carregar_dados("reservas", ["id",
        "cliente", "brinquedos", "data",
        "horario_entrega", "horario_retirada",
        "valor_total", "valor_extra", "frete", "desconto",
        "sinal", "falta", "observacao", "status", "pagamentos"
    ])
    custos = carregar_dados("custos", ["data", "descricao", "valor"])
    brinquedos_df = carregar_dados("brinquedos", ["nome", "valor", "categoria"])

    # =========================
    # 🧩 Tratamento de datas
    # =========================
    def parse_data_segura(v):
        try:
            if pd.isna(v) or str(v).strip() == "":
                return pd.NaT
            s = str(v).split(" ")[0]
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return pd.to_datetime(datetime.strptime(s, fmt)).normalize()
                except:
                    continue
            return pd.to_datetime(s, dayfirst=True, errors="coerce").normalize()
        except:
            return pd.NaT

    for df in [reservas, custos]:
        if "data" in df.columns:
            df["data"] = df["data"].apply(parse_data_segura)

    reservas = reservas.dropna(subset=["data"])
    custos = custos.dropna(subset=["data"])

    # =========================
    # 🔢 Conversões numéricas
    # =========================
    for col in ["valor_total", "valor_extra", "frete", "desconto", "sinal"]:
        if col not in reservas.columns:
            reservas[col] = 0.0
        reservas[col] = pd.to_numeric(reservas[col], errors="coerce").fillna(0.0)

    custos["valor"] = pd.to_numeric(custos.get("valor", 0), errors="coerce").fillna(0.0)

    # =========================
    # 📅 Agregações mensais
    # =========================
    # Garante que as colunas "data" sejam realmente datetimes
    for df_tmp in [reservas, custos]:
        if "data" in df_tmp.columns:
            df_tmp["data"] = pd.to_datetime(df_tmp["data"], errors="coerce")

    # Remove linhas sem data válida
    reservas = reservas.dropna(subset=["data"])
    custos = custos.dropna(subset=["data"])

    # Se não tiver nenhum dado válido, evita quebrar a página
    if reservas.empty and custos.empty:
        st.warning("Ainda não há dados suficientes para montar os indicadores.")
        return

    reservas["anomes"] = reservas["data"].dt.to_period("M").astype(str)
    custos["anomes"] = custos["data"].dt.to_period("M").astype(str)

    reservas["bruto"] = reservas["valor_total"].clip(lower=0)
    bruto_mensal = reservas.groupby("anomes", as_index=False)["bruto"].sum()
    custo_mensal = (
        custos.groupby("anomes", as_index=False)["valor"]
        .sum()
        .rename(columns={"valor": "custo"})
    )
    reservas["qtd_reservas"] = 1
    reservas_mensal = reservas.groupby("anomes", as_index=False)["qtd_reservas"].sum()


    df_fin_mensal = pd.merge(bruto_mensal, custo_mensal, on="anomes", how="outer").fillna(0)
    df_fin_mensal["liquido"] = (df_fin_mensal["bruto"] - df_fin_mensal["custo"]).clip(lower=0)
    df_fin_mensal = df_fin_mensal.sort_values("anomes")

    # =========================
    # 💳 Totais (cards)
    # =========================
    total_realizado = reservas["sinal"].sum()
    custo_total = custos["valor"].sum()
    liquido_total = df_fin_mensal["liquido"].sum()
    total_reservas = len(reservas)

    # ROI médio
    df_tmp = df_fin_mensal.copy()
    df_tmp["roi"] = (df_tmp["liquido"] / df_tmp["bruto"].replace(0, pd.NA)) * 100
    df_tmp["roi"] = pd.to_numeric(df_tmp["roi"], errors="coerce").fillna(0.0)
    roi_medio = df_tmp["roi"].mean()

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        ("💰 Total Realizado", f"R$ {total_realizado:,.2f}", "#2ECC71"),
        ("📉 Custos Totais", f"R$ {custo_total:,.2f}", "#E74C3C"),
        ("📊 Lucro Bruto", f"R$ {liquido_total:,.2f}", "#0078D7"),
        ("🎟️ Reservas", total_reservas, "#F1C40F"),
        ("📈 ROI Médio", f"{roi_medio:.1f}%", "#9B59B6"),
    ]
    for col, (titulo, valor, cor) in zip([c1, c2, c3, c4, c5], cards):
        col.markdown(
            f"""
            <div style="background-color:#f9f9f9; border-left:6px solid {cor};
                        border-radius:10px; padding:15px; text-align:center;
                        box-shadow:2px 2px 10px rgba(0,0,0,0.1);">
                <div style="font-size:1em;color:#555;">{titulo}</div>
                <div style="font-size:1.5em;font-weight:bold;">{valor}</div>
            </div>
            """, unsafe_allow_html=True
        )

    st.divider()

    # =========================
    # 🔄 Abas
    # =========================
    aba1, aba2 = st.tabs(["📊 Indicadores Financeiros", "🎠 Desempenho de Brinquedos"])

    # ===== ABA 1 =====
    with aba1:
        st.subheader("📈 Lucro Bruto × Líquido × Meta")

        anos_disp = sorted(df_fin_mensal["anomes"].str[:4].astype(int).unique())
        ano_sel = st.selectbox("Selecione o ano:", anos_disp, index=len(anos_disp) - 1)

        # ===== Carregar metas =====
        df_meta = carregar_dados("metas", ["anomes", "meta"])
        if df_meta.empty:
            base = pd.date_range(start="2024-01-01", end="2026-12-01", freq="MS")
            df_meta = pd.DataFrame({"anomes": base.strftime("%Y-%m"), "meta": [3000.0 for _ in base]})
            salvar_dados(df_meta, "metas")

        # Editor de metas
        with st.expander("🎯 Editar metas mensais até dez/2026"):
            for i, row in df_meta.iterrows():
                try:
                    mes_nome = pd.to_datetime(row["anomes"], format="%Y-%m").strftime("%B/%Y").capitalize()
                except Exception:
                    mes_nome = str(row["anomes"])
                col1, col2 = st.columns([2, 1])
                col1.write(f"Meta de **{mes_nome}**:")
                try:
                    meta_val = float(row["meta"]) if str(row["meta"]).strip() not in ["", "None", "nan"] else 0.0
                except Exception:
                    meta_val = 0.0
                nova_meta = col2.number_input(
                    f"Meta {row['anomes']}",
                    min_value=0.0,
                    value=meta_val,
                    step=100.0,
                    key=f"meta_{i}"
                )
                df_meta.at[i, "meta"] = nova_meta

            if st.button("💾 Salvar metas"):
                salvar_dados(df_meta, "metas")
                st.success("✅ Metas atualizadas!")
                st.rerun()

        # ===== Preparar gráfico principal =====
        df_fin_mensal["anomes"] = (
            pd.to_datetime(df_fin_mensal["anomes"], errors="coerce").dt.strftime("%Y-%m")
        )
        df_meta["anomes"] = (
            pd.to_datetime(df_meta["anomes"], errors="coerce").dt.strftime("%Y-%m")
        )

        df_meta["meta"] = pd.to_numeric(df_meta["meta"], errors="coerce").fillna(0.0)
        df_plot = pd.merge(df_meta, df_fin_mensal, on="anomes", how="left").fillna(0.0)
        df_plot["data_plot"] = pd.to_datetime(df_plot["anomes"], format="%Y-%m", errors="coerce")
        df_plot = df_plot.sort_values("data_plot")

        if not df_plot.empty:
            fig, ax = plt.subplots(figsize=(9, 4))
            ax.plot(df_plot["data_plot"], df_plot["liquido"], label="Lucro Líquido", marker="o")
            ax.plot(df_plot["data_plot"], df_plot["bruto"], label="Lucro Bruto", marker="s")
            ax.plot(df_plot["data_plot"], df_plot["meta"], label="Meta (até 12/2026)", linestyle="--", color="#FF9800")
            ax.set_xlabel("Mês")
            ax.set_ylabel("R$")
            ax.grid(True, linestyle="--", alpha=0.6)
            ax.legend()
            ax.set_xticks(df_plot["data_plot"])
            ax.set_xticklabels(df_plot["data_plot"].dt.strftime("%b/%y"), rotation=45)
            ax.set_title(f"Lucro Bruto, Líquido e Metas até Dez/2026 (Ano atual: {ano_sel})")
            st.pyplot(fig)

        # ===== ROI corrigido =====
        st.markdown("### 📊 ROI (%) por Mês")
        if not df_plot.empty:
            df_plot["roi"] = (df_plot["liquido"] / df_plot["bruto"].replace(0, pd.NA)) * 100
            df_plot["roi"] = df_plot["roi"].replace([pd.NA, float("inf"), -float("inf")], 0).fillna(0)
            if df_plot["roi"].abs().sum() > 0:
                fig3, ax3 = plt.subplots(figsize=(9, 3))
                ax3.plot(df_plot["data_plot"], df_plot["roi"], color="#7A5FFF", marker="o")
                ax3.axhline(0, color="gray", linestyle="--", linewidth=0.8)
                ax3.set_xlabel("Mês")
                ax3.set_ylabel("ROI (%)")
                ax3.set_xticks(df_plot["data_plot"])
                ax3.set_xticklabels(df_plot["data_plot"].dt.strftime("%b/%y"), rotation=45)
                ax3.set_title("Retorno sobre Investimento (ROI) Mensal")
                ax3.grid(True, linestyle="--", alpha=0.6)
                st.pyplot(fig3)
            else:
                st.info("Ainda não há dados suficientes para calcular ROI.")

    # ===== ABA 2 =====
    with aba2:
        st.subheader("🎠 Desempenho de Brinquedos")

        if reservas.empty:
            st.info("Sem reservas registradas.")
            return

        # ===== Explode brinquedos item a item
        linhas = []
        for _, r in reservas.iterrows():
            itens = [b.strip() for b in str(r["brinquedos"]).split(",") if b.strip()]
            if not itens:
                continue
            bruto_res = (r["valor_total"] + r["valor_extra"] + r["frete"] - r["desconto"])
            bruto_res = max(bruto_res, 0.0)
            valor_item = bruto_res / len(itens)
            for b in itens:
                linhas.append({"Brinquedo": b, "Data": r["data"], "Valor_Item": valor_item})

        itens_df = pd.DataFrame(linhas)
        if itens_df.empty:
            st.warning("Sem dados de brinquedos.")
            return

        # Corrigir categorias
        if not brinquedos_df.empty and "nome" in brinquedos_df.columns:
            brinquedos_df["categoria"] = brinquedos_df.get("categoria", "Tradicional").fillna("Tradicional")
            itens_df = itens_df.merge(
                brinquedos_df[["nome", "categoria"]],
                left_on="Brinquedo", right_on="nome", how="left"
            )
            itens_df.drop(columns=["nome"], inplace=True, errors="ignore")
        else:
            itens_df["categoria"] = "Tradicional"

        # Corrigir valores nulos
        itens_df["Valor_Item"] = pd.to_numeric(itens_df["Valor_Item"], errors="coerce").fillna(0.0)

        # ===== Rankings
        rank_valor = (
            itens_df.groupby("Brinquedo", as_index=False)
                    .agg(Valor_Total=("Valor_Item", "sum"), Locações=("Valor_Item", "count"))
                    .sort_values(["Valor_Total", "Locações"], ascending=[False, False])
        )

        st.markdown("### 💰 Top 15 Brinquedos por Valor")
        fig2, ax2 = plt.subplots(figsize=(9, 4))
        ax2.barh(rank_valor["Brinquedo"].head(15), rank_valor["Valor_Total"].head(15), color="#7A5FFF")
        ax2.invert_yaxis()
        ax2.set_xlabel("R$")
        ax2.set_ylabel("Brinquedo")
        ax2.grid(axis="x", linestyle="--", alpha=0.5)
        st.pyplot(fig2)

        st.markdown("### 🔢 Top 15 Brinquedos por Locações")
        fig3, ax3 = plt.subplots(figsize=(9, 4))
        ax3.barh(rank_valor["Brinquedo"].head(15), rank_valor["Locações"].head(15), color="#2ECC71")
        ax3.invert_yaxis()
        ax3.set_xlabel("Locações")
        ax3.set_ylabel("Brinquedo")
        ax3.grid(axis="x", linestyle="--", alpha=0.5)
        st.pyplot(fig3)



def pagina_brinquedos():
    import streamlit as st
    import pandas as pd
    from datetime import datetime
    from uuid import uuid4
    from banco import carregar_dados, inserir_um, atualizar_um, deletar_por_filtro

    st.header("🎠 Cadastro de Brinquedos")

    # ======================================
    # GARANTIR DF EXISTENTE
    # ======================================
    df = pd.DataFrame(columns=["id_brinquedo", "nome", "valor", "valor_compra", "data_compra", "status", "categoria"])

    # ======================================
    # CARREGAR DADOS
    # ======================================
    try:
        df = carregar_dados("brinquedos", ["id_brinquedo", "nome", "valor", "valor_compra", "data_compra", "status", "categoria"])
    except Exception as e:
        st.error(f"❌ Erro ao carregar brinquedos: {e}")

    for col in ["valor_compra", "data_compra", "categoria"]:
        if col not in df.columns:
            if col == "valor_compra":
                df[col] = 0.0
            elif col == "categoria":
                df[col] = "Tradicional"
            else:
                df[col] = ""

    # ======================================
    # FUNÇÕES AUXILIARES
    # ======================================
    def formatar_reais(valor):
        try:
            return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "R$ 0,00"

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

    # ======================================
    # INDICADORES NO TOPO
    # ======================================
    total_brinquedos = len(df)
    total_disponiveis = len(df[df["status"] == "Disponível"])
    total_indisponiveis = len(df[df["status"] == "Indisponível"])
    total_investido = df["valor_compra"].astype(float).sum()

    total_tradicional = len(df[df["categoria"] == "Tradicional"])
    total_montessori = len(df[df["categoria"] == "Montessori"])

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

    # ======================================
    # FORMULÁRIO DE CADASTRO / EDIÇÃO
    # ======================================
    if "editando_brinquedo" in st.session_state and st.session_state.editando_brinquedo is not None:
        i = st.session_state.editando_brinquedo
        brinquedo_edicao = df.iloc[i].to_dict()
        st.info(f"✏️ Editando brinquedo: {brinquedo_edicao['nome']}")
    else:
        brinquedo_edicao = {
            "id_brinquedo": "",
            "nome": "",
            "valor": 0.0,
            "valor_compra": 0.0,
            "data_compra": "",
            "status": "Disponível",
            "categoria": "Tradicional"
        }

    form_key = f"form_brinquedo_{st.session_state.get('editando_brinquedo', 'novo')}"
    with st.form(form_key):
        nome = st.text_input("Nome do brinquedo", value=brinquedo_edicao["nome"])
        valor = st.number_input("Valor de locação (R$)", min_value=0.0, step=10.0, value=float(brinquedo_edicao["valor"]))
        valor_compra = st.number_input("Valor de compra (R$)", min_value=0.0, step=10.0, value=float(brinquedo_edicao["valor_compra"]))
        data_compra = st.date_input(
            "Data de compra",
            value=pd.to_datetime(brinquedo_edicao["data_compra"], errors="coerce") if brinquedo_edicao["data_compra"] else datetime.today()
        )
        categoria = st.selectbox(
            "Categoria",
            ["Tradicional", "Montessori"],
            index=0 if brinquedo_edicao.get("categoria", "Tradicional") == "Tradicional" else 1
        )
        status = st.selectbox(
            "Status",
            ["Disponível", "Indisponível"],
            index=0 if brinquedo_edicao["status"] != "Indisponível" else 1
        )

        enviar = st.form_submit_button("💾 Salvar brinquedo")

        if enviar and nome:
            dados = {
                "nome": nome,
                "valor": float(valor),
                "valor_compra": float(valor_compra),
                "data_compra": str(data_compra),
                "status": status,
                "categoria": categoria,
            }

            if brinquedo_edicao.get("id_brinquedo"):
                atualizar_um("brinquedos", {"id_brinquedo": brinquedo_edicao["id_brinquedo"]}, dados)
                st.success(f"✅ {nome} atualizado com sucesso!")
            else:
                dados["id_brinquedo"] = str(uuid4())
                inserir_um("brinquedos", dados)
                st.success(f"✅ {nome} cadastrado com sucesso!")

            st.session_state.editando_brinquedo = None
            st.rerun()

    # ======================================
    # LISTAGEM DE BRINQUEDOS
    # ======================================
    st.subheader("📋 Brinquedos cadastrados")

    aba_todos, aba_tradicional, aba_montessori = st.tabs(["📋 Todos", "🎪 Tradicional", "🧩 Montessori"])

    def mostrar_resumo_e_lista(df_cat, categoria_nome):
        total = len(df_cat)
        disponiveis = len(df_cat[df_cat["status"] == "Disponível"])
        indisponiveis = len(df_cat[df_cat["status"] == "Indisponível"])

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
            cor_status = "🟢" if row["status"] == "Disponível" else "🔴"
            fundo_card = "#E8F8F5" if row["status"] == "Disponível" else "#FDEDEC"
            cor_badge = "#2ECC71" if row["status"] == "Disponível" else "#E74C3C"
            tempo_uso = calcular_tempo_uso(row["data_compra"])

            with st.expander(f"{cor_status} {row['nome']}"):
                st.markdown(
                    f"""
                    <div style='background-color:{fundo_card}; padding:15px; border-radius:10px;
                                box-shadow:2px 2px 10px rgba(0,0,0,0.1); position:relative;'>

                        <span style='position:absolute; top:10px; right:10px;
                                     background-color:{cor_badge}; color:white; padding:4px 10px;
                                     border-radius:8px; font-size:12px; font-weight:bold;'>
                            {row['status']}
                        </span>
                    """,
                    unsafe_allow_html=True
                )
                st.write(f"**Categoria:** {row['categoria']}")
                st.write(f"**Valor de locação:** {formatar_reais(row['valor'])}")
                st.write(f"**Valor de compra:** {formatar_reais(row['valor_compra'])}")
                st.write(f"**Data de compra:** {row['data_compra'] if row['data_compra'] else '-'}")
                st.write(f"**Tempo de uso:** {tempo_uso}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_brinquedo_{i}_{categoria_nome}"):
                        st.session_state.editando_brinquedo = i
                        st.rerun()
                with col2:
                    if st.button("🗑️ Excluir", key=f"del_brinquedo_{i}_{categoria_nome}"):
                        deletar_por_filtro("brinquedos", {"id_brinquedo": row["id_brinquedo"]})
                        st.warning(f"🗑️ {row['nome']} removido com sucesso!")
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

    with aba_todos:
        mostrar_resumo_e_lista(df, "Todos os brinquedos")

    with aba_tradicional:
        mostrar_resumo_e_lista(df[df["categoria"] == "Tradicional"], "Tradicional")

    with aba_montessori:
        mostrar_resumo_e_lista(df[df["categoria"] == "Montessori"], "Montessori")




def pagina_clientes():
    import re
    import requests
    import pandas as pd
    from datetime import date
    import streamlit as st
    from banco import carregar_dados, inserir_um, atualizar_um, deletar_por_filtro

    st.header("👨‍👩‍👧 Cadastro de Clientes")

    # --------------------------------------
    # Colunas principais (snake_case)
    # --------------------------------------
    colunas = [
        "nome", "telefone", "email", "tipo_cliente", "rg", "cpf", "cnpj",
        "como_conseguiu", "logradouro", "numero", "complemento",
        "bairro", "cidade", "cep", "observacao"
    ]

    # Carrega também o id_cliente (para editar/excluir sem duplicar)
    try:
        df = carregar_dados("clientes", colunas + ["id_cliente"]).fillna("")
    except Exception as e:
        st.error(f"❌ Erro ao carregar clientes: {e}")
        df = pd.DataFrame(columns=colunas + ["id_cliente"])

    if "id_cliente" not in df.columns:
        df["id_cliente"] = ""  # fallback

    # --------------------------------------
    # Estado (edição)
    # --------------------------------------
    if "editando_cliente" not in st.session_state:
        st.session_state.editando_cliente = None  # índice visual
    if "editando_cliente_id" not in st.session_state:
        st.session_state.editando_cliente_id = None  # UUID real

    # Cliente em edição (se houver)
    if st.session_state.editando_cliente is not None and not df.empty:
        i = st.session_state.editando_cliente
        if i in df.index:
            cliente_edicao = df.loc[i].to_dict()
            st.session_state.editando_cliente_id = cliente_edicao.get("id_cliente") or None
            st.info(f"✏️ Editando cliente: {cliente_edicao.get('nome','')}")
        else:
            cliente_edicao = {c: "" for c in (colunas + ["id_cliente"])}
            st.session_state.editando_cliente_id = None
    else:
        cliente_edicao = {c: "" for c in (colunas + ["id_cliente"])}
        st.session_state.editando_cliente_id = None

    # Inicializa cache de endereço (para Buscar CEP)
    for campo in ["logradouro", "bairro", "cidade"]:
        if campo not in st.session_state:
            st.session_state[campo] = cliente_edicao.get(campo, "")

    # --------------------------------------
    # Formulário
    # --------------------------------------
    with st.form("form_cliente"):
        nome = st.text_input("Nome do cliente", value=cliente_edicao.get("nome", ""))

        telefone_raw = re.sub(r"\D", "", str(cliente_edicao.get("telefone", "")))
        telefone_raw = st.text_input("Telefone (somente números)", value=telefone_raw, max_chars=11)
        if telefone_raw.isdigit() and len(telefone_raw) >= 10:
            telefone = f"({telefone_raw[:2]}) {telefone_raw[2:7]}-{telefone_raw[7:]}"
        else:
            telefone = telefone_raw

        email = st.text_input("Email", value=cliente_edicao.get("email", ""))

        tipo_cliente = st.radio(
            "Tipo de Cliente",
            ["Pessoa Física", "Pessoa Jurídica"],
            index=0 if cliente_edicao.get("tipo_cliente", "Pessoa Física") != "Pessoa Jurídica" else 1
        )

        # RG
        rg_raw = st.text_input("RG", value=str(cliente_edicao.get("rg", "")))
        rg_num = re.sub(r"\D", "", rg_raw)
        rg = f"{rg_num[:2]}.{rg_num[2:5]}.{rg_num[5:]}" if len(rg_num) >= 7 else rg_raw

        cpf, cnpj = cliente_edicao.get("cpf", ""), cliente_edicao.get("cnpj", "")
        if tipo_cliente == "Pessoa Física":
            cpf_raw = st.text_input("CPF", value=str(cliente_edicao.get("cpf", "")))
            cpf_num = re.sub(r"\D", "", cpf_raw)
            cpf = f"{cpf_num[:3]}.{cpf_num[3:6]}.{cpf_num[6:9]}-{cpf_num[9:]}" if len(cpf_num) == 11 else cpf_raw
            cnpj = ""
        else:
            cnpj_raw = st.text_input("CNPJ", value=str(cliente_edicao.get("cnpj", "")))
            cnpj_num = re.sub(r"\D", "", cnpj_raw)
            cnpj = f"{cnpj_num[:2]}.{cnpj_num[2:5]}.{cnpj_num[5:8]}/{cnpj_num[8:12]}-{cnpj_num[12:]}" if len(cnpj_num) == 14 else cnpj_raw
            cpf = ""

        opcoes_origem = ["Indicação", "Instagram", "Facebook", "Google", "WhatsApp", "Outro"]
        como_conseguiu_val = cliente_edicao.get("como_conseguiu", "")
        idx_origem = opcoes_origem.index(como_conseguiu_val) if como_conseguiu_val in opcoes_origem else 0
        como_conseguiu = st.selectbox("Como conseguiu esse cliente?", opcoes_origem, index=idx_origem)

        st.markdown("---")
        st.subheader("📍 Endereço")

        col_cep1, col_cep2 = st.columns([3, 1])
        with col_cep1:
            cep_raw = st.text_input("CEP", value=str(cliente_edicao.get("cep", "")), max_chars=9)
            cep_limpo = re.sub(r"\D", "", cep_raw)[:8]
            cep = f"{cep_limpo[:5]}-{cep_limpo[5:]}" if len(cep_limpo) == 8 else cep_raw
        with col_cep2:
            buscar_cep = st.form_submit_button("Buscar CEP")

        logradouro = st.text_input("Logradouro", value=st.session_state.get("logradouro", ""))
        numero = st.text_input("Número", value=str(cliente_edicao.get("numero", "")))
        complemento = st.text_input("Complemento", value=str(cliente_edicao.get("complemento", "")))
        bairro = st.text_input("Bairro", value=st.session_state.get("bairro", ""))
        cidade = st.text_input("Cidade", value=st.session_state.get("cidade", ""))

        observacao = st.text_area("Observação (opcional)", value=str(cliente_edicao.get("observacao", "")))

        salvar = st.form_submit_button("💾 Salvar cliente")

    # --------------------------------------
    # Buscar CEP (ViaCEP)
    # --------------------------------------
    if buscar_cep:
        cep_query = re.sub(r"\D", "", cep).strip()
        if len(cep_query) == 8:
            with st.spinner("🔎 Buscando CEP..."):
                try:
                    r = requests.get(f"https://viacep.com.br/ws/{cep_query}/json/", timeout=10)
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

    # --------------------------------------
    # Salvar (create/update) sem duplicar
    # --------------------------------------
    if salvar:
        if not nome.strip():
            st.error("⚠️ O nome é obrigatório.")
        else:
            registro = {
                "nome": nome.strip(),
                "telefone": telefone.strip(),
                "email": email.strip(),
                "tipo_cliente": tipo_cliente,
                "rg": rg.strip(),
                "cpf": cpf.strip(),
                "cnpj": cnpj.strip(),
                "como_conseguiu": como_conseguiu,
                "logradouro": st.session_state.get("logradouro", ""),
                "numero": numero.strip(),
                "complemento": complemento.strip(),
                "bairro": st.session_state.get("bairro", ""),
                "cidade": st.session_state.get("cidade", ""),
                "cep": cep.strip(),
                "observacao": observacao.strip(),
            }

            id_cli = st.session_state.get("editando_cliente_id")
            try:
                if id_cli:  # UPDATE por id_cliente
                    atualizar_um("clientes", {"id_cliente": id_cli}, registro)
                    st.success("✏️ Cliente atualizado com sucesso!")
                else:       # INSERT (UUID gerado no banco)
                    inserir_um("clientes", registro)
                    st.success("✅ Cliente cadastrado com sucesso!")
            except Exception as e:
                st.error(f"❌ Erro ao salvar: {e}")

            # limpa estado e cache de endereço
            st.session_state.editando_cliente = None
            st.session_state.editando_cliente_id = None
            for campo in ["logradouro", "bairro", "cidade"]:
                st.session_state.pop(campo, None)
            st.rerun()

    # --------------------------------------
    # Listagem (com Editar/Excluir)
    # --------------------------------------
    st.subheader("📋 Clientes cadastrados")
    if df.empty:
        st.info("Nenhum cliente cadastrado ainda.")
        return

    for i, row in df.iterrows():
        titulo = f"{row.get('nome','(sem nome)')}"
        with st.expander(titulo):
            st.write(f"**Telefone:** {row.get('telefone','')}")
            st.write(f"**Email:** {row.get('email','')}")
            st.write(f"**Tipo:** {row.get('tipo_cliente','')}")

            if row.get("rg"):
                st.write(f"**RG:** {row.get('rg','')}")
            if row.get("tipo_cliente") == "Pessoa Física" and row.get("cpf"):
                st.write(f"**CPF:** {row.get('cpf','')}")
            if row.get("tipo_cliente") == "Pessoa Jurídica" and row.get("cnpj"):
                st.write(f"**CNPJ:** {row.get('cnpj','')}")

            st.write(f"**Como conseguiu:** {row.get('como_conseguiu','')}")
            endereco_fmt = f"{row.get('logradouro','')}, {row.get('numero','')}"
            endereco_fmt += f" - {row.get('bairro','')}, {row.get('cidade','')}"
            if row.get("cep"):
                endereco_fmt += f" - CEP {row.get('cep','')}"
            st.write(f"**Endereço:** {endereco_fmt}")
            if row.get("complemento"):
                st.write(f"**Complemento:** {row.get('complemento','')}")
            if row.get("observacao"):
                st.write(f"**Observação:** {row.get('observacao','')}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Editar", key=f"edit_cliente_{i}"):
                    st.session_state.editando_cliente = i
                    st.session_state.editando_cliente_id = row.get("id_cliente") or None
                    # prepara campos do CEP no cache para mostrar no form
                    for campo in ["logradouro", "bairro", "cidade"]:
                        st.session_state[campo] = row.get(campo, "") or ""
                    st.rerun()

            with col2:
                if st.button("🗑️ Excluir", key=f"del_cliente_{i}"):
                    id_cli = row.get("id_cliente")
                    if not id_cli:
                        st.error("Cliente sem id_cliente — não é possível excluir.")
                    else:
                        try:
                            deletar_por_filtro("clientes", {"id_cliente": id_cli})
                            st.warning(f"🗑️ Cliente '{row.get('nome','')}' excluído.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao excluir: {e}")

# =========================================
# MÓDULO PAGINA_RESERVAS SUPABASE
# =========================================

import streamlit as st
import pandas as pd
import unicodedata
import re
import time
from datetime import datetime
from banco import carregar_dados, salvar_dados, calcular_distancia_km


# =========================================
# MÓDULO: pagina_reservas (Supabase + snake_case)
# =========================================

import re
import time
import unicodedata
from datetime import datetime, date, time as dtime

import pandas as pd
import streamlit as st

# ✅ ADICIONADO: inserir/update/delete por filtro (para não duplicar)
from banco import (
    carregar_dados,
    salvar_dados,
    calcular_distancia_km,
    inserir_um,
    atualizar_por_filtro,
    deletar_por_filtro,
)


def _to_date_safe(x):
    """Converte entrada em data (Timestamp normalizado) ou NaT."""
    try:
        if pd.isna(x) or str(x).strip() == "":
            return pd.NaT
        if isinstance(x, (pd.Timestamp, datetime, date)):
            return pd.to_datetime(x).normalize()
        s = str(x).strip().split(" ")[0]
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
            try:
                return pd.to_datetime(datetime.strptime(s, fmt)).normalize()
            except ValueError:
                continue
        return pd.to_datetime(s, dayfirst=True, errors="coerce").normalize()
    except Exception:
        return pd.NaT


def _norm(txt: str) -> str:
    """Normaliza nome para comparar disponibilidade (sem acento/pontuação)."""
    if not isinstance(txt, str):
        return ""
    txt = txt.lower().strip()
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("utf-8")
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return txt.strip()


def pagina_reservas():
    st.header("📅 Gerenciar Reservas")

    # ========================================
    # CARREGAMENTO DOS DADOS
    # ========================================
    col_brinquedos = ["nome", "valor", "status", "categoria"]
    col_clientes = [
        "nome", "telefone", "email", "tipo_cliente", "cpf", "cnpj",
        "como_conseguiu", "logradouro", "numero", "complemento",
        "bairro", "cidade", "cep", "observacao"
    ]
    col_reservas = ["id",
        "cliente", "brinquedos", "data", "horario_entrega", "horario_retirada",
        "inicio_festa", "fim_festa",
        "valor_total", "valor_extra", "frete", "desconto",
        "sinal", "falta", "observacao", "status", "pagamentos"
    ]

    brinquedos = carregar_dados("brinquedos", col_brinquedos)
    clientes = carregar_dados("clientes", col_clientes)
    reservas = carregar_dados("reservas", col_reservas)

    # Normaliza nomes de colunas (caso venham diferentes)
    brinquedos.columns = [c.lower().strip() for c in brinquedos.columns]
    clientes.columns = [c.lower().strip() for c in clientes.columns]
    reservas.columns = [c.lower().strip() for c in reservas.columns]

    # Garante colunas faltantes
    for c in col_brinquedos:
        if c not in brinquedos.columns:
            brinquedos[c] = "" if c not in ["valor"] else 0.0
    for c in col_clientes:
        if c not in clientes.columns:
            clientes[c] = ""
    for c in col_reservas:
        if c not in reservas.columns:
            reservas[c] = "" if c in ["cliente","brinquedos","horario_entrega","horario_retirada","inicio_festa","fim_festa","observacao","status","pagamentos","data"] else 0.0

    # Conversões
    reservas["data"] = reservas["data"].apply(_to_date_safe)
    hoje = pd.Timestamp.now().normalize()

    num_cols = ["valor_total", "valor_extra", "frete", "desconto", "sinal", "falta"]
    for c in num_cols:
        reservas[c] = pd.to_numeric(reservas[c], errors="coerce").fillna(0.0)
    brinquedos["valor"] = pd.to_numeric(brinquedos["valor"], errors="coerce").fillna(0.0)

    # ✅ Garante id numérico quando vier como texto/float
    if "id" in reservas.columns:
        reservas["id"] = pd.to_numeric(reservas["id"], errors="coerce")

    # ========================================
    # CLASSIFICAÇÃO DE RESERVAS
    # ========================================
    reservas_hoje = reservas[reservas["data"] == hoje].copy()
    reservas_futuras = reservas[reservas["data"] > hoje].copy()
    reservas_passadas = reservas[reservas["data"] < hoje].copy()

    # ========================================
    # INDICADORES
    # ========================================
    total_reservas = len(reservas)
    total_hoje = len(reservas_hoje)
    total_futuras = len(reservas_futuras)
    total_concluidas = len(reservas[reservas["status"] == "Concluído"])
    total_faturado = float(reservas["sinal"].sum())

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
    # ABAS DE LISTAGEM
    # ========================================
    aba_hoje, aba_futuras, aba_passadas = st.tabs(["📅 Hoje", "🚀 Futuras", "📖 Histórico"])

    def _cartao_reserva(df, tipo):
        if df.empty:
            st.info(f"Nenhuma reserva {tipo.lower()} encontrada.")
            return

        for i, row in df.sort_values("data").iterrows():
            dias_restantes = (row["data"] - hoje).days if pd.notna(row["data"]) else 0
            if row["status"] == "Concluído":
                cor_card = "#D6EAF8"
            elif dias_restantes < 0:
                cor_card = "#FADBD8"
            elif dias_restantes <= 3:
                cor_card = "#FCF3CF"
            else:
                cor_card = "#D5F5E3"

            if pd.notna(row["data"]):
                data_fmt = pd.to_datetime(row["data"]).strftime("%d/%m/%Y")
            else:
                data_fmt = "-"

            label_tempo = (
                "🟦 Concluída" if row["status"] == "Concluído"
                else "🔴 Hoje" if dias_restantes == 0
                else "⚠️ Amanhã" if dias_restantes == 1
                else f"🟡 Faltam {dias_restantes} dias" if dias_restantes <= 3
                else f"🟩 Em {dias_restantes} dias"
            )

            with st.expander(f"🎈 {row.get('cliente','')} - {data_fmt} ({label_tempo})"):
                st.markdown(f"<div style='background-color:{cor_card};padding:10px;border-radius:8px;'>", unsafe_allow_html=True)

                st.write(f"**Brinquedos:** {row.get('brinquedos','')}")
                st.write(f"**Horário Entrega:** {row.get('horario_entrega','')}")
                st.write(f"**Horário Retirada:** {row.get('horario_retirada','')}")
                st.write(f"**Início da Festa:** {row.get('inicio_festa','')}")
                st.write(f"**Fim da Festa:** {row.get('fim_festa','')}")
                st.write(f"**Valor Total:** R$ {float(row.get('valor_total',0)):,.2f}")
                st.write(f"**Pago (Sinal):** R$ {float(row.get('sinal',0)):,.2f}")
                st.write(f"**Falta Receber:** R$ {float(row.get('falta',0)):,.2f}")
                st.write(f"**Frete:** R$ {float(row.get('frete',0)):,.2f}")
                st.write(f"**Status:** {row.get('status','') or 'Pendente'}")

                # Observação
                nova_obs = st.text_area("📝 Atualizar observação", value=str(row.get("observacao","")), key=f"obs_{tipo}_{i}")
                if st.button("💾 Salvar observação", key=f"btn_obs_{tipo}_{i}"):
                    try:
                        rid = row.get("id")
                        if pd.isna(rid):
                            st.error("❌ Esta reserva não tem ID. Não dá para atualizar sem duplicar.")
                        else:
                            atualizar_por_filtro("reservas", {"observacao": nova_obs}, {"id": int(rid)})
                            st.success("📝 Observação salva com sucesso!")
                            st.balloons()
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar observação: {e}")

                # Pagamento parcial
                valor_parcial = st.number_input("Registrar pagamento (R$)", min_value=0.0, step=10.0, key=f"pag_{tipo}_{i}")
                if st.button("💰 Confirmar pagamento", key=f"btn_pag_{tipo}_{i}"):
                    if valor_parcial > 0:
                        try:
                            rid = row.get("id")
                            if pd.isna(rid):
                                st.error("❌ Esta reserva não tem ID. Não dá para atualizar sem duplicar.")
                            else:
                                sinal_novo = float(row.get("sinal", 0.0)) + float(valor_parcial)
                                valor_total_row = float(row.get("valor_total", 0.0))
                                falta_nova = max(valor_total_row - sinal_novo, 0.0)
                                status_novo = "Concluído" if falta_nova == 0 else "Pendente"

                                atualizar_por_filtro(
                                    "reservas",
                                    {"sinal": sinal_novo, "falta": falta_nova, "status": status_novo},
                                    {"id": int(rid)}
                                )

                                st.success(f"💰 Pagamento de R$ {valor_parcial:,.2f} registrado!")
                                st.balloons()
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao registrar pagamento: {e}")

                # Editar / Excluir
                if st.button("✏️ Editar reserva", key=f"edit_{tipo}_{i}"):
                    st.session_state.editando = int(i)
                    st.rerun()

                st.markdown("---")
                st.markdown("**🗑️ Excluir reserva**")

                confirmar = st.checkbox(
                    f"Confirmar exclusão da reserva de {row.get('cliente','')}",
                    key=f"chk_del_{tipo}_{i}",
                )

                if (
                    st.button("🗑️ Excluir DEFINITIVAMENTE", key=f"btn_del_{tipo}_{i}")
                    and confirmar
                ):
                    try:
                        # Excluir usando o ID, se existir
                        if "id" in reservas.columns and pd.notna(row.get("id")):
                            deletar_por_filtro("reservas", {"id": int(row["id"])})
                        else:
                            # Fallback: excluir pelo trio cliente + brinquedos + data
                            deletar_por_filtro(
                                "reservas",
                                {
                                    "cliente": row.get("cliente", ""),
                                    "brinquedos": row.get("brinquedos", ""),
                                    "data": str(row.get("data", "")),
                                },
                            )

                        st.success("🗑️ Reserva excluída com sucesso.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Erro ao excluir reserva: {e}")

                st.markdown("</div>", unsafe_allow_html=True)

    with aba_hoje:
        _cartao_reserva(reservas_hoje, "HOJE")
    with aba_futuras:
        _cartao_reserva(reservas_futuras, "FUTURA")
    with aba_passadas:
        _cartao_reserva(reservas_passadas, "PASSADA")

    # ========================================
    # FORMULÁRIO DE CADASTRO / EDIÇÃO
    # ========================================
    st.divider()
    st.subheader("➕ Adicionar / Editar Reserva")

    # Filtro por categoria de brinquedos
    if "categoria" not in brinquedos.columns:
        brinquedos["categoria"] = "Tradicional"

    st.markdown("#### 🎠 Filtrar brinquedos por categoria:")
    filtro_categoria = st.radio("", ["⚪ Todos", "🟣 Tradicional", "🩵 Montessori"], horizontal=True)

    if "Tradicional" in filtro_categoria:
        brinquedos_filtrados = brinquedos[brinquedos["categoria"].str.lower() == "tradicional"].copy()
    elif "Montessori" in filtro_categoria:
        brinquedos_filtrados = brinquedos[brinquedos["categoria"].str.lower() == "montessori"].copy()
    else:
        brinquedos_filtrados = brinquedos.copy()

    # Obtém reserva em edição (se houver)
    if "editando" in st.session_state and st.session_state.editando is not None and st.session_state.editando in reservas.index:
        idx_edit = st.session_state.editando
        reserva = reservas.loc[idx_edit].to_dict()
        st.info(f"✏️ Editando reserva de {reserva.get('cliente','')}")
    else:
        idx_edit = None
        reserva = {
            "cliente": "", "brinquedos": "", "data": pd.Timestamp.today(),
            "horario_entrega": "08:00", "horario_retirada": "18:00",
            "inicio_festa": "13:00", "fim_festa": "17:00",
            "valor_total": 0.0, "valor_extra": 0.0, "frete": 0.0,
            "desconto": 0.0, "sinal": 0.0, "falta": 0.0,
            "observacao": "", "status": "Pendente", "pagamentos": ""
        }

    # Cliente
    lista_clientes = clientes["nome"].dropna().tolist() if not clientes.empty else []
    try:
        idx_cliente = lista_clientes.index(reserva.get("cliente","")) if reserva.get("cliente","") in lista_clientes else 0
    except Exception:
        idx_cliente = 0
    cliente = st.selectbox("Cliente", lista_clientes, index=idx_cliente if lista_clientes else None)

    # Data para disponibilidade e para a reserva
    data_para_disponibilidade = st.date_input(
        "📅 Data para verificar disponibilidade",
        value=pd.to_datetime(reserva.get("data", pd.Timestamp.today()))
    )
    data_reserva = pd.to_datetime(data_para_disponibilidade)

    # Brinquedos indisponíveis na data
    reservados_no_dia = reservas.loc[reservas["data"] == data_reserva, "brinquedos"].dropna().tolist()
    ocupados = set()
    for r in reservados_no_dia:
        ocupados.update([_norm(b) for b in str(r).split(",") if b.strip()])
    # Se estiver editando, permitir manter os que já estão na própria reserva
    ja_selecionados = set()
    if reserva.get("brinquedos"):
        ja_selecionados = set([_norm(b) for b in str(reserva["brinquedos"]).split(",") if b.strip()])
    ocupados_externos = ocupados - ja_selecionados

    brinquedos_filtrados["nome_normalizado"] = brinquedos_filtrados["nome"].apply(_norm)
    disponiveis_df = brinquedos_filtrados[~brinquedos_filtrados["nome_normalizado"].isin(ocupados_externos)].copy()

    if ocupados_externos:
        st.warning("⚠️ Indisponíveis nesta data: " + ", ".join(sorted(list(ocupados_externos))))

    st.caption(f"🎪 {len(disponiveis_df)} brinquedo(s) disponível(is) nessa categoria e data.")

    itens_default = []
    if reserva.get("brinquedos"):
        itens_default = [b.strip() for b in str(reserva["brinquedos"]).split(",") if b.strip()]

    itens = st.multiselect(
        "🎠 Brinquedos disponíveis",
        sorted(disponiveis_df["nome"].tolist(), key=lambda x: x.lower()),
        default=itens_default
    )

    # ===== FRETE AUTOMÁTICO =====
    # Ajuste o CEP de origem conforme sua operação
    cep_origem = "09060-390"
    cep_destino = clientes.loc[clientes["nome"] == cliente, "cep"].values[0] if cliente in clientes["nome"].values else ""

    frete_auto = 0.0
    if cep_destino:
        dist_km = calcular_distancia_km(cep_origem, str(cep_destino))
        if dist_km:
            cats = [str(c).strip().lower() for c in brinquedos.loc[brinquedos["nome"].isin(itens), "categoria"].dropna().unique()]
            if not cats:
                multiplicador = 3
            elif "montessori" in cats and "tradicional" in cats:
                multiplicador = 5
            elif "montessori" in cats:
                multiplicador = 5
            else:
                multiplicador = 3
            frete_auto = round(float(dist_km) * multiplicador, 2)
            st.info(f"🚚 Distância aproximada: {dist_km} km")
            st.markdown(f"**📍 CEP origem:** {cep_origem} → **destino:** {cep_destino}")
            st.success(f"💰 Frete automático: R$ {frete_auto:,.2f}")
        else:
            st.warning("⚠️ Não foi possível calcular a distância para o CEP informado.")
    else:
        st.warning("⚠️ Este cliente não possui CEP cadastrado — cálculo automático indisponível.")

    # ====== FORM DA RESERVA ======
    with st.form("form_reserva"):
        st.markdown("### 📅 Data da reserva")
        st.info(f"**Data selecionada:** {data_reserva.strftime('%d/%m/%Y')}")

        def _time_from_str(s: str, fallback: str) -> dtime:
            try:
                s = (s or "").strip() or fallback
                return datetime.strptime(s, "%H:%M").time()
            except Exception:
                return datetime.strptime(fallback, "%H:%M").time()

        col_h1, col_h2 = st.columns(2)
        with col_h1:
            horario_entrega = st.time_input("Horário Entrega", value=_time_from_str(reserva.get("horario_entrega"), "08:00"))
            inicio_festa = st.time_input("🕒 Início da Festa", value=_time_from_str(reserva.get("inicio_festa"), "13:00"))
        with col_h2:
            horario_retirada = st.time_input("Horário Retirada", value=_time_from_str(reserva.get("horario_retirada"), "18:00"))
            fim_festa = st.time_input("🕓 Fim da Festa", value=_time_from_str(reserva.get("fim_festa"), "17:00"))

        observacao = st.text_area("Observação (opcional)", value=str(reserva.get("observacao","")))

        # Valores financeiros (mantidos todos editáveis)
        valor_extra = st.number_input("Valor Extra (R$)", min_value=0.0, step=10.0, value=float(reserva.get("valor_extra", 0.0)))
        frete = st.number_input("Frete (R$)", min_value=0.0, step=10.0, value=float(frete_auto or reserva.get("frete", 0.0)))
        desconto = st.number_input("Desconto (R$)", min_value=0.0, step=10.0, value=float(reserva.get("desconto", 0.0)))
        sinal = float(reserva.get("sinal", 0.0))  # já usado no cálculo de falta/status

        total_brinquedos = float(brinquedos[brinquedos["nome"].isin(itens)]["valor"].sum()) if itens else 0.0
        valor_total = float(total_brinquedos + valor_extra + frete - desconto)
        st.markdown(f"**💰 Valor Total calculado:** R$ {valor_total:,.2f}")

        bt_salvar = st.form_submit_button("💾 Salvar Reserva")

        if bt_salvar:
            if not cliente or not itens or pd.isna(data_reserva):
                st.error("⚠️ Selecione um cliente, uma data e pelo menos um brinquedo.")
            else:
                nova = {
                    "cliente": cliente,
                    "brinquedos": ", ".join(itens),
                    "data": data_reserva.strftime("%Y-%m-%d"),
                    "horario_entrega": horario_entrega.strftime("%H:%M"),
                    "horario_retirada": horario_retirada.strftime("%H:%M"),
                    "inicio_festa": inicio_festa.strftime("%H:%M"),
                    "fim_festa": fim_festa.strftime("%H:%M"),
                    "valor_total": valor_total,
                    "valor_extra": float(valor_extra),
                    "frete": float(frete),
                    "desconto": float(desconto),
                    "sinal": float(sinal),
                    "falta": max(valor_total - float(sinal), 0.0),
                    "observacao": observacao,
                    "status": "Concluído" if max(valor_total - float(sinal), 0.0) == 0 else "Pendente",
                    "pagamentos": str(reserva.get("pagamentos",""))
                }

                # ✅ AQUI É O QUE RESOLVE A DUPLICIDADE:
                # - se está editando: UPDATE por id
                # - se é nova: INSERT (sem mandar id)
                try:
                    if idx_edit is not None and idx_edit in reservas.index and pd.notna(reserva.get("id")):
                        rid = int(reserva["id"])
                        atualizar_por_filtro("reservas", nova, {"id": rid})
                        st.session_state.editando = None
                        st.success("✅ Reserva atualizada com sucesso!")
                    else:
                        inserir_um("reservas", nova)
                        st.success("✅ Reserva criada com sucesso!")
                except Exception as e:
                    st.error(f"❌ Erro ao salvar reserva: {e}")
                    return

                time.sleep(1)
                st.rerun()




# =========================
# 💸 Página de Estoque (mínima e estável)
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import unicodedata
import re

from banco import carregar_dados

def pagina_estoque():
    st.header("📦 Controle de Estoque e Disponibilidade")

    # =====================================
    # CARREGAR DADOS
    # =====================================
    brinquedos = carregar_dados("brinquedos", ["nome", "valor", "status", "categoria"])
    reservas = carregar_dados("reservas", ["id","cliente", "brinquedos", "data", "horario_entrega",
                                           "horario_retirada", "inicio_festa", "fim_festa", "status"])

    # Normaliza nomes das colunas para minúsculas
    brinquedos.columns = [c.lower().strip() for c in brinquedos.columns]
    reservas.columns = [c.lower().strip() for c in reservas.columns]

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

    if "data" in reservas.columns:
        reservas["data"] = reservas["data"].apply(parse_data_segura)

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
        reservas_dia = reservas.loc[reservas["data"] == pd.to_datetime(data_escolhida)]

        todos = []
        for _, br in brinquedos.iterrows():
            nome_brinquedo = br.get("nome", "")
            cat = br.get("categoria", "Tradicional")

            reservado = False
            cliente_reserva = ""
            inicio = ""
            fim = ""

            for _, res in reservas_dia.iterrows():
                lista = str(res.get("brinquedos", ""))
                if normalizar(nome_brinquedo) in normalizar(lista):
                    reservado = True
                    cliente_reserva = res.get("cliente", "")
                    inicio = res.get("inicio_festa", "")
                    fim = res.get("fim_festa", "")
                    break

            status = f"🔴 Indisponível (🎉 {cliente_reserva} - {inicio} às {fim})" if reservado else "🟢 Disponível"
            todos.append({
                "brinquedo": nome_brinquedo,
                "categoria": cat,
                "status": status,
                "disponivel": not reservado
            })

        df_disp = pd.DataFrame(todos)

        aba_todos, aba_trad, aba_mont = st.tabs(["🌈 Todos", "🎪 Tradicional", "🧸 Montessori"])

        def mostrar_resumo(df):
            total = len(df)
            disponiveis = len(df[df["disponivel"]])
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
                df = df[df["brinquedo"].str.lower().str.contains(busca, na=False)]
            for _, row in df.iterrows():
                cor_fundo = "#D4EDDA" if row["disponivel"] else "#F8D7DA"
                st.markdown(
                    f"<div style='background-color:{cor_fundo};padding:10px;border-radius:8px;margin-bottom:6px;'>"
                    f"<b>{row['brinquedo']}</b><br>{row['status']}</div>",
                    unsafe_allow_html=True
                )

        with aba_todos:
            exibir_lista(df_disp, "Todos")
        with aba_trad:
            exibir_lista(df_disp[df_disp["categoria"].str.lower() == "tradicional"], "Tradicional")
        with aba_mont:
            exibir_lista(df_disp[df_disp["categoria"].str.lower() == "montessori"], "Montessori")

    # ==============================================================
    # 2️⃣ ABA: CONSULTA RÁPIDA POR BRINQUEDO
    # ==============================================================
    with aba_consulta:
        st.subheader("🔎 Consulta rápida de disponibilidade por brinquedo")
        nome_busca = st.text_input("Digite o nome do brinquedo:", "").strip()
        if nome_busca:
            brinquedo = brinquedos[brinquedos["nome"].str.lower().str.contains(nome_busca.lower(), na=False)]
            if brinquedo.empty:
                st.warning("Nenhum brinquedo encontrado com esse nome.")
            else:
                nome_b = brinquedo.iloc[0]["nome"]
                hoje = datetime.today().date()
                dias = [hoje + timedelta(days=i) for i in range(15)]
                registros = []
                for d in dias:
                    data_fmt = d.strftime("%d/%m/%Y")
                    reservas_dia = reservas[reservas["data"] == pd.to_datetime(d)]
                    reservado = False
                    cliente = ""
                    for _, r in reservas_dia.iterrows():
                        if normalizar(nome_b) in normalizar(str(r.get("brinquedos", ""))):
                            reservado = True
                            cliente = r.get("cliente", "")
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
    # 3️⃣ ABA: AGENDA SEMANAL (7 DIAS)
    # ==============================================================
    with aba_agenda:
        st.subheader("🗓️ Agenda dos próximos 7 dias")
        hoje = datetime.today().date()
        dias = [hoje + timedelta(days=i) for i in range(7)]
        cabecalho = ["Brinquedo", "Categoria"] + [d.strftime("%d/%m") for d in dias]
        tabela = []

        for _, br in brinquedos.iterrows():
            linha = [br["nome"], br.get("categoria", "Tradicional")]
            for d in dias:
                reservas_dia = reservas[reservas["data"] == pd.to_datetime(d)]
                ocupado = any(normalizar(br["nome"]) in normalizar(str(r.get("brinquedos", ""))) for _, r in reservas_dia.iterrows())
                linha.append("🔴" if ocupado else "🟢")
            tabela.append(linha)

        st.dataframe(pd.DataFrame(tabela, columns=cabecalho))

    # ==============================================================
    # 4️⃣ ABA: RELATÓRIO DE UTILIZAÇÃO
    # ==============================================================
    with aba_relatorio:
        st.subheader("📊 Utilização dos Brinquedos (mês atual)")
        mes_atual = datetime.today().month
        reservas_mes = reservas[reservas["data"].dt.month == mes_atual]
        uso = []
        for _, b in brinquedos.iterrows():
            count = reservas_mes["brinquedos"].fillna("").apply(lambda x: normalizar(b["nome"]) in normalizar(x)).sum()
            uso.append({"Brinquedo": b["nome"], "Categoria": b.get("categoria", "Tradicional"), "Dias Locado": count})
        df_uso = pd.DataFrame(uso)
        if not df_uso.empty:
            df_uso["% Utilização"] = (df_uso["Dias Locado"] / df_uso["Dias Locado"].max() * 100).fillna(0).round(1)
        st.dataframe(df_uso)



# =========================
# 💸 Página de Custos (mínima e estável)
# =========================


# =========================================
# MÓDULO: pagina_custos (versão final completa com Supabase)
# =========================================

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from banco import carregar_dados, salvar_dados
import uuid


# ------------------------------------------------------
# FUNÇÕES AUXILIARES
# ------------------------------------------------------
def _ensure_cols(df: pd.DataFrame, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df.reindex(columns=cols)

def _to_date_safe(x):
    try:
        if pd.isna(x) or str(x).strip() == "":
            return pd.NaT
        return pd.to_datetime(str(x).split(" ")[0], errors="coerce")
    except Exception:
        return pd.NaT

# ------------------------------------------------------
# FUNÇÃO PRINCIPAL
# ------------------------------------------------------


import uuid
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st


import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, timedelta
import requests
from banco import carregar_dados, salvar_dados, inserir_um, atualizar_por_filtro, deletar_por_filtro


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def pagina_custos():
    st.header("💸 Controle de Custos")

    aba = st.tabs(["📘 Lançar Custos", "🏦 Empréstimos"])

    # ============================================================
    # 🧾 ABA 1 - LANÇAR CUSTOS
    # ============================================================
    with aba[0]:
        cols_custos = ["descricao", "categoria", "valor", "data", "forma_de_pagamento", "observacao"]

        try:
            df = carregar_dados("custos", cols_custos)
            if df is None or df.empty:
                df = pd.DataFrame(columns=cols_custos)
            else:
                df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
                if "valor" not in df.columns:
                    df["valor"] = 0.0
                df = _ensure_cols(df, cols_custos)
        except Exception as e:
            st.error(f"❌ Erro ao carregar dados de custos: {e}")
            df = pd.DataFrame(columns=cols_custos)

        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
        df["data"] = df["data"].apply(_to_date_safe)

        st.subheader("📆 Filtro de Período")
        hoje = datetime.now().date()
        opcoes = ["Mês Atual", "Últimos 7 dias", "Últimos 30 dias", "Período Personalizado"]
        filtro = st.radio("Selecione o intervalo:", opcoes, horizontal=True)

        if filtro == "Mês Atual":
            data_inicial = hoje.replace(day=1)
            data_final = hoje
        elif filtro == "Últimos 7 dias":
            data_inicial = hoje - timedelta(days=7)
            data_final = hoje
        elif filtro == "Últimos 30 dias":
            data_inicial = hoje - timedelta(days=30)
            data_final = hoje
        else:
            c1, c2 = st.columns(2)
            with c1:
                data_inicial = st.date_input("Data inicial", value=hoje.replace(day=1))
            with c2:
                data_final = st.date_input("Data final", value=hoje)

        if not df.empty:
            filtrado = df[
                (df["data"] >= pd.to_datetime(data_inicial)) &
                (df["data"] <= pd.to_datetime(data_final))
            ].copy()
        else:
            filtrado = df.copy()

        total_periodo = filtrado["valor"].sum() if not filtrado.empty else 0.0
        total_geral = df["valor"].sum() if not df.empty else 0.0
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
                ["Combustível", "Compra de Brinquedo", "Manutenção", "Anuncio", "Frete",
                 "Monitor", "Auxiliar de Montagem", "Comida", "Limpeza Casa", "Outros"]
            )
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0)
            data_val = st.date_input("Data do custo", value=datetime.today())
            forma = st.selectbox(
                "Forma de Pagamento",
                ["Pix", "Dinheiro", "Cartão de Crédito", "Cartão de Débito", "Transferência", "Outro"]
            )
            observacao = st.text_area("Observação (opcional)")

            salvar = st.form_submit_button("💾 Salvar custo")

            if salvar:
                if descricao and valor > 0:
                    novo = {
                        "descricao": descricao,
                        "categoria": categoria,
                        "valor": float(valor),
                        "data": str(data_val),
                        "forma_de_pagamento": forma,
                        "observacao": observacao
                    }
                    df.loc[len(df)] = novo
                    salvar_dados(df, "custos")
                    st.success(f"✅ Custo '{descricao}' registrado com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Informe uma descrição e um valor maior que zero.")

        st.divider()

        if not filtrado.empty:
            st.subheader("📊 Resumo por Categoria")
            resumo = filtrado.groupby("categoria", dropna=False)["valor"].sum().reset_index().sort_values("valor", ascending=False)
            for _, row in resumo.iterrows():
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:space-between;
                                background:#f9f9f9;padding:10px 15px;
                                border-left:6px solid #7A5FFF;border-radius:8px;
                                margin-bottom:8px;">
                        <strong>{row['categoria'] or '-'}</strong>
                        <span>R$ {row['valor']:.2f}</span>
                    </div>
                    """, unsafe_allow_html=True
                )
        else:
            st.info("Nenhum gasto encontrado no período selecionado.")

        st.divider()

        st.subheader("📋 Custos Registrados")
        if not filtrado.empty:
            df_sorted = filtrado.sort_values(by="data", ascending=False)
            for i, row in df_sorted.iterrows():
                data_fmt = pd.to_datetime(row["data"]).date().strftime("%d/%m/%Y") if pd.notna(row["data"]) else "-"
                with st.expander(f"💸 {row['descricao']} - {row['categoria']} ({data_fmt})"):
                    st.write(f"**Valor:** R$ {float(row['valor']):.2f}")
                    st.write(f"**Forma de Pagamento:** {row.get('forma_de_pagamento','')}")
                    st.write(f"**Observação:** {row.get('observacao') or '-'}")

                    if st.button("🗑️ Excluir", key=f"del_custo_{i}"):
                        idx_abs = row.name
                        if idx_abs in df.index:
                            df = df.drop(idx_abs).reset_index(drop=True)
                            salvar_dados(df, "custos")
                            st.warning(f"🗑️ Custo '{row['descricao']}' excluído!")
                            st.rerun()
        else:
            st.info("Nenhum custo cadastrado ainda.")

    # ============================================================
    # 🏦 ABA 2 - EMPRÉSTIMOS
    # ============================================================
    with aba[1]:
        st.subheader("🏦 Controle de Empréstimos")

        cols_emp = [
            "id_emprestimo", "descricao", "observacao",
            "valor_recebido", "valor_a_pagar", "juros",
            "parcelas", "valor_pendente", "data", "status",
            "criado_em", "atualizado_em"
        ]

        df_emp = carregar_dados("emprestimos", cols_emp).copy()
        df_pag = carregar_dados("pagamentos_emprestimos", ["id_pagamento", "id_emprestimo", "descricao", "valor_pago", "data_pagamento"]).copy()

        if not df_emp.empty:
            df_emp["valor_recebido"] = pd.to_numeric(df_emp["valor_recebido"], errors="coerce").fillna(0.0)
            df_emp["valor_a_pagar"] = pd.to_numeric(df_emp["valor_a_pagar"], errors="coerce").fillna(0.0)
            df_emp["valor_pendente"] = pd.to_numeric(df_emp["valor_pendente"], errors="coerce").fillna(0.0)
            df_emp["data"] = df_emp["data"].apply(_to_date_safe)

        if not df_pag.empty:
            df_pag["valor_pago"] = pd.to_numeric(df_pag["valor_pago"], errors="coerce").fillna(0.0)
            df_pag["data_pagamento"] = df_pag["data_pagamento"].apply(_to_date_safe)

        total_recebido = df_emp["valor_recebido"].sum() if not df_emp.empty else 0
        total_pagar = df_emp["valor_a_pagar"].sum() if not df_emp.empty else 0
        total_pendente = df_emp["valor_pendente"].sum() if not df_emp.empty else 0
        total_pago = total_pagar - total_pendente

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Recebido", f"R$ {total_recebido:,.2f}")
        c2.metric("💸 A Pagar", f"R$ {total_pagar:,.2f}")
        c3.metric("✅ Pago", f"R$ {total_pago:,.2f}")
        c4.metric("🟡 Pendente", f"R$ {total_pendente:,.2f}")

        st.divider()
        st.subheader("📥 Registrar novo empréstimo")

        with st.form("form_emp"):
            descricao = st.text_input("Descrição do Empréstimo")
            obs = st.text_area("Observação (motivo)")
            val_rec = st.number_input("Valor Recebido", min_value=0.0, step=100.0)
            val_pag = st.number_input("Valor a Pagar", min_value=0.0, step=100.0)
            parcelas = st.number_input("Parcelas", min_value=1, step=1)
            data_emp = st.date_input("Data", value=datetime.today())
            salvar_emp = st.form_submit_button("💾 Salvar Empréstimo")

            if salvar_emp and descricao and val_rec > 0:
                juros = round(((val_pag - val_rec) / val_rec) * 100, 2) if val_rec else 0.0
                novo_emp = {
                    "descricao": descricao,
                    "observacao": obs,
                    "valor_recebido": float(val_rec),
                    "valor_a_pagar": float(val_pag),
                    "juros": juros,
                    "parcelas": int(parcelas),
                    "valor_pendente": float(val_pag),
                    "data": str(data_emp),
                    "status": "🟡 Pendente"
                }
                try:
                    inserir_um("emprestimos", novo_emp)
                    st.success("✅ Empréstimo registrado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao salvar empréstimo: {e}")

        st.divider()

        if df_emp.empty:
            st.info("Nenhum empréstimo registrado ainda.")
            return

        for _, row in df_emp.sort_values("data", ascending=False).iterrows():
            with st.expander(f"🏦 {row['descricao']} — {row['status']} — Pendente: R$ {row['valor_pendente']:.2f}"):

                st.write(f"**Valor Recebido:** R$ {row['valor_recebido']:.2f}")
                st.write(f"**Valor a Pagar:** R$ {row['valor_a_pagar']:.2f}")
                st.write(f"**Juros:** {row['juros']:.2f}%")
                st.write(f"**Parcelas:** {int(row['parcelas'])}")
                st.write(f"**Data:** {row['data']}")
                st.write(f"**Observação:** {row['observacao'] or '-'}")

                # ✅ REGISTRAR PAGAMENTO
                with st.form(f"form_pag_{row['id_emprestimo']}"):
                    valor_pago = st.number_input("Valor pago", min_value=0.0, step=50.0, key=f"vp_{row['id_emprestimo']}")
                    data_pag = st.date_input("Data Pagamento", value=datetime.today(), key=f"dp_{row['id_emprestimo']}")
                    registrar = st.form_submit_button("💰 Registrar Pagamento")

                    if registrar and valor_pago > 0:
                        novo_pagamento = {
                            "id_emprestimo": row["id_emprestimo"],
                            "descricao": row["descricao"],
                            "valor_pago": float(valor_pago),
                            "data_pagamento": str(data_pag),
                        }
                        try:
                            inserir_um("pagamentos_emprestimos", novo_pagamento)
                            st.success(f"✅ Pagamento de R$ {valor_pago:.2f} registrado com sucesso!")

                            pagos = (
                                carregar_dados("pagamentos_emprestimos", ["id_emprestimo", "valor_pago"])
                                .query("id_emprestimo == @row.id_emprestimo")["valor_pago"]
                                .sum()
                            )
                            pendente = max(0, float(row["valor_a_pagar"]) - pagos)
                            status = "🟢 Quitado" if pendente <= 0 else "🟡 Pendente"

                            atualizar_por_filtro(
                                "emprestimos",
                                {"valor_pendente": pendente, "status": status, "atualizado_em": str(datetime.now())},
                                {"id_emprestimo": row["id_emprestimo"]},
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao registrar pagamento: {e}")

                # Histórico
                hist = df_pag[df_pag["id_emprestimo"] == row["id_emprestimo"]]
                if not hist.empty:
                    st.write("📜 **Histórico de Pagamentos:**")
                    for _, pg in hist.iterrows():
                        st.markdown(f"- {pg['data_pagamento']}: R$ {pg['valor_pago']:.2f}")

                # Excluir
                if st.button("🗑️ Excluir Empréstimo", key=f"del_emp_{row['id_emprestimo']}"):
                    deletar_por_filtro("emprestimos", {"id_emprestimo": row["id_emprestimo"]})
                    deletar_por_filtro("pagamentos_emprestimos", {"id_emprestimo": row["id_emprestimo"]})
                    st.warning(f"🗑️ Empréstimo '{row['descricao']}' excluído!")
                    st.rerun()






import streamlit as st
import pandas as pd
from datetime import datetime, date
import calendar
from banco import carregar_dados

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
    colunas = ["cliente", "brinquedos", "data", "valor_total", "status"]
    reservas = carregar_dados("reservas", colunas)

    if reservas is None or reservas.empty:
        st.info("Nenhuma reserva registrada ainda.")
        return

    reservas["data"] = pd.to_datetime(reservas["data"], errors="coerce")
    reservas = reservas.dropna(subset=["data"])

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
        (reservas["data"].dt.month == mes) & (reservas["data"].dt.year == ano)
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
    reservas_mes = reservas[(reservas["data"].dt.month == mes) & (reservas["data"].dt.year == ano)]

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
        reservas_dia = reservas_mes[reservas_mes["data"].dt.date == dia.date()]
        qtd = len(reservas_dia)
        nomes = ", ".join(reservas_dia["cliente"].astype(str)) if qtd > 0 else ""
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
        reservas_dia = reservas_mes[reservas_mes["data"].dt.date == sel]
        if reservas_dia.empty:
            st.info("Nenhuma reserva para este dia.")
        else:
            for _, r in reservas_dia.iterrows():
                st.markdown(
                    "<div style='background:#f9f9f9;border-radius:10px;padding:10px 15px;margin-bottom:8px;"
                    "box-shadow:0 2px 4px rgba(0,0,0,0.08)'>"
                    f"<b>{r.get('cliente','')}</b><br>"
                    f"🎠 {r.get('brinquedos','')}<br>"
                    f"💰 Valor total: R$ {float(r.get('valor_total',0)):.2f}<br>"
                    f"📌 Status: {r.get('status','')}"
                    "</div>",
                    unsafe_allow_html=True
                )

def pagina_checklist():
    import pandas as pd
    from datetime import datetime
    import pytz
    import streamlit as st
    from banco import carregar_dados, salvar_dados

    st.header("📋 Check-list de Brinquedos")

    # ========================================
    # CARREGAR DADOS DO SUPABASE
    # ========================================
    reservas = carregar_dados("reservas", ["id", "cliente", "brinquedos", "data", "status"])
    brinquedos_cadastrados = carregar_dados("brinquedos", ["nome"])
    pecas = carregar_dados("pecas_brinquedos", ["Brinquedo", "Item"])
    checklist = carregar_dados(
        "checklist",
        ["reserva_id", "cliente", "brinquedo", "tipo", "item", "ok",
         "data", "observacao", "conferido_por", "completo"]
    )

    if reservas is None or reservas.empty:
        st.info("Nenhuma reserva encontrada.")
        return

    # ========================================
    # GARANTIA DE COLUNAS
    # ========================================
    for df, cols in {
        "reservas": ["id", "cliente", "brinquedos", "data", "status"],
        "brinquedos": ["nome"],
        "pecas": ["Brinquedo", "Item"],
        "checklist": ["reserva_id", "cliente", "brinquedo", "tipo", "item", "ok",
                      "data", "observacao", "conferido_por", "completo"],
    }.items():
        try:
            df_check = eval(df)
            for col in cols:
                if col not in df_check.columns:
                    df_check[col] = ""
        except Exception:
            pass

    # ========================================
    # ABAS
    # ========================================
    aba1, aba2 = st.tabs(["✅ Realizar Check-list", "🧩 Cadastrar Peças"])

    # ========================================
    # ✅ ABA 1 - REALIZAR CHECK-LIST
    # ========================================
    with aba1:
        reservas["data"] = pd.to_datetime(reservas["data"], errors="coerce")
        reservas["label"] = reservas["id"].astype(str) + " - " + reservas["cliente"].astype(str) + " (" + reservas["data"].dt.strftime("%d/%m/%Y") + ")"

        sel_reserva = st.selectbox("Selecione a reserva:", reservas["label"])
        if not sel_reserva:
            return

        reserva_id = int(sel_reserva.split(" - ")[0])
        reserva = reservas.loc[reservas["id"] == reserva_id].iloc[0]
        cliente = reserva["cliente"]
        brinquedos_lista = [b.strip() for b in str(reserva["brinquedos"]).split(",") if b.strip()]

        # ======== CARD DE ANDAMENTO ========
        total_brinquedos = len(brinquedos_lista)
        brinquedos_completos = checklist[
            (checklist["reserva_id"] == reserva_id) & (checklist["completo"] == "✅")
        ]["brinquedo"].nunique()
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
                    <div style="height:18px;width:{progresso:.1f}%;background:{cor};
                                transition:width 0.8s ease;border-radius:8px;">
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

        # ======== STATUS DO CHECKLIST ========
        status_checklist = checklist[
            (checklist["reserva_id"] == reserva_id) &
            (checklist["brinquedo"] == brinquedo_sel) &
            (checklist["tipo"] == tipo)
        ]
        if not status_checklist.empty:
            st.success("✅ Este brinquedo já possui check-list registrado para este tipo.")
        else:
            st.warning("⚠️ Nenhum check-list registrado para este brinquedo ainda.")

        # ======== ITENS DO BRINQUEDO ========
        pecas_brinquedo = pecas[pecas["Brinquedo"].str.lower() == brinquedo_sel.lower()]
        if pecas_brinquedo.empty:
            st.warning("⚠️ Nenhuma peça cadastrada para este brinquedo.")
            return

        st.markdown(f"### Itens de verificação – {brinquedo_sel}")
        checks = {row["Item"]: st.checkbox(row["Item"], key=f"{tipo}_{i}") for i, row in pecas_brinquedo.iterrows()}
        observacao = st.text_area("Observações (opcional):")

        usuario_logado = st.session_state.get("usuario", "Usuário não identificado")

        if st.button("💾 Salvar check-list"):
            tz_sp = pytz.timezone("America/Sao_Paulo")
            data_hora = datetime.now(tz_sp).strftime("%Y-%m-%d %H:%M")
            completo = "✅" if all(checks.values()) else "❌"

            novos_registros = []
            for item, marcado in checks.items():
                novos_registros.append({
                    "reserva_id": reserva_id,
                    "cliente": cliente,
                    "brinquedo": brinquedo_sel,
                    "tipo": tipo,
                    "item": item,
                    "ok": "✅" if marcado else "❌",
                    "data": data_hora,
                    "observacao": observacao,
                    "conferido_por": usuario_logado,
                    "completo": completo
                })

            novos_df = pd.DataFrame(novos_registros)
            checklist = pd.concat([checklist, novos_df], ignore_index=True)
            salvar_dados(checklist, "checklist")
            st.success("✅ Check-list salvo com sucesso!")
            st.rerun()

        # ======== HISTÓRICO ========
        st.divider()
        st.subheader("📜 Histórico de check-lists")

        hist = checklist[checklist["reserva_id"] == reserva_id]
        if hist.empty:
            st.info("Nenhum check-list registrado para esta reserva ainda.")
        else:
            st.dataframe(hist.sort_values(["tipo", "brinquedo", "item"]),
                         use_container_width=True, hide_index=True)

    # ========================================
    # 🧩 ABA 2 - CADASTRAR PEÇAS
    # ========================================
    with aba2:
        st.subheader("🧩 Cadastro de Peças por Brinquedo")

        brinquedo_novo = st.selectbox("Brinquedo:", brinquedos_cadastrados["nome"].unique())
        nova_peca = st.text_input("Nome da peça:")
        adicionar = st.button("➕ Adicionar peça")

        if adicionar and nova_peca:
            nova_linha = pd.DataFrame([[brinquedo_novo, nova_peca]], columns=["Brinquedo", "Item"])
            pecas = pd.concat([pecas, nova_linha], ignore_index=True)
            salvar_dados("pecas_brinquedos", pecas)
            st.success(f"✅ Peça '{nova_peca}' adicionada ao brinquedo '{brinquedo_novo}'!")
            st.rerun()

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

        if not pecas.empty:
            st.dataframe(pecas.sort_values(["Brinquedo", "Item"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma peça cadastrada ainda.")


# ==============================
# MÓDULO FROTA – TimTim Festas (Supabase)
# ==============================
import pandas as pd
import streamlit as st
from datetime import datetime, date
from banco import carregar_dados, salvar_dados

# ---------------------------------
# CONFIGURAÇÕES / CONSTANTES
# ---------------------------------
COLS_VEIC = [
    "placa", "modelo", "tipo", "ano", "status", "km_atual",
    "valor_veiculo", "data_ipva", "data_licenciamento", "data_seguro",
    "ipva_pago", "licenciamento_pago", "seguro_pago", "observacao"
]

COLS_MANU = ["placa", "tipo", "descricao", "data", "km", "valor"]
COLS_CUSTOS = ["descricao", "categoria", "valor", "data", "forma_de_pagamento", "observacao"]
COLS_KMLOG = ["placa", "data", "km"]

TIPOS_MANU = [
    "Troca de óleo", "Pneus", "Freios", "Motor",
    "Elétrica", "Suspensão", "Outros"
]

KM_TROCA_OLEO = 6000
MESES_TROCA_OLEO = 6

# ---------------------------------
# FUNÇÕES DE CONVERSÃO E NORMALIZAÇÃO
# ---------------------------------
def _dates_to_str(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == "object":
            try:
                df[c] = pd.to_datetime(df[c], errors="ignore").astype(str)
            except Exception:
                pass
        elif pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df

def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def _ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def _to_date(series: pd.Series):
    return pd.to_datetime(series, errors="coerce").dt.date

def _to_num(series: pd.Series, as_int=False):
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    return s.astype(int) if as_int else s

def _to_bool(series: pd.Series):
    TRUE_SET = {"true","1","sim","yes","y","verdadeiro","pago","ok","on","t"}
    return series.astype(str).str.strip().str.lower().isin(TRUE_SET)

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
        st.error(f"❌ {rotulo} vencido há {abs(delta)} dia(s) ({data_venc.strftime('%d/%m/%Y')})")
    elif delta <= 15:
        st.warning(f"⚠️ {rotulo} vence em {delta} dia(s) ({data_venc.strftime('%d/%m/%Y')})")
    else:
        st.success(f"✅ {rotulo} em dia (vence {data_venc.strftime('%d/%m/%Y')})")

def proxima_troca_oleo_alerta(veic_row: pd.Series, df_manu: pd.DataFrame):
    placa = veic_row["placa"]
    km_atual = int(veic_row.get("km_atual", 0) or 0)
    manu_placa = df_manu[(df_manu["placa"] == placa) & (df_manu["tipo"].str.lower() == "troca de óleo")]

    if manu_placa.empty:
        st.info("🔧 Troca de óleo: sem histórico cadastrado.")
        return

    manu_placa["data"] = _to_date(manu_placa["data"])
    ultima = manu_placa.sort_values("data", ascending=False).iloc[0]
    data_ult = ultima["data"]
    km_ult = int(ultima.get("km", 0) or 0)
    meses = meses_passados(data_ult, date.today())
    km_diff = max(0, km_atual - km_ult)

    precisa = (km_diff >= KM_TROCA_OLEO) or (meses >= MESES_TROCA_OLEO)
    if precisa:
        st.warning(
            f"⚠️ Troca de óleo vencida • Última: {data_ult.strftime('%d/%m/%Y')} aos {km_ult} km • "
            f"{km_diff} km / {meses} mês(es) desde então."
        )
    else:
        st.success(
            f"✅ Troca de óleo em dia • Última: {data_ult.strftime('%d/%m/%Y')} aos {km_ult} km • "
            f"+{km_diff} km / {meses} mês(es) desde então."
        )

# ---------------------------------
# PÁGINA PRINCIPAL
# ---------------------------------
def pagina_frota():
    st.markdown("""
        <style>
        .tt-card{border:1px solid #eee;border-radius:16px;padding:12px;margin-bottom:10px;background:#FFF4B5;box-shadow:0 1px 3px rgba(0,0,0,.06)}
        .tt-title{font-weight:700;color:#7A5FFF}
        </style>
    """, unsafe_allow_html=True)

    st.header("🚗 Controle de Frota")

    # === Carrega do Supabase ===
    veiculos = _ensure_cols(_norm_cols(carregar_dados("veiculos", COLS_VEIC)), COLS_VEIC)
    manutencoes = _ensure_cols(_norm_cols(carregar_dados("manutencoes", COLS_MANU)), COLS_MANU)
    custos = _ensure_cols(_norm_cols(carregar_dados("custos", COLS_CUSTOS)), COLS_CUSTOS)
    km_log = _ensure_cols(_norm_cols(carregar_dados("km_log", COLS_KMLOG)), COLS_KMLOG)

    # === Tipos ===
    if not veiculos.empty:
        veiculos["ano"] = _to_num(veiculos["ano"], True)
        veiculos["km_atual"] = _to_num(veiculos["km_atual"], True)
        veiculos["valor_veiculo"] = _to_num(veiculos["valor_veiculo"])
        for d in ["data_ipva", "data_licenciamento", "data_seguro"]:
            veiculos[d] = _to_date(veiculos[d])
        for b in ["ipva_pago", "licenciamento_pago", "seguro_pago"]:
            veiculos[b] = _to_bool(veiculos[b])

    if not manutencoes.empty:
        manutencoes["data"] = _to_date(manutencoes["data"])
        manutencoes["valor"] = _to_num(manutencoes["valor"])
        manutencoes["km"] = _to_num(manutencoes["km"], True)

    if not km_log.empty:
        km_log["data"] = _to_date(km_log["data"])
        km_log["km"] = _to_num(km_log["km"], True)

    # === Cards ===
    tot_veic = len(veiculos)
    tot_manu = manutencoes["valor"].sum() if not manutencoes.empty else 0
    soma_frota = veiculos["valor_veiculo"].sum() if not veiculos.empty else 0
    ult_manu = manutencoes["data"].max() if not manutencoes.empty else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚘 Veículos", f"{tot_veic}")
    c2.metric("💵 Gasto em manutenções", f"R$ {tot_manu:,.2f}")
    c3.metric("🧾 Valor total da frota", f"R$ {soma_frota:,.2f}")
    c4.metric("🗓️ Última manutenção", ult_manu.strftime("%d/%m/%Y") if isinstance(ult_manu, date) else "-")

    aba1, aba2, aba3, aba4 = st.tabs(["Cadastro de Veículos", "Manutenções", "Resumo & Alertas", "Controle"])

    # === Aba 1 ===
    with aba1:
        st.subheader("Cadastrar / Atualizar Veículo")
        with st.form("cad_veic", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                placa = st.text_input("Placa").upper().strip()
                tipo = st.selectbox("Tipo", ["Kombi", "Carro", "Moto", "Van", "Pickup", "Outro"])
                ano = st.number_input("Ano", 1970, date.today().year+1, date.today().year)
            with col2:
                modelo = st.text_input("Modelo")
                status = st.selectbox("Status", ["Ativo", "Em manutenção", "Inativo"])
                km_atual = st.number_input("Km Atual", 0)
            with col3:
                valor = st.number_input("Valor Veículo (R$)", 0.0)

            col4, col5, col6 = st.columns(3)
            with col4:
                ipva = st.date_input("Data IPVA", value=None)
                pago1 = st.checkbox("IPVA Pago", False)
            with col5:
                lic = st.date_input("Data Licenciamento", value=None)
                pago2 = st.checkbox("Licenciamento Pago", False)
            with col6:
                seg = st.date_input("Data Seguro", value=None)
                pago3 = st.checkbox("Seguro Pago", False)
            obs = st.text_area("Observações")
            if st.form_submit_button("💾 Salvar veículo"):
                if not placa or not modelo:
                    st.error("Informe Placa e Modelo.")
                else:
                    novo = pd.DataFrame([{
                        "placa": placa, "modelo": modelo, "tipo": tipo, "ano": ano,
                        "status": status, "km_atual": km_atual, "valor_veiculo": valor,
                        "data_ipva": ipva, "data_licenciamento": lic, "data_seguro": seg,
                        "ipva_pago": pago1, "licenciamento_pago": pago2, "seguro_pago": pago3,
                        "observacao": obs
                    }])
                    if placa in veiculos["placa"].values:
                        veiculos.loc[veiculos["placa"] == placa] = novo.iloc[0]
                        st.success(f"Veículo {placa} atualizado!")
                    else:
                        veiculos = pd.concat([veiculos, novo], ignore_index=True)
                        st.success(f"Veículo {placa} cadastrado!")
                    salvar_dados(_dates_to_str(veiculos), "veiculos")

        st.dataframe(veiculos, use_container_width=True) if not veiculos.empty else st.info("Nenhum veículo cadastrado.")

    # === Aba 2 ===
    with aba2:
        st.subheader("Registrar Manutenção")
        if veiculos.empty:
            st.warning("Cadastre um veículo primeiro.")
        else:
            with st.form("cad_manu"):
                placa = st.selectbox("Placa", veiculos["placa"])
                tipo = st.selectbox("Tipo", TIPOS_MANU)
                data = st.date_input("Data", value=date.today())
                km = st.number_input("Km", 0)
                valor = st.number_input("Valor (R$)", 0.0)
                desc = st.text_area("Descrição")
                if st.form_submit_button("💾 Salvar manutenção"):
                    nova = pd.DataFrame([{"placa": placa, "tipo": tipo, "descricao": desc, "data": data, "km": km, "valor": valor}])
                    manutencoes = pd.concat([manutencoes, nova], ignore_index=True)
                    salvar_dados(_dates_to_str(manutencoes), "manutencoes")
                    st.success(f"Manutenção '{tipo}' registrada para {placa}!")
                    try:
                        novo_custo = pd.DataFrame([{
                            "descricao": f"Manutenção {tipo} - {placa}",
                            "categoria": "Manutenção de Frota",
                            "valor": valor,
                            "data": data,
                            "forma_de_pagamento": "Outro",
                            "observacao": desc
                        }])
                        custos = pd.concat([custos, novo_custo], ignore_index=True)
                        salvar_dados(_dates_to_str(custos), "custos")
                        st.info("📥 Lançado também em custos.")
                    except Exception as e:
                        st.warning(f"Erro ao lançar em custos: {e}")

    # === Aba 3 ===
    with aba3:
        st.subheader("Resumo e Alertas")
        hoje = date.today()
        for _, v in veiculos.iterrows():
            st.markdown(f"<div class='tt-card'><div class='tt-title'>{v['placa']} – {v['modelo']}</div>", unsafe_allow_html=True)
            for nome, data, pago in [
                ("IPVA", v["data_ipva"], v["ipva_pago"]),
                ("Licenciamento", v["data_licenciamento"], v["licenciamento_pago"]),
                ("Seguro", v["data_seguro"], v["seguro_pago"])
            ]:
                if pago:
                    st.success(f"✅ {nome} pago.")
                else:
                    alerta_vencimento(nome, data)
            proxima_troca_oleo_alerta(v, manutencoes)
            st.markdown("</div>", unsafe_allow_html=True)

    # === Aba 4 ===
    with aba4:
        st.subheader("Controle rápido")
        if veiculos.empty:
            st.info("Cadastre um veículo para usar esta aba.")
            return

        placa = st.selectbox("Placa", veiculos["placa"])
        v = veiculos.loc[veiculos["placa"] == placa].iloc[0]
        km_atual = st.number_input("Km Atual", value=int(v["km_atual"]))
        ipva_pago = st.checkbox("IPVA Pago", bool(v["ipva_pago"]))
        lic_pago = st.checkbox("Licenciamento Pago", bool(v["licenciamento_pago"]))
        seg_pago = st.checkbox("Seguro Pago", bool(v["seguro_pago"]))
        if st.button("💾 Salvar atualização"):
            veiculos.loc[veiculos["placa"] == placa, ["km_atual","ipva_pago","licenciamento_pago","seguro_pago"]] = [
                km_atual, ipva_pago, lic_pago, seg_pago
            ]
            salvar_dados(_dates_to_str(veiculos), "veiculos")
            km_log = pd.concat([km_log, pd.DataFrame([{"placa": placa, "data": date.today(), "km": km_atual}])], ignore_index=True)
            salvar_dados(_dates_to_str(km_log), "km_log")
            st.success("✅ Atualização salva!")

        df_km = km_log[km_log["placa"] == placa]
        if not df_km.empty:
            df_km["data"] = pd.to_datetime(df_km["data"])
            st.line_chart(df_km.set_index("data")["km"])
        else:
            st.info("Sem histórico de KM ainda.")


# =========================
# 📲 Módulo Envio WhatsApp
# =========================

# ======================================
# PÁGINA: WhatsApp e Suporte
# ======================================

import os
import base64
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

from banco import carregar_dados


def pagina_whatsapp():
    st.header("💬 Central WhatsApp e Suporte")

    # -----------------------------
    # Abas
    # -----------------------------
    aba1, aba2, aba3 = st.tabs(["🧰 Suporte Técnico", "📲 Envio WhatsApp", "📘 Portfólio Montessori"])

    # ======================================================
    # 🧰 ABA 1 - SUPORTE TÉCNICO
    # ======================================================
    with aba1:
        st.subheader("📖 Informações e respostas rápidas")
        st.info("""
        Esta aba é usada para armazenar respostas e instruções rápidas de suporte aos clientes.

        **Tatames:**
        - Tons Cinzas: 100 Tatames
        - Tons Azuis Antigo: 20 Tatames
        - Tons Azuis Novo: 65 Tatames
        - Tons Beges: 20 Tatames
        
        **Quantidade ideal para kits Montessori:**
        - Kit Doçura: 5m² (20 tatames, base bege)
        - Kit Alegria: 11 a 16m² (45 a 65 tatames)
        - Kit Encanto: 18 a 25m² (70 a 100 tatames)
        - Kit TimTim: 20 a 25m² (80 a 100 tatames)

        **Base de cálculo do frete:**
        - Montessori → R$ 5,00 por km
        - Tradicional → R$ 3,00 por km
        - Menor que 5 km → isento

        **Dados técnicos dos brinquedos:**
        - Cama Elástica 2,44 m: até 70 kg, 3 crianças por vez
        - Cama Elástica 1,83 m: até 60 kg, 2 crianças por vez
        - Tombo Legal: até 70 kg, 1 criança por vez, Bivolt
        - Mesa Air Game: sem limite de idade, 120 V
        """)

    # ======================================================
    # 📲 ABA 2 - ENVIO WHATSAPP
    # ======================================================
    with aba2:
        usuario_logado = st.session_state.get("usuario", "")
        if usuario_logado not in ["Bruno", "Maryanne"]:
            st.warning("⚠️ Você não tem permissão para acessar esta aba.")
            return

        # --------------------------
        # Dados do Supabase
        # --------------------------
        reservas = carregar_dados(
            "reservas",
            ["cliente", "brinquedos", "data", "horario_entrega", "horario_retirada",
             "inicio_festa", "fim_festa", "valor_total", "sinal", "falta", "frete", "status"]
        )
        clientes = carregar_dados("clientes", ["nome", "cep"])

        if reservas.empty:
            st.info("Nenhuma reserva encontrada.")
            return

        reservas.columns = [c.lower().strip() for c in reservas.columns]
        clientes.columns = [c.lower().strip() for c in clientes.columns]

        reservas["data"] = pd.to_datetime(reservas["data"], errors="coerce")
        reservas = reservas.dropna(subset=["data"])
        reservas = reservas.merge(clientes, how="left", left_on="cliente", right_on="nome").drop(columns=["nome"], errors="ignore")
        reservas["cep"] = reservas["cep"].fillna("")
        hoje = pd.Timestamp.now().normalize()

        # --------------------------
        # Filtros principais
        # --------------------------
        col1, col2, col3 = st.columns(3)
        meses = [
            (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
            (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
            (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro")
        ]
        with col1:
            mes_sel = st.selectbox("📅 Mês:", options=meses, index=hoje.month - 1, format_func=lambda x: x[1])[0]
        with col2:
            ano_sel = st.number_input("📆 Ano:", min_value=2023, max_value=2100, value=hoje.year, step=1)
        with col3:
            filtro_periodo = st.radio("📍 Exibir:", ["Todas as datas", "Somente futuras", "Hoje e futuras"], horizontal=True)

        df = reservas[
            (reservas["data"].dt.month == mes_sel) &
            (reservas["data"].dt.year == ano_sel)
        ].copy()

        if filtro_periodo == "Somente futuras":
            df = df[df["data"] > hoje]
        elif filtro_periodo == "Hoje e futuras":
            df = df[df["data"] >= hoje]

        if df.empty:
            st.warning("⚠️ Nenhuma reserva encontrada para o período selecionado.")
            return

        # --------------------------
        # Cards resumo
        # --------------------------
        total = len(df)
        futuras = len(df[df["data"] > hoje])
        concluidas = len(df[df["status"].str.lower() == "concluído"])
        c1, c2, c3 = st.columns(3)
        for col, (titulo, valor, cor) in zip(
            [c1, c2, c3],
            [
                ("📅 Total de Reservas", total, "#7A5FFF"),
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

        # --------------------------
        # Geração das mensagens
        # --------------------------
        df = df.sort_values("data")
        mensagens = []
        for _, row in df.iterrows():
            data_fmt = row["data"].strftime("%d/%m")
            cliente = row.get("cliente", "")
            brinquedos = row.get("brinquedos", "")
            cep = str(row.get("cep", "")).replace(".0", "").strip()
            inicio = row.get("inicio_festa", "")
            fim = row.get("fim_festa", "")
            entrega = row.get("horario_entrega", "")
            retirada = row.get("horario_retirada", "")
            valor_total = float(row.get("valor_total", 0) or 0)
            sinal = float(row.get("sinal", 0) or 0)
            falta = float(row.get("falta", 0) or 0)
            frete = float(row.get("frete", 0) or 0)

            msg = f"📍 {data_fmt} – {cliente}\n"
            if cep:
                msg += f"🗺️ CEP: {cep}\n"
            if inicio and fim:
                msg += f"⏰ Festa: {inicio} - {fim}\n"
            msg += f"🕘 Entrega: {entrega} | Retirada: {retirada}\n"
            msg += f"🎠 {brinquedos}\n"
            if frete > 0:
                msg += f"🚚 Frete: R$ {frete:,.2f}\n"
            msg += f"💰 Total: R$ {valor_total:,.2f}\n"
            msg += f"💳 Pagou: R$ {sinal:,.2f} | 💸 Falta: R$ {falta:,.2f}\n"
            mensagens.append(msg.strip())

        texto_final = "\n────────────\n".join(mensagens)

        st.subheader(f"📆 Reservas de {ano_sel} – Mês {mes_sel:02d}")
        st.text_area("Mensagens geradas:", texto_final, height=500)

        # --------------------------
        # Botões de cópia (JS)
        # --------------------------
        copiar_js = f"""
        <script>
        function copiarTexto() {{
            const texto = `{texto_final}`;
            navigator.clipboard.writeText(texto).then(() => {{
                alert("✅ Texto copiado!");
            }});
        }}
        function copiarHoje() {{
            const hoje = new Date().toLocaleDateString('pt-BR');
            const linhas = `{texto_final}`.split("────────────");
            const filtradas = linhas.filter(l => l.includes(hoje.split('/')[0] + '/' + hoje.split('/')[1]));
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
            <button onclick="copiarHoje()" style="background-color:#2ECC71;color:white;border:none;
                    border-radius:8px;padding:10px 20px;font-weight:bold;cursor:pointer;">
                📅 Copiar só hoje
            </button>
        </div>
        """
        components.html(copiar_js, height=100)

    # ======================================================
    # 📘 ABA 3 - PORTFÓLIO MONTESSORI
    # ======================================================
    
    with aba3:
        st.subheader("📘 Portfólio Montessori TimTim Festas")

        pdf_url = "https://hmrqsjdlixeazdfhrqqh.supabase.co/storage/v1/object/public/portfolio/portifolio_out2025.pdf"

        st.markdown(
            f'<iframe src="{pdf_url}" width="100%" height="900px" '
            f'style="border:none;" type="application/pdf"></iframe>',
            unsafe_allow_html=True
        )

        st.success("✅ Portfólio carregado diretamente do Supabase!")



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



# ======================================
# PÁGINA: PRÉ-RESERVAS
# ======================================

import streamlit as st
import pandas as pd
from banco import carregar_dados, supabase


def pagina_pre_reservas():

    st.header("📅 Aprovação de Pré-Reservas")

    # ======================================
    # CARREGAR DADOS
    # ======================================

    pre = carregar_dados(
        "pre_reservas",
        [
            "id","nome","telefone","email","rg","cpf","como_conheceu",
            "cep","logradouro","numero","complemento","bairro","cidade",
            "observacao","data","hora_inicio","hora_fim","brinquedos","status"
        ]
    )

    reservas = carregar_dados(
        "reservas",
        [
            "cliente","brinquedos","data","horario_entrega",
            "horario_retirada","inicio_festa","fim_festa","status"
        ]
    )

    clientes = carregar_dados(
        "clientes",
        [
            "nome","telefone","email","tipo_cliente","rg","cpf","cnpj",
            "como_conseguiu","logradouro","numero","complemento",
            "bairro","cidade","cep","observacao"
        ]
    )

    if pre.empty:
        st.info("Nenhuma pré-reserva encontrada.")
        return

    # ======================================
    # ORDENAR POR DATA
    # ======================================

    pre["data"] = pd.to_datetime(pre["data"])
    pre = pre.sort_values("data")

    # ======================================
    # INDICADORES
    # ======================================

    pendentes = len(pre[pre["status"] == "Pendente"])
    aprovadas = len(pre[pre["status"] == "Aprovada"])
    recusadas = len(pre[pre["status"] == "Recusada"])
    total = len(pre)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("📊 Total", total)
    c2.metric("⏳ Pendentes", pendentes)
    c3.metric("✅ Aprovadas", aprovadas)
    c4.metric("❌ Recusadas", recusadas)

    st.divider()

    # ======================================
    # ABAS
    # ======================================

    tab1, tab2, tab3 = st.tabs(
        ["⏳ Pendentes", "✅ Aprovadas", "❌ Recusadas"]
    )

    # ======================================
    # FUNÇÃO DE CARD
    # ======================================

    def mostrar_reserva(row):

        with st.container():

            st.subheader(f"👤 {row['nome']}")

            col1, col2 = st.columns(2)

            with col1:
                st.write(f"📅 Data: {row['data'].strftime('%d/%m/%Y')}")
                st.write(f"⏰ {row['hora_inicio']} - {row['hora_fim']}")
                st.write(f"🎠 Brinquedos: {row['brinquedos']}")

            with col2:
                st.write(f"📞 Telefone: {row['telefone']}")
                st.write(f"📧 Email: {row['email']}")
                st.write(f"📍 Cidade: {row['cidade']}")

            # ======================================
            # DETALHES EXPANDIDOS
            # ======================================

            with st.expander("📋 Ver todos dados do cliente"):

                st.write("**Documento**")
                st.write(f"RG: {row['rg']}")
                st.write(f"CPF: {row['cpf']}")

                st.write("**Endereço**")
                st.write(f"{row['logradouro']}, {row['numero']}")
                st.write(f"{row['bairro']} - {row['cidade']}")
                st.write(f"CEP: {row['cep']}")

                st.write("**Origem**")
                st.write(row["como_conheceu"])

                st.write("**Observação**")
                st.write(row["observacao"])

            # ======================================
            # BOTÕES
            # ======================================

            if row["status"] == "Pendente":

                col1, col2 = st.columns(2)

                # =============================
                # APROVAR
                # =============================

                if col1.button("✅ Aprovar", key=f"aprovar_{row['id']}"):

                    # CRIAR RESERVA

                    nova_reserva = {
                        "cliente": row["nome"],
                        "brinquedos": row["brinquedos"],
                        "data": row["data"].strftime("%d/%m/%Y"),
                        "horario_entrega": row["hora_inicio"],
                        "horario_retirada": row["hora_fim"],
                        "inicio_festa": row["hora_inicio"],
                        "fim_festa": row["hora_fim"],
                        "status": "Confirmada"
                    }

                    supabase.table("reservas").insert(nova_reserva).execute()

                    # =============================
                    # CLIENTE (UPSERT)
                    # =============================

                    cliente_data = {
                        "nome": row["nome"],
                        "telefone": row["telefone"],
                        "email": row["email"],
                        "tipo_cliente": "Pessoa Física",
                        "rg": row["rg"],
                        "cpf": row["cpf"],
                        "cnpj": "",
                        "como_conseguiu": row["como_conheceu"],
                        "logradouro": row["logradouro"],
                        "numero": row["numero"],
                        "complemento": row["complemento"],
                        "bairro": row["bairro"],
                        "cidade": row["cidade"],
                        "cep": row["cep"],
                        "observacao": row["observacao"]
                    }

                    supabase.table("clientes").upsert(cliente_data).execute()

                    # =============================
                    # ATUALIZAR STATUS
                    # =============================

                    supabase.table("pre_reservas")\
                        .update({"status": "Aprovada"})\
                        .eq("id", row["id"])\
                        .execute()

                    st.success("Reserva aprovada!")
                    st.rerun()

                # =============================
                # RECUSAR
                # =============================

                if col2.button("❌ Recusar", key=f"recusar_{row['id']}"):

                    supabase.table("pre_reservas")\
                        .update({"status": "Recusada"})\
                        .eq("id", row["id"])\
                        .execute()

                    st.warning("Pré-reserva recusada.")
                    st.rerun()

            st.divider()

    # ======================================
    # ABA PENDENTES
    # ======================================

    with tab1:

        dados = pre[pre["status"] == "Pendente"]

        if dados.empty:
            st.info("Nenhuma pré-reserva pendente.")
        else:
            for _, row in dados.iterrows():
                mostrar_reserva(row)

    # ======================================
    # ABA APROVADAS
    # ======================================

    with tab2:

        dados = pre[pre["status"] == "Aprovada"]

        if dados.empty:
            st.info("Nenhuma reserva aprovada.")
        else:
            for _, row in dados.iterrows():
                mostrar_reserva(row)

    # ======================================
    # ABA RECUSADAS
    # ======================================

    with tab3:

        dados = pre[pre["status"] == "Recusada"]

        if dados.empty:
            st.info("Nenhuma reserva recusada.")
        else:
            for _, row in dados.iterrows():
                mostrar_reserva(row)


# ======================================
# PÁGINA: Funcionários (Supabase)
# ======================================

import re
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import streamlit as st

from banco import carregar_dados, salvar_dados


def pagina_funcionarios():
    st.header("👥 Controle de Funcionários")

    # ---------------------------
    # Config / colunas esperadas
    # ---------------------------
    cols_db = [
        "nome", "cpf", "cargo", "categoria", "telefone",
        "data_nascimento", "data_admissao", "status",
        "foto", "observacao"
    ]

    # ---------------------------
    # Helpers locais
    # ---------------------------
    def _ensure_cols(df: pd.DataFrame, cols):
        """Garante colunas e ordem."""
        for c in cols:
            if c not in df.columns:
                df[c] = "" if c not in ["data_nascimento", "data_admissao"] else None
        return df[cols].copy()

    def _to_date_safe(x):
        try:
            if pd.isna(x) or str(x).strip() == "":
                return pd.NaT
            # aceita 'YYYY-MM-DD' ou outros formatos comuns
            return pd.to_datetime(str(x).split(" ")[0], errors="coerce")
        except Exception:
            return pd.NaT

    def _idade(dt: pd.Timestamp | None) -> int | None:
        if dt is None or pd.isna(dt):
            return None
        d = dt.to_pydatetime().date()
        hoje = date.today()
        return hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))

    def _meses_de_casa(dt: pd.Timestamp | None) -> int | None:
        if dt is None or pd.isna(dt):
            return None
        d = dt.to_pydatetime().date()
        hoje = date.today()
        return (hoje.year - d.year) * 12 + (hoje.month - d.month) - (1 if hoje.day < d.day else 0)

    def salvar_foto_imediato(content_bytes: bytes, hint: str, ext: str = ".jpg") -> str:
        """
        Salva bytes de imagem localmente em ./fotos_funcionarios e retorna o caminho relativo.
        """
        base = Path("fotos_funcionarios")
        base.mkdir(parents=True, exist_ok=True)
        # slug do hint
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", hint.strip())[:40] or "foto"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{slug}_{ts}{ext.lower()}"
        path = base / fname
        with open(path, "wb") as f:
            f.write(content_bytes)
        # retorna caminho relativo (string)
        return str(path.as_posix())

    # ---------------------------------
    # Estado inicial de UI
    # ---------------------------------
    if "func_show_camera" not in st.session_state:
        st.session_state.func_show_camera = False
    if "func_ultima_foto" not in st.session_state:
        st.session_state.func_ultima_foto = ""
    if "func_excluir_idx" not in st.session_state:
        st.session_state.func_excluir_idx = None
    if "func_edit_abs_idx" not in st.session_state:
        st.session_state.func_edit_abs_idx = None

    # ---------------------------------
    # Carrega base do Supabase
    # ---------------------------------
    df_base = carregar_dados("funcionarios", cols_db)
    # normaliza nomes
    df_base.columns = [c.lower().strip() for c in df_base.columns]
    df_base = _ensure_cols(df_base, cols_db).fillna("")
    # datas
    df_base["data_nascimento"] = df_base["data_nascimento"].apply(_to_date_safe)
    df_base["data_admissao"] = df_base["data_admissao"].apply(_to_date_safe)
    # foto como string
    df_base["foto"] = df_base["foto"].astype(str).replace(["nan", "None", "0"], "")

    # ---------------------------------
    # Cards (totais, ativos, etc.)
    # ---------------------------------
    total_func = len(df_base)
    ativos = (df_base["status"].str.strip().str.lower() == "ativo").sum()
    inativos = (df_base["status"].str.strip().str.lower() == "inativo").sum()
    com_foto = (df_base["foto"].str.strip() != "").sum()

    idades = []
    for v in df_base["data_nascimento"]:
        idade = _idade(v)
        if idade is not None and idade >= 0:
            idades.append(idade)
    idade_media = round(sum(idades) / len(idades), 1) if idades else 0.0

    meses_list = []
    for v in df_base["data_admissao"]:
        m = _meses_de_casa(v)
        if m is not None and m >= 0:
            meses_list.append(m)
    if meses_list:
        media_meses = int(round(sum(meses_list) / len(meses_list)))
        anos_med = media_meses // 12
        meses_med = media_meses % 12
        tempo_medio_str = f"{anos_med}a {meses_med}m"
    else:
        tempo_medio_str = "0a 0m"

    mes_atual = date.today().month
    aniversariantes_mes = 0
    for v in df_base["data_nascimento"]:
        if pd.notna(v) and v.month == mes_atual:
            aniversariantes_mes += 1

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

    # ---------------------------------
    # Busca
    # ---------------------------------
    st.divider()
    busca = st.text_input("🔎 Buscar funcionário pelo nome:")
    df_view = df_base.copy()
    df_view["_abs_idx"] = df_view.index  # mantém índice absoluto p/ edição/exclusão
    if busca:
        df_view = df_view[df_view["nome"].str.contains(busca, case=False, na=False)]

    st.subheader("➕ Cadastrar / Editar Funcionário")

    # Obtém registro em edição (índice absoluto)
    edit_abs_idx = st.session_state.get("func_edit_abs_idx", None)
    row_ed = df_base.iloc[edit_abs_idx] if (edit_abs_idx is not None and edit_abs_idx in df_base.index) else None

    # ---------------------------------
    # Formulário
    # ---------------------------------
    with st.form("form_funcionario"):
        nome = st.text_input("👤 Nome completo", value=row_ed["nome"] if row_ed is not None else "")

        cpf_input = st.text_input("🪪 CPF", value=row_ed["cpf"] if row_ed is not None else "")
        cpf_clean = re.sub(r"\D", "", cpf_input)
        cpf = f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}" if len(cpf_clean) == 11 else cpf_input

        tel_input = st.text_input("📞 Telefone / WhatsApp", value=row_ed["telefone"] if row_ed is not None else "")
        tel_clean = re.sub(r"\D", "", tel_input)
        telefone = f"({tel_clean[:2]}) {tel_clean[2:7]}-{tel_clean[7:]}" if len(tel_clean) == 11 else tel_input

        cargo = st.text_input("💼 Cargo / Função", value=row_ed["cargo"] if row_ed is not None else "")
        cat_list = ["Efetivo", "Temporário", "Parceiro"]
        cat_val = row_ed["categoria"] if row_ed is not None else "Efetivo"
        categoria = st.selectbox("🏷️ Categoria", cat_list, index=cat_list.index(cat_val) if cat_val in cat_list else 0)

        # datas
        dn_default = pd.to_datetime(row_ed["data_nascimento"], errors="coerce").date() if row_ed is not None and pd.notna(row_ed["data_nascimento"]) else date(1990, 1, 1)
        da_default = pd.to_datetime(row_ed["data_admissao"], errors="coerce").date() if row_ed is not None and pd.notna(row_ed["data_admissao"]) else date.today()

        data_nasc = st.date_input("🎂 Data de nascimento", value=dn_default, min_value=date(1950,1,1), max_value=date.today())
        data_adm = st.date_input("📅 Data de admissão", value=da_default, min_value=date(2000,1,1), max_value=date.today())

        status_list = ["Ativo", "Inativo"]
        status_val = row_ed["status"] if row_ed is not None else "Ativo"
        status = st.selectbox("⚙️ Status", status_list, index=status_list.index(status_val) if status_val in status_list else 0)

        observacao = st.text_area("📝 Observações", value=row_ed["observacao"] if row_ed is not None else "")

        st.markdown("### 📸 Foto do funcionário")
        foto_path = (row_ed["foto"] if row_ed is not None else "") or st.session_state.get("func_ultima_foto", "")

        # Mostra foto atual (se existir)
        if str(foto_path).strip():
            p = Path(str(foto_path)).expanduser()
            if not p.is_absolute():
                p = Path.cwd() / p
            if p.exists():
                st.image(p.as_posix(), width=150, caption="📷 Foto atual")

        uploaded_file = st.file_uploader("Enviar nova foto (.jpg ou .png)", type=["jpg","jpeg","png"], key="upload_foto_func")

        salvar = st.form_submit_button("💾 Salvar Funcionário")

        if salvar:
            # trata foto
            if uploaded_file is not None:
                ext = "." + (uploaded_file.type.split("/")[-1] if uploaded_file.type else "jpg")
                if ext.lower() not in [".jpg", ".jpeg", ".png"]:
                    ext = ".jpg"
                hint = nome or uploaded_file.name
                foto_path = salvar_foto_imediato(uploaded_file.getvalue(), hint, ext=ext)

            if not (nome or "").strip():
                st.error("⚠️ O nome é obrigatório.")
            else:
                novo = {
                    "nome": nome,
                    "cpf": cpf,
                    "cargo": cargo,
                    "categoria": categoria,
                    "telefone": telefone,
                    "data_nascimento": str(data_nasc),
                    "data_admissao": str(data_adm),
                    "status": status,
                    "foto": foto_path or "",
                    "observacao": observacao
                }

                df_to_save = df_base.copy()
                if edit_abs_idx is not None and edit_abs_idx in df_to_save.index:
                    # update
                    for k, v in novo.items():
                        df_to_save.at[edit_abs_idx, k] = v
                    st.success("✏️ Funcionário atualizado com sucesso!")
                    st.session_state.func_edit_abs_idx = None
                else:
                    # insert
                    df_to_save.loc[len(df_to_save)] = novo
                    st.success("✅ Funcionário cadastrado com sucesso!")

                salvar_dados(df_to_save, "funcionarios")
                st.session_state.func_ultima_foto = foto_path or ""
                st.rerun()

    # ---------------------------------
    # Câmera
    # ---------------------------------
    st.divider()
    st.subheader("📷 Capturar foto com a câmera")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("📸 Abrir câmera"):
            st.session_state.func_show_camera = True
    with col_b:
        if st.button("❌ Fechar câmera"):
            st.session_state.func_show_camera = False

    if st.session_state.func_show_camera:
        foto_cam = st.camera_input("Tire a foto e clique em 'Take Photo' 👇", key="cam_func")
        if foto_cam is not None:
            # usa 'nome' do formulário se existir; se não, usa 'funcionario'
            hint = st.session_state.get("last_nome_func", "") or "funcionario"
            foto_path_cam = salvar_foto_imediato(foto_cam.getvalue(), hint, ext=".jpg")
            st.session_state.func_ultima_foto = foto_path_cam
            st.image(foto_path_cam, width=150, caption="📸 Foto capturada e salva")
            st.success(f"Foto salva em: {foto_path_cam}")

    # ---------------------------------
    # Lista de funcionários
    # ---------------------------------
    st.divider()
    st.subheader("📋 Funcionários cadastrados")

    df_list = df_view.copy()
    if df_list.empty:
        st.info("Nenhum funcionário cadastrado.")
        return

    def tempo_casa_str(ts):
        if ts is None or pd.isna(ts):
            return "?"
        d = ts.to_pydatetime().date()
        hoje = date.today()
        anos = hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))
        meses_total = (hoje.year - d.year) * 12 + hoje.month - d.month - (1 if hoje.day < d.day else 0)
        return f"{anos}a {meses_total % 12}m"

    for _, row in df_list.iterrows():
        abs_idx = int(row["_abs_idx"])
        with st.container():
            col1, col2 = st.columns([1, 3])
            with col1:
                foto_val = str(row["foto"]).strip().replace("\\", "/")
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
                dn = row["data_nascimento"]
                is_bday_month = (pd.notna(dn) and dn.month == mes_atual)

                nome_display = f"**{row['nome']}**"
                if is_bday_month:
                    nome_display += (
                        " <span style='background-color:#EDE0FF; color:#7A5FFF; "
                        "padding:3px 8px; border-radius:8px; font-size:0.8em; "
                        "font-weight:600; margin-left:6px;'>🎉 Parabéns!</span>"
                    )
                st.markdown(nome_display, unsafe_allow_html=True)
                st.caption(f"{row['cargo']} • {row['categoria']}")

                status_icon = "🟢" if str(row["status"]).strip().lower() == "ativo" else "🔴"
                idade = _idade(dn) if pd.notna(dn) else "?"
                da = row["data_admissao"]
                tempo = tempo_casa_str(da) if pd.notna(da) else "?"

                st.write(f"{status_icon} {row['status']} • 🎂 {idade} anos • ⏱️ {tempo}")

                if row["telefone"]:
                    num = re.sub(r"\D", "", str(row["telefone"]))
                    if num:
                        st.markdown(f"[💬 WhatsApp](https://wa.me/55{num})", unsafe_allow_html=True)

                with st.expander("🔽 Ver mais detalhes"):
                    st.write(f"**CPF:** {row['cpf'] or '-'}")
                    st.write(f"**Nascimento:** {dn.date().strftime('%d/%m/%Y') if pd.notna(dn) else '-'}")
                    st.write(f"**Admissão:** {da.date().strftime('%d/%m/%Y') if pd.notna(da) else '-'}")
                    st.write(f"**Observações:** {row['observacao'] or '-'}")

                col_ed, col_del = st.columns(2)
                with col_ed:
                    if st.button("✏️ Editar", key=f"edit_func_{abs_idx}"):
                        st.session_state.func_edit_abs_idx = abs_idx
                        st.rerun()

                with col_del:
                    if st.session_state.get("func_excluir_idx") == abs_idx:
                        st.warning(f"⚠️ Confirmar exclusão de {row['nome']}?")
                        c_ok, c_cancel = st.columns(2)
                        with c_ok:
                            if st.button("✅ Sim, excluir", key=f"confirma_{abs_idx}"):
                                df_to_save = df_base.copy()
                                if abs_idx in df_to_save.index:
                                    df_to_save = df_to_save.drop(index=abs_idx).reset_index(drop=True)
                                    salvar_dados(df_to_save, "funcionarios")
                                    st.success(f"{row['nome']} foi removido com sucesso.")
                                st.session_state.func_excluir_idx = None
                                st.rerun()
                        with c_cancel:
                            if st.button("❌ Cancelar", key=f"cancela_{abs_idx}"):
                                st.session_state.func_excluir_idx = None
                                st.rerun()
                    else:
                        if st.button("🗑️ Excluir", key=f"del_func_{abs_idx}"):
                            st.session_state.func_excluir_idx = abs_idx
                            st.rerun()

# ========================================
# PAGINA CONTRATO INICIO
# ========================================
# =========================================
# MÓDULO: CONTRATOS
# =========================================

import os
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import streamlit as st
import pandas as pd
from banco import carregar_dados


def gerar_pdf(texto, caminho_pdf):
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    largura, altura = A4

    y = altura - 40
    for linha in texto.split("\n"):
        c.drawString(40, y, linha)
        y -= 14
        if y < 40:
            c.showPage()
            y = altura - 40

    c.save()


def pagina_contratos():
    st.header("📄 Gerar Contrato")

    # ===============================
    # CARREGAR DADOS
    # ===============================
    clientes = carregar_dados(
        "clientes",
        ["nome", "telefone", "email"]
    )

    reservas = carregar_dados(
        "reservas",
        ["id", "cliente", "brinquedos", "data", "valor_total", "sinal", "falta"]
    )

    if clientes.empty or reservas.empty:
        st.warning("⚠️ Cadastre clientes e reservas antes de gerar contratos.")
        return

    # ===============================
    # SELEÇÃO
    # ===============================
    cliente_nome = st.selectbox(
        "Cliente",
        sorted(clientes["nome"].dropna().unique())
    )

    reservas_cliente = reservas[reservas["cliente"] == cliente_nome]

    if reservas_cliente.empty:
        st.info("Este cliente não possui reservas.")
        return

    reserva_id = st.selectbox(
        "Reserva",
        reservas_cliente["id"].astype(str).tolist()
    )

    reserva = reservas_cliente[reservas_cliente["id"].astype(str) == reserva_id].iloc[0]
    cliente = clientes[clientes["nome"] == cliente_nome].iloc[0]

    # ===============================
    # DADOS FORMATADOS
    # ===============================
    brinquedos_txt = f"Brinquedos Locados: {reserva['brinquedos']}"
    data_evento = pd.to_datetime(reserva["data"]).strftime("%d/%m/%Y")

    mapa = {
        "{{CLIENTE}}": cliente_nome,
        "{{TELEFONE}}": cliente.get("telefone", ""),
        "{{DATA_EVENTO}}": data_evento,
        "{{BRINQUEDOS}}": brinquedos_txt,
        "{{VALOR_TOTAL}}": f"{float(reserva['valor_total']):,.2f}",
        "{{SINAL}}": f"{float(reserva['sinal']):,.2f}",
        "{{FALTA}}": f"{float(reserva['falta']):,.2f}",
    }

    # ===============================
    # GERAR CONTRATO
    # ===============================
    if st.button("📄 Gerar Contrato"):
        modelo_path = "modelo.docx"
        doc = Document(modelo_path)

        texto_completo = []

        for p in doc.paragraphs:
            for chave, valor in mapa.items():
                if chave in p.text:
                    p.text = p.text.replace(chave, valor)
            texto_completo.append(p.text)

        nome_base = f"Contrato_{cliente_nome.replace(' ', '_')}_{data_evento}"

        docx_path = f"/tmp/{nome_base}.docx"
        pdf_path = f"/tmp/{nome_base}.pdf"

        doc.save(docx_path)
        gerar_pdf("\n".join(texto_completo), pdf_path)

        st.success("✅ Contrato gerado com sucesso!")

        with open(docx_path, "rb") as f:
            st.download_button(
                "⬇️ Baixar contrato (Word)",
                f,
                file_name=f"{nome_base}.docx"
            )

        with open(pdf_path, "rb") as f:
            st.download_button(
                "⬇️ Baixar contrato (PDF)",
                f,
                file_name=f"{nome_base}.pdf"
            )

# ========================================
# PAGINA CONTRATO FIM
# ========================================

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
            "Pré-Reservas": ("📊 Aprovar Reservas", "pre_reservas"),
            "Agenda": ("🕓 Agenda", "agenda"),
            "Custos": ("💸 Custos", "custos"), 
            "Estoque": ("📦 Estoque", "estoque"),    
            "Check-list": ("✅ Check-list", "check-list"), 
            "Frota": ("🚗 Frota", "frota"),
            "Funcionários": ("👷 Funcionários", "funcionarios"),
            "Envio WhatsApp": ("📲 Suporte", "envio_whatsapp"),
            "Gerar Contratos": ("📲 Gerar Contratos", "pagina_contratos"),
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
    elif menu == "Pré-Reservas":
        pagina_pre_reservas()
    elif menu == "Aprovar Reservas":
        pagina_contratos() 
    elif menu == "Sair":
        st.session_state["logado"] = False
        st.experimental_rerun()




























