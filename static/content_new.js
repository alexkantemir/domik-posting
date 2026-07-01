const typeFields = {
  text:       { show: ['field_text'],               hide: ['field_url','field_file','field_caption','hint_audio'] },
  url:        { show: ['field_url'],                hide: ['field_text','field_file','field_caption','hint_audio'] },
  photo:      { show: ['field_file'],               hide: ['field_text','field_url','field_caption','hint_audio'] },
  photo_text: { show: ['field_file','field_caption'], hide: ['field_text','field_url','hint_audio'] },
  video:      { show: ['field_file'],               hide: ['field_text','field_url','field_caption','hint_audio'] },
  audio:      { show: ['field_file','hint_audio'],  hide: ['field_text','field_url','field_caption'] },
};
const fileAccept = {
  photo: 'image/*', photo_text: 'image/*',
  video: 'video/*', audio: 'audio/*',
};
const fileLabels = {
  photo: 'Фотография', photo_text: 'Фотография',
  video: 'Видеофайл', audio: 'Аудиофайл (MP3, OGG, WAV, M4A)',
};

function switchType(val) {
  const cfg = typeFields[val] || typeFields.text;
  cfg.show.forEach(function (id) { const el = document.getElementById(id); if (el) el.style.display = ''; });
  cfg.hide.forEach(function (id) { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
  const fi = document.getElementById('fileInput');
  if (fi) fi.accept = fileAccept[val] || '*/*';
  const fl = document.getElementById('fileLabel');
  if (fl) fl.textContent = fileLabels[val] || 'Файл';
}

function showFormError(msg) {
  const el = document.getElementById('formError');
  const txt = document.getElementById('formErrorText');
  if (txt) txt.textContent = msg;
  if (el) { el.classList.remove('d-none'); el.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
}

(function () {
  document.querySelectorAll('input[name="content_type"]').forEach(function (r) {
    r.addEventListener('change', function () { switchType(r.value); });
  });
  switchType('text');

  const form = document.getElementById('uploadForm');
  if (!form) return;
  form.addEventListener('submit', function (e) {
    document.getElementById('formError').classList.add('d-none');
    const typeEl = document.querySelector('input[name="content_type"]:checked');
    const type = typeEl ? typeEl.value : 'text';
    if (type === 'text') {
      const txtEl = document.querySelector('textarea[name="text"]');
      const txt = txtEl ? txtEl.value.trim() : '';
      if (!txt) { showFormError('Введите текст материала'); e.preventDefault(); return; }
      if (txt.length < 20) { showFormError('Текст слишком короткий (минимум 20 символов)'); e.preventDefault(); return; }
    }
    if (type === 'url') {
      const urlEl = document.querySelector('input[name="url"]');
      const url = urlEl ? urlEl.value.trim() : '';
      if (!url) { showFormError('Введите ссылку'); e.preventDefault(); return; }
      try { new URL(url); } catch (err) { showFormError('Некорректная ссылка'); e.preventDefault(); return; }
    }
    if (['photo','photo_text','video','audio'].includes(type)) {
      const fi = document.getElementById('fileInput');
      if (!fi || !fi.files || fi.files.length === 0) { showFormError('Выберите файл'); e.preventDefault(); return; }
    }
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Генерируем...';
    }
    const loadingMsg = document.getElementById('loadingMsg');
    if (loadingMsg) loadingMsg.style.display = '';
  });
}());
