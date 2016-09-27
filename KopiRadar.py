import os
import sys
import logging
import threading
import subprocess
import time
import json
import traceback
import googlemaps
import sqlite3

from ConfigParser import SafeConfigParser
from datetime import datetime
# from telegram.ext import Updater
# from telegram.ext import CommandHandler
# from telegram.ext import MessageHandler, Filters
# from telegram.ext import Job
# from telegram.error import (TelegramError, Unauthorized, BadRequest, TimedOut,NetworkError)

from lib.database import Database
from lib.radar import Radar

log = logging.getLogger()

def init_logging():
    logging.basicConfig(format='[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    log.setLevel(logging.DEBUG)

def init_database():
    d = Database()
    return d

if __name__ == "__main__":
    init_logging()
    d = init_database()
    radar = Radar(d)
    radar.start()
    
