import os
import configparser

_config = configparser.ConfigParser()

_parent_path = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
_config_path = os.path.join(_parent_path, 'config.ini')
_config.read(_config_path)

_bot_config = _config['bot']
bot_use_message_queue = _bot_config.getboolean('use_message_queue', True)
bot_token = _bot_config.get('token')
bot_provider = _bot_config.get('provider').replace('@', '')
bot_devs = [int(user_id) for user_id in _bot_config.get('dev_user_ids').split(",")]
bot_author = "farstars"
log_file = _bot_config.get('log_file')

_mysql_config = _config['mysql']
mysql_host = _mysql_config.get('host')
mysql_port = _mysql_config.get('port')
mysql_user = _mysql_config.get('user')
mysql_password = _mysql_config.get('password')
mysql_db = _mysql_config.get('database')

msg_folder = 'message_log'

_map_config = _config['map']
quest_map_url = _map_config.get('quest_map_url')

_tos_config = _config['tos']
tos_country = _tos_config['country']
tos_city = _tos_config['city']
tos_date = _tos_config['date']
