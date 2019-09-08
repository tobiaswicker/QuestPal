import logging
import re

from geopy.geocoders import Nominatim

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackContext, ConversationHandler

from chat import profile
from chat.profile import get_area_center_point, get_area_radius
from chat.tools import get_emoji, get_text, log_message, extract_ids
from chat.config import log_format, log_level, quest_map_url

from quest.data import quest_pokemon_list, quest_items_list, shiny_pokemon_list, get_item, get_pokemon, \
    get_task_by_id, get_all_tasks, get_id_by_task, get_all_quests_in_range, get_closest_quest

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

    lang = profile.get_language(chat_id)

    popup_text = get_text(lang, 'select_area_text0', format_str=False)

    text = f"{get_emoji('area')} *{get_text(lang, 'select_area')}*\n\n"

    center_point_invalid = 'area_center_point_message_invalid'
    center_point_failed = 'area_center_point_geo_localization_failed'
    if center_point_invalid in context.chat_data and context.chat_data[center_point_invalid]:
        del context.chat_data[center_point_invalid]
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_area_message_invalid')}*\n\n"
    elif center_point_failed in context.chat_data and context.chat_data[center_point_failed]:
        del context.chat_data[center_point_failed]
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_area_geo_localization_failed')}*\n\n"

    text += f"{get_text(lang, 'select_area_text0')}\n\n"

    center_point = profile.get_area_center_point(chat_id)
    radius = profile.get_area_radius(chat_id)
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
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

        context.bot.edit_message_text(text=text,
                                      parse_mode=ParseMode.MARKDOWN,
                                      chat_id=chat_id,
                                      message_id=msg_id,
                                      reply_markup=reply_markup,
                                      disable_web_page_preview=True)
    else:
        context.bot.send_message(text=text,
                                 parse_mode=ParseMode.MARKDOWN,
                                 chat_id=chat_id,
                                 reply_markup=reply_markup,
                                 disable_web_page_preview=True)
    return STEP0


@log_message
def set_quest_center_point(update: Update, context: CallbackContext):
    """Set the center point location, ask for radius"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    lang = profile.get_language(chat_id)

    message = update.effective_message

    text = f"{get_emoji('radius')} *{get_text(lang, 'select_radius')}*\n\n"

    # show invalid radius warning
    if 'area_radius_invalid' in context.chat_data and context.chat_data['area_radius_invalid']:
        del context.chat_data['area_radius_invalid']
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_radius_invalid')}*\n\n"
    elif 'area_radius_message_invalid' in context.chat_data and context.chat_data['area_radius_message_invalid']:
        del context.chat_data['area_radius_message_invalid']
        text += f"{get_emoji('warning')} *{get_text(lang, 'selected_radius_invalid')}*\n\n"
    # check for location
    elif message.location:
        profile.set_area_center_point(chat_id=chat_id,
                                      center_point=[message.location.latitude, message.location.longitude])
    # check for textual location
    elif message.text:
        geo_locator = Nominatim()
        # noinspection PyBroadException
        try:
            geo_location = geo_locator.geocode(message.text, timeout=10)
            profile.set_area_center_point(chat_id=chat_id,
                                          center_point=[geo_location.latitude, geo_location.longitude])
        except Exception:
            context.chat_data['area_center_point_geo_localization_failed'] = True
            return select_area(update, context)
    # start over if user sent anything else
    else:
        context.chat_data['area_center_point_message_invalid'] = True
        return select_area(update, context)

    center_point = profile.get_area_center_point(chat_id=chat_id)

    # ask for radius
    text += get_text(lang, 'select_radius_text0').format(center_point_latitude=center_point[0],
                                                         center_point_longitude=center_point[1])

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                      callback_data='back_to_overview')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(text=text,
                             parse_mode=ParseMode.MARKDOWN,
                             chat_id=chat_id,
                             reply_markup=reply_markup)

    return STEP1


@log_message
def set_quest_radius(update: Update, context: CallbackContext):
    """Set the radius, show area summary"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    lang = profile.get_language(chat_id)

    message = update.effective_message

    regex_number = re.compile(r'^\d+$')

    if not message.text:
        context.chat_data['area_radius_message_invalid'] = True
        return set_quest_center_point(update, context)

    # make sure input is a number
    if regex_number.match(message.text) and int(message.text) > 0:
        profile.set_area_radius(chat_id=chat_id, radius=int(message.text))
    # start over
    else:
        context.chat_data['area_radius_invalid'] = True
        return set_quest_center_point(update, context)

    center_point = profile.get_area_center_point(chat_id=chat_id)
    radius = profile.get_area_radius(chat_id=chat_id)

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
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(text=text,
                             parse_mode=ParseMode.MARKDOWN,
                             chat_id=chat_id,
                             reply_markup=reply_markup,
                             disable_web_page_preview=True)

    return ConversationHandler.END


@log_message
def choose_quest_type(update: Update, context: CallbackContext):
    """Choose quest type"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    lang = profile.get_language(chat_id)

    query = update.callback_query

    text = f"{get_emoji('quest')} *{get_text(lang, 'choose_quests')}*\n\n" \
           f"{get_text(lang, 'choose_quests_text0')}\n\n"

    popup_text = get_text(lang, 'choose_quests_text0', format_str=False)

    chat_data = context.chat_data
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
                text += f"- {get_pokemon(lang, pokemon_id)}{shiny_tag}\n"
        if items:
            text += f"\n" \
                    f"*{get_text(lang, 'items')}*\n"
            for item_id in items:
                text += f"- {get_item(lang, item_id)}\n"
        if tasks:
            text += f"\n" \
                    f"*{get_text(lang, 'tasks')}*\n"
            for task_id in tasks:
                text += f"- {get_task_by_id(lang, task_id)}\n"

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('pokemon')} {get_text(lang, 'add_pokemon')}",
                                      callback_data='choose_pokemon'),
                 InlineKeyboardButton(text=f"{get_emoji('item')} {get_text(lang, 'add_item')}",
                                      callback_data='choose_item')],
                [InlineKeyboardButton(text=f"{get_emoji('task')} {get_text(lang, 'add_task')}",
                                      callback_data='choose_task')],
                [InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                      callback_data='back_to_overview')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    context.bot.edit_message_text(text=text,
                                  parse_mode=ParseMode.MARKDOWN,
                                  chat_id=chat_id,
                                  message_id=msg_id,
                                  reply_markup=reply_markup)

    return STEP0


@log_message
def choose_pokemon(update: Update, context: CallbackContext):
    """Choose a pokemon quest"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    lang = profile.get_language(chat_id)

    params = query.data.split()

    popup_text = None

    chat_data = context.chat_data

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
            text += f"- {get_pokemon(lang, pokemon_id)}{shiny_tag}\n"

        chosen_pokemon = chat_data['pokemon']

    keyboard = []
    row = []
    for pokemon_id in sorted(quest_pokemon_list + list(set(chosen_pokemon) - set(quest_pokemon_list))):
        if pokemon_id in shiny_pokemon_list:
            button_text = f"{get_emoji('shiny')} {get_pokemon(lang, pokemon_id)}"
        else:
            button_text = get_pokemon(lang, pokemon_id)
        if 'pokemon' in chat_data and pokemon_id in chat_data['pokemon']:
            button_text += f" {get_emoji('checked')}"

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

    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    context.bot.edit_message_text(text=text,
                                  parse_mode=ParseMode.MARKDOWN,
                                  chat_id=chat_id,
                                  message_id=msg_id,
                                  reply_markup=reply_markup)
    return STEP0


@log_message
def choose_item(update: Update, context: CallbackContext):
    """Choose an item quest"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    lang = profile.get_language(chat_id)

    params = query.data.split()

    popup_text = None

    chat_data = context.chat_data

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
            text += f"- {get_item(lang, item_id)}\n"

        chosen_items = chat_data['items']

    keyboard = []
    row = []
    for item_id in sorted(quest_items_list + list(set(chosen_items) - set(quest_items_list))):
        if 'items' in chat_data and item_id in chat_data['items']:
            button_text = f"{get_item(lang, item_id)} {get_emoji('checked')}"
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

    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    context.bot.edit_message_text(text=text,
                                  parse_mode=ParseMode.MARKDOWN,
                                  chat_id=chat_id,
                                  message_id=msg_id,
                                  reply_markup=reply_markup)
    return STEP0


@log_message
def choose_task(update: Update, context: CallbackContext):
    """Choose a quest task"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    lang = profile.get_language(chat_id)

    params = query.data.split()

    popup_text = None

    chat_data = context.chat_data

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
                all_tasks.append(task)

        all_tasks.sort()

        for task in all_tasks:
            if get_id_by_task(lang, task) in chat_data['tasks']:
                text += f"- {task}\n"

    keyboard = []
    row = []
    for task in all_tasks:
        task_id = get_id_by_task(lang, task)
        if 'tasks' in chat_data and task_id in chat_data['tasks']:
            button_text = f"{task} {get_emoji('checked')}"
        else:
            button_text = task
        row.append(InlineKeyboardButton(text=button_text, callback_data=f'choose_task {task_id}'[:61]))
        if len(row) == 1:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text=f"{get_emoji('back')} {get_text(lang, 'back')}",
                                          callback_data='choose_quest_type'),
                     InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='back_to_overview')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    context.bot.edit_message_text(text=text,
                                  parse_mode=ParseMode.MARKDOWN,
                                  chat_id=chat_id,
                                  message_id=msg_id,
                                  reply_markup=reply_markup)
    return STEP0


@log_message
def start_hunt(update: Update, context: CallbackContext):
    """Start the quest hunt"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    query = update.callback_query

    lang = profile.get_language(chat_id)

    chat_data = context.chat_data

    area_center_point = get_area_center_point(chat_id=chat_id)
    area_radius = get_area_radius(chat_id=chat_id)

    has_area = area_center_point[0] and area_center_point[1] and area_radius

    pokemon_exist = 'pokemon' in chat_data and chat_data['pokemon']
    items_exist = 'items' in chat_data and chat_data['items']
    tasks_exist = 'tasks' in chat_data and chat_data['tasks']

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n"

    if not has_area:
        popup_text = f"{get_emoji('warning')} {get_text(lang, 'no_area')}"
        text += popup_text

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('area')} {get_text(lang, 'select_area')}",
                                          callback_data='select_area')],
                    [InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                          callback_data='overview')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=True)

            context.bot.edit_message_text(text=text,
                                          parse_mode=ParseMode.MARKDOWN,
                                          chat_id=chat_id,
                                          message_id=msg_id,
                                          reply_markup=reply_markup)
        else:
            context.bot.send_message(text=text,
                                     parse_mode=ParseMode.MARKDOWN,
                                     chat_id=chat_id,
                                     reply_markup=reply_markup)
        return ConversationHandler.END

    if not pokemon_exist and not items_exist and not tasks_exist:
        popup_text = f"{get_emoji('warning')} {get_text(lang, 'no_quests')}"
        text += popup_text

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('quest')} {get_text(lang, 'choose_quests')}",
                                          callback_data='choose_quest_type')],
                    [InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                          callback_data='overview')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=True)

            context.bot.edit_message_text(text=text,
                                          parse_mode=ParseMode.MARKDOWN,
                                          chat_id=chat_id,
                                          message_id=msg_id,
                                          reply_markup=reply_markup)
        else:
            context.bot.send_message(text=text,
                                     parse_mode=ParseMode.MARKDOWN,
                                     chat_id=chat_id,
                                     reply_markup=reply_markup)
        return ConversationHandler.END

    start_location_invalid = 'start_location_message_invalid'
    start_location_failed = 'start_location_geo_localization_failed'
    if start_location_invalid in chat_data and chat_data[start_location_invalid]:
        del chat_data[start_location_invalid]
        text += f"{get_emoji('warning')} *{get_text(lang, 'start_location_message_invalid')}*\n\n"
    elif start_location_failed in chat_data and chat_data[start_location_failed]:
        del chat_data[start_location_failed]
        text += f"{get_emoji('warning')} *{get_text(lang, 'start_location_geo_localization_failed')}*\n\n"

    popup_text = get_text(lang, 'send_start_location')
    text += popup_text

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('cancel')} {get_text(lang, 'cancel')}",
                                      callback_data='back_to_overview')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)
        context.bot.edit_message_text(text=text,
                                      parse_mode=ParseMode.MARKDOWN,
                                      chat_id=chat_id,
                                      message_id=msg_id,
                                      reply_markup=reply_markup)
    else:
        context.bot.send_message(text=text,
                                 parse_mode=ParseMode.MARKDOWN,
                                 chat_id=chat_id,
                                 reply_markup=reply_markup)

    return STEP0


@log_message
def set_start_location(update: Update, context: CallbackContext):
    """Set the hunting start location"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    lang = profile.get_language(chat_id)

    message = update.effective_message

    chat_data = context.chat_data

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
        context.chat_data['start_location_message_invalid'] = True
        return start_hunt(update, context)

    # clean up previous quest hunt
    if 'done_quests' in chat_data:
        del chat_data['done_quests']
    if 'deferred_quests' in chat_data:
        del chat_data['deferred_quests']
    if 'hunt_message_id' in chat_data:
        del chat_data['hunt_message_id']
        del chat_data['hunt_location_message_id']

    quests_found = get_all_quests_in_range(chat_data, get_area_center_point(chat_id), get_area_radius(chat_id))

    if not quests_found:
        text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n" \
               f"{get_text(lang, 'hunt_quest_none')}\n\n"

        if quest_map_url:
            text += get_text(lang, 'hunt_quest_none_map_hint').format(quest_map_url=quest_map_url)

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('overview')} {get_text(lang, 'overview')}",
                                          callback_data='overview')]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        context.bot.send_message(text=text,
                                 parse_mode=ParseMode.MARKDOWN,
                                 chat_id=chat_id,
                                 reply_markup=reply_markup)

        return ConversationHandler.END

    return send_next_quest(update, context)


def send_next_quest(update: Update, context: CallbackContext):
    """Send the next quest in line"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    lang = profile.get_language(chat_id)

    chat_data = context.chat_data

    query = update.callback_query

    # get all quests for chat
    quests_found = get_all_quests_in_range(chat_data, get_area_center_point(chat_id), get_area_radius(chat_id))

    # remove all finished quests
    if 'done_quests' in chat_data:
        for stop_id in chat_data['done_quests']:
            if stop_id in quests_found:
                del quests_found[stop_id]

    deferred_quests = {}
    # remove all deferred quests and treat them differently
    if 'deferred_quests' in chat_data:
        for stop_id in chat_data['deferred_quests']:
            if stop_id in quests_found:
                deferred_quests[stop_id] = quests_found[stop_id]
                del quests_found[stop_id]

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n"

    # make sure there are quests remaining
    if not quests_found:
        # check for deferred quests
        if deferred_quests:
            (closest_distance, closest_stop_id) = get_closest_quest(deferred_quests, chat_data['user_location'])
            rounded_distance = "%.0f" % closest_distance
            current_quest = deferred_quests[closest_stop_id]

            popup_text = get_text(lang, 'hunt_quest_count_deferred').format(deferred_count=len(deferred_quests))
            text += f"{popup_text}\n" \
                    f"{get_text(lang, 'hunt_quest_closest').format(distance=rounded_distance)}"

            context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

            context.bot.edit_message_text(text=text,
                                          parse_mode=ParseMode.MARKDOWN,
                                          message_id=chat_data['hunt_message_id'],
                                          chat_id=chat_id)

            context.bot.delete_message(chat_id=chat_id, message_id=chat_data['hunt_location_message_id'])

            keyboard = [[InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'quest_done')}",
                                              callback_data=f'quest_done {closest_stop_id}')],
                        [InlineKeyboardButton(text=f"{get_emoji('finish')} {get_text(lang, 'end_hunt')}",
                                              callback_data='end_hunt')]]

            reply_markup = InlineKeyboardMarkup(keyboard)

            sent_location = context.bot.send_location(chat_id=chat_id,
                                                      latitude=current_quest.latitude,
                                                      longitude=current_quest.longitude,
                                                      reply_markup=reply_markup)

            (sent_chat_id, sent_msg_id, sent_user_id, sent_username) = extract_ids(sent_location)
            chat_data['hunt_location_message_id'] = sent_msg_id

            return STEP1

        popup_text = get_text(lang, 'hunt_quest_all_done', format_str=False)

        text += f"{get_emoji('congratulation')} {get_text(lang, 'hunt_quest_all_done')}\n\n" \
                f"{get_text(lang, 'hunt_quest_new_quests_tomorrow')}"

        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

        keyboard = [[InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'done')}",
                                          callback_data=f'overview')]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        context.bot.edit_message_text(text=text,
                                      parse_mode=ParseMode.MARKDOWN,
                                      message_id=chat_data['hunt_message_id'],
                                      chat_id=chat_id,
                                      reply_markup=reply_markup)

        context.bot.delete_message(chat_id=chat_id, message_id=chat_data['hunt_location_message_id'])

        del chat_data['hunt_message_id']
        del chat_data['hunt_location_message_id']

        return ConversationHandler.END

    (closest_distance, closest_stop_id) = get_closest_quest(quests_found, chat_data['user_location'])
    rounded_distance = "%.0f" % closest_distance
    current_quest = quests_found[closest_stop_id]

    if deferred_quests:
        popup_text = get_text(lang, 'hunt_quest_count_open_and_deferred').format(open_count=len(quests_found),
                                                                                 deferred_count=len(deferred_quests))
        text += f"{popup_text}\n"

    else:
        popup_text = get_text(lang, 'hunt_quest_count_open').format(open_count=len(quests_found))
        text += f"{popup_text}\n"

    text += f"{get_text(lang, 'hunt_quest_closest').format(distance=rounded_distance)}"

    # send a new message if hunt just started
    if 'hunt_message_id' not in chat_data:
        sent_message = context.bot.send_message(text=text,
                                                parse_mode=ParseMode.MARKDOWN,
                                                chat_id=chat_id)

        (sent_chat_id, sent_msg_id, sent_user_id, sent_username) = extract_ids(sent_message)
        chat_data['hunt_message_id'] = sent_msg_id

    # edit existing hunt message and delete location
    else:
        context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

        context.bot.edit_message_text(text=text,
                                      parse_mode=ParseMode.MARKDOWN,
                                      message_id=chat_data['hunt_message_id'],
                                      chat_id=chat_id)

        context.bot.delete_message(chat_id=chat_id, message_id=chat_data['hunt_location_message_id'])

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'quest_done')}",
                                      callback_data=f'quest_done {closest_stop_id}'),
                 InlineKeyboardButton(text=f"{get_emoji('defer')} {get_text(lang, 'defer_quest')}",
                                      callback_data=f'defer_quest {closest_stop_id}')],
                [InlineKeyboardButton(text=f"{get_emoji('finish')} {get_text(lang, 'end_hunt')}",
                                      callback_data='end_hunt')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_location = context.bot.send_location(chat_id=chat_id,
                                              latitude=current_quest.latitude,
                                              longitude=current_quest.longitude,
                                              reply_markup=reply_markup)

    (sent_chat_id, sent_msg_id, sent_user_id, sent_username) = extract_ids(sent_location)
    chat_data['hunt_location_message_id'] = sent_msg_id

    return STEP1


@log_message
def quest_done(update: Update, context: CallbackContext):
    """Mark a quest as done / hunted"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    params = update.callback_query.data.split()
    stop_id = params[1]

    chat_data = context.chat_data

    if 'done_quests' not in chat_data:
        chat_data['done_quests'] = [stop_id]
    else:
        chat_data['done_quests'].append(stop_id)

    # get all quests for chat
    quests_found = get_all_quests_in_range(chat_data, get_area_center_point(chat_id), get_area_radius(chat_id))

    # update user location
    if stop_id in quests_found:
        chat_data['user_location'] = [quests_found[stop_id].latitude, quests_found[stop_id].longitude]

    return send_next_quest(update, context)


@log_message
def defer_quest(update: Update, context: CallbackContext):
    """Defer a quest"""
    params = update.callback_query.data.split()
    stop_id = params[1]

    chat_data = context.chat_data

    if 'deferred_quests' not in chat_data:
        chat_data['deferred_quests'] = [stop_id]
    else:
        chat_data['deferred_quests'].append(stop_id)

    return send_next_quest(update, context)


@log_message
def end_hunt(update: Update, context: CallbackContext):
    """End the hunt"""
    (chat_id, msg_id, user_id, username) = extract_ids(update)

    lang = profile.get_language(chat_id)

    query = update.callback_query

    chat_data = context.chat_data

    popup_text = get_text(lang, 'hunt_quest_finished_early')

    text = f"{get_emoji('quest')} *{get_text(lang, 'hunt_quests')}*\n\n" \
           f"{popup_text}"

    keyboard = [[InlineKeyboardButton(text=f"{get_emoji('checked')} {get_text(lang, 'done')}",
                                      callback_data=f'overview')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.edit_message_text(text=text,
                                  parse_mode=ParseMode.MARKDOWN,
                                  message_id=chat_data['hunt_message_id'],
                                  chat_id=chat_id,
                                  reply_markup=reply_markup)

    context.bot.delete_message(chat_id=chat_id, message_id=chat_data['hunt_location_message_id'])

    context.bot.answer_callback_query(callback_query_id=query.id, text=popup_text, show_alert=False)

    del chat_data['hunt_message_id']
    del chat_data['hunt_location_message_id']

    return ConversationHandler.END
