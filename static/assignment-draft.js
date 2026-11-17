const draftForm = document.querySelector("[data-draft-url]");

if (draftForm && window.fetch && window.AbortController && window.crypto?.randomUUID) {
  const source = draftForm.elements.source_text;
  const generate = draftForm.querySelector("[data-draft-generate]");
  const buttonLabel = generate.querySelector("span");
  const cancel = draftForm.querySelector("[data-draft-cancel]");
  const discard = draftForm.querySelector("[data-draft-discard]");
  const save = draftForm.querySelector("[data-save-assignment]");
  const feedback = draftForm.querySelector("[data-draft-feedback]");
  const message = feedback.querySelector("[data-draft-message]");
  const review = feedback.querySelector("[data-draft-review]");
  const evidence = feedback.querySelector("[data-draft-evidence]");
  const deadline = draftForm.elements.deadline;
  const deadlineField = deadline.closest(".field");
  const deadlineBadge = deadlineField.querySelector(".field-pending");
  const optional = draftForm.querySelector(".optional-fields");
  const refreshKey = "assignment-draft-pending";
  const seeded = new Map();
  let active = null;
  let saving = false;
  let reviewResult = null;

  function feedbackText(state, text) {
    feedback.dataset.state = state;
    feedback.hidden = !text;
    message.textContent = text;
  }

  function updateReview() {
    const reviewing = reviewResult && (feedback.dataset.state === "needs_review" || feedback.dataset.state === "reviewed");
    const missing = reviewing
      ? reviewResult.review.filter(item => !draftForm.elements.namedItem(item.name)?.value.trim())
      : [];
    review.textContent = missing.length ? "待确认：" + missing.map(item => item.label).join("、") : "";
    review.hidden = !missing.length;
    const datePending = missing.some(item => item.name === "deadline");
    deadlineBadge.hidden = !datePending;
    deadlineField.classList.toggle("has-pending-review", datePending);
    evidence.textContent = datePending ? reviewResult.deadline_text : "";
    evidence.hidden = !evidence.textContent;
    if (reviewing) {
      feedbackText(missing.length ? "needs_review" : "reviewed",
        missing.length ? reviewResult.message : "待确认字段已填写，请核对后保存。");
    }
  }

  function rememberPending(pending) {
    try {
      if (pending) sessionStorage.setItem(refreshKey, "1");
      else sessionStorage.removeItem(refreshKey);
    } catch {
      // Draft generation also works when the browser blocks session storage.
    }
  }

  function pendingControls(pending) {
    generate.disabled = pending;
    save.disabled = pending;
    cancel.hidden = !pending;
    discard.hidden = pending || !seeded.size;
  }

  function clearGeneratedFields() {
    for (const [field, value] of seeded) {
      if (field.value === value) field.value = "";
    }
    seeded.clear();
    reviewResult = null;
    updateReview();
  }

  function stopWaiting(text) {
    const previous = active;
    if (!previous) return;
    active = null;
    previous.controller.abort();
    rememberPending(false);
    pendingControls(false);
    buttonLabel.textContent = "重新生成";
    feedbackText("cancelled", text);
    updateReview();
  }

  async function generateDraft() {
    if (active || saving) return;
    const task = { id: crypto.randomUUID(), controller: new AbortController() };
    const body = new URLSearchParams({
      task_id: task.id,
      source_text: source.value,
      csrfmiddlewaretoken: draftForm.elements.csrfmiddlewaretoken.value,
    });
    active = task;
    rememberPending(true);
    pendingControls(true);
    feedbackText("processing", "正在生成草稿，请稍候。");
    updateReview();
    try {
      const response = await fetch(draftForm.dataset.draftUrl, {
        method: "POST",
        body,
        signal: task.controller.signal,
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("draft request failed");
      const result = await response.json();
      if (active !== task) return;
      if (result.task_id !== task.id) throw new Error("draft task mismatch");
      if (result.status === "draft" || result.status === "needs_review") {
        clearGeneratedFields();
        for (const [name, value] of Object.entries(result.fields)) {
          const field = draftForm.elements.namedItem(name);
          if (!field || field.value.trim() || !value) continue;
          field.value = value;
          if (field.value) seeded.set(field, field.value);
        }
        if (["submission_method", "filename_rule", "content_requirements"]
          .some(name => draftForm.elements.namedItem(name).value)) optional.open = true;
        reviewResult = result.status === "needs_review" ? result : null;
      }
      feedbackText(result.status, result.message);
      updateReview();
    } catch {
      if (active === task) feedbackText("manual", "连接中断。原文已保留，可重试或手工填写。");
    } finally {
      if (active === task) {
        active = null;
        rememberPending(false);
        pendingControls(false);
        buttonLabel.textContent = "重新生成";
      }
    }
  }

  draftForm.addEventListener("submit", event => {
    if (event.submitter === generate) {
      event.preventDefault();
      generateDraft();
      return;
    }
    if (active || saving) {
      event.preventDefault();
      return;
    }
    saving = true;
    save.disabled = true;
  });
  draftForm.addEventListener("input", event => {
    if (event.target !== source) {
      updateReview();
      return;
    }
    if (!active && !seeded.size && !reviewResult) return;
    clearGeneratedFields();
    if (active) stopWaiting("原文已修改，请重新生成草稿。");
    else {
      pendingControls(false);
      feedbackText("cancelled", "原文已修改，请重新生成草稿。");
    }
  });
  cancel.addEventListener("click", () => {
    stopWaiting("已停止等待。可以重新生成或手工填写。");
    generate.focus();
  });
  discard.addEventListener("click", () => {
    clearGeneratedFields();
    pendingControls(false);
    feedbackText("cancelled", "已放弃草稿。原文和手工修改已保留。");
    generate.focus();
  });

  if (performance.getEntriesByType("navigation")[0]?.type === "reload") {
    try {
      if (sessionStorage.getItem(refreshKey)) {
        feedbackText("cancelled", "刷新中断了上一次等待。请检查原文并重新生成。");
      }
    } catch {
      // The native form remains usable with storage restrictions.
    }
  }
  rememberPending(false);
  window.addEventListener("pageshow", event => {
    if (!event.persisted) return;
    saving = false;
    if (active) stopWaiting("离开页面中断了等待，请重新生成草稿。");
    pendingControls(false);
  });
}
