import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import CallbackContext

from chat import conversation
from chat.profile import get_language, set_language, has_accepted_tos_privacy, accept_tos_privacy, \
    get_area_center_point, get_area_radius, has_area, has_quests
from chat.utils import get_emoji, get_text, log_message, extract_ids, get_all_languages, MessageType, MessageCategory, \
    message_user, job_delete_message, delete_message_in_category
from chat.config import bot_author, bot_provider, tos_date, tos_city, tos_country, quest_map_url

from quest.data import quests, get_all_quests_in_range

logger = logging.getLogger(__name__)


@log_message
def start(update: Update, context: CallbackContext):
    """Start interacting with this bot."""
    # extract ids from received message
    (chat_id, msg_id, user_id, username) = extract_ids(update)
    popup_text = ""
    show_as_popup = False

    chat_data = context.chat_data

    lang = get_language(chat_data)

    user = update.effective_user

    languages = get_all_languages()

    # check for callback query aka button pressed
    if hasattr(update, 'callback_query') and update.callback_query is not None:
        is_button_action = True

        data = update.callback_query.data

        # remove location message and hunting flag on fallback trigger
        if 'is_hunting'in chat_data:
            delete_message_in_category(bot=context.bot,
                                       chat_id=chat_id,
                                       chat_data=chat_data,
                                       category=MessageCategory.location)
            del chat_data['is_hunting']

        params = data.split()

        # user wants to change language
        if len(params) == 3 and params[1] == 'choose_lang' and params[2] in languages:
            lang = params[2]
            set_language(chat_data, lang)
            popup_text = get_text(lang, 'language_set', format_str=False)

        # user accepted tos and privacy
        if len(params) == 2 and params[1] == 'accept_tos_privacy':
            accept_tos_privacy(chat_data)

    # not a button press (i.e. text command)
    else:
        # if user is still hunting, remove the /start call and ask for end hunt confirmation
        if 'is_hunting' in chat_data:
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=update.effective_message.message_id)
            except BadRequest as e:
                logger.warning(f"Failed to delete /start command message #{update.effective_message.message_id} in "
                               f"chat #{chat_id}: {e}")
            return conversation.end_hunt(update, context)

        # check for old /start message
        if 'start_command_message_id' in chat_data:
            start_command_message_id = chat_data['start_command_message_id']
            try:
                # delete old /start message
                context.bot.delete_message(chat_id=chat_id, message_id=start_command_message_id)
                # delete any exiting main message as well so new main message appears beneath new /start command
                delete_message_in_category(bot=context.bot,
                                           chat_id=chat_id,
                                           chat_data=chat_data,
                                           category=MessageCategory.main)
            except BadRequest as e:
                logger.warning(f"Failed to delete /start command message #{start_command_message_id} in "
                               f"chat #{chat_id}: {e}")
        # remember new /start message
        chat_data['start_command_message_id'] = update.effective_message.message_id

        is_button_action = False

    # show language chooser if no language is set
    if lang is None:
        languages_title = []
        for lang_id in languages:
            languages_title.append(get_text(lang_id, 'language'))

        title = " | ".join(languages_title)
        text = f"{get_emoji('language')} *{title}*\n\n"

        for lang_id in languages:
            text += f"{get_emoji(f'language_{lang_id}')} {get_text(lang_id, 'language_choose')}\n"

        possible_lang = (user.language_code or 'NA')[:2]
        if possible_lang in languages:
            text += f"\n{get_emoji('info')} {get_text(possible_lang, 'language_detected')}"

        popup_text = get_text('en', 'language_choose', format_str=False)

        keyboard = []
        row = []
        for lang_id in languages:
            row.append(InlineKeyboardButton(text=f"{get_emoji(f'language_{lang_id}')} "
                                                 f"{get_text(lang_id, f'language_{lang_id}')}",
                                            callback_data=f'overview choose_lang {lang_id}'))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        # user pressed button, edit message
        if is_button_action:
            query = update.callback_query
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=show_as_popup)

        return message_user(bot=context.bot,
                            chat_id=chat_id,
                            chat_data=chat_data,
                            message_type=MessageType.message,
                            payload=text,
                            keyboard=keyboard,
                            category=MessageCategory.main)

    text = "{} *{}*\n\n".format(get_emoji('overview'),
                                get_text(lang, 'overview'))

    # accepting tos and privacy is required
    if not has_accepted_tos_privacy(chat_data):
        i_accept = get_text(lang, 'i_accept')
        i_decline = get_text(lang, 'i_decline')

        popup_text = get_text(lang, 'accept_tos_privacy_first_0', format_str=False)

        text += f"{get_text(lang, 'accept_tos_privacy_first_0')}\n\n" \
                f"{get_text(lang, 'accept_tos_privacy_first_1').format(i_accept=i_accept, i_decline=i_decline)}"

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('tos')} {get_text(lang, 'tos')}",
                                          callback_data='info tos')],
                    [InlineKeyboardButton(text=f"{get_emoji('privacy')} {get_text(lang, 'privacy')}",
                                          callback_data='info privacy')],
                    [InlineKeyboardButton(text=f"{get_emoji('thumb_up')} {get_text(lang, 'i_accept')}",
                                          callback_data='overview accept_tos_privacy'),
                     InlineKeyboardButton(text=f"{get_emoji('thumb_down')} {get_text(lang, 'i_decline')}",
                                          callback_data='delete_data yes')]]

        # user pressed button, edit message
        if is_button_action:
            query = update.callback_query
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=show_as_popup)

        return message_user(bot=context.bot,
                            chat_id=chat_id,
                            chat_data=chat_data,
                            message_type=MessageType.message,
                            payload=text,
                            keyboard=keyboard,
                            category=MessageCategory.main)

    text += f"{get_text(lang, 'overview_text0').format(name=user.first_name)}\n\n" \
            f"{get_text(lang, 'overview_text1').format(bot=context.bot.username)}\n\n"

    if not has_area(chat_data) and not has_quests(chat_data):
        text += f"{get_emoji('warning')} {get_text(lang, 'no_area_nor_quests')}\n{get_text(lang, 'please_do_that')}"
    elif not has_area(chat_data):
        text += f"{get_emoji('warning')} {get_text(lang, 'no_area')}\n{get_text(lang, 'please_do_that')}"
    elif not has_quests(chat_data):
        text += f"{get_emoji('warning')} {get_text(lang, 'no_quests')}\n{get_text(lang, 'please_do_that')}"
    else:
        quests_found = get_all_quests_in_range(chat_data,
                                               get_area_center_point(chat_data=chat_data),
                                               get_area_radius(chat_data=chat_data))

        if not quests_found:
            text += f"{get_emoji('warning')} {get_text(lang, 'no_quests_summary')}\n" \
                    f"{get_text(lang, 'no_quests_found_extended_info0')}\n" \
                    f"{get_text(lang, 'no_quests_found_extended_info1')}\n\n" \
                    f"{get_text(lang, 'no_quests_found_quest_count').format(total_quests_count=len(quests))}\n\n"

            if quest_map_url:
                text += get_text(lang, 'no_quests_found_map_hint').format(quest_map_url=quest_map_url)
        else:
            text += f"{get_text(lang, 'quests_summary').format(quests_count=len(quests_found))} " \
                    f"{get_text(lang, 'quests_summary_hint').format(hunt_quests=get_text(lang, 'hunt_quests'))}"

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('area')} {get_text(lang, 'select_area')}",
                                      callback_data='select_area'),
                 InlineKeyboardButton(text=f"{get_emoji('quest')} {get_text(lang, 'choose_quests')}",
                                      callback_data='choose_quest_type')],
                [InlineKeyboardButton(text=f"{get_emoji('hunt')} {get_text(lang, 'hunt_quests')}",
                                      callback_data='start_hunt')],
                [InlineKeyboardButton(text=f"{get_emoji('settings')} {get_text(lang, 'settings')}",
                                      callback_data='settings'),
                 InlineKeyboardButton(text=f"{get_emoji('info')} {get_text(lang, 'info')}",
                                      callback_data='info')]]

    # user pressed button, edit message
    if is_button_action:
        query = update.callback_query
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=show_as_popup)

    return message_user(bot=context.bot,
                        chat_id=chat_id,
                        chat_data=chat_data,
                        message_type=MessageType.message,
                        payload=text,
                        keyboard=keyboard,
                        category=MessageCategory.main)


@log_message
def settings(update: Update, context: CallbackContext):
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    params = query.data.split()

    if len(params) == 3 and params[1] == "choose_lang" and params[2] in ['en', 'de']:
        lang = params[2]
        set_language(chat_data, lang)
        popup_text = get_text(lang, 'language_set', format_str=False)
    else:
        popup_text = get_text(lang, 'settings_text0', format_str=False)

    text = f"{get_emoji('settings')} *{get_text(lang, 'settings')}*\n\n" \
           f"{get_text(lang, 'settings_text0')}"

    # rotate languages
    languages = ['en', 'de']
    if lang in languages:
        current_language_id = languages.index(lang)
        next_language_id = (current_language_id + 1) % len(languages)
        next_language = languages[next_language_id]
    else:
        next_language = languages[0]

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji(f'language_{lang}')} {get_text(lang, f'language_{lang}')}",
                                      callback_data='settings choose_lang {}'.format(next_language)),
                 InlineKeyboardButton(text=f"{get_emoji('trash')} {get_text(lang, 'delete_data')}",
                                      callback_data='delete_data')],
                [InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                      callback_data='overview')]]

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    return message_user(bot=context.bot,
                        chat_id=chat_id,
                        chat_data=chat_data,
                        message_type=MessageType.message,
                        payload=text,
                        keyboard=keyboard,
                        category=MessageCategory.main)


@log_message
def info(update: Update, context: CallbackContext):
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    accepted_tos = has_accepted_tos_privacy(chat_data)

    keyboard = []
    text = ""
    popup_text = ""

    params = query.data.split()
    if len(params) < 2:

        popup_text = get_text(lang, 'info_0', format_str=False)

        text = f"{get_emoji('info')} *{get_text(lang, 'info')}*\n\n" \
               f"{get_text(lang, 'info_0')}\n\n"

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('privacy')} {get_text(lang, 'privacy')}",
                                          callback_data='info privacy')],
                    [InlineKeyboardButton(text=f"{get_emoji('tos')} {get_text(lang, 'tos')}",
                                          callback_data='info tos'),
                     InlineKeyboardButton(text=f"{get_emoji('contact')} {get_text(lang, 'contact')}",
                                          callback_data='info contact')],
                    [InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='overview')]]

    elif params[1] == 'tos':

        popup_text = get_text(lang, 'tos_preamble_text', format_str=False).format(author=bot_author)

        country = get_text(lang, tos_country.lower())
        date = datetime.strptime(tos_date, '%Y-%m-%d')
        month = get_text(lang, date.strftime('%B').lower())
        tos_signature = get_text(lang, 'tos_signature').format(city=tos_city,
                                                               country=country,
                                                               year=date.year,
                                                               month=month,
                                                               day=date.day,
                                                               provider=bot_provider)
        text = f"{get_emoji('tos')} *{get_text(lang, 'tos')}*\n\n" \
               f"_{get_text(lang, 'tos_preamble')}_\n" \
               f"{get_text(lang, 'tos_preamble_text').format(author=bot_author)}\n\n" \
               f"_§1 {get_text(lang, 'tos_§1_title')}_\n" \
               f"{get_text(lang, 'tos_§1_text').format(provider=bot_provider)}\n\n" \
               f"_§2 {get_text(lang, 'tos_§2_title')}_\n" \
               f"{get_text(lang, 'tos_§2_text').format(bot=context.bot.username)}\n\n" \
               f"_§3 {get_text(lang, 'tos_§3_title')}_\n" \
               f"{get_text(lang, 'tos_§3_text')}\n\n" \
               f"{tos_signature}"

        row = []
        if accepted_tos:
            row.append(InlineKeyboardButton(text=f"{get_emoji('back')} {get_text(lang, 'back')}",
                                            callback_data='info'))
        row.append(InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                        callback_data='overview'))
        keyboard = [row]

    elif params[1] == 'privacy':

        popup_text = get_text(lang, 'privacy_text_0', format_str=False).format(bot=context.bot.username)

        text = f"{get_emoji('privacy')} *{get_text(lang, 'privacy')}*\n\n" \
               f"{get_text(lang, 'privacy_text_0').format(bot=context.bot.username)}\n" \
               f"{get_text(lang, 'privacy_text_0_0')}\n" \
               f"{get_text(lang, 'privacy_text_0_1')}\n" \
               f"{get_text(lang, 'privacy_text_0_2')}\n\n" \
               f"{get_text(lang, 'privacy_text_1')}\n"

        row = []
        # don't show all buttons when tos not accepted
        if accepted_tos:
            text += f"{get_text(lang, 'privacy_text_2')}"
            keyboard.append([InlineKeyboardButton(text=f"{get_emoji('trash')} {get_text(lang, 'delete_data')}",
                                                  callback_data='delete_data')])

            row.append(InlineKeyboardButton(text=f"{get_emoji('back')} {get_text(lang, 'back')}",
                                            callback_data='info'))

        row.append(InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                        callback_data='overview'))
        keyboard.append(row)

    elif params[1] == 'contact':

        popup_text = get_text(lang, 'contact_text_0', format_str=False).format(provider=bot_provider)

        text = f"{get_emoji('contact')} *{get_text(lang, 'contact')}*\n\n" \
               f"{get_text(lang, 'contact_text_0').format(provider=bot_provider)}\n\n" \
               f"{get_text(lang, 'contact_text_1').format(provider=bot_provider)}"

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('back')} {get_text(lang, 'back')}",
                                          callback_data='info'),
                     InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='overview')]]

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    return message_user(bot=context.bot,
                        chat_id=chat_id,
                        chat_data=chat_data,
                        message_type=MessageType.message,
                        payload=text,
                        keyboard=keyboard,
                        category=MessageCategory.main)


@log_message
def delete_data(update: Update, context: CallbackContext):
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    params = query.data.split()

    # permanently delete user data
    if len(params) == 2 and params[1] == 'yes':

        first_name = update.effective_user.first_name

        text = f"{get_emoji('trash')} *{get_text(lang, 'delete_data')}*\n\n" \
               f"{get_text(lang, 'delete_done')}\n\n" \
               f"{get_text(lang, 'delete_good_bye').format(name=first_name)}"

        popup_text = f"{get_text(lang, 'delete_done', format_str=False)}\n\n" \
                     f"{get_text(lang, 'delete_good_bye', format_str=False).format(name=first_name)}"

        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=True)

        message_user(bot=context.bot,
                     chat_id=chat_id,
                     chat_data=chat_data,
                     message_type=MessageType.message,
                     payload=text,
                     keyboard=[],
                     category=MessageCategory.main)

        # delete last message after 10 seconds
        context.job_queue.run_once(callback=job_delete_message,
                                   context={'chat_id': chat_id, 'message_id': msg_id},
                                   when=10)
        # delete start message as well
        if 'start_command_message_id' in chat_data:
            start_command_message_id = chat_data['start_command_message_id']
            context.job_queue.run_once(callback=job_delete_message,
                                       context={'chat_id': chat_id, 'message_id': start_command_message_id},
                                       when=10)

        # delete chat data
        for key in list(context.chat_data):
            del context.chat_data[key]

        # don't return sent here because we don't want to trigger logging which
        # would create a new user entry
        return

    text = f"{get_emoji('trash')} *{get_text(lang, 'delete_data')}*\n\n" \
           f"{get_emoji('warning')} *{get_text(lang, 'delete_is_permanent')}*\n\n" \
           f"{get_text(lang, 'delete_confirm')}"

    popup_text = get_text(lang, 'delete_confirm', format_str=False)

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('thumb_up')} {get_text(lang, 'yes')}",
                                      callback_data='delete_data yes'),
                 InlineKeyboardButton(text=f"{get_emoji('thumb_down')} {get_text(lang, 'no')}",
                                      callback_data='overview')],
                [InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                      callback_data='overview')]]

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    return message_user(bot=context.bot,
                        chat_id=chat_id,
                        chat_data=chat_data,
                        message_type=MessageType.message,
                        payload=text,
                        keyboard=keyboard,
                        category=MessageCategory.main)
