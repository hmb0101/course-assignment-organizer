import json
from pathlib import Path
import unittest
import draft

SAMPLE = "课程：软件测试；作业：复测；截止时间：2026-11-23；提交物：报告.pdf。"
FIELDS = {"course_name":"软件测试","title":"复测","deadline":"2026-11-23",
          "deliverables":["报告.pdf"],"submission_method":"","filename_rule":"","content_requirements":""}

def reply(**updates):
    fields = {**FIELDS, **updates}
    return {"raw":json.dumps({"kind":"assignment","fields":fields,"deadline_text":fields["deadline"] or ""},
                             ensure_ascii=False),"usage":{"prompt_tokens":100,"completion_tokens":50,"total_tokens":150}}

class DraftTests(unittest.TestCase):
    def run_case(self, callback, text=SAMPLE):
        return draft.make_draft(text,"text",Path(".env"),call=callback)
    def test_normal(self):
        r = self.run_case(lambda *_:reply())
        self.assertEqual(r["status"],"draft")
        self.assertEqual(r["form_seed"]["source_text"],SAMPLE)
        self.assertEqual(r["form_seed"]["deliverables"],"报告.pdf")
    def test_missing_date(self):
        r = self.run_case(lambda *_:reply(deadline=None))
        self.assertEqual((r["status"],r["uncertain_fields"]),("needs_review",["deadline"]))
    def test_invalid_date(self):
        self.assertEqual(self.run_case(lambda *_:reply(deadline="2026-02-30"))["error"],"INVALID_SCHEMA")
    def test_invalid_json(self):
        self.assertEqual(self.run_case(lambda *_:{"raw":"not JSON","usage":{}})["error"],"INVALID_JSON")
    def test_timeout_retains_text(self):
        def timeout(*_):
            raise draft.DraftError("TIMEOUT","请手工录入。")
        r = self.run_case(timeout)
        self.assertEqual((r["status"],r["error"],r["form_seed"]["source_text"]),("manual","TIMEOUT",SAMPLE))
    def test_out_of_scope(self):
        r = self.run_case(lambda *_:{"raw":'{"kind":"out_of_scope"}',"usage":{}})
        self.assertEqual((r["status"],r["fields"]),("out_of_scope",{}))
    def test_empty_does_not_call(self):
        r = self.run_case(lambda *_:self.fail("不应调用"),"  ")
        self.assertEqual((r["calls"],r["error"]),(0,"INVALID_INPUT"))
    def test_secret_does_not_call(self):
        r = self.run_case(lambda *_:self.fail("不应调用"),"sk-"+"A"*30)
        self.assertEqual((r["calls"],r["error"]),(0,"SENSITIVE_INPUT"))
    def test_dataset_fixed_unique_cases(self):
        cases=json.loads((draft.ROOT/"cases.json").read_text(encoding="utf-8"))
        self.assertEqual(len({c["id"] for c in cases}),12)

if __name__ == "__main__":
    unittest.main(verbosity=2)
