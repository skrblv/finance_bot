import aiosqlite
from datetime import date
from config import DB_NAME


async def init_db():
    """Создает таблицу, если она не существует."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                report_date DATE PRIMARY KEY,
                checks INTEGER DEFAULT 0,
                cash REAL DEFAULT 0.0,
                card REAL DEFAULT 0.0,
                qr REAL DEFAULT 0.0,
                refund REAL DEFAULT 0.0
            )
        """)
        await db.commit()


async def add_data(column: str, value: float):
    """
    Добавляет значение к текущему показателю за сегодняшнюю дату.
    Использует UPSERT (вставка или обновление).
    """
    today = date.today()

    # Проверка на безопасность имени колонки (защита от инъекций)
    allowed_columns = ["checks", "cash", "card", "qr", "refund"]
    if column not in allowed_columns:
        raise ValueError("Недопустимое имя колонки")

    async with aiosqlite.connect(DB_NAME) as db:
        # Пытаемся создать запись на сегодня, если её нет
        await db.execute(
            "INSERT OR IGNORE INTO daily_stats (report_date) VALUES (?)",
            (today,)
        )
        # Обновляем значение (прибавляем новое к старому)
        sql = f"UPDATE daily_stats SET {column} = {column} + ? WHERE report_date = ?"
        await db.execute(sql, (value, today))
        await db.commit()


async def get_today_stats():
    """Получает статистику за сегодня."""
    today = date.today()
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT checks, cash, card, qr, refund FROM daily_stats WHERE report_date = ?",
            (today,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "checks": row[0],
                "cash": row[1],
                "card": row[2],
                "qr": row[3],
                "refund": row[4]
            }
        # Если данных нет, возвращаем нули
        return {"checks": 0, "cash": 0.0, "card": 0.0, "qr": 0.0, "refund": 0.0}


async def reset_today_stats():
    """Сбрасывает данные за сегодня (удаляет строку)."""
    today = date.today()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM daily_stats WHERE report_date = ?", (today,))
        await db.commit()
