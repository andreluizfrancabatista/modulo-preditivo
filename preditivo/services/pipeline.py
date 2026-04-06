from datetime import datetime, timezone
from .climacta import (
    autenticar, buscar_talhoes, buscar_tabela_vds,
    buscar_threshold, buscar_historico,
)
from .owm import buscar_previsao, estimar_dias_futuros
from .vds import calcular_vds, calcular_serie


def executar(field_id=None, farm_id=None, days=7):
    """
    Pipeline principal do módulo preditivo.

    Parâmetros:
        field_id  — filtra por talhão (int ou None)
        farm_id   — filtra por fazenda (int ou None)
        days      — horizonte de previsão em dias (1–7)

    Retorna lista de dicts, um por talhão.
    """
    days  = max(1, min(days, 7))
    hoje  = datetime.now(timezone.utc).date().isoformat()
    token = autenticar()

    talhoes    = buscar_talhoes(token, field_id=field_id, farm_id=farm_id)
    tabela_vds = buscar_tabela_vds(token)
    threshold  = buscar_threshold(token)

    resultado = []

    for talhao in talhoes:
        historico    = buscar_historico(token, talhao["id"])
        blocos       = buscar_previsao(talhao["latitude"], talhao["longitude"], days=days)
        dias_futuros = estimar_dias_futuros(blocos)

        serie = []

        # Histórico real (últimos 7 dias)
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

        # Estimativa futura (somente após hoje, dentro do horizonte solicitado)
        dias_futuros_filtrados = [d for d in dias_futuros if d["date"] > hoje][:days]

        for dia in dias_futuros_filtrados:
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
        serie = calcular_serie(serie, threshold)

        resultado.append({
            "id":      talhao["id"],
            "talhao":  talhao["name"],
            "fazenda": talhao["farm"],
            "cultivo": talhao.get("crop_type"),
            "serie":   serie,
        })

    return resultado
