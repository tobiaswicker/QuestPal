import logging
import telegram.bot

from telegram.ext import messagequeue

logger = logging.getLogger(__name__)


class MQBot(telegram.bot.Bot):
    """A subclass of Bot which delegates send method handling to MessageQueue"""

    def __init__(self, *args, is_queued_def=True, msg_queue=None, **kwargs):

        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = msg_queue or messagequeue.MessageQueue()

    def __del__(self):
        # noinspection PyBroadException
        try:
            self._msg_queue.stop()
        except Exception:
            pass

    @messagequeue.queuedmessage
    def send_message(self, *args, **kwargs):
        """Wrapped method would accept new `queued` and `isgroup` OPTIONAL arguments"""
        logger.info("Sending queued message")
        return super(MQBot, self).send_message(*args, **kwargs)
