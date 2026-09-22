/* NextGen PDF — Unified Reusable Upload System */

class PDFUploader {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.options = {
      multiple: false,
      accept: '.pdf,application/pdf',
      onFilesSelected: null,
      onProcess: null,
      ...options
    };

    this.files = [];
    this.renderDropzone();
  }

  renderDropzone() {
    this.container.innerHTML = `
      <div class="upload-system">
        <div class="upload-dropzone" id="dropzone-${this.container.id}">
          <div class="upload-icon-box">📄</div>
          <h3>Drop your PDF here</h3>
          <p>or click to browse files from your computer</p>
          <button type="button" class="btn btn-primary btn-sm">Select Files</button>
          <input type="file" id="file-input-${this.container.id}" ${this.options.multiple ? 'multiple' : ''} accept="${this.options.accept}" style="display:none">
        </div>
        <div class="upload-file-list" id="file-list-${this.container.id}"></div>
        <div class="progress-card" id="progress-card-${this.container.id}" style="display:none">
          <div class="progress-header-row">
            <span id="progress-status-${this.container.id}">Processing PDF...</span>
            <span id="progress-percent-${this.container.id}">0%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" id="progress-fill-${this.container.id}" style="width: 0%"></div>
          </div>
        </div>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const dropzone = this.container.querySelector('.upload-dropzone');
    const fileInput = this.container.querySelector('input[type="file"]');

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('is-dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('is-dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('is-dragover');
      if (e.dataTransfer.files.length) {
        this.handleFiles(Array.from(e.dataTransfer.files));
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) {
        this.handleFiles(Array.from(e.target.files));
      }
    });
  }

  handleFiles(files) {
    this.files = this.options.multiple ? [...this.files, ...files] : [files[0]];
    this.renderFiles();
    if (typeof this.options.onFilesSelected === 'function') {
      this.options.onFilesSelected(this.files);
    }
  }

  renderFiles() {
    const listEl = this.container.querySelector(`#file-list-${this.container.id}`);
    listEl.innerHTML = this.files.map((file, idx) => `
      <div class="upload-file-item">
        <div class="upload-file-info">
          <span class="upload-file-icon">📄</span>
          <div>
            <div class="upload-file-name">${file.name}</div>
            <div class="upload-file-size">${(file.size / (1024 * 1024)).toFixed(2)} MB</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); window.activeUploader?.removeFile(${idx})">✕</button>
      </div>
    `).join('');
  }

  removeFile(idx) {
    this.files.splice(idx, 1);
    this.renderFiles();
  }

  simulateProgress(onComplete) {
    const progressCard = this.container.querySelector(`#progress-card-${this.container.id}`);
    const fill = this.container.querySelector(`#progress-fill-${this.container.id}`);
    const percentText = this.container.querySelector(`#progress-percent-${this.container.id}`);
    const statusText = this.container.querySelector(`#progress-status-${this.container.id}`);

    progressCard.style.display = 'block';
    let current = 0;

    const interval = setInterval(() => {
      current += Math.floor(Math.random() * 15) + 5;
      if (current >= 100) {
        current = 100;
        clearInterval(interval);
        fill.style.width = '100%';
        percentText.textContent = '100%';
        statusText.textContent = '✓ Ready for download!';
        if (onComplete) onComplete();
      } else {
        fill.style.width = `${current}%`;
        percentText.textContent = `${current}%`;
      }
    }, 150);
  }
}

window.PDFUploader = PDFUploader;
