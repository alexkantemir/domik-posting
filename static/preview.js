function copyPostText(id) {
  const ta = document.getElementById('ta-' + id);
  const el = document.getElementById('text-' + id);
  const text = ta ? ta.value.trim() : (el ? el.textContent.trim() : '');
  if (!text) return;
  navigator.clipboard.writeText(text).then(function () {
    const btn = document.getElementById('copy-' + id);
    if (!btn) return;
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-check2"></i>';
    btn.classList.add('btn-success');
    btn.classList.remove('btn-outline-secondary');
    setTimeout(function () {
      btn.innerHTML = orig;
      btn.classList.remove('btn-success');
      btn.classList.add('btn-outline-secondary');
    }, 1500);
  });
}

function previewUpdateCount(id, text) {
  const el = document.getElementById('cc-prev-' + id);
  if (el) el.textContent = text.length + ' симв.';
}

function savePost(id) {
  const ta = document.getElementById('ta-' + id);
  if (!ta) return;
  const btn = document.getElementById('save-' + id);
  const orig = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>'; }
  const fd = new FormData();
  fd.append('text', ta.value);
  fd.append('csrf_token', CSRF_TOKEN);
  fetch('/posts/' + id + '/save', { method: 'POST', body: fd })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!btn) return;
      btn.disabled = false;
      if (data.ok) {
        btn.innerHTML = '<i class="bi bi-check2"></i> Сохранено';
        btn.classList.add('btn-success'); btn.classList.remove('btn-outline-primary');
        setTimeout(function () {
          btn.innerHTML = orig;
          btn.classList.remove('btn-success'); btn.classList.add('btn-outline-primary');
        }, 2000);
      } else {
        btn.innerHTML = orig;
      }
    })
    .catch(function () { if (btn) { btn.disabled = false; btn.innerHTML = orig; } });
}

(function () {
  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { copyPostText(this.dataset.postId); });
  });

  document.querySelectorAll('.post-textarea').forEach(function (ta) {
    ta.addEventListener('input', function () { previewUpdateCount(this.dataset.postId, this.value); });
  });

  document.querySelectorAll('.save-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { savePost(this.dataset.postId); });
  });
}());
