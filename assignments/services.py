from django.db import transaction

from .models import Assignment, TaskStep


@transaction.atomic
def create_assignment(cleaned_data):
    values = cleaned_data.copy()
    # Older callers may still supply steps. The current form never requires them.
    steps_text = values.pop("steps", "")
    assignment = Assignment.objects.create(**values)
    steps = (line.strip() for line in steps_text.splitlines() if line.strip())
    for index, title in enumerate(steps, start=1):
        TaskStep.objects.create(assignment=assignment, title=title, sort_order=index)
    return assignment


@transaction.atomic
def update_assignment(assignment, cleaned_data):
    values = cleaned_data.copy()
    values.pop("steps", None)
    for field, value in values.items():
        setattr(assignment, field, value)
    assignment.save()
    # TaskStep rows are legacy data, retained intact when editing requirements.
    return assignment
