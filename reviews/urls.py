from django.urls import path

from reviews import views

app_name = "reviews"

urlpatterns = [
    path("add/", views.add_review, name="add_review"),
]
