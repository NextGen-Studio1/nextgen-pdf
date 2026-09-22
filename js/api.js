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
    if (tool === 'word-to-pdf') {
      return name.endsWith('.docx') || name.endsWith('.doc') || type.includes('wordprocessingml');
    }
    if (tool === 'excel-to-pdf') {
      return name.endsWith('.xlsx') || name.endsWith('.xls') || type.includes('spreadsheetml');
    }
    if (tool === 'pptx-to-pdf') {
      return name.endsWith('.pptx') || name.endsWith('.ppt') || type.includes('presentationml');
    }
    if (tool === 'html-to-pdf') {
      return name.endsWith('.html') || name.endsWith('.htm') || type.includes('html');
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
    if (tool === 'organize' && !document.querySelector('#organize-order')?.value.trim()) return showError('Enter target page order e.g. 3, 1, 2.');
    if (tool === 'delete-pages' && !document.querySelector('#delete-pages-input')?.value.trim()) return showError('Enter pages to delete e.g. 2, 4-6.');
    if (tool === 'extract-pages' && !document.querySelector('#extract-pages-input')?.value.trim()) return showError('Enter pages to extract e.g. 1-3, 5.');
    if (tool === 'protect-pdf' && !document.querySelector('#protect-password')?.value.trim()) return showError('Enter a password to protect your PDF.');
    if (tool === 'redact-pdf' && !document.querySelector('#redact-text')?.value.trim()) return showError('Enter text or word to redact.');
    if (tool === 'edit-pdf' && !document.querySelector('#edit-text')?.value.trim()) return showError('Enter text to add to the PDF.');
    if (tool === 'add-image' && !document.querySelector('#image-file')?.files?.[0]) return showError('Choose an image file to stamp onto the PDF.');
    if (tool === 'add-links' && !document.querySelector('#link-url')?.value.trim()) return showError('Enter a URL to add as a link e.g. https://example.com.');
    if (tool === 'highlight-pdf' && !document.querySelector('#highlight-text')?.value.trim()) return showError('Enter text or phrase to highlight.');
    if (tool === 'annotate-pdf' && !document.querySelector('#annotate-comment')?.value.trim()) return showError('Enter comment or note text.');

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
      if (tool === 'watermark') {
        const textVal = document.querySelector('#watermark-text')?.value.trim() || 'CONFIDENTIAL';
        form.append('text', textVal);
        form.append('position', selectedValue('[data-group="position"]', 'diagonal'));
        form.append('color', selectedValue('[data-group="color"]', 'red'));
        form.append('opacity', selectedValue('[data-group="opacity"]', '0.35'));
        form.append('fontsize', selectedValue('[data-group="fontsize"]', '48'));
      }
      if (tool === 'organize') {
        form.append('order', document.querySelector('#organize-order')?.value.trim() || '');
      }
      if (tool === 'delete-pages') {
        form.append('pages', document.querySelector('#delete-pages-input')?.value.trim() || '');
      }
      if (tool === 'extract-pages') {
        form.append('pages', document.querySelector('#extract-pages-input')?.value.trim() || '');
      }
      if (tool === 'rotate') {
        form.append('angle', selectedValue('[data-group="angle"]', '90'));
        form.append('pages', document.querySelector('#rotate-pages-input')?.value.trim() || 'all');
      }
      if (tool === 'page-numbers') {
        form.append('position', selectedValue('[data-group="position"]', 'bottom-center'));
        form.append('format', selectedValue('[data-group="format"]', 'Page {page} of {total}'));
        form.append('start', document.querySelector('#pagenum-start')?.value.trim() || '1');
        form.append('fontsize', selectedValue('[data-group="fontsize"]', '10'));
        form.append('margin', selectedValue('[data-group="margin"]', '36'));
        form.append('pages', document.querySelector('#pagenum-pages')?.value.trim() || 'all');
      }
      if (tool === 'crop') {
        form.append('margin', selectedValue('[data-group="margin"]', '36'));
        form.append('pages', document.querySelector('#crop-pages')?.value.trim() || 'all');
      }
      if (tool === 'protect-pdf') {
        form.append('password', document.querySelector('#protect-password')?.value.trim() || '');
      }
      if (tool === 'unlock-pdf') {
        form.append('password', document.querySelector('#unlock-password')?.value.trim() || '');
      }
      if (tool === 'encrypt-pdf') {
        form.append('user_password', document.querySelector('#encrypt-user-password')?.value.trim() || '');
        form.append('owner_password', document.querySelector('#encrypt-owner-password')?.value.trim() || '');
        form.append('allow_print', document.querySelector('#encrypt-allow-print')?.checked ? 'true' : 'false');
        form.append('allow_copy', document.querySelector('#encrypt-allow-copy')?.checked ? 'true' : 'false');
        form.append('allow_edit', document.querySelector('#encrypt-allow-edit')?.checked ? 'true' : 'false');
      }
      if (tool === 'redact-pdf') {
        form.append('text', document.querySelector('#redact-text')?.value.trim() || '');
        form.append('pages', document.querySelector('#redact-pages')?.value.trim() || 'all');
      }
      if (tool === 'edit-pdf') {
        form.append('text', document.querySelector('#edit-text')?.value.trim() || '');
        form.append('fontsize', selectedValue('[data-group="fontsize"]', '14'));
        form.append('color', selectedValue('[data-group="color"]', 'black'));
        form.append('position', selectedValue('[data-group="position"]', 'top-left'));
        form.append('pages', document.querySelector('#edit-pages')?.value.trim() || 'all');
      }
      if (tool === 'add-image') {
        const imgInput = document.querySelector('#image-file');
        if (imgInput?.files?.[0]) form.append('image_file', imgInput.files[0], imgInput.files[0].name);
        form.append('position', selectedValue('[data-group="position"]', 'bottom-right'));
        form.append('width', document.querySelector('#image-width')?.value.trim() || '120');
        form.append('height', document.querySelector('#image-height')?.value.trim() || '120');
        form.append('pages', document.querySelector('#image-pages')?.value.trim() || 'all');
      }
      if (tool === 'add-links') {
        form.append('url', document.querySelector('#link-url')?.value.trim() || '');
        form.append('target_text', document.querySelector('#link-text')?.value.trim() || '');
        form.append('pages', document.querySelector('#link-pages')?.value.trim() || 'all');
      }
      if (tool === 'highlight-pdf') {
        form.append('text', document.querySelector('#highlight-text')?.value.trim() || '');
        form.append('color', selectedValue('[data-group="color"]', 'yellow'));
        form.append('pages', document.querySelector('#highlight-pages')?.value.trim() || 'all');
      }
      if (tool === 'annotate-pdf') {
        form.append('comment', document.querySelector('#annotate-comment')?.value.trim() || '');
        form.append('position', selectedValue('[data-group="position"]', 'top-left'));
        form.append('pages', document.querySelector('#annotate-pages')?.value.trim() || 'all');
      }
      if (tool === 'resize-pages') {
        form.append('paper_size', selectedValue('[data-group="size"]', 'a4'));
        form.append('orientation', selectedValue('[data-group="orientation"]', 'portrait'));
        form.append('pages', document.querySelector('#resize-pages-input')?.value.trim() || 'all');
      }
      if (tool === 'ocr-pdf') {
        form.append('language', selectedValue('[data-group="lang"]', 'eng'));
      }
      if (tool === 'ai-summarize') {
        form.append('summary_type', selectedValue('[data-group="type"]', 'executive'));
      }
      if (tool === 'chat-pdf') {
        form.append('question', document.querySelector('#chat-question')?.value.trim() || '');
      }
      if (tool === 'translate-pdf') {
        form.append('target_lang', selectedValue('[data-group="lang"]', 'es'));
      }
      if (tool === 'compare-pdfs') {
        const file2Input = document.querySelector('#file2');
        if (file2Input?.files?.[0]) form.append('file2', file2Input.files[0], file2Input.files[0].name);
      }
      if (tool === 'overlay-pdf') {
        const overlayInput = document.querySelector('#overlay-file');
        if (overlayInput?.files?.[0]) form.append('overlay_file', overlayInput.files[0], overlayInput.files[0].name);
      }
      if (tool === 'pdf-bookmarks') {
        form.append('action', selectedValue('[data-group="action"]', 'view'));
        form.append('toc_json', document.querySelector('#toc-json')?.value.trim() || '');
      }
      if (tool === 'metadata-editor') {
        form.append('title', document.querySelector('#meta-title')?.value.trim() || '');
        form.append('author', document.querySelector('#meta-author')?.value.trim() || '');
        form.append('subject', document.querySelector('#meta-subject')?.value.trim() || '');
        form.append('keywords', document.querySelector('#meta-keywords')?.value.trim() || '');
      }

      const endpoint = tool === 'images-to-pdf' ? 'images-to-pdf' : tool === 'pdf-to-images' ? 'pdf-to-images' : tool;
      const actionTitle = tool.replace(/-/g, ' ').toUpperCase();
      
      updateProgress(0, `Uploading document...`, `0 KB transferred`);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${NEXTGEN_API_BASE}/${endpoint}`, true);
      xhr.responseType = 'blob';

      // Attach Firebase ID token if user is signed in
      if (window.nextgenFirebase?.auth?.currentUser) {
        try {
          const idToken = await window.nextgenFirebase.auth.currentUser.getIdToken();
          xhr.setRequestHeader('Authorization', `Bearer ${idToken}`);
        } catch (tokenErr) {
          console.warn('[API] Failed to retrieve Firebase ID token:', tokenErr);
        }
      }

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && e.total > 0) {
          const percent = Math.round((e.loaded / e.total) * 90);
          const loadedStr = formatBytes(e.loaded);
          const totalStr = formatBytes(e.total);
          updateProgress(percent, `Uploading file (${percent}%)...`, `${loadedStr} of ${totalStr} transferred`);
        }
      };

      xhr.upload.onloadend = () => {
        updateProgress(95, `Processing & converting ${actionTitle}...`, `Executing transformations in-memory...`);
      };

      xhr.onload = async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          updateProgress(100, `Completed!`, `Processing completed successfully`, true);
          
          const blob = xhr.response;
          const contentType = xhr.getResponseHeader('Content-Type') || '';

          if (contentType.includes('application/json')) {
            const text = await blob.text();
            const json = JSON.parse(text);
            processBtn.style.display = 'none';
            result.style.display = 'block';
            if (downloadBtn) downloadBtn.style.display = 'none';
            
            let html = '';
            if (tool === 'ai-summarize') {
              html = `
                <div style="background: var(--bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-top: 15px;">
                  <h4 style="margin: 0 0 10px 0; color: var(--primary);">Summary Overview</h4>
                  <p style="margin-bottom: 15px; font-size: 0.95rem;">${json.executive_summary}</p>
                  <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 15px;">
                    <span class="badge" style="padding: 4px 10px; background: rgba(0,0,0,0.05); border-radius: 6px;">📖 ${json.word_count} words</span>
                    <span class="badge" style="padding: 4px 10px; background: rgba(0,0,0,0.05); border-radius: 6px;">⏱ ${json.reading_time_min} min read</span>
                    <span class="badge" style="padding: 4px 10px; background: rgba(0,0,0,0.05); border-radius: 6px;">📑 ${json.page_count} pages</span>
                  </div>
                  <h5 style="margin: 15px 0 8px 0;">Key Topics</h5>
                  <p style="margin: 0 0 15px 0;">${json.topics.join(' · ')}</p>
                  <h5 style="margin: 15px 0 8px 0;">Key Takeaways</h5>
                  <ul style="padding-left: 20px; margin: 0;">${json.key_takeaways.map(t => `<li style="margin-bottom: 6px;">${t}</li>`).join('')}</ul>
                </div>
              `;
            } else if (tool === 'chat-pdf') {
              html = `
                <div style="background: var(--bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-top: 15px;">
                  <h4 style="margin: 0 0 10px 0; color: var(--primary);">Q: ${json.question}</h4>
                  <p style="margin-bottom: 15px; font-size: 0.95rem;"><b>Answer:</b> ${json.answer}</p>
                  <h5 style="margin: 15px 0 8px 0;">Page Citations</h5>
                  <div style="display: flex; flex-direction: column; gap: 8px;">
                    ${json.citations.map(c => `<div style="padding: 8px 12px; background: rgba(0,0,0,0.03); border-radius: 6px; font-size: 0.88rem;"><b>Page ${c.page}:</b> <i>"${c.snippet}"</i></div>`).join('')}
                  </div>
                </div>
              `;
            } else if (tool === 'pdf-bookmarks') {
              html = `
                <div style="background: var(--bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-top: 15px;">
                  <h4 style="margin: 0 0 10px 0;">Table of Contents / Bookmarks</h4>
                  <pre style="background: #000; color: #0f0; padding: 12px; border-radius: 8px; font-size: 0.85rem; overflow-x: auto;">${JSON.stringify(json.toc, null, 2)}</pre>
                </div>
              `;
            } else {
              html = `<pre style="background: var(--bg); padding: 15px; border-radius: 8px;">${JSON.stringify(json, null, 2)}</pre>`;
            }
            resultText.innerHTML = html;
            return;
          }

          resultBlob = blob;
          const disposition = xhr.getResponseHeader('Content-Disposition') || '';
          const match = disposition.match(/filename="?([^";]+)"?/i);
          resultName = match?.[1] || 'nextgen-result';

          if (!/\.[a-z0-9]+$/i.test(resultName)) {
            if (resultBlob.type === 'application/zip') resultName += '.zip';
            else if (resultBlob.type === 'application/pdf') resultName += '.pdf';
            else if (resultBlob.type === 'image/png') resultName += '.png';
            else if (resultBlob.type === 'image/jpeg') resultName += '.jpg';
          }

          const originalBytes = Number(xhr.getResponseHeader('X-Original-Bytes'));
          const outputBytes = Number(xhr.getResponseHeader('X-Output-Bytes'));
          const reduction = originalBytes && outputBytes && outputBytes < originalBytes ? ` · ${Math.max(0, Math.round((1 - outputBytes / originalBytes) * 100))}% smaller` : '';

          processBtn.style.display = 'none';
          result.style.display = 'block';
          const typeLabel = resultBlob.type === 'application/zip' ? 'ZIP archive' : resultBlob.type.split('/').pop()?.toUpperCase();
          resultText.textContent = `${resultName} · ${formatBytes(resultBlob.size)} · ${typeLabel || 'file'}${reduction}`;
        } else {
          let message = `Processing failed (${xhr.status}).`;
          try {
            const text = await xhr.response.text();
            const data = JSON.parse(text);
            if (data.detail) message = data.detail;
          } catch {}
          const wrapper = document.querySelector('.progress-wrapper');
          if (wrapper) wrapper.style.display = 'none';
          showError(message);
          processBtn.disabled = false;
          processBtn.textContent = 'Process files →';
        }
      };

      xhr.onerror = () => {
        const wrapper = document.querySelector('.progress-wrapper');
        if (wrapper) wrapper.style.display = 'none';
        showError('Network error. Please try again.');
        processBtn.disabled = false;
        processBtn.textContent = 'Process files →';
      };

      xhr.send(form);
    } catch (error) {
      const wrapper = document.querySelector('.progress-wrapper');
      if (wrapper) wrapper.style.display = 'none';
      showError(error.message || 'Something went wrong. Please try again.');
      processBtn.disabled = false;
      processBtn.textContent = 'Process files →';
    }
  }

  function getOrCreateProgressWrapper() {
    let wrapper = document.querySelector('.progress-wrapper');
    if (!wrapper) {
      wrapper = document.createElement('div');
      wrapper.className = 'progress-wrapper';
      wrapper.innerHTML = `
        <div class="progress-header">
          <div class="progress-title">
            <span class="progress-spinner">⏳</span>
            <span class="progress-label-text">Processing document...</span>
          </div>
          <div class="progress-percent">0%</div>
        </div>
        <div class="progress-bar-track">
          <div class="progress-bar-fill"></div>
        </div>
        <div class="progress-status">
          <span class="progress-subtext">Preparing upload...</span>
          <span class="progress-badge">In Progress</span>
        </div>
      `;
      processBtn.insertAdjacentElement('beforebegin', wrapper);
    }
    return wrapper;
  }

  function updateProgress(percent, label, subtext, isCompleted = false) {
    const wrapper = getOrCreateProgressWrapper();
    wrapper.style.display = 'block';
    
    if (isCompleted) {
      wrapper.classList.add('completed');
    } else {
      wrapper.classList.remove('completed');
    }

    const fill = wrapper.querySelector('.progress-bar-fill');
    const percentEl = wrapper.querySelector('.progress-percent');
    const labelEl = wrapper.querySelector('.progress-label-text');
    const subtextEl = wrapper.querySelector('.progress-subtext');
    const spinnerEl = wrapper.querySelector('.progress-spinner');
    const badgeEl = wrapper.querySelector('.progress-badge');

    if (fill) fill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    if (percentEl) percentEl.textContent = `${Math.min(100, Math.max(0, percent))}%`;
    if (labelEl && label) labelEl.textContent = label;
    if (subtextEl && subtext) subtextEl.textContent = subtext;

    if (isCompleted) {
      if (spinnerEl) spinnerEl.textContent = '✓';
      if (badgeEl) {
        badgeEl.className = 'completed-badge';
        badgeEl.textContent = '✓ Completed';
      }
    } else {
      if (spinnerEl) spinnerEl.textContent = '⚡';
      if (badgeEl) {
        badgeEl.className = 'progress-badge';
        badgeEl.textContent = 'In Progress';
      }
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
