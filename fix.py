import re

with open("dashboard/static/app.js", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Update Currency from hardcoded $ to state.currentClient.currency
# In KPI dashboard grid
content = content.replace('prefix: "$"', 'prefix: (state.currentClient?.currency || "$") + " "')
# In Full KPI Breakdown
content = content.replace('label: "Spend ($)"', 'label: `Spend (${state.currentClient?.currency || "$"})`')
content = content.replace('label: "CPC ($)"', 'label: `CPC (${state.currentClient?.currency || "$"})`')
content = content.replace('label: "CPM ($)"', 'label: `CPM (${state.currentClient?.currency || "$"})`')
content = content.replace('curVal = "$" + curVal', 'curVal = (state.currentClient?.currency || "$") + " " + curVal')
content = content.replace('prevVal = "$" + prevVal', 'prevVal = (state.currentClient?.currency || "$") + " " + prevVal')
# In Efficiency Rows
content = content.replace('<td>$${formatNumber(cpc)}</td>', '<td>${state.currentClient?.currency || "$"} ${formatNumber(cpc)}</td>')
content = content.replace('<td>$${formatNumber(cpm)}</td>', '<td>${state.currentClient?.currency || "$"} ${formatNumber(cpm)}</td>')
content = content.replace('<td>$${formatNumber(cpa)}</td>', '<td>${state.currentClient?.currency || "$"} ${formatNumber(cpa)}</td>')
# In Chart
content = content.replace("label: 'Spend ($)'", "label: `Spend (${state.currentClient?.currency || '$'})`")

# Fix 2: renderConversationRows
old_conv = """function renderConversationRows(conversationsData) {
  const body = $("conversationRows");
  if (!body) return;
  
  if (!conversationsData || !conversationsData.data || conversationsData.data.length === 0) {
    body.innerHTML = `<tr><td colspan="5">
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
        <p>No conversations data fetched for this period.</p>
      </div>
    </td></tr>`;
    return;
  }
  
  body.innerHTML = conversationsData.data.map(page => {
    return `
      <tr>
        <td style="font-weight: 600;">${escapeHtml(page.page_id)}</td>
        <td>${formatNumber(page.total_conversations)}</td>
        <td style="color: ${page.unanswered > 0 ? '#ef4444' : 'inherit'};">${formatNumber(page.unanswered)}</td>
        <td>${formatNumber(page.avg_response_time_minutes)} mins</td>
        <td>
          <div class="kpi-target-status ${page.response_rate_percent >= 90 ? 'success' : 'danger'}">
            ${formatNumber(page.response_rate_percent)}%
          </div>
        </td>
      </tr>
    `;
  }).join("");
}"""

new_conv = """function renderConversationRows(conversationsData) {
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
}"""

content = content.replace(old_conv, new_conv)

# Fix 3: Empty Charts handling
chart_logic = """  if (demoCtx) {
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
    
  if (citiesCtx && topCities.length > 0) {
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
  }"""

new_chart_logic = """  let hasDemoData = false;
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
  }"""

content = content.replace(chart_logic, new_chart_logic)

with open("dashboard/static/app.js", "w", encoding="utf-8") as f:
    f.write(content)

