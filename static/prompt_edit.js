(function () {
  var textarea = document.getElementById('promptTextarea');
  var counter  = document.getElementById('charCount');

  if (textarea && counter) {
    textarea.addEventListener('input', function () {
      counter.textContent = textarea.value.length + ' симв.';
    });
  }
})();
