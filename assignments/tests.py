from datetime import date, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import AssignmentForm
from .models import Assignment, TaskStep
from .services import create_assignment, update_assignment


class AssignmentFlowTests(TestCase):
    def setUp(self):
        self.deadline = timezone.localdate() + timedelta(days=7)
        self.assignment = Assignment.objects.create(
            course_name="软件应用开发实践", title="实验4",
            deadline=self.deadline, deliverables="实验报告",
        )
        self.step = TaskStep.objects.create(assignment=self.assignment, title="实现功能", sort_order=1)

    def valid_payload(self, **overrides):
        data = {
            "course_name": "软件工程", "title": "需求分析",
            "deadline": self.deadline.isoformat(), "deliverables": "Word报告",
            "submission_method": "学习通", "filename_rule": "学号-姓名.docx",
            "content_requirements": "说明用户需求，给出验收条件。",
            "source_text": "完成需求分析。",
        }
        data.update(overrides)
        return data

    def test_empty_list_page_has_zero_counts(self):
        Assignment.objects.all().delete()
        response = self.client.get(reverse("assignment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assignments"], [])
        self.assertEqual(response.context["tab_all_count"], 0)

    def test_create_assignment_without_steps(self):
        response = self.client.post(reverse("assignment_create"), self.valid_payload())
        created = Assignment.objects.get(title="需求分析")
        self.assertRedirects(response, reverse("assignment_detail", args=[created.pk]))
        self.assertEqual(created.steps.count(), 0)
        self.assertFalse(created.is_submitted)
        self.assertEqual(created.submission_method, "学习通")
        self.assertIn("验收条件", created.content_requirements)
        self.assertNotIn("steps", AssignmentForm().fields)

    def test_optional_requirements_can_be_empty(self):
        form = AssignmentForm(self.valid_payload(submission_method="", content_requirements=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_required_fields_show_validation_errors(self):
        response = self.client.post(reverse("assignment_create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.context["form"].errors)
        self.assertIn("deadline", response.context["form"].errors)

    def test_past_deadline_is_rejected_for_new_record(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.post(reverse("assignment_create"), self.valid_payload(deadline=yesterday))
        self.assertIn("截止时间不能早于今天", str(response.context["form"].errors))

    def test_overdue_record_can_edit_requirements_without_changing_deadline(self):
        self.assignment.deadline = timezone.localdate() - timedelta(days=1)
        self.assignment.save(update_fields=["deadline"])
        response = self.client.post(
            reverse("assignment_edit", args=[self.assignment.pk]),
            self.valid_payload(title="补充要求", deadline=self.assignment.deadline.isoformat()),
        )
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.title, "补充要求")

    def test_duplicate_assignment_is_rejected(self):
        payload = self.valid_payload(course_name=self.assignment.course_name, title=self.assignment.title)
        response = self.client.post(reverse("assignment_create"), payload)
        self.assertIn("记录已存在", str(response.context["form"].errors))
        self.assertEqual(Assignment.objects.count(), 1)

    def test_edit_assignment_preserves_legacy_steps_and_submission_state(self):
        self.assignment.is_submitted = True
        self.assignment.save(update_fields=["is_submitted"])
        self.step.completed = True
        self.step.save(update_fields=["completed"])
        response = self.client.post(
            reverse("assignment_edit", args=[self.assignment.pk]),
            self.valid_payload(title="实验4修订版", steps="这项旧字段应忽略"),
        )
        self.assertRedirects(response, reverse("assignment_detail", args=[self.assignment.pk]))
        self.assignment.refresh_from_db()
        self.step.refresh_from_db()
        self.assertEqual(self.assignment.title, "实验4修订版")
        self.assertTrue(self.assignment.is_submitted)
        self.assertTrue(self.step.completed)
        self.assertEqual(self.step.title, "实现功能")
        self.assertEqual(self.assignment.steps.count(), 1)

    def test_service_legacy_calls_do_not_mutate_input_or_delete_steps(self):
        data = {"title": "新的名字", "steps": "不要替换旧数据"}
        update_assignment(self.assignment, data)
        self.assertIn("steps", data)
        self.assertTrue(TaskStep.objects.filter(pk=self.step.pk).exists())
        create_data = {
            "course_name": "旧接口", "title": "兼容测试", "deadline": self.deadline,
            "deliverables": "报告", "steps": "旧步骤一\n旧步骤二",
        }
        created = create_assignment(create_data)
        self.assertEqual(created.steps.count(), 2)
        self.assertIn("steps", create_data)

    def test_legacy_step_completion_does_not_mark_assignment_submitted(self):
        self.step.completed = True
        self.step.save(update_fields=["completed"])
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.progress_percent, 100)
        self.assertFalse(self.assignment.is_complete)
        self.assertFalse(self.assignment.is_submitted)

    def test_submission_requires_post_and_valid_explicit_action(self):
        url = reverse("assignment_submission", args=[self.assignment.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 400)
        self.assertEqual(self.client.post(url, {"action": "toggle"}).status_code, 400)
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_submitted)

    def test_submit_and_reopen_are_idempotent(self):
        url = reverse("assignment_submission", args=[self.assignment.pk])
        for action, expected in [("submit", True), ("submit", True), ("reopen", False), ("reopen", False)]:
            response = self.client.post(url, {"action": action, "return_to": "https://example.com"})
            self.assertRedirects(response, reverse("assignment_detail", args=[self.assignment.pk]))
            self.assignment.refresh_from_db()
            self.assertEqual(self.assignment.is_submitted, expected)
            self.assertEqual(self.assignment.is_complete, expected)
        self.step.refresh_from_db()
        self.assertFalse(self.step.completed)

    def test_submission_post_is_csrf_protected(self):
        protected_client = Client(enforce_csrf_checks=True)
        response = protected_client.post(
            reverse("assignment_submission", args=[self.assignment.pk]), {"action": "submit"},
        )
        self.assertEqual(response.status_code, 403)
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_submitted)

    def test_toggle_requires_post_and_preserves_submission(self):
        url = reverse("step_toggle", args=[self.step.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.step.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertTrue(self.step.completed)
        self.assertFalse(self.assignment.is_submitted)

    def test_delete_requires_post(self):
        url = reverse("assignment_delete", args=[self.assignment.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(Assignment.objects.filter(pk=self.assignment.pk).exists())

    def test_missing_assignment_returns_404(self):
        response = self.client.get(reverse("assignment_detail", args=[99999]))
        self.assertEqual(response.status_code, 404)


class WorkspaceFilterTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.active = Assignment.objects.create(
            course_name="软件工程", title="需求分析", deadline=self.today,
            deliverables="需求文档与用例表", content_requirements="包含用户故事",
        )
        self.pending_step = TaskStep.objects.create(assignment=self.active, title="编写文档")
        self.finished = Assignment.objects.create(
            course_name="数据库", title="数据库设计", deadline=self.today - timedelta(days=1),
            deliverables="SQL脚本", is_submitted=True,
        )
        self.tomorrow = Assignment.objects.create(
            course_name="软件工程", title="需求验收", deadline=self.today + timedelta(days=1),
            deliverables="验收文档", is_submitted=False,
        )

    def test_filters_search_deliverables_and_keep_global_counts(self):
        response = self.client.get(reverse("assignment_list"), {"q": "SQL", "status": "done"})
        self.assertEqual([item.pk for item in response.context["assignments"]], [self.finished.pk])
        self.assertEqual(response.context["assignment_total"], 3)
        self.assertEqual(response.context["active_count"], 2)
        self.assertEqual(response.context["done_count"], 1)
        self.assertEqual(response.context["overdue_count"], 0)
        self.assertEqual(response.context["urgent_count"], 2)
        self.assertEqual(response.context["tab_all_count"], 1)
        self.assertEqual(response.context["tab_active_count"], 0)
        self.assertEqual(response.context["tab_done_count"], 1)

    def test_tab_counts_scope_to_query_and_course_before_status_filter(self):
        self.tomorrow.is_submitted = True
        self.tomorrow.save(update_fields=["is_submitted"])
        response = self.client.get(reverse("assignment_list"), {
            "q": "需求", "course": "软件工程", "status": "done",
        })
        self.assertEqual([item.pk for item in response.context["assignments"]], [self.tomorrow.pk])
        self.assertEqual(response.context["tab_all_count"], 2)
        self.assertEqual(response.context["tab_active_count"], 1)
        self.assertEqual(response.context["tab_done_count"], 1)

    def test_search_can_find_content_requirements(self):
        response = self.client.get(reverse("assignment_list"), {"q": "用户故事"})
        self.assertEqual([item.pk for item in response.context["assignments"]], [self.active.pk])

    def test_invalid_status_defaults_to_all_and_empty_search_has_zero_tabs(self):
        response = self.client.get(reverse("assignment_list"), {"status": "unknown"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["status"], "all")
        empty = self.client.get(reverse("assignment_list"), {"q": "无匹配结果"})
        self.assertEqual(empty.context["assignments"], [])
        self.assertEqual(empty.context["tab_all_count"], 0)
        self.assertEqual(empty.context["tab_active_count"], 0)
        self.assertEqual(empty.context["tab_done_count"], 0)

    def test_pending_assignments_sort_before_submitted_by_deadline(self):
        response = self.client.get(reverse("assignment_list"))
        self.assertEqual(
            [item.pk for item in response.context["assignments"]],
            [self.active.pk, self.tomorrow.pk, self.finished.pk],
        )

    def test_deadline_states_are_relative_and_completed_is_not_overdue(self):
        for days, state, label in [
            (-1, "overdue", "已逾期 1 天"), (0, "today", "今天截止"),
            (1, "urgent", "明天截止"), (2, "normal", "还有 2 天"),
        ]:
            self.active.deadline = self.today + timedelta(days=days)
            self.assertEqual(self.active.deadline_state, state)
            self.assertEqual(self.active.deadline_text, label)
        self.assertEqual(self.finished.deadline_state, "submitted")
        self.assertEqual(self.finished.deadline_text, "已提交")

    def test_legacy_toggle_cannot_redirect_offsite(self):
        response = self.client.post(
            reverse("step_toggle", args=[self.pending_step.pk]), {"return_to": "https://example.com/"},
        )
        self.assertRedirects(response, reverse("assignment_detail", args=[self.active.pk]))

    @override_settings(UI_DEMO=False)
    def test_demo_seed_refuses_normal_environment(self):
        with self.assertRaises(CommandError):
            call_command("seed_ui_demo")
        self.assertEqual(Assignment.objects.count(), 3)


class DeadlineCalendarTests(TestCase):
    def setUp(self):
        self.today = date(2026, 9, 22)
        localdate = patch("assignments.views.timezone.localdate", return_value=self.today)
        localdate.start()
        self.addCleanup(localdate.stop)
        self.url = reverse("assignment_list")

        def assignment(title, deadline, *, submitted=False, course="软件工程"):
            return Assignment.objects.create(
                course_name=course, title=title, deadline=deadline,
                deliverables="报告", is_submitted=submitted,
            )

        self.today_pending = assignment("需求分析", self.today)
        self.today_submitted = assignment("需求修订", self.today, submitted=True)
        self.tomorrow = assignment("需求验收", self.today + timedelta(days=1))
        self.overdue = assignment("旧作业", self.today - timedelta(days=1), course="数据库")
        self.next_month = assignment("下月作业", date(2026, 10, 3))
        self.submitted = assignment("已交报告", date(2026, 9, 24), submitted=True)

    def calendar_day(self, response, value):
        return next(day for week in response.context["calendar_weeks"] for day in week if day["date"] == value)

    def test_calendar_counts_and_states_match_deadlines(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["calendar_month"], "2026-09")
        self.assertEqual(response.context["calendar_month_label"], "2026年9月")
        self.assertEqual(response.context["calendar_pending_count"], 3)
        self.assertEqual(response.context["calendar_submitted_count"], 2)
        today = self.calendar_day(response, self.today)
        self.assertEqual((today["total"], today["pending"], today["submitted"]), (2, 1, 1))
        self.assertTrue(today["is_today"])
        self.assertEqual(today["state"], "today")
        self.assertEqual(self.calendar_day(response, self.tomorrow.deadline)["state"], "urgent")
        self.assertEqual(self.calendar_day(response, self.overdue.deadline)["state"], "overdue")
        self.assertEqual(self.calendar_day(response, self.submitted.deadline)["state"], "submitted")
        self.assertEqual(self.calendar_day(response, date(2026, 9, 25))["state"], "empty")
        self.assertTrue(all(len(week) == 7 for week in response.context["calendar_weeks"]))
        self.assertEqual(response.context["calendar_weeks"][0][0]["date"].weekday(), 0)

    def test_selected_day_filters_list_and_tab_counts_but_not_calendar(self):
        response = self.client.get(self.url, {"day": "2026-09-22", "status": "active"})
        self.assertEqual(response.context["assignments"], [self.today_pending])
        self.assertEqual(response.context["tab_all_count"], 2)
        self.assertEqual(response.context["tab_active_count"], 1)
        self.assertEqual(response.context["tab_done_count"], 1)
        self.assertEqual(response.context["calendar_pending_count"], 3)
        self.assertEqual(response.context["calendar_submitted_count"], 0)
        self.assertEqual(self.calendar_day(response, self.tomorrow.deadline)["total"], 1)
        self.assertTrue(self.calendar_day(response, self.today)["is_selected"])

    def test_month_navigation_does_not_filter_assignment_list(self):
        response = self.client.get(self.url, {"month": "2026-10"})
        self.assertEqual(len(response.context["assignments"]), 6)
        self.assertEqual(response.context["tab_all_count"], 6)
        self.assertEqual(response.context["calendar_pending_count"], 1)
        self.assertEqual(response.context["calendar_submitted_count"], 0)
        self.assertIsNone(response.context["selected_day"])

    def test_month_navigation_and_clear_day_preserve_other_filters(self):
        response = self.client.get(self.url, {
            "q": "需求", "course": "软件工程", "status": "active",
            "month": "2026-09", "day": "2026-09-22",
        })
        expected = {"q": ["需求"], "course": ["软件工程"], "status": ["active"]}
        for key, month in [("previous_month_url", "2026-08"), ("next_month_url", "2026-10"), ("clear_day_url", "2026-09")]:
            params = parse_qs(urlparse(response.context[key]).query)
            self.assertEqual(params, {**expected, "month": [month]})
        today_params = parse_qs(urlparse(response.context["today_url"]).query)
        self.assertEqual(today_params, {**expected, "month": ["2026-09"], "day": ["2026-09-22"]})
        day_params = parse_qs(urlparse(self.calendar_day(response, self.tomorrow.deadline)["url"]).query)
        self.assertEqual(day_params, {**expected, "month": ["2026-09"], "day": ["2026-09-23"]})
        cleared = self.client.get(response.context["clear_day_url"])
        self.assertEqual(cleared.context["assignments"], [self.today_pending, self.tomorrow])

    def test_calendar_scope_respects_search_course_and_status(self):
        response = self.client.get(self.url, {"q": "需求", "course": "软件工程", "status": "done"})
        self.assertEqual(response.context["assignments"], [self.today_submitted])
        self.assertEqual(response.context["calendar_pending_count"], 0)
        self.assertEqual(response.context["calendar_submitted_count"], 1)
        self.assertEqual(self.calendar_day(response, self.today)["state"], "submitted")
        self.assertEqual(self.calendar_day(response, self.overdue.deadline)["total"], 0)

    def test_selected_day_without_month_opens_its_month(self):
        response = self.client.get(self.url, {"day": "2026-10-03"})
        self.assertEqual(response.context["calendar_month"], "2026-10")
        self.assertEqual(response.context["selected_day"], date(2026, 10, 3))
        self.assertEqual(response.context["assignments"], [self.next_month])

    def test_explicit_month_discards_stale_day_from_another_month(self):
        response = self.client.get(self.url, {"month": "2026-10", "day": "2026-09-22"})
        self.assertEqual(response.context["calendar_month"], "2026-10")
        self.assertIsNone(response.context["selected_day"])
        self.assertEqual(response.context["filters"]["day"], "")
        self.assertEqual(len(response.context["assignments"]), 6)

    def test_invalid_dates_are_ignored_safely(self):
        for invalid in ["", "garbage", "2026-02-30", "20260922", "2026-9-22", "1899-12-31", "2101-01-01", "9999-12-31"]:
            with self.subTest(day=invalid):
                response = self.client.get(self.url, {"day": invalid, "month": "2026-13"})
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["selected_day"])
                self.assertEqual(response.context["calendar_month"], "2026-09")
        for invalid in ["1899-12", "2101-01", "0000-01", "9999-12", "202609", "2026-9"]:
            with self.subTest(month=invalid):
                response = self.client.get(self.url, {"month": invalid})
                self.assertEqual(response.context["calendar_month"], "2026-09")

    def test_month_boundaries_do_not_offer_out_of_range_navigation(self):
        earliest = self.client.get(self.url, {"month": "1900-01"})
        self.assertIsNone(earliest.context["previous_month_url"])
        self.assertIn("month=1900-02", earliest.context["next_month_url"])
        latest = self.client.get(self.url, {"month": "2100-12"})
        self.assertIsNone(latest.context["next_month_url"])
        self.assertIn("month=2100-11", latest.context["previous_month_url"])
        for week in latest.context["calendar_weeks"]:
            for day in week:
                if day["date"].year > 2100:
                    self.assertIsNone(day["url"])

    def test_empty_selected_day_has_zero_tabs_and_keeps_month_marks(self):
        response = self.client.get(self.url, {"day": "2026-09-25"})
        self.assertEqual(response.context["assignments"], [])
        self.assertEqual(response.context["tab_all_count"], 0)
        self.assertEqual(response.context["tab_active_count"], 0)
        self.assertEqual(response.context["tab_done_count"], 0)
        self.assertEqual(response.context["calendar_pending_count"], 3)
