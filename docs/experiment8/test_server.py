"""Run the local Django app with a controlled model transport for browser tests."""
import argparse
import json
import os
from pathlib import Path
import sys
from time import sleep


def fixture_call(messages, config_path):
    text = json.loads(messages[1]["content"])["notice"]
    lines = dict(line.split("：", 1) for line in text.splitlines() if "：" in line)
    scenario = lines.get("测试", "")
    module = sys.modules["experiments.experiment7.draft"]
    if scenario == "慢速":
        sleep(8)
    if scenario == "模拟超时":
        sleep(0.5)
        raise module.DraftError("TIMEOUT", "等待模型超时，可重试或手工录入。")
    if scenario == "无效输出":
        return {"raw": "[", "usage": {}}
    if scenario == "拒绝":
        return {"raw": '{"kind":"out_of_scope"}', "usage": {}}

    fields = {
        "course_name": lines["课程"],
        "title": lines["作业"],
        "deadline": next(module.grounding.dated_spans(lines["截止时间"]))[1],
        "deliverables": [lines["提交物"]],
        "submission_method": "",
        "filename_rule": "",
        "content_requirements": "",
    }
    evidence = {
        "course_name": f"课程：{lines['课程']}",
        "title": f"作业：{lines['作业']}",
        "deadline": f"截止时间：{lines['截止时间']}",
        "deliverables": f"提交物：{lines['提交物']}",
    }
    payload = {"kind": "assignment", "fields": fields, "evidence": evidence,
               "deadline_text": evidence["deadline"]}
    return {"raw": json.dumps(payload, ensure_ascii=False), "usage": {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if args.db.exists():
        parser.error("--db must point to a new test database")
    os.environ["DJANGO_DB_PATH"] = str(args.db.resolve())
    os.environ["UI_DEMO"] = "1"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    sys.path.insert(0, str(args.project.resolve()))
    import django
    from django.core.management import call_command

    django.setup()
    from experiments.experiment7 import draft

    make_draft = draft.make_draft

    def generate(text, kind, config_path):
        return make_draft(text, kind, config_path, call=fixture_call)

    draft.make_draft = generate
    call_command("migrate", verbosity=0)
    call_command("seed_ui_demo")
    call_command("runserver", f"127.0.0.1:{args.port}", use_reloader=False)


if __name__ == "__main__":
    main()
