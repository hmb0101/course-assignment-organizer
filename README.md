# 课程作业要求智能整理系统

本项目面向需要同时处理多个课程作业通知的大学生，将原始通知整理为可核对的作业要求，集中查看截止时间、提交物、提交方式和文件命名。支持手工录入和提交状态管理，也可在新增作业时生成草稿。

## 当前阶段

实验4已完成非AI基础业务闭环：可以手工录入、校验、保存、编辑、删除作业，搜索与按课程筛选，并手动标记“待提交／已提交”。根据使用反馈，界面移除手填步骤与百分比进度，改为直接展示作业要求。状态标记不代表系统已向学习平台上传文件。原有步骤数据仍保留，不再作为提交状态的依据。

更新已有项目后先运行 `python manage.py migrate`，新增提交状态和要求字段，不删除旧作业或步骤。需求 V1 保留为历史基线，本次调整见[迭代记录](docs/experiment4/iteration-record.md)。

## 本地运行

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

浏览器访问 `http://127.0.0.1:8000/`。

清空并恢复演示数据：

```powershell
python manage.py reset_demo
python manage.py reset_demo --empty
```

执行自动化测试：

```powershell
python manage.py test
```

## 智能整理流程

草稿功能复用 [实验七原型](experiments/experiment7/README.md)。按原型说明配置密钥；如已有本地配置，可在启动 Django 前用 `ASSIGNMENT_AI_ENV` 指向该文件。

1. 在“新增作业”左侧粘贴通知，点击“生成草稿”。
2. 通义千问提取字段，校验通过的结果预填空白项，已有手工输入会保留。
3. 用户确认或修改关键信息。
4. 系统保存作业记录和内容要求，由用户维护提交状态。

## MVP计划范围

实验五的“要求核对”使用单独的本地 RAG 模块。启动 Django 前，将 `ASSIGNMENT_RAG_DIR` 指向包含 `rag.py`、`kb/` 和本地 `.env` 的模块目录，左侧导航即可进入问答。点击“仅查看检索结果”只做本地检索。

- 文本粘贴和 `.txt`、`.md` 文件导入。
- 作业关键信息智能提取。
- 人工确认、修改和保存。
- 作业列表、详情和提交状态管理。
- API失败时切换到手工录入。

图片OCR、PDF解析、自动抓取学习通、课表同步和系统级通知暂不纳入本学期MVP。

## 技术方案

- Python 3.13
- Django 6
- SQLite
- 阿里云百炼通义千问

密钥通过环境变量或本地配置读取。接口失败时页面保留原文和已填写字段，用户可以继续手工录入。

## 文档

- [个人项目方案](docs/project-proposal.md)
- [需求说明V1](docs/requirements-v1.md)
- [调研与访谈摘要](docs/research-notes.md)
- [软件架构设计V1](docs/design/architecture-design-v1.md)
- [数据与接口设计V1](docs/design/data-api-design-v1.md)
- [界面与交互设计V1](docs/design/interface-design-v1.md)

