#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import mysql.connector
import requests
from lxml import html
from datetime import datetime, time
from telegram import Bot, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, \
    Updater, CallbackContext, Filters, messagequeue
from telegram.utils.request import Request

from bot.messagequeuebot import MQBot
from chat import chat, conversation, tools, profile
from chat.config import bot_token, bot_use_message_queue, log_format, log_level, \
    mysql_host, mysql_port, mysql_user, mysql_password, mysql_db
from quest.data import quests, quest_pokemon_list, quest_items_list, shiny_pokemon_list, get_pokedex_id
from quest.quest import Quest

# enable logging
logging.basicConfig(format=log_format, level=log_level)
logger = logging.getLogger(__name__)

latest_quest_scan = 0


def load_quests(context: CallbackContext):
    db = mysql.connector.connect(
        host=mysql_host,
        port=mysql_port,
        user=mysql_user,
        passwd=mysql_password,
        database=mysql_db
    )

    global latest_quest_scan

    midnight = datetime.combine(datetime.today(), time.min).timestamp()

    # make sure only quests from today get loaded
    if midnight > latest_quest_scan:
        latest_quest_scan = midnight

    cursor = db.cursor()
    cursor.execute("SELECT "
                   "ps.pokestop_id,"
                   "ps.name, "
                   "ps.latitude, "
                   "ps.longitude, "
                   "q.quest_timestamp, "
                   "q.quest_pokemon_id, "
                   "q.quest_item_id, "
                   "q.quest_item_amount, "
                   "q.quest_template "
                   "FROM trs_quest as q "
                   "LEFT JOIN pokestop as ps "
                   "ON q.GUID = ps.pokestop_id "
                   "WHERE q.quest_timestamp >= %s "
                   "AND q.quest_stardust = 0 "
                   "ORDER BY q.quest_timestamp DESC",
                   (latest_quest_scan, ))

    result = cursor.fetchall()

    db.close()

    for (stop_id, stop_name, latitude, longitude, timestamp, pokemon_id, item_id, item_amount, task) in result:

        # skip quest if older than the existing quest entry
        if stop_id in quests and quests[stop_id].timestamp > timestamp:
            continue

        # remember quest rewards
        if pokemon_id != 0 and pokemon_id not in quest_pokemon_list:
            quest_pokemon_list.append(pokemon_id)
        if item_id != 0 and item_id not in quest_items_list:
            quest_items_list.append(item_id)

        # create new quest object
        quests[stop_id] = Quest(stop_id=stop_id,
                                stop_name=stop_name,
                                latitude=latitude,
                                longitude=longitude,
                                timestamp=timestamp,
                                pokemon_id=pokemon_id,
                                item_id=item_id,
                                item_amount=item_amount,
                                task=task)

        if timestamp > latest_quest_scan:
            latest_quest_scan = timestamp + 1

    quest_pokemon_list.sort()
    quest_items_list.sort()

    logger.info(f"{len(result)} new quests loaded from DB. Total quest count: {len(quests)}")


def clear_quests(context: CallbackContext):
    """Clears all quests"""
    global latest_quest_scan

    # set last quest scan to midnight
    latest_quest_scan = datetime.combine(datetime.today(), time.min).timestamp()

    quests.clear()

    logger.info("All quests cleared.")


def load_shinies(context: CallbackContext):
    """Load all shiny pokemon"""
    address = 'https://www.p337.info/pokemongo/pages/shiny-release-dates/'
    raw = requests.get(address)
    data = html.fromstring(raw.content)
    tr_elements = data.xpath('//tr//div[@class="sh_name"]/b/text()')

    shiny_pokemon_list.clear()

    for i in range(0, len(tr_elements)):
        dex_id = get_pokedex_id('en', tr_elements[i].replace(' Family', '').replace(' M', '♂').replace(' F', '♀'))
        if dex_id > 0:
            shiny_pokemon_list.append(dex_id)

    shiny_pokemon_list.sort()


def error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(f'Update "{update}" caused error "{context.error}"')


def main():
    logger.info("Starting Bot.")

    # load all profiles
    profile.load_profiles()

    # request object to bot
    request = Request(con_pool_size=8)

    # use message queue bot version
    if bot_use_message_queue:
        logger.info("Using MessageQueue to avoid flood limits.")
        # enable message queue with production limits
        msg_queue = messagequeue.MessageQueue(all_burst_limit=29, all_time_limit_ms=1017,
                                              group_burst_limit=20, group_time_limit_ms=60000)
        # create a message queue bot
        bot = MQBot(bot_token, request=request, msg_queue=msg_queue)
    # use regular bot
    else:
        logger.info("Using no MessageQueue. You may run into flood limits.")
        # use the default telegram bot (without message queue)
        bot = Bot(bot_token, request=request)

    # create the EventHandler and pass it the bot's instance
    updater = Updater(bot=bot, use_context=True)

    # jobs
    job_queue = updater.job_queue
    job_queue.run_daily(callback=clear_quests, time=time(hour=0, minute=0, second=0))
    job_queue.run_repeating(callback=load_quests, interval=300, first=0)
    job_queue.run_daily(callback=load_shinies, time=time(hour=0, minute=0, second=0))
    job_queue.run_once(callback=load_shinies, when=0)

    # get the dispatcher to register handlers
    dp = updater.dispatcher

    # overview
    dp.add_handler(CommandHandler(callback=chat.start, command='start'))
    dp.add_handler(CallbackQueryHandler(callback=chat.start, pattern='^overview'))

    # settings
    dp.add_handler(CallbackQueryHandler(chat.settings, pattern='^settings'))

    # info section
    dp.add_handler(CallbackQueryHandler(chat.info, pattern='^info'))

    # delete data
    dp.add_handler(CallbackQueryHandler(chat.delete_data, pattern='^delete_data'))

    # select area conversation
    conversation_handler_select_area = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback=conversation.select_area,
                                           pattern='^select_area$', pass_user_data=True)],
        states={
            # receive location, ask for radius
            conversation.STEP0: [MessageHandler(callback=conversation.set_quest_center_point,
                                                filters=Filters.all,
                                                pass_user_data=True)],
            # receive radius
            conversation.STEP1: [MessageHandler(callback=conversation.set_quest_radius,
                                                filters=Filters.all,
                                                pass_user_data=True)]
        },
        # fallback to overview
        fallbacks=[CallbackQueryHandler(callback=chat.start, pattern='^back_to_overview', pass_user_data=True)],
        allow_reentry=True
    )
    dp.add_handler(conversation_handler_select_area)

    # choose quest conversation
    conversation_handler_choose_quest = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback=conversation.choose_quest_type,
                                           pattern="^choose_quest_type$",
                                           pass_user_data=True)],
        states={
            # receive quest type, ask for quest
            conversation.STEP0: [CallbackQueryHandler(callback=conversation.choose_pokemon,
                                                      pattern="^choose_pokemon",
                                                      pass_user_data=True),
                                 CallbackQueryHandler(callback=conversation.choose_item,
                                                      pattern="^choose_item",
                                                      pass_user_data=True),
                                 CallbackQueryHandler(callback=conversation.choose_task,
                                                      pattern="^choose_task",
                                                      pass_user_data=True)],
            conversation.STEP1: [],
            conversation.STEP2: [],
            conversation.STEP3: [],
            conversation.STEP4: []
        },
        fallbacks=[CallbackQueryHandler(callback=chat.start, pattern='^back_to_overview', pass_user_data=True)],
        allow_reentry=True
    )
    dp.add_handler(conversation_handler_choose_quest)

    # hunt quest conversation
    conversation_handler_start_hunt = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback=conversation.start_hunt,
                                           pattern="^start_hunt",
                                           pass_user_data=True)],
        states={
            # receive start location, send quest
            conversation.STEP0: [MessageHandler(callback=conversation.set_start_location,
                                                filters=Filters.all,
                                                pass_user_data=True)],
            conversation.STEP1: [CallbackQueryHandler(callback=conversation.quest_done,
                                                      pattern="^quest_done",
                                                      pass_user_data=True),
                                 CallbackQueryHandler(callback=conversation.defer_quest,
                                                      pattern="^defer_quest",
                                                      pass_user_data=True),
                                 CallbackQueryHandler(callback=conversation.end_hunt,
                                                      pattern="^end_hunt",
                                                      pass_user_data=True)]
        },
        fallbacks=[CallbackQueryHandler(callback=chat.start, pattern='^back_to_overview', pass_user_data=True)],
        allow_reentry=True
    )
    dp.add_handler(conversation_handler_start_hunt)

    # catch-all handler that just logs messages
    dp.add_handler(MessageHandler(callback=tools.dummy_callback, filters=Filters.all))
    dp.add_handler(CallbackQueryHandler(callback=tools.dummy_callback, pattern=".*"))

    # log all errors
    dp.add_error_handler(error)

    # start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
