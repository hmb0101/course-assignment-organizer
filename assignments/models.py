from django.db import models
from django.utils import timezone


class Assignment(models.Model):
    course_name = models.CharField("课程名称", max_length=100)
    title = models.CharField("作业名称", max_length=150)
    deadline = models.DateField("截止时间")
    deliverables = models.TextField("提交物")
    submission_method = models.CharField("提交方式", max_length=255, blank=True)
    filename_rule = models.CharField("文件命名", max_length=255, blank=True)
    content_requirements = models.TextField("内容要求", blank=True)
    source_text = models.TextField("原始要求", blank=True)
    is_submitted = models.BooleanField("已提交", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["deadline", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["course_name", "title", "deadline"],
                name="unique_assignment_identity",
            )
        ]

    def __str__(self):
        return f"{self.course_name} - {self.title}"

    @property
    def progress_percent(self):
        total = getattr(self, "step_total", None)
        completed = getattr(self, "completed_total", None)
        if total is None:
            total = self.steps.count()
            completed = self.steps.filter(completed=True).count()
        return round(completed * 100 / total) if total else 0

    @property
    def is_complete(self):
        # Compatibility alias; legacy step completion never proves submission.
        return self.is_submitted

    @property
    def deadline_text(self):
        if self.is_submitted:
            return "已提交"
        days = (self.deadline - timezone.localdate()).days
        if days < 0:
            return f"已逾期 {abs(days)} 天"
        if days == 0:
            return "今天截止"
        if days == 1:
            return "明天截止"
        return f"还有 {days} 天"

    @property
    def deadline_state(self):
        if self.is_submitted:
            return "submitted"
        days = (self.deadline - timezone.localdate()).days
        if days < 0:
            return "overdue"
        if days == 0:
            return "today"
        if days == 1:
            return "urgent"
        return "normal"


class TaskStep(models.Model):
    assignment = models.ForeignKey(Assignment, related_name="steps", on_delete=models.CASCADE)
    title = models.CharField("任务步骤", max_length=200)
    sort_order = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title
