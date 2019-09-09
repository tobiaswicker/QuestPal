def set_language(chat_data, language):
    """Set language for chat."""
    language = language[:2]
    chat_data['language'] = language
    return


def get_language(chat_data):
    """Get player name in private chat."""
    return chat_data['language'] if 'language' in chat_data and chat_data['language'] else None


def accept_tos_privacy(chat_data):
    """Marks TOS and Privacy as accepted by user."""
    chat_data['accepted_tos_privacy'] = True
    return


def has_accepted_tos_privacy(chat_data):
    """Check if the user accepted TOS and Privacy"""
    return 'accepted_tos_privacy' in chat_data and chat_data['accepted_tos_privacy']


def set_area_center_point(chat_data, center_point):
    """Set the center point of the area for the quest hunt"""
    chat_data['area_center_point'] = center_point


def get_area_center_point(chat_data):
    """Get center point of the quest hunt area"""
    return chat_data['area_center_point'] if 'area_center_point' in chat_data else [None, None]


def set_area_radius(chat_data, radius):
    """Set the radius of the area for the quest hunt"""
    chat_data['area_radius'] = radius


def get_area_radius(chat_data):
    """Get the radius of an area"""
    return chat_data['area_radius'] if 'area_radius' in chat_data else 0


def has_area(chat_data):
    """Check if the user has selected an area"""
    area_center_point = get_area_center_point(chat_data=chat_data)
    area_radius = get_area_radius(chat_data=chat_data)
    return area_center_point[0] and area_center_point[1] and area_radius


def has_quests(chat_data):
    """Check if the user has chosen any quests"""
    pokemon_exist = 'pokemon' in chat_data and chat_data['pokemon']
    items_exist = 'items' in chat_data and chat_data['items']
    tasks_exist = 'tasks' in chat_data and chat_data['tasks']
    return pokemon_exist or items_exist or tasks_exist
