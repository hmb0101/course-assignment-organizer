from django.core.management import call_command
from django.core.management.base import BaseCommand

from assignments.models import Assignment


class Command(BaseCommand):
    help = "清空作业数据，并可恢复演示数据"

    def add_arguments(self, parser):
        parser.add_argument("--empty", action="store_true", help="只清空，不恢复演示数据")

    def handle(self, *args, **options):
        deleted, _ = Assignment.objects.all().delete()
        self.stdout.write(f"已清理 {deleted} 条相关记录。")
        if not options["empty"]:
            call_command("seed_demo")
