const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const TOOL_CONFIGS = {
  official_source_lookup: { title: "官方来源检索", scope: "仅核验申请政策、日期、费用和院校要求，并返回官方链接。", welcome: "告诉我需要核验的政策、日期、院校要求或官方信息。" },
  build_application_timeline: { title: "申请时间线", scope: "仅生成和调整申请时间线、里程碑与任务安排。", welcome: "请提供目标入学年份、申请体系、MCAT 日期和当前进度。" },
  compare_medical_schools: { title: "院校比较", scope: "仅依据你提供或知识库中的数据比较医学院。", welcome: "请提供学校名单、GPA、MCAT、州籍及希望比较的指标。" },
  evaluate_applicant_profile: { title: "申请档案评估", scope: "仅检查申请档案完整度和明显短板，不预测录取概率。", welcome: "请提供 GPA、MCAT、临床、跟诊、服务、科研和领导经历。" },
  match_prerequisites: { title: "先修课匹配", scope: "仅匹配已修课程与目标院校先修课要求。", welcome: "请提供已修课程和目标院校的官方 prerequisite 要求。" },
  application_calculator: { title: "申请计算器", scope: "仅计算 Overall/BCPM GPA 或申请费用。", welcome: "请选择计算 GPA 或申请费用，并提供课程或费用明细。" },
};

const state = {
  mode: "auto",
  history: [],
  busy: false,
  activeTool: null,
  toolBusy: false,
  toolHistories: Object.fromEntries(Object.keys(TOOL_CONFIGS).map((name) => [name, []])),
  settings: {
    apiKey: localStorage.getItem("medpath.deepseekKey") || "",
    model: localStorage.getItem("medpath.model") || "deepseek-chat",
    customPrompt: localStorage.getItem("medpath.customPrompt") || "",
  },
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

function formatAnswer(text) {
  return escapeHtml(text ?? "")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\n/g, "<br>");
}

function toast(message, type = "info") {
  const node = $("#toast");
  node.textContent = message;
  node.className = `toast show ${type === "error" ? "error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.className = "toast"; }, 3200);
}

function switchView(name) {
  if (!name || !$(`#${name}View`)) return;
  $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  $$(".view").forEach((view) => view.classList.remove("active"));
  $(`#${name}View`).classList.add("active");
  if (name === "knowledge") loadDocuments();
}

function updateApiStatus() {
  const connected = Boolean(state.settings.apiKey);
  $("#apiDot").classList.toggle("connected", connected);
  $("#apiStatusText").textContent = connected ? state.settings.model : "尚未配置";
}

function openSettings() {
  $("#apiKey").value = state.settings.apiKey;
  $("#model").value = state.settings.model;
  $("#customPrompt").value = state.settings.customPrompt;
  updatePromptCount();
  $("#settingsModal").hidden = false;
  $("#connectionResult").hidden = true;
  setTimeout(() => $("#apiKey").focus(), 0);
}

async function testConnection() {
  const apiKey = $("#apiKey").value.trim();
  const button = $("#testConnection");
  const result = $("#connectionResult");
  button.disabled = true;
  button.textContent = "连接中…";
  result.hidden = true;
  try {
    const response = await fetch("/api/deepseek/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apiKey }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "连接失败");
    result.className = "connection-result";
    result.textContent = `连接成功${data.models?.length ? `，可用模型：${data.models.join("、")}` : ""}`;
    result.hidden = false;
  } catch (error) {
    result.className = "connection-result error";
    result.textContent = error.message;
    result.hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = "测试连接";
  }
}

function closeSettings() { $("#settingsModal").hidden = true; }

function saveSettings() {
  state.settings.apiKey = $("#apiKey").value.trim();
  state.settings.model = $("#model").value;
  state.settings.customPrompt = $("#customPrompt").value.trim();
  localStorage.setItem("medpath.deepseekKey", state.settings.apiKey);
  localStorage.setItem("medpath.model", state.settings.model);
  localStorage.setItem("medpath.customPrompt", state.settings.customPrompt);
  updateApiStatus();
  closeSettings();
  toast(state.settings.apiKey ? "DeepSeek API 设置已保存" : "已保存，当前仅使用知识库");
}

function updatePromptCount() {
  $("#promptCount").textContent = `${$("#customPrompt").value.length}/2000`;
}

function resetChat() {
  state.history = [];
  $("#messages").innerHTML = "";
  $("#messages").classList.remove("active");
  $("#welcome").hidden = false;
  $("#question").focus();
}

function toolPromptKey(name) { return `medpath.toolPrompt.${name}`; }

function openTool(name) {
  const config = TOOL_CONFIGS[name];
  if (!config) {
    toast("工具配置无效，请强制刷新页面后重试", "error");
    return;
  }
  state.activeTool = name;
  $("#toolDirectory").hidden = true;
  $("#toolWorkspace").hidden = false;
  $("#activeToolTitle").textContent = config.title;
  $("#activeToolScope").textContent = config.scope;
  $("#toolCustomPrompt").value = localStorage.getItem(toolPromptKey(name)) || "";
  updateToolPromptCount();
  renderToolConversation();
  setTimeout(() => $("#toolQuestion").focus(), 0);
}

function closeTool() {
  state.activeTool = null;
  $("#toolWorkspace").hidden = true;
  $("#toolDirectory").hidden = false;
}

function toolMessageHtml(role, content, meta = {}) {
  if (role === "user") {
    return `<article class="tool-message user"><div>${escapeHtml(content)}</div><span>你</span></article>`;
  }
  const chips = (meta.tools || []).map((tool) => `<span class="tool-chip ${tool.status === "error" ? "error" : ""}">⌘ ${escapeHtml(tool.label)}</span>`).join("");
  const scopeClass = meta.outOfScope ? " out-of-scope" : "";
  return `<article class="tool-message assistant${scopeClass}"><span>M</span><div>${chips ? `<div class="tool-chips">${chips}</div>` : ""}<div class="message-content">${formatAnswer(content)}</div></div></article>`;
}

function renderToolConversation() {
  const name = state.activeTool;
  if (!name) return;
  const history = state.toolHistories[name];
  const welcome = TOOL_CONFIGS[name].welcome;
  $("#toolMessages").innerHTML = toolMessageHtml("assistant", welcome) + history.map((item) => toolMessageHtml(item.role, item.content, item.meta)).join("");
  $("#toolMessages").scrollTop = $("#toolMessages").scrollHeight;
}

function addToolTyping() {
  const node = document.createElement("article");
  node.className = "tool-message assistant";
  node.innerHTML = '<span>M</span><div><div class="typing"><span></span><span></span><span></span></div></div>';
  $("#toolMessages").appendChild(node);
  $("#toolMessages").scrollTop = $("#toolMessages").scrollHeight;
  return node;
}

async function askTool(question) {
  const name = state.activeTool;
  if (!name || state.toolBusy || !question.trim()) return;
  state.toolBusy = true;
  $("#toolSendButton").disabled = true;
  const history = state.toolHistories[name];
  history.push({ role: "user", content: question });
  renderToolConversation();
  const typing = addToolTyping();
  $("#toolQuestion").value = "";
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        activeTool: name,
        toolPrompt: localStorage.getItem(toolPromptKey(name)) || "",
        apiKey: state.settings.apiKey,
        model: state.settings.model,
        history: history.slice(0, -1).slice(-10),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "请求失败");
    typing.remove();
    history.push({ role: "assistant", content: data.answer || "工具没有返回内容，请重试。", meta: data });
    if (history.length > 20) history.splice(0, history.length - 20);
    renderToolConversation();
  } catch (error) {
    typing.remove();
    history.push({ role: "assistant", content: `暂时无法完成：${error.message}`, meta: { outOfScope: false } });
    renderToolConversation();
  } finally {
    state.toolBusy = false;
    $("#toolSendButton").disabled = false;
    $("#toolQuestion").focus();
  }
}

function updateToolPromptCount() {
  $("#toolPromptCount").textContent = `${$("#toolCustomPrompt").value.length}/2000`;
}

function saveToolPrompt() {
  if (!state.activeTool) return;
  localStorage.setItem(toolPromptKey(state.activeTool), $("#toolCustomPrompt").value.trim());
  toast(`${TOOL_CONFIGS[state.activeTool].title} Prompt 已保存`);
}

function addMessage(role, content, meta = {}) {
  $("#welcome").hidden = true;
  const messages = $("#messages");
  messages.classList.add("active");
  const node = document.createElement("article");
  node.className = `message ${role}`;
  if (role === "user") {
    node.innerHTML = `<div class="message-body"><div class="message-content">${escapeHtml(content)}</div></div><div class="avatar">你</div>`;
  } else {
    const sourceLabels = { hybrid: "知识库 + DEEPSEEK", knowledge: "知识库检索", deepseek: "DEEPSEEK 补充", none: "未找到信息" };
    const sources = (meta.sources || []).map((source) => `
      <div class="source-card">
        <strong>${escapeHtml(source.documentName)} · 片段 ${source.chunk}</strong>
        <p>${escapeHtml(source.text.slice(0, 240))}${source.text.length > 240 ? "…" : ""}</p>
      </div>`).join("");
    const tools = (meta.tools || []).map((tool) => `<span class="tool-chip ${tool.status === "error" ? "error" : ""}">⌘ ${escapeHtml(tool.label)}</span>`).join("");
    node.innerHTML = `<div class="avatar">M</div><div class="message-body">
      <div class="answer-label"><i></i>${sourceLabels[meta.source] || "申请助手"}</div>
      ${tools ? `<div class="tool-chips">${tools}</div>` : ""}
      <div class="message-content">${formatAnswer(content)}</div>
      ${sources ? `<details class="sources"><summary>查看 ${meta.sources.length} 条知识库依据</summary>${sources}</details>` : ""}
    </div>`;
  }
  messages.appendChild(node);
  $("#chatStage").scrollTo({ top: $("#chatStage").scrollHeight, behavior: "smooth" });
  return node;
}

function addTyping() {
  $("#welcome").hidden = true;
  const messages = $("#messages");
  messages.classList.add("active");
  const node = document.createElement("article");
  node.className = "message assistant";
  node.innerHTML = '<div class="avatar">M</div><div class="message-body"><div class="answer-label"><i></i>正在检索与分析</div><div class="typing"><span></span><span></span><span></span></div></div>';
  messages.appendChild(node);
  return node;
}

async function ask(question) {
  if (state.busy || !question.trim()) return;
  state.busy = true;
  $("#sendButton").disabled = true;
  addMessage("user", question);
  const typing = addTyping();
  $("#question").value = "";
  resizeTextarea();
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        mode: state.mode,
        apiKey: state.settings.apiKey,
        model: state.settings.model,
        customPrompt: state.settings.customPrompt,
        history: state.history,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "请求失败");
    typing.remove();
    addMessage("assistant", data.answer, data);
    state.history.push({ role: "user", content: question }, { role: "assistant", content: data.answer });
    state.history = state.history.slice(-12);
  } catch (error) {
    typing.remove();
    addMessage("assistant", `暂时无法完成回答：${error.message}`, { source: "none", sources: [] });
    toast(error.message, "error");
  } finally {
    state.busy = false;
    $("#sendButton").disabled = false;
    $("#question").focus();
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function loadDocuments() {
  try {
    const response = await fetch("/api/documents");
    const data = await response.json();
    renderDocuments(data.documents || []);
  } catch (error) {
    toast("无法读取知识库", "error");
  }
}

function renderDocuments(documents) {
  $("#docCount").textContent = documents.length;
  $("#docSummary").textContent = documents.length ? `${documents.length} 份资料，共 ${documents.reduce((sum, doc) => sum + doc.chunkCount, 0)} 个可检索片段` : "尚未添加资料";
  const list = $("#documentList");
  if (!documents.length) {
    list.innerHTML = '<div class="empty-state">知识库还是空的。添加申请指南、院校资料或个人笔记后即可开始检索。</div>';
    return;
  }
  list.innerHTML = documents.map((doc) => `
    <article class="document-item">
      <div class="file-type">${escapeHtml(doc.type)}</div>
      <div class="document-info"><strong title="${escapeHtml(doc.name)}">${escapeHtml(doc.name)}</strong><span>${formatBytes(doc.size)} · ${doc.chunkCount} 个片段 · ${new Date(doc.createdAt).toLocaleDateString("zh-CN")}</span></div>
      <button class="delete-button" data-delete="${doc.id}" title="删除文档" aria-label="删除 ${escapeHtml(doc.name)}">×</button>
    </article>`).join("");
}

async function uploadFiles(files) {
  if (!files.length) return;
  const form = new FormData();
  [...files].forEach((file) => form.append("files", file));
  toast(`正在处理 ${files.length} 个文件…`);
  try {
    const response = await fetch("/api/documents", { method: "POST", body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "上传失败");
    toast(`已收录 ${data.documents.length} 个文件`);
    await loadDocuments();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $("#fileInput").value = "";
  }
}

async function deleteDocument(id) {
  try {
    const response = await fetch(`/api/documents/${id}`, { method: "DELETE" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "删除失败");
    toast("文档已从知识库移除");
    await loadDocuments();
  } catch (error) { toast(error.message, "error"); }
}

function resizeTextarea() {
  const input = $("#question");
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 132)}px`;
}

$$('.nav-item').forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
$$('.mode').forEach((button) => button.addEventListener("click", () => {
  $$(".mode").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  state.mode = button.dataset.mode;
}));
$$('.suggestion').forEach((button) => button.addEventListener("click", () => ask(button.textContent.replace(/^\d+/, "").trim())));
$("#toolDirectory").addEventListener("click", (event) => {
  const button = event.target.closest(".tool-action[data-tool]");
  if (button) openTool(button.dataset.tool);
});
$("#backToTools").addEventListener("click", closeTool);
$("#toolChatForm").addEventListener("submit", (event) => { event.preventDefault(); askTool($("#toolQuestion").value); });
$("#toolQuestion").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#toolChatForm").requestSubmit(); }
});
$("#toolCustomPrompt").addEventListener("input", updateToolPromptCount);
$("#saveToolPrompt").addEventListener("click", saveToolPrompt);
$("#clearToolChat").addEventListener("click", () => {
  if (!state.activeTool) return;
  state.toolHistories[state.activeTool] = [];
  renderToolConversation();
});
$("#chatForm").addEventListener("submit", (event) => { event.preventDefault(); ask($("#question").value); });
$("#question").addEventListener("input", resizeTextarea);
$("#question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#chatForm").requestSubmit(); }
});
$("#newChat").addEventListener("click", resetChat);
$("#openSettings").addEventListener("click", openSettings);
$("#closeSettings").addEventListener("click", closeSettings);
$("#saveSettings").addEventListener("click", saveSettings);
$("#testConnection").addEventListener("click", testConnection);
$("#customPrompt").addEventListener("input", updatePromptCount);
$("#clearKey").addEventListener("click", () => { $("#apiKey").value = ""; saveSettings(); });
$("#toggleKey").addEventListener("click", () => {
  const input = $("#apiKey");
  input.type = input.type === "password" ? "text" : "password";
  $("#toggleKey").textContent = input.type === "password" ? "显示" : "隐藏";
});
$("#settingsModal").addEventListener("click", (event) => { if (event.target === $("#settingsModal")) closeSettings(); });
$("#uploadButton").addEventListener("click", () => $("#fileInput").click());
$("#browseButton").addEventListener("click", () => $("#fileInput").click());
$("#fileInput").addEventListener("change", (event) => uploadFiles(event.target.files));
$("#refreshDocs").addEventListener("click", loadDocuments);
$("#documentList").addEventListener("click", (event) => {
  const button = event.target.closest("[data-delete]");
  if (button) deleteDocument(button.dataset.delete);
});
const zone = $("#uploadZone");
["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => { event.preventDefault(); zone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => zone.addEventListener(name, (event) => { event.preventDefault(); zone.classList.remove("dragging"); }));
zone.addEventListener("drop", (event) => uploadFiles(event.dataTransfer.files));

updateApiStatus();
loadDocuments();
