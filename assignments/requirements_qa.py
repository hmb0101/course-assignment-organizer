import importlib.util
import logging
import os
from pathlib import Path
import sys
from uuid import uuid4

from django.shortcuts import render
from django.views.decorators.http import require_http_methods


logger = logging.getLogger("assignments")


def load_rag():
    directory = os.environ.get("ASSIGNMENT_RAG_DIR")
    if not directory:
        return None
    module_file = Path(directory).resolve() / "rag.py"
    if not module_file.is_file():
        return None
    spec = importlib.util.spec_from_file_location("assignment_rag", module_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rag = load_rag()


@require_http_methods(["GET", "POST"])
def requirements_qa(request):
    context = {}
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        context["question"] = question
        if not 0 < len(question) <= 1000:
            context["error"] = "请输入1至1000字符的问题。"
        elif rag is None:
            context["error"] = "请先配置作业要求问答模块。"
        else:
            try:
                chunks = rag.build_index()
                if request.POST.get("action") == "retrieve":
                    context["retrieved"] = True
                    context["hits"] = rag.retrieve(question, chunks)
                else:
                    config = rag.Config.from_env(rag.read_env(rag.ROOT / ".env"))
                    result = rag.ask(question, rag.CloudClient(config), chunks, version=2)
                    records = os.environ.get("ASSIGNMENT_RAG_RECORD_DIR")
                    if records:
                        try:
                            rag.dump(Path(records) / f"web-ask-{uuid4().hex}.json", result)
                        except OSError:
                            logger.warning("requirements_qa could not save the configured run record")
                    if result["ok"]:
                        output = result["output"]
                        sources = {source["source_id"]: source for source in result["sources"]}
                        context.update(
                            result=result,
                            citations=[
                                {**sources[citation["source_id"]], "quote": citation["quote"]}
                                for citation in output["citations"]
                            ],
                        )
                    else:
                        context["error"] = result.get("message", "模型未返回可用结果。")
            except (OSError, ValueError):
                context["error"] = "暂时无法读取资料或模型配置，请检查后重试。"
    return render(request, "assignments/requirements_qa.html", context)
