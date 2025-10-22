import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime

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

# ========================================
# FUNÇÕES AUXILIARES
# ========================================
def carregar_dados(nome_arquivo, colunas):
    if os.path.exists(nome_arquivo):
        df = pd.read_csv(nome_arquivo)
        df.columns = df.columns.str.strip()  # remove espaços extras
        return df
    else:
        return pd.DataFrame(columns=colunas)

def salvar_dados(df, nome_arquivo):
    df.to_csv(nome_arquivo, index=False)

# ========================================
# PÁGINAS
# ========================================
def pagina_brinquedos():
    st.header("🎠 Cadastro de Brinquedos")
    df = carregar_dados("brinquedos.csv", ["Nome", "Valor", "Status"])

    with st.form("form_brinquedo"):
        nome = st.text_input("Nome do brinquedo")
        valor = st.number_input("Valor de locação (R$)", min_value=0.0, step=10.0)
        status = st.selectbox("Status", ["Disponível", "Indisponível"])
        enviar = st.form_submit_button("Salvar brinquedo")

        if enviar and nome:
            df.loc[len(df)] = [nome, valor, status]
            salvar_dados(df, "brinquedos.csv")
            st.success(f"✅ {nome} cadastrado com sucesso!")

    st.subheader("Brinquedos cadastrados")
    st.dataframe(df)

    if len(df) > 0:
        index_excluir = st.number_input("Número da linha para excluir", 0, len(df)-1, 0)
        if st.button("Excluir brinquedo selecionado"):
            excluido = df.iloc[index_excluir]["Nome"]
            df = df.drop(index_excluir).reset_index(drop=True)
            salvar_dados(df, "brinquedos.csv")
            st.warning(f"🗑️ {excluido} removido com sucesso!")

def pagina_clientes():
    st.header("👨‍👩‍👧 Cadastro de Clientes")

    colunas = [
        "Nome", "Telefone", "Email", "Tipo de Cliente", "CPF", "CNPJ",
        "Como conseguiu", "Logradouro", "Número", "Complemento",
        "Bairro", "Cidade", "CEP", "Observação"
    ]

    df = carregar_dados("clientes.csv", colunas)

    with st.form("form_cliente"):
        nome = st.text_input("Nome do cliente")
        telefone_raw = st.text_input("Telefone (somente números)", max_chars=11)

        # Formatação automática do telefone
        telefone = ""
        if telefone_raw.isdigit() and len(telefone_raw) >= 10:
            telefone = f"({telefone_raw[:2]}) {telefone_raw[2:7]}-{telefone_raw[7:]}"
        else:
            telefone = telefone_raw

        email = st.text_input("Email")
        tipo_cliente = st.radio("Tipo de Cliente", ["Pessoa Física", "Pessoa Jurídica"])

        cpf, cnpj = "", ""
        if tipo_cliente == "Pessoa Física":
            cpf = st.text_input("CPF")
        else:
            cnpj = st.text_input("CNPJ")

        como_conseguiu = st.selectbox(
            "Como conseguiu esse cliente?",
            ["Indicação", "Instagram", "Facebook", "Google", "WhatsApp", "Outro"]
        )

        st.markdown("---")
        st.subheader("📍 Endereço")
        cep = st.text_input("CEP", max_chars=9)

        # 🔎 Busca automática do endereço via ViaCEP
        logradouro = numero = complemento = bairro = cidade = ""
        if st.form_submit_button("Buscar CEP"):
            cep_limpo = cep.replace("-", "").strip()
            if len(cep_limpo) == 8:
                try:
                    r = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/")
                    if r.status_code == 200:
                        dados = r.json()
                        if "erro" not in dados:
                            logradouro = dados.get("logradouro", "")
                            bairro = dados.get("bairro", "")
                            cidade = dados.get("localidade", "")
                            st.success("✅ Endereço encontrado!")
                        else:
                            st.warning("⚠️ CEP não encontrado.")
                    else:
                        st.error("Erro ao consultar o CEP.")
                except Exception as e:
                    st.error(f"Erro ao conectar ao ViaCEP: {e}")
            else:
                st.warning("Digite um CEP válido com 8 dígitos.")

        logradouro = st.text_input("Logradouro", value=logradouro)
        numero = st.text_input("Número", value=numero)
        complemento = st.text_input("Complemento", value=complemento)
        bairro = st.text_input("Bairro", value=bairro)
        cidade = st.text_input("Cidade", value=cidade)

        observacao = st.text_area("Observação (opcional)")

        enviar = st.form_submit_button("Salvar cliente")

        if enviar and nome:
            df.loc[len(df)] = [
                nome, telefone, email, tipo_cliente, cpf, cnpj,
                como_conseguiu, logradouro, numero, complemento, bairro, cidade, cep, observacao
            ]
            salvar_dados(df, "clientes.csv")
            st.success(f"✅ Cliente {nome} cadastrado com sucesso!")

    st.subheader("📋 Clientes cadastrados")
    st.dataframe(df)

def pagina_reservas():
    st.header("📅 Reservas")
    brinquedos = carregar_dados("brinquedos.csv", ["Nome", "Valor", "Status"])
    clientes = carregar_dados("clientes.csv", ["Nome", "Telefone", "Endereço"])
    
    reservas = carregar_dados(
        "reservas.csv",
        ["Cliente", "Brinquedos", "Data", "Valor Brinquedos", "Valor a Mais",
         "Frete", "Desconto", "Total", "Observação", "Status"]
    )

    # Inicializa o estado de edição
    if "editando_reserva" not in st.session_state:
        st.session_state.editando_reserva = None

    st.subheader("📋 Reservas realizadas")
    if not reservas.empty:
        for i, row in reservas.iterrows():
            with st.expander(f"🎈 {row['Cliente']} - {row['Data']}"):
                st.write(f"**Brinquedos:** {row['Brinquedos']}")
                st.write(f"**Valor Brinquedos:** R$ {row['Valor Brinquedos']:.2f}")
                st.write(f"**Valor a Mais:** R$ {row['Valor a Mais']:.2f}")
                st.write(f"**Frete:** R$ {row['Frete']:.2f}")
                st.write(f"**Desconto:** R$ {row['Desconto']:.2f}")
                st.write(f"**Total:** R$ {row['Total']:.2f}")
                st.write(f"**Observação:** {row['Observação']}")
                st.write(f"**Status:** {row['Status']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"editar_{i}"):
                        st.session_state.editando_reserva = i
                        st.rerun()
                with col2:
                    if st.button("🗑️ Excluir", key=f"excluir_{i}"):
                        reservas = reservas.drop(i).reset_index(drop=True)
                        salvar_dados(reservas, "reservas.csv")
                        st.success("Reserva excluída com sucesso!")
                        st.rerun()
    else:
        st.info("Nenhuma reserva cadastrada ainda.")

    st.divider()
    st.subheader("➕ Adicionar / Editar Reserva")

    # Dados para o formulário
    if st.session_state.editando_reserva is not None:
        i = st.session_state.editando_reserva
        reserva = reservas.iloc[i]
        st.info(f"Editando reserva de {reserva['Cliente']}")
    else:
        reserva = {"Cliente": "", "Brinquedos": "", "Data": datetime.today(),
                   "Valor Brinquedos": 0.0, "Valor a Mais": 0.0, "Frete": 0.0,
                   "Desconto": 0.0, "Total": 0.0, "Observação": "", "Status": "Pendente"}

    with st.form("form_reserva"):
        cliente = st.selectbox("Cliente", clientes["Nome"] if not clientes.empty else [],
                               index=clientes["Nome"].tolist().index(reserva["Cliente"]) 
                                     if reserva["Cliente"] in clientes["Nome"].tolist() else 0)
        itens = st.multiselect("Brinquedos", brinquedos["Nome"] if not brinquedos.empty else [],
                               default=reserva["Brinquedos"].split(", ") if reserva["Brinquedos"] else [])
        data = st.date_input("Data da reserva", pd.to_datetime(reserva["Data"]))

        st.markdown("---")
        st.subheader("💬 Informações adicionais")
        observacao = st.text_area("Observação (opcional)", value=reserva["Observação"])
        valor_extra = st.number_input("Valor a mais (R$)", min_value=0.0, step=10.0,
                                      value=float(reserva["Valor a Mais"]))
        frete = st.number_input("Frete (R$)", min_value=0.0, step=10.0,
                                value=float(reserva["Frete"]))
        desconto = st.number_input("Desconto (R$)", min_value=0.0, step=10.0,
                                   value=float(reserva["Desconto"]))

        status = st.selectbox("Status da reserva", ["Pendente", "Confirmada", "Cancelada"],
                              index=["Pendente", "Confirmada", "Cancelada"].index(reserva["Status"])
                                    if reserva["Status"] else 0)

        salvar = st.form_submit_button("💾 Salvar")

        if salvar and cliente and itens:
            valor_brinquedos = brinquedos[brinquedos["Nome"].isin(itens)]["Valor"].sum()
            total = valor_brinquedos + valor_extra + frete - desconto

            nova_reserva = {
                "Cliente": cliente,
                "Brinquedos": ", ".join(itens),
                "Data": str(data),
                "Valor Brinquedos": valor_brinquedos,
                "Valor a Mais": valor_extra,
                "Frete": frete,
                "Desconto": desconto,
                "Total": total,
                "Observação": observacao,
                "Status": status
            }

            if st.session_state.editando_reserva is not None:
                reservas.loc[st.session_state.editando_reserva] = nova_reserva
                st.session_state.editando_reserva = None
                st.success("Reserva atualizada com sucesso!")
            else:
                reservas.loc[len(reservas)] = nova_reserva
                st.success("Reserva adicionada com sucesso!")

            salvar_dados(reservas, "reservas.csv")
            st.rerun()

    # Total geral
    if not reservas.empty:
        total_geral = reservas["Total"].sum()
        st.markdown(f"### 💰 Total acumulado: R$ {total_geral:.2f}")

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

    menu = st.sidebar.radio("Menu", ["Brinquedos", "Clientes", "Reservas", "Relatórios", "Sair"])

    if menu == "Brinquedos":
        pagina_brinquedos()
    elif menu == "Clientes":
        pagina_clientes()
    elif menu == "Reservas":
        pagina_reservas()
    elif menu == "Relatórios":
        pagina_relatorios()
    elif menu == "Sair":
        st.session_state["logado"] = False
        st.experimental_rerun()
