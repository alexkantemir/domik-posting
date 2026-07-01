function submitReject() {
  const modal = document.getElementById('rejectModal');
  if (modal) bootstrap.Modal.getInstance(modal).hide();
  const inp = document.createElement('input');
  inp.type = 'hidden'; inp.name = 'action'; inp.value = 'reject_all';
  const form = document.getElementById('approveForm');
  form.appendChild(inp);
  form.submit();
}

const PLATFORM_LIMITS = {
  telegram_channel: 4096,
  telegram_group: 4096,
  vk_group: 4096,
};
const DEFAULT_LIMIT = 4096;

function getLimit(postId) {
  const card = document.getElementById('card-' + postId);
  if (!card) return DEFAULT_LIMIT;
  return PLATFORM_LIMITS[card.dataset.platform] || DEFAULT_LIMIT;
}

function updateCount(id, text) {
  const limit = getLimit(id);
  const len = text.length;
  const pct = len / limit;
  const el = document.getElementById('cc-' + id);
  if (!el) return;
  el.textContent = len + ' / ' + limit + ' симв.';
  if (pct >= 0.95) {
    el.className = 'char-count text-danger fw-semibold';
  } else if (pct >= 0.80) {
    el.className = 'char-count text-warning fw-semibold';
  } else {
    el.className = 'char-count text-muted';
  }
}

function toggleCard(id, enabled) {
  const ta = document.getElementById('ta-' + id);
  const card = document.getElementById('card-' + id);
  if (ta) ta.disabled = !enabled;
  if (card) card.style.opacity = enabled ? '1' : '0.4';
}

function toggleSchedule(show) {
  const block = document.getElementById('schedule_block');
  if (!block) return;
  block.style.display = show ? 'block' : 'none';
  if (show) {
    const d = new Date();
    d.setHours(d.getHours() + 4);
    const inp = document.getElementById('scheduled_at');
    if (inp) inp.value = d.toISOString().slice(0, 16);
  }
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
        btn.classList.add('btn-success'); btn.classList.remove('btn-outline-secondary');
        setTimeout(function () {
          btn.innerHTML = orig;
          btn.classList.remove('btn-success'); btn.classList.add('btn-outline-secondary');
        }, 2000);
      } else {
        btn.innerHTML = orig;
      }
    })
    .catch(function () { if (btn) { btn.disabled = false; btn.innerHTML = orig; } });
}

function copyPostText(id) {
  const ta = document.getElementById('ta-' + id);
  const pub = document.querySelector('#card-' + id + ' .p-3');
  const text = ta ? ta.value : (pub ? pub.textContent.trim() : '');
  if (!text) return;
  navigator.clipboard.writeText(text).then(function () {
    const btn = document.getElementById('copy-' + id);
    if (!btn) return;
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-check2"></i>';
    btn.classList.add('btn-success'); btn.classList.remove('btn-outline-secondary');
    setTimeout(function () {
      btn.innerHTML = orig;
      btn.classList.remove('btn-success'); btn.classList.add('btn-outline-secondary');
    }, 1500);
  });
}

(function () {
  document.querySelectorAll('.platform-check').forEach(function (chk) {
    chk.addEventListener('change', function () { toggleCard(this.dataset.postId, this.checked); });
  });

  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { copyPostText(this.dataset.postId); });
  });

  document.querySelectorAll('.post-textarea').forEach(function (ta) {
    ta.addEventListener('input', function () { updateCount(this.dataset.postId, this.value); });
    updateCount(ta.dataset.postId, ta.value);
  });

  document.querySelectorAll('.save-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { savePost(this.dataset.postId); });
  });

  const nowRadio = document.getElementById('now_radio');
  const laterRadio = document.getElementById('later_radio');
  if (nowRadio) nowRadio.addEventListener('change', function () { toggleSchedule(false); });
  if (laterRadio) laterRadio.addEventListener('change', function () { toggleSchedule(true); });

  const confirmBtn = document.getElementById('confirmRejectBtn');
  if (confirmBtn) confirmBtn.addEventListener('click', submitReject);

  const approveForm = document.getElementById('approveForm');
  if (approveForm) {
    approveForm.addEventListener('submit', function (e) {
      const btn = document.getElementById('approveBtn');
      if (e.submitter && e.submitter.value === 'approve' && btn) {
        if (btn.dataset.submitting) { e.preventDefault(); return; }
        btn.dataset.submitting = '1';
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Публикуем...';
      }
    });
  }
}());
