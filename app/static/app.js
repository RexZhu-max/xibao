const uploadForm = document.getElementById("uploadForm");
const reportDateInput = document.getElementById("reportDate");
const photoInput = document.getElementById("photoInput");
const uploadMsg = document.getElementById("uploadMsg");
const parsedBody = document.getElementById("parsedBody");
const rankingBody = document.getElementById("rankingBody");
const posterGrid = document.getElementById("posterGrid");
const submitFixBtn = document.getElementById("submitFixBtn");
const MAX_UPLOAD_BYTES = 4 * 1000 * 1000;

let currentReportDate = "";

function todayISO() {
  const now = new Date();
  return now.toISOString().slice(0, 10);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function showMessage(text, isError = false) {
  uploadMsg.textContent = text;
  uploadMsg.className = `msg ${isError ? "err" : "ok"}`;
}

function renderParsed(records = []) {
  if (!records.length) {
    parsedBody.innerHTML = '<tr><td colspan="5" class="empty">暂无数据</td></tr>';
    return;
  }

  const rows = records
    .map((item) => {
      return `<tr>
        <td><input data-key="employee_name" value="${escapeHtml(item.employee_name)}" /></td>
        <td><input data-key="deal_count" type="number" min="0" value="${Number(item.deal_count || 0)}" /></td>
        <td><input data-key="high_intent_count" type="number" min="0" value="${Number(item.high_intent_count || 0)}" /></td>
        <td><input data-key="private_domain_new" type="number" min="0" value="${Number(item.private_domain_new || 0)}" /></td>
        <td><input data-key="confidence" type="number" min="0" max="1" step="0.01" value="${Number(item.confidence || 0).toFixed(2)}" /></td>
      </tr>`;
    })
    .join("");

  parsedBody.innerHTML = rows;
}

function renderRanking(ranking = []) {
  if (!ranking.length) {
    rankingBody.innerHTML = '<tr><td colspan="5" class="empty">暂无排名</td></tr>';
    return;
  }

  rankingBody.innerHTML = ranking
    .map(
      (row) => `<tr>
        <td>${row.rank}</td>
        <td>${escapeHtml(row.employee_name)}</td>
        <td>${row.deal_count}</td>
        <td>${row.high_intent_count}</td>
        <td>${row.private_domain_new}</td>
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
      (poster) => `<article class="poster">
        <img src="${poster.url}" alt="${escapeHtml(poster.employee_name)} 喜报" />
        <div class="info">
          <strong>TOP ${poster.rank} · ${escapeHtml(poster.employee_name)}</strong><br />
          <a href="${poster.url}" target="_blank" rel="noreferrer">打开原图</a>
        </div>
      </article>`
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

    const obj = {};
    inputs.forEach((input) => {
      obj[input.dataset.key] = input.value;
    });

    const employeeName = (obj.employee_name || "").trim();
    if (!employeeName) {
      return;
    }

    records.push({
      employee_name: employeeName,
      deal_count: Number(obj.deal_count || 0),
      high_intent_count: Number(obj.high_intent_count || 0),
      private_domain_new: Number(obj.private_domain_new || 0),
      confidence: Number(obj.confidence || 1),
    });
  });

  return records;
}

async function fetchRankingByDate(reportDate) {
  const targetDate = reportDate || todayISO();
  const response = await fetch(`/api/ranking?report_date=${encodeURIComponent(targetDate)}`);
  if (!response.ok) {
    return;
  }
  const data = await response.json();
  currentReportDate = data.report_date || targetDate;
  renderRanking(data.ranking || []);
  renderPosters(data.posters || []);
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = photoInput.files?.[0];
  if (!file) {
    showMessage("请先选择照片", true);
    return;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    showMessage("图片过大，请压缩到 4MB 以内后再上传", true);
    return;
  }

  const reportDate = reportDateInput.value || todayISO();
  currentReportDate = reportDate;

  showMessage("正在识别中，请稍候...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`/api/upload?report_date=${encodeURIComponent(reportDate)}`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "上传失败");
    }

    currentReportDate = data.report_date || reportDate;
    renderParsed(data.parsed_records || []);
    renderRanking(data.ranking || []);
    renderPosters(data.posters || []);
    showMessage(`识别并提交成功：${currentReportDate}`);
  } catch (error) {
    showMessage(error.message || "上传失败", true);
  }
});

submitFixBtn.addEventListener("click", async () => {
  const records = collectParsedRows();
  if (!records.length) {
    showMessage("没有可提交的数据", true);
    return;
  }

  const payload = {
    report_date: currentReportDate || reportDateInput.value || todayISO(),
    records,
  };

  showMessage("正在提交修正数据...");
  try {
    const response = await fetch("/api/manual-submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "提交失败");
    }

    renderRanking(data.ranking || []);
    renderPosters(data.posters || []);
    showMessage(`修正成功：${payload.report_date}`);
  } catch (error) {
    showMessage(error.message || "提交失败", true);
  }
});

(function init() {
  const today = todayISO();
  reportDateInput.value = today;
  currentReportDate = today;
  fetchRankingByDate(today);
})();
