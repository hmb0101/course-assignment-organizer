import calendar
import logging
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from experiments.experiment7 import draft

from .forms import AssignmentForm
from .context_processors import course_counts, workspace_assignments
from .models import Assignment, TaskStep
from .services import create_assignment, update_assignment


logger = logging.getLogger("assignments")


def _calendar_date(value, *, month=False):
    """Accept only canonical, bounded dates from user-controlled query strings."""
    pattern = r"\d{4}-\d{2}" if month else r"\d{4}-\d{2}-\d{2}"
    if not re.fullmatch(pattern, value):
        return None
    try:
        parsed = date.fromisoformat(f"{value}-01" if month else value)
    except ValueError:
        return None
    return parsed if 1900 <= parsed.year <= 2100 else None


def _deadline_calendar(assignments, month, selected_day, today, filters):
    """Calendar scope excludes the selected day, but respects the other filters."""
    base_url = reverse("assignment_list")

    def calendar_url(target_month, target_day=None):
        params = {key: filters[key] for key in ("q", "course", "status") if filters[key]}
        params["month"] = target_month.strftime("%Y-%m")
        if target_day is not None:
            params["day"] = target_day.isoformat()
        return f"{base_url}?{urlencode(params)}"

    by_date = defaultdict(list)
    for assignment in assignments:
        by_date[assignment.deadline].append(assignment)

    weeks = []
    for week in calendar.Calendar(firstweekday=calendar.MONDAY).monthdatescalendar(month.year, month.month):
        days = []
        for day in week:
            items = by_date[day]
            pending = sum(not item.is_submitted for item in items)
            submitted = len(items) - pending
            state = "empty"
            if pending:
                days_left = (day - today).days
                state = "overdue" if days_left < 0 else "today" if days_left == 0 else "urgent" if days_left == 1 else "normal"
            elif submitted:
                state = "submitted"
            label = f"{day.year}年{day.month}月{day.day}日，{len(items)}项作业，待提交{pending}项，已提交{submitted}项"
            if day == today:
                label += "，今天"
            days.append({
                "date": day, "day": day.day, "in_month": day.month == month.month,
                "is_today": day == today, "is_selected": day == selected_day,
                "total": len(items), "pending": pending, "submitted": submitted,
                "state": state,
                "url": calendar_url(day.replace(day=1), day) if 1900 <= day.year <= 2100 else None,
                "label": label,
            })
        weeks.append(days)

    previous_month = (month - timedelta(days=1)).replace(day=1)
    next_month = (month + timedelta(days=32)).replace(day=1)
    month_assignments = [item for item in assignments if (item.deadline.year, item.deadline.month) == (month.year, month.month)]
    return {
        "calendar_weeks": weeks,
        "calendar_month": month.strftime("%Y-%m"),
        "calendar_month_label": f"{month.year}年{month.month}月",
        "previous_month_url": calendar_url(previous_month) if previous_month.year >= 1900 else None,
        "next_month_url": calendar_url(next_month) if next_month.year <= 2100 else None,
        "today_url": calendar_url(today.replace(day=1), today),
        "clear_day_url": calendar_url(month),
        "selected_day": selected_day,
        "calendar_pending_count": sum(not item.is_submitted for item in month_assignments),
        "calendar_submitted_count": sum(item.is_submitted for item in month_assignments),
    }


def assignment_list(request):
    all_assignments = workspace_assignments(request)
    today = timezone.localdate()
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    if status not in {"all", "active", "done"}:
        status = "all"
    course = request.GET.get("course", "").strip()
    assignments = sorted(all_assignments, key=lambda item: (item.is_complete, item.deadline, item.pk))
    if query:
        needle = query.casefold()
        assignments = [
            item for item in assignments
            if any(needle in value.casefold() for value in (
                item.title, item.course_name, item.deliverables, item.content_requirements,
            ))
        ]
    if course:
        assignments = [item for item in assignments if item.course_name == course]
    selected_day = _calendar_date(request.GET.get("day", ""))
    requested_month = _calendar_date(request.GET.get("month", ""), month=True)
    month = requested_month or (selected_day or today).replace(day=1)
    if selected_day and requested_month and selected_day.replace(day=1) != month:
        selected_day = None
    filters = {
        "q": query, "status": status, "course": course,
        "month": month.strftime("%Y-%m"), "day": selected_day.isoformat() if selected_day else "",
    }
    calendar_assignments = assignments
    if status == "active":
        calendar_assignments = [item for item in assignments if not item.is_submitted]
    elif status == "done":
        calendar_assignments = [item for item in assignments if item.is_submitted]
    calendar_context = _deadline_calendar(calendar_assignments, month, selected_day, today, filters)
    if selected_day:
        assignments = [item for item in assignments if item.deadline == selected_day]
    tab_all_count = len(assignments)
    tab_done_count = sum(item.is_submitted for item in assignments)
    tab_active_count = tab_all_count - tab_done_count
    if status == "active":
        assignments = [item for item in assignments if not item.is_complete]
    elif status == "done":
        assignments = [item for item in assignments if item.is_complete]
    done_count = sum(item.is_complete for item in all_assignments)
    context = {
        "assignments": assignments,
        "assignment_total": len(all_assignments),
        "active_count": len(all_assignments) - done_count,
        "done_count": done_count,
        "overdue_count": sum(item.deadline < today and not item.is_complete for item in all_assignments),
        "urgent_count": sum(
            today <= item.deadline <= today + timedelta(days=1) and not item.is_submitted
            for item in all_assignments
        ),
        "tab_all_count": tab_all_count,
        "tab_active_count": tab_active_count,
        "tab_done_count": tab_done_count,
        "courses": course_counts(all_assignments),
        "filters": filters,
        "current_date": today,
        **calendar_context,
    }
    return render(request, "assignments/list.html", context)


def assignment_create(request):
    if request.method == "POST" and request.POST.get("action") == "draft":
        original = request.POST.get("source_text", "")
        env = Path(os.environ.get("ASSIGNMENT_AI_ENV", draft.ROOT / ".env"))
        result = draft.make_draft(original, "text", env)
        initial = {name: request.POST.get(name, "") for name in AssignmentForm.Meta.fields}
        for name, value in result["form_seed"].items():
            if not initial[name].strip():
                initial[name] = value
        review = [draft.LABELS[name] for name in result["uncertain_fields"] if name in draft.LABELS]
        logger.info(
            "assignment_draft status=%s error=%s calls=%d elapsed_ms=%s",
            result["status"], result["error"], result["calls"], result["elapsed_ms"],
        )
        return render(request, "assignments/form.html", {
            "form": AssignmentForm(initial=initial),
            "draft_result": result,
            "draft_review": review,
            "review_deadline": "deadline" in result["uncertain_fields"] and not initial["deadline"],
        })
    form = AssignmentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        assignment = create_assignment(form.cleaned_data.copy())
        logger.info("assignment_created id=%s title=%s", assignment.pk, assignment.title)
        messages.success(request, "作业已保存。")
        return redirect("assignment_detail", pk=assignment.pk)
    return render(request, "assignments/form.html", {"form": form})


def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
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
def assignment_submission(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    action = request.POST.get("action")
    if action not in {"submit", "reopen"}:
        return HttpResponseBadRequest("无效的提交状态操作。")
    assignment.is_submitted = action == "submit"
    assignment.save(update_fields=["is_submitted"])
    logger.info("assignment_submission_changed id=%s submitted=%s", assignment.pk, assignment.is_submitted)
    messages.success(request, "已标记为已提交。" if assignment.is_submitted else "已恢复为待提交。")
    return redirect("assignment_detail", pk=assignment.pk)


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
    if request.POST.get("return_to") == "list":
        return redirect(f"{reverse('assignment_list')}?selected={step.assignment_id}")
    return redirect("assignment_detail", pk=step.assignment_id)


def custom_404(request, exception):
    logger.warning("page_not_found path=%s", request.path)
    return render(request, "404.html", status=404)
