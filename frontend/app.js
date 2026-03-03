const rulesEl = document.getElementById("rules");
const jobsEl = document.getElementById("jobs");
const metricsEl = document.getElementById("metrics");
const formEl = document.getElementById("rule-form");
const actionEl = document.getElementById("action-select");
const templateEl = document.getElementById("template-select");

let templates = [];

const wraps = {
  targetWrap: document.getElementById("target-wrap"),
  maxLinesWrap: document.getElementById("max-lines-wrap"),
  prefixWrap: document.getElementById("prefix-wrap"),
  suffixWrap: document.getElementById("suffix-wrap"),
  pdfNameWrap: document.getElementById("pdf-name-wrap"),
  imgFormatWrap: document.getElementById("img-format-wrap"),
  imgQualityWrap: document.getElementById("img-quality-wrap"),
  webhookWrap: document.getElementById("webhook-wrap"),
  emailWrap: document.getElementById("email-wrap"),
  draftDirWrap: document.getElementById("draft-dir-wrap"),
};

function parseCsv(value) {
  return String(value || "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

function updateActionFields() {
  const action = actionEl.value;
  wraps.targetWrap.classList.toggle("hidden", !["copy_to_folder", "move_to_folder"].includes(action));
  wraps.maxLinesWrap.classList.toggle("hidden", action !== "summarize_text_file");
  wraps.prefixWrap.classList.toggle("hidden", action !== "rename_with_timestamp");
  wraps.suffixWrap.classList.toggle("hidden", action !== "rename_with_timestamp");
  wraps.pdfNameWrap.classList.toggle("hidden", action !== "merge_pdfs_in_folder");
  wraps.imgFormatWrap.classList.toggle("hidden", action !== "convert_image");
  wraps.imgQualityWrap.classList.toggle("hidden", action !== "compress_image");
  wraps.webhookWrap.classList.toggle("hidden", action !== "notify_webhook");
  const emailDraftAction = action === "create_email_draft";
  wraps.emailWrap.classList.toggle("hidden", !emailDraftAction);
  wraps.draftDirWrap.classList.toggle("hidden", !emailDraftAction);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const asJson = await res.json();
      detail = asJson.detail || JSON.stringify(asJson);
    } catch {
      detail = await res.text();
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : {};
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
    const dryRunId = `dry-run-${rule.id}`;

    div.innerHTML = `
      <strong>${rule.name}</strong>
      <div class="meta">${rule.source_dir} | pattern: ${rule.pattern} | action: ${rule.action}</div>
      <div class="meta">enabled: ${rule.enabled ? "yes" : "no"} | schedule: ${rule.schedule?.enabled ? `every ${rule.schedule.interval_minutes || 60}m` : "off"}</div>
      <div class="meta">conditions: ${JSON.stringify(rule.conditions || {})}</div>
      <div class="row">
        <button class="secondary" data-toggle="${rule.id}" data-enabled="${rule.enabled}">${rule.enabled ? "Disable" : "Enable"}</button>
      </div>
      <div class="row">
        <input id="${manualInputId}" placeholder="/absolute/path/to/file.txt" />
        <label><input id="${dryRunId}" type="checkbox" /> dry run</label>
        <button data-run="${rule.id}" data-input-id="${manualInputId}" data-dry-id="${dryRunId}">Run on file path</button>
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
      const dry = document.getElementById(btn.dataset.dryId);
      const filePath = input.value.trim();
      if (!filePath) {
        alert("Enter a file path");
        return;
      }
      await api(`/api/rules/${id}/run`, {
        method: "POST",
        body: JSON.stringify({ file_path: filePath, dry_run: !!dry.checked }),
      });
      await loadJobs();
      await loadMetrics();
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
      <strong>#${job.id} ${job.status} ${job.dry_run ? "(dry-run)" : ""}</strong>
      <div class="meta">rule: ${job.rule_id} | attempts: ${job.attempt_count} | file: ${job.file_path}</div>
      <div class="meta">created: ${job.created_at}</div>
      <pre>${job.output || job.error || ""}</pre>
      <div class="row">
        <button class="secondary" data-logs="${job.id}">Logs</button>
        <button data-undo="${job.id}">Undo</button>
      </div>
      <pre id="logs-${job.id}"></pre>
    `;
    jobsEl.appendChild(div);
  }

  jobsEl.querySelectorAll("button[data-logs]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.logs);
      const logs = await api(`/api/jobs/${id}/logs`);
      const output = logs.map((l) => `[${l.level}] ${l.created_at} - ${l.message}`).join("\n");
      document.getElementById(`logs-${id}`).textContent = output || "No logs";
    });
  });

  jobsEl.querySelectorAll("button[data-undo]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.undo);
      try {
        const result = await api(`/api/jobs/${id}/undo`, { method: "POST" });
        alert(result.message);
      } catch (err) {
        alert(err.message);
      }
      await loadJobs();
    });
  });
}

function renderMetrics(metrics) {
  metricsEl.innerHTML = `
    <div class="metric-grid">
      <div class="metric"><strong>Total</strong><span>${metrics.total || 0}</span></div>
      <div class="metric"><strong>Success</strong><span>${metrics.success || 0}</span></div>
      <div class="metric"><strong>Failed</strong><span>${metrics.failed || 0}</span></div>
      <div class="metric"><strong>Dry Runs</strong><span>${metrics.dry_runs || 0}</span></div>
    </div>
    <pre>${JSON.stringify(metrics.by_rule || [], null, 2)}</pre>
  `;
}

async function loadTemplates() {
  templates = await api("/api/templates");
  templateEl.innerHTML = '<option value="">Select template</option>';
  templates.forEach((t, idx) => {
    const option = document.createElement("option");
    option.value = String(idx);
    option.textContent = t.name;
    templateEl.appendChild(option);
  });
}

function applyTemplate(template) {
  const set = (name, value) => {
    const el = formEl.elements[name];
    if (!el) return;
    if (el.type === "checkbox") {
      el.checked = !!value;
    } else {
      el.value = value ?? "";
    }
  };

  set("name", template.name);
  set("source_dir", template.source_dir);
  set("pattern", template.pattern);
  set("action", template.action);
  updateActionFields();

  const a = template.action_config || {};
  set("target_dir", a.target_dir || "");
  set("max_lines", a.max_lines || 8);
  set("prefix", a.prefix || "");
  set("suffix", a.suffix || "");
  set("output_name", a.output_name || "merged.pdf");
  set("format", a.format || "png");
  set("quality", a.quality || 70);
  set("webhook_url", a.webhook_url || "");
  set("to_email", a.to_email || "");
  set("drafts_dir", a.drafts_dir || "");
  set("max_retries", a.max_retries || 1);
  set("backoff_seconds", a.backoff_seconds || 1);
  set("quarantine_dir", a.quarantine_dir || "");

  const c = template.conditions || {};
  set("min_size_kb", c.min_size_kb || 0);
  set("max_size_kb", c.max_size_kb || 0);
  set("filename_contains", c.filename_contains || "");
  set("filename_excludes", c.filename_excludes || "");
  set("allowed_extensions", (c.allowed_extensions || []).join(","));
  set("allowed_weekdays", (c.allowed_weekdays || []).join(","));
  set("allowed_hour_start", c.allowed_hour_start ?? 0);
  set("allowed_hour_end", c.allowed_hour_end ?? 23);
  set("dedupe", c.dedupe !== false);

  const s = template.schedule || {};
  set("schedule_enabled", !!s.enabled);
  set("interval_minutes", s.interval_minutes || 60);
  set("weekdays_only", !!s.weekdays_only);
  set("schedule_dry_run", !!s.dry_run);
  set("downstream_rule_ids", (s.downstream_rule_ids || []).join(","));

  const i = template.integrations || {};
  set("integration_webhook", i.notify_webhook || "");
  set("append_csv", i.append_csv || "");
}

async function loadRules() {
  const rules = await api("/api/rules");
  renderRules(rules);
}

async function loadJobs() {
  const jobs = await api("/api/jobs?limit=30");
  renderJobs(jobs);
}

async function loadMetrics() {
  const metrics = await api("/api/metrics");
  renderMetrics(metrics);
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(formEl);
  const action = String(formData.get("action") || "");

  const action_config = {
    max_retries: Number(formData.get("max_retries") || 1),
    backoff_seconds: Number(formData.get("backoff_seconds") || 1),
    quarantine_dir: String(formData.get("quarantine_dir") || "").trim(),
  };

  if (["copy_to_folder", "move_to_folder"].includes(action)) {
    action_config.target_dir = String(formData.get("target_dir") || "").trim();
  }
  if (action === "summarize_text_file") {
    action_config.max_lines = Number(formData.get("max_lines") || 8);
  }
  if (action === "rename_with_timestamp") {
    action_config.prefix = String(formData.get("prefix") || "").trim();
    action_config.suffix = String(formData.get("suffix") || "").trim();
  }
  if (action === "merge_pdfs_in_folder") {
    action_config.output_name = String(formData.get("output_name") || "merged.pdf").trim();
  }
  if (action === "convert_image") {
    action_config.format = String(formData.get("format") || "png").trim();
  }
  if (action === "compress_image") {
    action_config.quality = Number(formData.get("quality") || 70);
  }
  if (action === "notify_webhook") {
    action_config.webhook_url = String(formData.get("webhook_url") || "").trim();
  }
  if (action === "create_email_draft") {
    action_config.to_email = String(formData.get("to_email") || "").trim();
    action_config.drafts_dir = String(formData.get("drafts_dir") || "").trim();
  }

  const conditions = {
    min_size_kb: Number(formData.get("min_size_kb") || 0),
    max_size_kb: Number(formData.get("max_size_kb") || 0),
    filename_contains: String(formData.get("filename_contains") || "").trim(),
    filename_excludes: String(formData.get("filename_excludes") || "").trim(),
    allowed_extensions: parseCsv(formData.get("allowed_extensions") || ""),
    allowed_weekdays: parseCsv(formData.get("allowed_weekdays") || ""),
    allowed_hour_start: Number(formData.get("allowed_hour_start") || 0),
    allowed_hour_end: Number(formData.get("allowed_hour_end") || 23),
    dedupe: formData.get("dedupe") === "on",
  };

  const schedule = {
    enabled: formData.get("schedule_enabled") === "on",
    interval_minutes: Number(formData.get("interval_minutes") || 60),
    weekdays_only: formData.get("weekdays_only") === "on",
    dry_run: formData.get("schedule_dry_run") === "on",
    downstream_rule_ids: parseCsv(formData.get("downstream_rule_ids") || "").map(Number).filter((v) => !Number.isNaN(v)),
  };

  const integrations = {
    notify_webhook: String(formData.get("integration_webhook") || "").trim(),
    append_csv: String(formData.get("append_csv") || "").trim(),
  };

  await api("/api/rules", {
    method: "POST",
    body: JSON.stringify({
      name: String(formData.get("name") || ""),
      source_dir: String(formData.get("source_dir") || ""),
      pattern: String(formData.get("pattern") || "*"),
      action,
      action_config,
      conditions,
      schedule,
      integrations,
      enabled: true,
    }),
  });

  formEl.reset();
  updateActionFields();
  await loadRules();
  await loadMetrics();
});

document.getElementById("refresh-jobs").addEventListener("click", loadJobs);
document.getElementById("refresh-metrics").addEventListener("click", loadMetrics);
actionEl.addEventListener("change", updateActionFields);
document.getElementById("apply-template").addEventListener("click", () => {
  const idx = Number(templateEl.value);
  if (Number.isNaN(idx) || !templates[idx]) {
    alert("Select a template first");
    return;
  }
  applyTemplate(templates[idx]);
});

document.getElementById("export-rules").addEventListener("click", async () => {
  const payload = await api("/api/rules/export");
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "flowforge-rules.json";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("import-file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const text = await file.text();
  const data = JSON.parse(text);
  await api("/api/rules/import", {
    method: "POST",
    body: JSON.stringify({ rules: data.rules || [] }),
  });
  await loadRules();
});

updateActionFields();
Promise.all([loadTemplates(), loadRules(), loadJobs(), loadMetrics()]).catch((err) => {
  console.error(err);
  alert(err.message);
});
