from django import forms

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

