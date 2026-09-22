/* NextGen PDF — Dashboard Controller & API Integration */

(function () {
  function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  function formatDate(isoString) {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return isoString;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>'"]/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[c]));
  }

  async function getAuthToken() {
    const user = window.nextgenFirebase?.auth?.currentUser;
    if (!user || user.isAnonymous) {
      window.location.href = '/pages/auth/login.html';
      throw new Error('Unauthenticated');
    }
    return await user.getIdToken();
  }

  async function fetchDashboardAPI(endpoint, options = {}) {
    const token = await getAuthToken();
    const baseUrl = (window.NEXTGEN_API_BASE || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
    const url = `${baseUrl}${endpoint}`;

    const headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    const res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      console.warn('[Dashboard] Session expired or invalid token. Redirecting to login.');
      window.location.href = '/pages/auth/login.html';
      throw new Error('Session expired');
    }

    if (!res.ok) {
      let detail = `Server error (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson.detail) detail = errJson.detail;
      } catch (e) {}
      throw new Error(detail);
    }

    return await res.json();
  }

  // --- Page Controllers ---

  // 1. OVERVIEW PAGE
  async function initOverviewPage() {
    const container = document.querySelector('.dashboard-content');
    if (!container) return;

    try {
      const data = await fetchDashboardAPI('/dashboard/overview');

      // Update Plan badge & daily usage
      document.querySelectorAll('[data-user-plan]').forEach(el => {
        el.textContent = `${(data.plan || 'FREE').toUpperCase()} PLAN`;
      });

      const usageTxt = document.querySelector('#overview-daily-usage-text');
      if (usageTxt) {
        usageTxt.textContent = `Daily operations: ${data.usage_today} / ${data.daily_limit} used (${data.remaining_today} remaining)`;
      }

      const progressFill = document.querySelector('#overview-daily-progress-fill');
      if (progressFill) {
        const pct = Math.min(100, Math.max(0, Math.round((data.usage_today / (data.daily_limit || 1)) * 100)));
        progressFill.style.width = `${pct}%`;
      }

      // Stats Cards
      const filesVal = document.querySelector('#stat-files-processed');
      if (filesVal) filesVal.textContent = data.files_processed || 0;

      const storageVal = document.querySelector('#stat-storage-used');
      if (storageVal) storageVal.textContent = formatBytes(data.total_bytes_processed || 0);

      const successVal = document.querySelector('#stat-success-rate');
      if (successVal) {
        const total = (data.successful_jobs || 0) + (data.failed_jobs || 0);
        const rate = total > 0 ? Math.round(((data.successful_jobs || 0) / total) * 100) : 100;
        successVal.textContent = `${rate}%`;
      }

      // Recent Jobs Table
      const recentContainer = document.querySelector('#recent-documents-container');
      if (recentContainer) {
        if (!data.recent_jobs || data.recent_jobs.length === 0) {
          recentContainer.innerHTML = `
            <p style="color: var(--text-muted); font-size: 14px;">No documents processed yet. Click "+ New PDF Task" above to process your first file.</p>
          `;
        } else {
          let rows = data.recent_jobs.map(job => `
            <tr style="border-bottom: 1px solid var(--border);">
              <td style="padding: 12px; font-family: monospace; font-weight: 700;">#TK-${job.job_id.substring(0, 6).toUpperCase()}</td>
              <td style="padding: 12px; font-weight: 600;">${escapeHtml(job.tool_name)}</td>
              <td style="padding: 12px;">
                <span class="badge" style="background: ${job.status === 'completed' ? 'rgba(40,167,69,0.1)' : 'rgba(220,53,69,0.1)'}; color: ${job.status === 'completed' ? 'var(--success)' : 'var(--danger)'}; padding: 4px 8px; border-radius: 4px; font-weight: 700; font-size: 12px;">
                  ${job.status.toUpperCase()}
                </span>
              </td>
              <td style="padding: 12px; color: var(--text-muted);">${formatDate(job.created_at)}</td>
              <td style="padding: 12px; text-align: right;">
                ${job.download_url ? `<button class="btn btn-outline btn-sm" onclick="NextGenDashboard.downloadFile('${job.result_file_id}', 'result.pdf')">Download</button>` : '—'}
              </td>
            </tr>
          `).join('');

          recentContainer.innerHTML = `
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
              <thead>
                <tr style="border-bottom: 1px solid var(--border); color: var(--text-muted);">
                  <th style="padding: 12px;">Task ID</th>
                  <th style="padding: 12px;">Operation</th>
                  <th style="padding: 12px;">Status</th>
                  <th style="padding: 12px;">Date</th>
                  <th style="padding: 12px; text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          `;
        }
      }

    } catch (err) {
      console.error('[Dashboard] Overview load error:', err);
    }
  }

  // 2. FILES PAGE
  let currentFilesPage = 1;
  const filesLimit = 10;

  async function loadUserFiles(page = 1) {
    const tableBody = document.querySelector('#files-table-body');
    const paginationEl = document.querySelector('#files-pagination');
    if (!tableBody) return;

    tableBody.innerHTML = `<tr><td colspan="4" style="padding: 24px; text-align: center; color: var(--text-muted);">Loading your files...</td></tr>`;

    try {
      const data = await fetchDashboardAPI(`/dashboard/files?page=${page}&limit=${filesLimit}`);
      currentFilesPage = data.page;

      if (!data.files || data.files.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="4" style="padding: 24px; text-align: center; color: var(--text-muted);">No saved files found. Process a PDF to save result files!</td></tr>`;
        if (paginationEl) paginationEl.style.display = 'none';
        return;
      }

      tableBody.innerHTML = data.files.map(f => `
        <tr style="border-bottom: 1px solid var(--border);">
          <td style="padding: 12px; font-weight: 700;">📄 ${escapeHtml(f.filename)}</td>
          <td style="padding: 12px;">${formatBytes(f.size)}</td>
          <td style="padding: 12px; color: var(--text-muted);">${formatDate(f.created_at)}</td>
          <td style="padding: 12px; text-align: right; display: flex; gap: 8px; justify-content: flex-end;">
            <button class="btn btn-outline btn-sm" onclick="NextGenDashboard.downloadFile('${f.id}', '${escapeHtml(f.filename)}')">Download</button>
            <button class="btn btn-ghost btn-sm" style="color: var(--danger, #dc3545);" onclick="NextGenDashboard.deleteFile('${f.id}')">Delete</button>
          </td>
        </tr>
      `).join('');

      if (paginationEl) {
        const totalPages = Math.ceil(data.total / filesLimit) || 1;
        paginationEl.style.display = totalPages > 1 ? 'flex' : 'none';
        paginationEl.innerHTML = `
          <button class="btn btn-ghost btn-sm" ${currentFilesPage <= 1 ? 'disabled' : ''} onclick="NextGenDashboard.loadUserFiles(${currentFilesPage - 1})">← Previous</button>
          <span style="font-size: 13px; font-weight: 600; align-self: center;">Page ${currentFilesPage} of ${totalPages}</span>
          <button class="btn btn-ghost btn-sm" ${currentFilesPage >= totalPages ? 'disabled' : ''} onclick="NextGenDashboard.loadUserFiles(${currentFilesPage + 1})">Next →</button>
        `;
      }

    } catch (err) {
      tableBody.innerHTML = `<tr><td colspan="4" style="padding: 24px; text-align: center; color: var(--danger);">Failed to load files: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  async function deleteFile(fileId) {
    if (!confirm('Are you sure you want to delete this file? This action cannot be undone.')) return;
    try {
      await fetchDashboardAPI(`/dashboard/files/${fileId}`, { method: 'DELETE' });
      if (window.Toast) window.Toast.show({ message: 'File deleted successfully', type: 'info' });
      loadUserFiles(currentFilesPage);
    } catch (err) {
      alert('Failed to delete file: ' + err.message);
    }
  }

  // 3. HISTORY PAGE
  let currentHistoryPage = 1;
  const historyLimit = 10;

  async function loadUserHistory(page = 1) {
    const tableBody = document.querySelector('#history-table-body');
    const paginationEl = document.querySelector('#history-pagination');
    if (!tableBody) return;

    tableBody.innerHTML = `<tr><td colspan="5" style="padding: 24px; text-align: center; color: var(--text-muted);">Loading processing history...</td></tr>`;

    try {
      const data = await fetchDashboardAPI(`/dashboard/history?page=${page}&limit=${historyLimit}`);
      currentHistoryPage = data.page;

      if (!data.history || data.history.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="5" style="padding: 24px; text-align: center; color: var(--text-muted);">No conversion history recorded yet.</td></tr>`;
        if (paginationEl) paginationEl.style.display = 'none';
        return;
      }

      tableBody.innerHTML = data.history.map(j => `
        <tr style="border-bottom: 1px solid var(--border);">
          <td style="padding: 12px; font-family: monospace; font-weight: 700;">#TK-${j.job_id.substring(0, 6).toUpperCase()}</td>
          <td style="padding: 12px; font-weight: 600;">${escapeHtml(j.tool_name)}</td>
          <td style="padding: 12px;">
            <span style="color: ${j.status === 'completed' ? 'var(--success)' : j.status === 'failed' ? 'var(--danger)' : 'var(--primary)'}; font-weight: 700; font-size: 13px;">
              ${j.status.toUpperCase()}
            </span>
            ${j.error_message ? `<div style="font-size: 11px; color: var(--danger); margin-top: 2px;">${escapeHtml(j.error_message)}</div>` : ''}
          </td>
          <td style="padding: 12px; color: var(--text-muted);">${formatDate(j.created_at)}</td>
          <td style="padding: 12px; text-align: right;">
            ${j.download_url ? `<button class="btn btn-outline btn-sm" onclick="NextGenDashboard.downloadFile('${j.result_file_id}', 'result.pdf')">Download</button>` : '—'}
          </td>
        </tr>
      `).join('');

      if (paginationEl) {
        const totalPages = Math.ceil(data.total / historyLimit) || 1;
        paginationEl.style.display = totalPages > 1 ? 'flex' : 'none';
        paginationEl.innerHTML = `
          <button class="btn btn-ghost btn-sm" ${currentHistoryPage <= 1 ? 'disabled' : ''} onclick="NextGenDashboard.loadUserHistory(${currentHistoryPage - 1})">← Previous</button>
          <span style="font-size: 13px; font-weight: 600; align-self: center;">Page ${currentHistoryPage} of ${totalPages}</span>
          <button class="btn btn-ghost btn-sm" ${currentHistoryPage >= totalPages ? 'disabled' : ''} onclick="NextGenDashboard.loadUserHistory(${currentHistoryPage + 1})">Next →</button>
        `;
      }

    } catch (err) {
      tableBody.innerHTML = `<tr><td colspan="5" style="padding: 24px; text-align: center; color: var(--danger);">Failed to load history: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  // 4. USAGE PAGE
  async function initUsagePage() {
    const container = document.querySelector('.dashboard-content');
    if (!container) return;

    try {
      const data = await fetchDashboardAPI('/dashboard/usage');

      const planVal = document.querySelector('#usage-plan-tier');
      if (planVal) planVal.textContent = (data.plan || 'FREE').toUpperCase();

      const opsVal = document.querySelector('#usage-today-ops');
      if (opsVal) opsVal.textContent = `${data.today_operations} / ${data.daily_limit} tasks (${data.remaining_today} remaining)`;

      const bytesToday = document.querySelector('#usage-bytes-today');
      if (bytesToday) bytesToday.textContent = formatBytes(data.bytes_processed_today || 0);

      const totalOps = document.querySelector('#usage-total-ops-all-time');
      if (totalOps) totalOps.textContent = data.total_operations_all_time || 0;

      const totalBytes = document.querySelector('#usage-total-bytes-all-time');
      if (totalBytes) totalBytes.textContent = formatBytes(data.total_bytes_all_time || 0);

      const successVal = document.querySelector('#usage-success-jobs');
      if (successVal) successVal.textContent = data.successful_jobs || 0;

      const failedVal = document.querySelector('#usage-failed-jobs');
      if (failedVal) failedVal.textContent = data.failed_jobs || 0;

    } catch (err) {
      console.error('[Dashboard] Usage load error:', err);
    }
  }

  // 5. SECURE FILE DOWNLOAD HELPER
  async function downloadFile(fileId, filename = 'document.pdf') {
    if (!fileId) return;
    try {
      const token = await getAuthToken();
      const baseUrl = (window.NEXTGEN_API_BASE || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
      const url = `${baseUrl}/files/${fileId}`;

      const res = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!res.ok) {
        if (res.status === 404) throw new Error('File has expired or was removed.');
        if (res.status === 403) throw new Error('Access denied: You do not own this file.');
        throw new Error(`Download failed (${res.status})`);
      }

      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const downloadName = match?.[1] || filename;

      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = downloadName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (err) {
      alert('Download error: ' + err.message);
    }
  }

  // Global Exports
  window.NextGenDashboard = {
    initOverviewPage,
    loadUserFiles,
    deleteFile,
    loadUserHistory,
    initUsagePage,
    downloadFile
  };
})();
