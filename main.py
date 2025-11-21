import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import BOT_TOKEN, MANAGERS_IDS, EMPLOYEES_IDS
import database as db

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def is_manager(user_id):
    return user_id in MANAGERS_IDS


def is_employee(user_id):
    return user_id in EMPLOYEES_IDS


async def generate_report_text():
    """Генерирует текст отчета на основе данных из БД."""
    stats = await db.get_today_stats()

    revenue = stats['cash'] + stats['card'] + stats['qr']
    total = revenue - stats['refund']

    report = (
        f"📅 <b>Отчёт за {db.date.today()}</b>\n\n"
        f"🧾 Чеки: {int(stats['checks'])}\n"
        f"💰 <b>Выручка: {revenue:,.2f}</b>\n"
        f"├ Нал: {stats['cash']:,.2f}\n"
        f"├ Карта: {stats['card']:,.2f}\n"
        f"└ QR: {stats['qr']:,.2f}\n\n"
        f"🔙 Возвраты: {stats['refund']:,.2f}\n"
        f"🏁 <b>ИТОГ ДНЯ: {total:,.2f}</b>"
    )
    return report


# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id

    if is_employee(user_id):
        text = (
            "👋 Привет, Сотрудник!\n\n"
            "<b>Команды для ввода данных:</b>\n"
            "/cash [сумма] - Добавить наличные\n"
            "/card [сумма] - Добавить карту\n"
            "/qr [сумма] - Добавить QR/перевод\n"
            "/refund [сумма] - Добавить возврат\n"
            "/checks [кол-во] - Добавить чеки\n\n"
            "📤 Отправка отчета:\n"
            "/report - Сдать смену"
        )
        await message.answer(text, parse_mode="HTML")

    elif is_manager(user_id):
        text = (
            "👋 Привет, Руководитель!\n\n"
            "<b>Команды управления:</b>\n"
            "/get_report - Получить текущий отчёт\n"
            "/reset - Сбросить данные дня (начать новую смену)"
        )
        await message.answer(text, parse_mode="HTML")

    else:
        await message.answer("⛔ Доступ запрещен. Обратитесь к администратору.")


# --- КОМАНДЫ СОТРУДНИКА ---

# Функция для обработки финансовых команд (уменьшает дублирование кода)
async def process_finance_command(message: Message, command: CommandObject, col_name: str, data_type=float):
    if not is_employee(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только сотрудникам.")
        return

    if command.args is None:
        await message.answer(f"⚠ Ошибка ввода. Пример: /{command.command} 100")
        return

    try:
        # Заменяем запятую на точку, если пользователь ошибся
        value = data_type(command.args.replace(',', '.'))

        if value < 0:
            await message.answer("⚠ Сумма должна быть положительной.")
            return

        await db.add_data(col_name, value)

        # Подтверждение
        emojis = {
            "cash": "💵", "card": "💳", "qr": "📱", "refund": "🔙", "checks": "🧾"
        }
        await message.answer(f"{emojis.get(col_name, '✅')} Принято: {value}")

    except ValueError:
        await message.answer("⚠ Ошибка: введите корректное число.")


@dp.message(Command("cash"))
async def cmd_cash(message: Message, command: CommandObject):
    await process_finance_command(message, command, "cash")


@dp.message(Command("card"))
async def cmd_card(message: Message, command: CommandObject):
    await process_finance_command(message, command, "card")


@dp.message(Command("qr"))
async def cmd_qr(message: Message, command: CommandObject):
    await process_finance_command(message, command, "qr")


@dp.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject):
    await process_finance_command(message, command, "refund")


@dp.message(Command("checks"))
async def cmd_checks(message: Message, command: CommandObject):
    await process_finance_command(message, command, "checks", data_type=int)


@dp.message(Command("report"))
async def cmd_report_submit(message: Message):
    if not is_employee(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        return

    report_text = await generate_report_text()

    # Отправка отчета всем руководителям
    count = 0
    for admin_id in MANAGERS_IDS:
        try:
            await bot.send_message(admin_id, f"📩 <b>Отчет от сотрудника:</b>\n\n{report_text}", parse_mode="HTML")
            count += 1
        except Exception as e:
            logging.error(f"Не удалось отправить отчет руководителю {admin_id}: {e}")

    if count > 0:
        await message.answer("✅ Отчёт успешно отправлен руководителю.")
    else:
        await message.answer("⚠ Ошибка отправки. Руководитель не найден или заблокировал бота.")


# --- КОМАНДЫ РУКОВОДИТЕЛЯ ---

@dp.message(Command("get_report"))
async def cmd_get_report(message: Message):
    if not is_manager(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        return

    report_text = await generate_report_text()
    await message.answer(report_text, parse_mode="HTML")


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    if not is_manager(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        return

    await db.reset_today_stats()
    await message.answer("🔄 <b>Смена сброшена.</b> Данные за сегодня обнулены.", parse_mode="HTML")


# --- ЗАПУСК ---

async def main():
    # Инициализация БД при старте
    await db.init_db()
    print("Бот запущен...")
    # Удаляем вебхуки и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")



