from django import forms
from django.utils import timezone

from .models import Assignment


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = [
            "course_name",
            "title",
            "deadline",
            "deliverables",
            "submission_method",
            "filename_rule",
            "content_requirements",
            "source_text",
        ]
        widgets = {
            "deadline": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "course_name": forms.TextInput(attrs={"placeholder": "例如：软件应用开发实践"}),
            "title": forms.TextInput(attrs={"placeholder": "填写作业或实验名称"}),
            "filename_rule": forms.TextInput(attrs={"placeholder": "例如：学号-姓名-实验名称.pdf"}),
            "submission_method": forms.TextInput(attrs={"placeholder": "例如：学习通对应作业入口"}),
            "deliverables": forms.Textarea(attrs={"rows": 2, "placeholder": "需要提交哪些文件？"}),
            "content_requirements": forms.Textarea(attrs={"rows": 5, "placeholder": "记录报告内容、小问、格式等要求，无需拆分任务步骤。"}),
            "source_text": forms.Textarea(attrs={"rows": 15, "placeholder": "在这里粘贴老师发布的作业要求。\n\n建议保留：\n截止时间、提交方式、文件格式、命名规则和评分要求。"}),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        unchanged_existing = self.instance.pk and deadline == self.instance.deadline
        if deadline < timezone.localdate() and not unchanged_existing:
            raise forms.ValidationError("截止时间不能早于今天。")
        return deadline

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
