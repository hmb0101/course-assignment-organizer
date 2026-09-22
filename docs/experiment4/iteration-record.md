# 实验4迭代记录

## 初版 v0.1.0-initial

- 建立 Django、SQLite 项目骨架和 assignments 业务模块。
- 完成作业列表、新建、详情查看以及任务步骤持久化。
- 提供 `seed_demo` 命令初始化样例数据。
- 首次启动发现 `enumerate` 的生成器参数缺少括号，修正后通过迁移和 `manage.py check`。

## 修订版 v0.2.0-revised

- 增加作业编辑、删除和任务步骤完成状态切换。
- 增加截止时间、重复作业、空步骤和重复步骤校验。
- 所有改变状态的操作限定为 POST，并保留 CSRF 防护。
- 增加空状态、404 错误页面、文件日志、数据清理与恢复命令。
- 建立 9 项自动化测试并全部通过。

## 复现命令

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py reset_demo
python manage.py test
python manage.py runserver 127.0.0.1:8000
```
