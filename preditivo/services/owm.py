import os
import requests
from collections import defaultdict
from datetime import datetime, timezone

OWM_URL        = "https://api.openweathermap.org/data/2.5/forecast"
APPID          = os.getenv("APPID")
UMIDADE_LIMIAR = 85
POP_LIMIAR     = 0.4
ORVALHO_LIMIAR = 95
CHUVA_LIMIAR_MM = 30.0


def buscar_previsao(lat, lon, days=7):
    """Busca blocos de 3h do OWM. cnt = days * 8 blocos."""
    cnt = min(days * 8, 56)  # OWM suporta até 56 blocos (~7 dias)
    r = requests.get(OWM_URL, params={
        "lat": lat, "lon": lon,
        "appid": APPID, "units": "metric", "cnt": cnt,
    }, timeout=10)
    r.raise_for_status()
    return r.json()["list"]


def estimar_dias_futuros(blocos):
    """
    Agrupa blocos por data UTC, estima PMF e chuva diária.
    Retorna lista de dicts por dia.
    """
    blocos_por_dia = defaultdict(list)
    for b in blocos:
        dt = datetime.fromtimestamp(b["dt"], tz=timezone.utc)
        blocos_por_dia[dt.date().isoformat()].append(b)

    dias = []
    for data in sorted(blocos_por_dia):
        blocos_dia   = blocos_por_dia[data]
        periodos     = _detectar_periodos(blocos_dia)
        chuva_mm_dia = sum(b.get("rain", {}).get("3h", 0) for b in blocos_dia)
        avg_temp_dia = (
            round(sum(b["main"]["temp"] for b in blocos_dia) / len(blocos_dia), 2)
            if blocos_dia else None
        )

        dias.append({
            "date":                   data,
            "pmf_estimado":           periodos,
            "total_horas_molhamento": round(sum(p["duration_hours"] for p in periodos), 1),
            "avg_temp_dia":           avg_temp_dia,
            "chuva_mm":               round(chuva_mm_dia, 2),
            "dia_chuvoso":            chuva_mm_dia > CHUVA_LIMIAR_MM,
        })

    return dias


def _bloco_molhado(b):
    return (
        b.get("rain", {}).get("3h", 0) > 0
        or b.get("pop", 0) >= POP_LIMIAR
        or b["main"]["humidity"] >= UMIDADE_LIMIAR
    )


def _detectar_periodos(blocos_dia):
    periodos   = []
    numero     = 1
    em_periodo = False
    inicio     = None
    fim        = None
    temps      = []

    for b in blocos_dia:
        dt = datetime.fromtimestamp(b["dt"], tz=timezone.utc)
        if _bloco_molhado(b):
            if not em_periodo:
                em_periodo = True
                inicio = dt
                temps  = []
            temps.append(b["main"]["temp"])
            fim = dt
        else:
            if em_periodo:
                periodos.append(_fechar_periodo(numero, inicio, fim, temps, blocos_dia))
                numero    += 1
                em_periodo = False

    if em_periodo:
        periodos.append(_fechar_periodo(numero, inicio, fim, temps, blocos_dia))

    return periodos


def _fechar_periodo(numero, inicio, fim, temps, blocos_dia):
    duracao = (fim - inicio).total_seconds() / 3600 + 3.0
    orvalho = any(
        b["main"]["humidity"] >= ORVALHO_LIMIAR
        for b in blocos_dia
        if inicio <= datetime.fromtimestamp(b["dt"], tz=timezone.utc) <= fim
    )
    return {
        "period_number":      numero,
        "start_time":         inicio.isoformat(),
        "end_time":           fim.isoformat(),
        "duration_hours":     round(duracao, 2),
        "avg_temperature":    round(sum(temps) / len(temps), 2),
        "teve_ponto_orvalho": orvalho,
        "estimado":           True,
    }
