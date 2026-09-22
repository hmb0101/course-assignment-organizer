from datetime import date

from django.core.management.base import BaseCommand

from assignments.models import Assignment, TaskStep


class Command(BaseCommand):
    help = "创建可重复使用的演示作业数据"

    def handle(self, *args, **options):
        assignment, created = Assignment.objects.get_or_create(
            course_name="软件应用开发实践",
            title="实验4：软件基础功能开发",
            defaults={
                "deadline": date(2026, 9, 22),
                "deliverables": "PDF实验报告、GitHub仓库版本证据",
                "filename_rule": "班级-学号-姓名-实验4-软件基础功能开发.pdf",
                "source_text": "完成可运行初版和测试修订版，记录测试、日志与AI辅助编码审查。",
            },
        )
        if created:
            for index, title in enumerate(["完成项目骨架", "实现业务闭环", "执行测试", "整理实验报告"], start=1):
                TaskStep.objects.create(assignment=assignment, title=title, sort_order=index)
            self.stdout.write(self.style.SUCCESS("演示数据创建完成。"))
        else:
            self.stdout.write("演示数据已存在，未重复创建。")

