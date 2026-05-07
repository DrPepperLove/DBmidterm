/**
 * Gilded Library — Main JavaScript
 * Toast notifications, page-load reveals, confirmation dialogs, form handling.
 */

// ── Toast System ───────────────────────────────────────────────────────────

function showToast(message, type) {
  type = type || 'success';
  var container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  var toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(function () {
    toast.classList.add('toast-exit');
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }, 3200);
}

// ── Confirmation Dialog ────────────────────────────────────────────────────

function confirmAction(message, callback) {
  // Simple but styled confirm — native confirm works fine for now
  // but could be replaced with a custom modal
  if (confirm(message)) {
    callback();
  }
}

// ── API Helpers ────────────────────────────────────────────────────────────

function apiPost(url, formData) {
  return fetch(url, {
    method: 'POST',
    body: formData
  }).then(function (r) { return r.json(); });
}

function apiPostJson(url) {
  return fetch(url, { method: 'POST' }).then(function (r) { return r.json(); });
}

// ── Flash Message Auto-hide ────────────────────────────────────────────────

function initFlashes() {
  var flashes = document.querySelectorAll('.flash-msg');
  for (var i = 0; i < flashes.length; i++) {
    (function (el) {
      setTimeout(function () {
        el.style.opacity = '0';
        el.style.transition = 'opacity 0.4s ease';
        setTimeout(function () {
          if (el.parentNode) el.parentNode.removeChild(el);
        }, 400);
      }, 3500);
    })(flashes[i]);
  }
}

// ── Page Entrance Animation ────────────────────────────────────────────────

function initPageEntrance() {
  // Add stagger delays to card grid items beyond the CSS nth-child range
  var cards = document.querySelectorAll('.card-grid .card');
  for (var i = 0; i < cards.length; i++) {
    if (i >= 5) {
      cards[i].style.animation = 'fadeInUp 0.4s ease both';
      cards[i].style.animationDelay = (0.05 * (i - 4)) + 's';
    }
  }
}

// ── Admin Form Toggle Helpers ──────────────────────────────────────────────

function toggleEdit(id) {
  var el = document.getElementById('edit-' + id);
  if (el) {
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }
}

function toggleCatEdit(id) {
  var el = document.getElementById('cat-edit-' + id);
  if (el) {
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }
}

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  initFlashes();
  initPageEntrance();
});
