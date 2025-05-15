// Custom JavaScript for enhanced Datasette functionality

document.addEventListener('DOMContentLoaded', function() {
  // Add a class to the body indicating this is the immutable version
  document.body.classList.add('immutable-datasette');

  // Add a banner indicating this is immutable data
  if (document.querySelector('header')) {
    const banner = document.createElement('div');
    banner.className = 'immutable-banner';
    banner.innerHTML = '<strong>Immutable Data:</strong> This Datasette instance serves data in read-only mode.';
    banner.style.backgroundColor = '#FFFDE7';
    banner.style.padding = '8px 16px';
    banner.style.textAlign = 'center';
    banner.style.borderBottom = '1px solid #E0E0E0';

    const header = document.querySelector('header');
    header.parentNode.insertBefore(banner, header.nextSibling);
  }

  // Add copy buttons to SQL queries
  const sqlTextareas = document.querySelectorAll('textarea.sql');
  sqlTextareas.forEach(function(textarea) {
    const copyButton = document.createElement('button');
    copyButton.textContent = 'Copy SQL';
    copyButton.className = 'copy-sql';
    copyButton.style.fontSize = '12px';
    copyButton.style.padding = '2px 6px';
    copyButton.style.marginLeft = '8px';

    copyButton.addEventListener('click', function() {
      textarea.select();
      document.execCommand('copy');

      // Show copied confirmation
      const origText = copyButton.textContent;
      copyButton.textContent = 'Copied!';
      setTimeout(function() {
        copyButton.textContent = origText;
      }, 1500);
    });

    textarea.parentNode.insertBefore(copyButton, textarea.nextSibling);
  });
});