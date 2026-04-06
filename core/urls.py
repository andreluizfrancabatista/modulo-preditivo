from django.urls import path, include

urlpatterns = [
    # Rotas sem prefixo /preditivo/ — o Nginx já remove o prefixo via proxy_pass
    path("", include("preditivo.urls")),
]
