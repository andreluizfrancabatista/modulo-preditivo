from django.shortcuts import render as django_render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests

from .services.pipeline import executar, executar_detalhado


def exemplo_view(request):
    return django_render(request, "preditivo/exemplo.html")


# ── Validação comum de query params ───────────────────────────────────────────
def _parse_params(query_params):
    """
    Retorna (field_id, farm_id, days) ou lança ValueError com mensagem.
    """
    days_raw = query_params.get("days", "7")
    try:
        days = int(days_raw)
        if not 1 <= days <= 7:
            raise ValueError
    except ValueError:
        raise ValueError("O parâmetro 'days' deve ser um inteiro entre 1 e 7.")

    field_id = query_params.get("field")
    if field_id is not None:
        try:
            field_id = int(field_id)
        except ValueError:
            raise ValueError("O parâmetro 'field' deve ser um inteiro.")

    farm_id = query_params.get("farm")
    if farm_id is not None:
        try:
            farm_id = int(farm_id)
        except ValueError:
            raise ValueError("O parâmetro 'farm' deve ser um inteiro.")

    return field_id, farm_id, days


def _handle_pipeline(request, pipeline_fn):
    """
    Valida params, executa o pipeline informado e retorna Response.
    """
    try:
        field_id, farm_id, days = _parse_params(request.query_params)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        dados = pipeline_fn(field_id=field_id, farm_id=farm_id, days=days)
    except requests.HTTPError as e:
        return Response(
            {"error": f"Erro ao chamar API externa: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except requests.Timeout:
        return Response(
            {"error": "Timeout ao chamar API externa."},
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro interno: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({
        "count":   len(dados),
        "days":    days,
        "filters": {"field": field_id, "farm": farm_id},
        "results": dados,
    })


# ── GET /api/v1/predicao/ ─────────────────────────────────────────────────────
class PredicaoView(APIView):
    """
    Estimativa básica de VDS, SRVDS e recomendação de pulverização.

    Query params:
        field   — id do talhão          (ex: ?field=177)
        farm    — id da fazenda         (ex: ?farm=52)
        days    — horizonte 1–7 dias    (ex: ?days=7, padrão: 7)
    """

    def get(self, request):
        return _handle_pipeline(request, executar)


# ── GET /api/v1/predicao/detalhada/ ──────────────────────────────────────────
class PredicaoDetalhadaView(APIView):
    """
    Mesmas informações de /predicao/ com adição do array 'methods'
    em cada entrada da série, contendo method_a, method_b, method_c e method_d
    no mesmo formato retornado por /diseases/daily-records/.

    method_a: up_dia, vds_dia, srup (acum. 7d), srvds
    method_b: vds_dia=None, svds=None (sem modelo preditivo)
    method_c: vds_dia, svds (acum. irrestrito), srvds
    method_d: campos None/False (aguardando especificação)

    Query params:
        field   — id do talhão          (ex: ?field=177)
        farm    — id da fazenda         (ex: ?farm=52)
        days    — horizonte 1–7 dias    (ex: ?days=7, padrão: 7)
    """

    def get(self, request):
        return _handle_pipeline(request, executar_detalhado)
