const state = {
  currentDate: "",
  employees: [],
  performances: [],
};

const navItems = Array.from(document.querySelectorAll(".nav-item"));
const views = Array.from(document.querySelectorAll(".view"));

const globalDate = document.getElementById("globalDate");
const ocrDate = document.getElementById("ocrDate");
const rankingDate = document.getElementById("rankingDate");
const perfDateFilter = document.getElementById("perfDateFilter");

const statStaff = document.getElementById("statStaff");
const statDeal = document.getElementById("statDeal");
const statIntent = document.getElementById("statIntent");
const statPrivate = document.getElementById("statPrivate");
const championName = document.getElementById("championName");
const championMetrics = document.getElementById("championMetrics");
const topThreeList = document.getElementById("topThreeList");

const uploadForm = document.getElementById("uploadForm");
const photoInput = document.getElementById("photoInput");
const uploadMsg = document.getElementById("uploadMsg");
const parsedBody = document.getElementById("parsedBody");
const submitFixBtn = document.getElementById("submitFixBtn");

const employeeSearch = document.getElementById("employeeSearch");
const employeeSearchBtn = document.getElementById("employeeSearchBtn");
const addEmployeeBtn = document.getElementById("addEmployeeBtn");
const employeeBody = document.getElementById("employeeBody");

const perfEmployeeFilter = document.getElementById("perfEmployeeFilter");
const perfFilterBtn = document.getElementById("perfFilterBtn");
const addPerfBtn = document.getElementById("addPerfBtn");
const performanceBody = document.getElementById("performanceBody");

const refreshRankingBtn = document.getElementById("refreshRankingBtn");
const rankingBody = document.getElementById("rankingBody");
const posterGrid = document.getElementById("posterGrid");

const modal = document.getElementById("modal");
const modalTitle = document.getElementById("modalTitle");
const modalForm = document.getElementById("modalForm");
const modalCancel = document.getElementById("modalCancel");
const modalConfirm = document.getElementById("modalConfirm");

let modalSubmit = null;

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function numberFmt(value) {
  return new Intl.NumberFormat("zh-CN").format(Number(value || 0));
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail = data?.detail || `请求失败(${response.status})`;
    throw new Error(detail);
  }
  return data;
}

function showMessage(message, isError = false) {
  uploadMsg.textContent = message;
  uploadMsg.className = `msg ${isError ? "err" : "ok"}`;
}

const VIEW_TITLES = {
  dashboard: { title: "仪表盘", subtitle: "统一管理：识别、录入、排名、喜报生成" },
  ocr: { title: "OCR 上传", subtitle: "上传白板照片，自动识别业绩数据" },
  employees: { title: "员工管理", subtitle: "管理销售团队成员信息" },
  performances: { title: "业绩管理", subtitle: "录入与查询员工每日业绩数据" },
  ranking: { title: "排名喜报", subtitle: "查看每日排名并生成销冠喜报" },
};

function switchView(viewKey) {
  navItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.view === viewKey);
  });

  views.forEach((view) => {
    view.classList.toggle("active", view.id === `view-${viewKey}`);
  });

  const info = VIEW_TITLES[viewKey];
  if (info) {
    const titleEl = document.getElementById("topbarTitle");
    const subtitleEl = document.getElementById("topbarSubtitle");
    if (titleEl) titleEl.textContent = info.title;
    if (subtitleEl) subtitleEl.textContent = info.subtitle;
  }
}

function openModal(config) {
  modalTitle.textContent = config.title;
  modalForm.innerHTML = config.fields
    .map((field) => {
      if (field.type === "select") {
        const options = (field.options || [])
          .map((opt) => {
            const selected = String(opt.value) === String(field.value ?? "") ? "selected" : "";
            return `<option value="${escapeHtml(opt.value)}" ${selected}>${escapeHtml(opt.label)}</option>`;
          })
          .join("");
        return `<label>${field.label}<select name="${field.name}" ${field.required ? "required" : ""}>${options}</select></label>`;
      }

      return `<label>${field.label}<input name="${field.name}" type="${field.type || "text"}" value="${escapeHtml(
        field.value ?? ""
      )}" ${field.required ? "required" : ""} ${field.min != null ? `min="${field.min}"` : ""} ${
        field.max != null ? `max="${field.max}"` : ""
      } ${field.step != null ? `step="${field.step}"` : ""} /></label>`;
    })
    .join("");

  modalSubmit = config.onSubmit;
  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
  modalForm.innerHTML = "";
  modalSubmit = null;
}

function getModalValues() {
  const formData = new FormData(modalForm);
  const output = {};
  for (const [key, value] of formData.entries()) {
    output[key] = String(value).trim();
  }
  return output;
}

function renderDashboard(data) {
  statStaff.textContent = numberFmt(data.staff_count);
  statDeal.textContent = numberFmt(data.total_deal);
  statIntent.textContent = numberFmt(data.total_high_intent);
  statPrivate.textContent = numberFmt(data.total_private_domain);

  if (data.champion) {
    championName.textContent = data.champion.employee_name;
    championMetrics.textContent = `成交量 ${data.champion.deal_count} · 高意向 ${data.champion.high_intent_count} · 私域新增 ${data.champion.private_domain_new}`;
  } else {
    championName.textContent = "暂无";
    championMetrics.textContent = "请先录入今日数据";
  }

  if (!data.top_three?.length) {
    topThreeList.innerHTML = '<li class="top3-empty">暂无数据，请先录入今日业绩</li>';
    return;
  }

  const rankClass = (r) => r === 1 ? "top3-rank-1" : r === 2 ? "top3-rank-2" : r === 3 ? "top3-rank-3" : "top3-rank-n";
  topThreeList.innerHTML = data.top_three
    .map(
      (item) => `<li class="top3-item">
        <div class="top3-rank ${rankClass(item.rank)}">${item.rank}</div>
        <span class="top3-name">${escapeHtml(item.employee_name)}</span>
        <div class="top3-stats">成交 ${item.deal_count}<br>意向 ${item.high_intent_count} / 私域 ${item.private_domain_new}</div>
      </li>`
    )
    .join("");
}

function renderParsed(records = []) {
  if (!records.length) {
    parsedBody.innerHTML = '<tr><td class="empty" colspan="5">暂无识别数据</td></tr>';
    return;
  }

  parsedBody.innerHTML = records
    .map(
      (item) => `<tr>
      <td><input data-key="employee_name" value="${escapeHtml(item.employee_name)}" /></td>
      <td><input data-key="deal_count" type="number" min="0" value="${Number(item.deal_count || 0)}" /></td>
      <td><input data-key="high_intent_count" type="number" min="0" value="${Number(item.high_intent_count || 0)}" /></td>
      <td><input data-key="private_domain_new" type="number" min="0" value="${Number(item.private_domain_new || 0)}" /></td>
      <td><input data-key="confidence" type="number" min="0" max="1" step="0.01" value="${Number(item.confidence || 0).toFixed(2)}" /></td>
    </tr>`
    )
    .join("");
}

function collectParsedRows() {
  const rows = Array.from(parsedBody.querySelectorAll("tr"));
  const records = [];

  rows.forEach((row) => {
    const inputs = Array.from(row.querySelectorAll("input"));
    if (!inputs.length) {
      return;
    }

    const item = {};
    inputs.forEach((input) => {
      item[input.dataset.key] = input.value;
    });

    if (!(item.employee_name || "").trim()) {
      return;
    }

    records.push({
      employee_name: item.employee_name.trim(),
      deal_count: Number(item.deal_count || 0),
      high_intent_count: Number(item.high_intent_count || 0),
      private_domain_new: Number(item.private_domain_new || 0),
      confidence: Number(item.confidence || 1),
    });
  });

  return records;
}

function renderEmployees(items = []) {
  if (!items.length) {
    employeeBody.innerHTML = '<tr><td class="empty" colspan="5">暂无员工</td></tr>';
    return;
  }

  employeeBody.innerHTML = items
    .map(
      (item) => `<tr>
      <td><span style="color:var(--text-tertiary);font-size:12px">#${item.id}</span></td>
      <td><strong>${escapeHtml(item.name)}</strong></td>
      <td>${item.performance_count} 条</td>
      <td style="color:var(--text-tertiary);font-size:12.5px">${item.created_at || "-"}</td>
      <td>
        <div class="action-group">
          <button class="btn sm" data-action="edit-employee" data-id="${item.id}">编辑</button>
          <button class="btn danger sm" data-action="delete-employee" data-id="${item.id}">删除</button>
        </div>
      </td>
    </tr>`
    )
    .join("");
}

function renderPerformanceFilterOptions() {
  const current = perfEmployeeFilter.value;
  const options = ['<option value="">全部</option>']
    .concat(state.employees.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`))
    .join("");

  perfEmployeeFilter.innerHTML = options;
  perfEmployeeFilter.value = current || "";
}

function renderPerformances(items = []) {
  if (!items.length) {
    performanceBody.innerHTML = '<tr><td class="empty" colspan="8">暂无业绩记录</td></tr>';
    return;
  }

  const confidenceBadge = (v) => {
    const n = Number(v);
    if (n >= 0.85) return `<span class="confidence-badge confidence-high">${n.toFixed(2)}</span>`;
    if (n >= 0.6) return `<span class="confidence-badge confidence-mid">${n.toFixed(2)}</span>`;
    return `<span class="confidence-badge confidence-low">${n.toFixed(2)}</span>`;
  };
  performanceBody.innerHTML = items
    .map(
      (item) => `<tr>
      <td><span style="color:var(--text-tertiary);font-size:12px">#${item.id}</span></td>
      <td>${item.report_date}</td>
      <td><strong>${escapeHtml(item.employee_name)}</strong></td>
      <td><strong>${item.deal_count}</strong></td>
      <td>${item.high_intent_count}</td>
      <td>${item.private_domain_new}</td>
      <td>${confidenceBadge(item.confidence)}</td>
      <td>
        <div class="action-group">
          <button class="btn sm" data-action="edit-performance" data-id="${item.id}">编辑</button>
          <button class="btn danger sm" data-action="delete-performance" data-id="${item.id}">删除</button>
        </div>
      </td>
    </tr>`
    )
    .join("");
}

function renderRanking(ranking = []) {
  if (!ranking.length) {
    rankingBody.innerHTML = '<tr><td class="empty" colspan="5">暂无排名数据</td></tr>';
    return;
  }

  const rankBadgeStyle = (r) => {
    if (r === 1) return `background:linear-gradient(135deg,#f59e0b,#fbbf24);color:#fff;box-shadow:0 2px 8px rgba(245,158,11,0.4)`;
    if (r === 2) return `background:linear-gradient(135deg,#94a3b8,#cbd5e1);color:#fff`;
    if (r === 3) return `background:linear-gradient(135deg,#b45309,#d97706);color:#fff`;
    return `background:var(--gray-200);color:var(--gray-600)`;
  };
  rankingBody.innerHTML = ranking
    .map(
      (item) => `<tr>
      <td><span class="rank-badge" style="${rankBadgeStyle(item.rank)}">${item.rank}</span></td>
      <td><strong>${escapeHtml(item.employee_name)}</strong></td>
      <td><strong>${item.deal_count}</strong></td>
      <td>${item.high_intent_count}</td>
      <td>${item.private_domain_new}</td>
    </tr>`
    )
    .join("");
}

function renderPosters(posters = []) {
  if (!posters.length) {
    posterGrid.innerHTML = '<p class="empty">暂无喜报</p>';
    return;
  }

  posterGrid.innerHTML = posters
    .map(
      (item) => `<article class="poster">
      <img src="${item.url}" alt="${escapeHtml(item.employee_name)} 喜报" />
      <div class="info">
        <strong>TOP ${item.rank} · ${escapeHtml(item.employee_name)}</strong><br />
        <a href="${item.url}" target="_blank" rel="noreferrer">打开原图</a>
      </div>
    </article>`
    )
    .join("");
}

async function loadDashboard() {
  const data = await apiRequest(`/api/dashboard?report_date=${encodeURIComponent(state.currentDate)}`);
  renderDashboard(data);
}

async function loadEmployees(keyword = "") {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  const data = await apiRequest(`/api/employees${query}`);
  state.employees = data.items || [];
  renderEmployees(state.employees);
  renderPerformanceFilterOptions();
}

async function loadPerformances() {
  const dateFilter = perfDateFilter.value || "";
  const employeeId = perfEmployeeFilter.value || "";

  const params = new URLSearchParams();
  if (dateFilter) {
    params.set("report_date", dateFilter);
  }
  if (employeeId) {
    params.set("employee_id", employeeId);
  }

  const query = params.toString() ? `?${params.toString()}` : "";
  const data = await apiRequest(`/api/performances${query}`);
  state.performances = data.items || [];
  renderPerformances(state.performances);
}

async function loadRanking() {
  const targetDate = rankingDate.value || state.currentDate;
  const data = await apiRequest(`/api/ranking?report_date=${encodeURIComponent(targetDate)}`);
  renderRanking(data.ranking || []);
  renderPosters(data.posters || []);
}

async function refreshMainViews() {
  await Promise.all([loadDashboard(), loadPerformances(), loadRanking()]);
}

function openEmployeeEditor(record = null) {
  openModal({
    title: record ? "编辑员工" : "新增员工",
    fields: [
      {
        name: "name",
        label: "员工姓名",
        type: "text",
        value: record?.name || "",
        required: true,
      },
    ],
    onSubmit: async (values) => {
      if (!values.name) {
        throw new Error("员工姓名不能为空");
      }

      if (record) {
        await apiRequest(`/api/employees/${record.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: values.name }),
        });
      } else {
        await apiRequest("/api/employees", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: values.name }),
        });
      }

      await loadEmployees(employeeSearch.value || "");
      await loadPerformances();
    },
  });
}

function openPerformanceEditor(record = null) {
  if (!state.employees.length) {
    alert("请先新增员工");
    return;
  }

  const employeeOptions = state.employees.map((item) => ({ value: String(item.id), label: item.name }));

  openModal({
    title: record ? "编辑业绩" : "新增业绩",
    fields: [
      {
        name: "employee_id",
        label: "员工",
        type: "select",
        value: String(record?.employee_id || state.employees[0].id),
        options: employeeOptions,
        required: true,
      },
      {
        name: "report_date",
        label: "统计日期",
        type: "date",
        value: record?.report_date || state.currentDate,
        required: true,
      },
      {
        name: "deal_count",
        label: "成交量",
        type: "number",
        min: 0,
        value: record?.deal_count ?? 0,
        required: true,
      },
      {
        name: "high_intent_count",
        label: "高意向客户数",
        type: "number",
        min: 0,
        value: record?.high_intent_count ?? 0,
        required: true,
      },
      {
        name: "private_domain_new",
        label: "私域新增数",
        type: "number",
        min: 0,
        value: record?.private_domain_new ?? 0,
        required: true,
      },
      {
        name: "confidence",
        label: "置信度（0-1）",
        type: "number",
        min: 0,
        max: 1,
        step: 0.01,
        value: record?.confidence ?? 1,
        required: true,
      },
    ],
    onSubmit: async (values) => {
      const payload = {
        employee_id: Number(values.employee_id),
        report_date: values.report_date,
        deal_count: Number(values.deal_count),
        high_intent_count: Number(values.high_intent_count),
        private_domain_new: Number(values.private_domain_new),
        confidence: Number(values.confidence),
      };

      if (record) {
        await apiRequest(`/api/performances/${record.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        await apiRequest("/api/performances", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      await refreshMainViews();
    },
  });
}

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    switchView(item.dataset.view);
  });
});

globalDate.addEventListener("change", async () => {
  state.currentDate = globalDate.value || todayISO();
  ocrDate.value = state.currentDate;
  rankingDate.value = state.currentDate;
  perfDateFilter.value = state.currentDate;
  await refreshMainViews();
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = photoInput.files?.[0];
  if (!file) {
    showMessage("请先选择照片", true);
    return;
  }
  if (file.size > 4 * 1000 * 1000) {
    showMessage("图片过大，请压缩到 4MB 以内", true);
    return;
  }

  showMessage("正在识别并入库...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const data = await apiRequest(`/api/upload?report_date=${encodeURIComponent(ocrDate.value || state.currentDate)}`, {
      method: "POST",
      body: formData,
    });

    renderParsed(data.parsed_records || []);
    renderRanking(data.ranking || []);
    renderPosters(data.posters || []);
    await loadEmployees();
    await loadDashboard();
    await loadPerformances();
    showMessage("上传识别成功");
  } catch (error) {
    showMessage(error.message, true);
  }
});

submitFixBtn.addEventListener("click", async () => {
  const records = collectParsedRows();
  if (!records.length) {
    showMessage("暂无可提交数据", true);
    return;
  }

  try {
    const data = await apiRequest("/api/manual-submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        report_date: ocrDate.value || state.currentDate,
        records,
      }),
    });

    renderRanking(data.ranking || []);
    renderPosters(data.posters || []);
    await loadEmployees();
    await loadDashboard();
    await loadPerformances();
    showMessage("修正提交成功");
  } catch (error) {
    showMessage(error.message, true);
  }
});

employeeSearchBtn.addEventListener("click", async () => {
  await loadEmployees(employeeSearch.value || "");
});

addEmployeeBtn.addEventListener("click", () => {
  openEmployeeEditor(null);
});

employeeBody.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const action = target.dataset.action;
  const id = Number(target.dataset.id || 0);
  if (!action || !id) {
    return;
  }

  const employee = state.employees.find((item) => item.id === id);
  if (!employee) {
    return;
  }

  if (action === "edit-employee") {
    openEmployeeEditor(employee);
    return;
  }

  if (action === "delete-employee") {
    if (!confirm(`确定删除员工「${employee.name}」吗？`)) {
      return;
    }

    try {
      await apiRequest(`/api/employees/${id}`, { method: "DELETE" });
      await loadEmployees(employeeSearch.value || "");
      await loadPerformances();
    } catch (error) {
      alert(error.message);
    }
  }
});

perfFilterBtn.addEventListener("click", async () => {
  await loadPerformances();
});

addPerfBtn.addEventListener("click", () => {
  openPerformanceEditor(null);
});

performanceBody.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const action = target.dataset.action;
  const id = Number(target.dataset.id || 0);
  if (!action || !id) {
    return;
  }

  const performance = state.performances.find((item) => item.id === id);
  if (!performance) {
    return;
  }

  if (action === "edit-performance") {
    openPerformanceEditor(performance);
    return;
  }

  if (action === "delete-performance") {
    if (!confirm(`确定删除业绩记录 #${id} 吗？`)) {
      return;
    }

    try {
      await apiRequest(`/api/performances/${id}`, { method: "DELETE" });
      await refreshMainViews();
    } catch (error) {
      alert(error.message);
    }
  }
});

refreshRankingBtn.addEventListener("click", async () => {
  await loadRanking();
});

modalCancel.addEventListener("click", () => {
  closeModal();
});

modalConfirm.addEventListener("click", async () => {
  if (!modalSubmit) {
    return;
  }

  try {
    await modalSubmit(getModalValues());
    closeModal();
  } catch (error) {
    alert(error.message);
  }
});

modal.addEventListener("click", (event) => {
  if (event.target === modal) {
    closeModal();
  }
});

(async function init() {
  state.currentDate = todayISO();
  globalDate.value = state.currentDate;
  ocrDate.value = state.currentDate;
  rankingDate.value = state.currentDate;
  perfDateFilter.value = state.currentDate;

  try {
    await loadEmployees();
    await refreshMainViews();
  } catch (error) {
    alert(error.message);
  }
})();
