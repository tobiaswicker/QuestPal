#!/usr/bin/env python3
import logging
import os
import sys
import traceback
from threading import Thread

import mysql.connector
import requests

from lxml import html
from datetime import datetime, time

from telegram import Bot, Update, InlineKeyboardButton
from telegram.utils.helpers import mention_markdown
from telegram.utils.request import Request
from telegram.ext import CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, \
    Updater, CallbackContext, Filters, messagequeue, PicklePersistence

from bot.messagequeuebot import MQBot

from chat import chat, conversation, utils, profile
from chat.config import bot_token, bot_use_message_queue, bot_provider, bot_devs, \
    mysql_host, mysql_port, mysql_user, mysql_password, mysql_db
from chat.utils import extract_ids, get_text, get_emoji, message_user, MessageType, MessageCategory, notify_devs, \
    set_bot

from quest.data import quests, quest_pokemon_list, quest_items_list, shiny_pokemon_list, get_task_by_id
from quest.quest import Quest

# enable logging
logging.basicConfig(format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
                    level=logging.INFO,
                    handlers=[logging.FileHandler(filename='bot.log', mode='a'),
                              logging.StreamHandler()])
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

    unknown_tasks = {}

    for (stop_id, stop_name, latitude, longitude, timestamp, pokemon_id, item_id, item_amount, task_id) in result:

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
                                task_id=task_id)

        if get_task_by_id('en', task_id) == task_id:
            unknown_tasks[task_id] = quests[stop_id]

        if timestamp > latest_quest_scan:
            latest_quest_scan = timestamp + 1

    if unknown_tasks:
        text = f"{get_emoji('bug')} *Bug Report*\n\n" \
               f"The following tasks are unknown:\n\n"
        # gather unknown tasks
        for quest in unknown_tasks.values():
            text += f"`task: {quest.task_id}\n" \
                    f"pokemon_id: {quest.pokemon_id}\n" \
                    f"item_id: {quest.item_id}\n" \
                    f"item_amount: {quest.item_amount}`\n\n"
        # inform devs
        notify_devs(text=text)

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
    address = 'https://pokemongo.gamepress.gg/pokemon-go-shinies-list'
    raw = requests.get(address)
    data = html.fromstring(raw.content)
    wild_shiny_links = data.xpath("//tr[contains(@class, 'Wild') or contains(@class, 'Research')]//a")

    shiny_pokemon_list.clear()

    for link_tag in wild_shiny_links:
        link = link_tag.attrib['href']
        dex_id = int(link.replace('/pokemon/', '').replace('-alolan', ''))
        if dex_id not in shiny_pokemon_list:
            shiny_pokemon_list.append(dex_id)

    shiny_pokemon_list.sort()


def error(update: Update, context: CallbackContext):
    """Handle Errors caused by Updates."""
    # get traceback
    trace = "".join(traceback.format_tb(sys.exc_info()[2]))

    error_details = ""

    # inform user
    if update:
        if update.effective_message:
            (chat_id, msg_id, user_id, username) = extract_ids(update)
            lang = profile.get_language(context.chat_data) if profile.get_language(context.chat_data) else 'en'
            text = f"{get_emoji('bug')} *{get_text(lang, 'error_occurred_title')}*\n\n" \
                   f"{get_text(lang, 'error_occurred_message').format(provider=bot_provider)}"
            keyboard = [[InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                              callback_data='overview')]]
            message_user(bot=context.bot,
                         chat_id=chat_id,
                         chat_data=context.chat_data,
                         message_type=MessageType.message,
                         payload=text,
                         keyboard=keyboard,
                         category=MessageCategory.main)

        user_obj = update.effective_user
        chat_obj = update.effective_chat

        if user_obj:
            error_details += f' with the user {mention_markdown(user_obj.id, user_obj.first_name)}'

        if chat_obj:
            error_details += f' within the {chat_obj.type} chat _{chat_obj.title}_'
            if chat_obj.username:
                error_details += f' (@{chat_obj.username})'

        # only add the poll id if there is neither a user nor a chat associated with this update
        if not error_details and update.poll:
            error_details += f' with the poll id {update.poll.id}.'

    # construct bug report for devs
    text = f"{get_emoji('bug')} *Bug Report*\n\n" \
           f"The error `{context.error}` happened{error_details}.\n\n" \
           f"Traceback:\n" \
           f"`{trace}`"
    notify_devs(text=text)

    # raise the error again, so the logger module can catch it
    raise


def main():
    def stop_and_restart():
        """Gracefully stop the Updater and replace the current process with a new one"""
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def restart(update: Update, context: CallbackContext):
        update.message.reply_text('Bot is restarting...')
        Thread(target=stop_and_restart).start()

    logger.info("Starting Bot.")

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

    set_bot(bot=bot)

    persistence = PicklePersistence(filename='persistent_data.pickle')

    # create the EventHandler and pass it the bot's instance
    updater = Updater(bot=bot, use_context=True, persistence=persistence)

    # jobs
    job_queue = updater.job_queue
    job_queue.run_daily(callback=clear_quests, time=time(hour=0, minute=0, second=0))
    job_queue.run_repeating(callback=load_quests, interval=300, first=0)
    job_queue.run_daily(callback=load_shinies, time=time(hour=0, minute=0, second=0))
    job_queue.run_once(callback=load_shinies, when=0)

    # get the dispatcher to register handlers
    dp = updater.dispatcher

    # restart handler for devs
    dp.add_handler(CommandHandler('r', restart, filters=Filters.user(user_id=bot_devs)))

    # overview
    dp.add_handler(CommandHandler(callback=chat.start, command='start'))
    dp.add_handler(CallbackQueryHandler(callback=chat.start, pattern='^overview'))

    # settings
    dp.add_handler(CallbackQueryHandler(callback=chat.settings, pattern='^settings'))

    # info section
    dp.add_handler(CallbackQueryHandler(callback=chat.info, pattern='^info'))

    # delete data
    dp.add_handler(CallbackQueryHandler(callback=chat.delete_data, pattern='^delete_data'))

    # select area conversation
    conversation_handler_select_area = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback=conversation.select_area, pattern='^select_area$')],
        states={
            # receive location, ask for radius
            conversation.STEP0: [MessageHandler(callback=conversation.set_quest_center_point, filters=Filters.all)],
            # receive radius
            conversation.STEP1: [MessageHandler(callback=conversation.set_quest_radius, filters=Filters.all)],
            # receive button click, ask for location or radius
            conversation.STEP2: [CallbackQueryHandler(callback=conversation.change_center_point,
                                                      pattern='^change_center_point'),
                                 CallbackQueryHandler(callback=conversation.change_radius, pattern='^change_radius')],
        },
        # fallback to overview
        fallbacks=[CallbackQueryHandler(callback=chat.start, pattern='^back_to_overview')],
        allow_reentry=True,
        persistent=True,
        name="select_area"
    )
    dp.add_handler(conversation_handler_select_area)

    # choose quest conversation
    conversation_handler_choose_quest = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback=conversation.choose_quest_type, pattern="^choose_quest_type$")],
        states={
            # receive quest type, ask for quest
            conversation.STEP0: [CallbackQueryHandler(callback=conversation.choose_pokemon, pattern="^choose_pokemon"),
                                 CallbackQueryHandler(callback=conversation.choose_item, pattern="^choose_item"),
                                 CallbackQueryHandler(callback=conversation.choose_task, pattern="^choose_task")]
        },
        fallbacks=[CallbackQueryHandler(callback=chat.start, pattern='^back_to_overview', pass_user_data=True)],
        allow_reentry=True,
        persistent=True,
        name="choose_quest"
    )
    dp.add_handler(conversation_handler_choose_quest)

    # hunt quest conversation
    conversation_handler_start_hunt = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback=conversation.start_hunt, pattern="^start_hunt")],
        states={
            # receive start location, send quest
            conversation.STEP0: [CallbackQueryHandler(callback=conversation.continue_previous_hunt,
                                                      pattern="^continue_previous_hunt"),
                                 CallbackQueryHandler(callback=conversation.reset_previous_hunt,
                                                      pattern="^reset_previous_hunt")],
            conversation.STEP1: [MessageHandler(callback=conversation.set_start_location, filters=Filters.all)],
            conversation.STEP2: [CallbackQueryHandler(callback=conversation.quest_collected, pattern="^quest_collected"),
                                 CallbackQueryHandler(callback=conversation.quest_skip, pattern="^quest_skip"),
                                 CallbackQueryHandler(callback=conversation.quest_ignore, pattern="^quest_ignore"),
                                 CallbackQueryHandler(callback=conversation.end_hunt, pattern="^end_hunt"),
                                 CallbackQueryHandler(callback=conversation.enqueue_skipped,
                                                      pattern="^enqueue_skipped"),
                                 CallbackQueryHandler(callback=conversation.continue_hunt, pattern="^continue_hunt"),
                                 CallbackQueryHandler(callback=conversation.process_hint, pattern="^hint")]
        },
        fallbacks=[CallbackQueryHandler(callback=chat.start, pattern='^back_to_overview')],
        allow_reentry=True,
        persistent=True,
        name="start_hunt"
    )
    dp.add_handler(conversation_handler_start_hunt)

    # catch-all handler that just logs messages
    dp.add_handler(MessageHandler(callback=utils.dummy_callback, filters=Filters.all))
    dp.add_handler(CallbackQueryHandler(callback=utils.dummy_callback, pattern=".*"))

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
