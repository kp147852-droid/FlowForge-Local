const rulesEl = document.getElementById("rules");
const jobsEl = document.getElementById("jobs");
const formEl = document.getElementById("rule-form");
const actionEl = document.getElementById("action-select");

const targetWrap = document.getElementById("target-wrap");
const maxLinesWrap = document.getElementById("max-lines-wrap");
const prefixWrap = document.getElementById("prefix-wrap");
const suffixWrap = document.getElementById("suffix-wrap");

function updateActionFields() {
  const action = actionEl.value;
  targetWrap.classList.toggle("hidden", !["copy_to_folder", "move_to_folder"].includes(action));
  maxLinesWrap.classList.toggle("hidden", action !== "summarize_text_file");
  prefixWrap.classList.toggle("hidden", action !== "rename_with_timestamp");
  suffixWrap.classList.toggle("hidden", action !== "rename_with_timestamp");
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || `Request failed: ${res.status}`);
  }
  return res.json();
}

function renderRules(rules) {
  rulesEl.innerHTML = "";
  if (!rules.length) {
    rulesEl.textContent = "No rules yet.";
    return;
  }

  for (const rule of rules) {
    const div = document.createElement("div");
    div.className = "item";

    const manualInputId = `manual-${rule.id}`;
    div.innerHTML = `
      <strong>${rule.name}</strong>
      <div class="meta">${rule.source_dir} | pattern: ${rule.pattern} | action: ${rule.action}</div>
      <div class="meta">enabled: ${rule.enabled ? "yes" : "no"}</div>
      <div class="row">
        <button class="secondary" data-toggle="${rule.id}" data-enabled="${rule.enabled}">${rule.enabled ? "Disable" : "Enable"}</button>
      </div>
      <div class="row">
        <input id="${manualInputId}" placeholder="/absolute/path/to/file.txt" />
        <button data-run="${rule.id}" data-input-id="${manualInputId}">Run on file path</button>
      </div>
    `;

    rulesEl.appendChild(div);
  }

  rulesEl.querySelectorAll("button[data-toggle]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.toggle);
      const enabled = btn.dataset.enabled !== "true";
      await api(`/api/rules/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      });
      await loadRules();
    });
  });

  rulesEl.querySelectorAll("button[data-run]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.run);
      const input = document.getElementById(btn.dataset.inputId);
      const filePath = input.value.trim();
      if (!filePath) {
        alert("Enter a file path");
        return;
      }
      const query = new URLSearchParams({ file_path: filePath });
      await api(`/api/rules/${id}/run?${query.toString()}`, { method: "POST" });
      await loadJobs();
    });
  });
}

function renderJobs(jobs) {
  jobsEl.innerHTML = "";
  if (!jobs.length) {
    jobsEl.textContent = "No jobs yet.";
    return;
  }

  for (const job of jobs) {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `
      <strong>#${job.id} ${job.status}</strong>
      <div class="meta">rule: ${job.rule_id} | file: ${job.file_path}</div>
      <div class="meta">created: ${job.created_at}</div>
      <pre>${job.output || job.error || ""}</pre>
    `;
    jobsEl.appendChild(div);
  }
}

async function loadRules() {
  const rules = await api("/api/rules");
  renderRules(rules);
}

async function loadJobs() {
  const jobs = await api("/api/jobs?limit=30");
  renderJobs(jobs);
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(formEl);
  const action = formData.get("action");

  const action_config = {};
  if (action === "copy_to_folder" || action === "move_to_folder") {
    action_config.target_dir = String(formData.get("target_dir") || "").trim();
  }
  if (action === "summarize_text_file") {
    action_config.max_lines = Number(formData.get("max_lines") || 8);
  }
  if (action === "rename_with_timestamp") {
    action_config.prefix = String(formData.get("prefix") || "").trim();
    action_config.suffix = String(formData.get("suffix") || "").trim();
  }

  await api("/api/rules", {
    method: "POST",
    body: JSON.stringify({
      name: String(formData.get("name") || ""),
      source_dir: String(formData.get("source_dir") || ""),
      pattern: String(formData.get("pattern") || "*"),
      action,
      action_config,
      enabled: true,
    }),
  });

  formEl.reset();
  updateActionFields();
  await loadRules();
});

document.getElementById("refresh-jobs").addEventListener("click", loadJobs);
actionEl.addEventListener("change", updateActionFields);

updateActionFields();
loadRules().then(loadJobs).catch((err) => {
  console.error(err);
  alert(err.message);
});
