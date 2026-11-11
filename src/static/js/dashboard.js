document.addEventListener('DOMContentLoaded', () => {
    const REFRESH_INTERVAL_MS = 60_000;

    // Знаходимо всі елементи з data-metric
    const metricEls = {
        appointments_count:    document.querySelector('[data-metric="appointments_count"]'),
        completed_count:       document.querySelector('[data-metric="completed_count"]'),
        cancelled_count:       document.querySelector('[data-metric="cancelled_count"]'),
        clients_count:         document.querySelector('[data-metric="clients_count"]'),
        active_clients_count:  document.querySelector('[data-metric="active_clients_count"]'),
        services_count:        document.querySelector('[data-metric="services_count"]'),
        active_services_count: document.querySelector('[data-metric="active_services_count"]'),
        employees_count:       document.querySelector('[data-metric="employees_count"]'),
    };

    // Якщо немає жодного — ми не на дашборді, виходимо
    if (!metricEls.appointments_count) return;

    function animateValue(el, newValue) {
        if (!el) return;
        const current = el.textContent.trim();
        if (current === String(newValue)) return;

        el.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateY(4px)';

        setTimeout(() => {
            el.textContent = newValue;
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 250);
    }

    function updateIndicator(active) {
        const dot = document.querySelector('[data-refresh-dot]');
        if (!dot) return;
        dot.classList.toggle('refresh-dot-active', active);
    }

    async function refresh() {
        try {
            updateIndicator(true);
            const response = await fetch('/api/dashboard/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });
            if (!response.ok) return;
            const data = await response.json();

            animateValue(metricEls.appointments_count,    data.appointments_count);
            animateValue(metricEls.completed_count,       data.completed_count);
            animateValue(metricEls.cancelled_count,       data.cancelled_count);
            animateValue(metricEls.clients_count,         data.clients_count);
            animateValue(metricEls.active_clients_count,  data.active_clients_count);
            animateValue(metricEls.services_count,        data.services_count);
            animateValue(metricEls.active_services_count, data.active_services_count);
            animateValue(metricEls.employees_count,       data.employees_count);

            // Оновлюємо час останнього оновлення
            const lastUpdated = document.querySelector('[data-last-updated]');
            if (lastUpdated) {
                const now = new Date();
                const formattedTime = new Intl.DateTimeFormat(document.documentElement.lang || 'en', {
                    hour: '2-digit', minute: '2-digit',
                    hourCycle: document.documentElement.dataset.timeFormat === '12' ? 'h12' : 'h23',
                }).format(now);
                lastUpdated.textContent = window.interpolate(
                    window.gettext('Updated at %(time)s'), { time: formattedTime }, true
                );
            }
        } catch (e) {
            // Тихо ігноруємо — не ламаємо сторінку
        } finally {
            setTimeout(() => updateIndicator(false), 600);
        }
    }

    setInterval(refresh, REFRESH_INTERVAL_MS);
});
