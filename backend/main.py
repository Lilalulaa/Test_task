"""
============================================================
main.py

Точка входа в проект.

Последовательность работы:

1. Поиск Excel-файлов в папке data/.
2. Парсинг файлов (извлечение иерархии и документов).
3. Создание базы SQLite (если не существует).
4. Загрузка данных в таблицу documents.
5. Генерация тестовых срезов для демонстрации динамики.
6. Вывод статистики по загруженным данным.

============================================================
"""

from pathlib import Path
import logging

from parser import DebtExcelParser
from database import Database


# ----------------------------------------------------------
# Настройка логирования
# ----------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------
# Пути проекта
# ----------------------------------------------------------

PROJECT_DIR = Path(__file__).parent.parent   # Корневая папка проекта
DATA_DIR = PROJECT_DIR / "data"              # Папка с Excel-файлами
DATABASE_FILE = Path(__file__).parent / "dashboard.db"  # Путь к БД


def main() -> None:
    """Основная функция проекта."""
    logger.info("=" * 70)
    logger.info("Запуск обработки отчетов")
    logger.info("=" * 70)

    # ------------------------------------------------------
    # Создаём парсер
    # ------------------------------------------------------
    parser = DebtExcelParser()

    # ------------------------------------------------------
    # Парсим все Excel-файлы в папке data/
    # ------------------------------------------------------
    documents = parser.parse_folder(DATA_DIR)
    logger.info("Получено документов: %s", len(documents))

    # ------------------------------------------------------
    # Создаём и заполняем БД
    # ------------------------------------------------------
    db = Database(DATABASE_FILE)
    db.connect()
    db.create_tables()
    db.clear()                     # Очищаем таблицу перед загрузкой
    db.insert_many(documents)      # Массовая вставка

    # ------------------------------------------------------
    # Генерация тестовых срезов для динамики
    # ------------------------------------------------------
    logger.info("Генерация тестовых срезов для динамики...")

    # Используем реальные даты возникновения документов
    cursor = db.connection.cursor()
    cursor.execute("""
        SELECT DISTINCT realization_date
        FROM documents
        WHERE realization_date IS NOT NULL
        ORDER BY realization_date
    """)
    all_dates = [row[0] for row in cursor.fetchall()]

    if all_dates and len(all_dates) > 1:
        total = len(all_dates)
        # Выбираем первую, последнюю и промежуточные даты (всего 3-4 точки)
        indices = [0]
        if total > 1:
            indices.append(total - 1)
        if total > 2:
            indices.append(total // 2)
        indices = sorted(set(indices))

        selected_dates = [all_dates[i] for i in indices if i < total]

        # Исключаем основную дату отчёта (snapshot_date)
        main_snapshot = db.connection.cursor().execute(
            "SELECT MAX(snapshot_date) FROM documents"
        ).fetchone()[0]
        selected_dates = [d for d in selected_dates if d != main_snapshot]

        if selected_dates:
            logger.info("Выбраны даты для срезов: %s", selected_dates)

            for test_date in selected_dates:
                cursor = db.connection.cursor()
                cursor.execute("""
                    INSERT INTO documents (
                        source, organization, sales_department, department, team, manager,
                        contractor, contract, document_name, realization_date, plan_payment_date,
                        days_to_plan, amount, debt_total, debt_share, overdue, days_overdue, our_debt,
                        snapshot_date
                    )
                    SELECT
                        source, organization, sales_department, department, team, manager,
                        contractor, contract, document_name, realization_date, plan_payment_date,
                        days_to_plan, amount, debt_total, debt_share, overdue, days_overdue, our_debt,
                        ?
                    FROM documents
                    WHERE snapshot_date = ?
                """, (test_date, main_snapshot))
                db.connection.commit()
                logger.info(f"Добавлен тестовый срез {test_date}")
        else:
            logger.info("Нет подходящих дат для срезов, пропускаем.")
    else:
        # Fallback: если нет дат реализации, используем стандартные
        logger.warning("Нет дат реализации. Используем стандартные даты.")
        test_dates = ['2026-07-06', '2026-07-07']
        main_snapshot = db.connection.cursor().execute(
            "SELECT MAX(snapshot_date) FROM documents"
        ).fetchone()[0]

        for test_date in test_dates:
            if test_date != main_snapshot:
                cursor = db.connection.cursor()
                cursor.execute("""
                    INSERT INTO documents (
                        source, organization, sales_department, department, team, manager,
                        contractor, contract, document_name, realization_date, plan_payment_date,
                        days_to_plan, amount, debt_total, debt_share, overdue, days_overdue, our_debt,
                        snapshot_date
                    )
                    SELECT
                        source, organization, sales_department, department, team, manager,
                        contractor, contract, document_name, realization_date, plan_payment_date,
                        days_to_plan, amount, debt_total, debt_share, overdue, days_overdue, our_debt,
                        ?
                    FROM documents
                    WHERE snapshot_date = ?
                """, (test_date, main_snapshot))
                db.connection.commit()
                logger.info(f"Добавлен тестовый срез {test_date}")

    # ------------------------------------------------------
    # Выводим статистику по последнему срезу (актуальные данные)
    # ------------------------------------------------------
    logger.info("-" * 70)

    # Получаем последнюю дату среза
    cursor = db.connection.cursor()
    cursor.execute("SELECT MAX(snapshot_date) as max_date FROM documents")
    last_snapshot = cursor.fetchone()['max_date']

    # Считаем показатели только для последней даты
    cursor.execute("""
        SELECT 
            COUNT(*) as cnt,
            COALESCE(SUM(debt_total), 0) as total_debt,
            COALESCE(SUM(amount), 0) as total_amount,
            COUNT(DISTINCT manager) as managers,
            COUNT(DISTINCT contractor) as contractors
        FROM documents
        WHERE snapshot_date = ?
    """, (last_snapshot,))
    row = cursor.fetchone()

    logger.info("Данные на последнюю дату среза: %s", last_snapshot)
    logger.info("Документов в БД: %s", row['cnt'])
    logger.info("Менеджеров: %s", row['managers'])
    logger.info("Контрагентов: %s", row['contractors'])
    logger.info("Общий долг: %.2f", row['total_debt'])
    logger.info("Сумма реализации: %.2f", row['total_amount'])
    logger.info("-" * 70)

    db.close()
    logger.info("Работа завершена.")


if __name__ == "__main__":
    main()