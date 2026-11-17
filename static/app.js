const dialog = document.querySelector("#delete-dialog");
let pendingDeleteForm = null;
document.querySelectorAll("[data-delete-form]").forEach(form => {
  form.addEventListener("submit", event => {
    if (!dialog || typeof dialog.showModal !== "function") {
      if (!window.confirm("删除这条作业及其保存的要求？此操作无法撤销。")) event.preventDefault();
      return;
    }
    event.preventDefault();
    pendingDeleteForm = form;
    dialog.showModal();
  });
});
document.querySelector("[data-dialog-cancel]")?.addEventListener("click", () => dialog.close());
document.querySelector("[data-dialog-confirm]")?.addEventListener("click", () => {
  if (pendingDeleteForm) HTMLFormElement.prototype.submit.call(pendingDeleteForm);
});
dialog?.addEventListener("close", () => { pendingDeleteForm = null; });
document.querySelectorAll("[data-copy]").forEach(button => {
  const label = button.querySelector("span");
  const icon = button.querySelector("use");
  const defaultLabel = label?.textContent || "复制命名规则";
  let resetTimer = null;
  let copyPending = false;

  button.addEventListener("click", async () => {
    if (copyPending) return;
    copyPending = true;
    window.clearTimeout(resetTimer);
    const status = document.querySelector("#interaction-status");
    if (status) status.textContent = "";

    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      if (label) label.textContent = "已复制";
      icon?.setAttribute("href", "#i-check");
      button.classList.add("is-copied");
      if (status) status.textContent = "文件命名规则已复制。";
    } catch {
      if (label) label.textContent = "请选中文字复制";
      icon?.setAttribute("href", "#i-copy");
      button.classList.remove("is-copied");
      if (status) status.textContent = "暂时无法访问剪贴板，请选中文件命名规则后手动复制。";
    } finally {
      copyPending = false;
      resetTimer = window.setTimeout(() => {
        if (label) label.textContent = defaultLabel;
        icon?.setAttribute("href", "#i-copy");
        button.classList.remove("is-copied");
        resetTimer = null;
      }, 2000);
    }
  });
});

const searchInput = document.querySelector("#assignment-search");
document.addEventListener("keydown", event => {
  if (!searchInput || event.isComposing || event.defaultPrevented) return;
  if (event.key === "Escape" && document.activeElement === searchInput) {
    event.preventDefault();
    searchInput.value = "";
    searchInput.dispatchEvent(new Event("input", { bubbles: true }));
    return;
  }
  if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
  const target = event.target;
  const isEditing = target instanceof Element && (
    target.matches("input, textarea, select") || target.isContentEditable
  );
  if (isEditing || document.querySelector("dialog[open]")) return;
  event.preventDefault();
  searchInput.focus();
});

const sourceInput = document.querySelector('textarea[name="source_text"]');
const sourceCount = document.querySelector("#source-char-count");
if (sourceInput && sourceCount) {
  const updateSourceCount = () => {
    sourceCount.textContent = `${Array.from(sourceInput.value).length} 字`;
  };
  sourceInput.addEventListener("input", updateSourceCount);
  updateSourceCount();
}

document.querySelectorAll("[data-submission-form]").forEach(form => {
  form.addEventListener("submit", event => {
    if (event.defaultPrevented) return;
    const button = form.querySelector("button");
    if (button) button.disabled = true;
  });
});

// Keep the calendar available above the list on compact screens without
// pushing every assignment below the fold. A selected date stays expanded.
const deadlineCalendar = document.querySelector("[data-calendar]");
if (deadlineCalendar) {
  const compactLayout = window.matchMedia("(max-width: 1100px)");
  const adaptCalendar = () => {
    deadlineCalendar.open = !compactLayout.matches || deadlineCalendar.dataset.selectedDay === "yes";
  };
  adaptCalendar();
  compactLayout.addEventListener("change", adaptCalendar);
}
