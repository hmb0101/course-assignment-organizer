# AI辅助编码审查记录

## 任务与AI初稿

任务：为 Django 新建作业页面增加表单校验和自动化测试。AI给出的初稿使用了常见写法 `AssignmentForm(request.POST or None)`。

## 人工审查

代码语法正确，正常表单也能保存，但审查测试发现空POST字典为假值，会被替换为 `None`，从而把一次真实提交当成未提交，页面不显示必填错误。该问题不是界面成功截图能够发现的。

## 人工修改

将表单绑定改为按请求方法判断：

```python
form = AssignmentForm(request.POST if request.method == "POST" else None)
```

同时审查改变状态的接口，把步骤切换和删除限制为POST，避免用GET修改数据。

## 验证结果

增加空表单、重复数据、过期日期、GET方法限制等测试后执行 `python manage.py test -v 2`，9项测试全部通过。结论是AI初稿可用于提速，但是否满足HTTP语义、异常输入和测试要求必须由人工确认。
