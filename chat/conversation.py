import logging
import re

from datetime import date
from geopy.geocoders import Nominatim

from telegram import Update, InlineKeyboardButton
from telegram.ext import CallbackContext, ConversationHandler

from chat.profile import get_language, get_area_center_point, set_area_center_point, get_area_radius, set_area_radius, \
    has_area, has_quests
from chat.utils import get_emoji, get_text, log_message, extract_ids, message_user, MessageType, MessageCategory, \
    delete_message_in_category, job_delete_message
from chat.config import log_format, log_level, quest_map_url

from quest.data import quests, quest_pokemon_list, quest_items_list, shiny_pokemon_list, get_item, get_pokemon, \
    get_task_by_id, get_all_tasks, get_id_by_task, get_all_quests_in_range, get_closest_quest
from quest.quest import Quest

# enable logging
logging.basicConfig(format=log_format, level=log_level)
logger = logging.getLogger(__name__)

# enumerate conversation steps
STEP0, STEP1, STEP2, STEP3, STEP4, STEP5, STEP6, STEP7, STEP8 = range(9)


@log_message
def select_area(update: Update, context: CallbackContext):
    """Let the user select the area for quest hunting"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    popup_text = get_text(lang, 'select_area_text0', format_str=False)

    text = f"{get_emoji('area')} *{get_text(lang, 'select_area')}*\n\n"

    center_point_invalid = 'area_center_point_message_invalid'
    center_point_failed = 'area_center_point_geo_localization_failed'
    if center_point_invalid in chat_data and chat_data[center_point_invalid]:
        del chat_data[center_point_invalid]
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_area_message_invalid')}*\n\n"
        # delete main message so new main message appears beneath user input
        delete_message_in_category(context.bot, chat_id, chat_data, MessageCategory.main)
    elif center_point_failed in chat_data and chat_data[center_point_failed]:
        del chat_data[center_point_failed]
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_area_geo_localization_failed')}*\n\n"
        # delete main message so new main message appears beneath user input
        delete_message_in_category(context.bot, chat_id, chat_data, MessageCategory.main)

    text += f"{get_text(lang, 'select_area_text0')}\n\n"

    center_point = get_area_center_point(chat_data=chat_data)
    radius = get_area_radius(chat_data=chat_data)
    if center_point[0] and center_point[1] and radius:
        current_area_text = get_text(lang, 'select_area_text1').format(center_point_latitude=center_point[0],
                                                                       center_point_longitude=center_point[1],
                                                                       radius_m=radius)
        current_area_url = get_text(lang, 'selected_area_url').format(center_point_latitude=center_point[0],
                                                                      center_point_longitude=center_point[1],
                                                                      radius_km=radius / 1000)
        text += f"{current_area_text}\n" \
                f"{current_area_url}\n\n"

    text += get_text(lang, 'select_area_text2')

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                      callback_data='back_to_overview')]]

    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return STEP0


@log_message
def set_quest_center_point(update: Update, context: CallbackContext):
    """Set the center point location, ask for radius"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    chat_data = context.chat_data

    lang = get_language(chat_data)

    message = update.effective_message

    text = f"{get_emoji('radius')} *{get_text(lang, 'select_radius')}*\n\n"

    # show invalid radius warning
    if 'area_radius_invalid' in chat_data and chat_data['area_radius_invalid']:
        del chat_data['area_radius_invalid']
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_radius_invalid')}*\n\n"
    elif 'area_radius_message_invalid' in chat_data and chat_data['area_radius_message_invalid']:
        del chat_data['area_radius_message_invalid']
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_radius_invalid')}*\n\n"

    # check for location
    elif message.location:
        set_area_center_point(chat_data=chat_data,
                              center_point=[message.location.latitude, message.location.longitude])

    # check for textual location
    elif message.text:
        geo_locator = Nominatim()
        # noinspection PyBroadException
        try:
            geo_location = geo_locator.geocode(message.text, timeout=10)
            set_area_center_point(chat_data=chat_data,
                                  center_point=[geo_location.latitude, geo_location.longitude])
        except Exception:
            # delete input message after 5 seconds
            context.job_queue.run_once(callback=job_delete_message,
                                       context={'chat_id': chat_id, 'message_id': msg_id},
                                       when=5)

            chat_data['area_center_point_geo_localization_failed'] = True
            return select_area(update, context)
    # start over if user sent anything else
    else:
        # delete input message after 5 seconds
        context.job_queue.run_once(callback=job_delete_message,
                                   context={'chat_id': chat_id, 'message_id': msg_id},
                                   when=5)

        chat_data['area_center_point_message_invalid'] = True
        return select_area(update, context)

    # delete input message after 5 seconds
    context.job_queue.run_once(callback=job_delete_message,
                               context={'chat_id': chat_id, 'message_id': msg_id},
                               when=5)

    center_point = get_area_center_point(chat_data=chat_data)

    # ask for radius
    text += get_text(lang, 'select_radius_text0').format(center_point_latitude=center_point[0],
                                                         center_point_longitude=center_point[1])

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                      callback_data='back_to_overview')]]

    # delete main message so new main message appears beneath user input
    delete_message_in_category(context.bot, chat_id, chat_data, MessageCategory.main)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return STEP1


@log_message
def set_quest_radius(update: Update, context: CallbackContext):
    """Set the radius, show area summary"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    chat_data = context.chat_data

    lang = get_language(chat_data)

    message = update.effective_message

    regex_number = re.compile(r'^\d+$')

    if not message.text:
        context.chat_data['area_radius_message_invalid'] = True
        return set_quest_center_point(update, context)

    # make sure input is a number
    if regex_number.match(message.text) and int(message.text) > 0:
        set_area_radius(chat_data=chat_data, radius=int(message.text))
    # start over
    else:
        # delete input message after 5 seconds
        context.job_queue.run_once(callback=job_delete_message,
                                   context={'chat_id': chat_id, 'message_id': msg_id},
                                   when=5)

        context.chat_data['area_radius_invalid'] = True
        return set_quest_center_point(update, context)

    # delete input message after 5 seconds
    context.job_queue.run_once(callback=job_delete_message,
                               context={'chat_id': chat_id, 'message_id': msg_id},
                               when=5)

    center_point = get_area_center_point(chat_data=chat_data)
    radius = get_area_radius(chat_data=chat_data)

    area_selected_text = get_text(lang, 'area_selected_text0').format(center_point_latitude=center_point[0],
                                                                      center_point_longitude=center_point[1],
                                                                      radius_m=radius)
    selected_area_url = get_text(lang, 'selected_area_url').format(center_point_latitude=center_point[0],
                                                                   center_point_longitude=center_point[1],
                                                                   radius_km=radius / 1000)
    text = f"{get_emoji('area')} *{get_text(lang, 'area_selected')}*\n\n" \
           f"{area_selected_text}\n" \
           f"{selected_area_url}"

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'done')}",
                                      callback_data='overview')]]

    # delete main message so new main message appears beneath user input
    delete_message_in_category(context.bot, chat_id, chat_data, MessageCategory.main)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return ConversationHandler.END


@log_message
def choose_quest_type(update: Update, context: CallbackContext):
    """Choose quest type"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    chat_data = context.chat_data

    lang = get_language(chat_data)

    query = update.callback_query

    text = f"{get_emoji('quest')} *{get_text(lang, 'choose_quests')}*\n\n" \
           f"{get_text(lang, 'choose_quests_text0')}\n\n"

    popup_text = get_text(lang, 'choose_quests_text0', format_str=False)

    pokemon = [] if 'pokemon' not in chat_data else chat_data['pokemon']
    items = [] if 'items' not in chat_data else chat_data['items']
    tasks = [] if 'tasks' not in chat_data else chat_data['tasks']

    if pokemon or items or tasks:
        text += f"{get_text(lang, 'choose_quests_text1')}\n"

        if pokemon:
            text += f"\n" \
                    f"*{get_text(lang, 'pokemon')}*\n"
            for pokemon_id in pokemon:
                shiny_tag = f" {get_emoji('shiny')}" if pokemon_id in shiny_pokemon_list else ""
                text += f"- `{get_pokemon(lang, pokemon_id)}`{shiny_tag}\n"
        if items:
            text += f"\n" \
                    f"*{get_text(lang, 'items')}*\n"
            for item_id in items:
                text += f"- `{get_item(lang, item_id)}`\n"
        if tasks:
            text += f"\n" \
                    f"*{get_text(lang, 'tasks')}*\n"
            for task_id in tasks:
                text += f"- `{get_task_by_id(lang, task_id)}`\n"

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('pokemon')} {get_text(lang, 'add_pokemon')}",
                                      callback_data='choose_pokemon'),
                 InlineKeyboardButton(text=f"{get_emoji('item')} {get_text(lang, 'add_item')}",
                                      callback_data='choose_item')],
                [InlineKeyboardButton(text=f"{get_emoji('task')} {get_text(lang, 'add_task')}",
                                      callback_data='choose_task')],
                [InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                      callback_data='back_to_overview')]]

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return STEP0


@log_message
def choose_pokemon(update: Update, context: CallbackContext):
    """Choose a pokemon quest"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    params = query.data.split()

    popup_text = None

    text = f"{get_emoji('pokemon')} *{get_text(lang, 'add_pokemon')}*\n\n" \
           f"{get_text(lang, 'add_pokemon_text0')}\n\n"

    # user chose a pokemon
    if len(params) == 2:

        pokemon_id = int(params[1])

        if 'pokemon' not in chat_data:
            chat_data['pokemon'] = [pokemon_id]
            popup_text = get_text(lang, 'added').format(quest=get_pokemon(lang, pokemon_id))
        elif pokemon_id in chat_data['pokemon']:
            chat_data['pokemon'].remove(pokemon_id)
            popup_text = get_text(lang, 'removed').format(quest=get_pokemon(lang, pokemon_id))
        else:
            chat_data['pokemon'].append(pokemon_id)
            popup_text = get_text(lang, 'added').format(quest=get_pokemon(lang, pokemon_id))

    chosen_pokemon = []
    # list chosen pokemon
    if 'pokemon' in chat_data and chat_data['pokemon']:
        text += f"{get_text(lang, 'add_pokemon_text1')}\n"

        chat_data['pokemon'].sort()
        for pokemon_id in chat_data['pokemon']:
            shiny_tag = f" {get_emoji('shiny')}" if pokemon_id in shiny_pokemon_list else ""
            text += f"- `{get_pokemon(lang, pokemon_id)}`{shiny_tag}\n"

        chosen_pokemon = chat_data['pokemon']

    keyboard = []
    row = []

    # list all pokemon that are available as well as those not available but previously chosen
    for pokemon_id in sorted(quest_pokemon_list + list(set(chosen_pokemon) - set(quest_pokemon_list))):
        if 'pokemon' in chat_data and pokemon_id in chat_data['pokemon']:
            button_text = f"{get_emoji('checked')} "
        else:
            button_text = ""
        if pokemon_id in shiny_pokemon_list:
            button_text += f"{get_pokemon(lang, pokemon_id)} {get_emoji('shiny')}"
        else:
            button_text += get_pokemon(lang, pokemon_id)

        row.append(InlineKeyboardButton(text=button_text, callback_data=f'choose_pokemon {pokemon_id}'))

        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text=f"{get_emoji('back')} {get_text(lang, 'back')}",
                                          callback_data='choose_quest_type'),
                     InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='back_to_overview')])

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return STEP0


@log_message
def choose_item(update: Update, context: CallbackContext):
    """Choose an item quest"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    params = query.data.split()

    popup_text = None

    text = f"{get_emoji('item')} *{get_text(lang, 'add_item')}*\n\n" \
           f"{get_text(lang, 'add_item_text0')}\n\n"
    # user chose an item
    if len(params) == 2:

        item_id = int(params[1])

        if 'items' not in chat_data:
            chat_data['items'] = [item_id]
            popup_text = get_text(lang, 'added').format(quest=get_item(lang, item_id))
        elif item_id in chat_data['items']:
            chat_data['items'].remove(item_id)
            popup_text = get_text(lang, 'removed').format(quest=get_item(lang, item_id))
        else:
            chat_data['items'].append(item_id)
            popup_text = get_text(lang, 'added').format(quest=get_item(lang, item_id))

    chosen_items = []
    # list chosen items
    if 'items' in chat_data and chat_data['items']:
        text += f"{get_text(lang, 'add_item_text1')}\n"

        chat_data['items'].sort()
        for item_id in chat_data['items']:
            text += f"- `{get_item(lang, item_id)}`\n"

        chosen_items = chat_data['items']

    keyboard = []
    row = []
    # list all items that are available as well as those not available but previously chosen
    for item_id in sorted(quest_items_list + list(set(chosen_items) - set(quest_items_list))):
        if 'items' in chat_data and item_id in chat_data['items']:
            button_text = f"{get_emoji('checked')} {get_item(lang, item_id)}"
        else:
            button_text = get_item(lang, item_id)

        row.append(InlineKeyboardButton(text=button_text, callback_data=f'choose_item {item_id}'))

        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text=f"{get_emoji('back')} {get_text(lang, 'back')}",
                                          callback_data='choose_quest_type'),
                     InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='back_to_overview')])

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return STEP0


@log_message
def choose_task(update: Update, context: CallbackContext):
    """Choose a quest task"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    params = query.data.split()

    popup_text = None

    text = f"{get_emoji('task')} *{get_text(lang, 'add_task')}*\n\n" \
           f"{get_text(lang, 'add_task_text0')}\n\n"
    # user chose a task
    if len(params) == 2:

        task_id = params[1]

        if 'tasks' not in chat_data:
            chat_data['tasks'] = [task_id]
            popup_text = get_text(lang, 'added').format(quest=get_task_by_id(lang, task_id).replace('.', ''))
        elif task_id in chat_data['tasks']:
            chat_data['tasks'].remove(task_id)
            popup_text = get_text(lang, 'removed').format(quest=get_task_by_id(lang, task_id).replace('.', ''))
        else:
            chat_data['tasks'].append(task_id)
            popup_text = get_text(lang, 'added').format(quest=get_task_by_id(lang, task_id).replace('.', ''))

    all_tasks = get_all_tasks(lang)

    # list chosen items
    if 'tasks' in chat_data and chat_data['tasks']:
        text += f"{get_text(lang, 'add_task_text1')}\n"

        # previously chosen tasks might no longer exist. make sure previously chosen tasks are listed and can be removed
        for task_id in chat_data['tasks']:
            task = get_task_by_id(lang, task_id)
            if task not in all_tasks:
                all_tasks = all_tasks + [task]

        all_tasks.sort()

        for task in all_tasks:
            task_id = get_id_by_task(lang, task)
            if task_id in chat_data['tasks'] or task_id == 'UNKNOWN_TASK':
                text += f"- `{task}`\n"

    keyboard = []
    # iterate all tasks including those chosen by the user
    for task in all_tasks:
        task_id = get_id_by_task(lang, task)
        # check if task has been chosen
        if 'tasks' in chat_data and task_id in chat_data['tasks']:
            button_text = f"{get_emoji('checked')} {task}"
            button_cmd = task_id
        # check if task is no longer known but was selected
        elif task_id == 'UNKNOWN_TASK' and 'tasks' in chat_data and task in chat_data['tasks']:
            button_text = f"{get_emoji('checked')} {task}"
            button_cmd = task
        # task hasn't been selected
        else:
            button_text = task
            button_cmd = task_id

        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f'choose_task {button_cmd}'[:61])])

    keyboard.append([InlineKeyboardButton(text=f"{get_emoji('back')} {get_text(lang, 'back')}",
                                          callback_data='choose_quest_type'),
                     InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='back_to_overview')])

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return STEP0


@log_message
def start_hunt(update: Update, context: CallbackContext):
    """Start the quest hunt"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n"

    if not has_area(chat_data):
        popup_text = f"{get_emoji('warning')} {get_text(lang, 'no_area')}\n{get_text(lang, 'please_do_that')}"
        text += popup_text

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('area')} {get_text(lang, 'select_area')}",
                                          callback_data='select_area')],
                    [InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                          callback_data='overview')]]

        if query:
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=True)

        message_user(bot=context.bot,
                     chat_id=chat_id,
                     chat_data=chat_data,
                     message_type=MessageType.message,
                     payload=text,
                     keyboard=keyboard,
                     category=MessageCategory.main)

        return ConversationHandler.END

    if not has_quests(chat_data):
        popup_text = f"{get_emoji('warning')} {get_text(lang, 'no_quests')}\n{get_text(lang, 'please_do_that')}"
        text += popup_text

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('quest')} {get_text(lang, 'choose_quests')}",
                                          callback_data='choose_quest_type')],
                    [InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                          callback_data='overview')]]

        if query:
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=True)

        message_user(bot=context.bot,
                     chat_id=chat_id,
                     chat_data=chat_data,
                     message_type=MessageType.message,
                     payload=text,
                     keyboard=keyboard,
                     category=MessageCategory.main)

        return ConversationHandler.END

    quests_found = get_all_quests_in_range(chat_data,
                                           get_area_center_point(chat_data=chat_data),
                                           get_area_radius(chat_data=chat_data))

    # make sure there are quests to hunt
    if not quests_found:
        if query:
            popup_text = f"{get_emoji('warning')} {get_text(lang, 'no_quests_found')}"
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=True)

        text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n" \
               f"{get_emoji('warning')} {get_text(lang, 'no_quests_found')}\n" \
               f"{get_text(lang, 'no_quests_found_extended_info0')}\n" \
               f"{get_text(lang, 'no_quests_found_extended_info1')}\n\n" \
               f"{get_text(lang, 'no_quests_found_quest_count').format(total_quests_count=len(quests))}\n\n"

        if quest_map_url:
            text += get_text(lang, 'no_quests_found_map_hint').format(quest_map_url=quest_map_url)

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='overview')]]

        # delete main message so new main message appears beneath user input
        delete_message_in_category(context.bot, chat_id, chat_data, MessageCategory.main)

        message_user(bot=context.bot,
                     chat_id=chat_id,
                     chat_data=chat_data,
                     message_type=MessageType.message,
                     payload=text,
                     keyboard=keyboard,
                     category=MessageCategory.main)

        if 'is_hunting' in chat_data:
            del chat_data['is_hunting']

        return ConversationHandler.END

    # skip asking for hunt continuation / reset if the user has seen this question before
    # and is just here because of invalid / failed location
    if 'start_location_message_invalid' in chat_data or 'start_location_geo_localization_failed' in chat_data:
        return ask_for_location(update, context)

    # ask if user wants to continue previous hunt or start a new hunt if hunt date is still the same / day didn't change
    if 'hunt_date' in chat_data and chat_data['hunt_date'] == str(date.today()):

        if query:
            popup_text = get_text(lang, 'continue_hunt_question', format_str=False)
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

        text += f"{get_text(lang, 'continue_hunt_detected')}\n\n" \
                f"{get_text(lang, 'continue_hunt_question')}"

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('continue')} {get_text(lang, 'continue_hunt')}",
                                          callback_data='continue_previous_hunt'),
                     InlineKeyboardButton(text=f"{get_emoji('reset')} {get_text(lang, 'reset_hunt')}",
                                          callback_data='reset_previous_hunt')],
                    [InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                          callback_data='overview')]]

        message_user(bot=context.bot,
                     chat_id=chat_id,
                     chat_data=chat_data,
                     message_type=MessageType.message,
                     payload=text,
                     keyboard=keyboard,
                     category=MessageCategory.main)

        return STEP0

    return ask_for_location(update, context)


@log_message
def continue_previous_hunt(update: Update, context: CallbackContext):
    """Continue the previous hunt"""
    context.chat_data['hunt_continued'] = True
    return ask_for_location(update, context)


@log_message
def reset_previous_hunt(update: Update, context: CallbackContext):
    """Reset the previous hunt"""
    context.chat_data['hunt_reset'] = True
    clean_up_hunt(context.chat_data)
    return ask_for_location(update, context)


def ask_for_location(update: Update, context: CallbackContext):
    """Ask the user for a location to start the hunt"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    chat_data = context.chat_data

    lang = get_language(chat_data)

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n"

    # set hunting flag
    chat_data['is_hunting'] = True

    if 'hunt_continued' in chat_data:
        del chat_data['hunt_continued']
        text += f"{get_text(lang, 'hunt_continued')}\n\n"
    elif 'hunt_reset' in chat_data:
        del chat_data['hunt_reset']
        text += f"{get_text(lang, 'hunt_reset')}\n\n"

    start_location_invalid = 'start_location_message_invalid'
    start_location_failed = 'start_location_geo_localization_failed'
    if start_location_invalid in chat_data:
        del chat_data[start_location_invalid]
        text += f"{get_emoji('warning')} *{get_text(lang, 'start_location_message_invalid')}*\n\n"
    elif start_location_failed in chat_data:
        del chat_data[start_location_failed]
        text += f"{get_emoji('warning')} *{get_text(lang, 'start_location_geo_localization_failed')}*\n\n"

    popup_text = get_text(lang, 'send_start_location')
    text += popup_text

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                      callback_data='back_to_overview')]]

    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    return STEP1


@log_message
def set_start_location(update: Update, context: CallbackContext):
    """Set the hunting start location"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    chat_data = context.chat_data

    message = update.effective_message

    # check for location
    if message.location:
        chat_data['user_location'] = [message.location.latitude, message.location.longitude]

    # check for textual location
    elif message.text:
        geo_locator = Nominatim()
        # noinspection PyBroadException
        try:
            geo_location = geo_locator.geocode(message.text, timeout=10)
            chat_data['user_location'] = [geo_location.latitude, geo_location.longitude]
        except Exception:
            context.chat_data['start_location_geo_localization_failed'] = True
            return start_hunt(update, context)

    # start over if user sent anything else
    else:
        # delete input message after 5 seconds
        context.job_queue.run_once(callback=job_delete_message,
                                   context={'chat_id': chat_id, 'message_id': msg_id},
                                   when=5)

        # delete main message so new main message appears beneath user input
        delete_message_in_category(context.bot, chat_id, chat_data, MessageCategory.main)

        context.chat_data['start_location_message_invalid'] = True
        return start_hunt(update, context)

    # delete input message after 5 seconds
    context.job_queue.run_once(callback=job_delete_message,
                               context={'chat_id': chat_id, 'message_id': msg_id},
                               when=5)

    # delete main message so new main message appears beneath user input
    delete_message_in_category(context.bot, chat_id, chat_data, MessageCategory.main)

    return send_next_quest(update, context)


def clean_up_hunt(chat_data):
    """Clean up previous quest hunt"""
    if 'fetched_quests' in chat_data:
        del chat_data['fetched_quests']
    if 'skipped_quests' in chat_data:
        del chat_data['skipped_quests']
    if 'ignored_quests' in chat_data:
        del chat_data['ignored_quests']
    if 'hunt_date' in chat_data:
        del chat_data['hunt_date']


def send_next_quest(update: Update, context: CallbackContext):
    """Send the next quest in line"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    chat_data = context.chat_data

    lang = get_language(chat_data)

    query = update.callback_query

    # get all quests for chat
    quests_found = get_all_quests_in_range(chat_data,
                                           get_area_center_point(chat_data=chat_data),
                                           get_area_radius(chat_data=chat_data))

    today = str(date.today())

    # clean up hunt if hunt date does not match / it's a new day
    if 'hunt_date' in chat_data and chat_data['hunt_date'] != today:
        clean_up_hunt(chat_data)

    # remember today's date
    chat_data['hunt_date'] = today

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n"

    if 'enqueue_skipped' in chat_data:
        del chat_data['enqueue_skipped']
        if 'skipped_quests' in chat_data:
            text += get_text(lang, 'hunt_quest_enqueued_skipped').format(skipped=len(chat_data['skipped_quests']))
            text += "\n\n"
            del chat_data['skipped_quests']

    # remove all finished quests
    if 'fetched_quests' in chat_data:
        for stop_id in chat_data['fetched_quests']:
            if stop_id in quests_found:
                del quests_found[stop_id]

    skipped_quests = {}
    # remove all skipped quests and treat them differently
    if 'skipped_quests' in chat_data:
        for stop_id in chat_data['skipped_quests']:
            if stop_id in quests_found:
                skipped_quests[stop_id] = quests_found[stop_id]
                del quests_found[stop_id]

    # remove all ignored quests
    if 'ignored_quests' in chat_data:
        for stop_id in chat_data['ignored_quests']:
            if stop_id in quests_found:
                del quests_found[stop_id]

    # make sure there are quests remaining
    if not quests_found:
        # check for skipped quests
        if skipped_quests:
            (closest_distance, closest_stop_id) = get_closest_quest(skipped_quests, chat_data['user_location'])
            current_quest = skipped_quests[closest_stop_id]

            popup_text = get_text(lang, 'hunt_quest_count_skipped', format_str=False) \
                .format(skipped=len(skipped_quests))

            text += f"{get_text(lang, 'hunt_quest_count_skipped').format(skipped=len(skipped_quests))}\n\n" \
                    f"{get_quest_summary(chat_data, current_quest, closest_distance)}"

            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

            message_user(bot=context.bot,
                         chat_id=chat_id,
                         chat_data=chat_data,
                         message_type=MessageType.message,
                         payload=text,
                         keyboard=[],
                         category=MessageCategory.main)

            row = [InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'quest_fetched')}",
                                        callback_data=f'quest_fetched {closest_stop_id}')]

            # only show skip button if more then one quests remain
            if len(skipped_quests) > 1:
                row.append(InlineKeyboardButton(text=f"{get_emoji('defer')} {get_text(lang, 'quest_skip')}",
                                                callback_data=f'quest_skip {closest_stop_id}'))

            row.append(InlineKeyboardButton(text=f"{get_emoji('trash')} {get_text(lang, 'quest_ignore')}",
                                            callback_data=f'quest_ignore {closest_stop_id}'))

            keyboard = [row,
                        [InlineKeyboardButton(text=f"{get_emoji('finish')} {get_text(lang, 'end_hunt')}",
                                              callback_data='end_hunt')]]

            message_user(bot=context.bot,
                         chat_id=chat_id,
                         chat_data=chat_data,
                         message_type=MessageType.location,
                         payload=[current_quest.latitude, current_quest.longitude],
                         keyboard=keyboard,
                         category=MessageCategory.location)

            return STEP2

        popup_text = get_text(lang, 'hunt_quest_all_done', format_str=False)

        text += f"{get_emoji('congratulation')} {get_text(lang, 'hunt_quest_all_done')}\n\n" \
                f"{get_text(lang, 'hunt_quest_new_quests_tomorrow')}"

        if query:
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'done')}",
                                          callback_data='overview')]]

        # inform user that all quests have been completed
        message_user(bot=context.bot,
                     chat_id=chat_id,
                     chat_data=chat_data,
                     message_type=MessageType.message,
                     payload=text,
                     keyboard=keyboard,
                     category=MessageCategory.main)

        # remove location message
        delete_message_in_category(bot=context.bot,
                                   chat_id=chat_id,
                                   chat_data=chat_data,
                                   category=MessageCategory.location)

        if 'is_hunting' in chat_data:
            del chat_data['is_hunting']

        return ConversationHandler.END

    (closest_distance, closest_stop_id) = get_closest_quest(quests_found, chat_data['user_location'])
    current_quest = quests_found[closest_stop_id]

    if skipped_quests:
        popup_text = get_text(lang, 'hunt_quest_count_open_and_skipped', format_str=False) \
            .format(open=len(quests_found), skipped=len(skipped_quests))
        text += get_text(lang, 'hunt_quest_count_open_and_skipped').format(open=len(quests_found),
                                                                           skipped=len(skipped_quests))
    else:
        popup_text = get_text(lang, 'hunt_quest_count_open', format_str=False).format(open=len(quests_found))
        text += get_text(lang, 'hunt_quest_count_open').format(open=len(quests_found))

    text += "\n\n"

    text += get_quest_summary(chat_data, current_quest, closest_distance)

    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=[],
                 category=MessageCategory.main)

    row = [InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'quest_fetched')}",
                                callback_data=f'quest_fetched {closest_stop_id}')]

    if len(quests_found) > 1 or skipped_quests:
        row.append(InlineKeyboardButton(text=f"{get_emoji('defer')} {get_text(lang, 'quest_skip')}",
                                        callback_data=f'quest_skip {closest_stop_id}'))
    row.append(InlineKeyboardButton(text=f"{get_emoji('trash')} {get_text(lang, 'quest_ignore')}",
                                    callback_data=f'quest_ignore {closest_stop_id}'))

    keyboard = [row]

    if 'skipped_quests' in chat_data:
        text = f"{get_emoji('enqueue')} {get_text(lang, 'quests_enqueue_skipped')} ({len(skipped_quests)})"
        keyboard.append([InlineKeyboardButton(text=text,
                                              callback_data='enqueue_skipped')])

    keyboard.append([InlineKeyboardButton(text=f"{get_emoji('finish')} {get_text(lang, 'end_hunt')}",
                                          callback_data='end_hunt')])

    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.location,
                 payload=[current_quest.latitude, current_quest.longitude],
                 keyboard=keyboard,
                 category=MessageCategory.location)

    return STEP2


def get_quest_summary(chat_data, quest: Quest, closest_distance):
    """Get a summary for a quest"""
    lang = get_language(chat_data)

    rounded_distance = "%.0f" % closest_distance

    if quest.item_id:
        reward = f"{quest.item_amount}x {get_item(lang, quest.item_id)}"
    else:
        reward = get_pokemon(lang, quest.pokemon_id)

    return get_text(lang, 'hunt_quest_closest').format(quest_name=get_task_by_id(lang, quest.task_id),
                                                       quest_reward=reward,
                                                       pokestop_name=quest.stop_name,
                                                       distance=rounded_distance)


@log_message
def quest_fetched(update: Update, context: CallbackContext):
    """Mark a quest as done / fetched"""
    params = update.callback_query.data.split()
    stop_id = params[1]

    chat_data = context.chat_data

    if 'fetched_quests' not in chat_data:
        chat_data['fetched_quests'] = [stop_id]
    else:
        chat_data['fetched_quests'].append(stop_id)

    # get all quests for chat
    quests_found = get_all_quests_in_range(chat_data,
                                           get_area_center_point(chat_data=chat_data),
                                           get_area_radius(chat_data=chat_data))

    # update user location
    if stop_id in quests_found:
        chat_data['user_location'] = [quests_found[stop_id].latitude, quests_found[stop_id].longitude]

    return send_next_quest(update, context)


@log_message
def quest_skip(update: Update, context: CallbackContext):
    """Skip a quest"""
    params = update.callback_query.data.split()
    stop_id = params[1]

    chat_data = context.chat_data

    if 'skipped_quests' not in chat_data:
        chat_data['skipped_quests'] = [stop_id]
    else:
        chat_data['skipped_quests'].append(stop_id)

    return send_next_quest(update, context)


@log_message
def quest_ignore(update: Update, context: CallbackContext):
    """Ignore a quest"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    chat_data = context.chat_data

    lang = get_language(chat_data)

    query = update.callback_query
    params = query.data.split()

    if params[1] == "yes":

        stop_id = params[2]

        if 'ignored_quests' not in chat_data:
            chat_data['ignored_quests'] = [stop_id]
        else:
            chat_data['ignored_quests'].append(stop_id)

        return send_next_quest(update, context)

    stop_id = params[1]

    popup_text = get_text(lang, 'hunt_quest_ignore_confirm', format_str=False)

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n" \
           f"{get_text(lang, 'hunt_quest_ignore_info')}\n\n" \
           f"{get_text(lang, 'hunt_quest_ignore_confirm')}"

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('thumb_up')} {get_text(lang, 'yes')}",
                                      callback_data=f'quest_ignore yes {stop_id}'),
                 InlineKeyboardButton(text=f"{get_emoji('thumb_down')} {get_text(lang, 'no')}",
                                      callback_data='continue_hunt')]]

    # update main message
    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    # delete location message
    delete_message_in_category(bot=context.bot,
                               chat_id=chat_id,
                               chat_data=chat_data,
                               category=MessageCategory.location)

    return STEP2


@log_message
def enqueue_skipped(update: Update, context: CallbackContext):
    """Ignore a quest"""

    context.chat_data['enqueue_skipped'] = True

    return send_next_quest(update, context)


@log_message
def end_hunt(update: Update, context: CallbackContext):
    """End the hunt"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    chat_data = context.chat_data

    lang = get_language(chat_data)

    query = update.callback_query

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n"

    # end hunt if user really wants to stop hunting
    if query and len(query.data.split()) == 2:
        popup_text = get_text(lang, 'hunt_quest_finished_early', format_str=False)

        text += get_text(lang, 'hunt_quest_finished_early', )

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'done')}",
                                          callback_data='overview')]]

        if 'is_hunting' in chat_data:
            del chat_data['is_hunting']

        return_value = ConversationHandler.END

    # ask for confirmation
    else:
        popup_text = get_text(lang, 'hunt_quest_finish_confirm', format_str=False)

        text += get_text(lang, 'hunt_quest_finish_confirm', )

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('thumb_up')} {get_text(lang, 'yes')}",
                                          callback_data='end_hunt yes'),
                     InlineKeyboardButton(text=f"{get_emoji('thumb_down')} {get_text(lang, 'no')}",
                                          callback_data='continue_hunt')]]

        return_value = STEP2

    # make sure this is a button callback call
    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    # update main message
    message_user(bot=context.bot,
                 chat_id=chat_id,
                 chat_data=chat_data,
                 message_type=MessageType.message,
                 payload=text,
                 keyboard=keyboard,
                 category=MessageCategory.main)

    # delete location message
    delete_message_in_category(bot=context.bot,
                               chat_id=chat_id,
                               chat_data=chat_data,
                               category=MessageCategory.location)

    return return_value


def continue_hunt(update: Update, context: CallbackContext):
    """Continue the hunt"""
    return send_next_quest(update, context)
