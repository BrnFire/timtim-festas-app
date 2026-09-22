# ==============================================================
# MÓDULO ROTEIRO DO DIA – TimTim Festas  (v2 — com simulação de horários)
# Arquivo independente. Não altera nenhum outro módulo do app.
#
# NOVIDADE v2:
#   - Tempo de montagem/desmontagem por parada
#   - Tempo de deslocamento estimado entre paradas
#   - Linha do tempo real (chegada / saída) encadeada
#   - Alerta de atraso ANTES de acontecer
#   - Sugestão de horário de saída da base
#
# INSTALAÇÃO:
#   1) Salve como  roteiro.py  na mesma pasta do app.py
#   2) Rode o SQL do roteiro_supabase.sql no Supabase
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
CEP_BASE = "09060-390"
ENDERECO_BASE = "09060-390, Santo André, SP"

CONSUMO_KML = 8.0
PRECO_COMBUSTIVEL = 6.20
MAX_WAYPOINTS_MAPS = 9

# ---------- ⏱️ TEMPOS OPERACIONAIS (NOVO na v2) ----------
MIN_MONTAGEM_PADRAO = 90        # 1h30 — tempo médio de montagem na entrega
MIN_DESMONTAGEM_PADRAO = 45     # retirada costuma ser mais rápida
MIN_POR_BRINQUEDO_EXTRA = 10    # a cada brinquedo além do 1º, soma este tempo
MIN_MONTESSORI_EXTRA = 20       # kit montessori (tatames) leva mais tempo

VELOCIDADE_MEDIA_KMH = 25.0     # trânsito urbano ABC/SP
MIN_FOLGA_SEGURANCA = 10        # margem entre sair de um cliente e chegar no outro
HORA_SAIDA_MINIMA = "06:00"     # não sugere sair da base antes disso

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

COLS_BRINQUEDOS = ["nome", "categoria"]

STATUS_IGNORADOS = {"cancelada", "cancelado", "recusada", "recusado"}


# ==============================================================
# HELPERS BÁSICOS
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


def _hora(v, padrao="00:00"):
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


def _min_do_dia(v):
    """'08:30' -> 510 minutos."""
    h, m = _hora(v).split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutos):
    """510 -> '08:30'. Aceita valores fora de 0-1439."""
    minutos = int(round(minutos))
    dia_seguinte = ""
    if minutos < 0:
        minutos += 1440
        dia_seguinte = " (D-1)"
    if minutos >= 1440:
        minutos -= 1440
        dia_seguinte = " (D+1)"
    return f"{minutos // 60:02d}:{minutos % 60:02d}{dia_seguinte}"


def _dur(minutos):
    """95 -> '1h35'. 45 -> '45min'."""
    minutos = int(round(abs(minutos)))
    if minutos < 60:
        return f"{minutos}min"
    h, m = divmod(minutos, 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


def _cep_limpo(v):
    return re.sub(r"\D", "", _s(v))[:8]


def _tel_limpo(v):
    return re.sub(r"\D", "", _s(v))


def _norm(txt):
    txt = unicodedata.normalize("NFKD", _s(txt).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", txt).strip()


# ==============================================================
# GEOLOCALIZAÇÃO (cache 24h)
# ==============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def _coords_endereco(logradouro: str, numero: str, cidade: str, uf: str, cep: str):
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
    if not c1 or not c2:
        return None
    lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
    lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def _km_rodado(km_reta):
    return round(km_reta * 1.35, 1) if km_reta else 0.0


def minutos_deslocamento(km):
    """Km -> minutos de trajeto, com piso de 5 min (estacionar, subir, etc.)."""
    if not km:
        return 0
    return max(5, int(round((km / VELOCIDADE_MEDIA_KMH) * 60)))


# ==============================================================
# ⏱️ TEMPO DE SERVIÇO POR PARADA (NOVO na v2)
# ==============================================================
def tempo_servico(parada: dict, cat_map: dict) -> int:
    """
    Estima o tempo NO CLIENTE.
    Base (montagem 90min / desmontagem 45min)
      + 10min por brinquedo extra
      + 20min se houver item montessori (tatames dão trabalho)
    """
    itens = [b.strip() for b in _s(parada.get("brinquedos")).split(",") if b.strip()]
    qtd = max(1, len(itens))

    if parada["tipo"] == "Entrega":
        base = MIN_MONTAGEM_PADRAO
        extra_item = MIN_POR_BRINQUEDO_EXTRA
    else:
        base = MIN_DESMONTAGEM_PADRAO
        extra_item = max(5, MIN_POR_BRINQUEDO_EXTRA // 2)

    total = base + (qtd - 1) * extra_item

    tem_montessori = any(cat_map.get(_norm(i), "") == "montessori" for i in itens)
    if tem_montessori:
        total += MIN_MONTESSORI_EXTRA if parada["tipo"] == "Entrega" else MIN_MONTESSORI_EXTRA // 2

    return int(total)


def _carregar_categorias() -> dict:
    """Mapa nome_normalizado -> categoria, para detectar montessori."""
    try:
        df = carregar_dados("brinquedos", COLS_BRINQUEDOS)
        if df is None or df.empty:
            return {}
        return {_norm(r["nome"]): _norm(r.get("categoria")) for _, r in df.iterrows()}
    except Exception:
        return {}


# ==============================================================
# MONTAGEM DAS PARADAS
# ==============================================================
def _endereco_texto(cli: dict) -> str:
    partes = []
    log, num = _s(cli.get("logradouro")), _s(cli.get("numero"))
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
    log, num = _s(cli.get("logradouro")), _s(cli.get("numero"))
    cid, cep = _s(cli.get("cidade")), _s(cli.get("cep"))
    if log and cid:
        base = f"{log}, {num}" if num else log
        return f"{base}, {cid}, SP" + (f", {cep}" if cep else "")
    return cep or cid or ""


def montar_paradas(data_alvo: date, reservas: pd.DataFrame, clientes: pd.DataFrame) -> list:
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
        d_retirada = d_reserva + timedelta(days=1) if _min_do_dia(h_ret) <= _min_do_dia(h_ent) else d_reserva

        cli = mapa_cli.get(_s(r.get("cliente")).lower(), {})

        for tipo, d_parada, hora in [("Entrega", d_reserva, h_ent), ("Retirada", d_retirada, h_ret)]:
            if d_parada != data_alvo:
                continue
            paradas.append({
                "reserva_id": r.get("id"),
                "tipo": tipo,
                "hora": hora,                      # horário COMBINADO com o cliente
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

    paradas.sort(key=lambda p: (_min_do_dia(p["hora"]), p["tipo"]))
    for i, p in enumerate(paradas, start=1):
        p["ordem"] = i
    return paradas


def calcular_distancias(paradas: list) -> tuple:
    if not paradas:
        return paradas, 0.0, 0

    base_info = _dados_cep(CEP_BASE)
    coord_base = _coords_endereco(
        base_info.get("logradouro", ""), "",
        base_info.get("cidade", "Santo André"),
        base_info.get("uf", "SP"), CEP_BASE
    )

    anterior = coord_base
    km_total = 0.0

    for p in paradas:
        cidade, uf = p["cidade"], "SP"
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
        p["min_deslocamento"] = minutos_deslocamento(km)
        km_total += km or 0.0

        if coord:
            anterior = coord

    km_volta = _km_rodado(_haversine(anterior, coord_base))
    min_volta = minutos_deslocamento(km_volta)
    km_total += km_volta or 0.0

    return paradas, round(km_total, 1), min_volta


# ==============================================================
# ⏱️ SIMULAÇÃO DA LINHA DO TEMPO (CORAÇÃO DA v2)
# ==============================================================
def simular_agenda(paradas: list, cat_map: dict, min_volta: int) -> dict:
    """
    Encadeia a operação real do dia:
      chegada -> serviço -> deslocamento -> próxima chegada

    Regras:
      - A 1ª parada começa no horário combinado.
      - Da 2ª em diante, a chegada REAL é o maior valor entre:
          (a) horário combinado com o cliente, e
          (b) saída da parada anterior + deslocamento.
        Se (b) > (a), há ATRASO previsto.
      - Se (a) > (b), há OCIOSIDADE (tempo livre entre paradas).
    """
    if not paradas:
        return {}

    relogio = None
    atraso_acumulado = 0

    for i, p in enumerate(paradas):
        combinado = _min_do_dia(p["hora"])
        p["min_servico"] = tempo_servico(p, cat_map)

        if i == 0:
            chegada = combinado
            p["atraso"] = 0
            p["ocioso"] = 0
        else:
            chegada_possivel = relogio + p["min_deslocamento"]
            if chegada_possivel > combinado:
                chegada = chegada_possivel
                p["atraso"] = chegada_possivel - combinado
                p["ocioso"] = 0
            else:
                chegada = combinado
                p["atraso"] = 0
                p["ocioso"] = combinado - chegada_possivel

        atraso_acumulado = max(atraso_acumulado, p["atraso"])

        p["chegada_prevista"] = chegada
        p["saida_prevista"] = chegada + p["min_servico"]
        relogio = p["saida_prevista"]

        # Conflito com o início da festa (só faz sentido na entrega)
        p["conflito_festa"] = False
        if p["tipo"] == "Entrega" and p["inicio_festa"]:
            ini = _min_do_dia(p["inicio_festa"])
            if p["saida_prevista"] > ini:
                p["conflito_festa"] = True
                p["min_apos_inicio"] = p["saida_prevista"] - ini

    primeira = paradas[0]
    saida_base = primeira["chegada_prevista"] - primeira["min_deslocamento"]
    piso = _min_do_dia(HORA_SAIDA_MINIMA)

    return {
        "saida_base": max(saida_base, piso) if saida_base < piso else saida_base,
        "saida_base_calculada": saida_base,
        "saida_base_antecipada": saida_base < piso,
        "retorno_base": relogio + min_volta,
        "min_volta": min_volta,
        "total_servico": sum(p["min_servico"] for p in paradas),
        "total_deslocamento": sum(p["min_deslocamento"] for p in paradas) + min_volta,
        "total_ocioso": sum(p.get("ocioso", 0) for p in paradas),
        "maior_atraso": atraso_acumulado,
        "paradas_atrasadas": [p for p in paradas if p["atraso"] > 0],
        "conflitos_festa": [p for p in paradas if p.get("conflito_festa")],
    }


def sugerir_horario_viavel(parada: dict, anterior: dict) -> str:
    """Horário mínimo realista para esta parada, dada a anterior."""
    return _hhmm(anterior["saida_prevista"] + parada["min_deslocamento"] + MIN_FOLGA_SEGURANCA)


# ==============================================================
# LINKS EXTERNOS
# ==============================================================
def url_navegar(destino: str) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(destino)}"


def urls_rota_completa(paradas: list) -> list:
    enderecos = [p["endereco_maps"] for p in paradas if p["endereco_maps"]]
    if not enderecos:
        return []
    links, tamanho = [], MAX_WAYPOINTS_MAPS + 1
    for ini in range(0, len(enderecos), tamanho):
        bloco = enderecos[ini:ini + tamanho]
        origem = ENDERECO_BASE if ini == 0 else enderecos[ini - 1]
        destino, meio = bloco[-1], bloco[:-1]
        url = ("https://www.google.com/maps/dir/?api=1"
               f"&origin={quote_plus(origem)}"
               f"&destination={quote_plus(destino)}"
               "&travelmode=driving")
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


def texto_roteiro(paradas: list, data_alvo: date, km_total: float, agenda: dict) -> str:
    linhas = [
        f"🚚 ROTEIRO {data_alvo.strftime('%d/%m/%Y')} — {len(paradas)} parada(s)",
        f"🏁 Sair da base: {_hhmm(agenda['saida_base'])}",
        ""
    ]
    for p in paradas:
        icone = "🟢" if p["tipo"] == "Entrega" else "🔴"
        linhas.append(f"{p['ordem']}. {icone} {p['tipo'].upper()} — combinado {p['hora']}")
        linhas.append(f"⏱️ Chegada {_hhmm(p['chegada_prevista'])} → saída {_hhmm(p['saida_prevista'])} "
                      f"({_dur(p['min_servico'])} no local)")
        if p["atraso"] > 0:
            linhas.append(f"🚨 ATRASO PREVISTO: {_dur(p['atraso'])}")
        linhas.append(f"👤 {p['cliente']}")
        linhas.append(f"📍 {p['endereco']}")
        if p["brinquedos"]:
            linhas.append(f"🎠 {p['brinquedos']}")
        if p["falta"] > 0:
            linhas.append(f"💰 RECEBER: R$ {p['falta']:,.2f}")
        if p["km_desde_anterior"]:
            linhas.append(f"🛣️ {p['km_desde_anterior']} km / {_dur(p['min_deslocamento'])} de trajeto")
        linhas.append("────────────")
    linhas.append(f"🏠 Retorno à base: {_hhmm(agenda['retorno_base'])}")
    linhas.append(f"📏 Total: {km_total} km • {_dur(agenda['total_servico'])} de serviço "
                  f"• {_dur(agenda['total_deslocamento'])} de estrada")
    return "\n".join(linhas)


# ==============================================================
# PERSISTÊNCIA DO STATUS
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
        .rt-card{border-radius:14px;padding:14px 18px;margin-bottom:8px;
                 box-shadow:0 2px 8px rgba(0,0,0,.08);border-left:7px solid #ccc;}
        .rt-entrega{background:#E8F8F0;border-left-color:#2ECC71;}
        .rt-retirada{background:#FDEDEC;border-left-color:#E74C3C;}
        .rt-atraso{background:#FDEBD0;border-left-color:#E67E22;}
        .rt-feito{background:#F2F2F2;border-left-color:#999;opacity:.6;}
        .rt-hora{font-size:1.25em;font-weight:800;color:#333;}
        .rt-cli{font-size:1.1em;font-weight:700;color:#7A5FFF;}
        .rt-receber{background:#FFF4B5;border:2px dashed #F1C40F;border-radius:8px;
                    padding:6px 12px;margin-top:8px;font-weight:700;color:#8A6D00;
                    display:inline-block;}
        .rt-janela{background:rgba(255,255,255,.75);border-radius:8px;padding:8px 12px;
                   margin:8px 0;font-size:.95em;border:1px solid rgba(0,0,0,.08);}
        .rt-trajeto{text-align:center;color:#888;font-size:.9em;margin:2px 0 10px 0;}
        .rt-alerta{background:#FADBD8;border-left:5px solid #C0392B;border-radius:8px;
                   padding:8px 12px;margin-top:8px;font-weight:600;color:#922B21;}
        </style>
    """, unsafe_allow_html=True)

    st.header("🚚 Roteiro do Dia")

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

    with st.spinner("Calculando rota e horários..."):
        paradas, km_total, min_volta = calcular_distancias(paradas)
        cat_map = _carregar_categorias()
        agenda = simular_agenda(paradas, cat_map, min_volta)

    status = carregar_status(data_alvo)
    for p in paradas:
        p["concluida"] = status.get(_chave_parada(p), False)

    # ---------- Cards de resumo ----------
    litros = km_total / CONSUMO_KML if CONSUMO_KML else 0
    combustivel = litros * PRECO_COMBUSTIVEL
    a_receber = sum(p["falta"] for p in paradas)
    feitas = sum(1 for p in paradas if p["concluida"])
    jornada = agenda["retorno_base"] - agenda["saida_base"]

    m1, m2, m3, m4, m5 = st.columns(5)
    resumo = [
        (m1, "📍 Paradas", f"{feitas}/{len(paradas)}", "#7A5FFF"),
        (m2, "🕐 Jornada", _dur(jornada), "#16A085"),
        (m3, "🛣️ Distância", f"{km_total} km", "#3498DB"),
        (m4, "⛽ Combustível", f"R$ {combustivel:,.2f}", "#E67E22"),
        (m5, "💰 A receber", f"R$ {a_receber:,.2f}", "#2ECC71"),
    ]
    for col, titulo, valor, cor in resumo:
        col.markdown(
            f"""<div style="background:#f9f9f9;border-left:6px solid {cor};border-radius:12px;
                 padding:14px;text-align:center;box-shadow:2px 2px 10px rgba(0,0,0,.08);">
                 <div style="font-size:.85em;color:#555;">{titulo}</div>
                 <div style="font-size:1.3em;font-weight:800;">{valor}</div></div>""",
            unsafe_allow_html=True
        )

    # ---------- ⏱️ Plano de horários ----------
    st.markdown("### ⏱️ Plano do dia")
    p1, p2, p3 = st.columns(3)
    p1.metric("🏁 Sair da base", _hhmm(agenda["saida_base"]))
    p2.metric("🔧 Tempo montando", _dur(agenda["total_servico"]))
    p3.metric("🏠 Retorno previsto", _hhmm(agenda["retorno_base"]))

    if agenda["saida_base_antecipada"]:
        st.warning(
            f"⚠️ Para chegar às {paradas[0]['hora']} na 1ª parada seria preciso sair às "
            f"{_hhmm(agenda['saida_base_calculada'])}, antes do seu horário mínimo "
            f"({HORA_SAIDA_MINIMA}). Considere remarcar a primeira entrega."
        )

    # ---------- 🚨 Alertas de atraso ----------
    atrasadas = agenda["paradas_atrasadas"]
    if atrasadas:
        st.error(f"🚨 {len(atrasadas)} parada(s) com atraso previsto — maior atraso: "
                 f"{_dur(agenda['maior_atraso'])}")
        with st.expander("Ver detalhes e sugestões de horário", expanded=True):
            for p in atrasadas:
                ant = paradas[p["ordem"] - 2]
                st.markdown(
                    f"**Parada {p['ordem']} — {p['cliente']}** (combinado **{p['hora']}**)\n\n"
                    f"- Sai de *{ant['cliente']}* às **{_hhmm(ant['saida_prevista'])}** "
                    f"após {_dur(ant['min_servico'])} de trabalho\n"
                    f"- Trajeto de {ant['cliente']} até aqui: **{_dur(p['min_deslocamento'])}** "
                    f"({p['km_desde_anterior']} km)\n"
                    f"- Chegada real prevista: **{_hhmm(p['chegada_prevista'])}** "
                    f"→ 🚨 **{_dur(p['atraso'])} de atraso**\n"
                    f"- ✅ Horário viável para remarcar: **{sugerir_horario_viavel(p, ant)}**"
                )
                st.divider()
    else:
        st.success("✅ Todos os horários combinados são viáveis com o tempo de montagem previsto.")

    conflitos = agenda["conflitos_festa"]
    if conflitos:
        st.warning(
            "🎉 **Montagem terminando depois do início da festa:** " +
            " • ".join(
                f"{p['cliente']} (festa {p['inicio_festa']}, montagem até "
                f"{_hhmm(p['saida_prevista'])} — {_dur(p['min_apos_inicio'])} depois)"
                for p in conflitos
            )
        )

    if agenda["total_ocioso"] > 45:
        st.info(f"🕓 Você tem **{_dur(agenda['total_ocioso'])}** de espera entre paradas. "
                "Dá para encaixar outra entrega ou adiantar um horário.")

    # ---------- Rota no Maps ----------
    links = urls_rota_completa(paradas)
    if links:
        st.markdown("#### 🗺️ Abrir rota no Google Maps")
        cols = st.columns(min(len(links), 3))
        for i, link in enumerate(links):
            rotulo = "🗺️ Abrir rota completa" if len(links) == 1 else f"🗺️ Rota parte {i+1}"
            cols[i % len(cols)].link_button(rotulo, link, use_container_width=True)

    st.divider()

    # ---------- Linha do tempo ----------
    st.markdown(f"#### 🏁 Saída da base — **{_hhmm(agenda['saida_base'])}**")

    for idx, p in enumerate(paradas):
        st.markdown(
            f"<div class='rt-trajeto'>🚐 {p['km_desde_anterior']} km • "
            f"{_dur(p['min_deslocamento'])} de trajeto ⬇️</div>",
            unsafe_allow_html=True
        )

        icone = "🟢" if p["tipo"] == "Entrega" else "🔴"
        if p["concluida"]:
            classe = "rt-feito"
        elif p["atraso"] > 0:
            classe = "rt-atraso"
        else:
            classe = "rt-entrega" if p["tipo"] == "Entrega" else "rt-retirada"

        bloco = [
            f"<div class='rt-card {classe}'>",
            f"<span class='rt-hora'>{p['ordem']}. {icone} {p['hora']}</span>",
            f"&nbsp;<b>{p['tipo'].upper()}</b>",
        ]
        if p["atraso"] > 0:
            bloco.append(f" &nbsp;<span style='color:#C0392B;font-weight:700;'>"
                         f"🚨 +{_dur(p['atraso'])}</span>")
        bloco.append("<br>")
        bloco.append(f"<span class='rt-cli'>{p['cliente']}</span><br>")
        bloco.append(f"📍 {p['endereco']}<br>")

        # Janela de permanência
        bloco.append(
            f"<div class='rt-janela'>"
            f"⏱️ <b>Chegada {_hhmm(p['chegada_prevista'])}</b> → "
            f"<b>saída {_hhmm(p['saida_prevista'])}</b><br>"
            f"🔧 {_dur(p['min_servico'])} de "
            f"{'montagem' if p['tipo'] == 'Entrega' else 'desmontagem'} previstos"
            + (f"<br>🕓 {_dur(p['ocioso'])} de espera antes desta parada" if p.get("ocioso", 0) >= 15 else "")
            + "</div>"
        )

        if p["brinquedos"]:
            bloco.append(f"🎠 {p['brinquedos']}<br>")
        if p["inicio_festa"] and p["fim_festa"]:
            bloco.append(f"🎉 Festa: {p['inicio_festa']} às {p['fim_festa']}<br>")
        if p["tipo"] == "Retirada" and p["data_festa"] != data_alvo:
            bloco.append(f"<i>↩️ Festa do dia {p['data_festa'].strftime('%d/%m')}</i><br>")
        if p.get("conflito_festa"):
            bloco.append(f"<div class='rt-alerta'>⚠️ Montagem termina "
                         f"{_dur(p['min_apos_inicio'])} após o início da festa "
                         f"({p['inicio_festa']})</div>")
        if p["falta"] > 0:
            bloco.append(f"<div class='rt-receber'>💰 RECEBER R$ {p['falta']:,.2f}</div>")
        bloco.append("</div>")
        st.markdown("".join(bloco), unsafe_allow_html=True)

        b1, b2, b3 = st.columns(3)

        if p["endereco_maps"]:
            b1.link_button("📍 Navegar", url_navegar(p["endereco_maps"]), use_container_width=True)

        if p["telefone"]:
            eta = _dur(p["min_deslocamento"])
            if p["tipo"] == "Entrega":
                msg = (f"Olá {p['cliente']}! Aqui é da TimTim Festas 🎈\n"
                       f"Estamos a caminho para a montagem, chegada prevista em cerca de {eta}.")
                if p["atraso"] > 0:
                    msg = (f"Olá {p['cliente']}! Aqui é da TimTim Festas 🎈\n"
                           f"Estamos finalizando a montagem anterior e seguimos para você. "
                           f"Previsão de chegada: {_hhmm(p['chegada_prevista'])}.")
            else:
                msg = (f"Olá {p['cliente']}! Aqui é da TimTim Festas 🎈\n"
                       f"Estamos a caminho para a retirada dos itens, chegamos em cerca de {eta}.")
            b2.link_button("💬 Avisar", url_whatsapp(p["telefone"], msg), use_container_width=True)

        rotulo = "↩️ Reabrir" if p["concluida"] else "✅ Concluir"
        if b3.button(rotulo, key=f"rt_ok_{_chave_parada(p)}", use_container_width=True):
            salvar_status(p["reserva_id"], p["tipo"], data_alvo, not p["concluida"])
            st.rerun()

    st.markdown(
        f"<div class='rt-trajeto'>🚐 {_dur(agenda['min_volta'])} de volta ⬇️</div>",
        unsafe_allow_html=True
    )
    st.markdown(f"#### 🏠 Retorno à base — **{_hhmm(agenda['retorno_base'])}** "
                f"(jornada de {_dur(jornada)})")

    # ---------- Exportar / parâmetros ----------
    st.divider()
    with st.expander("📋 Copiar roteiro em texto (enviar ao monitor)"):
        st.text_area("Roteiro:", texto_roteiro(paradas, data_alvo, km_total, agenda),
                     height=450, key="rt_texto")

    with st.expander("⚙️ Parâmetros usados no cálculo"):
        st.markdown(f"""
| Parâmetro | Valor |
|---|---|
| Base de origem | {ENDERECO_BASE} |
| Montagem (entrega) | {_dur(MIN_MONTAGEM_PADRAO)} |
| Desmontagem (retirada) | {_dur(MIN_DESMONTAGEM_PADRAO)} |
| Por brinquedo extra | +{MIN_POR_BRINQUEDO_EXTRA} min |
| Kit Montessori | +{MIN_MONTESSORI_EXTRA} min |
| Velocidade média | {VELOCIDADE_MEDIA_KMH} km/h |
| Consumo | {CONSUMO_KML} km/l a R$ {PRECO_COMBUSTIVEL}/l |
        """)
        st.caption("Edite as constantes no topo de roteiro.py. Depois de alguns dias reais, "
                   "compare com o relógio e o odômetro para calibrar.")


# ==============================================================
# COMO INTEGRAR NO app.py — APENAS 3 LINHAS
# ==============================================================
#   from roteiro import pagina_roteiro
#   "Roteiro": ("🚚 Roteiro do Dia", "roteiro"),
#   elif menu == "Roteiro":
#       pagina_roteiro()
# ==============================================================
