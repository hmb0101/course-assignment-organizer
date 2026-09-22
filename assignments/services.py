from django.db import transaction

from .models import Assignment, TaskStep


@transaction.atomic
def create_assignment(cleaned_data):
    steps_text = cleaned_data.pop("steps")
    assignment = Assignment.objects.create(**cleaned_data)
    steps = (line.strip() for line in steps_text.splitlines() if line.strip())
    for index, title in enumerate(steps, start=1):
        TaskStep.objects.create(assignment=assignment, title=title, sort_order=index)
    return assignment


@transaction.atomic
def update_assignment(assignment, cleaned_data):
    steps_text = cleaned_data.pop("steps")
    for field, value in cleaned_data.items():
        setattr(assignment, field, value)
    assignment.save()
    assignment.steps.all().delete()
    steps = (line.strip() for line in steps_text.splitlines() if line.strip())
    TaskStep.objects.bulk_create(
        [TaskStep(assignment=assignment, title=title, sort_order=index) for index, title in enumerate(steps, start=1)]
    )
    return assignment
