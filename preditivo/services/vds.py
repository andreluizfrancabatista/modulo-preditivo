JANELA_DIAS  = 7
UP_DIVISOR   = 2.984   # constante method_a

RECOMENDACOES = {
    -1: "Não pulverizar",
     0: "Alerta",
     1: "Pulverizar a cada 7 dias",
     2: "Pulverizar a cada 5 dias",
}


# ── VDS básico ────────────────────────────────────────────────────────────────
def calcular_vds(temp, pmf_horas, tabela_vds):
    """
    Dado avg_temp e total_horas_molhamento do dia,
    retorna o VDS correspondente na tabela (0, 1, 2 ou 3).
    """
    for item in tabela_vds:
        if (float(item["min_temp"]) <= temp <= float(item["max_temp"]) and
                float(item["min_pmf"]) <= pmf_horas <= float(item["max_pmf"])):
            return item["value"]
    return 0


# ── Recomendação ──────────────────────────────────────────────────────────────
def calcular_recomendacao(srvds, dias_chuva, threshold):
    ax_x   = threshold["axis_x_config"]
    ax_y   = threshold["axis_y_config"]
    matrix = threshold["results_matrix"]["results"]

    breaks_x = ax_x["breaks"]
    col = len(breaks_x) - 2
    for i in range(1, len(breaks_x) - 1):
        if breaks_x[i] is not None and srvds < breaks_x[i]:
            col = i - 1
            break

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


# ── AD (alerta de decisão) ────────────────────────────────────────────────────
# Matriz:
#              SRUP <= 60   61–80   > 80      (colunas)
# SRVDS  < 9      -1         0       1
# SRVDS  9–15      0         0       1
# SRVDS  > 15      1         1       1

_AD_MATRIX = [
    [-1, 0, 1],
    [ 0, 0, 1],
    [ 1, 1, 1],
]

def calcular_ad(srup, srvds):
    """
    Mapeia srup → coluna e srvds → linha na matriz AD.
    Retorna -1, 0 ou 1.
    """
    if srup <= 60:
        col = 0
    elif srup <= 80:
        col = 1
    else:
        col = 2

    if srvds < 9:
        linha = 0
    elif srvds <= 15:
        linha = 1
    else:
        linha = 2

    return _AD_MATRIX[linha][col]


# ── Série base (rota /predicao/) ──────────────────────────────────────────────
def calcular_serie(serie, threshold):
    """
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


# ── Série detalhada (rota /predicao/detalhada/) ───────────────────────────────
def calcular_serie_detalhada(serie, threshold):
    """
    Estende cada entrada da série com os quatro métodos no mesmo
    formato do /diseases/daily-records/, acrescidos de 'ad' e 'am'.

    method_a:
        up_dia  = 0 se vds_dia == 0, senão avg_temp / UP_DIVISOR
        vds_dia = vds_estimado
        srup    = soma acumulativa dos últimos 7 dias de up_dia
        srvds   = soma acumulativa dos últimos 7 dias de vds_dia
        ad      = matriz AD(srup, srvds) → -1, 0 ou 1
        am      = None

    method_b:
        ad = None, am = None

    method_c:
        vds_dia = vds_estimado
        svds    = soma acumulativa de TODOS os vds disponíveis até o dia
        srvds   = mesmo que method_a.srvds
        ad      = matriz AD(srup, srvds) — mesmo srup do method_a
        am      = None

    method_d:
        tudo None / False (aguardando especificação)
        ad = None, am = None
    """
    # Primeiro passo: base (srvds, recomendacao, chuva_last_7)
    calcular_serie(serie, threshold)

    # Segundo passo: métodos detalhados
    svds_acum = 0.0   # acumulado irrestrito para method_c.svds

    for i, dia in enumerate(serie):
        vds_dia  = dia["vds_estimado"]
        avg_temp = dia.get("avg_temp") or 0.0

        # ── up_dia ───────────────────────────────────────────────────────────
        up_dia = 0.0 if vds_dia == 0 else round(avg_temp / UP_DIVISOR, 4)

        # ── srup: soma dos últimos 7 up_dia (incluindo o atual) ──────────────
        janela_up = [serie[j].get("_up_dia", 0.0)
                     for j in range(max(0, i - JANELA_DIAS + 1), i)]
        janela_up.append(up_dia)
        srup = round(sum(janela_up), 4)

        # ── srvds: janela 7 dias (já calculado em calcular_serie) ────────────
        srvds = dia["srvds"]

        # ── svds acumulativo irrestrito (method_c) ────────────────────────────
        svds_acum = round(svds_acum + vds_dia, 4)

        # ── AD (compartilhado por method_a e method_c) ────────────────────────
        ad = calcular_ad(srup, srvds)

        # Salva up_dia para iterações seguintes calcularem srup
        dia["_up_dia"] = up_dia

        dia["methods"] = {
            "method_a": {
                "up_dia":         up_dia,
                "vds_dia":        vds_dia,
                "srup":           srup,
                "srvds":          srvds,
                "teve_aplicacao": False,
                "sob_protecao":   False,
                "ad":             ad,
                "am":             None,
            },
            "method_b": {
                "vds_dia":        None,
                "svds":           None,
                "teve_aplicacao": False,
                "sob_protecao":   False,
                "ad":             None,
                "am":             None,
            },
            "method_c": {
                "vds_dia":        vds_dia,
                "svds":           svds_acum,
                "srvds":          srvds,
                "teve_aplicacao": False,
                "sob_protecao":   False,
                "ad":             ad,
                "am":             None,
            },
            "method_d": {
                "df":                  None,
                "svds":                None,
                "srdf":                None,
                "vds_day":             None,
                "accumulated_rain":    None,
                "is_rainy_day":        False,
                "rain_days_count":     None,
                "hours_high_humidity": None,
                "hours_low_humidity":  None,
                "teve_aplicacao":      False,
                "sob_protecao":        False,
                "ad":                  None,
                "am":                  None,
            },
        }

    # Remove campo auxiliar temporário
    for dia in serie:
        dia.pop("_up_dia", None)

    return serie
