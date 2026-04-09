from django.urls import path
from .views import PredicaoView, PredicaoDetalhadaView, exemplo_view

urlpatterns = [
    path("api/v1/predicao/",            PredicaoView.as_view(),          name="predicao"),
    path("api/v1/predicao/detalhada/",  PredicaoDetalhadaView.as_view(), name="predicao-detalhada"),
    path("exemplo/",                    exemplo_view,                    name="exemplo"),
]
