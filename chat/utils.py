import json
import logging
import os
from enum import Enum

from telegram import Update, message as telegram_message, InlineKeyboardMarkup, ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext
from telegram.utils.promise import Promise

from chat.config import msg_folder, log_format, log_level

# enable logging
logging.basicConfig(format=log_format, level=log_level)
logger = logging.getLogger(__name__)

_texts = {}
_languages = []


def load_all_languages():
    """Load all language files"""
    current_directory = os.path.dirname(os.path.realpath(__file__))
    language_directory = 'language'
    language_directory_path = os.path.join(current_directory, language_directory)

    for filename in os.listdir(language_directory_path):
        if filename.endswith(".json"):
            lang_id = filename.replace('.json', '')
            if lang_id not in _languages:
                _languages.append(lang_id)
            if lang_id in _texts:
                continue
            file_path = os.path.join(language_directory_path, filename)
            with open(file=file_path, mode='r', encoding="utf-8") as data:
                _texts[lang_id] = json.load(data)


def get_all_languages():
    """Get a list of supported languages"""
    if not _languages:
        load_all_languages()
    return _languages


def get_text(language, key, format_str=True):
    """Provides simple translation lookup"""

    def remove_format(text):
        """Remove markdown text formatting from string"""
        return text.replace('`', '').replace('_', '').replace('*', '')

    if not _texts:
        load_all_languages()

    # try to access key for requested language
    if language in _texts and key in _texts[language]:
        if format_str:
            return _texts[language][key]
        else:
            return remove_format(_texts[language][key])

    # fallback to german if translation in requested language does not exist
    elif key in _texts['en']:
        if format_str:
            return _texts['en'][key]
        else:
            return remove_format(_texts['en'][key])

    # no translation available
    return "Text not found."


def get_emoji(emoji):
    emojis = {
        "language": "🈯️",
        "language_de": "🇩🇪",
        "language_en": "🇺🇸",
        "overview": "🎮",
        "area": "🌎",
        "location": "📍",
        "radius": "📏",
        "quest": "📜",
        "pokemon": "🐾",
        "shiny": "✨",
        "item": "🍇",
        "task": "🔖",
        "hunt": "🎯️",
        "defer": "⏱",
        "finish": "🏁",
        "congratulation": "🏆",
        "settings": "⚙️",
        "alert": "⏰",
        "info": "ℹ️",
        "warning": "⚠️",
        "back": "🔙",
        "cancel": "❌",
        "checked": "✅️",
        "trash": "🗑",
        "thumb_up": "👍",
        "thumb_down": "👎",
        "privacy": "👁",
        "tos": "📜",
        "contact": "💬",
        "add": "➕",
        "bug": "👻",
        "question_mark": "❓"
    }

    return emojis.get(emoji, emojis.get('question_mark', '?'))


def dummy_callback(update: Update, context: CallbackContext):
    """Callback that just logs messages. Useful for unexpected callbacks."""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    msg = update.effective_message.to_dict()
    # logger.info(f"VALUES: {strip_false(msg, '', ['from'])}")

    logger.info(f"Received unexpected message from {username} ({user_id}) in chat {chat_id}: {msg}")

    try:
        context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except BadRequest as e:
        logger.warning(f"Failed to delete message #{msg_id} in chat #{chat_id}: {e}")


def extract_ids(update):
    """Extract chat_id, msg_id, user_id, username from update or directly from a message"""

    def extract_ids_from_message(message_helper, from_user_helper):
        """Helper function to extract ids from a message"""
        chat_id_helper = None
        msg_id_helper = None
        user_id_helper = None
        username_helper = None

        if hasattr(message_helper, 'chat_id'):
            chat_id_helper = message_helper.chat_id
        if hasattr(message_helper, 'message_id'):
            msg_id_helper = message_helper.message_id
        # if hasattr(message, 'from_user'):
        #    from_user = message.from_user
        if hasattr(from_user_helper, 'id'):
            user_id_helper = from_user_helper.id
        if hasattr(from_user_helper, 'username'):
            username_helper = from_user_helper.username
        return chat_id_helper, msg_id_helper, user_id_helper, username_helper

    chat_id = None
    msg_id = None
    user_id = None
    username = None

    # callback query
    if hasattr(update, 'callback_query') and update.callback_query is not None:
        message = update.callback_query.message
        user = update.effective_user
    # received message
    elif hasattr(update, 'message') and update.message is not None:
        message = update.message
        user = update.effective_user
    # sent message using MQBot
    elif isinstance(update, Promise):
        message = update.result()
        user = message.from_user
    else:
        message = update
        user = update.from_user

    if message is not None:
        (chat_id, msg_id, user_id, username) = extract_ids_from_message(message, user)

    # turn chat id into a string to avoid issues with json auto converting it to string and thus chat_id not matching
    # as key (because it's an int)
    chat_id = str(chat_id)

    logger.debug(f"Extracted ids: {(chat_id, msg_id, user_id, username)}")

    return chat_id, msg_id, user_id, username


def strip_false(obj, parents="", except_keys=None):
    """Convert object to string and remove all empty / logical false values."""

    if except_keys is None:
        except_keys = []

    def strip_false_helper(obj_helper, parents_helper="", except_keys_helper=None):

        if except_keys_helper is None:
            except_keys_helper = []

        # convert object to dict if not of base type, dict or list
        if not isinstance(obj_helper, (int, float, complex, str, dict, list)):
            obj_helper = obj_helper.to_dict()

        text_helper = ""

        # is this a dict?
        if isinstance(obj_helper, dict):
            # parse all items
            for key, value in obj_helper.items():
                # don't parse key if in except list
                if key in except_keys_helper:
                    continue
                # prepend parent and current key to value(s)
                if parents_helper:
                    text_helper += strip_false_helper(value, parents_helper + '.' + key, except_keys_helper)
                # just prepend key
                else:
                    text_helper += strip_false_helper(value, key, except_keys_helper)
        # not a dict. this must be a list or any other base type
        else:
            # don't process empty values
            if obj_helper:
                # add '' to strings
                if isinstance(obj_helper, str):
                    value_str = "'" + obj_helper + "'"
                else:
                    value_str = str(obj_helper)
                text_helper = f"{parents_helper}: {value_str}, "
        return text_helper

    # generate text
    text = strip_false_helper(obj, parents, except_keys)
    # remove last 2 chars which are ', '
    return text[:-2]


def log_message(func):
    """Decorator for logging all message ids to have more control about messages we send and receive."""

    def func_wrapper(update: Update, context: CallbackContext, user_data=None):
        """Wrapper for decorated function"""

        def update_msg_log(chat_id_log, msg_id_log, user_id_log, username_log):
            """Store all messages for a chat in a file"""
            data = {}
            changes_detected = False
            fn = str(chat_id_log) + '.json'
            if not os.path.exists(msg_folder):
                os.makedirs(msg_folder)
            msg_file = os.path.join(msg_folder, fn)
            # read message history
            if os.path.isfile(msg_file):
                with open(msg_file, 'r') as f:
                    data = json.load(f)
            # convert user_id to string to avoid errors
            user_id_log = str(user_id_log)
            # init dict for user
            if user_id_log not in data:
                data[user_id_log] = {}
                changes_detected = True
            # set or update username
            if 'username' not in data[user_id_log] or data[user_id_log]['username'] != username_log:
                data[user_id_log]['username'] = username_log
                changes_detected = True
            # init message list
            if 'messages' not in data[user_id_log]:
                data[user_id_log]['messages'] = []
                changes_detected = True
            # store message
            if msg_id_log not in data[user_id_log]['messages']:
                data[user_id_log]['messages'].append(msg_id_log)
                changes_detected = True
            # save file
            if changes_detected:
                with open(msg_file, 'w+') as f:
                    json.dump(data, f)
            return

        def log_to_logger(update_log, user_id_log, username_log):
            """Unified logger output"""
            chat = update_log.effective_chat
            full_name = update_log.effective_user.full_name
            # inline keyboard command
            if hasattr(update_log, 'callback_query') and update_log.callback_query is not None:
                action = f"button command [{update_log.callback_query.data}]"
            # text command
            else:
                action = f"text command [{update_log.effective_message.text}]"
            # get details for logging
            chat_type = chat.type
            chat_title = chat.title
            if not chat_title and chat_type == 'private':
                chat_title = "Private Chat"

            logger.info(f"Received {action} in '{chat_title}' from {full_name} (@{username_log} / {user_id_log})")

            return

        # extract ids from received message
        (chat_id, msg_id, user_id, username) = extract_ids(update)

        # log received message
        update_msg_log(chat_id, msg_id, user_id, username)

        # log to console
        log_to_logger(update, user_id, username)

        # run wrapped function
        if user_data is None:
            message = func(update, context)
        else:
            message = func(update, context, user_data)

        if isinstance(message, telegram_message.Message):
            # extract ids from sent message
            # noinspection PyTypeChecker
            (chat_id, msg_id, user_id, username) = extract_ids(message)

            # log sent message
            update_msg_log(chat_id, msg_id, user_id, username)

        # return result of wrapped function
        return message

    return func_wrapper


class MessageType(Enum):
    animation, audio, contact, document, game = range(0, 5)
    invoice, location, message, photo, sticker = range(5, 10)
    venue, video, video_note, voice = range(10, 14)


class MessageCategory(Enum):
    main = 1
    location = 2


def message_user(bot, chat_id, chat_data, message_type: MessageType, payload, keyboard, category=None):
    """Send a message of a certain category to the user. Only one message per category is allowed."""

    reply_markup = InlineKeyboardMarkup(keyboard)

    # check if category is set
    if category:
        # check if this category has a message
        if category in chat_data:
            # get message details
            old_message_id = chat_data[category]['message_id']
            old_message_type = chat_data[category]['message_type']

            # only text messages can be edited
            if message_type == MessageType.message and old_message_type == MessageType.message:

                # try to edit message
                try:
                    sent = bot.edit_message_text(text=payload,
                                                 parse_mode=ParseMode.MARKDOWN,
                                                 chat_id=chat_id,
                                                 message_id=old_message_id,
                                                 reply_markup=reply_markup,
                                                 disable_web_page_preview=True)
                # send a new message if editing failed
                except BadRequest as e:

                    # only log unknown errors
                    if not e.message.startswith('Message is not modified'):
                        logger.warning(f"Failed to edit message #{old_message_id} in chat #{chat_id}: {e}")

                    # try to remove old message. editing might have failed due to no new message content
                    try:
                        bot.delete_message(chat_id=chat_id, message_id=old_message_id)
                    except BadRequest as e:
                        logger.warning(f"Failed to delete message #{old_message_id} in chat #{chat_id}: {e}")

                    sent = bot.send_message(text=payload,
                                            parse_mode=ParseMode.MARKDOWN,
                                            chat_id=chat_id,
                                            reply_markup=reply_markup,
                                            disable_web_page_preview=True)

                    # remember the new message id
                    (_, msg_id, _, _) = extract_ids(sent)
                    chat_data[category]['message_id'] = msg_id

                return sent

            # delete old message
            try:
                bot.delete_message(chat_id=chat_id, message_id=old_message_id)
            except BadRequest as e:
                logger.warning(f"Failed to delete message #{old_message_id} in chat #{chat_id}: {e}")
            # delete message reference
            del chat_data[category]

    # send new message
    if message_type == MessageType.message:
        sent = bot.send_message(text=payload,
                                parse_mode=ParseMode.MARKDOWN,
                                chat_id=chat_id,
                                reply_markup=reply_markup,
                                disable_web_page_preview=True)
    elif message_type == MessageType.location:
        sent = bot.send_location(latitude=payload[0],
                                 longitude=payload[1],
                                 chat_id=chat_id,
                                 reply_markup=reply_markup)
    else:
        logger.warning("Failed to send message: Unsupported MessageType.")
        return

    # check if message should be remembered
    if category:
        # get message id
        (_, msg_id, _, _) = extract_ids(sent)
        # ensure category exists
        if category not in chat_data:
            chat_data[category] = {}
        # remember message id and type
        chat_data[category]['message_id'] = msg_id
        chat_data[category]['message_type'] = message_type

    return sent


def delete_message_in_category(bot, chat_id, chat_data, category):
    if category in chat_data:
        message_id = chat_data[category]['message_id']

        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except BadRequest as e:
            logger.warning(f"Failed to delete message #{message_id} for category #{category} in chat #{chat_id}: {e}")

        del chat_data[category]


def job_delete_message(context: CallbackContext):
    chat_id = context.job.context['chat_id']
    message_id = context.job.context['message_id']
    try:
        context.bot.delete_message(chat_id=chat_id,
                                   message_id=message_id)
    except BadRequest as e:
        logger.warning(f"Failed to delete message #{message_id} in chat #{chat_id}: {e}")
