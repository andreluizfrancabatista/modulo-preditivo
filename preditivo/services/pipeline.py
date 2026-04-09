from datetime import datetime, timezone
from .climacta import (
    autenticar, buscar_talhoes, buscar_tabela_vds,
    buscar_threshold, buscar_historico,
)
from .owm import buscar_previsao, estimar_dias_futuros
from .vds import calcular_vds, calcular_serie, calcular_serie_detalhada


# ── Monta série base comum aos dois pipelines ─────────────────────────────────
def _montar_serie(talhao, historico, dias_futuros, tabela_vds, hoje, days):
    serie = []

    for data in sorted(historico):
        h = historico[data]
        serie.append({
            "date":         data,
            "vds_estimado": h["vds"],
            "pmf_horas":    None,
            "avg_temp":     None,
            "chuva_mm":     h["chuva_mm"],
            "dia_chuvoso":  h["dia_chuvoso"],
            "estimado":     False,
        })

    for dia in [d for d in dias_futuros if d["date"] > hoje][:days]:
        avg_temp  = dia["avg_temp_dia"] or 0.0
        pmf_horas = dia["total_horas_molhamento"]
        vds       = calcular_vds(avg_temp, pmf_horas, tabela_vds)
        serie.append({
            "date":         dia["date"],
            "vds_estimado": vds,
            "pmf_horas":    pmf_horas,
            "avg_temp":     avg_temp,
            "chuva_mm":     dia["chuva_mm"],
            "dia_chuvoso":  dia["dia_chuvoso"],
            "pmf_periodos": dia["pmf_estimado"],
            "estimado":     True,
        })

    serie.sort(key=lambda d: d["date"])
    return serie


# ── Busca dados externos (reutilizável) ───────────────────────────────────────
def _buscar_dados(field_id, farm_id, days):
    days  = max(1, min(days, 7))
    hoje  = datetime.now(timezone.utc).date().isoformat()
    token = autenticar()

    talhoes    = buscar_talhoes(token, field_id=field_id, farm_id=farm_id)
    tabela_vds = buscar_tabela_vds(token)
    threshold  = buscar_threshold(token)

    return token, talhoes, tabela_vds, threshold, hoje, days


# ── Pipeline 1: rota /predicao/ ───────────────────────────────────────────────
def executar(field_id=None, farm_id=None, days=7):
    """
    Retorna estimativa básica: vds_estimado, srvds, chuva_last_7, recomendacao.
    """
    token, talhoes, tabela_vds, threshold, hoje, days = _buscar_dados(
        field_id, farm_id, days
    )
    resultado = []

    for talhao in talhoes:
        historico    = buscar_historico(token, talhao["id"])
        blocos       = buscar_previsao(talhao["latitude"], talhao["longitude"], days=days)
        dias_futuros = estimar_dias_futuros(blocos)

        serie = _montar_serie(talhao, historico, dias_futuros, tabela_vds, hoje, days)
        serie = calcular_serie(serie, threshold)

        resultado.append({
            "id":      talhao["id"],
            "talhao":  talhao["name"],
            "fazenda": talhao["farm"],
            "cultivo": talhao.get("crop_type"),
            "serie":   serie,
        })

    return resultado


# ── Pipeline 2: rota /predicao/detalhada/ ────────────────────────────────────
def executar_detalhado(field_id=None, farm_id=None, days=7):
    """
    Retorna tudo de /predicao/ mais o array 'methods' com
    method_a, method_b, method_c, method_d em cada entrada da série.
    """
    token, talhoes, tabela_vds, threshold, hoje, days = _buscar_dados(
        field_id, farm_id, days
    )
    resultado = []

    for talhao in talhoes:
        historico    = buscar_historico(token, talhao["id"])
        blocos       = buscar_previsao(talhao["latitude"], talhao["longitude"], days=days)
        dias_futuros = estimar_dias_futuros(blocos)

        serie = _montar_serie(talhao, historico, dias_futuros, tabela_vds, hoje, days)
        serie = calcular_serie_detalhada(serie, threshold)

        resultado.append({
            "id":      talhao["id"],
            "talhao":  talhao["name"],
            "fazenda": talhao["farm"],
            "cultivo": talhao.get("crop_type"),
            "serie":   serie,
        })

    return resultado
