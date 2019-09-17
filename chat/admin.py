import os
import sys
from threading import Thread

from telegram import Update
from telegram.ext import Updater, CallbackContext


def stop_and_restart(updater: Updater):
    """Gracefully stop the Updater and replace the current process with a new one"""
    updater.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)


def restart(updater: Updater, update: Update, context: CallbackContext):
    """Restart the bot upon admin command"""
    update.message.reply_text('Bot is restarting...')
    Thread(target=stop_and_restart, args=[updater]).start()
