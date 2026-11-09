document.addEventListener('DOMContentLoaded', () => {
    const TOAST_VISIBLE_MS = 4000;
    const TOAST_FADE_MS = 400;

    document.querySelectorAll('.alert[role="alert"]').forEach(alert => {
        // Додаємо кнопку закриття
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'toast-close';
        closeBtn.setAttribute('aria-label', window.gettext('Close'));
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', () => dismiss(alert));
        alert.appendChild(closeBtn);

        // Прогрес-бар
        const progress = document.createElement('div');
        progress.className = 'toast-progress';
        alert.appendChild(progress);
        progress.style.animationDuration = TOAST_VISIBLE_MS + 'ms';

        // Автозникнення
        const timer = setTimeout(() => dismiss(alert), TOAST_VISIBLE_MS);

        // Пауза при наведенні
        alert.addEventListener('mouseenter', () => {
            clearTimeout(timer);
            progress.style.animationPlayState = 'paused';
        });
        alert.addEventListener('mouseleave', () => {
            setTimeout(() => dismiss(alert), TOAST_FADE_MS + 500);
            progress.style.animationPlayState = 'running';
        });
    });

    function dismiss(alert) {
        alert.style.transition = `opacity ${TOAST_FADE_MS}ms ease, transform ${TOAST_FADE_MS}ms ease`;
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-8px)';
        setTimeout(() => alert.remove(), TOAST_FADE_MS);
    }
});
