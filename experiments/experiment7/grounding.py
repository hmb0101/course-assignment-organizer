"""修订版：范围预检、截止日期约束和可回溯字段检查。"""
from datetime import date
import re

DATE = re.compile(r"(?<!\d)(20\d{2})\s*(?:年|[-/.])\s*(\d{1,2})\s*(?:月|[-/.])\s*(\d{1,2})(?:日)?(?!\d)")
CUTOFF_BEFORE = re.compile(r"(?:截止(?:时间|日期)?|截至|最迟|不晚于|提交期限)(?:\s|[:：]|是|为|改为|调整为|延至)*$")
CUTOFF_AFTER = re.compile(r"^\s*(?:\d{1,2}:\d{2}\s*)?(?:截止|前(?:提交|上交|上传))")
FINAL_CHANGE = re.compile(r"(?:最终截止(?:时间|日期)?(?:改为|调整为|为)|截止(?:时间|日期)?(?:改为|调整为|延至))\s*[:：]?\s*$")
UNRESOLVED = re.compile(r"(?:目前|暂时|尚|仍)?未确认以哪个为准|不确定以哪个为准|两个日期待核实")
ACTION = re.compile(r"^\s*(?:请替我|请帮我|帮我|替我|请你)(?:先)?(?:登录|上传|代交|提交|把作业标记)", re.I)

def scope_reason(text, kind):
    if kind != "text":
        return "UNSUPPORTED_MEDIA"
    if ACTION.search(text) and not re.search(r"(?:课程|作业|提交物)[：:]",text):
        return "EXTERNAL_ACTION"
    return None

def dated_spans(text):
    for m in DATE.finditer(text):
        try:
            value = date(*(int(x) for x in m.groups())).isoformat()
        except ValueError:
            continue
        yield m, value

def allowed_deadlines(text):
    seen, revisions = set(), set()
    for match, value in dated_spans(text):
        before = text[max(0,match.start()-40):match.start()]
        after = text[match.end():match.end()+24]
        if CUTOFF_BEFORE.search(before) or CUTOFF_AFTER.match(after):
            seen.add(value)
            if FINAL_CHANGE.search(before):
                revisions.add(value)
    if UNRESOLVED.search(text) and len(seen)>1:
        return set()
    return revisions if len(revisions)==1 else seen if len(seen)==1 else set()

def check(obj, text):
    fields = dict(obj["fields"])
    source = obj.get("evidence")
    if not isinstance(source, dict):
        raise ValueError("模型未提供可核查的证据对象。")
    checked, warnings = {}, {}
    allowed = allowed_deadlines(text)
    for key, value in list(fields.items()):
        if not value:
            continue
        quote = source.get(key)
        has_quote = isinstance(quote,str) and bool(quote.strip()) and len(quote)<=800 and quote in text
        if key=="deadline":
            ok = has_quote and value in allowed and value in {d for _,d in dated_spans(quote)}
            code = "DEADLINE_UNCONFIRMED"
        elif key=="deliverables":
            ok = has_quote and all(x in quote for x in value)
            code = "EVIDENCE_MISMATCH"
        else:
            ok = has_quote and value in quote
            code = "EVIDENCE_MISMATCH"
        if ok:
            checked[key] = quote
        else:
            fields[key] = None if key=="deadline" else [] if key=="deliverables" else ""
            warnings[key] = code
    deadline_text = obj["deadline_text"]
    if deadline_text and deadline_text not in text:
        deadline_text = ""
        warnings["deadline_text"] = "EVIDENCE_MISMATCH"
    return fields, checked, warnings, deadline_text
