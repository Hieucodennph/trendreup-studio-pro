const state = { health: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function setStatus(message, kind = "ready") {
  const line = $("#statusLine");
  line.textContent = message;
  line.className = kind ? `status-${kind}` : "";
}

function showResult(data) {
  $("#resultBox").textContent = JSON.stringify(data, null, 2);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function formToObject(form) {
  const data = new FormData(form);
  const output = {};
  for (const [key, value] of data.entries()) output[key] = value;
  for (const checkbox of form.querySelectorAll("input[type='checkbox']")) output[checkbox.name] = checkbox.checked;
  for (const number of form.querySelectorAll("input[type='number']")) output[number.name] = Number(output[number.name]);
  return output;
}

function csv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function submitForm(form, path, label, transform = (payload) => payload, after = refreshAll) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus(`${label} running...`, "running");
    try {
      const result = await api(path, { method: "POST", body: JSON.stringify(transform(formToObject(form))) });
      setStatus(`${label} complete.`, "success");
      showResult(result);
      await after();
    } catch (error) {
      setStatus(error.message, "failed");
      showResult({ success: false, error: error.message });
      await loadJobs();
    }
  });
}

function activateTab(id) {
  $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.tab === id));
  $$(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === id));
  $("#screenTitle").textContent = id
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function card(title, meta, extra = "") {
  return `<div class="job-item"><strong>${title}</strong><span class="job-meta">${meta}</span>${extra}</div>`;
}

async function loadHealth() {
  const health = await api("/api/health");
  state.health = health;
  $("#healthText").textContent = `${health.status} · ${health.platforms.length} platforms`;
  $("#settingsView").innerHTML = Object.entries(health)
    .map(([key, value]) => card(key, Array.isArray(value) ? value.join(", ") : typeof value === "object" ? JSON.stringify(value) : value))
    .join("");
}

async function loadPlatforms() {
  const data = await api("/api/platforms");
  const options = data.platforms.map((platform) => `<option value="${platform.id}">${platform.label}</option>`).join("");
  $$(".platform-select").forEach((select) => (select.innerHTML = options));
}

async function loadStats() {
  const { stats } = await api("/api/stats");
  const labels = {
    videos: "Videos",
    queue_pending: "Pending",
    queue_failed: "Failed",
    channels: "Channels",
    ideas: "Ideas",
    crawled: "Crawled",
    downloaded: "Downloaded",
    processed: "Processed",
    workers: "Worker Runs",
    total_views: "Views",
    total_likes: "Likes",
  };
  $("#statsGrid").innerHTML = Object.entries(labels)
    .map(([key, label]) => `<div class="metric"><span>${label}</span><strong>${stats[key] ?? 0}</strong></div>`)
    .join("");
}

async function loadJobs() {
  const data = await api("/api/jobs?limit=25");
  $("#jobsList").innerHTML = data.jobs.length
    ? data.jobs
        .map((job) => card(`#${job.id} ${job.kind} <span class="status-${job.status}">${job.status}</span>`, `${job.platform || "local"} · ${job.input || ""} · ${job.updated_at}`, job.error ? `<span class="status-failed">${job.error}</span>` : ""))
        .join("")
    : `<p>No jobs yet.</p>`;
}

async function loadIdeas() {
  const data = await api("/api/ideas");
  $("#ideasList").innerHTML = data.ideas.length
    ? data.ideas.map((idea) => card(`${idea.name} <span class="badge">${idea.type}</span>`, `${idea.category} · ${idea.platform_filter} · priority ${idea.priority} · results ${idea.total_results}`)).join("")
    : `<p>No ideas yet.</p>`;
}

async function loadTrends() {
  const data = await api("/api/trends/content?limit=30");
  $("#trendsList").innerHTML = data.content.length
    ? data.content.map((item) => card(`${item.title}`, `${item.source_platform} · score ${item.trend_score} · views ${item.view_count}`, `<span class="job-meta">${item.video_url}</span>`)).join("")
    : `<p>No crawled trend content yet.</p>`;
}

async function loadQueue() {
  const data = await api("/api/queue?limit=50");
  $("#queueList").innerHTML = data.queue.length
    ? data.queue.map((item) => card(`#${item.id} <span class="status-${item.status}">${item.status}</span> ${item.platform}`, `${item.url} · priority ${item.priority} · channel ${item.channel_id}`)).join("")
    : `<p>Queue is empty.</p>`;
}

async function loadChannels() {
  const data = await api("/api/channels");
  $("#channelsList").innerHTML = data.channels.length
    ? data.channels.map((item) => card(`${item.name}`, `${item.id} · ${item.platform} · videos ${item.total_videos}`)).join("")
    : `<p>No channels yet.</p>`;
}

async function loadVideos() {
  const data = await api("/api/videos?limit=10");
  $("#videosList").innerHTML = data.videos.length
    ? data.videos.map((video) => card(video.title || video.id, `${video.source_platform} · ${video.status} · ${video.output_path || video.source_url}`)).join("")
    : `<p>No videos saved yet.</p>`;
}

async function loadHashtags() {
  const data = await api("/api/trends/hashtags");
  $("#hashtagsList").innerHTML = data.hashtags.map((tag) => card(tag.name, `${tag.platform} · score ${tag.score}`)).join("");
}

async function loadWorkerRuns() {
  const data = await api("/api/worker/runs?limit=30");
  const html = data.runs.length
    ? data.runs
        .map((run) =>
          card(
            `#${run.id} ${run.worker_id} <span class="status-${run.status}">${run.status}</span>`,
            `queue ${run.queue_id || "-"} · ${run.updated_at}`,
            run.detail?.error ? `<span class="status-failed">${run.detail.error}</span>` : "",
          ),
        )
        .join("")
    : `<p>No worker activity yet.</p>`;
  const workerList = $("#workerRunsList");
  if (workerList) workerList.innerHTML = html;
}

async function refreshAll() {
  await Promise.all([loadHealth(), loadStats(), loadJobs(), loadIdeas(), loadTrends(), loadQueue(), loadChannels(), loadVideos(), loadHashtags(), loadWorkerRuns()]);
  const autoQueueList = $("#autoQueueList");
  const queueList = $("#queueList");
  if (autoQueueList && queueList) autoQueueList.innerHTML = queueList.innerHTML;
}

function setupTheme() {
  const saved = localStorage.getItem("studio-theme") || "dark";
  document.body.classList.toggle("light", saved === "light");
  $("#themeToggle").checked = saved === "light";
  $("#themeToggle").addEventListener("change", (event) => {
    document.body.classList.toggle("light", event.target.checked);
    localStorage.setItem("studio-theme", event.target.checked ? "light" : "dark");
  });
}

async function main() {
  setupTheme();
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tab)));
  $("#refreshAll").addEventListener("click", refreshAll);
  await loadPlatforms();

  submitForm($("#reupForm"), "/api/reup", "Quick reup");
  submitForm($("#autoPlanForm"), "/api/automation/plan", "Auto reup plan", (payload) => ({
    ...payload,
    platforms: csv(payload.platforms),
  }));
  submitForm($("#downloadForm"), "/api/download", "Download", (payload) => ({
    ...payload,
    output_dir: payload.output_dir || null,
  }));
  submitForm($("#ideaForm"), "/api/ideas", "Add idea", (payload) => payload, async () => {
    await Promise.all([loadIdeas(), loadStats()]);
  });
  submitForm($("#trendForm"), "/api/trends/search", "Trend search", (payload) => ({ ...payload, platforms: csv(payload.platforms) }), async () => {
    await Promise.all([loadTrends(), loadStats()]);
  });
  submitForm($("#queueForm"), "/api/queue", "Add queue item", (payload) => payload, async () => {
    await Promise.all([loadQueue(), loadStats()]);
  });
  submitForm($("#channelForm"), "/api/channels", "Save channel", (payload) => payload, async () => {
    await Promise.all([loadChannels(), loadStats()]);
  });
  submitForm($("#processForm"), "/api/video/process", "Video process");
  submitForm($("#contentForm"), "/api/content/edit", "Content edit");

  $("#crawlIdeasBtn").addEventListener("click", async () => {
    setStatus("Crawling active ideas...", "running");
    const result = await api("/api/trends/crawl-ideas", { method: "POST", body: JSON.stringify({ max_per_idea: 3 }) });
    showResult(result);
    setStatus("Idea crawl complete.", "success");
    await Promise.all([loadTrends(), loadIdeas(), loadStats()]);
  });

  $("#processNextBtn").addEventListener("click", async () => {
    setStatus("Processing next queue item...", "running");
    try {
      const result = await api("/api/queue/process-next", { method: "POST", body: JSON.stringify({}) });
      showResult(result);
      setStatus("Queue step complete.", "success");
    } catch (error) {
      showResult({ success: false, error: error.message });
      setStatus(error.message, "failed");
    }
    await Promise.all([loadQueue(), loadJobs(), loadStats()]);
  });

  await refreshAll();
}

main().catch((error) => {
  setStatus(error.message, "failed");
  showResult({ success: false, error: error.message });
});
