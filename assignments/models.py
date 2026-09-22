from django.db import models


class Assignment(models.Model):
    course_name = models.CharField("课程名称", max_length=100)
    title = models.CharField("作业名称", max_length=150)
    deadline = models.DateField("截止时间")
    deliverables = models.TextField("提交物")
    filename_rule = models.CharField("文件命名", max_length=255, blank=True)
    source_text = models.TextField("原始要求", blank=True)
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


class TaskStep(models.Model):
    assignment = models.ForeignKey(Assignment, related_name="steps", on_delete=models.CASCADE)
    title = models.CharField("任务步骤", max_length=200)
    sort_order = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title
