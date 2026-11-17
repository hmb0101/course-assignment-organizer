const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const mode = process.argv[2];
const origin = process.argv[3] || "http://127.0.0.1:8788";
const output = process.argv[4];
const formURL = origin + "/assignments/new/";
function dateAfter(days) {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai", year: "numeric",
    month: "2-digit", day: "2-digit" }).format(new Date(Date.now() + days * 86400000));
}
function chineseDate(date) {
  const [year, month, day] = date.split("-").map(Number);
  return `${year}年${month}月${day}日`;
}
const deadline = dateAfter(7);
const notice = (title, scenario = "") => [
  "课程：软件应用开发实践", "作业：" + title, "截止时间：" + chineseDate(deadline),
  "提交物：集成报告.pdf", scenario && "测试：" + scenario,
].filter(Boolean).join("\n");
const report = (id, detail) => console.log(id + " PASS " + detail);
const input = (page, name) => page.locator('[name="' + name + '"]');
const feedback = page => page.locator("[data-draft-feedback]");
const generates = page => page.locator("[data-draft-generate]");

async function record(page, name) {
  if (!output) return;
  fs.mkdirSync(output, { recursive: true });
  await page.mouse.move(1260, 10);
  await page.screenshot({ path: path.join(output, name + ".png"), fullPage: true, animations: "disabled" });
}

async function status(page, name) {
  await page.locator('[data-draft-feedback][data-state="' + name + '"]').waitFor({ timeout: 20000 });
}

async function begin(page, text) {
  await input(page, "source_text").fill(text);
  await generates(page).click();
}

async function checkSaved(page, title) {
  const detail = page.waitForURL(/\/assignments\/\d+\/$/);
  await page.getByRole("button", { name: "保存作业" }).click();
  await detail;
  await page.reload();
  assert.equal(await page.locator("h1").innerText(), title);
}

async function baseline(page) {
  await page.goto(formURL);
  const sent = page.waitForRequest(req => req.method() === "POST" && req.url() === formURL);
  await input(page, "source_text").fill(notice("基线草稿", "慢速"));
  const submit = page.getByRole("button", { name: "生成草稿" }).click();
  await sent;
  assert.equal(await page.getByRole("button", { name: "取消等待" }).count(), 0);
  await submit;
  await page.locator(".draft-feedback-draft").waitFor();
  assert.equal(await input(page, "title").inputValue(), "基线草稿");
  report("B01", "同步提交可生成草稿，请求期间没有等待提示或取消入口");
  await checkSaved(page, "基线草稿");
  report("B02", "人工确认后保存，刷新详情仍可查看");
}

async function live(page) {
  await page.goto(formURL);
  await begin(page, notice("AI能力与软件系统集成"));
  await status(page, "draft");
  assert.equal(await input(page, "title").inputValue(), "AI能力与软件系统集成");
  assert.equal(await input(page, "deadline").inputValue(), deadline);
  await record(page, "预填草稿");
  const edited = "实验八集成报告";
  await input(page, "title").fill(edited);
  await checkSaved(page, edited);
  await record(page, "确认保存");
  report("L01", "真实千问生成草稿，修改标题后保存，刷新详情保留修改值");
}

async function revised(page, context) {
  await page.goto(formURL);
  const original = notice("交互验证");
  const other = await context.newPage();
  await begin(page, original);
  await status(page, "draft");
  assert.equal(await input(page, "source_text").inputValue(), original);
  assert.equal(await input(page, "title").inputValue(), "交互验证");
  assert.equal(await input(page, "deadline").inputValue(), deadline);
  await other.goto(origin + "/?q=" + encodeURIComponent("交互验证"));
  assert.doesNotMatch(await other.locator("main").innerText(), /集成报告\.pdf/);
  await input(page, "deliverables").fill("人工确认附件.docx");
  await checkSaved(page, "交互验证");
  assert.match(await page.locator("main").innerText(), /人工确认附件\.docx/);
  report("T01", "预填阶段保留原文，确认后保存人工修改值");

  await page.goto(formURL);
  await begin(page, " ");
  await status(page, "manual");
  assert.match(await feedback(page).innerText(), /4000/);
  report("T02", "后端拒绝空白原文");

  await page.goto(formURL);
  await input(page, "title").fill("人工标题保留");
  await begin(page, notice("日期冲突") + "\n教师群通知截止时间为" + chineseDate(dateAfter(9)) + "，目前未确认以哪个为准。");
  await status(page, "needs_review");
  assert.equal(await input(page, "deadline").inputValue(), "");
  assert.equal(await input(page, "title").inputValue(), "人工标题保留");
  assert.equal(await page.locator(".field-pending").isVisible(), true);
  await record(page, "日期待确认");
  await input(page, "deadline").fill(deadline);
  assert.equal(await page.locator(".field-pending").isVisible(), false);
  report("T03", "冲突日期留空，待确认提示随人工填写消失");

  await page.goto(formURL);
  const failed = notice("手工录入示例", "模拟超时");
  await begin(page, failed);
  await status(page, "manual");
  assert.match(await feedback(page).innerText(), /超时/);
  assert.equal(await input(page, "source_text").inputValue(), failed);
  await record(page, "模拟超时");
  await input(page, "title").fill("手工录入示例");
  await input(page, "course_name").fill("软件应用开发实践");
  await input(page, "deadline").fill(deadline);
  await input(page, "deliverables").fill("集成报告.pdf");
  await checkSaved(page, "手工录入示例");
  report("T04", "模拟超时保留原文，手工填写后保存成功");

  await page.goto(formURL);
  await begin(page, notice("无效输出示例", "无效输出"));
  await status(page, "manual");
  assert.match(await feedback(page).innerText(), /JSON/);
  await begin(page, notice("重试示例"));
  await status(page, "draft");
  assert.equal(await input(page, "title").inputValue(), "重试示例");
  report("T05", "拒绝非法JSON后重试，正确预填新结果");

  await page.goto(formURL);
  const requests = [];
  page.on("request", req => {
    if (req.url().endsWith("/new/draft/") && req.method() === "POST") requests.push(req);
  });
  await begin(page, notice("取消测试", "慢速"));
  await status(page, "processing");
  assert.equal(await generates(page).isDisabled(), true);
  await page.locator("form[data-draft-url]").evaluate(form => {
    form.requestSubmit(form.querySelector("[data-draft-generate]"));
  });
  await record(page, "生成等待");
  await page.getByRole("button", { name: "取消等待" }).click();
  await status(page, "cancelled");
  await begin(page, notice("取消后重试"));
  await status(page, "draft");
  await page.waitForTimeout(8200);
  assert.equal(await input(page, "title").inputValue(), "取消后重试");
  assert.equal(requests.length, 2);
  report("T06", "等待时拦截重复提交，取消后旧结果未覆盖重试草稿");

  await page.goto(formURL);
  await begin(page, notice("刷新前的草稿", "慢速"));
  await status(page, "processing");
  await page.reload();
  await status(page, "cancelled");
  assert.match(await feedback(page).innerText(), /刷新中断/);
  assert.equal(await input(page, "title").inputValue(), "");
  report("T07", "刷新后提示重新操作，旧草稿没有回填");

  await page.goto(formURL);
  await other.goto(formURL);
  const taskA = page.waitForRequest(req => req.url().endsWith("/new/draft/"));
  await begin(page, notice("任务甲", "慢速"));
  await status(page, "processing");
  const taskB = other.waitForRequest(req => req.url().endsWith("/new/draft/"));
  await begin(other, notice("任务乙"));
  await status(other, "draft");
  assert.equal(await feedback(page).getAttribute("data-state"), "processing");
  assert.equal(await input(other, "title").inputValue(), "任务乙");
  await status(page, "draft");
  assert.equal(await input(page, "title").inputValue(), "任务甲");
  const id = request => new URLSearchParams(request.postData()).get("task_id");
  assert.notEqual(id(await taskA), id(await taskB));
  report("T08", "两标签先发甲、先回乙，任务编号与草稿各自对应");

  await page.goto(formURL);
  await begin(page, original);
  await status(page, "draft");
  await page.getByRole("button", { name: "保存作业" }).click();
  await page.locator(".form-alert").waitFor();
  assert.match(await page.locator(".form-alert").innerText(), /已存在/);
  report("T09", "再次保存同一课程、作业和日期，页面提示记录已存在");

  await page.goto(formURL);
  await begin(page, "请帮我登录学习通并提交文件");
  await status(page, "out_of_scope");
  assert.match(await feedback(page).innerText(), /不识图、登录或代交/);
  await begin(page, notice("拒绝示例", "拒绝"));
  await status(page, "out_of_scope");
  report("T10", "本地越界输入和模型返回的越界结果均显示能力范围提示");

  await page.goto(formURL);
  await begin(page, notice("放弃示例"));
  await status(page, "draft");
  await input(page, "title").fill("人工保留标题");
  await page.getByRole("button", { name: "放弃草稿" }).click();
  assert.equal(await input(page, "title").inputValue(), "人工保留标题");
  assert.equal(await input(page, "deadline").inputValue(), "");
  assert.equal(await input(page, "source_text").inputValue(), notice("放弃示例"));
  report("T11", "放弃草稿只清空未经修改的预填字段");

  await page.goto(formURL);
  await page.route("**/assignments/new/draft/", route => route.abort("internetdisconnected"));
  await begin(page, notice("断网示例"));
  await status(page, "manual");
  assert.match(await feedback(page).innerText(), /连接中断/);
  assert.equal(await input(page, "source_text").inputValue(), notice("断网示例"));
  report("T12", "浏览器请求中断时保留原文并提示重试或手工填写");
}

(async () => {
  const browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {});
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 950 } });
    const page = await context.newPage();
    if (mode === "--baseline") await baseline(page);
    else if (mode === "--live") await live(page);
    else await revised(page, context);
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
