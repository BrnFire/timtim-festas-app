# ==============================================================
# MÓDULO ROTEIRO DO DIA – TimTim Festas
# Arquivo independente. Não altera nenhum outro módulo do app.
#
# INSTALAÇÃO (3 passos):
#   1) Salve este arquivo como  roteiro.py  na mesma pasta do app.py
#   2) Rode o SQL do arquivo roteiro_supabase.sql no Supabase
#   3) No app.py, adicione as 3 linhas indicadas no final deste arquivo
# ==============================================================

import re
import math
import unicodedata
from datetime import datetime, date, time as dtime, timedelta
from urllib.parse import quote_plus

import requests
import pandas as pd
import streamlit as st

from banco import carregar_dados, inserir_um, atualizar_por_filtro

# --------------------------------------------------------------
# CONFIGURAÇÕES (ajuste conforme sua operação)
# --------------------------------------------------------------
CEP_BASE = "09060-390"              # ponto de partida/retorno
ENDERECO_BASE = "09060-390, Santo André, SP"

CONSUMO_KML = 8.0                   # km por litro (Kombi 1.4 Flex)
PRECO_COMBUSTIVEL = 6.20            # R$ por litro
MAX_WAYPOINTS_MAPS = 9              # limite do Google Maps por link

COLS_ROTEIRO = ["id_parada", "reserva_id", "tipo", "data", "concluida", "atualizado_em"]

COLS_RESERVAS = [
    "id", "cliente", "brinquedos", "data",
    "horario_entrega", "horario_retirada",
    "inicio_festa", "fim_festa",
    "valor_total", "sinal", "falta", "status"
]

COLS_CLIENTES = [
    "nome", "telefone", "logradouro", "numero",
    "complemento", "bairro", "cidade", "cep"
]

STATUS_IGNORADOS = {"cancelada", "cancelado", "recusada", "recusado"}


# ==============================================================
# HELPERS BÁSICOS
# ==============================================================
def _s(v, padrao=""):
    """String segura."""
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


def _hora(v, padrao="00:00"):
    """Normaliza '8:00', '08:00:00', datetime -> '08:00'."""
    txt = _s(v)
    if not txt:
        return padrao
    m = re.match(r"(\d{1,2})[:h]?(\d{2})?", txt)
    if not m:
        return padrao
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    if h > 23 or mi > 59:
        return padrao
    return f"{h:02d}:{mi:02d}"


def _hora_ord(v):
    """Hora como número para ordenar (08:30 -> 830)."""
    h, m = _hora(v).split(":")
    return int(h) * 60 + int(m)


def _cep_limpo(v):
    return re.sub(r"\D", "", _s(v))[:8]


def _tel_limpo(v):
    return re.sub(r"\D", "", _s(v))


# ==============================================================
# GEOLOCALIZAÇÃO (cache de 24h — obrigatório p/ não estourar o Nominatim)
# ==============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def _coords_endereco(logradouro: str, numero: str, cidade: str, uf: str, cep: str):
    """
    Coordenadas do ENDEREÇO (não só da cidade).
    Diferença essencial em relação ao cálculo de frete: dentro do ABC,
    buscar pela cidade daria distância zero entre paradas.
    Tenta: rua+numero+cidade -> rua+cidade -> CEP -> cidade.
    """
    tentativas = []
    if logradouro and cidade:
        if numero:
            tentativas.append(f"{logradouro}, {numero}, {cidade}, {uf}, Brazil")
        tentativas.append(f"{logradouro}, {cidade}, {uf}, Brazil")
    if cep:
        tentativas.append(f"{cep}, Brazil")
    if cidade:
        tentativas.append(f"{cidade}, {uf}, Brazil")

    for q in tentativas:
        try:
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": "TimTimFestas/1.0"},
                timeout=5,
            )
            if r.status_code == 200:
                d = r.json()
                if d:
                    return float(d[0]["lat"]), float(d[0]["lon"])
        except Exception:
            continue
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def _dados_cep(cep: str):
    """ViaCEP -> dict com logradouro/bairro/cidade/uf."""
    cep = _cep_limpo(cep)
    if len(cep) != 8:
        return {}
    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if "erro" not in d:
                return {
                    "logradouro": d.get("logradouro", ""),
                    "bairro": d.get("bairro", ""),
                    "cidade": d.get("localidade", ""),
                    "uf": d.get("uf", ""),
                }
    except Exception:
        pass
    return {}


def _haversine(c1, c2):
    """Distância em km entre dois pares (lat, lon)."""
    if not c1 or not c2:
        return None
    lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
    lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def _km_rodado(km_reta):
    """Ajuste rota real x linha reta (fator ~1.35 em área urbana)."""
    return round(km_reta * 1.35, 1) if km_reta else 0.0


# ==============================================================
# MONTAGEM DAS PARADAS
# ==============================================================
def _endereco_texto(cli: dict) -> str:
    partes = []
    log = _s(cli.get("logradouro"))
    num = _s(cli.get("numero"))
    if log:
        partes.append(f"{log}, {num}" if num else log)
    for k in ["complemento", "bairro", "cidade"]:
        if _s(cli.get(k)):
            partes.append(_s(cli.get(k)))
    cep = _s(cli.get("cep"))
    if cep:
        partes.append(f"CEP {cep}")
    return " - ".join(partes) if partes else "Endereço não cadastrado"


def _endereco_maps(cli: dict) -> str:
    """String compacta e precisa para a URL do Maps."""
    log = _s(cli.get("logradouro"))
    num = _s(cli.get("numero"))
    cid = _s(cli.get("cidade"))
    cep = _s(cli.get("cep"))
    if log and cid:
        base = f"{log}, {num}" if num else log
        return f"{base}, {cid}, SP" + (f", {cep}" if cep else "")
    return cep or cid or ""


def montar_paradas(data_alvo: date, reservas: pd.DataFrame, clientes: pd.DataFrame) -> list:
    """
    Desdobra reservas em PARADAS.
    Uma reserva vira até 2 paradas independentes (entrega e retirada),
    que podem cair em dias diferentes.
    """
    if reservas is None or reservas.empty:
        return []

    mapa_cli = {}
    if clientes is not None and not clientes.empty:
        for _, c in clientes.iterrows():
            mapa_cli[_s(c.get("nome")).lower()] = c.to_dict()

    paradas = []
    for _, r in reservas.iterrows():
        if _s(r.get("status")).lower() in STATUS_IGNORADOS:
            continue

        d_reserva = pd.to_datetime(r.get("data"), errors="coerce")
        if pd.isna(d_reserva):
            continue
        d_reserva = d_reserva.date()

        h_ent = _hora(r.get("horario_entrega"), "08:00")
        h_ret = _hora(r.get("horario_retirada"), "18:00")

        # Retirada anterior à entrega -> retirada no dia seguinte (D+1)
        d_retirada = d_reserva + timedelta(days=1) if _hora_ord(h_ret) <= _hora_ord(h_ent) else d_reserva

        cli = mapa_cli.get(_s(r.get("cliente")).lower(), {})

        candidatas = [
            ("Entrega", d_reserva, h_ent),
            ("Retirada", d_retirada, h_ret),
        ]
        for tipo, d_parada, hora in candidatas:
            if d_parada != data_alvo:
                continue
            paradas.append({
                "reserva_id": r.get("id"),
                "tipo": tipo,
                "hora": hora,
                "cliente": _s(r.get("cliente"), "(sem cliente)"),
                "telefone": _s(cli.get("telefone")),
                "endereco": _endereco_texto(cli),
                "endereco_maps": _endereco_maps(cli),
                "cep": _s(cli.get("cep")),
                "logradouro": _s(cli.get("logradouro")),
                "numero": _s(cli.get("numero")),
                "cidade": _s(cli.get("cidade")),
                "brinquedos": _s(r.get("brinquedos")),
                "falta": _f(r.get("falta")) if tipo == "Entrega" else 0.0,
                "inicio_festa": _hora(r.get("inicio_festa"), ""),
                "fim_festa": _hora(r.get("fim_festa"), ""),
                "data_festa": d_reserva,
            })

    # Ordena por HORÁRIO (compromisso com o cliente manda, não a distância)
    paradas.sort(key=lambda p: (_hora_ord(p["hora"]), p["tipo"]))
    for i, p in enumerate(paradas, start=1):
        p["ordem"] = i
    return paradas


def calcular_distancias(paradas: list) -> tuple:
    """
    Distância de cada parada em relação à ANTERIOR (não à base).
    Retorna (paradas_atualizadas, km_total_estimado).
    """
    if not paradas:
        return paradas, 0.0

    base_info = _dados_cep(CEP_BASE)
    coord_base = _coords_endereco(
        base_info.get("logradouro", ""), "",
        base_info.get("cidade", "Santo André"),
        base_info.get("uf", "SP"), CEP_BASE
    )

    anterior = coord_base
    km_total = 0.0

    for p in paradas:
        cidade = p["cidade"]
        uf = "SP"
        if not cidade and p["cep"]:
            info = _dados_cep(p["cep"])
            cidade = info.get("cidade", "")
            uf = info.get("uf", "SP")
            if not p["logradouro"]:
                p["logradouro"] = info.get("logradouro", "")

        coord = _coords_endereco(p["logradouro"], p["numero"], cidade, uf, p["cep"])
        p["_coord"] = coord

        km = _km_rodado(_haversine(anterior, coord))
        p["km_desde_anterior"] = km
        km_total += km or 0.0

        if coord:
            anterior = coord

    # retorno à base
    km_volta = _km_rodado(_haversine(anterior, coord_base))
    km_total += km_volta or 0.0

    return paradas, round(km_total, 1)


def detectar_ineficiencia(paradas: list) -> list:
    """
    Sinaliza quando a ordem por horário gera desvio grande,
    mas NÃO reordena (horário é compromisso com o cliente).
    """
    avisos = []
    if len(paradas) < 3:
        return avisos
    for i in range(1, len(paradas) - 1):
        atual = paradas[i]
        km_atual = atual.get("km_desde_anterior") or 0
        if km_atual < 8:
            continue
        anterior = paradas[i - 1]
        for j in range(i + 1, len(paradas)):
            outra = paradas[j]
            d = _haversine(anterior.get("_coord"), outra.get("_coord"))
            if d is not None and _km_rodado(d) < km_atual * 0.4:
                avisos.append(
                    f"Parada {atual['ordem']} ({atual['cliente']}) fica a {km_atual} km da anterior, "
                    f"mas a parada {outra['ordem']} ({outra['cliente']}) está a apenas "
                    f"{_km_rodado(d)} km — avalie trocar se os horários permitirem."
                )
                break
    return avisos


# ==============================================================
# LINKS EXTERNOS
# ==============================================================
def url_navegar(destino: str) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(destino)}"


def urls_rota_completa(paradas: list) -> list:
    """
    Gera 1+ links. O Google aceita ~9 waypoints intermediários por URL,
    então dias muito cheios são quebrados em blocos.
    """
    enderecos = [p["endereco_maps"] for p in paradas if p["endereco_maps"]]
    if not enderecos:
        return []

    links = []
    tamanho = MAX_WAYPOINTS_MAPS + 1
    for ini in range(0, len(enderecos), tamanho):
        bloco = enderecos[ini:ini + tamanho]
        origem = ENDERECO_BASE if ini == 0 else enderecos[ini - 1]
        destino = bloco[-1] if ini + tamanho >= len(enderecos) else bloco[-1]
        meio = bloco[:-1]

        url = (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={quote_plus(origem)}"
            f"&destination={quote_plus(destino)}"
            "&travelmode=driving"
        )
        if meio:
            url += "&waypoints=" + quote_plus("|".join(meio))
        links.append(url)
    return links


def url_whatsapp(telefone: str, mensagem: str) -> str:
    num = _tel_limpo(telefone)
    if not num:
        return ""
    if not num.startswith("55"):
        num = "55" + num
    return f"https://wa.me/{num}?text={quote_plus(mensagem)}"


def texto_roteiro(paradas: list, data_alvo: date, km_total: float) -> str:
    linhas = [f"🚚 ROTEIRO {data_alvo.strftime('%d/%m/%Y')} — {len(paradas)} parada(s)", ""]
    for p in paradas:
        icone = "🟢" if p["tipo"] == "Entrega" else "🔴"
        linhas.append(f"{p['ordem']}. {icone} {p['hora']} — {p['tipo'].upper()}")
        linhas.append(f"👤 {p['cliente']}")
        linhas.append(f"📍 {p['endereco']}")
        if p["brinquedos"]:
            linhas.append(f"🎠 {p['brinquedos']}")
        if p["falta"] > 0:
            linhas.append(f"💰 RECEBER: R$ {p['falta']:,.2f}")
        if p["km_desde_anterior"]:
            linhas.append(f"🛣️ {p['km_desde_anterior']} km da parada anterior")
        linhas.append("────────────")
    linhas.append(f"📏 Total estimado: {km_total} km (ida e volta)")
    return "\n".join(linhas)


# ==============================================================
# PERSISTÊNCIA DO STATUS DAS PARADAS
# ==============================================================
def _chave_parada(p) -> str:
    return f"{p['reserva_id']}_{p['tipo']}"


def carregar_status(data_alvo: date) -> dict:
    try:
        df = carregar_dados("roteiro_status", COLS_ROTEIRO)
        if df is None or df.empty:
            return {}
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
        df = df[df["data"] == data_alvo]
        return {
            f"{_s(r['reserva_id'])}_{_s(r['tipo'])}": _s(r["concluida"]).lower() in {"true", "sim", "1", "t"}
            for _, r in df.iterrows()
        }
    except Exception:
        return {}


def salvar_status(reserva_id, tipo: str, data_alvo: date, concluida: bool):
    registro = {
        "reserva_id": int(reserva_id) if pd.notna(reserva_id) else None,
        "tipo": tipo,
        "data": str(data_alvo),
        "concluida": bool(concluida),
        "atualizado_em": str(datetime.now()),
    }
    filtro = {"reserva_id": registro["reserva_id"], "tipo": tipo, "data": str(data_alvo)}
    try:
        atualizar_por_filtro("roteiro_status", registro, filtro)
    except Exception:
        pass
    try:
        inserir_um("roteiro_status", registro)
    except Exception:
        pass


# ==============================================================
# PÁGINA
# ==============================================================
def pagina_roteiro():
    st.markdown("""
        <style>
        .rt-card{border-radius:14px;padding:14px 18px;margin-bottom:12px;
                 box-shadow:0 2px 8px rgba(0,0,0,.08);border-left:7px solid #ccc;}
        .rt-entrega{background:#E8F8F0;border-left-color:#2ECC71;}
        .rt-retirada{background:#FDEDEC;border-left-color:#E74C3C;}
        .rt-feito{background:#F2F2F2;border-left-color:#999;opacity:.6;}
        .rt-hora{font-size:1.3em;font-weight:800;color:#333;}
        .rt-cli{font-size:1.1em;font-weight:700;color:#7A5FFF;}
        .rt-receber{background:#FFF4B5;border:2px dashed #F1C40F;border-radius:8px;
                    padding:6px 12px;margin-top:8px;font-weight:700;color:#8A6D00;
                    display:inline-block;}
        </style>
    """, unsafe_allow_html=True)

    st.header("🚚 Roteiro do Dia")

    # ---------- Seletor de data ----------
    hoje = date.today()
    if "rt_data" not in st.session_state:
        st.session_state.rt_data = hoje

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        data_alvo = st.date_input("📅 Data do roteiro", value=st.session_state.rt_data,
                                  format="DD/MM/YYYY", key="rt_data_input")
        st.session_state.rt_data = data_alvo
    with c2:
        if st.button("Hoje", use_container_width=True):
            st.session_state.rt_data = hoje
            st.rerun()
    with c3:
        if st.button("Amanhã", use_container_width=True):
            st.session_state.rt_data = hoje + timedelta(days=1)
            st.rerun()

    # ---------- Dados ----------
    try:
        reservas = carregar_dados("reservas", COLS_RESERVAS)
        clientes = carregar_dados("clientes", COLS_CLIENTES)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    paradas = montar_paradas(data_alvo, reservas, clientes)

    if not paradas:
        st.info(f"Nenhuma entrega ou retirada em {data_alvo.strftime('%d/%m/%Y')}. Dia livre! 🎉")
        return

    with st.spinner("Calculando distâncias..."):
        paradas, km_total = calcular_distancias(paradas)

    status = carregar_status(data_alvo)
    for p in paradas:
        p["concluida"] = status.get(_chave_parada(p), False)

    # ---------- Cards de resumo ----------
    litros = km_total / CONSUMO_KML if CONSUMO_KML else 0
    combustivel = litros * PRECO_COMBUSTIVEL
    a_receber = sum(p["falta"] for p in paradas)
    feitas = sum(1 for p in paradas if p["concluida"])

    m1, m2, m3, m4 = st.columns(4)
    resumo = [
        (m1, "📍 Paradas", f"{feitas}/{len(paradas)}", "#7A5FFF"),
        (m2, "🛣️ Distância", f"{km_total} km", "#3498DB"),
        (m3, "⛽ Combustível", f"R$ {combustivel:,.2f}", "#E67E22"),
        (m4, "💰 A receber", f"R$ {a_receber:,.2f}", "#2ECC71"),
    ]
    for col, titulo, valor, cor in resumo:
        col.markdown(
            f"""<div style="background:#f9f9f9;border-left:6px solid {cor};border-radius:12px;
                 padding:14px;text-align:center;box-shadow:2px 2px 10px rgba(0,0,0,.08);">
                 <div style="font-size:.9em;color:#555;">{titulo}</div>
                 <div style="font-size:1.4em;font-weight:800;">{valor}</div></div>""",
            unsafe_allow_html=True
        )

    # ---------- Progresso ----------
    prog = (feitas / len(paradas) * 100) if paradas else 0
    st.markdown(
        f"""<div style="margin:16px 0 6px 0;background:#eee;border-radius:8px;overflow:hidden;">
             <div style="height:16px;width:{prog:.0f}%;background:#2ECC71;
                  transition:width .6s ease;"></div></div>
             <p style="color:#666;font-size:13px;">🎯 {prog:.0f}% do roteiro concluído</p>""",
        unsafe_allow_html=True
    )

    # ---------- Rota completa ----------
    links = urls_rota_completa(paradas)
    if links:
        st.markdown("#### 🗺️ Abrir rota no Google Maps")
        cols = st.columns(min(len(links), 3))
        for i, link in enumerate(links):
            rotulo = "🗺️ Abrir rota completa" if len(links) == 1 else f"🗺️ Rota parte {i+1}"
            cols[i % len(cols)].link_button(rotulo, link, use_container_width=True)
        if len(links) > 1:
            st.caption("O Google Maps aceita até 9 paradas intermediárias por link — "
                       "o roteiro foi dividido em blocos.")

    avisos = detectar_ineficiencia(paradas)
    if avisos:
        with st.expander(f"⚠️ {len(avisos)} possível otimização de rota"):
            for a in avisos:
                st.write(f"• {a}")
            st.caption("A ordem segue o horário combinado com o cliente. "
                       "Só troque se conseguir remarcar.")

    st.divider()

    # ---------- Lista de paradas ----------
    for p in paradas:
        icone = "🟢" if p["tipo"] == "Entrega" else "🔴"
        classe = "rt-feito" if p["concluida"] else (
            "rt-entrega" if p["tipo"] == "Entrega" else "rt-retirada"
        )

        bloco = [
            f"<div class='rt-card {classe}'>",
            f"<span class='rt-hora'>{p['ordem']}. {icone} {p['hora']}</span>",
            f"&nbsp;<b>{p['tipo'].upper()}</b><br>",
            f"<span class='rt-cli'>{p['cliente']}</span><br>",
            f"📍 {p['endereco']}<br>",
        ]
        if p["brinquedos"]:
            bloco.append(f"🎠 {p['brinquedos']}<br>")
        if p["inicio_festa"] and p["fim_festa"]:
            bloco.append(f"🎉 Festa: {p['inicio_festa']} às {p['fim_festa']}<br>")
        if p["tipo"] == "Retirada" and p["data_festa"] != data_alvo:
            bloco.append(f"<i>↩️ Festa do dia {p['data_festa'].strftime('%d/%m')}</i><br>")
        if p["km_desde_anterior"]:
            origem = "da base" if p["ordem"] == 1 else "da parada anterior"
            bloco.append(f"🛣️ {p['km_desde_anterior']} km {origem}<br>")
        if p["falta"] > 0:
            bloco.append(f"<div class='rt-receber'>💰 RECEBER R$ {p['falta']:,.2f}</div>")
        bloco.append("</div>")
        st.markdown("".join(bloco), unsafe_allow_html=True)

        b1, b2, b3 = st.columns([1, 1, 1])

        if p["endereco_maps"]:
            b1.link_button("📍 Navegar", url_navegar(p["endereco_maps"]),
                           use_container_width=True)

        if p["telefone"]:
            if p["tipo"] == "Entrega":
                msg = (f"Olá {p['cliente']}! Aqui é da TimTim Festas 🎈 "
                       f"Estamos a caminho para a entrega, chegamos em aproximadamente 20 minutos.")
            else:
                msg = (f"Olá {p['cliente']}! Aqui é da TimTim Festas 🎈 "
                       f"Estamos a caminho para a retirada dos itens, chegamos em breve.")
            b2.link_button("💬 Avisar", url_whatsapp(p["telefone"], msg),
                           use_container_width=True)

        rotulo = "↩️ Reabrir" if p["concluida"] else "✅ Concluir"
        if b3.button(rotulo, key=f"rt_ok_{_chave_parada(p)}", use_container_width=True):
            salvar_status(p["reserva_id"], p["tipo"], data_alvo, not p["concluida"])
            st.rerun()

    # ---------- Exportar ----------
    st.divider()
    with st.expander("📋 Copiar roteiro em texto (enviar ao monitor)"):
        st.text_area("Roteiro:", texto_roteiro(paradas, data_alvo, km_total),
                     height=400, key="rt_texto")

    with st.expander("⚙️ Parâmetros usados no cálculo"):
        st.write(f"**Base de origem:** {ENDERECO_BASE}")
        st.write(f"**Consumo:** {CONSUMO_KML} km/l • **Combustível:** R$ {PRECO_COMBUSTIVEL}/l")
        st.caption("Distâncias são estimativas em linha reta com fator urbano de 1,35x. "
                   "Edite as constantes no topo de roteiro.py para ajustar.")


# ==============================================================
# COMO INTEGRAR NO app.py — ADICIONE APENAS ESTAS 3 LINHAS
# ==============================================================
#
# 1) No topo do app.py, junto dos outros imports:
#
#       from roteiro import pagina_roteiro
#
# 2) No dicionário menu_opcoes, logo abaixo de "Agenda":
#
#       "Roteiro": ("🚚 Roteiro do Dia", "roteiro"),
#
# 3) Na navegação, junto dos outros elif:
#
#       elif menu == "Roteiro":
#           pagina_roteiro()
#
# Nada mais no app.py precisa mudar.
# ==============================================================
