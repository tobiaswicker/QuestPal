import logging
import os
import subprocess
import sys
from threading import Thread

from telegram import Update
from telegram.ext import Updater, CallbackContext

from chat.config import bot_devs
from chat.utils import notify_devs, get_emoji

logger = logging.getLogger(__name__)


def admins_only(func):
    """Decorator to restrict access to admins only """
    def func_wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user = update.effective_user
        if user.id not in bot_devs:
            warning = f"Unauthorized access to admin function by user {user.first_name} (#{user.id} / @{user.username})"
            logger.warning(warning)
            text = f"{get_emoji('warning')} *Unauthorized Access*\n\n" \
                   f"{warning}"
            notify_devs(text=text)
            return
        return func(update, context, *args, **kwargs)
    return func_wrapper


@admins_only
def restart(update: Update, context: CallbackContext, updater: Updater, notify=True):
    """Restart the bot upon admin command"""

    query = update.callback_query
    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text='Restarting bot now.')

    def stop_and_restart():
        """Gracefully stop the Updater and replace the current process with a new one"""
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    if notify:
        text = f"{get_emoji('info')} *Restarting Bot*\n\n" \
               f"Bot is restarting."
        notify_devs(text=text)

    Thread(target=stop_and_restart).start()


@admins_only
def git_pull(update: Update, context: CallbackContext, updater: Updater):
    """Pull the latest changes from git repository"""

    query = update.callback_query
    if query:
        context.bot.answer_callback_query(callback_query_id=query.id, text='Pulling from git repository now.')

    try:
        pull_result = subprocess.check_output(["git", "pull"]).decode()
    except subprocess.CalledProcessError as e:
        text = f"{get_emoji('bug')} *Bug Report*\n\n" \
               f"Failed to pull latest changes from github: `{e.output}`"
        notify_devs(text=text)
        return

    text = f"{get_emoji('info')} *Updating Bot*\n\n" \
           f"Pulled the latest changes from git repository:\n" \
           f"`{pull_result}`\n"

    up_to_date = 'Already up to date'

    if up_to_date not in pull_result:
        text += "Restarting bot now."

    notify_devs(text=text)

    if up_to_date not in pull_result:
        restart(update, context, updater, notify=False)
