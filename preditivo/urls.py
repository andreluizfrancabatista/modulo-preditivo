from django.urls import path
from .views import PredicaoView, exemplo_view

urlpatterns = [
    path("api/v1/predicao/", PredicaoView.as_view(), name="predicao"),
    path("exemplo/",         exemplo_view,           name="exemplo"),
]
