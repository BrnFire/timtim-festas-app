# ==============================================================
# MÓDULO ROTEIRO DO DIA – TimTim Festas   ***VERSÃO 3***
# Arquivo independente. Não altera nenhum outro módulo do app.
#
# COMO SABER QUE É A v3 (e não a v2):
#   - Cada parada tem 4 BOTÕES: Navegar | Avisar | 📍 Cheguei | ✏️ Ajustar
#   - Existe o painel "📊 Seus tempos reais (calibração)"
#   - Os cards de resumo são 5 (inclui 🕐 Jornada)
#   - Ao abrir a página aparece no topo: "Roteiro do Dia · v3"
#
# NOVIDADES DA v3:
#   - Botões "📍 Cheguei" / "✅ Terminei" gravam o horário REAL
#   - O tempo real substitui a estimativa e recalcula o resto do dia
#   - Cronômetro da parada em andamento (minutos decorridos)
#   - Comparativo real x previsto (ex.: "40min mais rápido")
#   - Ajuste manual de horário caso esqueça de clicar
#   - Calibração automática da sua média de montagem
#
# INSTALAÇÃO:
#   1) Salve este arquivo como  roteiro.py  (substituindo o antigo)
#   2) Rode o SQL do roteiro_supabase_v3.sql no Supabase
#   3) No app.py, as mesmas 3 linhas do final deste arquivo
#   4) PARE e RODE de novo:  streamlit run app.py   (F5 não basta!)
# ==============================================================

VERSAO_MODULO = "v3"

import re
import math
import unicodedata
from datetime import datetime, date, timedelta
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

# ---------- ⏱️ TEMPOS OPERACIONAIS ----------
MIN_MONTAGEM_PADRAO = 90        # 1h30 — tempo médio de montagem na entrega
MIN_DESMONTAGEM_PADRAO = 45     # retirada costuma ser mais rápida
MIN_POR_BRINQUEDO_EXTRA = 10    # a cada brinquedo além do 1º
MIN_MONTESSORI_EXTRA = 20       # kit montessori (tatames) leva mais tempo

VELOCIDADE_MEDIA_KMH = 25.0     # trânsito urbano ABC/SP
MIN_FOLGA_SEGURANCA = 10        # margem ao sugerir novo horário
HORA_SAIDA_MINIMA = "06:00"     # não sugere sair da base antes disso

# ---------- 📡 TEMPO REAL (v3) ----------
MIN_AMOSTRAS_CALIBRACAO = 3     # registros mínimos p/ sugerir novo padrão
DIAS_HISTORICO_CALIBRACAO = 180 # janela do histórico na calibração

COLS_ROTEIRO = [
    "id_parada", "reserva_id", "tipo", "data", "concluida",
    "chegada_real", "saida_real", "atualizado_em"
]

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
    """510 -> '08:30'. Trata valores fora de 0-1439."""
    minutos = int(round(minutos))
    sufixo = ""
    if minutos < 0:
        minutos += 1440
        sufixo = " (D-1)"
    if minutos >= 1440:
        minutos -= 1440
        sufixo = " (D+1)"
    return f"{minutos // 60:02d}:{minutos % 60:02d}{sufixo}"


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


def agora_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


# ==============================================================
# GEOLOCALIZAÇÃO (cache 24h)
# ==============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def _coords_endereco(logradouro: str, numero: str, cidade: str, uf: str, cep: str):
    """
    Coordenadas do ENDEREÇO (não só da cidade).
    Essencial dentro do ABC: buscar pela cidade daria distância zero entre paradas.
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
    """Ajuste rota real x linha reta (fator ~1.35 em área urbana)."""
    return round(km_reta * 1.35, 1) if km_reta else 0.0


def minutos_deslocamento(km):
    """Km -> minutos de trajeto, com piso de 5 min (estacionar, subir, etc.)."""
    if not km:
        return 0
    return max(5, int(round((km / VELOCIDADE_MEDIA_KMH) * 60)))


# ==============================================================
# ⏱️ TEMPO DE SERVIÇO ESTIMADO POR PARADA
# ==============================================================

def tempo_servico(parada: dict, cat_map: dict) -> int:

    if parada["tipo"] == "Entrega":
        return int(MIN_MONTAGEM_PADRAO)
    return int(MIN_DESMONTAGEM_PADRAO)


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
    """
    Desdobra reservas em PARADAS.
    Uma reserva vira até 2 paradas (entrega e retirada), que podem cair em dias diferentes.
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
        d_ret = d_reserva + timedelta(days=1) if _min_do_dia(h_ret) <= _min_do_dia(h_ent) else d_reserva

        cli = mapa_cli.get(_s(r.get("cliente")).lower(), {})

        for tipo, d_parada, hora in [("Entrega", d_reserva, h_ent), ("Retirada", d_ret, h_ret)]:
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

    # Ordena por HORÁRIO (compromisso com o cliente manda, não a distância)
    paradas.sort(key=lambda p: (_min_do_dia(p["hora"]), p["tipo"]))
    for i, p in enumerate(paradas, start=1):
        p["ordem"] = i
    return paradas


def calcular_distancias(paradas: list) -> tuple:
    """Distância de cada parada em relação à ANTERIOR (não à base)."""
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
# ⏱️ SIMULAÇÃO DA LINHA DO TEMPO — CORAÇÃO DA v3
# ==============================================================
def simular_agenda(paradas: list, cat_map: dict, min_volta: int, agora: int = None) -> dict:
    """
    Encadeia: chegada -> serviço -> deslocamento -> próxima chegada

    🔴 O RELÓGIO REAL TEM PRIORIDADE ABSOLUTA:
      - chegada_real registrada -> ela vale, não a estimativa
      - saida_real registrada  -> o tempo REAL substitui o estimado
        (terminou em 50min em vez de 1h30 -> o resto do dia adianta 40min)
      - EM ANDAMENTO (chegou, não saiu) -> projeta usando o maior valor
        entre o tempo estimado e o já decorrido
      - Só paradas não iniciadas usam a estimativa pura
    """
    if not paradas:
        return {}

    relogio = None
    atraso_max = 0
    economia = 0          # minutos ganhos (+) ou perdidos (-) vs. o previsto

    for i, p in enumerate(paradas):
        combinado = _min_do_dia(p["hora"])
        p["min_servico_estimado"] = tempo_servico(p, cat_map)

        ch_real = p.get("chegada_real_min")
        sa_real = p.get("saida_real_min")

        # ---------- CHEGADA ----------
        if ch_real is not None:
            chegada = ch_real
            p["chegada_confirmada"] = True
        else:
            p["chegada_confirmada"] = False
            if i == 0 or relogio is None:
                chegada = combinado
            else:
                chegada = max(combinado, relogio + p["min_deslocamento"])

        # ---------- SERVIÇO ----------
        if ch_real is not None and sa_real is not None:
            p["status_exec"] = "concluida"
            p["min_servico"] = max(0, sa_real - ch_real)
            p["min_servico_real"] = p["min_servico"]
            saida = sa_real
            economia += p["min_servico_estimado"] - p["min_servico"]
        elif ch_real is not None and agora is not None:
            p["status_exec"] = "andamento"
            decorrido = max(0, agora - ch_real)
            p["min_decorrido"] = decorrido
            p["min_servico"] = max(p["min_servico_estimado"], decorrido)
            saida = chegada + p["min_servico"]
        elif ch_real is not None:
            # chegou, mas estamos vendo outro dia -> usa estimativa
            p["status_exec"] = "andamento"
            p["min_decorrido"] = 0
            p["min_servico"] = p["min_servico_estimado"]
            saida = chegada + p["min_servico"]
        else:
            p["status_exec"] = "pendente"
            p["min_servico"] = p["min_servico_estimado"]
            saida = chegada + p["min_servico"]

        # ---------- ATRASO / OCIOSIDADE ----------
        p["atraso"] = max(0, chegada - combinado)
        if i == 0 or relogio is None:
            p["ocioso"] = 0
        else:
            folga = combinado - (relogio + p["min_deslocamento"])
            p["ocioso"] = max(0, folga) if p["atraso"] == 0 else 0

        atraso_max = max(atraso_max, p["atraso"])

        p["chegada_prevista"] = chegada
        p["saida_prevista"] = saida
        relogio = saida

        # ---------- CONFLITO COM A FESTA ----------
        p["conflito_festa"] = False
        if p["tipo"] == "Entrega" and p["inicio_festa"] and p["status_exec"] != "concluida":
            ini = _min_do_dia(p["inicio_festa"])
            if saida > ini:
                p["conflito_festa"] = True
                p["min_apos_inicio"] = saida - ini

    primeira = paradas[0]
    saida_base = primeira["chegada_prevista"] - primeira["min_deslocamento"]
    piso = _min_do_dia(HORA_SAIDA_MINIMA)

    pendentes = [p for p in paradas if p["status_exec"] == "pendente"]
    em_andamento = next((p for p in paradas if p["status_exec"] == "andamento"), None)

    return {
        "saida_base": max(saida_base, piso) if saida_base < piso else saida_base,
        "saida_base_calculada": saida_base,
        "saida_base_antecipada": saida_base < piso,
        "retorno_base": relogio + min_volta,
        "min_volta": min_volta,
        "total_servico": sum(p["min_servico"] for p in paradas),
        "total_deslocamento": sum(p["min_deslocamento"] for p in paradas) + min_volta,
        "total_ocioso": sum(p.get("ocioso", 0) for p in paradas),
        "maior_atraso": atraso_max,
        "paradas_atrasadas": [p for p in paradas
                              if p["atraso"] > 0 and p["status_exec"] != "concluida"],
        "conflitos_festa": [p for p in paradas if p.get("conflito_festa")],
        # --- v3 ---
        "economia": economia,
        "concluidas": [p for p in paradas if p["status_exec"] == "concluida"],
        "em_andamento": em_andamento,
        "pendentes": pendentes,
        "proxima": pendentes[0] if pendentes else None,
    }


def sugerir_horario_viavel(parada: dict, anterior: dict) -> str:
    return _hhmm(anterior["saida_prevista"] + parada["min_deslocamento"] + MIN_FOLGA_SEGURANCA)


# ==============================================================
# 📊 CALIBRAÇÃO AUTOMÁTICA (v3)
# ==============================================================
def estatisticas_reais(dias: int = DIAS_HISTORICO_CALIBRACAO) -> dict:
    """Média/mediana do tempo real de montagem e desmontagem."""
    try:
        df = carregar_dados("roteiro_status", COLS_ROTEIRO)
        if df is None or df.empty:
            return {}
        df = df.copy()
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        limite = pd.Timestamp(date.today() - timedelta(days=dias))
        df = df[df["data"] >= limite]
        if df.empty:
            return {}

        df["ch"] = df["chegada_real"].apply(lambda x: _min_do_dia(x) if _s(x) else None)
        df["sa"] = df["saida_real"].apply(lambda x: _min_do_dia(x) if _s(x) else None)
        df = df.dropna(subset=["ch", "sa"])
        if df.empty:
            return {}

        df["dur"] = df["sa"] - df["ch"]
        df = df[(df["dur"] > 5) & (df["dur"] < 480)]   # descarta cliques errados
        if df.empty:
            return {}

        out = {}
        for tipo, rotulo in [("Entrega", "montagem"), ("Retirada", "desmontagem")]:
            sub = df[df["tipo"] == tipo]
            if len(sub) >= 1:
                out[rotulo] = {
                    "n": int(len(sub)),
                    "media": int(round(sub["dur"].mean())),
                    "mediana": int(round(sub["dur"].median())),
                    "min": int(sub["dur"].min()),
                    "max": int(sub["dur"].max()),
                }
        return out
    except Exception:
        return {}


# ==============================================================
# LINKS EXTERNOS
# ==============================================================
def url_navegar(destino: str) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(destino)}"


def urls_rota_completa(paradas: list) -> list:
    """Gera 1+ links (Google aceita ~9 waypoints intermediários por URL)."""
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
        if p["status_exec"] == "concluida":
            linhas.append(f"✅ REAL: chegou {p['chegada_real']} → saiu {p['saida_real']} "
                          f"({_dur(p['min_servico_real'])})")
        else:
            linhas.append(f"⏱️ Chegada {_hhmm(p['chegada_prevista'])} → "
                          f"saída {_hhmm(p['saida_prevista'])} "
                          f"({_dur(p['min_servico'])} no local)")
        if p["atraso"] > 0 and p["status_exec"] != "concluida":
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
# PERSISTÊNCIA DOS MARCOS (chegada / saída reais)
# ==============================================================
def _chave_parada(p) -> str:
    return f"{p['reserva_id']}_{p['tipo']}"


def carregar_marcos(data_alvo: date) -> dict:
    """{chave: {"concluida":bool, "chegada":"HH:MM"|None, "saida":"HH:MM"|None}}"""
    try:
        df = carregar_dados("roteiro_status", COLS_ROTEIRO)
        if df is None or df.empty:
            return {}
        df = df.copy()
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
        df = df[df["data"] == data_alvo]
        out = {}
        for _, r in df.iterrows():
            out[f"{_s(r['reserva_id'])}_{_s(r['tipo'])}"] = {
                "concluida": _s(r.get("concluida")).lower() in {"true", "sim", "1", "t"},
                "chegada": _hora(r.get("chegada_real")) if _s(r.get("chegada_real")) else None,
                "saida": _hora(r.get("saida_real")) if _s(r.get("saida_real")) else None,
            }
        return out
    except Exception:
        return {}


def salvar_marco(reserva_id, tipo: str, data_alvo: date, **campos):
    """
    Grava/atualiza um marco da parada.
    campos: concluida (bool), chegada_real (str|None), saida_real (str|None)
    Tenta UPDATE; se não houver linha, faz INSERT (a unique do banco protege duplicata).
    """
    registro = {
        "reserva_id": int(reserva_id) if pd.notna(reserva_id) else None,
        "tipo": tipo,
        "data": str(data_alvo),
        "atualizado_em": str(datetime.now()),
    }
    registro.update(campos)
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
        .rt-andando{background:#FEF5E7;border-left-color:#F39C12;}
        .rt-feito{background:#F2F2F2;border-left-color:#999;opacity:.65;}
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
    st.caption(f"Módulo {VERSAO_MODULO} · cronômetro em tempo real ativo")

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

    # ---------- Marcos reais ANTES da simulação ----------
    marcos = carregar_marcos(data_alvo)
    for p in paradas:
        m = marcos.get(_chave_parada(p), {})
        p["chegada_real"] = m.get("chegada")
        p["saida_real"] = m.get("saida")
        p["chegada_real_min"] = _min_do_dia(m["chegada"]) if m.get("chegada") else None
        p["saida_real_min"] = _min_do_dia(m["saida"]) if m.get("saida") else None
        p["concluida"] = bool(m.get("concluida")) or p["saida_real"] is not None

    agora_min = _min_do_dia(agora_hhmm()) if data_alvo == hoje else None

    with st.spinner("Calculando rota e horários..."):
        paradas, km_total, min_volta = calcular_distancias(paradas)
        cat_map = _carregar_categorias()
        agenda = simular_agenda(paradas, cat_map, min_volta, agora=agora_min)

    # ---------- Cards de resumo (5 na v3) ----------
    litros = km_total / CONSUMO_KML if CONSUMO_KML else 0
    combustivel = litros * PRECO_COMBUSTIVEL
    a_receber = sum(p["falta"] for p in paradas)
    feitas = len(agenda["concluidas"])
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

    # ---------- Plano do dia ----------
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

    # ---------- 📡 PAINEL AO VIVO (v3) ----------
    andando = agenda.get("em_andamento")
    economia = agenda.get("economia", 0)

    if andando:
        restante = andando["min_servico_estimado"] - andando.get("min_decorrido", 0)
        txt = (f"faltam ~{_dur(restante)} para o tempo médio" if restante > 0
               else f"já passou {_dur(-restante)} do tempo médio")
        st.info(
            f"⏳ **Em andamento:** {andando['cliente']} — chegou às **{andando['chegada_real']}**, "
            f"**{_dur(andando.get('min_decorrido', 0))}** decorridos ({txt}). "
            f"Ao clicar em **✅ Terminei**, o restante do dia é recalculado."
        )
    elif agenda.get("proxima") and agenda["concluidas"]:
        prox = agenda["proxima"]
        st.info(
            f"🚐 **Próxima parada:** {prox['cliente']} às **{prox['hora']}** — "
            f"{prox['km_desde_anterior']} km / {_dur(prox['min_deslocamento'])} de trajeto. "
            f"Chegada prevista: **{_hhmm(prox['chegada_prevista'])}**."
        )

    if agenda["concluidas"]:
        if economia > 4:
            st.success(f"🟢 Você está **{_dur(economia)} adiantado** em relação ao plano original — "
                       f"os horários seguintes já foram recalculados.")
        elif economia < -4:
            st.warning(f"🔴 Você está **{_dur(-economia)} atrasado** em relação ao plano original — "
                       f"veja abaixo as paradas afetadas.")

    if data_alvo == hoje and (andando or agenda["pendentes"]):
        if st.button("🔄 Atualizar relógio", key="rt_refresh"):
            st.rerun()
        st.caption(f"Horários calculados às {agora_hhmm()}. "
                   "Clique em Atualizar para recalcular com o relógio atual.")

    # ---------- 🚨 Alertas de atraso ----------
    atrasadas = agenda["paradas_atrasadas"]
    if atrasadas:
        st.error(f"🚨 {len(atrasadas)} parada(s) com atraso previsto — maior atraso: "
                 f"{_dur(agenda['maior_atraso'])}")
        with st.expander("Ver detalhes e sugestões de horário", expanded=True):
            for p in atrasadas:
                if p["ordem"] < 2:
                    continue
                ant = paradas[p["ordem"] - 2]
                st.markdown(
                    f"**Parada {p['ordem']} — {p['cliente']}** (combinado **{p['hora']}**)\n\n"
                    f"- Sai de *{ant['cliente']}* às **{_hhmm(ant['saida_prevista'])}** "
                    f"após {_dur(ant['min_servico'])} de trabalho\n"
                    f"- Trajeto até aqui: **{_dur(p['min_deslocamento'])}** "
                    f"({p['km_desde_anterior']} km)\n"
                    f"- Chegada real prevista: **{_hhmm(p['chegada_prevista'])}** "
                    f"→ 🚨 **{_dur(p['atraso'])} de atraso**\n"
                    f"- ✅ Horário viável para remarcar: **{sugerir_horario_viavel(p, ant)}**"
                )
                st.divider()
    elif agenda["pendentes"]:
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
        if len(links) > 1:
            st.caption("O Google Maps aceita até 9 paradas intermediárias por link — "
                       "o roteiro foi dividido em blocos.")

    st.divider()

    # ---------- Linha do tempo ----------
    st.markdown(f"#### 🏁 Saída da base — **{_hhmm(agenda['saida_base'])}**")

    for p in paradas:
        st.markdown(
            f"<div class='rt-trajeto'>🚐 {p['km_desde_anterior']} km • "
            f"{_dur(p['min_deslocamento'])} de trajeto ⬇️</div>",
            unsafe_allow_html=True
        )

        icone = "🟢" if p["tipo"] == "Entrega" else "🔴"
        if p["status_exec"] == "concluida":
            classe = "rt-feito"
        elif p["status_exec"] == "andamento":
            classe = "rt-andando"
        elif p["atraso"] > 0:
            classe = "rt-atraso"
        else:
            classe = "rt-entrega" if p["tipo"] == "Entrega" else "rt-retirada"

        bloco = [
            f"<div class='rt-card {classe}'>",
            f"<span class='rt-hora'>{p['ordem']}. {icone} {p['hora']}</span>",
            f"&nbsp;<b>{p['tipo'].upper()}</b>",
        ]
        if p["atraso"] > 0 and p["status_exec"] != "concluida":
            bloco.append(f" &nbsp;<span style='color:#C0392B;font-weight:700;'>"
                         f"🚨 +{_dur(p['atraso'])}</span>")
        bloco.append("<br>")
        bloco.append(f"<span class='rt-cli'>{p['cliente']}</span><br>")
        bloco.append(f"📍 {p['endereco']}<br>")

        # ---- Janela: real / em andamento / previsto ----
        servico_nome = "montagem" if p["tipo"] == "Entrega" else "desmontagem"
        if p["status_exec"] == "concluida":
            dif = p["min_servico_estimado"] - p["min_servico_real"]
            if dif > 4:
                comparativo = (f"<br>🟢 <b>{_dur(dif)} mais rápido</b> que o previsto "
                               f"({_dur(p['min_servico_estimado'])})")
            elif dif < -4:
                comparativo = (f"<br>🔴 <b>{_dur(-dif)} mais lento</b> que o previsto "
                               f"({_dur(p['min_servico_estimado'])})")
            else:
                comparativo = "<br>🎯 Dentro do previsto"
            bloco.append(
                f"<div class='rt-janela' style='border-left:4px solid #2ECC71;'>"
                f"✅ <b>REAL:</b> chegou {p['chegada_real']} → saiu {p['saida_real']}<br>"
                f"🔧 {_dur(p['min_servico_real'])} de {servico_nome}{comparativo}</div>"
            )
        elif p["status_exec"] == "andamento":
            bloco.append(
                f"<div class='rt-janela' style='border-left:4px solid #F39C12;'>"
                f"⏳ <b>EM ANDAMENTO</b> — chegou às {p['chegada_real']}<br>"
                f"⏱️ <b>{_dur(p.get('min_decorrido', 0))} decorridos</b> "
                f"(previsto: {_dur(p['min_servico_estimado'])})<br>"
                f"🏁 Saída projetada: <b>{_hhmm(p['saida_prevista'])}</b></div>"
            )
        else:
            bloco.append(
                f"<div class='rt-janela'>"
                f"⏱️ <b>Chegada {_hhmm(p['chegada_prevista'])}</b> → "
                f"<b>saída {_hhmm(p['saida_prevista'])}</b><br>"
                f"🔧 {_dur(p['min_servico'])} de {servico_nome} previstos"
                + (f"<br>🕓 {_dur(p['ocioso'])} de espera antes desta parada"
                   if p.get("ocioso", 0) >= 15 else "")
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

        # ---- 4 BOTÕES (marca registrada da v3) ----
        ch = _chave_parada(p)
        b1, b2, b3, b4 = st.columns(4)

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

        # ---- CRONÔMETRO ----
        if p["status_exec"] == "pendente":
            if b3.button("📍 Cheguei", key=f"rt_ch_{ch}", type="primary", use_container_width=True):
                salvar_marco(p["reserva_id"], p["tipo"], data_alvo,
                             chegada_real=agora_hhmm(), concluida=False)
                st.rerun()
        elif p["status_exec"] == "andamento":
            if b3.button("✅ Terminei", key=f"rt_sa_{ch}", type="primary", use_container_width=True):
                salvar_marco(p["reserva_id"], p["tipo"], data_alvo,
                             saida_real=agora_hhmm(), concluida=True)
                st.rerun()
        else:
            if b3.button("↩️ Desfazer", key=f"rt_un_{ch}", use_container_width=True):
                salvar_marco(p["reserva_id"], p["tipo"], data_alvo,
                             saida_real=None, concluida=False)
                st.rerun()

        # ---- AJUSTE MANUAL (esqueceu de clicar) ----
        with b4.popover("✏️ Ajustar", use_container_width=True):
            st.caption("Corrija os horários se esqueceu de clicar na hora.")
            ch_txt = st.text_input("Chegada (HH:MM)", value=p["chegada_real"] or "",
                                   key=f"rt_ajch_{ch}", placeholder="08:05")
            sa_txt = st.text_input("Saída (HH:MM)", value=p["saida_real"] or "",
                                   key=f"rt_ajsa_{ch}", placeholder="08:55")
            c_ok, c_lim = st.columns(2)
            if c_ok.button("💾 Salvar", key=f"rt_ajok_{ch}", use_container_width=True):
                nova_ch = _hora(ch_txt) if ch_txt.strip() else None
                nova_sa = _hora(sa_txt) if sa_txt.strip() else None
                salvar_marco(p["reserva_id"], p["tipo"], data_alvo,
                             chegada_real=nova_ch, saida_real=nova_sa,
                             concluida=nova_sa is not None)
                st.rerun()
            if c_lim.button("🗑️ Limpar", key=f"rt_ajlim_{ch}", use_container_width=True):
                salvar_marco(p["reserva_id"], p["tipo"], data_alvo,
                             chegada_real=None, saida_real=None, concluida=False)
                st.rerun()

    st.markdown(
        f"<div class='rt-trajeto'>🚐 {_dur(agenda['min_volta'])} de volta ⬇️</div>",
        unsafe_allow_html=True
    )
    st.markdown(f"#### 🏠 Retorno à base — **{_hhmm(agenda['retorno_base'])}** "
                f"(jornada de {_dur(jornada)})")

    # ---------- Exportar ----------
    st.divider()
    with st.expander("📋 Copiar roteiro em texto (enviar ao monitor)"):
        st.text_area("Roteiro:", texto_roteiro(paradas, data_alvo, km_total, agenda),
                     height=450, key="rt_texto")

    # ---------- 📊 Calibração (v3) ----------
    with st.expander("📊 Seus tempos reais (calibração)"):
        stats = estatisticas_reais()
        if not stats:
            st.info("Ainda não há horários reais registrados. Use **📍 Cheguei** e "
                    "**✅ Terminei** em algumas paradas — depois disso aparece aqui a sua "
                    "média real de montagem para ajustar os parâmetros.")
        else:
            linhas = ["| Serviço | Registros | Média real | Mediana | Mais rápido | Mais lento | Padrão atual |",
                      "|---|---|---|---|---|---|---|"]
            padroes = {"montagem": MIN_MONTAGEM_PADRAO, "desmontagem": MIN_DESMONTAGEM_PADRAO}
            for rotulo, s in stats.items():
                linhas.append(
                    f"| {rotulo.capitalize()} | {s['n']} | **{_dur(s['media'])}** | {_dur(s['mediana'])} "
                    f"| {_dur(s['min'])} | {_dur(s['max'])} | {_dur(padroes[rotulo])} |"
                )
            st.markdown("\n".join(linhas))

            for rotulo, s in stats.items():
                if s["n"] < MIN_AMOSTRAS_CALIBRACAO:
                    st.caption(f"ℹ️ {rotulo.capitalize()}: {s['n']} registro(s) — "
                               f"a partir de {MIN_AMOSTRAS_CALIBRACAO} a sugestão fica confiável.")
                    continue
                atual = padroes[rotulo]
                sugerido = s["mediana"]
                if abs(sugerido - atual) >= 10:
                    const = "MIN_MONTAGEM_PADRAO" if rotulo == "montagem" else "MIN_DESMONTAGEM_PADRAO"
                    st.success(
                        f"💡 Sua {rotulo} real tem mediana de **{_dur(sugerido)}**, "
                        f"contra {_dur(atual)} configurado. "
                        f"Considere ajustar no topo do arquivo: `{const} = {sugerido}`"
                    )
                else:
                    st.caption(f"✅ {rotulo.capitalize()}: o padrão configurado está "
                               f"alinhado ao seu tempo real.")

    with st.expander("⚙️ Parâmetros usados no cálculo"):
        st.markdown(f"""
| Parâmetro | Valor |
|---|---|
| Versão do módulo | **{VERSAO_MODULO}** |
| Base de origem | {ENDERECO_BASE} |
| Montagem (entrega) | {_dur(MIN_MONTAGEM_PADRAO)} |
| Desmontagem (retirada) | {_dur(MIN_DESMONTAGEM_PADRAO)} |
| Por brinquedo extra | +{MIN_POR_BRINQUEDO_EXTRA} min |
| Kit Montessori | +{MIN_MONTESSORI_EXTRA} min |
| Velocidade média | {VELOCIDADE_MEDIA_KMH} km/h |
| Consumo | {CONSUMO_KML} km/l a R$ {PRECO_COMBUSTIVEL}/l |
        """)
        st.caption("Edite as constantes no topo de roteiro.py.")


# ==============================================================
# COMO INTEGRAR NO app.py — APENAS 3 LINHAS
# ==============================================================
#   from roteiro import pagina_roteiro
#   "Roteiro": ("🚚 Roteiro do Dia", "roteiro"),
#   elif menu == "Roteiro":
#       pagina_roteiro()
# ==============================================================
