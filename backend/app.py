"""
============================================================
app.py - Веб-сервер дашборда дебиторской задолженности
============================================================

Технологический стек:
  - Flask 2.3.3: WSGI-сервер
  - SQLite3: хранение данных
  - Flask-CORS: кросс-доменные запросы

REST API:
  GET /api/kpi              → KPI + дельта
  GET /api/departments      → Детализация по отделам
  GET /api/charts           → Тренд (общая + просроченная)
  GET /api/department-trend → Динамика по отделам (мультилинейные)
  GET /api/top-overdue      → Топ-15 по сумме просрочки
  GET /api/top-days         → Топ-15 по дням просрочки
  GET /api/stats            → Общая статистика
============================================================
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, List, Dict


# ----------------------------------------------------------
# 1. НАСТРОЙКА ЛОГИРОВАНИЯ
# ----------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------
# 2. КОНФИГУРАЦИЯ
# ----------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent          # Корень проекта
DB_PATH = Path(__file__).parent / "dashboard.db" # Путь к БД
STATIC_FOLDER = BASE_DIR / "frontend"            # Путь к статике (HTML, CSS, JS)


# ----------------------------------------------------------
# 3. ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
# ----------------------------------------------------------

app = Flask(__name__, static_folder=str(STATIC_FOLDER), static_url_path='')
CORS(app)  # Разрешаем кросс-доменные запросы


# ----------------------------------------------------------
# 4. РАБОТА С БАЗОЙ ДАННЫХ
# ----------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """
    Создаёт НОВОЕ подключение к SQLite для каждого запроса.

    Returns:
        sqlite3.Connection с row_factory = sqlite3.Row
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Безопасное преобразование в float.

    Args:
        value: Значение для преобразования
        default: Значение по умолчанию

    Returns:
        float или default
    """
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Безопасное преобразование в int.

    Args:
        value: Значение для преобразования
        default: Значение по умолчанию

    Returns:
        int или default
    """
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


# ----------------------------------------------------------
# 5. МАРШРУТЫ: СТАТИКА
# ----------------------------------------------------------

@app.route('/')
def index():
    """Отдаёт главную страницу дашборда."""
    try:
        return send_from_directory(STATIC_FOLDER, 'index.html')
    except FileNotFoundError:
        return jsonify({'error': 'Frontend not found'}), 404


@app.route('/<path:filename>')
def static_files(filename: str):
    """Отдаёт статические файлы (CSS, JS, изображения)."""
    try:
        return send_from_directory(STATIC_FOLDER, filename)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404


# ----------------------------------------------------------
# 6. API: KPI + ДЕЛЬТА
# ----------------------------------------------------------

@app.route('/api/kpi')
def get_kpi():
    """
    Возвращает 4 ключевых показателя + дельту к предыдущей дате.

    Returns:
        JSON: total_debt, overdue, in_approach, forecast + их дельты
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем последние 2 даты срезов
    cur.execute("""
        SELECT DISTINCT snapshot_date
        FROM documents
        ORDER BY snapshot_date DESC
        LIMIT 2
    """)
    dates = cur.fetchall()

    if len(dates) == 0:
        conn.close()
        return jsonify({
            'total_debt': 0, 'overdue': 0, 'in_approach': 0, 'forecast': 0,
            'total_debt_delta': 0, 'overdue_delta': 0,
            'in_approach_delta': 0, 'forecast_delta': 0
        })

    current_date = dates[0]['snapshot_date']
    previous_date = dates[1]['snapshot_date'] if len(dates) > 1 else None

    # Текущие показатели
    cur.execute("""
        SELECT
            COALESCE(SUM(debt_total), 0) as total_debt,
            COALESCE(SUM(overdue), 0) as overdue,
            COALESCE(SUM(CASE WHEN days_to_plan BETWEEN 1 AND 5 THEN debt_total ELSE 0 END), 0) as in_approach,
            COALESCE(SUM(CASE WHEN days_to_plan BETWEEN 1 AND 7 THEN debt_total ELSE 0 END), 0) as forecast
        FROM documents
        WHERE snapshot_date = ?
    """, (current_date,))
    current = cur.fetchone()

    result = {
        'total_debt': round(float(current['total_debt']), 2),
        'overdue': round(float(current['overdue']), 2),
        'in_approach': round(float(current['in_approach']), 2),
        'forecast': round(float(current['forecast']), 2),
        'total_debt_delta': 0,
        'overdue_delta': 0,
        'in_approach_delta': 0,
        'forecast_delta': 0,
    }

    # Если есть предыдущая дата — считаем дельту в процентах
    if previous_date:
        cur.execute("""
            SELECT
                COALESCE(SUM(debt_total), 0) as total_debt,
                COALESCE(SUM(overdue), 0) as overdue,
                COALESCE(SUM(CASE WHEN days_to_plan BETWEEN 1 AND 5 THEN debt_total ELSE 0 END), 0) as in_approach,
                COALESCE(SUM(CASE WHEN days_to_plan BETWEEN 1 AND 7 THEN debt_total ELSE 0 END), 0) as forecast
            FROM documents
            WHERE snapshot_date = ?
        """, (previous_date,))
        previous = cur.fetchone()

        def calc_delta(current_val: float, previous_val: float) -> float:
            """Вычисляет процентное изменение."""
            if previous_val == 0:
                return 0.0
            return round(((current_val - previous_val) / previous_val) * 100, 1)

        result['total_debt_delta'] = calc_delta(
            float(current['total_debt']),
            float(previous['total_debt'])
        )
        result['overdue_delta'] = calc_delta(
            float(current['overdue']),
            float(previous['overdue'])
        )
        result['in_approach_delta'] = calc_delta(
            float(current['in_approach']),
            float(previous['in_approach'])
        )
        result['forecast_delta'] = calc_delta(
            float(current['forecast']),
            float(previous['forecast'])
        )

    conn.close()
    return jsonify(result)


# ----------------------------------------------------------
# 7. API: ОТДЕЛЫ (ДЕТАЛИЗАЦИЯ)
# ----------------------------------------------------------

@app.route('/api/departments')
def get_departments():
    """
    Возвращает детализацию по отделам на последнюю дату.

    Returns:
        JSON: массив отделов с общей ДЗ, просроченной, % просрочки, в подходе, прогнозом
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем последнюю дату среза
    cur.execute("SELECT MAX(snapshot_date) as max_date FROM documents")
    max_date = cur.fetchone()['max_date']

    cur.execute("""
        SELECT
            department,
            COALESCE(SUM(debt_total), 0) as total_debt,
            COALESCE(SUM(overdue), 0) as overdue,
            COALESCE(SUM(
                CASE WHEN days_to_plan BETWEEN 1 AND 5
                THEN debt_total ELSE 0 END
            ), 0) as in_approach,
            COALESCE(SUM(
                CASE WHEN days_to_plan BETWEEN 1 AND 7
                THEN debt_total ELSE 0 END
            ), 0) as forecast
        FROM documents
        WHERE snapshot_date = ?
        GROUP BY department
        ORDER BY total_debt DESC
    """, (max_date,))

    result = []
    for row in cur.fetchall():
        total = safe_float(row['total_debt'])
        overdue = safe_float(row['overdue'])
        overdue_percent = round((overdue / total * 100), 1) if total > 0 else 0.0

        result.append({
            'department': row['department'],
            'total_debt': round(total, 2),
            'overdue': round(overdue, 2),
            'overdue_percent': overdue_percent,
            'in_approach': round(safe_float(row['in_approach']), 2),
            'forecast': round(safe_float(row['forecast']), 2),
        })

    conn.close()
    return jsonify(result)


# ----------------------------------------------------------
# 8. API: ГРАФИК ТРЕНДА
# ----------------------------------------------------------

@app.route('/api/charts')
def get_charts():
    """
    Возвращает данные для графика тренда.

    Returns:
        JSON: dates, total_trend (млн), overdue_trend (млн), percent_trend
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            snapshot_date,
            COALESCE(SUM(debt_total), 0) as total,
            COALESCE(SUM(overdue), 0) as overdue
        FROM documents
        GROUP BY snapshot_date
        ORDER BY snapshot_date
    """)

    dates = []
    total_trend = []
    overdue_trend = []
    percent_trend = []

    for row in cur.fetchall():
        total = safe_float(row['total'])
        overdue = safe_float(row['overdue'])

        date_val = row['snapshot_date']
        if isinstance(date_val, datetime):
            date_val = date_val.strftime('%d.%m.%Y')

        dates.append(date_val)
        total_trend.append(round(total / 1_000_000, 2))       # В миллионах
        overdue_trend.append(round(overdue / 1_000_000, 2))  # В миллионах
        percent_trend.append(round((overdue / total * 100), 1) if total > 0 else 0.0)

    conn.close()
    return jsonify({
        'dates': dates,
        'total_trend': total_trend,
        'overdue_trend': overdue_trend,
        'percent_trend': percent_trend,
    })


# ----------------------------------------------------------
# 9. API: ДИНАМИКА ПО ОТДЕЛАМ (МУЛЬТИЛИНЕЙНЫЕ)
# ----------------------------------------------------------

@app.route('/api/department-trend')
def get_department_trend():
    """
    Возвращает динамику ДЗ по отделам для мультилинейных графиков.

    Returns:
        JSON: dates, total_datasets (общая ДЗ по отделам), overdue_datasets (просроченная)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            snapshot_date,
            department,
            COALESCE(SUM(debt_total), 0) as total,
            COALESCE(SUM(overdue), 0) as overdue
        FROM documents
        GROUP BY snapshot_date, department
        ORDER BY snapshot_date, department
    """)

    # Группировка по датам: {дата: {отдел: {total, overdue}}}
    dates_dict = {}
    for row in cur.fetchall():
        date_val = row['snapshot_date']
        if isinstance(date_val, datetime):
            date_val = date_val.strftime('%d.%m.%Y')

        if date_val not in dates_dict:
            dates_dict[date_val] = {}

        dates_dict[date_val][row['department']] = {
            'total': float(row['total']),
            'overdue': float(row['overdue'])
        }

    # Список всех отделов
    cur.execute("SELECT DISTINCT department FROM documents")
    departments = [row['department'] for row in cur.fetchall()]

    dates = sorted(dates_dict.keys())
    colors = ['#2196F3', '#f44336', '#4CAF50', '#FF9800', '#9C27B0', '#00BCD4',
              '#795548', '#607D8B', '#E91E63', '#3F51B5']

    total_datasets = []
    overdue_datasets = []

    for i, dept in enumerate(departments):
        total_data = []
        overdue_data = []

        for date in dates:
            if date in dates_dict and dept in dates_dict[date]:
                total_data.append(round(dates_dict[date][dept]['total'] / 1_000_000, 2))
                overdue_data.append(round(dates_dict[date][dept]['overdue'] / 1_000_000, 2))
            else:
                total_data.append(0)
                overdue_data.append(0)

        color = colors[i % len(colors)]
        total_datasets.append({
            'label': dept,
            'data': total_data,
            'borderColor': color,
            'backgroundColor': color + '20',
            'tension': 0.3,
            'pointRadius': 3,
            'fill': False,
        })
        overdue_datasets.append({
            'label': dept,
            'data': overdue_data,
            'borderColor': color,
            'backgroundColor': color + '20',
            'tension': 0.3,
            'pointRadius': 3,
            'fill': False,
        })

    conn.close()
    return jsonify({
        'dates': dates,
        'total_datasets': total_datasets,
        'overdue_datasets': overdue_datasets,
    })


# ----------------------------------------------------------
# 10. API: ТОП-15 ПО СУММЕ ПРОСРОЧКИ
# ----------------------------------------------------------

@app.route('/api/top-overdue')
def get_top_overdue():
    """
    Возвращает Топ-15 контрагентов по сумме просрочки на последнюю дату.

    Returns:
        JSON: массив с rank, contractor, department, amount, days
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT MAX(snapshot_date) as max_date FROM documents")
    max_date = cur.fetchone()['max_date']

    cur.execute("""
        SELECT
            contractor,
            department,
            COALESCE(SUM(overdue), 0) as total_overdue,
            COALESCE(MAX(days_overdue), 0) as max_days
        FROM documents
        WHERE snapshot_date = ?
          AND contractor IS NOT NULL
          AND contractor != ''
          AND overdue > 0
        GROUP BY contractor, department
        ORDER BY total_overdue DESC
        LIMIT 15
    """, (max_date,))

    result = []
    for i, row in enumerate(cur.fetchall(), 1):
        result.append({
            'rank': i,
            'contractor': row['contractor'],
            'department': row['department'],
            'amount': round(safe_float(row['total_overdue']), 2),
            'days': safe_int(row['max_days']),
        })

    conn.close()
    return jsonify(result)


# ----------------------------------------------------------
# 11. API: ТОП-15 ПО ДНЯМ ПРОСРОЧКИ
# ----------------------------------------------------------

@app.route('/api/top-days')
def get_top_days():
    """
    Возвращает Топ-15 контрагентов по дням просрочки на последнюю дату.

    Returns:
        JSON: массив с rank, contractor, department, days, amount
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT MAX(snapshot_date) as max_date FROM documents")
    max_date = cur.fetchone()['max_date']

    cur.execute("""
        SELECT
            contractor,
            department,
            COALESCE(MAX(days_overdue), 0) as max_days,
            COALESCE(SUM(debt_total), 0) as total_debt
        FROM documents
        WHERE snapshot_date = ?
          AND contractor IS NOT NULL
          AND contractor != ''
          AND days_overdue > 0
        GROUP BY contractor, department
        ORDER BY max_days DESC
        LIMIT 15
    """, (max_date,))

    result = []
    for i, row in enumerate(cur.fetchall(), 1):
        result.append({
            'rank': i,
            'contractor': row['contractor'],
            'department': row['department'],
            'days': safe_int(row['max_days']),
            'amount': round(safe_float(row['total_debt']), 2),
        })

    conn.close()
    return jsonify(result)


# ----------------------------------------------------------
# 12. API: СТАТИСТИКА
# ----------------------------------------------------------

@app.route('/api/stats')
def get_stats():
    """
    Возвращает общую статистику по документам.

    Returns:
        JSON: total_documents, total_contractors, total_managers
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as value FROM documents")
    total_docs = safe_int(cur.fetchone()['value'])

    cur.execute("SELECT COUNT(DISTINCT contractor) as value FROM documents WHERE contractor IS NOT NULL")
    total_contractors = safe_int(cur.fetchone()['value'])

    cur.execute("SELECT COUNT(DISTINCT manager) as value FROM documents WHERE manager IS NOT NULL")
    total_managers = safe_int(cur.fetchone()['value'])

    conn.close()

    return jsonify({
        'total_documents': total_docs,
        'total_contractors': total_contractors,
        'total_managers': total_managers,
    })


# ----------------------------------------------------------
# 13. ЗАПУСК
# ----------------------------------------------------------

if __name__ == '__main__':
    print('\n' + '=' * 70)
    print('  📊 ДАШБОРД ДЕБИТОРСКОЙ ЗАДОЛЖЕННОСТИ')
    print('  ' + '=' * 66)
    print(f'  🚀 Сервер запущен: http://127.0.0.1:5000')
    print(f'  📁 База данных: {DB_PATH}')
    print(f'  📁 Статика: {STATIC_FOLDER}')
    print('  ' + '-' * 66)
    print('  Доступные API эндпоинты:')
    print('    GET /api/kpi              - KPI + дельта')
    print('    GET /api/departments      - Детализация по отделам')
    print('    GET /api/charts           - Тренд (общая + просроченная)')
    print('    GET /api/department-trend - Динамика по отделам')
    print('    GET /api/top-overdue      - Топ-15 по сумме просрочки')
    print('    GET /api/top-days         - Топ-15 по дням просрочки')
    print('    GET /api/stats            - Общая статистика')
    print('=' * 70 + '\n')

    app.run(debug=True, host='0.0.0.0', port=5000)