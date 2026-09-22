from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AssignmentForm
from .models import Assignment
from .services import create_assignment


def assignment_list(request):
    return render(request, "assignments/list.html", {"assignments": Assignment.objects.prefetch_related("steps")})


def assignment_create(request):
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assignment = create_assignment(form.cleaned_data.copy())
        messages.success(request, "作业已保存。")
        return redirect("assignment_detail", pk=assignment.pk)
    return render(request, "assignments/form.html", {"form": form})


def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.prefetch_related("steps"), pk=pk)
    return render(request, "assignments/detail.html", {"assignment": assignment})

