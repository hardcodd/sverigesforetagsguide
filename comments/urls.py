from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("add/", views.add_comment, name="add_comment"),
    path("header/", views.count_header, name="header"),
    path("delete/<int:comment_id>/", views.delete_comment, name="delete_comment"),
    path("publish/<int:comment_id>", views.publish_comment, name="publish_comment"),
    path("reject/<int:comment_id>", views.reject_comment, name="reject_comment"),
    path("delete/<int:comment_id>", views.delete_comment, name="delete_comment"),
]
