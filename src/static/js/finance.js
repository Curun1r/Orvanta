window._revenueChartInit = function () {
    const canvas = document.getElementById('revenueChart');
    if (!canvas) return;

    const dataEl = document.getElementById('revenueChartData');
    if (!dataEl) return;

    let raw;
    try { raw = JSON.parse(dataEl.textContent); } catch (e) { return; }
    if (!raw || !raw.length) return;

    raw.sort((a, b) => a.appointment_date.localeCompare(b.appointment_date));

    const locale = document.documentElement.lang || 'en';
    const money = new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const monthLabel = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' });
    const dateLabel = new Intl.DateTimeFormat(locale);

    // Унікальні місяці у порядку зростання
    const monthKeys = [...new Set(raw.map(d => d.appointment_date.slice(0, 7)))].sort();

    const isDark = localStorage.getItem('orvanta-dark') === '1';
    const accent    = isDark ? '#60a5fa' : '#6366f1';
    const gridColor = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.08)';
    const tickColor = isDark ? '#94a3b8' : '#6b7280';

    let activeMonth = null; // null = всі
    let activeType  = 'bar';

    function getFiltered() {
        if (!activeMonth) return raw;
        return raw.filter(d => d.appointment_date.startsWith(activeMonth));
    }

    function buildConfig(type, data) {
        const labels = data.map(d => {
            const [y, m, day] = d.appointment_date.split('-');
            return dateLabel.format(new Date(Number(y), Number(m) - 1, Number(day)));
        });
        const values = data.map(d => parseFloat(d.revenue) || 0);
        const isLine = type === 'line';
        return {
            type,
            data: {
                labels,
                datasets: [{
                    label: gettext('Revenue (UAH)'),
                    data: values,
                    backgroundColor: isLine ? accent + '33' : accent + 'bb',
                    borderColor: accent,
                    borderWidth: isLine ? 2 : 0,
                    borderRadius: isLine ? 0 : 6,
                    fill: isLine,
                    tension: 0.35,
                    pointRadius: isLine ? 4 : 0,
                    pointBackgroundColor: accent,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 300 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${money.format(ctx.parsed.y)} ${gettext('UAH')}`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: gridColor },
                        ticks: { maxTicksLimit: 14, font: { size: 12 }, color: tickColor }
                    },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            font: { size: 12 },
                            color: tickColor,
                            callback: v => Number(v).toLocaleString(locale) + ' ' + gettext('UAH')
                        },
                        beginAtZero: true
                    }
                }
            }
        };
    }

    function redraw() {
        chart.destroy();
        chart = new Chart(canvas, buildConfig(activeType, getFiltered()));
    }

    let chart = new Chart(canvas, buildConfig('bar', raw));

    // Перемикач тип графіку
    document.querySelectorAll('.chart-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.chart-toggle-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeType = btn.dataset.chartType;
            redraw();
        });
    });

    // Кнопки місяців
    if (monthKeys.length > 1) {
        const filterWrap = document.getElementById('chart-month-filter');
        if (!filterWrap) return;

        const allBtn = document.createElement('button');
        allBtn.className = 'btn btn-sm btn-outline-secondary chart-month-btn active';
        allBtn.textContent = gettext('All');
        allBtn.dataset.month = '';
        filterWrap.appendChild(allBtn);

        monthKeys.forEach(key => {
            const [y, m] = key.split('-');
            const btn = document.createElement('button');
            btn.className = 'btn btn-sm btn-outline-secondary chart-month-btn';
            btn.textContent = monthLabel.format(new Date(Number(y), Number(m) - 1, 1));
            btn.dataset.month = key;
            filterWrap.appendChild(btn);
        });

        filterWrap.addEventListener('click', e => {
            const btn = e.target.closest('.chart-month-btn');
            if (!btn) return;
            filterWrap.querySelectorAll('.chart-month-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeMonth = btn.dataset.month || null;
            redraw();
        });
    }
};
window._revenueChartInit();
