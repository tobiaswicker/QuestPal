# QuestPal

QuestPal is a [Telegram](https://telegram.org) bot that lets users hunt quests in Pokémon Go. QuestPal is designed to 
work with quests made available by [Map'A'Droid](https://github.com/Map-A-Droid/MAD/).  

## Features & Usage
- At first the user has to select an area and the quests they like to hunt. This has to be done just once.
- The user can then start the hunt and QuestPal shows the quest that is closest in terms of a straight line / as the 
crow flies to the users location.
- Quests can be marked as `Collected` which sets the user location to the location of the quest and looks for other 
quests nearby.
- Quests can also be deferred by pressing `Later` or put on an `Ignored` list. Both choices won't change the user 
location from which to look for new quests.

## Installation
1. Clone this repository: `git clone https://github.com/tobiaswicker/QuestPal.git`
2. [Download Python 3.x](https://www.python.org/downloads/) if you haven't already
3. Install [Python-Telegram-Bot](https://python-telegram-bot.org) by running `pip install python-telegram-bot` from a 
terminal.
4. Talk to [@BotFather](https://t.me/BotFather) to get a `token`.
5. Create a username for yourself in the settings of your Telegram account, if you haven't already done so.
6. Rename `config-bot.ini.example` to `config-bot.ini` and edit it. 
   - Replace `BOT_TOKEN` with your bots `token`.
   - Replace `YOUR_TELEGRAM_USERNAME` with your username. Remember that this should be _your_ username, **not** your 
   bots username.
   - Add the user ids of all admins and developers to `dev_user_ids`. You can get your user id by contacting 
   [@JsonDumpBot](https://t.me/JsonDumpBot). Leave this blank if you don't want to get notified about issues (not 
   recommended).
   - Fill in the connection details for your MySQL database.
7. Run the bot from a terminal: `python3 questpalbot.py`
