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

"""
d.add_filter(-161006688, "pidgey")
d.add_filter(-161006688, "rattata")
d.add_filter(-161006688, "psyduck")
d.add_filter(-161006688, "zubat")
d.add_filter(-161006688, "bellsprout")

d.add_chatid(217372209, 1.3490515,103.9414295)
"""

def test():
    d.add_chatid(-161006688, 1.3490515,103.9414295) #group chat
    d.add_chatid(163592895, 1.3490515,103.9414295) #ahmin
    d.add_chatid(217372209, 1.306171,103.79155) #val

    d.add_location(163592895, "home", 1.3419647,103.6889841)

    d.add_location(-161006688, "sp20", 1.2869952,103.7818955)
    d.add_location(-161006688, "lengkokbahru55", 1.2874217,103.81342)
    d.add_location(-161006688, "jurongwestst91", 1.3419647,103.6889841)
    d.add_location(-161006688, "starvista", 1.3068123,103.7884621)
    d.add_location(-161006688, "sp12", 1.290323,103.786674)

    d.add_location(217372209, "home", 1.3490515,103.9414295)
    d.add_location(217372209, "simei", 1.3459934,103.9592207)
    d.add_location(217372209, "metropolis", 1.306171,103.79155)

def addfilter():
    d.remove_filter(217372209, "pidgey\nrattata\nweedle\ncaterpie\nvenonat\nstaryu\nhorsea\nzubat\ngolbat\npsyduck\nkrabby\nspearow\ngoldeen\nkingler\npoliwag\nseaking\nfearow\nslowpoke\nparas\ntentacool\npidgeotto\nmagikarp\nekans\npinsir\npidgeot\nbellsprout\nexeggcute\nraticate\ndodrio\ndoduo\noddish\ntangela\nmetapod\nkakuna\nmagnemite\nmagneton\nvoltorb\nelectrode")

if __name__ == "__main__":
    init_logging()
    d = init_database()
    radar = Radar(d)
    radar.start()
    
