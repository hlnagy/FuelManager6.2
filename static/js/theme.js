function setTheme(themeName) {
    document.documentElement.setAttribute('data-theme', themeName);
    localStorage.setItem('theme', themeName);

    // Sync with backend for persistence across sessions
    fetch('/api/set-theme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme: themeName })
    }).catch(err => console.debug('Offline or theme sync failed'));
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    let nextTheme = 'light';

    if (currentTheme === 'light') nextTheme = 'dark';
    else if (currentTheme === 'dark') nextTheme = 'budila';
    else nextTheme = 'light';

    setTheme(nextTheme);
}

// Immediately invoked to prevent flash using localStorage as fallback
(function () {
    const savedTheme = localStorage.getItem('theme') || 'light';
    // Only apply if the server hasn't already injected a theme or to ensure immediate apply
    if (!document.documentElement.getAttribute('data-theme')) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
})();
