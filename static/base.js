const CSRF_TOKEN = document.body.dataset.csrf || '';

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  const open = sidebar.classList.toggle('open');
  const ov = document.getElementById('sidebarOverlay');
  if (ov) ov.style.display = open ? 'block' : 'none';
  const btn = document.getElementById('sidebarToggle');
  if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.remove('open');
  const ov = document.getElementById('sidebarOverlay');
  if (ov) ov.style.display = 'none';
}

(function () {
  const ov = document.getElementById('sidebarOverlay');
  if (ov) ov.addEventListener('click', closeSidebar);
  const btn = document.getElementById('sidebarToggle');
  if (btn) btn.addEventListener('click', toggleSidebar);
  document.querySelectorAll('.sidebar nav a').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.innerWidth < 768) closeSidebar();
    });
  });
}());
