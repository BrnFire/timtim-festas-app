# ==============================================================
# MÓDULO ESCALA DE EQUIPE – TimTim Festas
# Arquivo independente. Não altera nenhum outro módulo do app.
#
# O QUE FAZ:
#   - Define quem ENTREGA, quem MONITORA e quem RETIRA cada evento
#   - Marca automaticamente como PENDENTE o que ainda não tem gente
#   - Gera alertas escalonados: 10, 5 e 3 dias antes (configurável)
#   - Para de alertar assim que a função é preenchida
#   - Monta a mensagem pronta para o grupo do WhatsApp
#   - Registra o que já foi avisado (não repete o mesmo alerta)
#
# INSTALAÇÃO:
#   1) Salve como  escala.py  na mesma pasta do app.py
#   2) Rode o SQL do escala_supabase.sql no Supabase
#   3) No app.py, adicione as 3 linhas indicadas no final deste arquivo
# ==============================================================

VERSAO_MODULO = "v1"

import re
from datetime import datetime, date, timedelta
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

from banco import carregar_dados, inserir_um, atualizar_por_filtro, deletar_por_filtro

# --------------------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------------------

# 🔗 Link de convite do SEU grupo do WhatsApp.
# Como obter: abra o grupo > nome do grupo > "Convidar via link" > Copiar link.
# Cole aqui. Se deixar vazio, o app mostra só o texto para copiar.
LINK_GRUPO_WHATSAPP = ""   # ex.: "https://chat.whatsapp.com/XXXXXXXXXXXXXXX"

# 📞 Telefones para aviso individual (fallback do grupo)
# O wa.me NÃO abre grupos — só conversas individuais.
RESPONSAVEIS = {
    "Bruno": "",        # ex.: "11987654321"
    "Maryanne": "",
}

# 🔔 Marcos de alerta (dias antes do evento)
MARCOS_ALERTA = [10, 5, 3, 1]

# 🎭 Funções que precisam ser preenchidas em cada evento
FUNCOES = ["Entrega", "Monitor", "Retirada"]

# Rótulos especiais do selectbox
OPCAO_VAZIA = "— não definido —"
OPCAO_MANUAL = "✏️ Digitar nome..."

# Funções consideradas OBRIGATÓRIAS para o alerta disparar
FUNCOES_CRITICAS = ["Monitor", "Entrega", "Retirada"]

COLS_ESCALA = [
    "id_escala", "reserva_id", "data_evento", "funcao",
    "funcionario", "observacao", "criado_em", "atualizado_em"
]

COLS_AVISOS = [
    "id_aviso", "reserva_id", "marco_dias", "enviado_em", "canal"
]

COLS_RESERVAS = [
    "id", "cliente", "brinquedos", "data",
    "horario_entrega", "horario_retirada",
    "inicio_festa", "fim_festa", "valor_total", "status"
]

COLS_FUNCIONARIOS = ["nome", "cargo", "categoria", "telefone", "status"]

STATUS_IGNORADOS = {"cancelada", "cancelado", "recusada", "recusado"}


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


def _f(v, padrao=0.0):
    try:
        if v is None or pd.isna(v):
            return padrao
        return float(v)
    except (TypeError, ValueError):
        return padrao


def _hora(v, padrao=""):
    txt = _s(v)
    if not txt:
        return padrao
    m = re.match(r"(\d{1,2})[:h]?(\d{2})?", txt)
    if not m:
        return padrao
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    return f"{h:02d}:{mi:02d}" if h <= 23 and mi <= 59 else padrao


def _data(v):
    d = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(d) else d.date()


def _tel_limpo(v):
    return re.sub(r"\D", "", _s(v))


def url_whatsapp(telefone: str, mensagem: str) -> str:
    num = _tel_limpo(telefone)
    if not num:
        return ""
    if not num.startswith("55"):
        num = "55" + num
    return f"https://wa.me/{num}?text={quote_plus(mensagem)}"


def _dias_ate(d: date) -> int:
    return (d - date.today()).days


def _rotulo_prazo(dias: int) -> str:
    if dias < 0:
        return f"há {abs(dias)} dia(s)"
    if dias == 0:
        return "HOJE"
    if dias == 1:
        return "AMANHÃ"
    return f"em {dias} dias"


def _cor_urgencia(dias: int, completo: bool) -> tuple:
    """Retorna (cor, icone) conforme urgência."""
    if completo:
        return "#2ECC71", "✅"
    if dias <= 1:
        return "#C0392B", "🔥"
    if dias <= 3:
        return "#E74C3C", "🚨"
    if dias <= 5:
        return "#E67E22", "⚠️"
    if dias <= 10:
        return "#F1C40F", "🟡"
    return "#3498DB", "🔵"


# ==============================================================
# CARGA DE DADOS
# ==============================================================
def carregar_eventos(dias_frente: int = 60, incluir_passados: int = 0) -> pd.DataFrame:
    """Reservas futuras dentro da janela."""
    try:
        df = carregar_dados("reservas", COLS_RESERVAS)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])
    df["data_d"] = df["data"].dt.date

    hoje = date.today()
    ini = hoje - timedelta(days=incluir_passados)
    fim = hoje + timedelta(days=dias_frente)
    df = df[(df["data_d"] >= ini) & (df["data_d"] <= fim)]

    df = df[~df["status"].apply(lambda x: _s(x).lower() in STATUS_IGNORADOS)]
    return df.sort_values("data_d")


def carregar_escala() -> pd.DataFrame:
    try:
        df = carregar_dados("escala_equipe", COLS_ESCALA)
        if df is None or df.empty:
            return pd.DataFrame(columns=COLS_ESCALA)
        return df.copy()
    except Exception:
        return pd.DataFrame(columns=COLS_ESCALA)


def carregar_avisos() -> pd.DataFrame:
    try:
        df = carregar_dados("escala_avisos", COLS_AVISOS)
        if df is None or df.empty:
            return pd.DataFrame(columns=COLS_AVISOS)
        return df.copy()
    except Exception:
        return pd.DataFrame(columns=COLS_AVISOS)


def carregar_equipe() -> pd.DataFrame:
    """Funcionários ativos, para os selects."""
    try:
        df = carregar_dados("funcionarios", COLS_FUNCIONARIOS)
        if df is None or df.empty:
            return pd.DataFrame(columns=COLS_FUNCIONARIOS)
        df = df.copy()
        df["status"] = df["status"].apply(_s)
        ativos = df[df["status"].str.lower() != "inativo"]
        return ativos if not ativos.empty else df
    except Exception:
        return pd.DataFrame(columns=COLS_FUNCIONARIOS)


def nomes_ja_usados(df_escala: pd.DataFrame, nomes_cadastrados: list) -> list:
    """
    Nomes digitados manualmente em escalas anteriores (não estão em Funcionários).
    Ficam disponíveis no select dos próximos eventos, sem precisar digitar de novo.
    """
    if df_escala is None or df_escala.empty:
        return []
    usados = {_s(n) for n in df_escala["funcionario"].dropna().tolist() if _s(n)}
    return sorted(usados - set(nomes_cadastrados))


# ==============================================================
# LÓGICA DA ESCALA
# ==============================================================
def escala_do_evento(df_escala: pd.DataFrame, reserva_id) -> dict:
    """{funcao: funcionario} do evento."""
    if df_escala is None or df_escala.empty:
        return {}
    sub = df_escala[df_escala["reserva_id"].astype(str) == str(reserva_id)]
    out = {}
    for _, r in sub.iterrows():
        func = _s(r.get("funcionario"))
        if func:
            out[_s(r.get("funcao"))] = func
    return out


def pendencias_do_evento(atribuicoes: dict) -> list:
    """Funções críticas ainda sem responsável."""
    return [f for f in FUNCOES_CRITICAS if not atribuicoes.get(f)]


def marco_atual(dias: int) -> int:
    """
    Qual marco de alerta está ativo agora.
    Ex.: faltam 7 dias -> marco 10 (já passou de 10, ainda não chegou em 5).
    Retorna None se ainda não atingiu o primeiro marco.
    """
    marcos = sorted(MARCOS_ALERTA, reverse=True)
    ativo = None
    for m in marcos:
        if dias <= m:
            ativo = m
    return ativo


def ja_avisado(df_avisos: pd.DataFrame, reserva_id, marco: int) -> bool:
    if df_avisos is None or df_avisos.empty or marco is None:
        return False
    sub = df_avisos[
        (df_avisos["reserva_id"].astype(str) == str(reserva_id)) &
        (pd.to_numeric(df_avisos["marco_dias"], errors="coerce") == marco)
    ]
    return not sub.empty


def montar_painel(eventos: pd.DataFrame, df_escala: pd.DataFrame,
                  df_avisos: pd.DataFrame) -> list:
    """Lista de eventos enriquecida com escala, pendências e status de alerta."""
    itens = []
    for _, ev in eventos.iterrows():
        d = ev["data_d"]
        dias = _dias_ate(d)
        atrib = escala_do_evento(df_escala, ev["id"])
        pend = pendencias_do_evento(atrib)
        marco = marco_atual(dias)

        itens.append({
            "reserva_id": ev["id"],
            "cliente": _s(ev.get("cliente"), "(sem cliente)"),
            "data": d,
            "dias": dias,
            "brinquedos": _s(ev.get("brinquedos")),
            "inicio_festa": _hora(ev.get("inicio_festa")),
            "fim_festa": _hora(ev.get("fim_festa")),
            "horario_entrega": _hora(ev.get("horario_entrega")),
            "horario_retirada": _hora(ev.get("horario_retirada")),
            "valor_total": _f(ev.get("valor_total")),
            "atribuicoes": atrib,
            "pendencias": pend,
            "completo": len(pend) == 0,
            "marco": marco,
            "avisado": ja_avisado(df_avisos, ev["id"], marco),
            # alerta ativo = tem pendência + atingiu um marco + ainda não avisado
            "alerta_ativo": len(pend) > 0 and marco is not None and dias >= 0,
        })
    return itens


# ==============================================================
# PERSISTÊNCIA
# ==============================================================
def salvar_atribuicao(reserva_id, data_evento: date, funcao: str,
                      funcionario: str, observacao: str = ""):
    registro = {
        "reserva_id": int(reserva_id) if pd.notna(reserva_id) else None,
        "data_evento": str(data_evento),
        "funcao": funcao,
        "funcionario": _s(funcionario),
        "observacao": _s(observacao),
        "atualizado_em": str(datetime.now()),
    }
    filtro = {"reserva_id": registro["reserva_id"], "funcao": funcao}
    try:
        atualizar_por_filtro("escala_equipe", registro, filtro)
    except Exception:
        pass
    try:
        registro["criado_em"] = str(datetime.now())
        inserir_um("escala_equipe", registro)
    except Exception:
        pass


def limpar_atribuicao(reserva_id, funcao: str):
    try:
        deletar_por_filtro("escala_equipe", {
            "reserva_id": int(reserva_id), "funcao": funcao
        })
    except Exception:
        pass


def registrar_aviso(reserva_id, marco: int, canal: str = "WhatsApp"):
    try:
        inserir_um("escala_avisos", {
            "reserva_id": int(reserva_id) if pd.notna(reserva_id) else None,
            "marco_dias": int(marco),
            "enviado_em": str(datetime.now()),
            "canal": canal,
        })
    except Exception:
        pass


def limpar_avisos_evento(reserva_id):
    """Ao completar a escala, zera o histórico (se remarcar, avisa de novo)."""
    try:
        deletar_por_filtro("escala_avisos", {"reserva_id": int(reserva_id)})
    except Exception:
        pass


# ==============================================================
# MENSAGENS
# ==============================================================
def msg_pendencia_evento(item: dict) -> str:
    pend = ", ".join(item["pendencias"])
    return (
        f"⚠️ *PENDÊNCIA DE ESCALA*\n"
        f"📅 {item['data'].strftime('%d/%m/%Y')} ({_rotulo_prazo(item['dias'])})\n"
        f"👤 Cliente: {item['cliente']}\n"
        f"🎠 {item['brinquedos']}\n"
        f"🎉 Festa: {item['inicio_festa']} às {item['fim_festa']}\n\n"
        f"❌ *Falta definir:* {pend}\n\n"
        f"Precisamos fechar isso o quanto antes! 🙏"
    )


def msg_resumo_pendencias(itens: list) -> str:
    pendentes = [i for i in itens if not i["completo"] and i["dias"] >= 0]
    if not pendentes:
        return ("✅ *ESCALA EM DIA*\n\n"
                "Todos os eventos futuros já têm entrega, monitor e retirada definidos. 🎉")

    linhas = [f"⚠️ *PENDÊNCIAS DE ESCALA* — {len(pendentes)} evento(s)", ""]
    for i in sorted(pendentes, key=lambda x: x["dias"]):
        _, icone = _cor_urgencia(i["dias"], False)
        linhas.append(f"{icone} *{i['data'].strftime('%d/%m')}* ({_rotulo_prazo(i['dias'])}) — {i['cliente']}")
        linhas.append(f"   ❌ Falta: {', '.join(i['pendencias'])}")
        ok = [f"{f}: {n}" for f, n in i["atribuicoes"].items() if n]
        if ok:
            linhas.append(f"   ✅ Já temos: {' | '.join(ok)}")
        linhas.append("")
    linhas.append("Bora fechar essas escalas! 🙏")
    return "\n".join(linhas)


def msg_escala_confirmada(item: dict) -> str:
    linhas = [
        f"✅ *ESCALA CONFIRMADA*",
        f"📅 {item['data'].strftime('%d/%m/%Y')}",
        f"👤 {item['cliente']}",
        f"🎠 {item['brinquedos']}",
        f"🎉 Festa: {item['inicio_festa']} às {item['fim_festa']}",
        "",
    ]
    for f in FUNCOES:
        nome = item["atribuicoes"].get(f)
        if f == "Entrega":
            hora = item["horario_entrega"]
        elif f == "Retirada":
            hora = item["horario_retirada"]
        else:
            hora = f"{item['inicio_festa']}-{item['fim_festa']}"
        linhas.append(f"• *{f}* ({hora}): {nome or '—'}")
    return "\n".join(linhas)


# ==============================================================
# PÁGINA
# ==============================================================
def pagina_escala():
    st.markdown("""
        <style>
        .es-card{border-radius:14px;padding:14px 18px;margin-bottom:10px;
                 box-shadow:0 2px 8px rgba(0,0,0,.08);border-left:7px solid #ccc;
                 background:#fff;}
        .es-titulo{font-size:1.15em;font-weight:800;color:#333;}
        .es-cli{color:#7A5FFF;font-weight:700;}
        .es-pend{background:#FADBD8;border-radius:8px;padding:6px 12px;
                 margin-top:8px;font-weight:700;color:#922B21;display:inline-block;}
        .es-ok{background:#E8F8F0;border-radius:8px;padding:6px 12px;
               margin-top:8px;font-weight:700;color:#1E8449;display:inline-block;}
        .es-func{background:#F8F9F9;border-radius:8px;padding:8px 12px;
                 margin:6px 0;font-size:.95em;border:1px solid rgba(0,0,0,.06);}
        </style>
    """, unsafe_allow_html=True)

    st.header("👷 Escala de Equipe")
    st.caption(f"Módulo {VERSAO_MODULO} · alertas em {', '.join(map(str, MARCOS_ALERTA))} dias antes")

    # ---------- Dados ----------
    with st.spinner("Carregando eventos e escala..."):
        eventos = carregar_eventos()
        df_escala = carregar_escala()
        df_avisos = carregar_avisos()
        equipe = carregar_equipe()

    if eventos.empty:
        st.info("Nenhum evento futuro encontrado nos próximos 60 dias.")
        return

    itens = montar_painel(eventos, df_escala, df_avisos)

    nomes_equipe = sorted(equipe["nome"].dropna().unique().tolist()) if not equipe.empty else []
    nomes_avulsos = nomes_ja_usados(df_escala, nomes_equipe)
    if not nomes_equipe:
        st.warning("⚠️ Nenhum funcionário ativo cadastrado. "
                   "Cadastre em **Funcionários** para escalar a equipe.")

    # ---------- Cards de resumo ----------
    total = len(itens)
    completos = sum(1 for i in itens if i["completo"])
    pendentes = total - completos
    criticos = sum(1 for i in itens if not i["completo"] and 0 <= i["dias"] <= 3)
    sem_monitor = sum(1 for i in itens if "Monitor" in i["pendencias"])

    m1, m2, m3, m4, m5 = st.columns(5)
    resumo = [
        (m1, "📅 Eventos", total, "#7A5FFF"),
        (m2, "✅ Completos", completos, "#2ECC71"),
        (m3, "⚠️ Pendentes", pendentes, "#E67E22"),
        (m4, "🚨 Críticos (≤3d)", criticos, "#C0392B"),
        (m5, "🎭 Sem monitor", sem_monitor, "#9B59B6"),
    ]
    for col, titulo, valor, cor in resumo:
        col.markdown(
            f"""<div style="background:#f9f9f9;border-left:6px solid {cor};border-radius:12px;
                 padding:14px;text-align:center;box-shadow:2px 2px 10px rgba(0,0,0,.08);">
                 <div style="font-size:.85em;color:#555;">{titulo}</div>
                 <div style="font-size:1.4em;font-weight:800;">{valor}</div></div>""",
            unsafe_allow_html=True
        )

    st.divider()

    # ==========================================================
    # 🔔 CENTRAL DE ALERTAS
    # ==========================================================
    alertas = [i for i in itens if i["alerta_ativo"]]
    novos = [i for i in alertas if not i["avisado"]]

    if alertas:
        st.markdown("### 🔔 Central de Alertas")
        if novos:
            st.error(f"🚨 **{len(novos)} pendência(s) não avisada(s)** no grupo — "
                     f"marcos atingidos: "
                     f"{', '.join(sorted({str(i['marco']) + 'd' for i in novos}))}")
        else:
            st.success("✅ Todas as pendências atuais já foram avisadas no grupo.")

        texto_grupo = msg_resumo_pendencias(itens)

        ca, cb = st.columns([1, 1])
        with ca:
            if LINK_GRUPO_WHATSAPP:
                st.link_button("💬 Abrir grupo do WhatsApp", LINK_GRUPO_WHATSAPP,
                               use_container_width=True)
            else:
                st.caption("Configure `LINK_GRUPO_WHATSAPP` no topo de escala.py "
                           "para abrir o grupo direto.")
        with cb:
            if novos and st.button("✅ Marcar alertas como enviados",
                                   use_container_width=True):
                for i in novos:
                    registrar_aviso(i["reserva_id"], i["marco"])
                st.success(f"{len(novos)} aviso(s) registrado(s).")
                st.rerun()

        with st.expander("📋 Mensagem pronta para o grupo", expanded=bool(novos)):
            st.text_area("Copie e cole no grupo:", texto_grupo, height=300,
                         key="es_msg_grupo")
            st.caption("O WhatsApp não permite envio automático para grupos por link. "
                       "Copie o texto e cole no grupo — ou use o envio individual abaixo.")

        # Aviso individual (wa.me funciona para pessoa, não para grupo)
        tels = {k: v for k, v in RESPONSAVEIS.items() if _tel_limpo(v)}
        if tels:
            st.markdown("**Ou avise individualmente:**")
            cols = st.columns(len(tels))
            for col, (nome, tel) in zip(cols, tels.items()):
                col.link_button(f"💬 {nome}", url_whatsapp(tel, texto_grupo),
                                use_container_width=True)
        st.divider()

    # ==========================================================
    # ABAS
    # ==========================================================
    aba_pend, aba_todos, aba_hist = st.tabs(
        ["⚠️ Pendentes", "📅 Todos os eventos", "📜 Histórico de avisos"]
    )

    def _render_evento(item: dict, prefixo: str):
        cor, icone = _cor_urgencia(item["dias"], item["completo"])
        rid = item["reserva_id"]

        cabecalho = (
            f"<div class='es-card' style='border-left-color:{cor};'>"
            f"<span class='es-titulo'>{icone} {item['data'].strftime('%d/%m/%Y')} "
            f"— {_rotulo_prazo(item['dias'])}</span><br>"
            f"<span class='es-cli'>{item['cliente']}</span><br>"
        )
        if item["brinquedos"]:
            cabecalho += f"🎠 {item['brinquedos']}<br>"
        if item["inicio_festa"]:
            cabecalho += f"🎉 Festa: {item['inicio_festa']} às {item['fim_festa']}<br>"
        cabecalho += (f"🚚 Entrega {item['horario_entrega']} · "
                      f"Retirada {item['horario_retirada']}<br>")

        if item["completo"]:
            cabecalho += "<div class='es-ok'>✅ Escala completa</div>"
        else:
            cabecalho += (f"<div class='es-pend'>❌ Falta: "
                          f"{', '.join(item['pendencias'])}</div>")
            if item["marco"]:
                estado = "já avisado" if item["avisado"] else "AVISAR NO GRUPO"
                cabecalho += f"<br><small>🔔 Marco de {item['marco']} dias — {estado}</small>"
        cabecalho += "</div>"
        st.markdown(cabecalho, unsafe_allow_html=True)

        # ---- Atribuição por função ----
        cols = st.columns(len(FUNCOES))
        for col, funcao in zip(cols, FUNCOES):
            with col:
                atual = item["atribuicoes"].get(funcao, "")
                icone_f = ("🚚" if funcao == "Entrega"
                           else "🎭" if funcao == "Monitor" else "📦")

                # Lista = cadastrados + avulsos já usados antes + o atual
                opcoes = [OPCAO_VAZIA] + nomes_equipe
                for avulso in nomes_avulsos:
                    if avulso not in opcoes:
                        opcoes.append(avulso)
                if atual and atual not in opcoes:
                    opcoes.append(atual)
                opcoes.append(OPCAO_MANUAL)

                idx = opcoes.index(atual) if atual in opcoes else 0
                escolha = st.selectbox(
                    f"{icone_f} {funcao}", opcoes, index=idx,
                    key=f"{prefixo}_sel_{rid}_{funcao}"
                )

                # ---- Digitação manual ----
                if escolha == OPCAO_MANUAL:
                    novo_nome = st.text_input(
                        "Nome do responsável",
                        key=f"{prefixo}_manual_{rid}_{funcao}",
                        placeholder="Ex.: Aline (monitora da Vila)",
                        label_visibility="collapsed",
                    )
                    c_ok, c_ca = st.columns(2)
                    if c_ok.button("💾", key=f"{prefixo}_mok_{rid}_{funcao}",
                                   use_container_width=True,
                                   help="Salvar este nome"):
                        nome = _s(novo_nome)
                        if not nome:
                            st.warning("Digite um nome.")
                        else:
                            salvar_atribuicao(rid, item["data"], funcao, nome)
                            novas = dict(item["atribuicoes"])
                            novas[funcao] = nome
                            if not pendencias_do_evento(novas):
                                limpar_avisos_evento(rid)
                            st.rerun()
                    if c_ca.button("✖️", key=f"{prefixo}_mca_{rid}_{funcao}",
                                   use_container_width=True, help="Cancelar"):
                        st.rerun()
                    st.caption("Nome avulso — fica disponível nos próximos eventos.")

                # ---- Seleção normal ----
                elif escolha != (atual or OPCAO_VAZIA):
                    if escolha == OPCAO_VAZIA:
                        limpar_atribuicao(rid, funcao)
                    else:
                        salvar_atribuicao(rid, item["data"], funcao, escolha)
                        novas = dict(item["atribuicoes"])
                        novas[funcao] = escolha
                        if not pendencias_do_evento(novas):
                            limpar_avisos_evento(rid)
                    st.rerun()

                # Marca visualmente quem não é do cadastro
                elif atual and atual not in nomes_equipe:
                    st.caption("✏️ avulso")

        # ---- Ações do evento ----
        a1, a2 = st.columns(2)
        if not item["completo"]:
            with a1.popover("💬 Avisar só deste evento", use_container_width=True):
                st.text_area("Mensagem:", msg_pendencia_evento(item), height=220,
                             key=f"{prefixo}_msg_{rid}")
                if LINK_GRUPO_WHATSAPP:
                    st.link_button("Abrir grupo", LINK_GRUPO_WHATSAPP,
                                   use_container_width=True)
                if item["marco"] and not item["avisado"]:
                    if st.button("✅ Marcar como avisado", key=f"{prefixo}_av_{rid}",
                                 use_container_width=True):
                        registrar_aviso(rid, item["marco"])
                        st.rerun()
        else:
            with a1.popover("📋 Escala confirmada", use_container_width=True):
                st.text_area("Mensagem:", msg_escala_confirmada(item), height=220,
                             key=f"{prefixo}_conf_{rid}")

        if a2.button("🧹 Limpar escala", key=f"{prefixo}_lim_{rid}",
                     use_container_width=True):
            for f in FUNCOES:
                limpar_atribuicao(rid, f)
            limpar_avisos_evento(rid)
            st.rerun()

        st.divider()

    # ---------- ABA PENDENTES ----------
    with aba_pend:
        lista = [i for i in itens if not i["completo"] and i["dias"] >= 0]
        lista.sort(key=lambda x: x["dias"])
        if not lista:
            st.success("🎉 Nenhuma pendência! Todos os eventos futuros estão com "
                       "entrega, monitor e retirada definidos.")
        else:
            st.caption(f"{len(lista)} evento(s) aguardando definição — "
                       "ordenados por urgência.")
            for i in lista:
                _render_evento(i, "pend")

    # ---------- ABA TODOS ----------
    with aba_todos:
        f1, f2 = st.columns(2)
        filtro_status = f1.radio("Mostrar:", ["Todos", "Só completos", "Só pendentes"],
                                 horizontal=True, key="es_filtro_status")
        janela = f2.selectbox("Período:", ["Próximos 15 dias", "Próximos 30 dias",
                                           "Próximos 60 dias"],
                              index=1, key="es_filtro_janela")
        limite = {"Próximos 15 dias": 15, "Próximos 30 dias": 30,
                  "Próximos 60 dias": 60}[janela]

        lista = [i for i in itens if 0 <= i["dias"] <= limite]
        if filtro_status == "Só completos":
            lista = [i for i in lista if i["completo"]]
        elif filtro_status == "Só pendentes":
            lista = [i for i in lista if not i["completo"]]

        if not lista:
            st.info("Nenhum evento com esses filtros.")
        else:
            for i in sorted(lista, key=lambda x: x["dias"]):
                _render_evento(i, "todos")

    # ---------- ABA HISTÓRICO ----------
    with aba_hist:
        st.subheader("📜 Avisos já enviados")
        if df_avisos.empty:
            st.info("Nenhum aviso registrado ainda.")
        else:
            mapa = {str(i["reserva_id"]): i for i in itens}
            linhas = []
            for _, a in df_avisos.iterrows():
                ev = mapa.get(str(a.get("reserva_id")))
                linhas.append({
                    "Evento": ev["cliente"] if ev else f"Reserva {a.get('reserva_id')}",
                    "Data do evento": ev["data"].strftime("%d/%m/%Y") if ev else "-",
                    "Marco": f"{_s(a.get('marco_dias'))} dias antes",
                    "Enviado em": _s(a.get("enviado_em"))[:16],
                    "Canal": _s(a.get("canal"), "WhatsApp"),
                })
            st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("##### ⚙️ Como funcionam os alertas")
        st.markdown(f"""
- Os marcos são **{', '.join(f'{m} dias' for m in MARCOS_ALERTA)}** antes do evento.
- Um evento só entra em alerta se faltar **{', '.join(FUNCOES_CRITICAS)}**.
- Assim que a última função é preenchida, o evento **sai da lista** e o histórico
  de avisos dele é apagado (se algo mudar depois, o alerta volta).
- "Marcar como enviado" evita que o mesmo marco apareça de novo como novidade.
        """)


# ==============================================================
# COMO INTEGRAR NO app.py — APENAS 3 LINHAS
# ==============================================================
#   from escala import pagina_escala
#   "Escala": ("👷 Escala de Equipe", "escala"),
#   elif menu == "Escala":
#       pagina_escala()
# ==============================================================
