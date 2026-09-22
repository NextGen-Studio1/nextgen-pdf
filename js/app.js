const root = document.documentElement;
const saved = localStorage.getItem('nextgen-theme');
if (saved) root.dataset.theme = saved;

function updateThemeIcon() {
  const b = document.querySelector('[data-theme-toggle]');
  if (b) b.textContent = root.dataset.theme === 'dark' ? '☀' : '☾';
}

// Master Tools Database for Intent Search Engine
const TOOLS_DB = [
  { id: 'compress', title: 'Compress PDF', desc: 'Reduce file size while keeping clear visual quality.', icon: '↓', path: 'pages/compress.html', tags: ['smaller', 'compress', 'reduce size', 'shrink', 'zip', 'minimize'] },
  { id: 'merge', title: 'Merge PDF', desc: 'Combine multiple PDFs into one file.', icon: '＋', path: 'pages/merge.html', tags: ['join', 'merge', 'combine', 'combine pdfs', 'append', 'attach'] },
  { id: 'split', title: 'Split PDF', desc: 'Separate pages or selected ranges.', icon: '✂', path: 'pages/split.html', tags: ['split', 'divide', 'separate', 'break', 'cut'] },
  { id: 'jpg-to-pdf', title: 'JPG / PNG → PDF', desc: 'Convert images into a clean PDF document.', icon: '▧', path: 'pages/jpg-to-pdf.html', tags: ['jpg to pdf', 'png to pdf', 'image to pdf', 'convert image', 'photos to pdf'] },
  { id: 'pdf-to-jpg', title: 'PDF → JPG / PNG', desc: 'Convert PDF pages into high-res images.', icon: '▤', path: 'pages/pdf-to-jpg.html', tags: ['pdf to jpg', 'pdf to png', 'pdf to image', 'export images', 'page images'] },
  { id: 'pdf-to-word', title: 'PDF → Word', desc: 'Export PDF to editable Microsoft Word .docx.', icon: '📝', path: 'pages/pdf-to-word.html', tags: ['word', 'docx', 'doc', 'change to word', 'convert word'] },

  { id: 'word-to-pdf', title: 'Word → PDF', desc: 'Convert .docx documents to PDF.', icon: '📄', path: 'pages/word-to-pdf.html', tags: ['word to pdf', 'docx to pdf', 'doc to pdf'] },
  { id: 'pdf-to-excel', title: 'PDF → Excel', desc: 'Extract tables & data to .xlsx spreadsheet.', icon: '📗', path: 'pages/pdf-to-excel.html', tags: ['excel', 'xlsx', 'xls', 'spreadsheet', 'tables'] },
  { id: 'add-image', title: 'Add Image / Signature', desc: 'Stamp PNG graphics, logos, and signatures.', icon: '🖼️', path: 'pages/add-image.html', tags: ['sign', 'signature', 'stamp', 'logo', 'image', 'picture'] },
  { id: 'ocr-pdf', title: 'OCR PDF', desc: 'Make scanned image PDFs searchable and selectable.', icon: '🔍', path: 'pages/ocr-pdf.html', tags: ['ocr', 'scan', 'searchable', 'scanned pdf', 'read text'] },
  { id: 'page-numbers', title: 'Page Numbers', desc: 'Add header & footer page numbers.', icon: '#', path: 'pages/page-numbers.html', tags: ['page numbers', 'numbering', 'footer', 'header', 'pagination'] },
  { id: 'unlock-pdf', title: 'Unlock PDF', desc: 'Remove password protection from encrypted PDFs.', icon: '🔓', path: 'pages/unlock-pdf.html', tags: ['unlock', 'remove password', 'decrypt', 'password'] },
  { id: 'protect-pdf', title: 'Protect PDF', desc: 'Add password encryption to lock documents.', icon: '🔐', path: 'pages/protect-pdf.html', tags: ['protect', 'password', 'lock', 'encrypt', 'security'] },
  { id: 'delete-pages', title: 'Delete Pages', desc: 'Remove unwanted pages or ranges.', icon: '🗑', path: 'pages/delete-pages.html', tags: ['delete', 'remove page', 'remove page 5', 'erase page'] },
  { id: 'extract-pages', title: 'Extract Pages', desc: 'Save selected pages into a new PDF.', icon: '⎘', path: 'pages/extract-pages.html', tags: ['extract', 'extract pages 2 to 5', 'save pages'] },
  { id: 'rotate', title: 'Rotate PDF', desc: 'Turn pages 90°, 180°, or 270°.', icon: '↻', path: 'pages/rotate.html', tags: ['rotate', 'turn', 'orientation', 'upside down', 'flip'] },
  { id: 'watermark', title: 'Watermark PDF', desc: 'Stamp security notices & text overlays.', icon: '💧', path: 'pages/watermark.html', tags: ['watermark', 'stamp text', 'confidential', 'overlay text'] },
  { id: 'crop', title: 'Crop PDF', desc: 'Trim margins & page borders.', icon: '⬚', path: 'pages/crop.html', tags: ['crop', 'trim', 'margins', 'cut margins'] },
  { id: 'ai-summarize', title: 'AI PDF Summarizer', desc: 'Executive summaries, key takeaways, and metrics.', icon: '🧠', path: 'pages/ai-summarize.html', tags: ['summarize', 'summary', 'ai summary', 'key points', 'takeaways'] },
  { id: 'chat-pdf', title: 'Chat with PDF', desc: 'Interactive Q&A engine with page citations.', icon: '💬', path: 'pages/chat-pdf.html', tags: ['chat', 'q&a', 'ask questions', 'ai chat', 'citations'] },
  { id: 'translate-pdf', title: 'Translate PDF', desc: 'Translate document text across 10 languages.', icon: '🌐', path: 'pages/translate-pdf.html', tags: ['translate', 'language', 'spanish', 'french', 'german'] },
  { id: 'pdf-to-markdown', title: 'PDF → Markdown', desc: 'Export headings and text to GitHub Markdown .md.', icon: '📑', path: 'pages/pdf-to-markdown.html', tags: ['markdown', 'md', 'github markdown'] },
  { id: 'repair-pdf', title: 'Repair PDF', desc: 'Fix corrupt XREF tables and syntax errors.', icon: '🛠️', path: 'pages/repair-pdf.html', tags: ['repair', 'fix', 'corrupt', 'broken', 'repair pdf'] },
  { id: 'compare-pdfs', title: 'Compare PDFs', desc: 'Side-by-side text and visual diff comparison.', icon: '📊', path: 'pages/compare-pdfs.html', tags: ['compare', 'diff', 'comparison report', 'side by side'] },
  { id: 'flatten-pdf', title: 'Flatten PDF', desc: 'Bake form fields and annotations into page graphics.', icon: '📄', path: 'pages/flatten-pdf.html', tags: ['flatten', 'flatten form', 'bake annotations'] },
  { id: 'deskew-pdf', title: 'Deskew PDF', desc: 'Detect scan tilt angles and straighten crooked pages.', icon: '📐', path: 'pages/deskew-pdf.html', tags: ['deskew', 'straighten', 'tilt', 'crooked scan'] },
  { id: 'extract-images', title: 'Extract Images', desc: 'Export embedded PNG/JPG photos into a ZIP archive.', icon: '🖼️', path: 'pages/extract-images.html', tags: ['extract images', 'rip images', 'save photos', 'zip images'] },
];

document.addEventListener('DOMContentLoaded', () => {
  updateThemeIcon();
  document.querySelector('[data-theme-toggle]')?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('nextgen-theme', root.dataset.theme);
    updateThemeIcon();
  });

  // Mobile menu toggle
  const mobBtn = document.querySelector('[data-mobile-toggle]');
  const navMenu = document.querySelector('.nav nav');
  mobBtn?.addEventListener('click', () => {
    navMenu?.classList.toggle('is-open');
  });

  // Header Mega-Menu Toggle
  const megaToggle = document.querySelector('[data-mega-toggle]');
  const megaMenu = document.querySelector('.tools-mega-menu');
  if (megaToggle && megaMenu) {
    megaToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      megaMenu.classList.toggle('is-active');
    });
    document.addEventListener('click', (e) => {
      if (!megaMenu.contains(e.target) && e.target !== megaToggle) {
        megaMenu.classList.remove('is-active');
      }
    });
  }

  // Intent-Based Natural Language Search Engine
  const searchInput = document.querySelector('.search-input');
  const popup = document.querySelector('.search-results-popup');

  if (searchInput && popup) {
    // Relative path helper (handles root vs pages/ directory)
    const isSubPage = window.location.pathname.includes('/pages/');

    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.trim().toLowerCase();
      if (!query) {
        popup.style.display = 'none';
        popup.innerHTML = '';
        return;
      }

      const matches = TOOLS_DB.filter(tool => {
        if (tool.title.toLowerCase().includes(query)) return true;
        if (tool.desc.toLowerCase().includes(query)) return true;
        return tool.tags.some(tag => tag.toLowerCase().includes(query));
      });

      if (matches.length > 0) {
        popup.innerHTML = matches.slice(0, 6).map(t => {
          const targetPath = isSubPage ? t.path.replace('pages/', '') : t.path;
          return `
            <a href="${targetPath}" class="search-result-item">
              <span class="s-icon">${t.icon}</span>
              <div>
                <h5>${t.title}</h5>
                <p>${t.desc}</p>
              </div>
            </a>
          `;
        }).join('');
        popup.style.display = 'block';
      } else {
        popup.innerHTML = `
          <div style="padding: 16px; text-align: center; color: var(--muted); font-size: 14px;">
            No matching PDF tools found for "${query}". Try "compress", "merge", or "word".
          </div>
        `;
        popup.style.display = 'block';
      }
    });

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !popup.contains(e.target)) {
        popup.style.display = 'none';
      }
    });

    // Tag Click handler
    document.querySelectorAll('.search-tag-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const query = chip.dataset.query || chip.textContent.trim();
        searchInput.value = query;
        searchInput.dispatchEvent(new Event('input'));
        searchInput.focus();
      });
    });
  }

  // FAQ Accordion Toggle
  document.querySelectorAll('.faq-question').forEach(q => {
    q.addEventListener('click', () => {
      const parent = q.closest('.faq-item');
      if (parent) {
        const isOpen = parent.classList.contains('is-open');
        document.querySelectorAll('.faq-item').forEach(item => item.classList.remove('is-open'));
        if (!isOpen) parent.classList.add('is-open');
      }
    });
  });
});
