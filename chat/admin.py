import logging
import os
import sys
from threading import Thread

from telegram import Update
from telegram.ext import Updater, CallbackContext

from chat.config import bot_devs
from chat.utils import notify_devs

logger = logging.getLogger(__name__)


def admins_only(func):
    """Decorator to restrict access to admins only """
    def func_wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user = update.effective_user
        if user.id not in bot_devs:
            logger.warning(f"Unauthorized access by user {user.first_name} (#{user.id} / @{user.username})")
            return
        return func(update, context, *args, **kwargs)
    return func_wrapper


@admins_only
def restart(update: Update, context: CallbackContext, updater: Updater):
    """Restart the bot upon admin command"""

    def stop_and_restart():
        """Gracefully stop the Updater and replace the current process with a new one"""
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    notify_devs(text="Bot is restarting.")
    Thread(target=stop_and_restart).start()
