document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-demo-drop]').forEach(zone => {
    const input = zone.querySelector('input');
    input?.addEventListener('change', () => {
      if (input.files[0]) handleHomepageUpload(zone, input.files[0]);
    });
    ['dragover', 'drop'].forEach(evt => zone.addEventListener(evt, e => {
      e.preventDefault();
      if (evt === 'drop' && e.dataTransfer.files[0]) {
        handleHomepageUpload(zone, e.dataTransfer.files[0]);
      }
    }));
  });
});

function handleHomepageUpload(zone, file) {
  const name = file.name || 'Document';
  const isImage = /\.(jpg|jpeg|png|webp)$/i.test(name) || file.type.startsWith('image/');
  const targetTool = isImage ? 'pages/jpg-to-pdf.html' : 'pages/compress.html';

  zone.querySelector('h3').textContent = name;
  zone.querySelector('p').innerHTML = `File loaded! <a href="${targetTool}" style="color:var(--accent);font-weight:700;text-decoration:underline">Proceed to tool →</a>`;
  const small = zone.querySelector('small');
  if (small) {
    small.textContent = `File ready. Click to process in ${isImage ? 'JPG → PDF' : 'Compress PDF'}.`;
  }
}
