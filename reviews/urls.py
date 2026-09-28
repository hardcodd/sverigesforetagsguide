from django.urls import path

from reviews import views

app_name = "reviews"

urlpatterns = [
    path("add/", views.add_review, name="add_review"),
    path("delete/<int:review_id>/", views.delete_review, name="delete_review"),
    path("publish/<int:review_id>", views.publish_review, name="publish_review"),
    path("reject/<int:review_id>", views.reject_review, name="reject_review"),
    path("delete/<int:review_id>", views.delete_review, name="delete_review"),
    path("load-more/", views.load_more_reviews, name="load_more_reviews"),
    path("import-review/", views.import_review, name="import_review"),
]
