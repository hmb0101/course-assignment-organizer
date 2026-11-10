import json
from pathlib import Path
import unittest
from unittest.mock import patch
import draft

SAMPLE = "课程：软件测试；作业：复测；截止时间：2026-11-23；提交物：报告.pdf。"
FIELDS = {"course_name":"软件测试","title":"复测","deadline":"2026-11-23",
          "deliverables":["报告.pdf"],"submission_method":"","filename_rule":"","content_requirements":""}

def reply(evidence=None, **updates):
    fields = {**FIELDS, **updates}
    evidence = {"course_name":"软件测试","title":"复测","deadline":"2026-11-23","deliverables":"报告.pdf"} if evidence is None else evidence
    return {"raw":json.dumps({"kind":"assignment","fields":fields,"deadline_text":"2026-11-23" if fields["deadline"] else "",
                             "evidence":evidence},
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
    def test_image_preflight(self):
        r = draft.make_draft("仅一张图片","image",Path(".env"),call=lambda *_:self.fail("不应请求模型"))
        self.assertEqual((r["status"],r["calls"]),("out_of_scope",0))
    def test_action_preflight(self):
        r = self.run_case(lambda *_:self.fail("不应请求模型"),"请替我登录学习通并上传文件。")
        self.assertEqual((r["status"],r["calls"]),("out_of_scope",0))
    def test_forged_field_rejected(self):
        r = self.run_case(lambda *_:reply(course_name="未出现的课程"))
        self.assertEqual(r["fields"]["course_name"],"")
        self.assertEqual(r["warnings"]["course_name"],"EVIDENCE_MISMATCH")
    def test_forged_evidence_rejected(self):
        r = self.run_case(lambda *_:reply(evidence={"course_name":"未出现的课程"},course_name="未出现的课程"))
        self.assertNotIn("course_name",r["evidence"])
    def test_conflicting_date_not_accepted(self):
        r = self.run_case(lambda *_:reply(), SAMPLE+"；平台截止时间：2026-11-25。")
        self.assertEqual((r["status"],r["fields"]["deadline"]),("needs_review",None))
    def test_release_date_not_used(self):
        r = self.run_case(lambda *_:reply(),SAMPLE.replace("截止时间","发布日期"))
        self.assertEqual(r["warnings"]["deadline"],"DEADLINE_UNCONFIRMED")
    def test_relative_date_not_guessed(self):
        r = self.run_case(lambda *_:reply(),SAMPLE.replace("2026-11-23","下周五"))
        self.assertIsNone(r["fields"]["deadline"])
    def test_explicit_revision(self):
        r = self.run_case(lambda *_:reply(),SAMPLE.replace("截止时间：","原截止时间：2026-11-21；最终截止时间改为"))
        self.assertEqual(r["fields"]["deadline"],"2026-11-23")
    def test_bad_evidence_schema(self):
        r = self.run_case(lambda *_:reply(evidence=[]))
        self.assertEqual((r["status"],r["error"]),("manual","INVALID_SCHEMA"))
    def test_model_outside_scope_is_still_handled(self):
        r = self.run_case(lambda *_:{"raw":'{"kind":"out_of_scope"}',"usage":{}},"今天的天气怎么样？")
        self.assertEqual((r["status"],r["calls"]),("out_of_scope",1))
    def test_out_of_scope_preserves_original(self):
        text="请替我登录课程平台。"
        r=self.run_case(lambda *_:self.fail("不应请求模型"),text)
        self.assertEqual(r["original"],text)
        self.assertEqual(r["form_seed"],{})
    def test_form_draft_never_writes_database(self):
        r=self.run_case(lambda *_:reply())
        self.assertNotIn("is_submitted",r["form_seed"])
        self.assertEqual(r["form_seed"]["deadline"],"2026-11-23")
    def test_transport_timeout_is_mapped_to_manual(self):
        with patch("draft.load_config", return_value=(draft.settings.BASE_URL, "local-test-key")), \
             patch("draft.urllib.request.urlopen", side_effect=TimeoutError):
            r = draft.make_draft(SAMPLE, "text", Path(".env"))
        self.assertEqual((r["status"],r["error"]),("manual","TIMEOUT"))
        self.assertEqual(r["form_seed"]["source_text"],SAMPLE)

if __name__ == "__main__":
    unittest.main(verbosity=2)
