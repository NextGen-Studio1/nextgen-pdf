const NEXTGEN_API_BASE = (window.NEXTGEN_API_BASE || 'http://127.0.0.1:8000/api').replace(/\/$/, '');

document.addEventListener('DOMContentLoaded', () => {
  const tool = document.body.dataset.tool;
  if (!tool) return;

  const input = document.querySelector('#files');
  const list = document.querySelector('#list');
  const drop = document.querySelector('#drop');
  const processBtn = document.querySelector('#process');
  const result = document.querySelector('#result');
  const resultText = document.querySelector('#resultText');
  const downloadBtn = document.querySelector('#download');
  const againBtn = document.querySelector('#again');
  let files = [];
  let resultBlob = null;
  let resultName = 'nextgen-result';
  let draggedIndex = null;

  if (!input || !list || !drop || !processBtn) return;

  const maxFiles = tool === 'merge' || tool === 'images-to-pdf' ? 20 : 1;
  const maxFileBytes = 25 * 1024 * 1024;

  function isAllowedFile(file) {
    const name = (file.name || '').toLowerCase();
    const type = (file.type || '').toLowerCase();
    if (tool === 'images-to-pdf') {
      return type.startsWith('image/') || /\.(jpg|jpeg|png|webp)$/i.test(name);
    }
    return type === 'application/pdf' || type === 'application/octet-stream' || type === 'application/x-pdf' || name.endsWith('.pdf');
  }

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes)) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }

  function render() {
    list.innerHTML = files.map((file, index) => `
      <div class="file-row" draggable="${maxFiles > 1}" data-index="${index}">
        ${maxFiles > 1 ? '<span class="drag-handle" title="Drag to reorder">⋮⋮</span>' : ''}
        <span class="tool-icon">▤</span>
        <div class="file-meta"><b>${escapeHtml(file.name)}</b><br><small>${formatBytes(file.size)}</small></div>
        ${maxFiles > 1 ? `<button class="move" type="button" data-up="${index}" ${index === 0 ? 'disabled' : ''}>↑</button><button class="move" type="button" data-down="${index}" ${index === files.length - 1 ? 'disabled' : ''}>↓</button>` : ''}
        <button class="remove" type="button" data-remove="${index}" aria-label="Remove file">×</button>
      </div>`).join('');

    list.querySelectorAll('[data-remove]').forEach(btn => btn.addEventListener('click', () => {
      files.splice(Number(btn.dataset.remove), 1); render();
    }));
    list.querySelectorAll('[data-up]').forEach(btn => btn.addEventListener('click', () => moveFile(Number(btn.dataset.up), -1)));
    list.querySelectorAll('[data-down]').forEach(btn => btn.addEventListener('click', () => moveFile(Number(btn.dataset.down), 1)));

    list.querySelectorAll('.file-row[draggable="true"]').forEach(row => {
      const idx = Number(row.dataset.index);
      row.addEventListener('dragstart', () => { draggedIndex = idx; });
      row.addEventListener('dragover', e => e.preventDefault());
      row.addEventListener('drop', e => {
        e.preventDefault();
        if (draggedIndex === null || draggedIndex === idx) return;
        const [item] = files.splice(draggedIndex, 1);
        files.splice(idx, 0, item);
        draggedIndex = null;
        render();
      });
    });
  }

  function moveFile(index, direction) {
    const next = index + direction;
    if (next < 0 || next >= files.length) return;
    [files[index], files[next]] = [files[next], files[index]];
    render();
  }

  function setFiles(selected) {
    const incoming = Array.from(selected || []);
    if (!incoming.length) return;
    const invalid = incoming.find(file => !isAllowedFile(file) || file.size > maxFileBytes);
    if (invalid) {
      showError(`${invalid.name}: unsupported file type or file is larger than 25 MB.`);
      return;
    }
    if (files.length + incoming.length > maxFiles) {
      showError(`You can select up to ${maxFiles} file${maxFiles === 1 ? '' : 's'} for this tool.`);
      return;
    }
    hideError();
    files = [...files, ...incoming];
    render();
  }

  input.addEventListener('change', e => { setFiles(e.target.files); input.value = ''; });
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('is-dragging'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('is-dragging'));
  drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('is-dragging'); setFiles(e.dataTransfer.files); });

  document.querySelectorAll('.options').forEach(group => {
    group.querySelectorAll('.option').forEach(card => card.addEventListener('click', () => {
      group.querySelectorAll('.option').forEach(x => x.classList.remove('active'));
      card.classList.add('active');
      const rangeControl = document.querySelector('#page-ranges-wrap');
      if (rangeControl) rangeControl.style.display = card.dataset.value === 'ranges' ? 'grid' : 'none';
    }));
  });

  const firstOptions = document.querySelector('.options');
  if (tool === 'split') {
    const wrap = document.createElement('div');
    wrap.id = 'page-ranges-wrap';
    wrap.className = 'split-range-control';
    wrap.style.display = 'none';
    wrap.innerHTML = `<label for="page-ranges"><b>Pages / ranges</b><small>Examples: 1-3,5,7-9 or 2,4.</small></label><input id="page-ranges" type="text" placeholder="1-3,5,7-9" autocomplete="off">`;
    firstOptions?.insertAdjacentElement('afterend', wrap);
  }

  if (tool === 'pdf-to-images') {
    const wrap = document.createElement('div');
    wrap.id = 'image-page-ranges-wrap';
    wrap.className = 'split-range-control';
    wrap.innerHTML = `<label for="image-page-ranges"><b>Pages / ranges (optional)</b><small>Leave empty to convert all pages. Examples: 1-3,5.</small></label><input id="image-page-ranges" type="text" placeholder="All pages" autocomplete="off">`;
    firstOptions?.insertAdjacentElement('afterend', wrap);
  }

  function selectedValue(groupSelector, fallback) {
    const container = document.querySelector(groupSelector) || document.querySelector('.options');
    return container?.querySelector('.option.active')?.dataset.value || fallback;
  }

  async function process() {
    if (!files.length) return showError('Please choose a file first.');
    if (tool === 'merge' && files.length < 2) return showError('Choose at least two PDF files to merge.');
    if (tool === 'images-to-pdf' && files.length < 1) return showError('Choose at least one image.');
    if (tool === 'split' && selectedValue('.options', 'every') === 'ranges' && !document.querySelector('#page-ranges')?.value.trim()) return showError('Enter at least one page or page range.');

    processBtn.disabled = true;
    processBtn.textContent = 'Processing…';
    hideError();
    try {
      const form = new FormData();
      if (tool === 'merge' || tool === 'images-to-pdf') files.forEach(file => form.append('files', file, file.name));
      else form.append('file', files[0], files[0].name);

      if (tool === 'compress') form.append('level', selectedValue('.options', 'balanced'));
      if (tool === 'images-to-pdf') {
        form.append('layout', selectedValue('[data-group="layout"]', 'portrait'));
        form.append('fit', selectedValue('[data-group="fit"]', 'fit'));
      }
      if (tool === 'split') {
        form.append('mode', selectedValue('.options', 'every'));
        form.append('ranges', document.querySelector('#page-ranges')?.value.trim() || '');
      }
      if (tool === 'pdf-to-images') {
        form.append('format', selectedValue('.options', 'jpg'));
        form.append('ranges', document.querySelector('#image-page-ranges')?.value.trim() || '');
      }

      const endpoint = tool === 'images-to-pdf' ? 'images-to-pdf' : tool === 'pdf-to-images' ? 'pdf-to-images' : tool;
      const response = await fetch(`${NEXTGEN_API_BASE}/${endpoint}`, { method: 'POST', body: form });
      if (!response.ok) {
        let message = `Processing failed (${response.status}).`;
        try { const data = await response.json(); message = data.detail || message; } catch {}
        throw new Error(message);
      }

      resultBlob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      resultName = match?.[1] || 'nextgen-result';

      if (!/\.[a-z0-9]+$/i.test(resultName)) {
        if (resultBlob.type === 'application/zip') resultName += '.zip';
        else if (resultBlob.type === 'application/pdf') resultName += '.pdf';
        else if (resultBlob.type === 'image/png') resultName += '.png';
        else if (resultBlob.type === 'image/jpeg') resultName += '.jpg';
      }

      const originalBytes = Number(response.headers.get('X-Original-Bytes'));
      const outputBytes = Number(response.headers.get('X-Output-Bytes'));
      const reduction = originalBytes && outputBytes && outputBytes < originalBytes ? ` · ${Math.max(0, Math.round((1 - outputBytes / originalBytes) * 100))}% smaller` : '';

      processBtn.style.display = 'none';
      result.style.display = 'block';
      const typeLabel = resultBlob.type === 'application/zip' ? 'ZIP archive' : resultBlob.type.split('/').pop()?.toUpperCase();
      resultText.textContent = `${resultName} · ${formatBytes(resultBlob.size)} · ${typeLabel || 'file'}${reduction}`;
    } catch (error) {
      showError(error.message || 'Something went wrong. Please try again.');
      processBtn.disabled = false;
      processBtn.textContent = 'Process files →';
    }
  }

  function showError(message) {
    let box = document.querySelector('.tool-error');
    if (!box) { box = document.createElement('div'); box.className = 'tool-error'; processBtn.insertAdjacentElement('beforebegin', box); }
    box.textContent = message; box.style.display = 'block';
  }
  function hideError() { const box = document.querySelector('.tool-error'); if (box) box.style.display = 'none'; }

  processBtn.addEventListener('click', process);
  downloadBtn?.addEventListener('click', () => {
    if (!resultBlob) return;
    const url = URL.createObjectURL(resultBlob);
    const a = document.createElement('a'); a.href = url; a.download = resultName;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  againBtn?.addEventListener('click', () => location.reload());
});
