import json
import logging
import os

from chat.config import data_storage, log_format, log_level

# enable logging
logging.basicConfig(format=log_format, level=log_level)
logger = logging.getLogger(__name__)

all_profiles = {}


def save_profiles():
    """Save all profiles"""
    logger.info("Saving profile data...")
    with open(file=data_storage, mode='w+', encoding="utf-8") as f:
        json.dump(all_profiles, f)
        logger.info("Profile data saved.")
        logger.debug(f"Data: {all_profiles}")
    return


def load_profiles():
    """Load all profiles."""
    logger.info("Loading profile data...")
    if not os.path.isfile(data_storage):
        logger.info("Stats data file does not exist. Nothing to load.")
        return
    with (open(file=data_storage, mode='r', encoding="utf-8")) as f:
        global all_profiles
        all_profiles = json.load(f)
        logger.info("Stats data loaded.")
        logger.debug(f"Data: {all_profiles}")
    return


def set_chat_setting(chat_id, key, value):
    """Set setting for chat."""
    chat_id = str(chat_id)
    key = str(key)
    # init dict for chat
    if chat_id not in all_profiles:
        all_profiles[chat_id] = {}
    # set key to value
    all_profiles[chat_id][key] = value
    # save
    save_profiles()
    return


def get_chat_setting(chat_id, key, default=None):
    """Get setting for chat."""
    chat_id = str(chat_id)
    key = str(key)
    value = all_profiles.get(chat_id, {}).get(key, default)
    return value


def set_language(user_id, language):
    """Set language for chat."""
    language = language[:2]
    logger.info(f'Setting language to {language} for {user_id}.')
    set_chat_setting(chat_id=user_id, key='language', value=language)
    return


def get_language(chat_id):
    """Get player name in private chat."""
    return get_chat_setting(chat_id=chat_id, key='language')


def accept_tos_privacy(user_id):
    """Marks TOS and Privacy as accepted by user."""
    logger.info(f'Accepting TOS & Privacy for {user_id}.')
    tos_value = True
    set_chat_setting(user_id, 'accepted_tos_privacy', tos_value)
    return


def has_accepted_tos_privacy(user_id):
    """Check if the user accepted TOS and Privacy"""
    return get_chat_setting(chat_id=user_id, key='accepted_tos_privacy', default=False)


def set_area_center_point(chat_id, center_point):
    """Set the center point of the area for the quest hunt"""
    logger.info(f'Setting area center point to \'{center_point}\'.')
    set_chat_setting(chat_id=chat_id, key='area_latitude', value=center_point[0])
    set_chat_setting(chat_id=chat_id, key='area_longitude', value=center_point[1])


def get_area_center_point(chat_id):
    """Get center point of the quest hunt area"""
    return [get_chat_setting(chat_id=chat_id, key='area_latitude'),
            get_chat_setting(chat_id=chat_id, key='area_longitude')]


def set_area_radius(chat_id, radius):
    """Set the radius of the area for the quest hunt"""
    logger.info(f'Setting area radius to {radius} m.')
    set_chat_setting(chat_id=chat_id, key='area_radius', value=radius)


def get_area_radius(chat_id):
    return get_chat_setting(chat_id=chat_id, key='area_radius')


def delete_profile(user_id):
    """Delete all information for a certain chat"""
    logger.info(f'Deleting profile {user_id}')
    user_id = str(user_id)
    # make sure we have info on that chat
    if user_id in all_profiles:
        # delete chat profile
        del all_profiles[user_id]

    # save
    save_profiles()
    return
