from django.shortcuts import render as django_render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests

from .services.pipeline import executar


def exemplo_view(request):
    return django_render(request, "preditivo/exemplo.html")


class PredicaoView(APIView):
    """
    GET /api/v1/predicao/

    Query params:
        field   — id do talhão          (ex: ?field=177)
        farm    — id da fazenda         (ex: ?farm=52)
        days    — horizonte 1–7 dias    (ex: ?days=7, padrão: 7)

    Os parâmetros são combináveis: ?farm=52&days=3
    """

    def get(self, request):
        # ── Validação dos parâmetros ──────────────────────────────────────────
        field_id = request.query_params.get("field")
        farm_id  = request.query_params.get("farm")
        days_raw = request.query_params.get("days", "7")

        try:
            days = int(days_raw)
            if not 1 <= days <= 7:
                raise ValueError
        except ValueError:
            return Response(
                {"error": "O parâmetro 'days' deve ser um inteiro entre 1 e 7."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if field_id is not None:
            try:
                field_id = int(field_id)
            except ValueError:
                return Response(
                    {"error": "O parâmetro 'field' deve ser um inteiro."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if farm_id is not None:
            try:
                farm_id = int(farm_id)
            except ValueError:
                return Response(
                    {"error": "O parâmetro 'farm' deve ser um inteiro."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Execução do pipeline ──────────────────────────────────────────────
        try:
            dados = executar(field_id=field_id, farm_id=farm_id, days=days)
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
            "count":      len(dados),
            "days":       days,
            "filters":    {"field": field_id, "farm": farm_id},
            "results":    dados,
        })
