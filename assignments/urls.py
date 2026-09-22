from django.urls import path

from . import views


urlpatterns = [
    path("", views.assignment_list, name="assignment_list"),
    path("assignments/new/", views.assignment_create, name="assignment_create"),
    path("assignments/<int:pk>/", views.assignment_detail, name="assignment_detail"),
]

