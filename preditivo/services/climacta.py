import os
import requests
from datetime import datetime, timezone, timedelta

BASE_URL          = os.getenv("BASE_URL")
LOGIN             = os.getenv("LOGIN")
SENHA             = os.getenv("SENHA")
VDS_TABLE_ID      = 2
ACTION_THRESHOLD_ID = 1
JANELA_DIAS       = 7
CHUVA_LIMIAR_MM   = 30.0


# ── Autenticação ──────────────────────────────────────────────────────────────
def autenticar():
    r = requests.post(
        f"{BASE_URL}/accounts/login/",
        json={"username": LOGIN, "password": SENHA},
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    return body.get("token") or body.get("access")


# ── Talhões ───────────────────────────────────────────────────────────────────
def buscar_talhoes(token, field_id=None, farm_id=None):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/fields/"
    params = {}
    if field_id:
        params["id"] = field_id
    if farm_id:
        params["farm"] = farm_id

    talhoes = []
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        talhoes.extend(data.get("results", []))
        url = data.get("next")
        params = {}  # next já carrega os params na URL

    # Filtro local por field_id caso a API não suporte o parâmetro ?id=
    if field_id:
        talhoes = [t for t in talhoes if t["id"] == field_id]

    return talhoes


# ── Tabela VDS ────────────────────────────────────────────────────────────────
def buscar_tabela_vds(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(
        f"{BASE_URL}/diseases/vds-tables/{VDS_TABLE_ID}/",
        headers=headers,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["items"]


# ── Threshold de ação ─────────────────────────────────────────────────────────
def buscar_threshold(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(
        f"{BASE_URL}/diseases/action-thresholds/{ACTION_THRESHOLD_ID}/",
        headers=headers,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ── Histórico: VDS + chuva diária ────────────────────────────────────────────
def buscar_historico(token, field_id):
    """
    Retorna dict {date: {vds, chuva_mm, dia_chuvoso}} dos últimos JANELA_DIAS dias.
    VDS: method_c com fallback method_a.
    Chuva: accumulated_rain de method_d.
    """
    headers = {"Authorization": f"Bearer {token}"}
    desde = (datetime.now(timezone.utc) - timedelta(days=JANELA_DIAS)).strftime("%Y-%m-%d")
    url = f"{BASE_URL}/diseases/daily-records/?field={field_id}"
    historico = {}

    while url:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        for rec in data.get("results", []):
            if rec["date"] < desde:
                return historico

            vds = (rec.get("method_c") or {}).get("vds_dia")
            if vds is None:
                vds = (rec.get("method_a") or {}).get("vds_dia")

            chuva_mm = (rec.get("method_d") or {}).get("accumulated_rain") or 0.0
            historico[rec["date"]] = {
                "vds":         vds if vds is not None else 0,
                "chuva_mm":    chuva_mm,
                "dia_chuvoso": chuva_mm > CHUVA_LIMIAR_MM,
            }

        url = data.get("next")

    return historico
