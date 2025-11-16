from django.urls import path
from .views import nlp_intent

urlpatterns = [
    path("nlp/intent/", nlp_intent, name="nlp_intent"),
]
