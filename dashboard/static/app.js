const state = {
  config: null,
  assets: { ad_accounts: [], pages: [], warnings: [] },
  currentClient: null,
  lastReportPath: "",
  pipelineTimer: null,
};

const $ = (id) => document.getElementById(id);

// UI Navigation
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', (e) => {
    if (btn.disabled) return;
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active'));
    
    btn.classList.add('active');
    $(btn.dataset.target).classList.add('active');
  });
});

function showToast(message, type = 'info') {
  const el = $('status');
  el.textContent = message;
  el.className = `toast-notification ${type}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 5000);
}

// Simulated Pipeline Animation
function startPipelineVisuals() {
  $('pipelineProgress').classList.remove('hidden');
  $('pipelineLogs').classList.remove('hidden');
  $('pipelineLogs').textContent = "Initializing pipeline...\n";
  $('runPipelineBtn').disabled = true;
  $('navResultsBtn').disabled = true;
  
  // Reset stepper
  document.querySelectorAll('.step').forEach(s => s.className = 'step');
  document.querySelectorAll('.step-line').forEach(l => l.classList.remove('active'));
  $('pipelineBar').style.width = '0%';
  
  const steps = [
    { text: "Connecting APIs...", log: "Checking credentials and connecting to Meta Graph API...", step: 1 },
    { text: "Fetching Paid Data...", log: "Extracting campaign metrics, spend, and conversions...", step: 2 },
    { text: "Fetching Organic...", log: "Extracting posts, reels, and engagement metrics...", step: 3 },
    { text: "Generating Reports...", log: "Compiling data and rendering markdown...", step: 4 },
    { text: "AI Synthesis...", log: "Sending data to OpenAI for strategic synthesis. This takes a moment...", step: 5 },
    { text: "Generating PPTX...", log: "Structuring output into slides and rendering PowerPoint...", step: 6 },
    { text: "Pipeline Completed Successfully!", log: "Done", step: 7 }
  ];

  state.pipelineTimer = setInterval(async () => {
    try {
      const clientId = $("clientSelect").value;
      const period = getPeriodLabel();
      const status = await api(`/api/status?client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`);
      
      if (status.step > 0) {
        // Animate progress bar based on step (each step is ~14%)
        const progress = Math.min(95, (status.step / 7) * 100);
        $('pipelineBar').style.width = `${progress}%`;
        
        $('pipelineStatusText').textContent = status.message || steps[status.step - 1]?.text || "Processing...";
        
        // Update stepper visually
        for (let i = 1; i <= 7; i++) {
          const stepEl = $(`step-${i}`);
          if (!stepEl) continue;
          
          if (i < status.step) {
            stepEl.classList.add('completed');
            stepEl.classList.remove('active');
          } else if (i === status.step) {
            stepEl.classList.add('active');
            stepEl.classList.remove('completed');
          }
        }
        
        // Update lines
        const lines = document.querySelectorAll('.step-line');
        for (let i = 0; i < lines.length; i++) {
          if (i < status.step - 1) {
            lines[i].classList.add('active');
          }
        }
      }
    } catch (e) {
      console.error("Status check failed", e);
    }
  }, 1000);
}

function finishPipelineVisuals(ok, logs) {
  clearInterval(state.pipelineTimer);
  $('runPipelineBtn').disabled = false;
  $('pipelineLogs').textContent += `\n${logs}\n`;
  
  if (ok) {
    $('pipelineBar').style.width = '100%';
    $('pipelineStatusText').textContent = "Pipeline Completed Successfully!";
    document.querySelectorAll('.step').forEach(s => s.classList.add('completed'));
    document.querySelectorAll('.step-line').forEach(l => l.classList.add('active'));
    
    $('navResultsBtn').disabled = false;
    setTimeout(() => {
      document.querySelector('[data-target="results-view"]').click();
    }, 1500);
  } else {
    $('pipelineStatusText').textContent = "Pipeline Failed!";
    $('pipelineBar').style.background = 'var(--danger)';
  }
}

// API Calls
async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function selectedClient() {
  const clientId = $("clientSelect").value;
  return state.config.clients.find((client) => client.id === clientId) || state.config.clients[0];
}

function renderClients() {
  const select = $("clientSelect");
  select.innerHTML = state.config.clients
    .map((client) => `<option value="${client.id}">${escapeHtml(client.name || client.id)}</option>`)
    .join("");
  state.currentClient = selectedClient();
  
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const year = now.getFullYear();
  const month = pad(now.getMonth() + 1);
  const lastDate = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  
  $("sinceInput").value = `${year}-${month}-01`;
  $("untilInput").value = `${year}-${month}-${pad(lastDate)}`;
  
  if (state.currentClient) {
    $("masterTokenInput").value = state.currentClient.meta?.access_token || state.currentClient.organic?.access_token || "";
    $("aiTokenInput").value = state.currentClient.ai_provider?.api_key || "";
  }
  
  checkAllTokensOnLoad();
  
  updatePipelineHeader();
}

function updatePipelineHeader() {
  const client = selectedClient();
  if (client) {
    $('pipelineClientName').textContent = client.name || client.id;
  }
}

function renderAssets() {
  const client = selectedClient();
  const configuredIds = new Set(
    (client.meta.accounts || []).map((account) => account.ad_account_id || account.id || account.ad_account_id_env)
  );
  const list = $("adAccountsList");
  if (!state.assets.ad_accounts.length) {
    list.innerHTML = `<p class="muted" style="padding:12px;">No ad accounts loaded yet.</p>`;
  } else {
    list.innerHTML = state.assets.ad_accounts
      .map((account) => {
        const checked = configuredIds.has(account.id) ? "checked" : "";
        const details = [account.id, account.currency, account.timezone].filter(Boolean).join(" • ");
        return `
          <label class="asset-item">
            <input type="checkbox" name="adAccount" value="${escapeAttr(account.id)}" ${checked}>
            <div class="asset-details">
              <strong>${escapeHtml(account.name || account.id)}</strong>
              <small>${escapeHtml(details)}</small>
            </div>
          </label>
        `;
      })
      .join("");
  }

  const pageSelect = $("pageSelect");
  const pageId = client.organic.page_id || "";
  pageSelect.innerHTML = `<option value="">No page selected</option>` + state.assets.pages
    .map((page) => {
      const selected = page.id === pageId ? "selected" : "";
      const ig = page.instagram ? ` · IG: @${page.instagram.username || page.instagram.id}` : "";
      return `<option value="${escapeAttr(page.id)}" ${selected}>${escapeHtml(page.name + ig)}</option>`;
    })
    .join("");

  renderInstagramSelect();
  $("facebookEnabled").checked = Boolean(client.organic.facebook_enabled);
  $("instagramEnabled").checked = Boolean(client.organic.instagram_enabled);
}

function renderInstagramSelect() {
  const client = selectedClient();
  const currentIg = client.organic.instagram_account_id || "";
  const options = [];
  for (const page of state.assets.pages) {
    if (page.instagram && page.instagram.id) {
      options.push({
        id: page.instagram.id,
        label: `${page.instagram.username || page.instagram.name || page.instagram.id} (${page.name})`,
      });
    }
  }
  const deduped = [];
  const seen = new Set();
  for (const option of options) {
    if (!seen.has(option.id)) {
      deduped.push(option);
      seen.add(option.id);
    }
  }
  $("instagramSelect").innerHTML = `<option value="">Auto from selected page / none</option>` + deduped
    .map((option) => {
      const selected = option.id === currentIg ? "selected" : "";
      return `<option value="${escapeAttr(option.id)}" ${selected}>${escapeHtml(option.label)}</option>`;
    })
    .join("");
}

function renderMetrics() {
  const client = selectedClient();
  renderMetricGroup("paidMetrics", state.config.metric_options.paid, client.meta.fields || []);
  renderMetricGroup(
    "facebookMetrics",
    state.config.metric_options.facebook_organic,
    client.organic.facebook_post_insight_metrics || []
  );
  renderMetricGroup(
    "instagramMetrics",
    state.config.metric_options.instagram_organic,
    client.organic.instagram_media_insight_metrics || []
  );
}

function renderMetricGroup(id, options, selectedValues) {
  const selected = new Set(selectedValues);
  $(id).innerHTML = options
    .map((option) => {
      const checked = selected.has(option.id) ? "checked" : "";
      return `<label><input type="checkbox" value="${escapeAttr(option.id)}" ${checked}>${escapeHtml(option.label)}</label>`;
    })
    .join("");
}

function selectedValues(containerId) {
  return Array.from(document.querySelectorAll(`#${containerId} input:checked`)).map((input) => input.value);
}

function selectedAdAccounts() {
  const checked = Array.from(document.querySelectorAll('input[name="adAccount"]:checked')).map((input) => input.value);
  return state.assets.ad_accounts
    .filter((account) => checked.includes(account.id))
    .map((account) => ({ id: account.id, name: account.name || account.id }));
}

function selectedPageName() {
  const pageId = $("pageSelect").value;
  const page = state.assets.pages.find((item) => item.id === pageId);
  return page ? page.name || page.id : "";
}

function payloadFromForm() {
  const client = selectedClient();
  return {
    client_id: client.id,
    client_name: client.name,
    timezone: client.timezone,
    currency: client.currency,
    ads_token: $("masterTokenInput").value.trim(),
    organic_token: $("masterTokenInput").value.trim(),
    ai_token: $("aiTokenInput").value.trim(),
    meta_enabled: true,
    ad_accounts: selectedAdAccounts(),
    paid_metrics: selectedValues("paidMetrics"),
    organic_enabled: true,
    facebook_enabled: $("facebookEnabled").checked,
    instagram_enabled: $("instagramEnabled").checked,
    page_id: $("pageSelect").value,
    page_name: selectedPageName(),
    instagram_account_id: $("instagramSelect").value,
    max_facebook_posts: 100,
    max_instagram_media: 100,
    facebook_organic_metrics: selectedValues("facebookMetrics"),
    instagram_organic_metrics: selectedValues("instagramMetrics"),
  };
}

async function loadConfig() {
  state.config = await api("/api/config");
  renderClients();
  renderMetrics();
}

async function loadAssets() {
  showToast("Fetching Meta Assets...");
  const clientId = $("clientSelect")?.value || "";
  state.assets = await api(`/api/meta/assets?client=${encodeURIComponent(clientId)}`);
  renderAssets();
  const warnings = state.assets.warnings || [];
  if (warnings.length) {
    showToast(warnings.join(" | "), "error");
  } else {
    showToast("Assets synced successfully", "success");
  }
}

async function saveConfig() {
  try {
    const payload = payloadFromForm();
    const result = await api("/api/config", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.config = result.config;
    renderMetrics();
    showToast("Configuration Saved", "success");
  } catch(e) {
    showToast(e.message, "error");
  }
}

async function validateToken(type) {
  const token = $(`${type}TokenInput`).value.trim();
  const statusEl = $(`${type}TokenStatus`);
  
  if (!token) {
    statusEl.innerHTML = `<span class="text-muted">Using default from .env</span>`;
    return;
  }
  
  statusEl.innerHTML = `<span class="text-warning">Validating...</span>`;
  
  try {
    const payload = {};
    if (type === "master") {
      payload.ads_token = token;
      payload.organic_token = token;
    } else {
      payload[`${type}_token`] = token;
    }
    
    const result = await api("/api/tokens/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    
    // For master token, just check if ads (or organic) is valid since it's the same token
    const tokenResult = type === "master" ? result.ads : result[type];
    
    if (tokenResult.valid) {
      let badges = `<span class="text-success">✅ Valid (${escapeHtml(tokenResult.name)})</span>`;
      const perms = tokenResult.permissions || [];
      
      if (perms.includes('page_token')) {
        badges += ` <span class="badge badge-success">Page Token</span>`;
      } else {
        if (perms.includes('ads_read')) {
          badges += ` <span class="badge badge-success">Ads Access</span>`;
        }
        if (perms.includes('pages_read_engagement') || perms.includes('pages_show_list')) {
          badges += ` <span class="badge badge-success">Pages Access</span>`;
        }
        if (perms.includes('instagram_basic')) {
          badges += ` <span class="badge badge-pink">IG Access</span>`;
        }
      }
      statusEl.innerHTML = badges;
      
      // Auto-save the new token and reload assets
      await saveConfig();
      await loadAssets();
      showToast("Token validated & assets refreshed!", "success");
    } else {
      statusEl.innerHTML = `<span class="text-danger">❌ Invalid: ${escapeHtml(tokenResult.message)}</span>`;
    }
  } catch (error) {
    statusEl.innerHTML = `<span class="text-danger">❌ Error: ${escapeHtml(error.message)}</span>`;
  }
}

async function checkAllTokensOnLoad() {
  validateToken("master");
  validateAiToken();
}

async function validateAiToken() {
  const token = $("aiTokenInput").value.trim();
  const statusEl = $("aiTokenStatus");
  if (!token) {
    statusEl.innerHTML = `<span class="text-muted">Using default from .env</span>`;
    return;
  }
  statusEl.innerHTML = `<span class="text-success">✅ Token Saved</span>`;
}

function getPeriodLabel() {
  const since = $("sinceInput").value;
  const until = $("untilInput").value;
  if (!since || !until) return "";
  return `${since}_to_${until}`;
}

async function runPipeline() {
  const since = $("sinceInput").value;
  const until = $("untilInput").value;
  if (!since || !until) {
    showToast("Please select Start and End dates", "error");
    return;
  }

  await saveConfig();
  
  // Switch view to pipeline execution automatically
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active'));
  $('pipeline-view').classList.add('active');
  
  startPipelineVisuals();
  
  try {
    const result = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({
        client_id: $("clientSelect").value,
        since: $("sinceInput").value,
        until: $("untilInput").value,
      }),
    });
    state.lastReportPath = result.report_path || "";
    finishPipelineVisuals(result.ok, result.output);
    
    if (result.ok) {
      await loadReport();
      await loadAiReport();
      await loadDetails();
    }
  } catch (e) {
    finishPipelineVisuals(false, e.message);
  }
}

async function loadReport() {
  const clientId = $("clientSelect").value;
  const period = getPeriodLabel();
  if (!period) return;
  const result = await api(`/api/report?client=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`);
  $("reportPreview").innerHTML = result.ok ? markdownToHtml(result.content) : `<p>${escapeHtml(result.message)}</p>`;
}

async function loadAiReport() {
  const clientId = $("clientSelect").value;
  const period = getPeriodLabel();
  if (!period) return;
  const result = await api(`/api/report?client=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}&kind=ai`);
  if (result.ok) {
    $("aiReportPreview").innerHTML = markdownToHtml(result.content);
    $("aiReportEditor").value = result.content;
    state.rawAiReport = result.content;
  } else {
    $("aiReportPreview").innerHTML = `<p>${escapeHtml(result.message)}</p>`;
    $("aiReportEditor").value = "";
    state.rawAiReport = "";
  }
}

async function exportReport(type) {
  const clientId = $("clientSelect").value;
  const period = getPeriodLabel();
  if (!period) return;

  const btnId = type === 'pptx' ? 'exportPptxBtn' : 'exportPdfBtn';
  const btn = $(btnId);
  const originalText = btn.innerHTML;
  btn.innerHTML = '⏳ Generating...';
  btn.disabled = true;

  try {
    const reportContent = $("aiReportEditor").value;
    
    // Use standard fetch to get the binary file blob
    const response = await fetch(`/api/export/${type}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId, period, report_content: reportContent }),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || `Export failed`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    
    // Extract filename from Content-Disposition header if available
    const disposition = response.headers.get("Content-Disposition");
    let filename = `${clientId}_report.${type}`;
    if (disposition && disposition.indexOf("filename=") !== -1) {
      filename = disposition.split("filename=")[1].replace(/["']/g, "");
    }
    
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    showToast(`Successfully exported ${type.toUpperCase()}`, "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

async function loadDetails() {
  const clientId = $("clientSelect").value;
  const period = getPeriodLabel();
  if (!period) return;
  const result = await api(`/api/details?client=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`);
  
  renderWarnings(result.warnings || []);
  renderContentRows(result.organic_content || []);
  renderCampaignRows(result.campaigns || []);
  renderAiStatus(result.ai_report);
}

function renderWarnings(warnings) {
  const banner = $("warningsBanner");
  const list = $("warningsList");
  if (!warnings || warnings.length === 0) {
    banner.classList.add("hidden");
    return;
  }
  banner.classList.remove("hidden");
  list.innerHTML = warnings.map(w => `<div>${escapeHtml(w)}</div>`).join("");
}

function renderAiStatus(status) {
  const el = $("aiStatus");
  if (!status || !status.path) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  
  const mode = status.mode === "openai" ? "AI Pipeline" : "Fallback Script";
  const detail = status.mode === "openai"
    ? "Successfully generated AI synthesis and PPTX slides."
    : "AI failed or is disabled. Used fallback script logic.";
  
  if(status.error) {
    el.className = "ai-banner error";
    el.innerHTML = `<strong>Failed to run AI:</strong> ${escapeHtml(status.error)}`;
  } else {
    el.className = "ai-banner success";
    el.innerHTML = `<strong>${escapeHtml(mode)}:</strong> ${escapeHtml(detail)}`;
  }
}

function renderContentRows(rows) {
  const body = $("contentRows");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7">
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        <p>No organic content found for this period.</p>
      </div>
    </td></tr>`;
    return;
  }
  body.innerHTML = rows.slice(0, 50).map((row) => {
    const url = row.permalink || "";
    const preview = row.text_preview || row.content_id || "Open content";
    const link = url
      ? `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">Preview Link</a>`
      : escapeHtml(preview.slice(0, 30));
    return `
      <tr>
        <td>${escapeHtml(titleCase(row.platform))}</td>
        <td>${escapeHtml(row.content_format || "")}</td>
        <td>${escapeHtml(row.content_topic || "")}</td>
        <td>${formatNumber(row.views)}</td>
        <td>${formatNumber(row.engagements)}</td>
        <td>${formatRate(row.engagement_rate)}</td>
        <td>${link}</td>
      </tr>
    `;
  }).join("");
}

function renderCampaignRows(rows) {
  const body = $("campaignRows");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7">
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 20V10M18 20V4M6 20v-4"></path></svg>
        <p>No active campaigns found for this period.</p>
      </div>
    </td></tr>`;
    return;
  }
  body.innerHTML = rows.slice(0, 50).map((row) => {
    const conversions = Number(row.leads || 0) + Number(row.purchases || 0);
    return `
    <tr>
      <td>${escapeHtml(row.account_name || row.account_alias || "")}</td>
      <td>${escapeHtml(row.campaign_name || "")}</td>
      <td>${escapeHtml(row.objective || "")}</td>
      <td>${formatNumber(row.spend)}</td>
      <td>${formatNumber(row.clicks)}</td>
      <td>${formatPercent(row.ctr)}</td>
      <td>${formatNumber(conversions)}</td>
    </tr>
  `}).join("");
}

function markdownToHtml(markdown) {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let table = [];
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((line) => !/^\|\s*-/.test(line));
    html.push("<table>");
    rows.forEach((row, index) => {
      const cells = row.split("|").slice(1, -1).map((cell) => cell.trim());
      const tag = index === 0 ? "th" : "td";
      html.push(`<tr>${cells.map((cell) => `<${tag}>${inlineMarkdown(cell)}</${tag}>`).join("")}</tr>`);
    });
    html.push("</table>");
    table = [];
  };

  for (const line of lines) {
    if (line.startsWith("|")) {
      table.push(line);
      continue;
    }
    flushTable();
    if (line.startsWith("# ")) html.push(`<h1>${escapeHtml(line.slice(2))}</h1>`);
    else if (line.startsWith("## ")) html.push(`<h2>${escapeHtml(line.slice(3))}</h2>`);
    else if (line.startsWith("### ")) html.push(`<h3>${escapeHtml(line.slice(4))}</h3>`);
    else if (line.startsWith("- ")) html.push(`<ul><li>${inlineMarkdown(line.slice(2))}</li></ul>`);
    else if (line.trim()) html.push(`<p>${inlineMarkdown(line)}</p>`);
  }
  flushTable();
  return html.join("").replace(/<\/ul><ul>/g, ''); // merge adjacent lists
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function formatNumber(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "0";
}

function formatPercent(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? `${number.toFixed(2)}%` : "0.00%";
}

function formatRate(value) {
  const number = Number(value || 0) * 100;
  return Number.isFinite(number) ? `${number.toFixed(2)}%` : "0.00%";
}

function titleCase(value) {
  return String(value || "").replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

async function init() {
  try {
    await loadConfig();
    $("clientSelect").addEventListener("change", () => {
      state.currentClient = selectedClient();
      renderAssets();
      renderMetrics();
      updatePipelineHeader();
      if (state.currentClient) {
        $("adsTokenInput").value = state.currentClient.meta.access_token || "";
        $("organicTokenInput").value = state.currentClient.organic.access_token || "";
        $("aiTokenInput").value = state.currentClient.ai_token || "";
        $("adsTokenStatus").innerHTML = "";
        $("organicTokenStatus").innerHTML = "";
        $("aiTokenStatus").innerHTML = "";
        checkAllTokensOnLoad();
      }
    });
    $("pageSelect").addEventListener("change", () => {
      const page = state.assets.pages.find((item) => item.id === $("pageSelect").value);
      if (page && page.instagram && page.instagram.id) {
        $("instagramSelect").value = page.instagram.id;
      }
    });
    $("refreshAssetsBtn").addEventListener("click", loadAssets);
    $("saveConfigBtn").addEventListener("click", saveConfig);
    $("runPipelineBtn").addEventListener("click", runPipeline);
    $("loadReportBtn").addEventListener("click", () => {
      loadReport();
      loadAiReport();
    });
    
    $("validateMasterTokenBtn").addEventListener("click", () => validateToken("master"));
    $("validateAiTokenBtn").addEventListener("click", () => validateAiToken());
    
    // Export and Edit Handlers
    $("exportPptxBtn").addEventListener("click", () => exportReport("pptx"));
    $("exportPdfBtn").addEventListener("click", () => exportReport("pdf"));
    $("toggleEditBtn").addEventListener("click", () => {
      const editor = $("aiReportEditor");
      const preview = $("aiReportPreview");
      if (editor.classList.contains("hidden")) {
        editor.classList.remove("hidden");
        preview.classList.add("hidden");
        $("toggleEditBtn").innerText = "View Preview";
      } else {
        editor.classList.add("hidden");
        preview.classList.remove("hidden");
        // Update preview with edited content
        preview.innerHTML = markdownToHtml(editor.value);
        $("toggleEditBtn").innerText = "Edit Markdown";
      }
    });

    // Auto load assets
    await loadAssets();
  } catch (error) {
    showToast(error.message, "error");
  }
}

init();
