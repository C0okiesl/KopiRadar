import os
import sys
import logging
import googlemaps
import traceback
import json
import subprocess
import time

from ConfigParser import SafeConfigParser
from datetime import datetime

from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
from telegram.ext import Job
from telegram.error import (TelegramError, Unauthorized, BadRequest, TimedOut,NetworkError)

from lib.constants import _ROOT, _DEFAULT_LAT, _DEFAULT_LNG

log = logging.getLogger(__name__)

class Radar():
	def __init__(self, database):
		config = os.path.join(_ROOT, "conf", "KopiRadar.cfg")
		parser = SafeConfigParser()
		parser.read(config)

		log.info("Initialising Radar")

		log.debug("Config read from {0}".format(config))

		self.database   = database
		self.updater	= Updater(token=parser.get('general', 'telegram_key'))
		self.dispatcher = self.updater.dispatcher
		self.gmaps	  = googlemaps.Client(key=parser.get('general', 'gmap_key'))

		self.filters = {}
		self.locations = {}
		self.favs = {}
		self.chatids = {}
		self.filterswitch = {}
		self.radius = 0.003

		#initialise with existing chat ids first#
		log.info("Initialising information in Database")
		chatids = self.database.get_all_chatid()

		for x in chatids:
			locations   = self.database.get_locations_by_chatid(x)
			filters	 = self.database.get_filters_by_chatid(x)
			favs		= self.database.get_favs_by_chatid(x)

			self.filters[int(x)] = []
			self.locations[int(x)] = []
			self.favs[int(x)] = []
			self.chatids[int(x)] = ()

			for y in locations:
				self.locations[int(x)].append((y.name, y.lat, y.lng))
			for y in filters:
				self.filters[int(x)].append(y.name)
			for y in favs:
				self.favs[int(x)].append(y.name)

			self.chatids[int(x)] = self.database.get_currentlocation(x)
			self.filterswitch[int(x)] = self.database.get_filterswitch(x)

		log.debug("chatids: {0}".format(self.chatids))
		log.debug("filters: {0}".format(self.filters))
		log.debug("favs: {0}".format(self.favs))
		log.debug("locations: {0}".format(self.locations))
		log.debug("filterswitch: {0}".format(self.filterswitch))

	def _help(self, bot, update):
		start_message = "Welcome to KopiRadar (Alpha 0.6)\n"
		start_message += "You don't have to do anything to start\n"
		log.info("Hello {0}".format(update.message.chat_id))
		bot.sendMessage(chat_id=update.message.chat_id, text=start_message)

	def _process_result(self, chatid, results, filtered_pokemons, filterswitch):
		message = ""
		summaries = ""
		data = results["result"]

		for r in data:
			pokemon = None

			# get the name of the pokemon
			if "pokemon_id" in r:
				pokemon = r["pokemon_id"]
			elif "lure_info" in r:
				if "active_pokemon_id" in r["lure_info"]:
					pokemon = r["lure_info"]["active_pokemon_id"]

			log.info(filtered_pokemons)
			log.info(filterswitch)
			# process the information
			if pokemon == None:
				continue
			elif pokemon.lower() in filtered_pokemons and filterswitch == True:
				log.debug("---{0} is in filter list".format(pokemon.lower()))

				pokemon_latitude 	= r['latitude']
				pokemon_longitude 	= r['longitude']

				#history.write("{0} appears in ({1},{2})\n".format(pokemon, str(pokemon_latitude), str(pokemon_longitude)))
			else:
				pokemon_latitude 	= None
				pokemon_longitude 	= None
				pokemon_expire 		= None

				if "latitude" in r:
					pokemon_latitude 	= r['latitude']
					pokemon_longitude 	= r['longitude']
					pokemon_location	= (float(pokemon_latitude),float(pokemon_longitude))
				else:
					continue

				if "expiration_timestamp_ms" in r:
					pokemon_expire = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(r["expiration_timestamp_ms"])/1000))
				else:
					# self.database.add_history(chatid, pokemon, pokemon_latitude, pokemon_longitude, pokemon_expire)
					pokemon_expire = "Can't Find Expire Time"

				log.info("Checking {0} {1}".format(pokemon, pokemon_expire))

				if self.database.check_history(chatid, pokemon, float(pokemon_latitude), float(pokemon_longitude), str(pokemon_expire)):
					log.info("Already alarmed the user about this pokemon: {0}".format(pokemon))
				else:
					self.database.add_history(chatid, pokemon, pokemon_latitude, pokemon_longitude, str(pokemon_expire))
					log.info("Added history to Database")

					location_by_name 	= self._get_location(pokemon_location)
					special_location 	= self._get_special_location(pokemon_location)
					location_by_gmap 	= "https://www.google.com/maps/place/" + str(pokemon_location[0]) + "," + str(pokemon_location[1])

					message += "{0}: {1}\n{2}\n{3}\n".format(pokemon, pokemon_expire,location_by_name, location_by_gmap)
					if special_location != False:
						message += "{0}\n\n".format(special_location.upper())
					else:
						message += "({0},{1})\n\n".format(str(pokemon_location[0]), str(pokemon_location[1]))

					summaries += pokemon.upper()
					summaries += " "

		log.info("-- {0}".format(message))

		if message == "":
			final_message = None
		else:
			final_message = summaries + "\n\n" + message

		return final_message

	def _query_data(self, chatid, coordinates):
		data = None
		message = None
		chatid = int(chatid)
		while data == None or "result" not in data:
			curl_args = ['curl', "https://api.fastpokemap.se/?key=allow-all&ts=0&lat=" + str(coordinates[0]) + "&lng=" + str(coordinates[1]), "-H", "origin: https://fastpokemap.se", "-H", "user-agent: Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36", "-H", 'authority: api.fastpokemap.se', "--compressed"]
			response = subprocess.check_output(curl_args)
			if response == None or response == "":
				time.sleep(5)
			else:
				log.info("response: {0}".format(response))
				data = json.loads(response)

				if data == None:
					time.sleep(5)
				elif "result" not in data:
					log.info("Server is currently overloaded. Let's wait for 5 seconds: {0}".format(data))
					time.sleep(5)
				else:
					tfilter_switch = self.filterswitch[chatid]
					filtered_pokemons = []
					if chatid in self.filters:
						filtered_pokemons = self.filters[chatid]
					else:
						filtered_pokemons = []

					#chatid, results, filtered_pokemons, filterswitch
					message = self._process_result(chatid, data, filtered_pokemons, tfilter_switch)

					if message != None:
						log.info("Done! Reply to our user...")
						#bot.sendMessage(chat_id=chatid, text=message)
						return message
					else:
						return None

	def _watch(self, bot, job):
		timer 		= 300.0
		coordinates = None
		location 	= None # location in coordinates

		if int(job.context) in self.chatids:
			coordinates = float(self.chatids[job.context][0]), float(self.chatids[job.context][1])
			location = self._get_location(coordinates)
		else:
			self.update_chatid(job.context, _DEFAULT_LAT, _DEFAULT_LNG)
			self.favs[int(x)]	   = []
			self.filters[int(x)]	= []
			self.locations[int(x)]  = []

			log.info("Done initialising for new chatid #{0}".format(job.context))
			coordinates = (_DEFAULT_LAT, _DEFAULT_LNG)
			location = _DEFAULT_NAME

		if location == None:
			log.error("Could not get/create any location")

		message = self._query_data(job.context, coordinates)
		if message != None:
			bot.sendMessage(chat_id=job.context, text=message)

	def addfilter(self, bot, update, args):
		if len(args) < 1:
			bot.sendMessage(chat_id=update.message.chat_id, text="Perhaps you can give us a pokemon name. /addfilter pidgey rattata")
		else:
			message = "Added:\n"
			x_list = []
			for x in args:
				pokemon = x.rstrip().lower()
				message += "- {0}\n".format(pokemon)
				x_list.append(pokemon)

			self._add_filter(update.message.chat_id, x_list)
			bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def removefilter(self, bot, update, args):
		if len(args) < 1:
			bot.sendMessage(chat_id=update.message.chat_id, text="Perhaps you can give us a name")
		else:
			message = "Removed:\n"
			x_remove = []
			for x in args:
				pokemon = x.rstrip().lower()
				x_remove.append(pokemon)
				message+= "- {0}\n".format(pokemon)
			self._remove_filter(update.message.chat_id, x_remove)
			bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def showfilter(self, bot, update):
		message = ""

		if update.message.chat_id not in self.filters:
			self.filters[update.message.chat_id] = []
			bot.sendMessage(chat_id=update.message.chat_id, text="You don't have a filter list yet. Start by using /addfilter")
		else:
			for l in self.filters[update.message.chat_id]:
				message += l
				if l != self.filters[update.message.chat_id][-1]:
					message += "\n"

			if len( self.filters[update.message.chat_id]) == 0:
				message = "No pokemon yet."
			bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def filterswitchf(self, bot, update, args):
		switch = False
		if len(args) < 1:
			bot.sendMessage(chat_id=update.message.chat_id, text="Turn on by /filteron 1. Turn off by using /filteron 0")
		elif int(args[0]) == 1:
			switch = True
		self.database.update_filter_switch(update.message.chat_id, switch)
		self.filterswitch[update.message.chat_id] = switch
		message = "Updated Filter Switch: {0}".format(switch)
		bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def addlocation(self, bot, update, args):
		if len(args) < 1:
			bot.sendMessage(chat_id=update.message.chat_id, text="Perhaps you can give us a location. /addlocation sp20 20 Science Park Drive")
		else:
			message = ""

			name = args[0]
			user_location = ""

			for x in args[1:]:
				user_location += x
				user_location += " "

			google_location = self._get_location_by_name(user_location)

			if google_location == None:
				bot.sendMessage(chat_id=update.message.chat_id, text="We can't find this address. Perhaps you can add more details? (e.g street or blk number)")
			else:
				best_result 		= google_location[0]
				formatted_address 	= None
				lat 				= None
				lon 				= None

				if "formatted_address" in best_result:
					formatted_address 	= best_result["formatted_address"]
					lat 				= best_result["geometry"]["location"]["lat"]
					lon 				= best_result["geometry"]["location"]["lng"]


				if formatted_address:
					self._add_location(update.message.chat_id, name, float(lat), float(lon))
					message = "Added to location list:\n{0} as {1}".format(formatted_address, name)
					bot.sendMessage(chat_id=update.message.chat_id, text=message)
				else:
					bot.sendMessage(chat_id=update.message.chat_id, text="We can't get enough info for this address.")

	def removelocation(self, bot, update, args):
		if len(args) < 1:
			bot.sendMessage(chat_id=update.message.chat_id, text="Perhaps you can give us a location. /removelocation sp20")
		else:
			log.info("Removing location {0}".format(args[0]))
			self._remove_location(update.message.chat_id, args[0])
			message = "Removed {0} from location list\n".format(args[0])
			bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def showlocation(self, bot, update):
		message = ""
		index = 0

		if update.message.chat_id not in self.chatids:
			message += "Cannot find your chat_id. Weird."

		if self.locations[update.message.chat_id] == []:
			message += "You have not added any locations yet"
		else:
			locations = self.locations[int(update.message.chat_id)]
			for l in locations:
				print l
				message += "{0}. {1} ({2}, {3})\n".format(index, l[0], l[1],  l[2])
				index = index + 1

		bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def setlocation(self, bot, update, args):
		if len(args) < 1:
			bot.sendMessage(chat_id=update.message.chat_id, text="Perhaps you can give us a location. /setlocation sp20")
		else:
			user_location = args[0]
			locations = self.locations[int(update.message.chat_id)]
			lat = 0
			lng = 0
			for location in locations:
				if location[0].lower() == user_location.lower():
					lat = float(location[1])
					lng = float(location[2])
					break

			message = ""
			if lat == 0 or lng == 0:
				message += "Cannot find a suitable location. Perhaps you want to use /showlocation"
			else:
				message += "Update current location to {0} {1},{2}".format(user_location, lat, lng)

			self.database.update_current_location(update.message.chat_id, lat, lng)
			self.chatids[int(update.message.chat_id)] = (float(lat), float(lng))
			bot.sendMessage(chat_id=update.message.chat_id, text=message)
			log.debug("Current location for {0} is {1} {2}".format(update.message.chat_id, lat, lng))
			m = self._query_data(update.message.chat_id, (float(lat), float(lng)))

			if m != None:
				bot.sendMessage(chat_id=update.message.chat_id, text=m)

	def addspeciallocation(self, bot, update, args):
		if len(args) < 3:
			bot.sendMessage(chat_id=update.message.chat_id, text="/addspeciallocation name lat lng")
		else:
			message = ""

			name = args[0]
			lat = float(args[1])
			lng = float(args[2])

			minlat = lat-self.radius
			maxlat = lat+self.radius

			minlng = lng-self.radius
			maxlng = lng+self.radius

			self.database.add_speciallocation(name, minlat, maxlat, minlng, maxlng)

			if minlat == 0 or maxlat == 0 or minlng == 0 or maxlng == 0:
				message += "Weird coordinate. Unable to add"
			else:
				message += "Added {0} to Special Location List".format(name)

			bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def removespeciallocation(self, bot, update, args):
		if len(args) < 1:
			bot.sendMessage(chat_id=update.message.chat_id, text="/removespeciallocation name")
		else:
			self.database.remove_speciallocation(name)
			bot.sendMessage(chat_id=update.message.chat_id, text="Removed")

	def showspeciallocation(self, bot, update):
		specials = self.database.get_all_speciallocation()
		message = ""
		for x in specials:
			message += "{0}\n".format(x)

		if len(specials) == 0:
			message += "No special location has been added."

		bot.sendMessage(chat_id=update.message.chat_id, text=message)

	def start(self):
		# test
		help_handler = CommandHandler('help', self._help)
		self.dispatcher.add_handler(help_handler)

		# Location Relevance #
		addlocation_handler = CommandHandler("addlocation", self.addlocation, pass_args=True)
		self.dispatcher.add_handler(addlocation_handler)

		removelocation_handler = CommandHandler("removelocation", self.removelocation, pass_args=True)
		self.dispatcher.add_handler(removelocation_handler)

		showlocation_handler = CommandHandler("showlocation", self.showlocation)
		self.dispatcher.add_handler(showlocation_handler)

		setlocation_handler = CommandHandler("setlocation", self.setlocation, pass_args=True)
		self.dispatcher.add_handler(setlocation_handler)

		addspeciallocation_handler = CommandHandler("addspeciallocation", self.addspeciallocation, pass_args=True)
		self.dispatcher.add_handler(addspeciallocation_handler)

		removespeciallocation_handler = CommandHandler("removespeciallocation", self.removespeciallocation, pass_args=True)
		self.dispatcher.add_handler(removespeciallocation_handler)

		showspeciallocation_handler = CommandHandler("showspeciallocation", self.showspeciallocation)
		self.dispatcher.add_handler(showspeciallocation_handler)

		# Filter #
		addfilter_handler = CommandHandler("addfilter", self.addfilter, pass_args=True)
		self.dispatcher.add_handler(addfilter_handler)

		removefilter_handler = CommandHandler("removefilter", self.removefilter, pass_args=True)
		self.dispatcher.add_handler(removefilter_handler)

		showfilter_handler = CommandHandler("showfilter", self.showfilter)
		self.dispatcher.add_handler(showfilter_handler)

		filterswitch_handler = CommandHandler("filteron", self.filterswitchf, pass_args=True)
		self.dispatcher.add_handler(filterswitch_handler)

		# Add existing chat ids back into the queue
		chatids = self.database.get_all_chatid()
		for chatid in chatids:
			log.info("Adding #{0} to job queue".format(chatid))
			job_alarm = Job(self._watch, 240.0 , context=chatid)
			self.updater.job_queue.put(job_alarm, next_t=0.0)

		self.updater.start_polling()
		self.updater.idle()


	################## Helper ###################
	def _update_chatid(self, chatid, lat, lng):
		#add to  database
		success = False
		if chatid not in self.chatids:
			success = self.database.add_chatid(chatid, lat, lng)
		else:
			success = self.database.update_current_location(chatid, lat, lng)

		#update current list
		self.chatids[int(chatid)] = (lat, lng)

		return success

	def _add_filter(self, chatid, names):
		if chatid not in self.chatids:
			log.warning("Chat ID {0} not in database".format(chatid))
			return False

		if chatid not in self.filters:
			log.warning("Chat ID {0} not in filters".format(chatid))
			return False

		for name in names:
			self.database.add_filter(chatid, name)
			self.filters[int(chatid)].append(name)

		return True

	def _remove_filter(self, chatid, names):
		if chatid not in self.chatids:
			log.warning("Chat ID {0} not in database".format(chatid))
			return False

		if chatid not in self.filters:
			log.warning("Chat ID {0} not in filters".format(chatid))
			return False
		log.info(self.filters[int(chatid)])
		for name in names:
			self.database.remove_filter(chatid, name)
			self.filters[int(chatid)].remove(name)

		return True

	def _add_location(self, chatid, name, lat, lng):
		if name == None or lat == None or lng == None:
			log.warning("name:{0} or lat:{1} or lng:{2} is None".format(name, lta, lng))
			return False

		if chatid not in self.chatids:
			log.warning("Chat ID {0} not in database".format(chatid))
			return False

		if chatid not in self.locations:
			log.warning("Chat ID {0} not in locations".format(chatid))
			return False

		self.database.add_location(chatid, name, float(lat), float(lng))
		self.locations[int(chatid)].append((name, float(lat), float(lng)))
		return True

	def _remove_location(self, chatid, name):
		if name == None:
			log.warning("name is None")
			return False

		if chatid not in self.chatids:
			log.warning("chatid not found")
			return False

		self.database.remove_location(chatid, name)
		for location in self.locations[int(chatid)]:
			if location[0] == name:
				self.locations[int(chatid)].remove(location)
				break

		return True

	def _get_location(self, location):
		reverse_geocode_result = self.gmaps.reverse_geocode(location)

		if len(reverse_geocode_result) == 0:
			self.logger.warning("No geocoding for {0}".format(location))
			return None
		elif "formatted_address" not in reverse_geocode_result[0]:
			self.logger.warning("Could not find any formatted address for {0}".formatted(location))
			return None
		else:
			return reverse_geocode_result[0]["formatted_address"]

	def _get_special_location(self, location):
		log.info("Getting special location for {0}".format(location))

		# Given location of the Pokemon
		pokemon_lat = float(location[0])
		pokemon_lng = float(location[1])

		min_lat = pokemon_lat - self.radius
		max_lat = pokemon_lat + self.radius

		min_lng = pokemon_lng - self.radius
		max_lng = pokemon_lng + self.radius

		return self.database.check_speciallocation(min_lat, max_lat,  min_lng, max_lng)

	def _get_location_by_name(self, location):
		log.info("Getting location for {0}".format(location))
		geocode_result = self.gmaps.geocode(location)

		if len(geocode_result) == 0:
			log.warning("No geocoding for {0}".format(location))
			return None
		elif "formatted_address" not in geocode_result[0]:
			log.warning("Could not find any formatted address for {0}".formatted(location))
			return None
		else:
			log.debug(geocode_result)
			return geocode_result
