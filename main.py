import os

from telegram import Update  #upm package(python-telegram-bot)
from telegram.ext import Updater, CommandHandler, CallbackContext  #upm package(python-telegram-bot)

from datetime import time, datetime, timedelta
from pytz import timezone

from flask import render_template
from flask import Flask

TZ = timezone('Europe/Moscow')
EDA_START_TIME_MSK = time(9, 0)
EDA_END_TIME_MSK = time(23, 1)
EDA_PERIOD_SEC = 3 * 3600

app = Flask(__name__)


@app.route('/')
def home(page=None):
    return render_template('home.html')


def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Привет! Отправь /eda для напоминания о еде. `/eda stop` для отмены напоминаний'
    )


def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def alarm(context: CallbackContext) -> None:
    ctx = context.job.context
    job_name = ctx['job_name']
    chat_id = ctx['chat_id']
    due = create_job(context, job_name, chat_id)
    context.bot.send_message(
        chat_id,
        f'🥣 Пора есть, следующее напоминание: {due.strftime("%H:%M:%S")}'
    )


def create_job(context: CallbackContext, job_name: str,
               chat_id: int) -> datetime:
    remove_job_if_exists(job_name, context)
    now = datetime.now(TZ)
    due = now + timedelta(seconds=EDA_PERIOD_SEC)
    if due > TZ.localize(datetime.combine(now, EDA_END_TIME_MSK)):
        due = TZ.localize(
            datetime.combine(now + timedelta(days=1), EDA_START_TIME_MSK))
    context.job_queue.run_once(alarm,
                               due,
                               name=job_name,
                               context={
                                   'chat_id': chat_id,
                                   'job_name': job_name
                               })
    return due


def set_eda_timer(update: Update,
                  context: CallbackContext,
                  text: str = "") -> None:
    chat_id = update.effective_message.chat_id
    job_name = "eda_" + str(chat_id)
    cmd = context.args[0] if len(context.args) > 0 else ''

    if cmd in ['stop']:
        unset(update, context, job_name)

    elif cmd in ['show', 'list']:
        timer_list(update, context, job_name)

    else:
        due = create_job(context, job_name, chat_id)
        update.effective_message.reply_text(
            f'Напоминание установлено на {due.strftime("%H:%M:%S")}')


def unset(update: Update, context: CallbackContext, job_name: str) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(job_name, context)
    text = "Напоминания отменены!" if job_removed else "Никаких напоминаний и не было запланировано."
    context.bot.send_message(chat_id, text)


def timer_list(update: Update, context: CallbackContext,
               job_name: str) -> None:
    chat_id = update.message.chat_id
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    l = []
    for job in current_jobs:
        l.append(job.next_t.astimezone(TZ).strftime("%H:%M:%S"))
    context.bot.send_message(chat_id, text="Напоминания: " + ", ".join(l))


def main():
    updater = Updater(os.getenv("TOKEN"))

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", help_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("eda", set_eda_timer))

    #    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), log))

    updater.start_polling()

    #updater.idle()
    app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
