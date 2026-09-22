import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AssignmentForm
from .models import Assignment, TaskStep
from .services import create_assignment, update_assignment


logger = logging.getLogger("assignments")


def assignment_list(request):
    return render(request, "assignments/list.html", {"assignments": Assignment.objects.prefetch_related("steps")})


def assignment_create(request):
    form = AssignmentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        assignment = create_assignment(form.cleaned_data.copy())
        logger.info("assignment_created id=%s title=%s", assignment.pk, assignment.title)
        messages.success(request, "作业已保存。")
        return redirect("assignment_detail", pk=assignment.pk)
    return render(request, "assignments/form.html", {"form": form})


def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.prefetch_related("steps"), pk=pk)
    return render(request, "assignments/detail.html", {"assignment": assignment})


def assignment_edit(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    form = AssignmentForm(request.POST if request.method == "POST" else None, instance=assignment)
    if request.method == "POST" and form.is_valid():
        update_assignment(assignment, form.cleaned_data.copy())
        logger.info("assignment_updated id=%s", assignment.pk)
        messages.success(request, "作业已更新。")
        return redirect("assignment_detail", pk=assignment.pk)
    return render(request, "assignments/form.html", {"form": form, "assignment": assignment})


@require_POST
def assignment_delete(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    title = assignment.title
    assignment.delete()
    logger.info("assignment_deleted title=%s", title)
    messages.success(request, "作业已删除。")
    return redirect("assignment_list")


@require_POST
def step_toggle(request, pk):
    step = get_object_or_404(TaskStep, pk=pk)
    step.completed = not step.completed
    step.save(update_fields=["completed"])
    logger.info("step_toggled id=%s completed=%s", step.pk, step.completed)
    return redirect("assignment_detail", pk=step.assignment_id)


def custom_404(request, exception):
    logger.warning("page_not_found path=%s", request.path)
    return render(request, "404.html", status=404)
