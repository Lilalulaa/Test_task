/**
 * ============================================================
 * script.js - ЛОГИКА ДАШБОРДА
 * ============================================================
 *
 * Отвечает за:
 * - Загрузку данных из API
 * - Отображение KPI
 * - Построение графиков (Chart.js)
 * - Заполнение таблиц
 * - Переключение вкладок
 * - Автообновление данных
 * ============================================================
 */

'use strict';

// ----------------------------------------------------------
// 1. КОНСТАНТЫ
// ----------------------------------------------------------

const API_URL = 'http://127.0.0.1:5000/api';
const REFRESH_INTERVAL_MS = 300000; // 5 минут

// ----------------------------------------------------------
// 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ----------------------------------------------------------

/**
 * Форматирует число в денежный формат (млн ₽, тыс ₽, ₽).
 *
 * @param {number} value - Число для форматирования
 * @returns {string} Отформатированная строка
 */
function formatMoney(value) {
    if (typeof value !== 'number' || isNaN(value)) {
        return '—';
    }
    const abs = Math.abs(value);
    if (abs >= 1_000_000) {
        return (value / 1_000_000).toFixed(1) + ' млн ₽';
    }
    if (abs >= 1_000) {
        return (value / 1_000).toFixed(0) + ' тыс ₽';
    }
    return value.toFixed(0) + ' ₽';
}

/**
 * Определяет статус отдела по проценту просрочки.
 *
 * @param {number} percent - Процент просрочки
 * @returns {{key: string, label: string}} Ключ и метка статуса
 */
function getStatus(percent) {
    if (percent <= 15) return { key: 'normal', label: '✅ Норма' };
    if (percent <= 30) return { key: 'warning', label: '⚠️ Внимание' };
    return { key: 'critical', label: '🚨 Критично' };
}

// ----------------------------------------------------------
// 3. ВКЛАДКИ (с ленивой инициализацией графиков)
// ----------------------------------------------------------

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        // Убираем активный класс у всех кнопок
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');

        // Показываем нужную вкладку
        const tabId = this.dataset.tab;
        document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');

        // Если переключились на вкладку динамики – инициализируем графики
        if (tabId === 'tab-dynamics') {
            initDepartmentCharts();
            setTimeout(resizeCharts, 300);
        } else {
            setTimeout(resizeCharts, 300);
        }
    });
});

// ----------------------------------------------------------
// 4. ЗАГРУЗКА KPI
// ----------------------------------------------------------

/**
 * Загружает KPI-показатели и обновляет карточки на странице.
 */
async function loadKPI() {
    try {
        const response = await fetch(`${API_URL}/kpi`);
        const data = await response.json();

        document.getElementById('totalDebt').textContent = formatMoney(data.total_debt);
        document.getElementById('overdue').textContent = formatMoney(data.overdue);
        document.getElementById('inApproach').textContent = formatMoney(data.in_approach);
        document.getElementById('forecast').textContent = formatMoney(data.forecast);

        function formatDelta(value) {
            if (value === 0) return '0%';
            const sign = value > 0 ? '+' : '';
            const color = value > 0 ? '#4CAF50' : (value < 0 ? '#f44336' : '#888');
            return `<span style="color:${color}">${sign}${value}%</span>`;
        }

        document.getElementById('totalDebtDelta').innerHTML = formatDelta(data.total_debt_delta);
        document.getElementById('overdueDelta').innerHTML = formatDelta(data.overdue_delta);
        document.getElementById('inApproachDelta').innerHTML = formatDelta(data.in_approach_delta);
        document.getElementById('forecastDelta').innerHTML = formatDelta(data.forecast_delta);

    } catch (error) {
        console.error('❌ Ошибка загрузки KPI:', error);
    }
}

// ----------------------------------------------------------
// 5. ЗАГРУЗКА ТАБЛИЦЫ ОТДЕЛОВ
// ----------------------------------------------------------

/**
 * Загружает детализацию по отделам и заполняет таблицу.
 */
async function loadDepartments() {
    try {
        const response = await fetch(`${API_URL}/departments`);
        const departments = await response.json();

        const tbody = document.getElementById('departmentsTableBody');
        tbody.innerHTML = '';

        let totalDebtSum = 0;
        let overdueSum = 0;
        let approachSum = 0;
        let forecastSum = 0;

        departments.forEach(dept => {
            totalDebtSum += dept.total_debt;
            overdueSum += dept.overdue;
            approachSum += dept.in_approach || 0;
            forecastSum += dept.forecast || 0;

            const status = getStatus(dept.overdue_percent);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${dept.department}</strong></td>
                <td class="data-table__col--numeric">${formatMoney(dept.total_debt)}</td>
                <td class="data-table__col--numeric">${formatMoney(dept.overdue)}</td>
                <td class="data-table__col--numeric"><strong>${dept.overdue_percent}%</strong></td>
                <td class="data-table__col--numeric">${formatMoney(dept.in_approach || 0)}</td>
                <td class="data-table__col--numeric">${formatMoney(dept.forecast || 0)}</td>
                <td><span class="status-badge status-badge--${status.key}">${status.label}</span></td>
            `;
            tbody.appendChild(tr);
        });

        // Строка ИТОГО
        const totalPercent = totalDebtSum > 0 ? ((overdueSum / totalDebtSum) * 100).toFixed(1) : '0.0';
        const totalRow = document.createElement('tr');
        totalRow.className = 'data-table__row--total';
        totalRow.innerHTML = `
            <td>📌 ИТОГО</td>
            <td class="data-table__col--numeric">${formatMoney(totalDebtSum)}</td>
            <td class="data-table__col--numeric">${formatMoney(overdueSum)}</td>
            <td class="data-table__col--numeric"><strong>${totalPercent}%</strong></td>
            <td class="data-table__col--numeric">${formatMoney(approachSum)}</td>
            <td class="data-table__col--numeric">${formatMoney(forecastSum)}</td>
            <td>—</td>
        `;
        tbody.appendChild(totalRow);

    } catch (error) {
        console.error('❌ Ошибка загрузки отделов:', error);
    }
}

// ----------------------------------------------------------
// 6. ГРАФИКИ (обзор)
// ----------------------------------------------------------

let trendChartInstance = null;
let departmentsChartInstance = null;

/**
 * Загружает и строит графики на вкладке "Обзор".
 */
async function loadCharts() {
    try {
        // --- График 1: Тренд ---
        const chartResponse = await fetch(`${API_URL}/charts`);
        const chartData = await chartResponse.json();

        const ctx1 = document.getElementById('trendChart').getContext('2d');
        if (trendChartInstance) trendChartInstance.destroy();

        const hasData = chartData.dates && chartData.dates.length > 0;

        trendChartInstance = new Chart(ctx1, {
            type: 'line',
            data: {
                labels: hasData ? chartData.dates : ['Нет данных'],
                datasets: [
                    {
                        label: 'Общая ДЗ',
                        data: hasData ? chartData.total_trend : [0],
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.08)',
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4,
                    },
                    {
                        label: 'Просроченная',
                        data: hasData ? chartData.overdue_trend : [0],
                        borderColor: '#f44336',
                        backgroundColor: 'rgba(244, 67, 54, 0.05)',
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4,
                    },
                    {
                        label: 'Доля просрочки, %',
                        data: hasData ? chartData.percent_trend : [0],
                        borderColor: '#FF9800',
                        borderDash: [6, 4],
                        tension: 0.35,
                        pointRadius: 3,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, padding: 20, font: { size: 12 } } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const label = ctx.dataset.label || '';
                                const value = ctx.parsed.y;
                                if (label.includes('%')) return `${label}: ${value.toFixed(1)}%`;
                                return `${label}: ${value.toFixed(1)} млн ₽`;
                            },
                        },
                    },
                },
                scales: {
                    y: {
                        position: 'left',
                        beginAtZero: false,
                        ticks: { callback: (v) => v.toFixed(0) + ' млн' },
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    },
                    y1: {
                        position: 'right',
                        beginAtZero: true,
                        max: 20,
                        ticks: { callback: (v) => v.toFixed(0) + '%' },
                        grid: { drawOnChartArea: false }
                    },
                },
            },
        });

        // --- График 2: Сравнение отделов ---
        const deptResponse = await fetch(`${API_URL}/departments`);
        const departments = await deptResponse.json();

        const ctx2 = document.getElementById('departmentsChart').getContext('2d');
        if (departmentsChartInstance) departmentsChartInstance.destroy();

        departmentsChartInstance = new Chart(ctx2, {
            type: 'bar',
            data: {
                labels: departments.map(d => d.department),
                datasets: [
                    {
                        label: 'Общая ДЗ',
                        data: departments.map(d => +(d.total_debt / 1_000_000).toFixed(2)),
                        backgroundColor: 'rgba(33, 150, 243, 0.7)',
                        borderColor: '#2196F3',
                        borderWidth: 2,
                        borderRadius: 4,
                    },
                    {
                        label: 'Просроченная',
                        data: departments.map(d => +(d.overdue / 1_000_000).toFixed(2)),
                        backgroundColor: 'rgba(244, 67, 54, 0.7)',
                        borderColor: '#f44336',
                        borderWidth: 2,
                        borderRadius: 4,
                    },
                    {
                        label: 'В подходе',
                        data: departments.map(d => +((d.in_approach || 0) / 1_000_000).toFixed(2)),
                        backgroundColor: 'rgba(76, 175, 80, 0.7)',
                        borderColor: '#4CAF50',
                        borderWidth: 2,
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, padding: 20, font: { size: 12 } } },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: (v) => v.toFixed(0) + ' млн' },
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    },
                },
            },
        });

    } catch (error) {
        console.error('❌ Ошибка загрузки графиков:', error);
    }
}

// ----------------------------------------------------------
// 7. МУЛЬТИЛИНЕЙНЫЕ ГРАФИКИ ПО ОТДЕЛАМ (ленивая инициализация)
// ----------------------------------------------------------

let deptTrendData = null;
let deptTotalTrendChart = null;
let deptOverdueTrendChart = null;
let departmentChartsInitialized = false;

/**
 * Загружает данные для мультилинейных графиков.
 */
async function loadDepartmentTrend() {
    try {
        const response = await fetch(`${API_URL}/department-trend`);
        deptTrendData = await response.json();
        // Если вкладка уже активна – инициализируем сразу
        if (document.getElementById('tab-dynamics').classList.contains('active')) {
            initDepartmentCharts();
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки динамики отделов:', error);
    }
}

/**
 * Инициализирует мультилинейные графики (лениво, при первом переключении).
 */
function initDepartmentCharts() {
    if (departmentChartsInitialized || !deptTrendData) return;
    const data = deptTrendData;

    // График общей ДЗ по отделам
    const ctx1 = document.getElementById('deptTotalTrendChart').getContext('2d');
    if (deptTotalTrendChart) deptTotalTrendChart.destroy();
    deptTotalTrendChart = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: data.total_datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, padding: 15, font: { size: 11 } }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: (v) => v.toFixed(0) + ' млн' }
                }
            }
        }
    });

    // График просроченной ДЗ по отделам
    const ctx2 = document.getElementById('deptOverdueTrendChart').getContext('2d');
    if (deptOverdueTrendChart) deptOverdueTrendChart.destroy();
    deptOverdueTrendChart = new Chart(ctx2, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: data.overdue_datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, padding: 15, font: { size: 11 } }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: (v) => v.toFixed(0) + ' млн' }
                }
            }
        }
    });

    departmentChartsInitialized = true;

    // Принудительное обновление размеров после появления
    setTimeout(() => {
        if (deptTotalTrendChart) deptTotalTrendChart.resize();
        if (deptOverdueTrendChart) deptOverdueTrendChart.resize();
    }, 200);
}

// ----------------------------------------------------------
// 8. ТОП-15
// ----------------------------------------------------------

/**
 * Загружает и отображает Топ-15 по сумме просрочки.
 */
async function loadTopOverdue() {
    try {
        const response = await fetch(`${API_URL}/top-overdue`);
        const data = await response.json();

        const tbody = document.getElementById('topOverdueTableBody');
        tbody.innerHTML = '';

        data.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${item.rank}</strong></td>
                <td>${item.contractor}</td>
                <td>${item.department}</td>
                <td class="data-table__col--numeric">${formatMoney(item.amount)}</td>
                <td class="data-table__col--numeric">${item.days}</td>
            `;
            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error('❌ Ошибка загрузки Топ-15 по просрочке:', error);
    }
}

/**
 * Загружает и отображает Топ-15 по дням просрочки.
 */
async function loadTopDays() {
    try {
        const response = await fetch(`${API_URL}/top-days`);
        const data = await response.json();

        const tbody = document.getElementById('topDaysTableBody');
        tbody.innerHTML = '';

        data.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${item.rank}</strong></td>
                <td>${item.contractor}</td>
                <td>${item.department}</td>
                <td class="data-table__col--numeric"><strong>${item.days}</strong></td>
                <td class="data-table__col--numeric">${formatMoney(item.amount)}</td>
            `;
            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error('❌ Ошибка загрузки Топ-15 по дням:', error);
    }
}

// ----------------------------------------------------------
// 9. ОБНОВЛЕНИЕ ВСЕХ ДАННЫХ
// ----------------------------------------------------------

/**
 * Обновляет все данные на дашборде.
 */
async function refreshData() {
    const btn = document.querySelector('.app-header__refresh');
    if (btn) {
        btn.textContent = '⏳ Загрузка...';
        btn.disabled = true;
    }

    console.log('🔄 Обновление данных...');

    try {
        await Promise.all([
            loadKPI(),
            loadDepartments(),
            loadCharts(),
            loadDepartmentTrend(),
            loadTopOverdue(),
            loadTopDays(),
        ]);
        console.log('✅ Данные обновлены!');
    } catch (error) {
        console.error('❌ Ошибка обновления:', error);
    } finally {
        if (btn) {
            btn.textContent = '🔄 Обновить';
            btn.disabled = false;
        }
    }
}

// ----------------------------------------------------------
// 10. АДАПТАЦИЯ ГРАФИКОВ
// ----------------------------------------------------------

/**
 * Обновляет размеры всех графиков при изменении размера окна.
 */
function resizeCharts() {
    if (trendChartInstance) {
        trendChartInstance.resize();
        trendChartInstance.update();
    }
    if (departmentsChartInstance) {
        departmentsChartInstance.resize();
        departmentsChartInstance.update();
    }
    if (deptTotalTrendChart) {
        deptTotalTrendChart.resize();
        deptTotalTrendChart.update();
    }
    if (deptOverdueTrendChart) {
        deptOverdueTrendChart.resize();
        deptOverdueTrendChart.update();
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => { clearTimeout(timeout); func(...args); };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

const debouncedResize = debounce(resizeCharts, 200);
window.addEventListener('resize', debouncedResize);

window.addEventListener('load', function() {
    setTimeout(resizeCharts, 500);
});

if (window.screen && window.screen.orientation) {
    window.screen.orientation.addEventListener('change', function() {
        setTimeout(resizeCharts, 300);
    });
} else {
    window.addEventListener('orientationchange', function() {
        setTimeout(resizeCharts, 300);
    });
}

// ----------------------------------------------------------
// 11. ЗАПУСК
// ----------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Дашборд загружается...');
    refreshData();
    setInterval(refreshData, REFRESH_INTERVAL_MS);
    console.log('✅ Дашборд готов, автообновление каждые 5 минут');
});