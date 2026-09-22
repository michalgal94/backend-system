const jobApi = '';
const baseHost = `${location.protocol}//${location.hostname}`;
const processorApi = `${baseHost}:8001`;
const auditApi = `${baseHost}:8002`;
let selectedJobId = null;
let jobs = [];

const byId = (id) => document.getElementById(id);
const tagsFrom = (value) => value.split(',').map((tag) => tag.trim()).filter(Boolean);

function showNotice(message, isError = false) {
  const notice = byId('notice');
  notice.textContent = message;
  notice.style.background = isError ? '#fef2f2' : '';
  notice.style.color = isError ? '#9f2929' : '';
  notice.hidden = false;
  window.setTimeout(() => { notice.hidden = true; }, 5500);
}

function addDocument(id = '', text = '') {
  const node = byId('document-template').content.firstElementChild.cloneNode(true);
  node.querySelector('.document-id').value = id;
  node.querySelector('.document-text').value = text;
  node.querySelector('.remove-document').addEventListener('click', () => {
    if (byId('documents').children.length > 1) node.remove();
  });
  byId('documents').append(node);
}

async function request(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.detail?.message || data?.detail || `Request failed (${response.status})`);
  return data;
}

function statusElement(status) {
  const badge = document.createElement('span');
  badge.className = `status ${status}`;
  badge.textContent = status;
  return badge;
}

function renderJobs() {
  const target = byId('jobs');
  target.replaceChildren();
  if (!jobs.length) { target.innerHTML = '<p class="muted">No jobs yet. Create your first request.</p>'; return; }
  jobs.slice().reverse().forEach((job) => {
    const row = document.createElement('button');
    row.className = `job-row ${job.id === selectedJobId ? 'selected' : ''}`;
    const title = document.createElement('span'); title.className = 'job-row-title'; title.textContent = job.title || 'Untitled job';
    const info = document.createElement('small'); info.textContent = `${job.documents.length} document${job.documents.length === 1 ? '' : 's'} · ${new Date(job.created_at).toLocaleString()}`;
    row.append(title, statusElement(job.status), info);
    row.addEventListener('click', () => selectJob(job.id));
    target.append(row);
  });
}

async function loadJobs() {
  try { jobs = await request(`${jobApi}/api/jobs`); renderJobs(); if (selectedJobId) await selectJob(selectedJobId, false); }
  catch (error) { showNotice(`Could not load jobs: ${error.message}`, true); }
}

async function selectJob(id, updateList = true) {
  try {
    const job = await request(`${jobApi}/api/jobs/${id}`);
    selectedJobId = id;
    if (updateList) renderJobs();
    byId('details-card').hidden = false;
    byId('detail-title').textContent = job.title || 'Untitled job';
    byId('detail-id').textContent = `Job ID: ${job.id}`;
    byId('detail-status').replaceWith(statusElement(job.status));
    byId('detail-status').id = 'detail-status';
    byId('edit-title').value = job.title || '';
    byId('edit-tags').value = job.tags.join(', ');
    const error = byId('detail-error'); error.hidden = !job.error; error.textContent = job.error || '';
    renderResults(job.results || [], job.status);
    await loadAudit(job);
  } catch (error) { showNotice(`Could not load job: ${error.message}`, true); }
}

function renderResults(results, status) {
  const target = byId('results'); target.replaceChildren();
  if (!results.length) {
    if (status === 'Pending' || status === 'Processing') target.innerHTML = '<p class="muted">Analysis is in progress. This page refreshes automatically.</p>';
    return;
  }
  const heading = document.createElement('h3'); heading.textContent = 'Document results'; target.append(heading);
  results.forEach((result) => {
    const card = document.createElement('article'); card.className = 'result';
    const title = document.createElement('h3'); title.textContent = result.document_id;
    const metrics = document.createElement('div'); metrics.className = 'metrics';
    [['Words', result.word_count], ['Unique words', result.unique_word_count], ['Characters', result.character_count]].forEach(([name, value]) => {
      const metric = document.createElement('span'); metric.className = 'metric'; metric.textContent = `${name}: ${value}`; metrics.append(metric);
    });
    const top = document.createElement('p'); top.className = 'top-words'; top.textContent = `Top words: ${(result.top_words || []).map((word) => `${word.word} (${word.count})`).join(', ') || 'None'}`;
    const hash = document.createElement('p'); hash.className = 'hash'; hash.textContent = `SHA-256: ${result.sha256}`;
    card.append(title, metrics, top, hash); target.append(card);
  });
}

async function loadAudit(job) {
  const target = byId('audit-result'); target.textContent = '';
  if (!['Completed', 'Failed'].includes(job.status)) return;
  try {
    const record = await request(`${auditApi}/api/audit/${job.id}`);
    target.textContent = `Audit record: ${record.status} · reported ${new Date(record.reported_at).toLocaleString()}`;
  } catch (_) { target.textContent = 'Audit record is not available yet.'; }
}

async function refreshHealth() {
  const services = [['job-health', `${jobApi}/health`], ['processor-health', `${processorApi}/health`], ['audit-health', `${auditApi}/health`]];
  await Promise.all(services.map(async ([id, url]) => {
    const dot = byId(id); dot.className = 'dot';
    try { await request(url); dot.classList.add('ok'); } catch (_) { dot.classList.add('bad'); }
  }));
}

byId('add-document').addEventListener('click', () => addDocument());
byId('refresh-jobs').addEventListener('click', loadJobs);
byId('refresh-health').addEventListener('click', refreshHealth);
byId('create-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const documents = [...byId('documents').children].map((row) => ({ id: row.querySelector('.document-id').value.trim(), text: row.querySelector('.document-text').value }));
  try {
    const job = await request(`${jobApi}/api/jobs`, { method: 'POST', body: JSON.stringify({ title: byId('title').value.trim() || null, tags: tagsFrom(byId('tags').value), documents }) });
    showNotice('Job accepted for processing.');
    event.target.reset(); byId('documents').replaceChildren(); addDocument();
    await loadJobs(); await selectJob(job.id);
  } catch (error) { showNotice(`Could not create job: ${error.message}`, true); }
});
byId('save-metadata').addEventListener('click', async () => {
  if (!selectedJobId) return;
  try {
    await request(`${jobApi}/api/jobs/${selectedJobId}`, { method: 'PATCH', body: JSON.stringify({ title: byId('edit-title').value.trim() || null, tags: tagsFrom(byId('edit-tags').value) }) });
    showNotice('Metadata saved.'); await loadJobs();
  } catch (error) { showNotice(`Could not save metadata: ${error.message}`, true); }
});

addDocument('document-1');
refreshHealth();
loadJobs();
window.setInterval(() => { if (jobs.some((job) => ['Pending', 'Processing'].includes(job.status))) loadJobs(); }, 2000);
