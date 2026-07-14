"""
============================================================
database.py

Работа с SQLite.

- Создание базы данных.
- Создание таблицы документов.
- Сохранение результатов парсинга.
- Агрегатные запросы для дашборда.

============================================================
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Iterable

from parser import DocumentRecord


logger = logging.getLogger(__name__)


class Database:
    """
    Класс для работы с SQLite.

    Обеспечивает:
    - Подключение к БД
    - Создание таблиц
    - Массовую вставку документов
    - Агрегатные запросы
    """
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        self.connection: sqlite3.Connection | None = None


    def connect(self) -> None:
        """Создаёт подключение к SQLite и устанавливает row_factory = sqlite3.Row."""
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        logger.info("SQLite подключена.")


    def close(self) -> None:
        """Закрывает подключение к БД."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            logger.info("SQLite закрыта.")


    def create_tables(self) -> None:
        """
        Создаёт таблицу documents, если она не существует.

        Поля таблицы соответствуют модели DocumentRecord.
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                organization TEXT,
                sales_department TEXT,
                department TEXT,
                team TEXT,
                manager TEXT,
                contractor TEXT,
                contract TEXT,
                document_name TEXT,
                realization_date DATE,
                plan_payment_date DATE,
                days_to_plan INTEGER,
                amount REAL,
                debt_total REAL,
                debt_share REAL,
                overdue REAL,
                days_overdue INTEGER,
                our_debt REAL,
                snapshot_date DATE
            )
        """)
        self.connection.commit()
        logger.info("Таблица documents создана.")


    def clear(self) -> None:
        """Полностью очищает таблицу documents (удаляет все записи)."""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM documents")
        self.connection.commit()
        logger.info("Таблица очищена.")


    def insert_document(self, document: DocumentRecord) -> None:
        """
        Сохраняет один документ в базу данных.

        Args:
            document: Объект DocumentRecord для вставки
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO documents
            (
                source, organization, sales_department, department, team,
                manager, contractor, contract, document_name,
                realization_date, plan_payment_date, days_to_plan,
                amount, debt_total, debt_share, overdue, days_overdue, our_debt,
                snapshot_date
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                document.source,
                document.organization,
                document.sales_department,
                document.department,
                document.team,
                document.manager,
                document.contractor,
                document.contract,
                document.document_name,
                document.realization_date,
                document.plan_payment_date,
                document.days_to_plan,
                document.amount,
                document.debt_total,
                document.debt_share,
                document.overdue,
                document.days_overdue,
                document.our_debt,
                document.snapshot_date
            )
        )
        self.connection.commit()


    def insert_many(self, documents: Iterable[DocumentRecord]) -> None:
        """
        Сохраняет список документов в базу данных (массовая вставка).

        Args:
            documents: Итерируемый объект с DocumentRecord
        """
        cursor = self.connection.cursor()
        cursor.executemany(
            """
            INSERT INTO documents
            (
                source, organization, sales_department, department, team,
                manager, contractor, contract, document_name,
                realization_date, plan_payment_date, days_to_plan,
                amount, debt_total, debt_share, overdue, days_overdue, our_debt,
                snapshot_date
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    d.source,
                    d.organization,
                    d.sales_department,
                    d.department,
                    d.team,
                    d.manager,
                    d.contractor,
                    d.contract,
                    d.document_name,
                    d.realization_date,
                    d.plan_payment_date,
                    d.days_to_plan,
                    d.amount,
                    d.debt_total,
                    d.debt_share,
                    d.overdue,
                    d.days_overdue,
                    d.our_debt,
                    d.snapshot_date
                )
                for d in documents
            ]
        )
        self.connection.commit()
        logger.info("В базу сохранено %s документов.", cursor.rowcount)


    def count_documents(self) -> int:
        """Возвращает общее количество документов в таблице."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        return cursor.fetchone()[0]


    def get_total_debt(self) -> float:
        """Возвращает общую сумму задолженности (debt_total) по всем документам."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT COALESCE(SUM(debt_total), 0) FROM documents")
        return float(cursor.fetchone()[0])


    def get_total_amount(self) -> float:
        """Возвращает общую сумму реализации (amount) по всем документам."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM documents")
        return float(cursor.fetchone()[0])


    def count_managers(self) -> int:
        """Возвращает количество уникальных менеджеров."""
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT COUNT(DISTINCT manager) FROM documents WHERE manager IS NOT NULL"
        )
        return cursor.fetchone()[0]


    def count_contractors(self) -> int:
        """Возвращает количество уникальных контрагентов."""
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT COUNT(DISTINCT contractor) FROM documents WHERE contractor IS NOT NULL"
        )
        return cursor.fetchone()[0]


    def fetch_all(self) -> list[sqlite3.Row]:
        """
        Возвращает все документы, отсортированные по организации и менеджеру.

        Returns:
            Список строк (sqlite3.Row)
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM documents
            ORDER BY organization, manager
            """
        )
        return cursor.fetchall()