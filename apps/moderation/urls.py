from django.urls import path
from .views import SubmitFlagView

urlpatterns = [
    path("flag/", SubmitFlagView.as_view(), name="submit-flag"),
]