# 实验七 作业通知结构化草稿

这是“课程作业要求智能整理系统”的核心能力原型。将作业通知文字变成可核对的草稿，保留原文并标记待确认字段。不会访问学习通，也不会写入正式数据库。

Python 3.10及以上，仅用标准库。复制本目录的 .env.example 为本地 .env 并配置密钥，或者用 --env 指向已有配置。settings.py 集中管理模型、Prompt、超时和参数。

```powershell
python draft.py --env .env draft --sample N01
python draft.py --env .env draft --file 通知.txt --json
python draft.py --env .env evaluate --output artifacts/v1.jsonl
python -m unittest -v
```

evaluate 使用 cases.json 中12条合成通知，与真实作业日期无关。输出逐条记录，拒绝覆盖已有日志。普通 draft 只展示，不写日志。输入为UTF-8文字，图片、代交、登录和平台抓取不在范围内。模型超时或JSON无效时返回手工录入状态，保留原文。form_seed 可供现有 AssignmentForm 后续预填；用户确认与基础表单校验仍然必要。

v1 是直接调用模型后做字段类型检查的可运行初版，用作固定基线。验收依据是实验二 US-01（结构化）、US-02（确认后保存）、US-03（不猜日期）、US-04（故障保留原文）以及多提交物样例。单元测试不请求云端。
