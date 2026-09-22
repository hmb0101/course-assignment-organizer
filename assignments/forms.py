from django import forms
from django.utils import timezone

from .models import Assignment


class AssignmentForm(forms.ModelForm):
    steps = forms.CharField(
        label="任务步骤",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "每行填写一个步骤"}),
        help_text="每行填写一个步骤。",
    )

    class Meta:
        model = Assignment
        fields = [
            "course_name",
            "title",
            "deadline",
            "deliverables",
            "filename_rule",
            "source_text",
        ]
        widgets = {
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "deliverables": forms.Textarea(attrs={"rows": 3}),
            "source_text": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["steps"].initial = "\n".join(
                self.instance.steps.values_list("title", flat=True)
            )

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline < timezone.localdate():
            raise forms.ValidationError("截止时间不能早于今天。")
        return deadline

    def clean_steps(self):
        lines = [line.strip() for line in self.cleaned_data["steps"].splitlines() if line.strip()]
        if not lines:
            raise forms.ValidationError("至少填写一个任务步骤。")
        if len(lines) != len(set(lines)):
            raise forms.ValidationError("任务步骤不能重复。")
        return "\n".join(lines)

    def clean(self):
        cleaned = super().clean()
        course_name = cleaned.get("course_name", "").strip()
        title = cleaned.get("title", "").strip()
        deadline = cleaned.get("deadline")
        if course_name and title and deadline:
            duplicate = Assignment.objects.filter(
                course_name=course_name,
                title=title,
                deadline=deadline,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError("同一课程、作业名称和截止时间的记录已存在。")
        cleaned["course_name"] = course_name
        cleaned["title"] = title
        return cleaned
