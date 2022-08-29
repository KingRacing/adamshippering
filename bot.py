import logging
import os
import json
import math
import random
import schedule
import time
import threading
import redis
from telegram.ext import Updater, CommandHandler, CallbackContext, Filters
from telegram import Update
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

TOKEN = os.getenv('5478645762:AAH4pRIpRCA6ky2ZoF-VeFO5cV6k28CAcj8')


deadline = datetime(datetime.today().year, datetime.today().month, datetime.today().day, hour=14)
VICTORY = 30
victory_text = ''

listen = ['default']
redis_url = os.getenv('redis-17314.c270.us-east-1-3.ec2.cloud.redislabs.com:17314')
PORT = int(os.environ.get('PORT', 5000))
        

def setup_shippering_db(update: Update, context: CallbackContext):

    if update.effective_chat.type != 'private':

        chat_administrators = context.bot.get_chat_administrators(chat_id=update.effective_chat.id)
        chat_ship = {}
        chat_ship[update.effective_chat.id] = {}
        chat_ship[update.effective_chat.id]['shippable'] = True
        chat_ship[update.effective_chat.id]['user_counters'] = {}
        for chat_member in chat_administrators:
            chat_ship[update.effective_chat.id]['user_counters'][chat_member.user.id] = 0
        chat_ship[update.effective_chat.id]['last_couple'] = []
        # set a single key containing an object like string, if the key doesn't exist already
        redis_server.setnx(str(update.effective_chat.id), json.dumps(chat_ship[update.effective_chat.id]))


def victory(update: Update, context: CallbackContext, winner1, winner2=None):
    first_name1 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                              user_id=winner1).user.first_name
    last_name1 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                             user_id=winner1).user.last_name
    if winner2:
        first_name2 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                  user_id=winner2).user.first_name
        last_name2 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                 user_id=winner2).user.last_name

    text = f'<a href="tg://user?id={winner1}">{first_name1} {last_name1}</a> ' if last_name1 else f'<a href="tg://user?id={winner1}">{first_name1}</a> '
    if winner2:
        text += f'e <a href="tg://user?id={winner2}">{first_name2} {last_name2}</a> mendapatkan {VICTORY} pasangan. \nSelamat 👋' \
            if last_name2 else f'e <a href="tg://user?id={winner2}">{first_name2}</a>' \
                                f'Telah dapat {VICTORY} pasangan. \nSelamat 👋'
    else:
        text += f'Mendapatkan {VICTORY} Pasangan. \nSelamat 👋'

    text += 'Jika Anda ingin memulai dari awal, gunakan /reset'

    return text


def start(update: Update, context: CallbackContext):

    setup_shippering_db(update, context)

    logging.info(update.effective_chat.id)
    text = '😄 Halo! Eiko Shippering adalah bot yang akan memilih pasangan dalam obrolan Anda.\n\n ' \
            'Gunakan /help untuk info lebih lanjut.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def help(update: Update, context: CallbackContext):
    text = '💕 Eiko shippering adalah bot yang akan memilih pasangan dalam obrolan Anda. ' \
           'Setiap orang yang menulis pesan di chat Anda akan ditambahkan ke daftar kandidat' \
           'untuk beberapa hari. Tambahkan bot ini ke obrolan Anda ' \
           'dan tunggu sampai mengumpulkan kandidat yang cukup sebelum mengirim perintah.\n' \
           '/chelp: pesan ini\n' \
           '/shipping: Memilih Pasangan secara acak\n' \
           '/top: Rank Pasangan\n' \
           '/last: Pasangan terakhir yang dipilih\n' \
           '/reset: menghapus setiap pasangan'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')


def shipping(update: Update, context: CallbackContext):
    global victory_text

    setup_shippering_db(update, context)

    counters = redis_server.get(str(update.effective_chat.id))
    counters = json.loads(counters)

    now = datetime.utcnow()
    this_moment = datetime(datetime.today().year, datetime.today().month, datetime.today().day,
                           hour=now.hour, minute=now.minute, second=now.second,
                           microsecond=now.microsecond)
    last_update = datetime.strptime(counters['last_update'], '%Y-%m-%d %H:%M:%S.%f')
    logging.info('TEMPI')
    logging.info(last_update)
    logging.info(deadline)
    logging.info(now)
    # we can either ship another time if the flag has been updated
    # or if the scheduler missed it, which, means that the flag remained false
    # and the last update was before the deadline, and now we got past the deadline
    if (counters['shippable']) or (not counters['shippable'] and last_update < deadline < this_moment):
        ship1, ship2 = tuple(
            random.sample(range(0, len(counters['user_counters'].keys())), k=2))

        # find the id whose index in the key list is the rng number
        user_id_shipped1 = list(counters['user_counters'].items())[ship1][0]
        user_id_shipped2 = list(counters['user_counters'].items())[ship2][0]

        counters['user_counters'][user_id_shipped1] += 1
        counters['user_counters'][user_id_shipped2] += 1
        counters['last_couple'].append(user_id_shipped1)
        counters['last_couple'].append(user_id_shipped2)
        if len(counters['last_couple']) > 10:
            counters['last_couple'].pop(0)
            counters['last_couple'].pop(0)
        # if someone reached 30, winner
        winners = []
        if counters['user_counters'][user_id_shipped1] >= VICTORY:
            winners.append(user_id_shipped1)
        if counters['user_counters'][user_id_shipped2] >= VICTORY:
            winners.append(user_id_shipped2)
        if len(winners) > 0:
            victory_text = victory(update, context, *winners)

        now = datetime.utcnow()
        counters['last_update'] = str(datetime(datetime.today().year, datetime.today().month, datetime.today().day,
                                               hour=now.hour, minute=now.minute, second=now.second,
                                               microsecond=now.microsecond))

    else:
        # if the ship for today is picked, only need to pop from the stack
        user_id_shipped2 = counters['last_couple'][-1]
        user_id_shipped1 = counters['last_couple'][-2]
    logging.info('LANGKAH DI SINI')
    # find out how much needs to be waited to ship again
    logging.info('BATAS WAKTU SAAT INI')
    logging.info(str(deadline.date()))
    logging.info(str(deadline.time()))

    logging.info('DEADLINE DAN JADWAL HARUS BERSAMAAN')
    logging.info(str(schedule.next_run()))
    now = datetime.utcnow()

    logging.info('SEKARANG')
    logging.info(str(now.date()))
    logging.info(str(now.time()))

    time_to_wait = deadline - now
    total_seconds = time_to_wait.seconds + math.floor(round(time_to_wait.microseconds / 1000000, 1))
    hours, remaining_seconds = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remaining_seconds, 60)

    first_name1 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                              user_id=user_id_shipped1).user.first_name
    last_name1 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                             user_id=user_id_shipped1).user.last_name
    first_name2 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                              user_id=user_id_shipped2).user.first_name
    last_name2 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                           user_id=user_id_shipped2).user.last_name
    text = ''
    if victory_text:
        text += victory_text + '\n\n'
    text += 'Pasangan hari ini:\n\n' if counters['shippable'] else 'Pasangan hari ini telah dipilih:\n\n'
    if counters['shippable']:
        text += f'<a href="tg://user?id={user_id_shipped1}">{first_name1} {last_name1}</a> ' if last_name1 else f'<a href="tg://user?id={user_id_shipped1}">{first_name1}</a>'
        text += f'+ <a href="tg://user?id={user_id_shipped2}">{first_name2} {last_name2}</a> = ❤\n' if last_name2 else f'+ <a href="tg://user?id={user_id_shipped2}">{first_name2}</a> = ❤\n'
    else:
        text += f'{first_name1} {last_name1} ' if last_name1 else f'{first_name1}'
        text += f'+ {first_name2} {last_name2} = ❤\n' if last_name2 else f'+ {first_name2} = ❤\n'

    text += f'Pasangan baru hari ini dapat dipilih dari {hours} jam, {minutes} menit {seconds} detik'

    counters['shippable'] = False
    # write updates
    redis_server.set(str(update.effective_chat.id), json.dumps(counters))
    context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')


def last_ship(update: Update, context: CallbackContext):
    setup_shippering_db(update, context)

    text = 'Pasangan yang dipilih dalam beberapa hari terakhir:\n\n'

    counters = redis_server.get(str(update.effective_chat.id))
    counters = json.loads(counters)

    last_couple_stack = counters['last_couple']
    for i in range(0, len(counters['last_couple']), 2):
        user_id_shipped2 = last_couple_stack.pop()
        user_id_shipped1 = last_couple_stack.pop()
        first_name1 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                  user_id=user_id_shipped1).user.first_name
        last_name1 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                 user_id=user_id_shipped1).user.last_name
        first_name2 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                  user_id=user_id_shipped2).user.first_name
        last_name2 = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                 user_id=user_id_shipped2).user.last_name
        text += '❤ = '
        text += f'{first_name1} {last_name1} + ' if last_name1 else f'{first_name1} + '
        text += f'{first_name2} {last_name2}\n' if last_name2 else f'{first_name2}\n'

    context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')


def top_ship(update: Update, context: CallbackContext):
    setup_shippering_db(update, context)

    text = 'Top Pasangan (yang paling banyak dipilih):\n\n'

    counters = redis_server.get(str(update.effective_chat.id))
    counters = json.loads(counters)

    id_items = list(counters['user_counters'].items())
    ranking = sorted(id_items, key=lambda id_counter : id_counter[1], reverse=True)
    i = 1
    for rank in ranking:
        first_name = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                  user_id=rank[0]).user.first_name
        last_name = context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                 user_id=rank[0]).user.last_name
        text += f'{i}. '
        text += f'{first_name} {last_name} — <b>{rank[1]}</b>\n' if last_name else f'{first_name} — <b>{rank[1]}</b>\n'
        i += 1
    context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')


def restart_counter(update: Update):
    counters = redis_server.get(str(update.effective_chat.id))
    counters = json.loads(counters)

    for user_id in counters['user_counters']:
        counters['user_counters'][user_id] = 0
    counters['last_couple'] = []
    counters['shippable'] = True

    redis_server.set(str(update.effective_chat.id), json.dumps(counters))


def reset(update: Update, context: CallbackContext):
    setup_shippering_db(update, context)

    restart_counter(update)
    context.bot.send_message(chat_id=update.effective_chat.id, text='Reset Berhasil', parse_mode='HTML')


def callback_shipping(chat_id):
    global deadline
    deadline += timedelta(days=1)

    logging.info("CALLBACK TIMER")
    logging.info(deadline)
    counters = redis_server.get(str(chat_id))
    counters = json.loads(counters)

    counters['shippable'] = True
    redis_server.set(str(chat_id), json.dumps(counters))


def run_continuously(interval=1):
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    logging.info("THREAD RUNNING")
    return cease_continuous_run


def main():

    updater = Updater(token='5478645762:AAH4pRIpRCA6ky2ZoF-VeFO5cV6k28CAcj8', use_context=True)

    dispatcher = updater.dispatcher
    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('chelp', help)
    ship_handler = CommandHandler('shipping', shipping, Filters.group)
    last_ship_handler = CommandHandler('last', last_ship, Filters.group)
    top_ship_handler = CommandHandler('top', top_ship, Filters.group)
    reset_handler = CommandHandler('reset', reset, Filters.group)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(ship_handler)
    dispatcher.add_handler(last_ship_handler)
    dispatcher.add_handler(top_ship_handler)
    dispatcher.add_handler(reset_handler)

    updater.start_webhook(listen="0.0.0.0",
                          port=int(PORT),
                          url_path=TOKEN)
    updater.bot.setWebhook('https://pasang12.herokuapp.com/' + TOKEN)

    schedule.every().day.at("14:00").do(callback_shipping, -1001188937737)
    run_continuously()

    updater.idle()


if __name__ == '__main__':
    main()
