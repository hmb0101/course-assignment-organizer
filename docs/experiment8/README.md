# 实验八 作业草稿的网页集成

打开“新增作业”，粘贴老师发布的通知并点击“生成草稿”。右侧预填可核对的字段，截止日期存在冲突时留空，填写确认后的日期再保存。接口异常时可以保留原文并手工填写。

## 本地运行

先按项目 README 安装依赖、迁移数据库并启动 Django。配置见 `experiments/experiment7/.env.example`。已有配置文件可通过 `ASSIGNMENT_AI_ENV` 指定，配置文件留在本机。草稿生成会把粘贴的通知发送给通义千问。作业保存在本地 SQLite。

生成接口为 `POST /assignments/new/draft/`，使用 CSRF 校验并接收 `task_id` 和 `source_text`。响应包含任务编号、状态、提示、预填字段和待确认项。预填保留手工输入。最终保存沿用新增作业表单与数据库的课程、名称、截止日期唯一约束。

浏览器用独立任务编号核对响应。同一页面等待期间只提交一次。取消停止页面等待，已发送到服务端的请求仍可返回，迟到结果不会回填。刷新后依据标签页的等待标记提示重做，草稿和模型原始响应不会写入任务表。应用日志记录任务编号、状态、错误码、调用次数和耗时。

## 复测

浏览器脚本使用 Playwright。准备 Node.js 环境并安装 Playwright 和 Chromium，也可把 `PLAYWRIGHT_CHANNEL` 设为 `chrome` 来使用已有的 Chrome。

```powershell
python manage.py test
python docs/experiment8/test_server.py --db .ui-preview/exp8-check.sqlite3 --port 8788
# 在另一终端运行，DB 路径应为新文件，其父目录应已存在
node docs/experiment8/browser-checks.cjs --fixture http://127.0.0.1:8788
```

受控测试服务器只绑定到本机，替换模型传输层以模拟延迟、超时、拒绝和异常 JSON，其他步骤仍经过 Django、原型校验和 SQLite。启动配置真实千问的独立演示数据库后，可用 `--live` 验证一次真实请求。脚本最后一个可选参数是截图输出目录。

基线版本为 `a732e53`。可在另一个 Git 工作区检出基线，用当前版本的 `test_server.py` 的 `--project` 指向基线项目，再用 `browser-checks.cjs --baseline` 对照同步生成与保存行为。
