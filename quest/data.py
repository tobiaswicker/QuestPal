import json
import os

from geopy.distance import great_circle

from chat.utils import get_text

quests = {}

# list of all available quests
quest_pokemon_list = []
quest_items_list = []

# dict of quests and their location (quest_id => location
quest_locations = {}

shiny_pokemon_list = []

_items = {}
_item_code_names = {}
_pokemon = {}
_task_lookup = {}
_task_id_lookup = {}
_tasks = {}


def _get_item_code_name(item_id):
    """Get item code name by id"""
    global _item_code_names
    if not _item_code_names:
        current_directory = os.path.dirname(os.path.realpath(__file__))
        file_name = 'items.json'
        file_path = os.path.join(current_directory, file_name)
        with open(file=file_path, mode='r', encoding='utf-8') as f:
            _item_code_names = json.load(f)

    item_id = str(item_id)
    if item_id in _item_code_names:
        return _item_code_names.get(item_id)

    return _item_code_names("0")


def get_item(lang, item_id):
    """Get item name in a certain language by id"""
    if not _items:
        current_directory = os.path.dirname(os.path.realpath(__file__))
        items_directory = os.path.join(current_directory, 'items')
        for filename in os.listdir(items_directory):
            if filename.endswith(".json"):
                lang_id = filename.replace('.json', '')
                file_path = os.path.join(items_directory, filename)
                with open(file=file_path, mode='r', encoding='utf-8') as f:
                    _items[lang_id] = json.load(f)

    item_code_name = _get_item_code_name(item_id)

    if lang in _items and item_code_name in _items[lang]:
        return _items[lang][item_code_name]

    return _items[lang]['Unknown']


def _load_pokemon():
    """Load all pokemon for various languages"""
    if not _pokemon:
        current_directory = os.path.dirname(os.path.realpath(__file__))
        pokemon_directory = os.path.join(current_directory, 'pokemon')
        for filename in os.listdir(pokemon_directory):
            if filename.endswith(".json"):
                lang_id = filename.replace('.json', '')
                file_path = os.path.join(pokemon_directory, filename)
                with open(file=file_path, mode='r', encoding='utf-8') as f:
                    _pokemon[lang_id] = json.load(f)


def get_pokemon(lang, pokedex_id):
    """Get pokemon name for a certain language by id"""
    _load_pokemon()

    pokedex_id = int(pokedex_id)
    if lang in _pokemon and pokedex_id < len(_pokemon[lang]) + 1:
        return _pokemon[lang][pokedex_id - 1]

    return get_text(lang, 'unknown_pokemon')


def get_pokedex_id(lang, pokemon_name):
    """Get pokedex id of a specific pokemon in a certain language"""
    _load_pokemon()

    if lang in _pokemon:
        for name in _pokemon[lang]:
            if name.lower() == pokemon_name.lower():
                return _pokemon[lang].index(name) + 1

    return 0


def _load_tasks():
    """Load all tasks from file and create lookup dicts"""
    if not _task_lookup:
        current_directory = os.path.dirname(os.path.realpath(__file__))
        tasks_directory = os.path.join(current_directory, 'tasks')
        for filename in os.listdir(tasks_directory):
            if filename.endswith(".json"):
                lang_id = filename.replace('.json', '')
                file_path = os.path.join(tasks_directory, filename)
                with open(file=file_path, mode='r', encoding='utf-8') as f:
                    _task_lookup[lang_id] = json.load(f)
        for lang, tasks in _task_lookup.items():
            if lang not in _tasks:
                _tasks[lang] = []
                _task_id_lookup[lang] = {}
            for task_id, task in tasks.items():
                if task not in _tasks[lang]:
                    _tasks[lang].append(task)
                    _task_id_lookup[lang][task] = task_id
            _tasks[lang].sort()


def get_task_by_id(lang, task_id):
    """Get task description in a certain language by id"""
    _load_tasks()

    if lang in _task_lookup and task_id in _task_lookup[lang]:
        return _task_lookup[lang][task_id]

    return task_id


def get_id_by_task(lang, task):
    """Get id of a task"""
    _load_tasks()

    if lang in _task_id_lookup and task in _task_id_lookup[lang]:
        return _task_id_lookup[lang][task]

    return "UNKNOWN_TASK"


def get_all_tasks(lang):
    """Get all tasks in a certain language"""
    _load_tasks()
    return _tasks[lang]


def get_all_quests_in_range(chat_data, center_point, radius):
    """Get all quests that the user chose within a radius to a point"""
    quests_found = {}

    pokemon = chat_data['pokemon'] if 'pokemon' in chat_data else []
    items = chat_data['items'] if 'items' in chat_data else []
    tasks = chat_data['tasks'] if 'tasks' in chat_data else []

    for stop_id, quest in quests.items():
        if quest.pokemon_id in pokemon or quest.item_id in items or quest.task_id in tasks:
            if great_circle(center_point, [quest.latitude, quest.longitude]).meters <= radius:
                quests_found[stop_id] = quest

    return quests_found


def get_closest_quest(quests_found, current_location):
    """Get quest that is closest to a given location"""
    closest_distance = None
    closest_stop_id = None

    for stop_id, quest in quests_found.items():

        if closest_distance is None:
            closest_distance = great_circle(current_location, [quest.latitude, quest.longitude]).meters
            closest_stop_id = stop_id
            continue

        distance = great_circle(current_location, [quest.latitude, quest.longitude]).meters
        if distance < closest_distance:
            closest_distance = distance
            closest_stop_id = stop_id

    return closest_distance, closest_stop_id
