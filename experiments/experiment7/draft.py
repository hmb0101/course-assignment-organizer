"""作业通知 → 可核对草稿；不访问正式数据库，也不执行通知中的命令。"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import settings
import grounding

ROOT = Path(__file__).resolve().parent
FIELD_NAMES = ("course_name", "title", "deadline", "deliverables",
               "submission_method", "filename_rule", "content_requirements")
REQUIRED = ("course_name", "title", "deadline", "deliverables")
LABELS = {"course_name":"课程", "title":"作业名称", "deadline":"截止日期",
          "deliverables":"提交物", "submission_method":"提交方式",
          "filename_rule":"命名规则", "content_requirements":"内容要求"}
SECRET = re.compile(r"sk-[A-Za-z0-9_-]{15,}|Bearer\s+[A-Za-z0-9_.-]{12,}", re.I)

class DraftError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

def load_config(path):
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                if key.strip() in {"LLM_API_KEY", "LLM_BASE_URL"}:
                    values[key.strip()] = value.strip().strip('"').strip("'")
    key = os.getenv("LLM_API_KEY") or values.get("LLM_API_KEY", "")
    if not key:
        raise DraftError("MISSING_CONFIG", "未配置密钥，可先手工录入。")
    base = (os.getenv("LLM_BASE_URL") or values.get("LLM_BASE_URL") or settings.BASE_URL).rstrip("/")
    url = urllib.parse.urlsplit(base)
    if (url.scheme != "https" or url.username or url.password or url.query or url.fragment
        or (url.hostname != "dashscope.aliyuncs.com" and not (url.hostname or "").endswith(".maas.aliyuncs.com"))):
        raise DraftError("INVALID_CONFIG", "仅接受已配置的百炼HTTPS接口。")
    return base, key

def cloud_call(messages, env):
    base, key = load_config(env)
    body = {"model":settings.MODEL, "messages":messages, "temperature":settings.TEMPERATURE,
            "max_tokens":settings.MAX_TOKENS, "stream":False,
            "response_format":{"type":"json_object"}, "enable_thinking":settings.ENABLE_THINKING}
    req = urllib.request.Request(base + "/chat/completions",
                                 data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type":"application/json"}, method="POST")
    req.add_unredirected_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=settings.TIMEOUT) as resp:
            data = json.loads(resp.read(2_000_000).decode("utf-8"))
        usage = data.get("usage") or {}
        if not isinstance(usage, dict):
            raise ValueError("invalid usage")
        return {"raw":data["choices"][0]["message"]["content"], "usage":usage}
    except urllib.error.HTTPError as exc:
        raise DraftError(f"HTTP_{exc.code}", "模型接口返回错误，原文已保留。") from None
    except (TimeoutError, socket.timeout):
        raise DraftError("TIMEOUT", "等待模型超时，可重试或手工录入。") from None
    except urllib.error.URLError as exc:
        code = "TIMEOUT" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "CONNECTION_ERROR"
        raise DraftError(code, "模型连接未完成，可重试或手工录入。") from None
    except OSError:
        raise DraftError("CONNECTION_ERROR", "连接中断，可手工录入。") from None
    except (ValueError, TypeError, KeyError, IndexError):
        raise DraftError("INVALID_API_RESPONSE", "接口响应无法解析，可手工录入。") from None

def preprocess(raw):
    text = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text or len(text) > settings.MAX_INPUT_CHARS:
        raise DraftError("INVALID_INPUT", "请粘贴1至4000字符的作业通知。")
    if SECRET.search(text):
        raise DraftError("SENSITIVE_INPUT", "输入疑似包含密钥，已停止发送，请先删除敏感内容。")
    return text

def validate(raw):
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        raise DraftError("INVALID_JSON", "模型未返回有效JSON。") from None
    if not isinstance(obj, dict) or obj.get("kind") not in ("assignment", "out_of_scope"):
        raise DraftError("INVALID_SCHEMA", "缺少有效的通知类型。")
    if obj["kind"] == "out_of_scope":
        return obj
    fields = obj.get("fields")
    if not isinstance(fields, dict) or set(fields) != set(FIELD_NAMES):
        raise DraftError("INVALID_SCHEMA", "草稿字段不完整或含额外字段。")
    for k in FIELD_NAMES:
        value = fields[k]
        if k == "deliverables":
            if not isinstance(value, list) or len(value) > 12 or any(not isinstance(x, str) or not x.strip() or len(x)>150 for x in value):
                raise DraftError("INVALID_SCHEMA", "提交物须为有效的字符串数组。")
            fields[k] = list(dict.fromkeys(x.strip() for x in value))
        elif k == "deadline":
            if value is not None:
                try:
                    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                        raise ValueError()
                except ValueError:
                    raise DraftError("INVALID_SCHEMA", "截止日期格式或日期值无效。") from None
        else:
            maximum = {"course_name":100,"title":150,"submission_method":255,"filename_rule":255}.get(k,800)
            if not isinstance(value, str) or len(value) > maximum:
                raise DraftError("INVALID_SCHEMA", "字段类型或长度不符合要求。")
            fields[k] = value.strip()
    if not isinstance(obj.get("deadline_text"), str) or len(obj["deadline_text"]) > 250:
        raise DraftError("INVALID_SCHEMA", "截止原文格式无效。")
    return obj

def make_draft(original, input_kind, env, call=cloud_call):
    started = time.perf_counter()
    result = {"version":settings.VERSION, "model":settings.MODEL, "original":original,
              "input_kind":input_kind, "calls":0, "usage":{}, "trace":[], "error":None,
              "status":"manual", "fields":{}, "deadline_text":"", "uncertain_fields":[],
              "form_seed":{}, "message":"", "evidence":{}, "warnings":{}}
    def mark(stage, **details):
        result["trace"].append({"stage":stage, **details})
    try:
        text = preprocess(original)
        mark("preprocessed", characters=len(text))
        reason = grounding.scope_reason(text,input_kind)
        if reason:
            obj = {"kind":"out_of_scope"}
            mark("scope_rejected", by="preflight", reason=reason)
        else:
            messages = [{"role":"system", "content":settings.PROMPT},
                        {"role":"user", "content":json.dumps({"input_kind":input_kind,"notice":text},ensure_ascii=False)}]
            result["calls"] = 1
            reply = call(messages, env)
            result["usage"] = reply["usage"]
            result["raw_model"] = SECRET.sub("[REDACTED]", str(reply["raw"]))
            mark("model_returned", usage=result["usage"])
            obj = validate(reply["raw"])
        if obj["kind"] == "out_of_scope":
            result.update(status="out_of_scope", message="只支持作业通知文字；不识图、登录或代交。")
            if not reason:
                mark("scope_rejected", by="model")
        else:
            try:
                fields, evidence, warnings, deadline_text = grounding.check(obj,text)
            except ValueError as exc:
                raise DraftError("INVALID_SCHEMA",str(exc)) from None
            uncertain = list(dict.fromkeys([k for k in REQUIRED if not fields[k]] + list(warnings)))
            seed = {**fields, "deadline":fields["deadline"] or "",
                    "deliverables":"\n".join(fields["deliverables"]), "source_text":original}
            result.update(status="needs_review" if uncertain else "draft", fields=fields,
                          deadline_text=deadline_text, uncertain_fields=uncertain, form_seed=seed,
                          evidence=evidence, warnings=warnings,
                          message="有待确认字段，请对照原文补齐。" if uncertain else "草稿已生成，请对照原文确认。")
            mark("validated", uncertain=uncertain, evidence_fields=list(evidence), warnings=warnings)
    except DraftError as exc:
        if exc.code in {"MISSING_CONFIG","INVALID_CONFIG"}:
            result["calls"] = 0
        result.update(error=exc.code, message=str(exc), form_seed={"source_text":original})
        mark("failed", code=exc.code)
    result["elapsed_ms"] = round((time.perf_counter()-started)*1000, 2)
    usage = result["usage"]
    result["estimated_cny"] = round((usage.get("prompt_tokens",0)*settings.PRICE["input"] +
                                     usage.get("completion_tokens",0)*settings.PRICE["output"])/1_000_000, 8)
    return result

def judge(case, result):
    e = case["expected"]
    mismatches = []
    if result["status"] != e["status"]:
        mismatches.append("status")
    for key, value in e["fields"].items():
        got = result["fields"].get(key, object())
        if key == "deliverables" and isinstance(got, list):
            got, value = sorted(got), sorted(value)
        if got != value:
            mismatches.append(key)
    for key, value in e.get("contains", {}).items():
        if value not in result["fields"].get(key, ""):
            mismatches.append(key)
    if e.get("deadline_text_contains", "") not in result["deadline_text"]:
        mismatches.append("deadline_text")
    if not set(e.get("uncertain", [])) <= set(result["uncertain_fields"]):
        mismatches.append("uncertain_fields")
    if result["original"] != case["notice"]:
        mismatches.append("original")
    return {"passed":not mismatches, "mismatches":mismatches}

def evaluate(env, output):
    cases_path = ROOT / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as f:
        def write(item):
            f.write(json.dumps(item, ensure_ascii=False)+"\n")
            f.flush()
        write({"type":"metadata", "version":settings.VERSION, "model":settings.MODEL,
               "temperature":settings.TEMPERATURE, "max_tokens":settings.MAX_TOKENS,
               "timeout_s":settings.TIMEOUT, "prompt_sha256":sha256(settings.PROMPT.encode()).hexdigest(),
               "cases_sha256":sha256(cases_path.read_bytes()).hexdigest()})
        for case in cases:
            result = make_draft(case["notice"], case["input_kind"], env)
            verdict = judge(case, result)
            write({"type":"case", "id":case["id"], "category":case["category"], "result":result, "verdict":verdict})
            print(case["id"], result["status"], "pass" if verdict["passed"] else verdict["mismatches"],
                  f'{result["elapsed_ms"]:.2f}ms', result["usage"].get("total_tokens", 0), flush=True)
            if result["error"] in {"HTTP_401","HTTP_403","HTTP_429","MISSING_CONFIG","INVALID_CONFIG"}:
                raise SystemExit(2)

def show(result):
    print("【原文】\n"+result["original"])
    print("\n【结果】"+result["message"])
    for key, value in result["fields"].items():
        rendered = "、".join(value) if isinstance(value, list) else value
        print(LABELS[key]+"："+(rendered or "待确认"))
        if key in result.get("evidence", {}):
            print("  原文依据："+result["evidence"][key])
    if result["deadline_text"]:
        print("截止原文："+result["deadline_text"])
    if result["error"]:
        print("错误类型："+result["error"])
    if result["warnings"]:
        print("待核查原因："+json.dumps(result["warnings"],ensure_ascii=False))

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="课程作业通知草稿原型")
    parser.add_argument("--env",type=Path,default=ROOT/".env")
    commands = parser.add_subparsers(dest="command",required=True)
    draft = commands.add_parser("draft")
    source = draft.add_mutually_exclusive_group()
    source.add_argument("--sample")
    source.add_argument("--file",type=Path)
    draft.add_argument("--json",action="store_true",help="输出草稿及表单预填字段，不保存数据库")
    batch = commands.add_parser("evaluate")
    batch.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.command == "evaluate":
        evaluate(args.env,args.output);return
    kind = "text"
    if args.sample:
        cases = json.loads((ROOT/"cases.json").read_text(encoding="utf-8"))
        case = next((x for x in cases if x["id"]==args.sample),None)
        if not case:
            parser.error("找不到样例编号")
        original, kind = case["notice"], case["input_kind"]
    elif args.file:
        if args.file.suffix.lower() not in {".txt",".md"}:
            parser.error("仅接收UTF-8 txt或md文本")
        original = args.file.read_text(encoding="utf-8-sig")
    else:
        print("粘贴通知后结束输入（Windows：Ctrl+Z后回车）。",file=sys.stderr)
        original = sys.stdin.read()
    result = make_draft(original,kind,args.env)
    if args.json:
        print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        show(result)

if __name__ == "__main__":
    main()
