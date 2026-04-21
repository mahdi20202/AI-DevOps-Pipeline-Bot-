const state = { token: localStorage.getItem('access_token') || '', pipelineChart: null, githubChart: null, stageMixChart: null, deployChart: null, currentRunId: null };
const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => [...document.querySelectorAll(selector)];

function setMessage(message, isError = false) {
  const target = qs('#loginMessage');
  target.textContent = message;
  target.style.color = isError ? 'var(--danger)' : 'var(--muted)';
}

async function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(url, { credentials: 'include', ...options, headers });
  if (!response.ok) {
    let detail = 'Request failed';
    try { detail = (await response.json()).detail || detail; } catch { detail = response.statusText || detail; }
    throw new Error(detail);
  }
  const contentType = response.headers.get('content-type') || '';
  return contentType.includes('application/json') ? response.json() : response.text();
}

async function login(event) {
  event.preventDefault();
  const formData = new FormData(event.target);
  try {
    const payload = new URLSearchParams(formData);
    const data = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, credentials: 'include', body: payload }).then(async (res) => {
      if (!res.ok) throw new Error((await res.json()).detail || 'Invalid email or password');
      return res.json();
    });
    state.token = data.access_token; localStorage.setItem('access_token', state.token);
    setMessage(`Signed in as ${data.user.full_name}`); qs('#profileChip').textContent = `${data.user.role} · active`;
    await Promise.all([loadProfile(), loadRuns(), maybeLoadGitHubDashboard()]);
  } catch (error) { setMessage(error.message, true); }
}

async function loadProfile() {
  try {
    const profile = await apiFetch('/api/auth/me');
    qs('#profileChip').textContent = `${profile.role} · ${profile.full_name}`;
  } catch (_) {}
}

async function logout() {
  await apiFetch('/api/auth/logout', { method: 'POST' });
  state.token = ''; localStorage.removeItem('access_token'); setMessage('Logged out'); qs('#profileChip').textContent = 'Auth required';
}

async function createRun(event) {
  event.preventDefault();
  if (!state.token) return setMessage('Please sign in first.', true);
  const form = new FormData(event.target);
  try {
    const result = await apiFetch('/api/pipeline/runs', { method: 'POST', body: form });
    state.currentRunId = result.run_id;
    await Promise.all([loadRuns(), loadRunDetail(result.run_id)]);
    const repo = form.get('github_repository');
    if (repo) { qs('#repoLookup').value = repo; qs('#branchLookup').value = form.get('github_branch') || ''; await loadGitHubDashboard(repo, form.get('github_branch')); }
    if (form.get('jira_issue_key')) await previewJiraIssue(form.get('jira_issue_key'));
  } catch (error) { alert(error.message); }
}

async function previewJiraIssue(issueKey) {
  if (!issueKey) return;
  try {
    const issue = await apiFetch(`/api/jira/issues/${issueKey}`);
    qs('#jiraPreview').innerHTML = `
      <div class="list-item"><strong>${issue.key} · ${issue.summary}</strong><span>${issue.status} · ${issue.priority || 'No priority'} · ${issue.assignee || 'Unassigned'}</span></div>
      <div class="list-item"><strong>Description</strong><span>${issue.description}</span></div>
      <div class="list-item"><strong>Acceptance criteria</strong><span>${(issue.acceptance_criteria || []).join(' · ') || 'No explicit criteria found'}</span></div>`;
  } catch (error) { qs('#jiraPreview').innerHTML = `<div class="list-item"><strong>Jira preview failed</strong><span>${error.message}</span></div>`; }
}

async function loadRuns() {
  if (!state.token) return;
  const data = await apiFetch('/api/pipeline/runs');
  const runList = qs('#runList');
  runList.innerHTML = data.runs.length ? data.runs.map((run) => `
    <button class="run-item" data-run-id="${run.id}">
      <strong>#${run.id} · ${run.title}</strong>
      <span>${run.source_type.replace('_', ' ')} · ${run.overall_status} · ${run.progress_percent}%</span>
    </button>`).join('') : '<div class="run-item"><strong>No runs yet</strong><span>Launch a pipeline to populate history.</span></div>';
  qsa('[data-run-id]').forEach((item) => item.addEventListener('click', () => loadRunDetail(item.dataset.runId)));
  updatePipelineChart(data.runs);
  if (data.runs[0] && !state.currentRunId) { state.currentRunId = data.runs[0].id; loadRunDetail(state.currentRunId); }
}

async function loadRunDetail(runId) {
  const run = await apiFetch(`/api/pipeline/runs/${runId}`);
  state.currentRunId = run.id; qs('#runBadge').textContent = `${run.overall_status.toUpperCase()} · ${run.progress_percent}%`;
  qs('#stageContainer').innerHTML = run.stages.map((stage) => `
    <article class="stage-card">
      <div class="chip ${stage.status === 'success' ? 'success' : 'warning'}">${stage.stage_name}</div>
      <h4>${stage.summary}</h4>
      <p>Status: ${stage.status}</p>
      <div class="detail-list">${stage.details.map((detail) => `<div class="detail-row"><span>${detail.label}</span><span>${detail.value}</span></div>`).join('')}</div>
    </article>`).join('');
  updateStageMixChart(run.stages);
}

async function maybeLoadGitHubDashboard() {
  const repo = qs('#repoLookup').value || qs('#githubRepository').value;
  const branch = qs('#branchLookup').value || qs('#githubBranch').value;
  if (repo) return loadGitHubDashboard(repo, branch);
}

async function loadGitHubDashboard(repository, branch) {
  if (!state.token || !repository) return;
  const params = new URLSearchParams({ repository }); if (branch) params.set('branch', branch);
  const data = await apiFetch(`/api/github/dashboard?${params.toString()}`);
  qs('#healthScore').textContent = `${data.health_score}%`; qs('#buildRate').textContent = `${data.build_success_rate}%`; qs('#deploymentsCount').textContent = data.deployments_this_week;
  qs('#repoHeading').textContent = `${data.repository} · ${data.default_branch}`; qs('#integrationStatus').textContent = `${data.integration_status} · ${data.pull_requests_open} PRs`; qs('#integrationStatus').className = 'chip success';
  qs('#githubStages').innerHTML = data.pipeline_stages.map((item) => `<article class="stage-card"><div class="chip ${item.status === 'success' ? 'success' : 'warning'}">${item.status}</div><h4>${item.stage}</h4><p>${item.duration}s</p></article>`).join('');
  qs('#commitList').innerHTML = data.commits.map((commit) => `<div class="list-item"><strong>${commit.sha} · ${commit.message}</strong><span>${commit.author} · ${commit.time}</span></div>`).join('');
  qs('#workflowTable').innerHTML = data.workflow_runs.map((run) => `<tr><td>${run.name}</td><td>${run.branch}</td><td>${run.status}</td><td>${run.conclusion}</td><td>${run.duration_seconds}s</td><td>${run.started_at}</td></tr>`).join('');
  qs('#badgeRow').innerHTML = (data.badges || []).map((badge) => `<a class="badge-card" href="${badge.target_url}" target="_blank" rel="noreferrer"><img alt="${badge.label}" src="${badge.image_url}" /><span>${badge.label}</span></a>`).join('');
  updateGitHubChart(data.workflow_runs);
}

function updatePipelineChart(runs) {
  const ctx = qs('#pipelineChart'); const labels = runs.slice(0, 6).reverse().map((run) => `Run ${run.id}`); const values = runs.slice(0, 6).reverse().map((run) => run.progress_percent);
  if (state.pipelineChart) state.pipelineChart.destroy();
  state.pipelineChart = new Chart(ctx, { type: 'line', data: { labels, datasets: [{ label: 'Progress %', data: values, borderWidth: 3, tension: 0.35, fill: true }] }, options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, max: 100 } } } });
}
function updateStageMixChart(stages) {
  const ctx = qs('#stageMixChart'); if (state.stageMixChart) state.stageMixChart.destroy();
  const statusCounts = stages.reduce((acc, stage) => { acc[stage.status] = (acc[stage.status] || 0) + 1; return acc; }, {});
  state.stageMixChart = new Chart(ctx, { type: 'doughnut', data: { labels: Object.keys(statusCounts), datasets: [{ data: Object.values(statusCounts) }] }, options: { responsive: true } });
}
function updateGitHubChart(runs) {
  const ctx = qs('#githubChart'); if (state.githubChart) state.githubChart.destroy();
  state.githubChart = new Chart(ctx, { type: 'bar', data: { labels: runs.map((run) => run.name), datasets: [{ label: 'Duration (s)', data: runs.map((run) => run.duration_seconds) }] }, options: { responsive: true, plugins: { legend: { display: false } } } });
}
function updateDeployChart() {
  const ctx = qs('#deployChart'); if (state.deployChart) state.deployChart.destroy();
  state.deployChart = new Chart(ctx, { type: 'radar', data: { labels: ['Security', 'CI/CD', 'Hosting', 'Telemetry', 'Auth'], datasets: [{ label: 'Platform readiness', data: [90, 92, 88, 91, 93] }] }, options: { responsive: true, plugins: { legend: { display: false } } } });
}
function bindNavigation() {
  qsa('.nav-link').forEach((button) => button.addEventListener('click', () => {
    qsa('.nav-link').forEach((node) => node.classList.remove('active')); button.classList.add('active');
    ['platform', 'github', 'deploy'].forEach((view) => qs(`#${view}View`).classList.add('hidden')); qs(`#${button.dataset.view}View`).classList.remove('hidden');
  }));
}
function bindThemeToggle() {
  const saved = localStorage.getItem('theme'); if (saved === 'light') document.body.classList.add('light');
  qs('#themeToggle').addEventListener('click', () => { document.body.classList.toggle('light'); localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark'); });
}
function bindSeedButtons() {
  qs('#loadSampleTicket').addEventListener('click', () => {
    qs('#ticketText').value = 'JIRA-300: Deliver version 3 of the AI DevOps platform with live Jira ingestion, production login with refresh tokens, CI badges, hosted deployment manifests, and real analytics charts for workflow health.';
    qs('#githubRepository').value = 'mahdi20202/AI-DevOps-Pipeline-Bot-'; qs('#githubBranch').value = 'main';
  });
  qs('#fetchJiraBtn').addEventListener('click', () => previewJiraIssue(qs('#jiraIssueKey').value));
  qs('#logoutBtn').addEventListener('click', logout);
}
function bindGitHubForm() { qs('#githubForm').addEventListener('submit', async (event) => { event.preventDefault(); try { await loadGitHubDashboard(qs('#repoLookup').value, qs('#branchLookup').value); } catch (error) { alert(error.message); } }); }
window.addEventListener('DOMContentLoaded', async () => { bindNavigation(); bindThemeToggle(); bindSeedButtons(); bindGitHubForm(); updateDeployChart(); qs('#loginForm').addEventListener('submit', login); qs('#pipelineForm').addEventListener('submit', createRun); if (state.token) { setMessage('Session restored.'); await Promise.all([loadProfile(), loadRuns(), maybeLoadGitHubDashboard()]); } });
