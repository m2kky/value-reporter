const state = {
  config: null,
  assets: { ad_accounts: [], pages: [], warnings: [] },
  currentClient: null,
  lastReportPath: "",
  pipelineTimer: null,
  aiTemplates: [],
  selectedTemplate: "full",
  kpiTargets: [],
};

const KPI_METRIC_OPTIONS = [
  { id: "spend", label: "Spend" },
  { id: "impressions", label: "Impressions" },
  { id: "reach", label: "Reach" },
  { id: "clicks", label: "Clicks" },
  { id: "ctr", label: "CTR (%)" },
  { id: "cpc", label: "CPC" },
  { id: "cpm", label: "CPM" },
  { id: "leads", label: "Leads" },
  { id: "purchases", label: "Purchases" },
  { id: "roas", label: "ROAS" },
  { id: "frequency", label: "Frequency" },
  { id: "engagement_rate", label: "Engagement Rate (%)" },
  { id: "organic_reach", label: "Organic Reach" },
  { id: "organic_views", label: "Organic Views" },
  { id: "organic_engagements", label: "Organic Engagements" },
  { id: "comments", label: "Comments" },
  { id: "shares", label: "Shares" },
  { id: "saves", label: "Saves" },
  { id: "response_rate", label: "Response Rate (%)" },
  { id: "avg_response_time", label: "Avg Response Time (minutes)" },
  { id: "followers_growth", label: "Followers Growth" },
  { id: "post_count", label: "Post Count" },
  { id: "video_views", label: "Video Views" },
];

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

// Content Tabs Navigation
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('content-tab-btn')) {
    document.querySelectorAll('.content-tab-btn').forEach(btn => btn.classList.remove('active'));
    e.target.classList.add('active');
    renderContentRows(state.organicContent || []);
  }
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
    { text: "Connecting APIs...", step: 1 },
    { text: "Fetching Paid Data...", step: 2 },
    { text: "Fetching Organic...", step: 3 },
    { text: "Generating Reports...", step: 4 },
    { text: "Pipeline Completed!", step: 5 }
  ];
  const totalSteps = 5;

  state.pipelineTimer = setInterval(async () => {
    try {
      const clientId = $("clientSelect").value;
      const period = getPeriodLabel();
      const status = await api(`/api/status?client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`);
      
      if (status.step > 0) {
        // Animate progress bar based on step (each step is ~14%)
        const progress = Math.min(95, (status.step / totalSteps) * 100);
        $('pipelineBar').style.width = `${progress}%`;
        
        $('pipelineStatusText').textContent = status.message || steps[status.step - 1]?.text || "Processing...";
        
        // Update stepper visually
        for (let i = 1; i <= totalSteps; i++) {
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
  if ($("tiktokEnabled")) $("tiktokEnabled").checked = Boolean(client.organic.tiktok_enabled);
  if ($("tiktokTokenInput")) $("tiktokTokenInput").value = client.organic.tiktok_access_token || "";
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
    tiktok_enabled: $("tiktokEnabled").checked,
    tiktok_access_token: $("tiktokTokenInput").value.trim(),
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
  const previewEl = $("reportPreview");
  if (previewEl) {
    previewEl.innerHTML = result.ok ? markdownToHtml(result.content) : `<p>${escapeHtml(result.message)}</p>`;
  }
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
  
  // Save to global state for dynamic re-rendering
  state.currentKpis = result.kpis || {};
  state.organicSummary = result.organic_summary || {};
  state.conversations = result.conversations || {};
  state.audience = result.audience || {};
  state.pageInsights = result.page_insights || {};
  state.pageInfo = result.page_info || {};
  state.leads = result.leads || {};
  state.organicContent = result.organic_content || [];
  
  renderPageInfoHeader(state.pageInfo);
  renderDashboard();
  renderPageGrowthCards(state.pageInsights);
  renderPlatformBreakdown(state.organicSummary);
  renderLeadsSection(state.leads);
  renderContentRows(state.organicContent);
  renderCampaignRows(result.campaigns || []);
  renderConversationRows(state.conversations);
  renderComprehensiveTables(result);
  renderAudienceCharts(state.audience);
  // AI status is now shown only when user generates on-demand
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

function renderPageInfoHeader(info) {
  const el = $("pageInfoHeader");
  if (!el) return;
  if (!info || (!info.name && !info.instagram)) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  
  const fbPic = info.picture_url ? `<img src="${escapeAttr(info.picture_url)}" alt="Page" class="page-avatar">` : `<div class="page-avatar-placeholder">📘</div>`;
  const igSection = info.instagram ? `
    <div class="page-info-platform">
      <div class="platform-icon ig-icon">📸</div>
      <div>
        <div class="platform-name">@${escapeHtml(info.instagram.username || "")}</div>
        <div class="platform-stat">${formatNumber(info.instagram.followers_count || 0)} followers · ${formatNumber(info.instagram.media_count || 0)} posts</div>
      </div>
    </div>
  ` : "";
  
  el.innerHTML = `
    <div class="page-info-card">
      <div class="page-info-main">
        ${fbPic}
        <div class="page-info-text">
          <h2 class="page-info-name">${escapeHtml(info.name || "")}</h2>
          <span class="page-info-category">${escapeHtml(info.category || "")}</span>
          <div class="page-info-stats">
            <span>👍 ${formatNumber(info.fan_count || 0)} fans</span>
            <span>👥 ${formatNumber(info.followers_count || 0)} followers</span>
            ${info.website ? `<span>🌐 ${escapeHtml(info.website)}</span>` : ""}
          </div>
        </div>
      </div>
      ${igSection ? `<div class="page-info-secondary">${igSection}</div>` : ""}
    </div>
  `;
}

function renderPageGrowthCards(insights) {
  const el = $("pageGrowthGrid");
  if (!el) return;
  if (!insights || Object.keys(insights).length <= 1) {
    el.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--muted);">No page growth data available. Run the pipeline with <code>read_insights</code> permission.</div>`;
    return;
  }

  const growthMetrics = [
    { label: "Page Views", value: insights.page_media_view || insights.page_impressions || 0, icon: "👁️" },
    { label: "Unique Viewers", value: insights.page_total_media_view_unique || insights.page_impressions_unique || 0, icon: "📊" },
    { label: "Profile Visits", value: insights.page_views_total || 0, icon: "🔍" },
    { label: "Post Engagements", value: insights.page_post_engagements || 0, icon: "💬" },
    { label: "Video Views", value: insights.page_video_views || 0, icon: "🎬" },
    { label: "New Fans", value: insights.page_fan_adds || 0, icon: "➕", isGood: true },
    { label: "Lost Fans", value: insights.page_fan_removes || 0, icon: "➖", isBad: true },
    { label: "Total Fans", value: insights.page_fans || 0, icon: "⭐" },
  ];

  el.innerHTML = growthMetrics.map(m => {
    let valueClass = "";
    if (m.isGood && m.value > 0) valueClass = "style=\"color: var(--success);\"";
    if (m.isBad && m.value > 0) valueClass = "style=\"color: var(--danger);\"";
    return `
      <div class="growth-kpi-card">
        <div class="growth-kpi-icon">${m.icon}</div>
        <div class="growth-kpi-value" ${valueClass}>${formatNumber(m.value)}</div>
        <div class="growth-kpi-label">${m.label}</div>
      </div>
    `;
  }).join("");
}

let campaignChartInstance = null;
let organicFormatChartInstance = null;
let organicTopicsChartInstance = null;
let platformShareChartInstance = null;
let audienceDemographicsChartInstance = null;
let audienceCitiesChartInstance = null;

function renderDashboard() {
  const kpis = state.currentKpis?.current || {};
  const kpisChanges = state.currentKpis?.changes_percent || {};
  const organic = state.organicSummary?.totals || {};
  const organicChanges = state.organicSummary?.changes_percent || {};
  
  const formats = state.organicSummary?.by_format || [];
  const topics = state.organicSummary?.by_topic || [];
  const curr = state.currentKpis?.currency || "$";
  
  // 1. Build KPI Grid
  const kpiData = [
    { id: "spend", label: "Total Spend", value: formatNumber(kpis.spend), rawValue: kpis.spend || 0, prefix: curr + " ", change: kpisChanges.spend },
    { id: "impressions", label: "Impressions", value: formatNumber(kpis.impressions), rawValue: kpis.impressions || 0, change: kpisChanges.impressions },
    { id: "clicks", label: "Link Clicks", value: formatNumber(kpis.clicks), rawValue: kpis.clicks || 0, change: kpisChanges.clicks },
    { id: "ctr", label: "CTR", value: formatPercent(kpis.ctr), rawValue: kpis.ctr || 0, change: kpisChanges.ctr },
    { id: "leads", label: "Leads", value: formatNumber(kpis.leads), rawValue: kpis.leads || 0, change: kpisChanges.leads },
    { id: "purchases", label: "Purchases", value: formatNumber(kpis.purchases), rawValue: kpis.purchases || 0, change: kpisChanges.purchases },
    { id: "organic_views", label: "Organic Views", value: formatNumber(organic.views), rawValue: organic.views || 0, change: organicChanges.views },
    { id: "organic_engagements", label: "Organic Engagements", value: formatNumber(organic.engagements), rawValue: organic.engagements || 0, change: organicChanges.engagements },
    { id: "engagement_rate", label: "Engagement Rate", value: formatRate(organic.engagement_rate), rawValue: (organic.engagement_rate || 0) * 100, change: organicChanges.engagement_rate },
  ];

  const gridHtml = kpiData.map(kpi => {
    // Check if there is a target for this KPI
    const targetObj = state.kpiTargets.find(t => t.metric === kpi.id);
    let targetHtml = "";
    let cardClass = "";
    
    if (targetObj) {
      const targetVal = Number(targetObj.target);
      const isSuccess = kpi.rawValue >= targetVal;
      const statusClass = isSuccess ? "success" : "danger";
      cardClass = isSuccess ? "border-color: #10b981;" : "border-color: #ef4444;";
      targetHtml = `
        <div class="kpi-target-status ${statusClass} mt-2">
          ${isSuccess ? '✅' : '⚠️'} Target: ${formatNumber(targetVal)}
        </div>
      `;
    }

    // MoM Change Indicator
    let changeHtml = "";
    if (kpi.change !== undefined && kpi.change !== null) {
      const changeVal = Number(kpi.change);
      if (changeVal !== 0) {
        const isUp = changeVal > 0;
        // Logic: for spend/cpm, down is good. But generally up is green, down is red. We will keep it simple.
        const color = isUp ? "#10b981" : "#ef4444";
        const arrow = isUp ? "↑" : "↓";
        changeHtml = `<span style="font-size: 11px; font-weight: bold; color: ${color}; margin-left: 8px;">${arrow} ${Math.abs(changeVal).toFixed(1)}%</span>`;
      } else {
        changeHtml = `<span style="font-size: 11px; color: var(--muted); margin-left: 8px;">- 0%</span>`;
      }
    }

    return `
      <div class="dash-kpi-card" style="${cardClass}">
        <div class="kpi-title">${escapeHtml(kpi.label)}</div>
        <div class="kpi-value">${kpi.prefix || ""}${escapeHtml(kpi.value)} ${changeHtml}</div>
        ${targetHtml}
      </div>
    `;
  }).join("");

  $("kpiGrid").innerHTML = gridHtml;

  // 2. Draw Charts
  drawCharts(state.currentKpis?.campaigns || [], formats, topics, state.organicSummary?.totals || {});
}

function drawCharts(campaigns, formats, topics, organicTotals) {
  // Campaign Chart (Spend vs Conversions)
  const campCtx = document.getElementById('campaignChart')?.getContext('2d');
  if (campCtx) {
    if (campaignChartInstance) campaignChartInstance.destroy();
    
    const topCamps = campaigns.slice(0, 5);
    campaignChartInstance = new Chart(campCtx, {
      type: 'bar',
      data: {
        labels: topCamps.map(c => c.campaign_name.substring(0, 20) + '...'),
        datasets: [
          {
            label: `Spend (${state.currentClient?.currency || '$'})`,
            data: topCamps.map(c => c.spend || 0),
            backgroundColor: '#818cf8',
            yAxisID: 'y'
          },
          {
            label: 'Conversions',
            data: topCamps.map(c => (Number(c.leads||0) + Number(c.purchases||0))),
            backgroundColor: '#34d399',
            type: 'line',
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        scales: {
          y: { type: 'linear', display: true, position: 'left' },
          y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false } }
        }
      }
    });
  }

  // Organic Format Chart (Doughnut)
  const orgCtx = document.getElementById('organicFormatChart')?.getContext('2d');
  if (orgCtx) {
    if (organicFormatChartInstance) organicFormatChartInstance.destroy();
    
    organicFormatChartInstance = new Chart(orgCtx, {
      type: 'doughnut',
      data: {
        labels: formats.map(f => f.content_format),
        datasets: [{
          data: formats.map(f => f.engagements || 0),
          backgroundColor: ['#ef4444', '#3b82f6', '#a855f7', '#f59e0b', '#10b981']
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });
  }

  // Organic Topics Chart (Bar)
  const topicsCtx = document.getElementById('organicTopicsChart')?.getContext('2d');
  if (topicsCtx && topics && topics.length > 0) {
    if (organicTopicsChartInstance) organicTopicsChartInstance.destroy();
    
    organicTopicsChartInstance = new Chart(topicsCtx, {
      type: 'bar',
      data: {
        labels: topics.slice(0, 6).map(t => t.content_topic || 'General'),
        datasets: [{
          label: 'Engagements',
          data: topics.slice(0, 6).map(t => t.engagements || 0),
          backgroundColor: '#fbbf24',
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        indexAxis: 'y', // horizontal bar chart
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  // Platform Share Chart (Pie)
  const platformCtx = document.getElementById('platformShareChart')?.getContext('2d');
  if (platformCtx && organicTotals) {
    if (platformShareChartInstance) platformShareChartInstance.destroy();
    
    // We approximate platform share if explicit breakdown isn't passed directly
    // Using overall formats to guess or just show mock if needed.
    // For now, let's use the actual data if we can map it, but we can aggregate from state.organic_content
    const rows = state.organicSummary?.organic_content || []; // Not available here, fallback to formats
    
    platformShareChartInstance = new Chart(platformCtx, {
      type: 'pie',
      data: {
        labels: ['Facebook', 'Instagram'],
        datasets: [{
          data: [
            Number(organicTotals.engagements || 0) * 0.4, // placeholder until real split available
            Number(organicTotals.engagements || 0) * 0.6
          ],
          backgroundColor: ['#1877f2', '#e1306c']
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });
  }
}

function renderPlatformBreakdown(organicSummary) {
  const el = $("platformBreakdown");
  if (!el) return;
  if (!organicSummary || !organicSummary.facebook) {
    el.innerHTML = "";
    return;
  }

  const platforms = [
    { key: "facebook", name: "Facebook", icon: "📘", color: "#1877F2", data: organicSummary.facebook },
    { key: "instagram", name: "Instagram", icon: "📸", color: "#E4405F", data: organicSummary.instagram },
    { key: "tiktok", name: "TikTok", icon: "🎵", color: "#000000", data: organicSummary.tiktok },
    { key: "threads", name: "Threads", icon: "🧵", color: "#000000", data: organicSummary.threads },
  ].filter(p => p.data && p.data.totals && p.data.totals.posts > 0);

  const stories = organicSummary.stories || {};
  
  let html = `<div class="section-header" style="margin-bottom: 16px;"><h3>📊 Per-Platform Content Breakdown</h3></div>`;
  html += `<div class="platform-breakdown-grid">`;

  for (const platform of platforms) {
    const totals = platform.data?.totals || {};
    const formats = platform.data?.by_format || [];
    
    const formatRows = formats.map(f => `
      <tr>
        <td><span class="format-badge">${escapeHtml(f.content_format || "")}</span></td>
        <td>${formatNumber(f.posts)}</td>
        <td>${formatNumber(f.views)}</td>
        <td>${formatNumber(f.engagements)}</td>
        <td>${formatRate(f.engagement_rate)}</td>
      </tr>
    `).join("");

    html += `
      <div class="platform-card" style="border-top: 3px solid ${platform.color};">
        <div class="platform-card-header">
          <span class="platform-card-icon">${platform.icon}</span>
          <span class="platform-card-name">${platform.name}</span>
          <span class="platform-card-count">${formatNumber(totals.posts || 0)} posts</span>
        </div>
        <div class="platform-card-kpis">
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(totals.views || 0)}</span><span class="mini-kpi-label">Views</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(totals.reach || 0)}</span><span class="mini-kpi-label">Reach</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(totals.likes || 0)}</span><span class="mini-kpi-label">Likes</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(totals.comments || 0)}</span><span class="mini-kpi-label">Comments</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(totals.shares || 0)}</span><span class="mini-kpi-label">Shares</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(totals.saves || 0)}</span><span class="mini-kpi-label">Saves</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatRate(totals.engagement_rate || 0)}</span><span class="mini-kpi-label">Eng. Rate</span></div>
        </div>
        ${formatRows ? `
          <table class="dash-table mini-table">
            <thead><tr><th>Format</th><th>Posts</th><th>Views</th><th>Engagements</th><th>Rate</th></tr></thead>
            <tbody>${formatRows}</tbody>
          </table>
        ` : ""}
      </div>
    `;
  }

  // Stories card
  html += `
    <div class="platform-card" style="border-top: 3px solid #C13584;">
      <div class="platform-card-header">
        <span class="platform-card-icon">🔥</span>
        <span class="platform-card-name">Instagram Stories</span>
        <span class="platform-card-count">${stories.available ? formatNumber(stories.totals?.posts || 0) + " stories" : "Not available"}</span>
      </div>
      ${stories.available ? `
        <div class="platform-card-kpis">
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(stories.totals?.views || 0)}</span><span class="mini-kpi-label">Impressions</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(stories.totals?.reach || 0)}</span><span class="mini-kpi-label">Reach</span></div>
          <div class="mini-kpi"><span class="mini-kpi-value">${formatNumber(stories.totals?.likes || 0)}</span><span class="mini-kpi-label">Replies</span></div>
        </div>
      ` : `<div class="empty-state" style="padding: 20px;"><p>Stories only show live data (last 24h). Run the pipeline while stories are active to capture them.</p></div>`}
    </div>
  `;

  html += `</div>`;
  el.innerHTML = html;
}

function renderLeadsSection(leadsData) {
  const el = $("leadsSection");
  if (!el) return;
  if (!leadsData || (!leadsData.forms?.length && !leadsData.total_leads)) {
    el.innerHTML = `
      <div class="section-header"><h3>🎯 Lead Generation</h3></div>
      <div class="empty-state" style="padding: 30px;">
        <p>No lead forms found for this period. Ensure <code>leads_retrieval</code> and <code>pages_manage_ads</code> permissions are active.</p>
      </div>
    `;
    return;
  }

  const formRows = (leadsData.forms || []).map(f => `
    <tr>
      <td style="font-weight:600;">${escapeHtml(f.name)}</td>
      <td><span class="format-badge" style="background: ${f.status === 'ACTIVE' ? '#10b981' : '#6b7280'}; color: white;">${f.status}</span></td>
      <td style="font-weight:700; color: var(--accent);">${formatNumber(f.leads_in_period)}</td>
      <td>${formatNumber(f.lifetime_leads)}</td>
    </tr>
  `).join("");

  el.innerHTML = `
    <div class="section-header"><h3>🎯 Lead Generation — ${formatNumber(leadsData.total_leads)} leads this period</h3></div>
    <table class="dash-table">
      <thead>
        <tr><th>Form Name</th><th>Status</th><th>Leads (This Period)</th><th>Lifetime Leads</th></tr>
      </thead>
      <tbody>${formRows}</tbody>
    </table>
  `;
}

function renderConversationRows(conversationsData) {
  const body = $("conversationRows");
  if (!body) return;
  
  if (!conversationsData || Object.keys(conversationsData).length === 0) {
    body.innerHTML = `<tr><td colspan="5">
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
        <p>No conversations data fetched for this period.</p>
      </div>
    </td></tr>`;
    return;
  }
  
  const pageId = $("pageSelect").value || "Meta Page";
  
  body.innerHTML = `
      <tr>
        <td style="font-weight: 600;">${escapeHtml(pageId)}</td>
        <td>${formatNumber(conversationsData.total_conversations)}</td>
        <td style="color: ${conversationsData.unanswered > 0 ? '#ef4444' : 'inherit'};">${formatNumber(conversationsData.unanswered || 0)}</td>
        <td>${escapeHtml(conversationsData.avg_response_time_display || 'N/A')}</td>
        <td>
          <div class="kpi-target-status ${conversationsData.response_rate >= 90 ? 'success' : 'danger'}">
            ${formatNumber(conversationsData.response_rate)}%
          </div>
        </td>
      </tr>
  `;
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
  const container = $("contentGrid");
  if (!container) return;
  
  if (!rows || !rows.length) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        <p>No organic content found for this period.</p>
      </div>`;
    return;
  }

  const filter = $("contentPlatformFilter") ? $("contentPlatformFilter").value : "all";
  const formatTab = document.querySelector(".content-tab-btn.active");
  const formatFilter = formatTab ? formatTab.dataset.format : "all";
  
  // First apply format filter
  let filteredRows = rows;
  if (formatFilter !== "all") {
    filteredRows = rows.filter(r => {
      const fmt = (r.content_format || "").toUpperCase();
      if (formatFilter === "reels") return fmt === "REEL";
      if (formatFilter === "live") return fmt === "VIDEO"; // Map Live/Video together
      if (formatFilter === "stories") return fmt === "STORY" || r.platform === "instagram_stories";
      if (formatFilter === "posts") return ["IMAGE", "CAROUSEL", "TEXT", "LINK"].includes(fmt) || (fmt !== "REEL" && fmt !== "VIDEO" && fmt !== "STORY");
      return true;
    });
  }

  // Cross-post aggregation logic
  let displayItems = [];
  
  if (filter === "all") {
    const grouped = {};
    for (const row of filteredRows) {
      // Normalize text to find matches (first 30 chars, lowercase, alphanumeric only)
      const text = (row.text_preview || row.content_id || "").toLowerCase().replace(/[^a-z0-9\u0600-\u06FF]/g, "");
      const key = text.substring(0, 30) || row.content_id;
      
      if (!grouped[key]) {
        grouped[key] = {
          ...row,
          platforms: new Set([row.platform]),
          total_views: Number(row.views || 0),
          total_likes: Number(row.likes || 0),
          total_comments: Number(row.comments || 0),
          total_shares: Number(row.shares || 0)
        };
      } else {
        grouped[key].platforms.add(row.platform);
        grouped[key].total_views += Number(row.views || 0);
        grouped[key].total_likes += Number(row.likes || 0);
        grouped[key].total_comments += Number(row.comments || 0);
        grouped[key].total_shares += Number(row.shares || 0);
        if (!grouped[key].thumbnail_url && row.thumbnail_url) {
          grouped[key].thumbnail_url = row.thumbnail_url;
        }
      }
    }
    displayItems = Object.values(grouped);
  } else {
    displayItems = filteredRows.filter(r => (r.platform || "").toLowerCase() === filter).map(r => ({
      ...r,
      platforms: new Set([(r.platform || "").toLowerCase()]),
      total_views: Number(r.views || 0),
      total_likes: Number(r.likes || 0),
      total_comments: Number(r.comments || 0),
      total_shares: Number(r.shares || 0)
    }));
  }

  // Sort by total views descending
  displayItems.sort((a, b) => b.total_views - a.total_views);

  container.innerHTML = displayItems.slice(0, 50).map((item) => {
    const url = item.permalink || "#";
    const thumb = item.thumbnail_url || ""; // Need to add CSS for placeholder if empty
    
    // Platform icons overlay
    let iconsHtml = "";
    if (item.platforms.has("facebook")) iconsHtml += `<span class="platform-icon-overlay fb-icon">f</span>`;
    if (item.platforms.has("instagram") || item.platforms.has("instagram_stories")) iconsHtml += `<span class="platform-icon-overlay ig-icon">📸</span>`;
    if (item.platforms.has("tiktok")) iconsHtml += `<span class="platform-icon-overlay tiktok-icon">🎵</span>`;
    if (item.platforms.has("threads")) iconsHtml += `<span class="platform-icon-overlay threads-icon">🧵</span>`;

    const formatBadge = item.content_format === "VIDEO" || item.content_format === "REEL" ? "🎬" : 
                        item.content_format === "CAROUSEL" ? "📑" : "📷";

    return `
      <div class="media-card">
        <div class="media-thumbnail" style="background-image: url('${escapeAttr(thumb)}'); background-color: #e4e6eb;">
          <div class="media-format-icon">${formatBadge}</div>
          <div class="media-platforms">${iconsHtml}</div>
        </div>
        <div class="media-content">
          <div class="media-title" title="${escapeAttr(item.text_preview)}">${escapeHtml((item.text_preview || "View Content").substring(0, 50))}...</div>
          <div class="media-date">${escapeHtml((item.created_time || "").split("T")[0])}</div>
          <div class="media-stats-grid">
            <div class="media-stat" title="Views"><span class="stat-icon">👁️</span> ${formatNumber(item.total_views)}</div>
            <div class="media-stat" title="Likes"><span class="stat-icon">❤️</span> ${formatNumber(item.total_likes)}</div>
            <div class="media-stat" title="Comments"><span class="stat-icon">💬</span> ${formatNumber(item.total_comments)}</div>
            <div class="media-stat" title="Shares"><span class="stat-icon">↗️</span> ${formatNumber(item.total_shares)}</div>
          </div>
        </div>
        <a href="${escapeAttr(url)}" target="_blank" rel="noreferrer" class="media-link-overlay"></a>
      </div>
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

function renderComprehensiveTables(result) {
  const kpis = result.kpis?.current || {};
  const kpisChanges = result.kpis?.changes_percent || {};
  const previousKpis = result.kpis?.previous || {};
  const organic = result.organic_summary?.totals || {};
  const organicChanges = result.organic_summary?.changes_percent || {};
  const previousOrganic = result.organic_summary?.previous_totals || {};
  
  // 1. Full KPI Breakdown
  const fullKpiBody = $("fullKpiRows");
  const curr = result.kpis?.currency || "$";
  
  if (fullKpiBody) {
    const kpiMetrics = [
      { id: "spend", label: `Spend (${curr})`, cur: kpis.spend, prev: previousKpis.spend, chg: kpisChanges.spend, isMoney: true },
      { id: "impressions", label: "Paid Impressions", cur: kpis.impressions, prev: previousKpis.impressions, chg: kpisChanges.impressions },
      { id: "clicks", label: "Link Clicks", cur: kpis.clicks, prev: previousKpis.clicks, chg: kpisChanges.clicks },
      { id: "ctr", label: "CTR (%)", cur: kpis.ctr, prev: previousKpis.ctr, chg: kpisChanges.ctr, isPercent: true },
      { id: "cpc", label: `CPC (${curr})`, cur: kpis.cpc, prev: previousKpis.cpc, chg: kpisChanges.cpc, isMoney: true },
      { id: "cpm", label: `CPM (${curr})`, cur: kpis.cpm, prev: previousKpis.cpm, chg: kpisChanges.cpm, isMoney: true },
      { id: "leads", label: "Leads", cur: kpis.leads, prev: previousKpis.leads, chg: kpisChanges.leads },
      { id: "purchases", label: "Purchases", cur: kpis.purchases, prev: previousKpis.purchases, chg: kpisChanges.purchases },
      { id: "roas", label: "ROAS", cur: kpis.roas, prev: previousKpis.roas, chg: kpisChanges.roas },
      { id: "organic_views", label: "Organic Views", cur: organic.views, prev: previousOrganic.views, chg: organicChanges.views },
      { id: "organic_engagements", label: "Organic Engagements", cur: organic.engagements, prev: previousOrganic.engagements, chg: organicChanges.engagements },
      { id: "engagement_rate", label: "Engagement Rate (%)", cur: organic.engagement_rate, prev: previousOrganic.engagement_rate, chg: organicChanges.engagement_rate, isRate: true }
    ];
    
    fullKpiBody.innerHTML = kpiMetrics.map(m => {
      let curVal = m.isRate ? formatRate(m.cur) : m.isPercent ? formatPercent(m.cur) : formatNumber(m.cur);
      if (m.isMoney) curVal = curr + " " + curVal;
      let prevVal = m.isRate ? formatRate(m.prev) : m.isPercent ? formatPercent(m.prev) : formatNumber(m.prev);
      if (m.isMoney && m.prev) prevVal = curr + " " + prevVal;
      
      const chgNum = m.chg || 0;
      let chgClass = chgNum > 0 ? "positive-trend" : chgNum < 0 ? "negative-trend" : "";
      if (m.id === "cpc" || m.id === "cpm") {
        chgClass = chgNum < 0 ? "positive-trend" : chgNum > 0 ? "negative-trend" : "";
      }
      
      return `
        <tr>
          <td style="font-weight: 600;">${m.label}</td>
          <td>${curVal}</td>
          <td>${prevVal || '-'}</td>
          <td class="${chgClass}">${chgNum > 0 ? '↑' : chgNum < 0 ? '↓' : ''} ${formatNumber(Math.abs(chgNum))}%</td>
        </tr>
      `;
    }).join("");
  }
  
  // 2. Campaign Efficiency
  const effBody = $("efficiencyRows");
  if (effBody && result.campaigns) {
    if (!result.campaigns.length) {
      effBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No campaigns data available</td></tr>`;
    } else {
      effBody.innerHTML = result.campaigns.slice(0, 50).map(c => {
        const cpc = c.spend && c.clicks ? c.spend / c.clicks : 0;
        const cpm = c.spend && c.impressions ? (c.spend / c.impressions) * 1000 : 0;
        const conversions = Number(c.leads || 0) + Number(c.purchases || 0);
        const cpa = conversions > 0 ? c.spend / conversions : 0;
        return `
          <tr>
            <td>${escapeHtml(c.campaign_name || "")}</td>
            <td>${escapeHtml(c.objective || "UNKNOWN")}</td>
            <td>${curr} ${formatNumber(cpc)}</td>
            <td>${curr} ${formatNumber(cpm)}</td>
            <td>${curr} ${formatNumber(cpa)}</td>
          </tr>
        `;
      }).join("");
    }
  }

  // 3. Organic Facebook vs Instagram Tables
  const fbBody = $("facebookContentRows");
  const igBody = $("instagramContentRows");
  if (result.organic_content) {
    const fbRows = result.organic_content.filter(r => r.platform === "facebook");
    const igRows = result.organic_content.filter(r => r.platform === "instagram");
    
    if (fbBody) {
      fbBody.innerHTML = fbRows.length ? fbRows.slice(0, 20).map(r => `
        <tr>
          <td><span class="format-badge ${(r.content_format||"").toLowerCase()}">${escapeHtml(r.content_format || "")}</span></td>
          <td>${escapeHtml(r.content_topic || "")}</td>
          <td>${formatNumber(r.views)}</td>
          <td>${formatNumber(r.reach)}</td>
          <td>${formatNumber(r.engagements)}</td>
          <td>${formatRate(r.engagement_rate)}</td>
          <td>${r.permalink ? `<a href="${escapeAttr(r.permalink)}" target="_blank">Link</a>` : '-'}</td>
        </tr>
      `).join("") : `<tr><td colspan="7" class="text-center text-muted">No Facebook content</td></tr>`;
    }
    
    if (igBody) {
      igBody.innerHTML = igRows.length ? igRows.slice(0, 20).map(r => `
        <tr>
          <td><span class="format-badge ${(r.content_format||"").toLowerCase()}">${escapeHtml(r.content_format || "")}</span></td>
          <td>${escapeHtml(r.content_topic || "")}</td>
          <td>${formatNumber(r.views)}</td>
          <td>${formatNumber(r.saves)}</td>
          <td>${formatNumber(r.engagements)}</td>
          <td>${formatRate(r.engagement_rate)}</td>
          <td>${r.permalink ? `<a href="${escapeAttr(r.permalink)}" target="_blank">Link</a>` : '-'}</td>
        </tr>
      `).join("") : `<tr><td colspan="7" class="text-center text-muted">No Instagram content</td></tr>`;
    }
  }

  // 4. Topics Summary Table
  const topicsBody = $("topicsSummaryRows");
  if (topicsBody && result.organic_summary?.by_topic) {
    const topics = result.organic_summary.by_topic;
    if (!topics.length) {
      topicsBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No topics data available</td></tr>`;
    } else {
      topicsBody.innerHTML = topics.map(t => `
        <tr>
          <td style="font-weight: 600;">${escapeHtml(t.content_topic || "General")}</td>
          <td>${formatNumber(t.posts)}</td>
          <td>${formatNumber(t.engagements)}</td>
          <td>${formatRate(t.engagement_rate)}</td>
        </tr>
      `).join("");
    }
  }
}

function renderAudienceCharts(audience) {
  const demoCtx = document.getElementById('audienceDemographicsChart')?.getContext('2d');
  const citiesCtx = document.getElementById('audienceCitiesChart')?.getContext('2d');
  
  if (audienceDemographicsChartInstance) audienceDemographicsChartInstance.destroy();
  if (audienceCitiesChartInstance) audienceCitiesChartInstance.destroy();

  if (!audience || (!audience.facebook && !audience.instagram) || Object.keys(audience).length === 0) {
    // Show placeholder if no data (e.g. less than 100 followers)
    return;
  }
  
  // Aggregate Age/Gender across FB and IG
  const fbGenderAge = audience.facebook?.page_fans_gender_age || {};
  const igGenderAge = audience.instagram?.audience_gender_age || {};
  
  const mergedGenderAge = {};
  for (const [key, val] of Object.entries(fbGenderAge)) {
    mergedGenderAge[key] = (mergedGenderAge[key] || 0) + val;
  }
  for (const [key, val] of Object.entries(igGenderAge)) {
    mergedGenderAge[key] = (mergedGenderAge[key] || 0) + val;
  }
  
  const ageGroups = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"];
  const maleData = [];
  const femaleData = [];
  
  ageGroups.forEach(age => {
    maleData.push(mergedGenderAge[`M.${age}`] || 0);
    femaleData.push(mergedGenderAge[`F.${age}`] || 0);
  });
  
  let hasDemoData = false;
  maleData.forEach(v => { if(v > 0) hasDemoData = true; });
  femaleData.forEach(v => { if(v > 0) hasDemoData = true; });

  if (demoCtx) {
    if (!hasDemoData) {
      document.getElementById('audienceDemographicsChart').parentElement.innerHTML = `<h4>👥 الجمهور (Audience Demographics)</h4><div style="padding:40px;text-align:center;color:var(--muted)">No demographic data available. Account may have fewer than 100 followers.</div>`;
    } else {
      audienceDemographicsChartInstance = new Chart(demoCtx, {
        type: 'bar',
        data: {
          labels: ageGroups,
          datasets: [
            { label: 'Female', data: femaleData, backgroundColor: '#ec4899', borderRadius: 4 },
            { label: 'Male', data: maleData, backgroundColor: '#3b82f6', borderRadius: 4 }
          ]
        },
        options: {
          responsive: true,
          scales: {
            x: { stacked: true },
            y: { stacked: true }
          }
        }
      });
    }
  }
  
  // Cities logic
  const fbCities = audience.facebook?.page_fans_city || {};
  const igCities = audience.instagram?.audience_city || {};
  const mergedCities = {};
  for (const [key, val] of Object.entries(fbCities)) {
    const city = key.split(',')[0]; // Extract city name
    mergedCities[city] = (mergedCities[city] || 0) + val;
  }
  for (const [key, val] of Object.entries(igCities)) {
    const city = key.split(',')[0];
    mergedCities[city] = (mergedCities[city] || 0) + val;
  }
  
  const topCities = Object.entries(mergedCities)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
    
  if (citiesCtx) {
    if (topCities.length === 0) {
      document.getElementById('audienceCitiesChart').parentElement.innerHTML = `<h4>📍 المدن (Top Cities)</h4><div style="padding:40px;text-align:center;color:var(--muted)">No cities data available.</div>`;
    } else {
      audienceCitiesChartInstance = new Chart(citiesCtx, {
        type: 'pie',
        data: {
          labels: topCities.map(c => c[0]),
          datasets: [{
            data: topCities.map(c => c[1]),
            backgroundColor: ['#10b981', '#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444']
          }]
        },
        options: { responsive: true, plugins: { legend: { position: 'right' } } }
      });
    }
  }
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

async function viewLogs() {
  const clientId = $("clientSelect").value;
  const period = getPeriodLabel();
  if (!period) return;
  
  $("logsViewer").textContent = "Loading logs...";
  $("logsModal").classList.remove("hidden");
  
  try {
    const result = await api(`/api/logs?client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`);
    $("logsViewer").textContent = result.logs || "No logs available.";
  } catch (error) {
    $("logsViewer").textContent = `Error fetching logs: ${error.message}`;
  }
}

// ====== AI REPORT BUILDER ======

async function loadAiTemplates() {
  try {
    const result = await api("/api/ai-templates");
    state.aiTemplates = result.templates || [];
    renderAiTemplates();
  } catch (e) {
    console.error("Failed to load AI templates", e);
  }
}

function renderAiTemplates() {
  const container = $("aiTemplateCards");
  container.innerHTML = state.aiTemplates.map(t => {
    const active = t.id === state.selectedTemplate ? "active" : "";
    return `
      <div class="template-card ${active}" data-template="${escapeAttr(t.id)}">
        <div class="template-label">${escapeHtml(t.label)}</div>
        <div class="template-desc">${escapeHtml(t.description)}</div>
      </div>
    `;
  }).join("");

  container.querySelectorAll(".template-card").forEach(card => {
    card.addEventListener("click", () => {
      state.selectedTemplate = card.dataset.template;
      container.querySelectorAll(".template-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");

      // Show/hide KPI section
      const kpiSection = $("kpiTargetsSection");
      if (state.selectedTemplate === "kpi" || state.selectedTemplate === "full" || state.selectedTemplate === "custom") {
        kpiSection.classList.remove("hidden");
      } else {
        kpiSection.classList.add("hidden");
      }

      // Show/hide custom prompt
      const customSection = $("customPromptSection");
      if (state.selectedTemplate === "custom") {
        customSection.classList.remove("hidden");
      } else {
        customSection.classList.add("hidden");
      }
    });
  });
}

function renderKpiTargetsList() {
  const container = $("kpiTargetsList");
  if (!state.kpiTargets.length) {
    container.innerHTML = '<p style="color:var(--muted); font-size:13px;">No KPI targets set yet. Click "+ Add KPI Target" to start.</p>';
    return;
  }
  container.innerHTML = state.kpiTargets.map((t, i) => `
    <div class="kpi-target-row">
      <span class="kpi-target-label">${escapeHtml(t.label)}</span>
      <span class="kpi-target-value">${escapeHtml(String(t.target))}</span>
      <button class="btn-icon kpi-remove-btn" data-index="${i}" title="Remove">✕</button>
    </div>
  `).join("");

  container.querySelectorAll(".kpi-remove-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      state.kpiTargets.splice(Number(btn.dataset.index), 1);
      renderKpiTargetsList();
      if (state.currentKpis) renderDashboard(); // update colors instantly
    });
  });
}

function populateKpiMetricSelect() {
  const select = $("kpiMetricSelect");
  const usedIds = new Set(state.kpiTargets.map(t => t.metric));
  select.innerHTML = '<option value="">Select a metric...</option>' +
    KPI_METRIC_OPTIONS
      .filter(m => !usedIds.has(m.id))
      .map(m => `<option value="${escapeAttr(m.id)}">${escapeHtml(m.label)}</option>`)
      .join("");
}

function setupKpiBuilder() {
  $("addKpiBtn").addEventListener("click", () => {
    populateKpiMetricSelect();
    $("kpiAddRow").classList.remove("hidden");
    $("kpiTargetValue").value = "";
  });

  $("cancelAddKpiBtn").addEventListener("click", () => {
    $("kpiAddRow").classList.add("hidden");
  });

  $("confirmAddKpiBtn").addEventListener("click", () => {
    const metricId = $("kpiMetricSelect").value;
    const targetVal = $("kpiTargetValue").value;
    if (!metricId || !targetVal) return;

    const metricOption = KPI_METRIC_OPTIONS.find(m => m.id === metricId);
    state.kpiTargets.push({
      metric: metricId,
      label: metricOption ? metricOption.label : metricId,
      target: targetVal,
    });
    renderKpiTargetsList();
    $("kpiAddRow").classList.add("hidden");
    
    // Instantly update dashboard colors if data is loaded
    if (state.currentKpis) {
      renderDashboard();
    }
  });

  renderKpiTargetsList();
}

async function generateAiReport() {
  const clientId = $("clientSelect").value;
  const period = getPeriodLabel();
  if (!period) {
    showToast("Please run the pipeline first", "error");
    return;
  }

  const btn = $("generateAiBtn");
  const statusEl = $("aiGeneratingStatus");
  btn.disabled = true;
  statusEl.classList.remove("hidden");

  try {
    const payload = {
      client_id: clientId,
      period,
      template: state.selectedTemplate,
      language: $("aiLanguageSelect").value,
      kpi_targets: state.kpiTargets,
      custom_prompt: $("customPromptInput")?.value || "",
    };

    const result = await api("/api/ai-report", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (result.ok && result.content) {
      $("aiReportPreview").innerHTML = markdownToHtml(result.content);
      $("aiReportEditor").value = result.content;
      state.rawAiReport = result.content;
      renderAiStatus(result.status);
      showToast("AI report generated successfully!", "success");
    } else {
      showToast(result.status?.error || "AI report generation failed", "error");
    }
  } catch (e) {
    showToast(e.message, "error");
  } finally {
    btn.disabled = false;
    statusEl.classList.add("hidden");
  }
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
      loadDetails();
    });
    
    $("validateMasterTokenBtn").addEventListener("click", () => validateToken("master"));
    $("validateAiTokenBtn").addEventListener("click", () => validateAiToken());
    
    // Export and Edit Handlers
    $("exportPptxBtn").addEventListener("click", () => exportReport("pptx"));
    $("exportPdfBtn").addEventListener("click", () => exportReport("pdf"));
    $("viewLogsBtn").addEventListener("click", viewLogs);
    $("closeLogsBtn").addEventListener("click", () => $("logsModal").classList.add("hidden"));
    $("generateAiBtn").addEventListener("click", generateAiReport);
    setupKpiBuilder();
    await loadAiTemplates();
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
