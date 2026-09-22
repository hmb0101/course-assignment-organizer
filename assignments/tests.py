from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Assignment, TaskStep


class AssignmentFlowTests(TestCase):
    def setUp(self):
        self.deadline = timezone.localdate() + timedelta(days=7)
        self.assignment = Assignment.objects.create(
            course_name="软件应用开发实践",
            title="实验4",
            deadline=self.deadline,
            deliverables="实验报告",
        )
        self.step = TaskStep.objects.create(assignment=self.assignment, title="实现功能", sort_order=1)

    def valid_payload(self, **overrides):
        data = {
            "course_name": "软件工程",
            "title": "需求分析",
            "deadline": self.deadline.isoformat(),
            "deliverables": "Word报告",
            "filename_rule": "学号-姓名.docx",
            "source_text": "完成需求分析。",
            "steps": "整理要求\n编写报告",
        }
        data.update(overrides)
        return data

    def test_empty_list_page_has_clear_prompt(self):
        Assignment.objects.all().delete()
        response = self.client.get(reverse("assignment_list"))
        self.assertContains(response, "还没有作业")

    def test_create_assignment_and_steps(self):
        response = self.client.post(reverse("assignment_create"), self.valid_payload())
        created = Assignment.objects.get(title="需求分析")
        self.assertRedirects(response, reverse("assignment_detail", args=[created.pk]))
        self.assertEqual(created.steps.count(), 2)

    def test_required_fields_show_validation_errors(self):
        response = self.client.post(reverse("assignment_create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "这个字段是必填项")

    def test_past_deadline_is_rejected(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.post(reverse("assignment_create"), self.valid_payload(deadline=yesterday))
        self.assertContains(response, "截止时间不能早于今天")

    def test_duplicate_assignment_is_rejected(self):
        payload = self.valid_payload(
            course_name=self.assignment.course_name,
            title=self.assignment.title,
            deadline=self.assignment.deadline.isoformat(),
        )
        response = self.client.post(reverse("assignment_create"), payload)
        self.assertContains(response, "记录已存在")
        self.assertEqual(Assignment.objects.count(), 1)

    def test_edit_assignment_replaces_steps(self):
        response = self.client.post(
            reverse("assignment_edit", args=[self.assignment.pk]),
            self.valid_payload(title="实验4修订版", steps="修复问题\n重新测试"),
        )
        self.assertRedirects(response, reverse("assignment_detail", args=[self.assignment.pk]))
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.title, "实验4修订版")
        self.assertEqual(list(self.assignment.steps.values_list("title", flat=True)), ["修复问题", "重新测试"])

    def test_toggle_requires_post_and_changes_state(self):
        url = reverse("step_toggle", args=[self.step.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.step.refresh_from_db()
        self.assertTrue(self.step.completed)

    def test_delete_requires_post(self):
        url = reverse("assignment_delete", args=[self.assignment.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(Assignment.objects.filter(pk=self.assignment.pk).exists())

    def test_missing_assignment_returns_404(self):
        response = self.client.get(reverse("assignment_detail", args=[99999]))
        self.assertEqual(response.status_code, 404)
