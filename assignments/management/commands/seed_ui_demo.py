from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from assignments.models import Assignment


class Command(BaseCommand):
    help = "在独立演示数据库中初始化界面预览数据，不修改正式作业数据。"

    @transaction.atomic
    def handle(self, *args, **options):
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        real_database_path = (settings.BASE_DIR / "db.sqlite3").resolve()
        if not settings.UI_DEMO or database_path == real_database_path:
            raise CommandError("演示数据需要 UI_DEMO=1，并通过 DJANGO_DB_PATH 指定独立数据库。")
        if Assignment.objects.exists():
            raise CommandError("演示数据库已有作业，保留现有数据；请使用新的空演示数据库。")

        today = timezone.localdate()
        records = [
            {
                "course_name": "软件应用开发实践",
                "title": "实验四 · 软件基础功能开发",
                "offset": 1,
                "deliverables": "实验报告 PDF\n项目源代码与 GitHub 仓库地址\n核心流程运行截图",
                "filename_rule": "班级-学号-姓名-实验4-软件基础功能开发.pdf",
                "submission_method": "学习通对应实验作业入口；源代码更新至 GitHub 仓库",
                "content_requirements": "说明基础功能的实现与异常处理。\n保留初版和修订版提交，附核心流程截图与测试结果。\n截图、表格按顺序编号并配文字说明。",
                "source_text": "完成非 AI 基础业务闭环，保留初版和修订版提交。实验报告需要说明模块实现、异常处理和测试结果，截图与表格须编号。通过学习通提交 PDF，源代码更新至个人仓库。",
            },
            {
                "course_name": "数据库系统原理",
                "title": "校园借阅系统 · 数据库设计",
                "offset": 3,
                "deliverables": "数据库设计说明书\nE-R 图与建表 SQL",
                "filename_rule": "学号-姓名-数据库设计.zip",
                "submission_method": "待确认",
                "content_requirements": "包含概念结构、逻辑结构与主外键约束说明。\n提供 E-R 图、建表 SQL 和至少六条测试查询。",
                "source_text": "围绕图书、读者、借阅记录三类实体完成概念结构与逻辑结构设计。说明主外键约束，并提供至少六条测试查询。设计说明书和 SQL 脚本打包后提交。",
            },
            {
                "course_name": "计算机网络",
                "title": "Wireshark 抓包与协议分析",
                "offset": 5,
                "deliverables": "协议分析报告\n脱敏后的抓包文件",
                "filename_rule": "学号-姓名-TCP分析.zip",
                "submission_method": "待确认",
                "content_requirements": "标注 TCP 连接建立与释放报文的序号和确认号。\n说明三次握手的作用；截图须遮挡个人地址及无关会话。",
                "source_text": "观察一次完整 TCP 连接建立与释放过程，标记报文序号和确认号。说明三次握手的作用，截图前遮挡个人地址与无关会话。",
            },
            {
                "course_name": "软件应用开发实践",
                "title": "实验三 · 软件架构与界面设计",
                "offset": -3,
                "deliverables": "软件架构与界面设计报告 PDF",
                "filename_rule": "班级-学号-姓名-实验3-软件架构与界面设计.pdf",
                "submission_method": "学习通对应实验作业入口",
                "content_requirements": "说明模块划分、数据库设计及核心界面原型。\n给出人工确认、异常恢复设计和可验证的接口约定。",
                "is_submitted": True,
                "source_text": "提交模块划分、数据库设计与核心界面原型。说明人工确认与异常恢复的设计，并给出可验证的接口约定。",
            },
            {
                "course_name": "软件工程",
                "title": "课程项目 · 用例与验收标准",
                "offset": 7,
                "deliverables": "需求用例文档\n验收条件对照表",
                "filename_rule": "学号-姓名-需求用例.docx",
                "submission_method": "待确认",
                "content_requirements": "选择三条主要用户故事，包含前置条件、基本流程和异常流程。\n验收标准应可测量，避免将实现方案当作用户需求。",
                "source_text": "选取个人项目的三条主要用户故事，补充前置条件、基本流程、异常流程与可测量的验收标准。避免将实现方案写成用户需求。",
            },
        ]
        for record in records:
            offset = record.pop("offset")
            Assignment.objects.create(deadline=today + timedelta(days=offset), **record)
        self.stdout.write(self.style.SUCCESS("已在独立数据库创建 5 条界面演示作业。"))
