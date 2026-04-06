JANELA_DIAS = 7

RECOMENDACOES = {
    -1: "Não pulverizar",
     0: "Alerta",
     1: "Pulverizar a cada 7 dias",
     2: "Pulverizar a cada 5 dias",
}


def calcular_vds(temp, pmf_horas, tabela_vds):
    """
    Dado avg_temperature e total_horas_molhamento do dia,
    retorna o VDS correspondente na tabela (0, 1, 2 ou 3).
    """
    for item in tabela_vds:
        if (float(item["min_temp"]) <= temp <= float(item["max_temp"]) and
                float(item["min_pmf"]) <= pmf_horas <= float(item["max_pmf"])):
            return item["value"]
    return 0


def calcular_recomendacao(srvds, dias_chuva, threshold):
    """
    Mapeia srvds → coluna e dias_chuva → linha na matriz do threshold.
    Retorna dict com codigo, texto, labels.
    """
    ax_x   = threshold["axis_x_config"]   # srvds
    ax_y   = threshold["axis_y_config"]   # dias de chuva
    matrix = threshold["results_matrix"]["results"]

    # Coluna (SRVDS) — percorre breaks até encontrar o intervalo
    breaks_x = ax_x["breaks"]
    col = len(breaks_x) - 2  # default: última coluna
    for i in range(1, len(breaks_x) - 1):
        if breaks_x[i] is not None and srvds < breaks_x[i]:
            col = i - 1
            break

    # Linha (dias de chuva) — breaks: [None, 4, None] → label '>= 5' se dias >= 5
    breaks_y = ax_y["breaks"]
    linha = 0
    for i in range(1, len(breaks_y) - 1):
        if breaks_y[i] is not None and dias_chuva >= breaks_y[i] + 1:
            linha = i

    codigo = matrix[linha][col]
    return {
        "codigo":      codigo,
        "texto":       RECOMENDACOES.get(codigo, "Desconhecido"),
        "srvds_label": ax_x["labels"][col],
        "chuva_label": ax_y["labels"][linha],
    }


def calcular_serie(serie, threshold):
    """
    Recebe lista ordenada de dicts com {date, vds_estimado, dia_chuvoso, ...}.
    Adiciona srvds, chuva_last_7 e recomendacao em cada entrada.
    """
    ax_y = threshold["axis_y_config"]

    for i, dia in enumerate(serie):
        janela     = serie[max(0, i - JANELA_DIAS + 1): i + 1]
        srvds      = sum(d["vds_estimado"] for d in janela)
        dias_chuva = sum(1 for d in janela if d["dia_chuvoso"])
        label_y    = ax_y["labels"][0 if dias_chuva < 5 else 1]

        dia["srvds"] = srvds
        dia["chuva_last_7"] = {
            "dias_chuva": dias_chuva,
            "label":      label_y,
        }
        dia["recomendacao"] = calcular_recomendacao(srvds, dias_chuva, threshold)

    return serie
