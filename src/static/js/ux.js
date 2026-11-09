// ── Темна тема ───────────────────────────────────────────────────────────────
(function () {
    const DARK_KEY = 'orvanta-dark';
    const body    = document.getElementById('app-body');
    const btn     = document.getElementById('theme-toggle');

    if (!body || !btn) return;

    const isDark = () => body.classList.contains('dark-theme');

    // Застосовуємо збережений стан одразу (до DOMContentLoaded)
    if (localStorage.getItem(DARK_KEY) === '1') {
        body.classList.add('dark-theme');
    }
    document.documentElement.classList.remove('dark-theme-init');

    const updateIcon = () => { btn.textContent = isDark() ? '☀' : '🌙'; };
    updateIcon();

    btn.addEventListener('click', () => {
        body.classList.toggle('dark-theme');
        localStorage.setItem(DARK_KEY, isDark() ? '1' : '0');
        updateIcon();
    });
})();

document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', (event) => {
        const button = event.target.closest('[data-confirm]');
        if (button && !window.confirm(button.dataset.confirm)) {
            event.preventDefault();
        }
    });


    // ── 1. Кнопка × для очищення пошукових полів у filter-form ───────────────

    document.querySelectorAll('.filter-form input[type="text"], .filter-form input[type="search"]').forEach(input => {
        const wrapper = document.createElement('span');
        wrapper.className = 'search-clear-wrapper';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'search-clear-btn';
        btn.setAttribute('aria-label', window.gettext('Clear'));
        btn.innerHTML = '&times;';
        btn.style.display = input.value ? 'flex' : 'none';
        wrapper.appendChild(btn);

        input.addEventListener('input', () => {
            btn.style.display = input.value ? 'flex' : 'none';
        });

        btn.addEventListener('click', () => {
            input.value = '';
            btn.style.display = 'none';
            input.focus();
            // Автосабміт форми щоб список оновився
            input.closest('form').submit();
        });
    });


    // ── 2. Попередження про незбережені зміни в app-form ─────────────────────

    document.querySelectorAll('form.app-form').forEach(form => {
        let isDirty = false;
        let isSubmitting = false;

        // Відстежуємо зміни
        form.addEventListener('input', () => { isDirty = true; });
        form.addEventListener('change', () => { isDirty = true; });

        // Якщо форма сабміттиться — все ок, не попереджаємо
        form.addEventListener('submit', () => { isSubmitting = true; });

        window.addEventListener('beforeunload', (e) => {
            if (isDirty && !isSubmitting) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    });

});
