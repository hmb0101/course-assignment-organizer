# 数据与接口设计V1

## 1 核心数据对象

### Assignment

保存课程名称、作业名称、截止时间、原始文本、确认状态和创建时间。`source_text`可能包含课程内部信息，属于需要保护的业务数据。

### Deliverable

保存作业对应的提交物及文件命名规则，一项作业可以包含多个提交物。

### TaskStep

保存任务步骤、顺序和完成状态，一项作业可以包含多个步骤。

### ExtractionRecord

保存模型名称、调用状态、耗时、待确认字段和错误摘要。原始模型响应只在调试阶段短期保留，日志不得保存API密钥。

## 2 主要接口

| 接口 | 提供模块 | 调用者 | 输入 | 输出 | 失败处理 |
| --- | --- | --- | --- | --- | --- |
| `POST /api/extractions` | AI提取服务 | 输入页 | `source_text` | 结构化草稿 | 400空输入；502模型错误；504超时 |
| `POST /api/assignments` | 作业服务 | 确认页 | 已确认字段 | 作业详情 | 400校验失败；409重复提交 |
| `GET /api/assignments` | 查询服务 | 首页 | 状态筛选 | 作业列表 | 500时显示重试提示 |
| `GET /api/assignments/{id}` | 查询服务 | 详情页 | 作业ID | 作业及步骤 | 404不存在 |
| `PATCH /api/steps/{id}` | 进度服务 | 详情页 | `completed` | 更新后的步骤 | 400非法值；404不存在 |

## 3 正常调用示例

```json
POST /api/extractions
{
  "source_text": "软件应用开发实践实验3，9月15日前提交Word转PDF，文件名按班级-学号-姓名命名。"
}
```

```json
200 OK
{
  "course_name": "软件应用开发实践",
  "assignment_title": "实验3：软件架构与界面设计",
  "deadline": "2026-09-15",
  "deliverables": ["PDF实验报告"],
  "filename_rule": "班级-学号-姓名-实验3-软件架构与界面设计.pdf",
  "steps": ["完成设计", "整理报告", "转换PDF", "上传学习通"],
  "uncertain_fields": []
}
```

## 4 错误调用示例

```json
POST /api/extractions
{
  "source_text": ""
}
```

```json
400 Bad Request
{
  "error": "EMPTY_SOURCE_TEXT",
  "message": "请输入作业要求或上传txt、md文件。"
}
```

## 5 安全约束

- 通义千问API密钥只保存在服务端环境变量或本地 `.env` 中。
- 前端响应、错误提示和应用日志不得包含密钥或Authorization头。
- 未经用户确认的原始文本不作为正式作业长期保存。
- 模型输出必须通过字段白名单和类型校验。

