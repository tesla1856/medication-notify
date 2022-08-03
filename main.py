import os

from threading import Thread

from telegram import Update  #upm package(python-telegram-bot)
from telegram.ext import Updater, CommandHandler, CallbackContext, JobQueue  #upm package(python-telegram-bot)

from datetime import time, datetime, timedelta
from pytz import timezone

from flask import render_template
from flask import Flask

from replit import db

import requests

TZ = timezone('Europe/Moscow')
EDA_START_TIME_MSK = time(9, 0)
EDA_END_TIME_MSK = time(23, 1)
EDA_PERIOD_SEC = 3 * 3600

app = Flask(__name__)

BOT_START_DATE = datetime.now(TZ)


@app.route('/')
def home(page=None):
    #print("check: " + datetime.now(TZ).strftime("%d.%m.%y %H:%M") + " -> " +
    #      BOT_START_DATE.strftime("%d.%m.%y %H:%M"))
    return render_template('home.html',
                           start_dt=BOT_START_DATE.strftime("%d.%m.%y %H:%M"))


def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Привет! Отправь /eda для напоминания о еде. `/eda stop` для отмены напоминаний'
    )


def remove_job_if_exists(name: str, job_queue: JobQueue) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
        del db["job:" + job.name]
    return True


def alarm(context: CallbackContext) -> None:
    ctx = context.job.context
    job_name = ctx['job_name']
    chat_id = ctx['chat_id']
    if 'eda' in job_name:
        del db[f"job:{job_name}"]
        due = create_job_eda(context.job_queue, job_name, chat_id)
        msg = '🥣 Пора есть, следующее напоминание: ' + due.strftime("%H:%M")

    anek = ""
    try:
        resp = requests.get('http://rzhunemogu.ru/RandJSON.aspx?CType=1')
        anek = resp.text.replace('{"content":"', '').replace('"}', '')
    except:
        None
    if anek:
        msg += f'\n\n===\n{anek}'

    context.bot.send_message(chat_id, msg)


def create_job_eda(job_queue: JobQueue, job_name: str,
                   chat_id: int, due: datetime = None) -> datetime:
    remove_job_if_exists(job_name, job_queue)
    if not due:
        now = datetime.now(TZ)
        due = now + timedelta(seconds=EDA_PERIOD_SEC)
        if due > TZ.localize(datetime.combine(now, EDA_END_TIME_MSK)):
            due = TZ.localize(
                datetime.combine(now + timedelta(days=1), EDA_START_TIME_MSK))
    # print({'due': due.isoformat(), 'chat_id': chat_id, 'job_name': job_name})
    job_queue.run_once(alarm,
                       due,
                       name=job_name,
                       context={
                           'chat_id': chat_id,
                           'job_name': job_name
                       })
    db[f"job:{job_name}"] = {
        'due': datetime.strftime(due,"%d%m%y%H%M%S"),
        'chat_id': chat_id,
        'job_name': job_name
    }
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
        due = create_job_eda(context.job_queue, job_name, chat_id)
        update.effective_message.reply_text(
            f'Напоминание установлено на {due.strftime("%H:%M")}')


def unset(update: Update, context: CallbackContext, job_name: str) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(job_name, context.job_queue)
    text = "Напоминания отменены!" if job_removed else "Никаких напоминаний и не было запланировано."
    context.bot.send_message(chat_id, text)


def timer_list(update: Update, context: CallbackContext,
               job_name: str) -> None:
    chat_id = update.message.chat_id
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    l = []
    for job in current_jobs:
        l.append(job.next_t.astimezone(TZ).strftime("%H:%M"))
    context.bot.send_message(chat_id, text="Напоминания: " + ", ".join(l))


def run():
    app.run(host='0.0.0.0', port=8080)


def jobs_up_from_db(job_queue: JobQueue):
    for d in db.prefix("job:"):
        if 'eda' in db[d]["job_name"]:
            print("start job ", db[d])
            create_job_eda(job_queue, db[d]["job_name"], db[d]["chat_id"], TZ.localize(datetime.strptime(db[d]["due"],"%d%m%y%H%M%S")))


def main():
    print("Start")
    updater = Updater(os.getenv("TOKEN"))

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", help_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("eda", set_eda_timer))

    #dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), log))
    jobs_up_from_db(updater.job_queue)

    updater.start_polling()

    t = Thread(target=run)
    t.start()
    updater.idle()
    #app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
