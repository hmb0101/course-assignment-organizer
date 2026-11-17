from django.urls import path

from . import views
from .requirements_qa import requirements_qa


urlpatterns = [
    path("", views.assignment_list, name="assignment_list"),
    path("assignments/new/", views.assignment_create, name="assignment_create"),
    path("requirements/", requirements_qa, name="requirements_qa"),
    path("assignments/<int:pk>/", views.assignment_detail, name="assignment_detail"),
    path("assignments/<int:pk>/edit/", views.assignment_edit, name="assignment_edit"),
    path("assignments/<int:pk>/submission/", views.assignment_submission, name="assignment_submission"),
    path("assignments/<int:pk>/delete/", views.assignment_delete, name="assignment_delete"),
    path("steps/<int:pk>/toggle/", views.step_toggle, name="step_toggle"),
]
