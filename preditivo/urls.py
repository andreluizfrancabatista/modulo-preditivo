from django.urls import path
from .views import PredicaoView

urlpatterns = [
    path("predicao/", PredicaoView.as_view(), name="predicao"),
]
