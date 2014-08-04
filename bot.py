# -*- coding: utf-8 -*-
'''
OsberBot
Copyright 2014 Quentin Brault AKA Tititesouris
Contact: osberbot@gmail.com

This file is part of OsberBot.
OsberBot is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with OsberBot. If not, see <http://www.gnu.org/licenses/>.
'''

import math, time, datetime, calendar, random as moduleRand, os, sys, socket, re, MySQLdb, urllib2, traceback, json
from config import *

botName = "osberbot"
botOwner = "tititesouris"

database = MySQLdb.connect(host="localhost", user="osberbot", passwd=dbPass, db="osberbot")
cur = database.cursor()
cur.execute("UPDATE bot SET lastboot = UTC_TIMESTAMP")
cur.execute("SHOW COLUMNS FROM statuses")
powersNames = [column[0] for column in cur.fetchall()][3:-3]

def randNb(min, max):
   return moduleRand.randint(min, max)

def randItem(list):
   return moduleRand.choice(list)

def minmax(minimum, maximum, var):
   return min(maximum, max(minimum, var), var)

def getTime():
   return calendar.timegm(datetime.datetime.utcnow().utctimetuple())

def getTimeFromDate(date, pattern):
   return calendar.timegm(datetime.datetime.strptime(date, pattern).timetuple())

def isTime(timestamp):
   if getTime() >= timestamp:
      return True
   else:
      return False

def getChannelId(channel):
   cur.execute("SELECT id FROM channels WHERE name = %s", (channel,))
   try:
      id = int(cur.fetchone()[0])
   except:
      id = None
   return id

def getUserId(channelId, user):
   cur.execute("SELECT id FROM users WHERE channelId = %s AND name = %s", (channelId, user))
   try:
      id = int(cur.fetchone()[0])
   except:
      id = None
   return id

def hasStatus(channelId, user, statusId): # Not used
   userId = getUserId(channelId, user)
   if userId != None and channelId != None:
      cur.execute("SELECT users.* FROM channels INNER JOIN statuses ON channels.id = statuses.channelId INNER JOIN users ON statuses.id = users.statusId WHERE channels.id = %s AND users.id = %s AND statuses.id = %s", (channelId, userId, statusId))
      results = cur.fetchall()
      if len(results) > 0:
         return True
      else:
         return False
   else:
      return None

def getStatusPowers(statusId):
   cur.execute("SELECT * FROM statuses WHERE id = %s", (statusId,))
   results = cur.fetchall()
   powers = [power[0] for power in enumerate(results[0][3:-3]) if power[1]] # Indexes
   return [powersNames[id] for id in powers]

def getUserPowers(channelId, user):
   userId = getUserId(channelId, user)
   if userId != None and channelId != None:
      cur.execute("SELECT statuses.* FROM channels INNER JOIN statuses ON channels.id = statuses.channelId INNER JOIN users ON statuses.id = users.statusId WHERE channels.id = %s AND users.id = %s", (channelId, userId))
      results = cur.fetchall()
      powers = [power[0] for power in enumerate(results[0][3:-3]) if power[1]] # Indexes
      return [powersNames[id] for id in powers]
   else:
      return None

def hasPowers(channelId, user, powers):
   userPowers = getUserPowers(channelId, user)
   if userPowers != None:
      return all([power in userPowers for power in powers])
   else:
      return None

def isMod(channel, user):
   channelId = getChannelId(channel)
   userId = getUserId(channelId, user)
   if userId != None and channelId != None:
      cur.execute("SELECT isMod FROM users WHERE id = %s", (userId,))
      results = cur.fetchall()
      return results[0][0]
   else:
      return None

def isViewer(channel, user):
   channelId = getChannelId(channel)
   userId = getUserId(channelId, user)
   if userId != None and channelId != None:
      cur.execute("SELECT isViewer FROM users WHERE id = %s", (userId,))
      results = cur.fetchall()
      return results[0][0]
   else:
      return None

class bot:
   def __init__(self):
      self.irc = socket.socket() #Create socket connection
      self.messageQueue = [] # [channel, message]
      self.messageLimit = []
      self.nextPing = 0
   
   def boot(self):
      try: #Connect to Twitch
         self.irc.connect(("199.9.250.229", 6667))
      except:
         print "199.9.250.229 not responding, trying 199.9.253.199"
         try:
            self.irc.connect(("199.9.253.199", 6667))
         except:
            print "199.9.250.229 not responding, trying 199.9.253.210"
            try:
               self.irc.connect(("199.9.253.210", 6667))
            except:
               print "199.9.253.210 not responding, trying 199.9.250.239"
               self.irc.connect(("199.9.250.239", 6667))
      self.irc.send("PASS {}\r\n".format(twitchPass))
      self.irc.send("NICK {}\r\n".format(botName))
      self.irc.send("USER {} 0 * :{}\r\n".format(botName, botOwner))
      cur.execute("SELECT name FROM channels WHERE active = 1")
      channels = cur.fetchall()
      if len(channels) > 0:
         for channel in channels:
            print "Joining {}".format(channel[0])
            self.irc.send("JOIN #{}\r\n".format(channel[0]))
            time.sleep(0.4) # 3 per second max
      else: # If the bot was just reset
         self.addChannel(botName)
      self.irc.send("PRIVMSG #{} :Ready\r\n".format(botName))
      self.getData()

   def addMsg(self, channel, message):
      self.messageQueue.append([channel, message])
      self.messageLimit.append(getTime())
      self.sendMsgs()
   
   def sendMsgs(self):
      self.messageLimit = [time for time in self.messageLimit if not isTime(time+30)]
      if len(self.messageLimit) <= 90: #8 hour ban if more than 100msgs/30secs and mod.
         for message in self.messageQueue:
            if isMod(message[0], botName):
               self.irc.send("PRIVMSG #{} :{}\r\n".format(message[0], message[1]))
               cur.execute("INSERT INTO logs (channelId, userId, channel, name, message, timestamp) VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP)", (getChannelId(message[0]), getUserId(getChannelId(message[0]), botName), message[0], botName, message[1])) # Logs
               print "[{}] {}".format(message[0], message[1])
            self.messageQueue.remove(message)
      else:
         print "/!\ Message throttle /!\\"
   
   def getData(self):
      for line in self.irc.makefile():
         cur.execute("UPDATE bot SET lastping = %s", (getTime(),)) # Ping
         database.commit()
         data = line.strip("\r\n")
         self.sendMsgs() # Send messages in queue
         #print(data)
         if "PRIVMSG" in data.split(" ")[1] and not data.startswith(":jtv"): #:name!name@name.tmi.twitch.tv PRIVMSG #channel :message
            author = data.split(":")[1].split("!")[0]
            channel = data.split(" ")[2].strip("#")
            message = data.split(":", 2)[2]
            if author == botOwner:
               if message.lower().startswith("!impersonate ") and message.count(" ") >= 2:
                  author = message.lower().split(" ")[1]
                  message = message.split(" ", 2)[2]
            channelId = getChannelId(channel)
            authorChannelId = getChannelId(author)
            self.addUser(channelId, author)
            if channel == botName:
               if author == botOwner:
                  if message.lower() in ["reboot", "!reboot"]:
                     self.addMsg(channel, "Rebooting...")
                     database.commit()
                     cur.close()
                     database.close()
                     os.execv(os.path.realpath(sys.executable), [os.path.basename(sys.executable)] + sys.argv)
                  elif message.lower() in ["stop", "!stop"]:
                     self.addMsg(channel, "Shutting down...")
                     database.commit()
                     cur.close()
                     database.close()
                     sys.exit(datetime.datetime.utcfromtimestamp(getTime()).strftime("Script terminated the %d/%m/%Y at %H:%M:%S UTC."))
                  elif message.lower().startswith("!say ") and message.count(" ") >= 2:
                     self.addMsg(message.split(" ")[1], message.split(" ", 2)[2])
               if message.lower() == "!join":
                  if authorChannelId == None: # If the channel was never joined
                     self.addChannel(author)
                  else: # If the channel was joined
                     cur.execute("SELECT active FROM channels WHERE id = %s", (authorChannelId,))
                     if cur.fetchone()[0]: # If the channel is active
                        self.addMsg(channel, "Channel {} is already using OsberBot.".format(author))
                     else: # If the channel is not active
                        self.joinChannel(author, authorChannelId)
               elif message.lower() == "!leave":
                  if getChannelId(author) == None:
                     self.addMsg(channel, "Channel {} is not using OsberBot.".format(author))
                  else:
                     cur.execute("SELECT active FROM channels WHERE id = %s", (authorChannelId,))
                     if cur.fetchone()[0]:
                        self.partChannel(author, authorChannelId)
                     else:
                        self.addMsg(channel, "Channel {} is not using OsberBot.".format(author))
            database.commit() # Update all infos
            cur.execute("INSERT INTO logs (channelId, userId, channel, name, message, timestamp) VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP)", (channelId, getUserId(channelId, author), channel, author, message)) # Logs
            print "[{}] {}{}: {}".format(channel, isMod(channel, author)*"+", author, message)
            if message.startswith("!osberbot") and hasPowers(channelId, author, ["canosberbot"]):
               self.addMsg(channel, "You can find help and information about OsberBot at http://osberbot.com")
            elif message.startswith("!badword ") and hasPowers(channelId, author, ["canbadwords"]):
               MODERATION.badwords(channel, channelId, message.lower(), author)
            elif message.startswith("!cmd ") and hasPowers(channelId, author, ["cancommands"]):
               COMMANDS.input(channel, channelId, message, author)
            elif message.startswith("!ht") and hasPowers(channelId, author, ["canhighlight"]):
               HIGHLIGHTS.input(channel, channelId, author)
            elif message.startswith("!mod ") and hasPowers(channelId, author, ["canmod"]):
               MODERATION.input(channel, channelId, message.lower(), author)
            elif message.startswith("!news ") and hasPowers(channelId, author, ["cannews"]):
               NEWS.input(channel, channelId, message, author)
            elif message.startswith("!poll ") and hasPowers(channelId, author, ["canpolls"]):
               POLLS.input(channel, channelId, message, author)
            elif message.startswith("!vote ") and hasPowers(channelId, author, ["canvotepolls"]) and message.count(" ") >= 2:
               POLLS.vote(channel, channelId, message.split(" ")[1], message.split(" ", 2)[2], author)
            elif message.startswith("!permit ") and hasPowers(channelId, author, ["canpermit"]):
               MODERATION.permit(channel, channelId, message.split(" ")[0].lower())
            elif message.startswith("!quote") and hasPowers(channelId, author, ["canquotes"]):
               QUOTES.input(channel, channelId, message, author)
            elif message.startswith("!raffle ") and hasPowers(channelId, author, ["canraffles"]):
               RAFFLES.input(channel, channelId, message, author)
            elif message.startswith("!rand ") and hasPowers(channelId, author, ["canrandom"]):
               RANDOM.input(channel, channelId, message.lower(), author)
            elif message.startswith("!status ") and hasPowers(channelId, author, ["canstatuses"]):
               STATUSES.input(channel, channelId, message, author)
            elif message.startswith("!strike ") and hasPowers(channelId, author, ["canstrikes"]):
               MODERATION.input(channel, channelId, message.lower(), author)
            elif message.startswith("!title ") and hasPowers(channelId, author, ["cantitle"]):
               TITLE.input(channel, channelId, message, author)
            elif message.startswith("!"):
               COMMANDS.output(channel, channelId, message, author)
            else:
               if not isMod(channel, author):
                  MODERATION.output(channel, channelId, message, author)
               if hasPowers(channelId, author, ["canenterraffles"]):
                  RAFFLES.output(channel, channelId, message, author)
            
            UPDATES.input(channel, channelId)
         elif data.startswith(":jtv MODE"):
            user = data.split(" ")[4]
            channel = data.split(" ")[2].strip("#")
            mode = data.split(" ")[3]
            channelId = getChannelId(channel)
            self.addUser(channelId, user)
            if mode == "+o":
               print "[{}] {} is now mod.".format(channel, user)
               cur.execute("UPDATE users SET isMod = 1, lastMod = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (getTime(), getUserId(channelId, user)))
               cur.execute("SELECT hasStatus FROM users WHERE id = %s", (getUserId(channelId, user),))
               if not cur.fetchone()[0]: # If the user doesn't have a status
                  cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, "Moderator"))
                  result = cur.fetchone()
                  cur.execute("UPDATE users SET statusId = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (result[0], getUserId(channelId, user)))
                  print "[{}] {}'s status changed to Moderator.".format(channel, user)
            elif mode == "-o":
               print "[{}] {} is no longer mod.".format(channel, user)
               cur.execute("UPDATE users SET isMod = 0, timestamp = UTC_TIMESTAMP WHERE id = %s", (getUserId(channelId, user),))
               cur.execute("SELECT hasStatus, lastMod FROM users WHERE id = %s", (getUserId(channelId, user),))
               results = cur.fetchone()
               if not results[0] and isTime(results[1]+3600): # If the user doesn't have a status and has not been +oed in the past hour
                  cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, "Default"))
                  result = cur.fetchone()
                  cur.execute("UPDATE users SET statusId = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (result[0], getUserId(channelId, user)))
                  print "[{}] {}'s status changed to Default.".format(channel, user)
         elif "JOIN" in data:
            user = data.split(":")[1].split("!")[0]
            channel = data.split(" ")[2].strip("#")
            channelId = getChannelId(channel)
            self.addUser(channelId, user)
            cur.execute("UPDATE users SET isViewer = 1, timestamp = UTC_TIMESTAMP WHERE id = %s", (getUserId(channelId, user),))
            print "[{}] {} joined.".format(channel, user)
         elif "PART" in data:
            user = data.split(":")[1].split("!")[0]
            channel = data.split(" ")[2].strip("#")
            channelId = getChannelId(channel)
            self.addUser(channelId, user)
            cur.execute("UPDATE users SET isViewer = 0, isMod = 0, timestamp = UTC_TIMESTAMP WHERE id = %s", (getUserId(channelId, user),))
            print "[{}] {} left.".format(channel, user)
         elif "PING" in data:
            self.irc.send("PONG #{} \r\n".format(botName))
         database.commit()
   
   def addUser(self, channelId, user):
      cur.execute("SELECT id FROM users WHERE channelId = %s AND name = %s", (channelId, user))
      results = cur.fetchall()
      if len(results) == 0: # If the user is new to the channel
         cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, "Default"))
         results = cur.fetchone()
         cur.execute("INSERT INTO users (channelId, name, statusId, createdAt, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, user, results[0]))
         return cur.lastrowid
      else:
         return results[0][0]
   
   def addChannel(self, channel):
      cur.execute("INSERT INTO channels (name, createdAt, timestamp) VALUES (%s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channel,))
      channelId = cur.lastrowid
      cur.execute("INSERT INTO statuses (channelId, name, author, createdAt, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, "Default", botName)) # Creating Default status
      cur.execute("INSERT INTO statuses (channelId, name, canosberbot, cancaps, canlink, canswear, canspam, canemotes, canquotes, cangetquotes, canrandom, canrandomnumber, canrandomviewer, canrandomletter, canrandomdice, canrandomtext, canrandomelement, canrandomfruit, canrandomcolour, author, createdAt, timestamp) VALUES (%s, %s, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, "Regular", botName)) # Creating Regular status
      cur.execute("INSERT INTO statuses (channelId, name, {}, author, createdAt, timestamp) VALUES (%s, %s, {}, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)".format(", ".join(powersNames), ", ".join(["1"]*len(powersNames))), (channelId, "Moderator", botName)) # Creating Moderator status
      statusId = cur.lastrowid
      cur.execute("INSERT INTO users (channelId, name, statusId, isAdmin, createdAt, timestamp) VALUES (%s, %s, %s, 1, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, channel, statusId))
      self.addMsg(botName, "Channel {} is now using OsberBot.".format(channel))
      self.irc.send("JOIN #{}\r\n".format(channel))
   
   def joinChannel(self, channel, channelId):
      cur.execute("UPDATE channels SET active = 1, timestamp = UTC_TIMESTAMP WHERE id = %s", (channelId,))
      self.addMsg(botName, "Channel {} is now using OsberBot.".format(channel))
      self.irc.send("JOIN #{}\r\n".format(channel))
   
   def partChannel(self, channel, channelId):
      cur.execute("UPDATE channels SET active = 0, timestamp = UTC_TIMESTAMP WHERE id = %s", (channelId,))
      self.addMsg(botName, "Channel {} is no longer using OsberBot.".format(channel))
      self.irc.send("PART #{}\r\n".format(channel))
   
   def deleteChannel(self, channel, channelId):
      cur.execute("DELETE FROM channels WHERE id = %s", (channelId,))
      self.irc.send("PART #{}\r\n".format(channel))
BOT = bot()

class commands:
   def input(self, channel, channelId, message, author):
      if message.count(" ") >= 1:
         if message.split(" ")[1].lower() in ["list"]:
            if hasPowers(channelId, author, ["canlistcommands"]):
               self.list(channel, channelId)
         elif message.count(" ") >= 2:
            if message.split(" ")[1].lower() in ["rem", "remove", "del", "delete"]:
               if hasPowers(channelId, author, ["canremovecommands"]):
                  self.remove(channel, channelId, message.split(" ")[2].lower())
            elif message.count(" ") >= 3:
               if message.split(" ")[1].lower() in ["add", "new", "create"]:
                  if hasPowers(channelId, author, ["canaddcommands"]):
                     self.add(channel, channelId, message.split(" ")[2].lower(), message.split(" ", 3)[3], author)
               elif message.split(" ")[1].lower() in ["set", "status", "setstatus"]:
                  if hasPowers(channelId, author, ["cansetcommands"]):
                     self.set(channel, channelId, message.split(" ")[2].lower(), message.split(" ")[3].lower())
               else:
                  BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#commands")
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#commands")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#commands")
   
   def add(self, channel, channelId, name, text, author):
      if re.match("^[a-zA-Z0-9_]+$", name):
         if len(name) <= 100:
            if not name in ["osberbot", "bw", "calc", "cmd", "ht", "mod", "news", "permit", "poll", "quote", "raffle", "rand", "status", "strike", "vote"]:
               cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, "Moderator"))
               results = cur.fetchall()
               statusId = results[0][0]
               cur.execute("SELECT id FROM commands WHERE channelId = %s AND name = %s", (channelId, name))
               results = cur.fetchall()
               if len(results) == 0: # If the command does not exist
                  cur.execute("INSERT INTO commands (channelId, statusId, name, text, author, createdAt, timestamp) VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, statusId, name, text, author))
                  BOT.addMsg(channel, "The command '{}' has been created.".format(name))
               else:
                  cur.execute("UPDATE commands SET statusId = %s, text = %s, author = %s, timestamp = UTC_TIMESTAMP WHERE channelId = %s AND id = %s", (statusId, text, author, channelId, results[0][0]))
                  BOT.addMsg(channel, "The command '{}' has been updated.".format(name))
            else:
               BOT.addMsg(channel, "This command name is not available.")
         else:
            BOT.addMsg(channel, "The command name must not be longer than 100 characters.")
      else:
         BOT.addMsg(channel, "The command name must be composed of alpha-numeric characters or underscores.")
   
   def remove(self, channel, channelId, name):
      cur.execute("SELECT id FROM commands WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) == 1: # If the command exists
         cur.execute("DELETE FROM commands WHERE id = %s", (results[0][0],))
         BOT.addMsg(channel, "The command '{}' has been removed.".format(name))
      else:
         BOT.addMsg(channel, "The command '{}' does not exist.".format(name))
   
   def set(self, channel, channelId, name, status):
      cur.execute("SELECT id FROM commands WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) == 1: # If the command exists
         commandId = results[0][0]
         cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, status))
         results = cur.fetchall()
         if len(results) == 1: # If the status exists
            cur.execute("UPDATE commands SET statusId = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (results[0][0], commandId))
            BOT.addMsg(channel, "The status '{}' has been set for the command '{}'.".format(status, name))
         else:
            BOT.addMsg(channel, "The status '{}' does not exist.".format(status))
      else:
         BOT.addMsg(channel, "The command '{}' does not exist.".format(name))
   
   def list(self, channel, channelId):
      cur.execute("SELECT name FROM commands WHERE channelId = %s", (channelId,))
      results = cur.fetchall()
      if len(results) >= 1: # If the channel has at least 1 command
         BOT.addMsg(channel, "List of commands: {}.".format(", ".join(["'{}'".format(result[0]) for result in results])))
      else:
         BOT.addMsg(channel, "This channel does not have any command.")
   
   def output(self, channel, channelId, name, author):
      cur.execute("SELECT statusId, text FROM commands WHERE channelId = %s AND name = %s", (channelId, name.strip("!")))
      results = cur.fetchall()
      if len(results) == 1: # If the command exists
         statusId = results[0][0]
         text = results[0][1]
         if hasPowers(channelId, author, getStatusPowers(statusId)):
            BOT.addMsg(channel, text)
COMMANDS = commands()

class highlights:
   def input(self, channel, channelId, author):
      cur.execute("SELECT unixtime FROM highlights WHERE author = %s AND channelId = %s ORDER BY unixtime DESC LIMIT 1", (author, channelId))
      results = cur.fetchone()
      if not results or abs(int(results[0]) - getTime()) >= 60: # If the user hasn't !ht in the last minute
         url = "http://api.justin.tv/api/stream/list.json?channel={}".format(channel)
         results = json.loads(urllib2.urlopen(url).read())
         if results:
            startTimestamp = getTimeFromDate(results[0]["up_time"], "%a %b %d %H:%M:%S %Y")+7*3600 # UTC-7
            highlightTime = (getTime()-startTimestamp)//60*60
            cur.execute("INSERT INTO highlights (channelId, streamId, title, startTime, time, unixtime, author, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP)", (channelId, results[0]["id"], results[0]["title"], startTimestamp, highlightTime, getTime(), author))
HIGHLIGHTS = highlights()

class moderation:
   def input(self, channel, channelId, message, author):
      if message.count(" ") >= 2:
         if message.split(" ")[1] in ["caps", "links", "words", "spam", "emotes"]:
            self.mod(channel, channelId, message.split(" ")[1], message.split(" ")[2], author)
         elif message.split(" ")[1] in ["clear"]:
               if hasPowers(channelId, author, ["canclearstrikes"]):
                  self.clearStrike(channel, channelId, message.split(" ")[2])
         elif message.count(" ") >= 3:
            if message.split(" ")[1] in ["set"]:
               if hasPowers(channelId, author, ["cansetstrikes"]):
                  self.setStrike(channel, channelId, message.split(" ")[2], message.split(" ")[3])
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#moderation")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#moderation")
      else:
         BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#moderation")
   
   def mod(self, channel, channelId, mod, bool, author):
      if bool in ["true", "1", "on"]:
         cur.execute("UPDATE channels SET {} = 1, timestamp = UTC_TIMESTAMP WHERE id = %s".format("mod"+mod), (channelId,))
         BOT.addMsg(channel, "Now moderating {}.".format(mod))
      elif bool in ["false", "0", "off"]:
         cur.execute("UPDATE channels SET {} = 0, timestamp = UTC_TIMESTAMP WHERE id = %s".format("mod"+mod), (channelId,))
         BOT.addMsg(channel, "No longer moderating {}.".format(mod))
   
   def badwords(self, channel, channelId, message, author):
      if message.count(" ") >= 1:
         if message.split(" ")[1].lower() in ["list"]:
            if hasPowers(channelId, author, ["canlistbadwords"]):
               self.listBadwords(channel, channelId)
         elif message.count(" ") >= 2:
            if message.split(" ")[1] in ["add", "new", "create"]:
               if hasPowers(channelId, author, ["canaddbadwords"]):
                  self.addBadword(channel, channelId, message.split(" ", 2)[2], author)
            elif message.split(" ")[1] in ["rem", "remove", "del", "delete"]:
               if hasPowers(channelId, author, ["canremovebadwords"]):
                  self.removeBadword(channel, channelId, message.split(" ", 2)[2])
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#moderation")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#moderation")
   
   def addBadword(self, channel, channelId, text, author):
      if len(text) <= 100:
         cur.execute("SELECT id FROM badwords WHERE channelId = %s AND text = %s", (channelId, text))
         results = cur.fetchall()
         if len(results) == 0: # If the badword does not exist
            cur.execute("INSERT INTO badwords (channelId, text, author, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP)", (channelId, text, author))
            BOT.addMsg(channel, "'{}' has been added to the bad words list.".format(text))
         else:
            BOT.addMsg(channel, "'{}' is already in the bad words list.".format(text))
      else:
         BOT.addMsg(channel, "The text must not be longer than 100 characters.")
   
   def removeBadword(self, channel, channelId, text):
      cur.execute("SELECT id FROM badwords WHERE channelId = %s AND text = %s", (channelId, text))
      results = cur.fetchall()
      if len(results) == 1: # If the badword exists
         cur.execute("DELETE FROM badwords WHERE id = %s", (results[0][0],))
         BOT.addMsg(channel, "'{}' has been removed from the bad words list.".format(text))
      else:
         BOT.addMsg(channel, "'{}' is not in the bad words list.".format(text))
   
   def listBadwords(self, channel, channelId):
      cur.execute("SELECT name FROM badwords WHERE channelId = %s", (channelId,))
      results = cur.fetchall()
      if len(results) >= 1: # If the channel has at least 1 badword
         BOT.addMsg(channel, "List of bad words: {}.".format(", ".join(["'{}'".format(result[0]) for result in results])))
      else:
         BOT.addMsg(channel, "This channel does not have any bad word.")
   
   def setStrike(self, channel, channelId, id, time):
      try:
         id = int(id)
         time = int(time)
         if 1 <= id <= 5:
            if 0 <= time <= 604800: # 1 week max, 0 for perma ban
               cur.execute("UPDATE channels SET strike{} = %s, timestamp = UTC_TIMESTAMP WHERE id = %s".format(id), (time, channelId))
               BOT.addMsg(channel, "Strike {} time set to {} seconds.".format(id, time))
            else:
               BOT.addMsg(channel, "The strike time must be between 1 and 604800 seconds, or 0 second for a permanent ban.")
         else:
            BOT.addMsg(channel, "The strike id must be between 1 and 5.")
      except:
         BOT.addMsg(channel, "Invalid id or time.")
   
   def clearStrike(self, channel, channelId, name):
      userId = BOT.addUser(channelId, name)
      cur.execute("UPDATE users SET strikes = 0, timestamp = UTC_TIMESTAMP WHERE id = %s", (userId,))
      BOT.addMsg(channel, "Strikes cleared for {}.".format(name.capitalize()))
   
   def strike(self, channel, channelId, user):
      cur.execute("SELECT id, strikes FROM users WHERE channelId = %s AND name = %s", (channelId, user))
      results = cur.fetchall()
      userId = results[0][0]
      nbStrike = int(results[0][1])+1
      cur.execute("SELECT strike{} FROM channels WHERE id = %s".format(nbStrike), (channelId,))
      results = cur.fetchall()
      if results[0][0] == 0:
         self.ban(channel, user)
      else:
         self.kick(channel, user, results[0][0])
      if nbStrike == 5:
         nbStrike = 0
      cur.execute("UPDATE users SET strikes = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (nbStrike, userId))
   
   def permit(self, channel, channelId, name):
      userId = BOT.addUser(channelId, name)
      cur.execute("UPDATE users SET permitted = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (getTime()+60, userId))
      BOT.addMsg(channel, "{} has been permitted for 60 seconds.".format(name.capitalize()))
   
   def kick(self, channel, user, time=1):
      BOT.irc.send("PRIVMSG #{} :/timeout {} {}\r\n".format(channel, user, time))
   
   def ban(self, channel, user):
      BOT.irc.send("PRIVMSG #{} :/ban {} \r\n".format(channel, user))
   
   def unban(self, channel, user):
      BOT.irc.send("PRIVMSG #{} :/unban {}\r\n".format(channel, user))
   
   def slow(self, channel, time=60):
      BOT.irc.send("PRIVMSG #{} :/slow {}\r\n".format(channel, time))
   
   def slowOff(self, channel):
      BOT.irc.send("PRIVMSG #{} :/slowoff\r\n".format(channel))
   
   def subs(self, channel):
      BOT.irc.send("PRIVMSG #{} :/subscribers\r\n".format(channel))
   
   def subsOff(self, channel):
      BOT.irc.send("PRIVMSG #{} :/subscribersoff\r\n".format(channel))
   
   def ads(self, channel, time=30):
      BOT.irc.send("PRIVMSG #{} :/commercial {} \r\n".format(channel, minmax(30, 180, time//30*30)))
   
   def output(self, channel, channelId, message, author):
      cur.execute("SELECT modcaps, modlinks, modwords, modspam, modemotes FROM channels WHERE id = %s", (channelId,))
      mods = cur.fetchall()[0]
      cur.execute("SELECT permitted FROM users WHERE channelId = %s and name = %s", (channelId, author))
      results = cur.fetchall()
      if isTime(results[0][0]): # If the user is not permitted
         if mods[0] and not hasPowers(channelId, author, ["cancaps"]): # Caps
            if message.count(" ") > 2 and len(message) > 8 and len(re.findall("[A-Z]", message)) >= len(message.replace(" ", ""))*(3.0/4):
               BOT.addMsg(channel, "Watch the caps {}!".format(author.capitalize()))
               print "Caps"
               self.strike(channel, channelId, author)
         if mods[1] and not hasPowers(channelId, author, ["canlink"]): # Links
            if re.match("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", message):
               BOT.addMsg(channel, "No links in this chat {}!".format(author.capitalize()))
               print "Links"
               self.strike(channel, channelId, author)
         if mods[2] and not hasPowers(channelId, author, ["canswear"]): # Words
            cur.execute("SELECT text FROM badwords WHERE channelId = %s", (channelId,))
            badwords = [result[0] for result in cur.fetchall()]
            if any([badword in message.lower() for badword in badwords]):
               BOT.addMsg(channel, "Watch your language {}!".format(author.capitalize()))
               print "Swear"
               self.strike(channel, channelId, author)
         if mods[3] and not hasPowers(channelId, author, ["canspam"]): # Spam
            r = re.compile(r"(.+?)\1+")
            repetitions = [[match.group(1), len(match.group(0))/len(match.group(1))] for match in r.finditer(message)]
            if any([len(repetition[0]) > 5 and repetition[1] > 5 for repetition in repetitions]):
               BOT.addMsg(channel, "No spamming {}!".format(author.capitalize()))
               print "Spam"
               self.strike(channel, channelId, author)
            if len(message) > 30 and len(re.findall("[a-zA-Z0-9_\- ]", message)) < len(message)*(1.0/4):
               BOT.addMsg(channel, "No spamming symbols {}!".format(author.capitalize()))
               print "Spam symbols"
               self.strike(channel, channelId, author)
         if mods[4] and not hasPowers(channelId, author, ["canemotes"]): # Emotes
            if 1==0:
               print "Emotes"
               self.strike(channel, channelId, author)
MODERATION = moderation()

class news:
   def input(self, channel, channelId, message, author):
      if message.count(" ") >= 1:
         if message.split(" ")[1].lower() in ["get", "fetch", "retrieve"]:
            if hasPowers(channelId, author, ["cangetnews"]):
               self.get(channel, channelId)
         elif message.split(" ")[1].lower() in ["on", "activate"]:
            if hasPowers(channelId, author, ["canturnonnews"]):
               self.turnOn(channel, channelId)
         elif message.split(" ")[1].lower() in ["off", "deactivate"]:
            if hasPowers(channelId, author, ["canturnoffnews"]):
               self.turnOff(channel, channelId)
         elif message.count(" ") >= 2:
            if message.split(" ")[1].lower() in ["add", "new", "create"]:
               if hasPowers(channelId, author, ["canaddnews"]):
                  self.add(channel, channelId, message.split(" ", 2)[2], author)
            elif message.split(" ")[1].lower() in ["rem", "remove", "del", "delete"]:
               if hasPowers(channelId, author, ["canremovenews"]):
                  self.remove(channel, channelId, message.split(" ")[2])
            elif message.split(" ")[1].lower() in ["time", "settime"]:
               if hasPowers(channelId, author, ["cantimenews"]):
                  self.time(channel, channelId, message.split(" ")[2])
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#news")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#news")
      else:
         BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#news")
   
   def add(self, channel, channelId, text, author):
      cur.execute("INSERT INTO news (channelId, text, author, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP)", (channelId, text, author))
      BOT.addMsg(channel, "The news has been created.")
   
   def remove(self, channel, channelId, newsId):
      cur.execute("SELECT id FROM news WHERE channelId = %s ORDER BY id", (channelId,))
      results = cur.fetchall()
      try:
         newsId = int(newsId)
         if newsId > 0:
            if len(results) >= newsId:
               cur.execute("DELETE FROM news WHERE id = %s", (results[newsId-1][0],))
               BOT.addMsg(channel, "News {} has been removed.".format(newsId))
            else:
               BOT.addMsg(channel, "News {} does not exist.".format(newsId))
         else:
            BOT.addMsg(channel, "The news id must be a positive integer.")
      except:
         BOT.addMsg(channel, "Invalid news id.")
   
   def time(self, channel, channelId, interval):
      try:
         interval = int(interval)
         if 60 <= interval <= 86400:
            cur.execute("UPDATE channels SET newsinterval = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (interval, channelId))
            BOT.addMsg(channel, "News are now displayed every {} seconds.".format(interval))
         else:
            BOT.addMsg(channel, "The time interval must be between 60 seconds and 86400 seconds.")
      except:
         BOT.addMsg(channel, "Invalid time interval.")
   
   def turnOn(self, channel, channelId):
      cur.execute("UPDATE channels SET displaynews = 1, timestamp = UTC_TIMESTAMP WHERE id = %s", (channelId,))
      BOT.addMsg(channel, "Now displaying news.")
   
   def turnOff(self, channel, channelId):
      cur.execute("UPDATE channels SET displaynews = 0, timestamp = UTC_TIMESTAMP WHERE id = %s", (channelId,))
      BOT.addMsg(channel, "No longer displaying news.")
   
   def get(self, channel, channelId):
      cur.execute("SELECT text FROM news WHERE channelId = %s ORDER BY id", (channelId,))
      news = cur.fetchall()
      if len(news) > 0:
         cur.execute("SELECT currentnews FROM channels WHERE id = %s", (channelId,))
         currentNews = cur.fetchone()[0]
         BOT.addMsg(channel, "[News {}] {}".format(currentNews+1, news[currentNews][0]))
         if currentNews < len(news)-1:
            currentNews += 1
         else:
            currentNews = 0
         cur.execute("UPDATE channels SET currentnews = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (currentNews, channelId))
NEWS = news()

# TODO Tweet polls!
class polls:
   def input(self, channel, channelId, message, author):
      if message.count(" ") >= 2:
         if message.split(" ")[1].lower() in ["rem", "remove", "del", "delete"]:
            if hasPowers(channelId, author, ["canremovepolls"]):
               self.remove(channel, channelId, message.split(" ")[2])
         elif message.split(" ")[1].lower() in ["open"]:
            if hasPowers(channelId, author, ["canopenpolls"]):
               self.open(channel, channelId, message.split(" ")[2])
         elif message.split(" ")[1].lower() in ["close"]:
            if hasPowers(channelId, author, ["canclosepolls"]):
               self.close(channel, channelId, message.split(" ")[2])
         elif message.split(" ")[1].lower() in ["time"]:
            if hasPowers(channelId, author, ["cantimepolls"]):
               self.time(channel, channelId, message.split(" ")[2])
         elif message.split(" ")[1].lower() in ["get", "fetch", "retrieve"]:
            if hasPowers(channelId, author, ["cangetpolls"]):
               self.get(channel, channelId, message.split(" ")[2])
         elif message.count(" ") >= 3:
            if message.split(" ")[1].lower() in ["add", "new", "create"]:
               if hasPowers(channelId, author, ["canaddpolls"]):
                  self.add(channel, channelId, message.split(" ")[2], message.split(" ", 3)[3], author)
            elif message.count(" ") >= 4 and message.split(" ")[1].lower() in ["option", "options"]:
               if message.split(" ")[2].lower() in ["add", "new", "create"]:
                  if hasPowers(channelId, author, ["canaddpolloptions"]):
                     self.addOption(channel, channelId, message.split(" ")[3], message.split(" ", 4)[4], author)
               elif message.split(" ")[2].lower() in ["rem", "remove", "del", "delete"]:
                  if hasPowers(channelId, author, ["canremovepolloptions"]):
                     self.removeOption(channel, channelId, message.split(" ")[3], message.split(" ", 4)[4])
               else:
                  BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#polls")
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#polls")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#polls")
      else:
         BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#polls")
   
   def add(self, channel, channelId, name, description, author):
      if re.match("^[a-zA-Z0-9_]+$", name):
         if len(name) <= 100:
            cur.execute("SELECT id FROM polls WHERE channelId = %s AND name = %s", (channelId, name))
            results = cur.fetchall()
            if len(results) == 0: # If the poll does not exist
               cur.execute("INSERT INTO polls (channelId, name, description, author, createdAt, timestamp) VALUES (%s, %s, %s, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, name, description, author))
               BOT.addMsg(channel, "Poll '{0}' has been created. Type '!poll option add {0} [option]' to create an option to vote for.".format(name))
            else:
               BOT.addMsg(channel, "Poll '{}' already exists.".format(name))
         else:
            BOT.addMsg(channel, "The poll name must not be longer than 100 characters.")
      else:
         BOT.addMsg(channel, "The poll name must be composed of alpha-numeric characters or underscores.")
   
   def remove(self, channel, channelId, name):
      cur.execute("SELECT id FROM polls WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) == 1: # If the poll exists
         cur.execute("DELETE FROM polls WHERE id = %s", (results[0][0],))
         BOT.addMsg(channel, "Poll '{}' has been removed.".format(name))
      else:
         BOT.addMsg(channel, "Poll '{}' does not exist.".format(name))
   
   def addOption(self, channel, channelId, poll, name, author):
      if re.match("^[a-zA-Z0-9_ ]+$", name):
         if len(name) <= 100:
            cur.execute("SELECT id, open FROM polls WHERE channelId = %s AND name = %s", (channelId, poll))
            results = cur.fetchall()
            if len(results) == 1: # If the poll exists
               pollId = results[0][0]
               isOpen = results[0][1]
               cur.execute("SELECT name FROM pollOptions WHERE pollId = %s AND name = %s", (pollId, name))
               results = cur.fetchall()
               if len(results) == 0: # If the option does not exist
                  cur.execute("INSERT INTO pollOptions (pollId, name, author, createdAt, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (pollId, name, author))
                  BOT.addMsg(channel, "Option '{}' for poll '{}' created.{}".format(name, poll, (1-isOpen)*" Type '!poll open {}' to open the poll to votes.".format(poll)))
               else:
                  BOT.addMsg(channel, "Option '{}' for poll '{}' already exists.".format(name, poll))
            else:
               BOT.addMsg(channel, "Poll '{}' does not exist.".format(poll))
         else:
            BOT.addMsg(channel, "The option name must not be longer than 100 characters.")
      else:
         BOT.addMsg(channel, "The option name must be composed of alpha-numeric characters, underscores or spaces.")
   
   def removeOption(self, channel, channelId, poll, name):
      cur.execute("SELECT id FROM polls WHERE channelId = %s AND name = %s", (channelId, poll))
      results = cur.fetchall()
      if len(results) == 1: # If the poll exists
         cur.execute("SELECT id FROM pollOptions WHERE pollId = %s and name = %s", (results[0][0], name))
         results = cur.fetchall()
         if len(results) == 1: # If the option exists
            cur.execute("DELETE FROM pollOptions WHERE id = %s", (results[0][0],))
            BOT.addMsg(channel, "Option '{}' for poll '{}' has been removed.".format(name, poll))
         else:
            BOT.addMsg(channel, "Option '{}' for poll '{}' does not exist.".format(name, poll))
      else:
         BOT.addMsg(channel, "Poll '{}' does not exist.".format(poll))
   
   def get(self, channel, channelId, name):
      cur.execute("SELECT id FROM polls WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) == 1: # If the poll exists
         BOT.addMsg(channel, "Votes for poll '{0}': http://osberbot.com/poll/{1}. Type '!poll vote {0} [option]' to vote.".format(name, results[0][0]))
      else:
         BOT.addMsg(channel, "Poll '{}' does not exist.".format(name.lower()))
   
   def display(self, channel, channelId):
      cur.execute("SELECT id, name FROM polls WHERE channelId = %s AND open = 1", (channelId,))
      polls = cur.fetchall()
      if len(polls) > 0:
         if len(polls) == 1:
            BOT.addMsg(channel, "Poll {0} is open http://osberbot.com/poll/{1}. Type '!vote {0} [option]' to vote.".format(polls[0][1], polls[0][0]))
         else:
            BOT.addMsg(channel, "There are {} polls open: {}. Type '!vote [poll] [option]' to vote.".format(len(polls), ", ".join(["{} http://osberbot.com/poll/{}".format(poll[1], poll[0]) for poll in polls])))
   
   def vote(self, channel, channelId, poll, option, author):
      userId = getUserId(channelId, author)
      cur.execute("SELECT id, open FROM polls WHERE channelId = %s AND name = %s", (channelId, poll))
      results = cur.fetchall()
      if len(results) == 1: # If the poll exists
         if results[0][1]: # If the poll is open
            pollId = results[0][0]
            cur.execute("SELECT id FROM pollOptions WHERE pollId = %s and name = %s", (pollId, option))
            results = cur.fetchall()
            if len(results) == 1: # If the option exists
               optionId = results[0][0]
               cur.execute("SELECT id FROM pollVotes WHERE pollId = %s and userId = %s", (pollId, userId))
               results = cur.fetchall()
               if len(results) == 0: # If the user has not voted
                  cur.execute("UPDATE pollOptions SET score = score+1, timestamp = UTC_TIMESTAMP WHERE id = %s", (optionId,))
                  cur.execute("INSERT INTO pollVotes (pollId, userId, timestamp) VALUES (%s, %s, UTC_TIMESTAMP)", (pollId, userId))
   
   def open(self, channel, channelId, name):
      cur.execute("SELECT id FROM polls WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) == 1: # If the poll exists
         pollId = results[0][0]
         cur.execute("SELECT name FROM pollOptions WHERE pollId = %s", (pollId,))
         results = cur.fetchall()
         if len(results) > 0: # If the poll has at least one option
            cur.execute("UPDATE polls SET open = 1, timestamp = UTC_TIMESTAMP WHERE id = %s", (pollId,))
            BOT.addMsg(channel, "Poll '{0}' has been opened. Type '!poll vote {0} [option]' to vote. The options for poll '{0}' are: {1}.".format(name.lower(), ", ".join([result[0] for result in results])))
         else:
            BOT.addMsg(channel, "Poll '{0}' has no options to vote for. Type '!poll option add {0} [option]' to create one.".format(name.lower()))
      else:
         BOT.addMsg(channel, "Poll '{}' does not exist.".format(name.lower()))
   
   def close(self, channel, channelId, name):
      cur.execute("SELECT id FROM polls WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) == 1: # If the poll exists
         cur.execute("UPDATE polls SET open = 0, timestamp = UTC_TIMESTAMP WHERE id = %s", (results[0][0],))
         BOT.addMsg(channel, "Poll '{}' has been closed. You can no longer vote.".format(name.lower()))
      else:
         BOT.addMsg(channel, "Poll '{}' does not exist.".format(name.lower()))
   
   def time(self, channel, channelId, interval):
      try:
         interval = int(interval)
         if 60 <= interval <= 86400:
            cur.execute("UPDATE channels SET pollsinterval = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (interval, channelId))
            BOT.addMsg(channel, "Open polls are now displayed every {} seconds.".format(interval))
         else:
            BOT.addMsg(channel, "The time interval must be between 60 seconds and 86400 seconds.")
      except:
         BOT.addMsg(channel, "Invalid time interval.")
POLLS = polls()

class quotes:
   def input(self, channel, channelId, message, author):
      if message.count(" ") == 0:
         if hasPowers(channelId, author, ["cangetquotes"]):
            self.get(channel, channelId, [])
      elif message.count(" ") >= 1:
         if message.split(" ")[1].lower() in ["get", "fetch", "retrieve"]:
            if hasPowers(channelId, author, ["cangetquotes"]):
               if message.count(" ") >= 2:
                  keywords = message.replace("; ", ";").split(" ")[2].split(";")
               else:
                  keywords = []
               self.get(channel, channelId, keywords)
         elif message.count(" ") >= 2:
            if message.split(" ")[1].lower() in ["add", "new"]:
               if hasPowers(channelId, author, ["canaddquotes"]):
                  self.add(channel, channelId, message.split(" ", 2)[2], author)
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#quotes")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#quotes")
      else:
         BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#quotes")
   
   def add(self, channel, channelId, quote, author):
      cur.execute("INSERT INTO quotes (channelId, text, author, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP)", (channelId, quote, author))
      BOT.addMsg(channel, "The quote has been added.")
   
   def remove(self, channel, channelId, quoteId):
      cur.execute("SELECT id FROM quotes WHERE channelId = %s ORDER BY id", (channelId,))
      results = cur.fetchall()
      try:
         quoteId = int(quoteId)
         if quoteId > 0:
            if len(results) >= quoteId:
               cur.execute("DELETE FROM quotes WHERE id = %s", (results[quoteId-1][0],))
               BOT.addMsg(channel, "Quote {} has been removed.".format(quoteId))
            else:
               BOT.addMsg(channel, "Quote {} does not exist.".format(quoteId))
         else:
            BOT.addMsg(channel, "The quote id must be a positive integer.")
      except:
         BOT.addMsg(channel, "Invalid quote id.")
   
   def get(self, channel, channelId, keywords):
      cur.execute("SELECT text FROM quotes WHERE channelId = %s ORDER BY id", (channelId,))
      results = cur.fetchall()
      quotes = [result[0] for result in results]
      if len(keywords) > 0: # If there are keywords
         cur.execute("SELECT DISTINCT text FROM quotes WHERE channelId = %s AND text RLIKE %s", (channelId, "|".join(keywords)))
         matches = cur.fetchall()
         if len(matches) > 0:
            quoteMatch = randItem(matches)[0]
            quoteId = quotes.index(quoteMatch)+1
            if len(matches) == 1:
               BOT.addMsg(channel, "[Quote {}] {}".format(quoteId, quoteMatch))
            else:
               BOT.addMsg(channel, "{} quote(s) found. [Quote {}] {}".format(len(matches), quoteId, quoteMatch))
         else:
            BOT.addMsg(channel, "Could not find any quote matching the keywords.")
      else:
         quoteId = randNb(0, len(quotes)-1)
         BOT.addMsg(channel, "[Quote {}] {}".format(quoteId+1, quotes[quoteId]))
QUOTES = quotes()

class raffles:
   def input(self, channel, channelId, message, author):
      if message.count(" ") >= 1:
         if message.split(" ")[1].lower() in ["on", "activate"]:
            if hasPowers(channelId, author, ["canturnonraffles"]):
               self.turnOn(channel, channelId)
         elif message.split(" ")[1].lower() in ["off", "deactivate"]:
            if hasPowers(channelId, author, ["canturnoffraffles"]):
               self.turnOff(channel, channelId)
         elif message.split(" ")[1].lower() in ["get", "fetch", "retrieve"]:
            if hasPowers(channelId, author, ["cangetraffles"]):
               self.get(channel, channelId)
         elif message.count(" ") == 2:
            if message.split(" ")[1].lower() in ["add", "new", "create", "reset", "clear"]:
               if hasPowers(channelId, author, ["canaddraffles"]):
                  self.add(channel, channelId, message.split(" ")[2], author)
            elif message.split(" ")[1].lower() in ["rem", "remove", "del", "delete"]:
               if hasPowers(channelId, author, ["canremoveraffles"]):
                  self.remove(channel, channelId, message.split(" ")[2])
            elif message.split(" ")[1].lower() in ["open"]:
               if hasPowers(channelId, author, ["canopenraffles"]):
                  self.open(channel, channelId, message.split(" ")[2])
            elif message.split(" ")[1].lower() in ["close"]:
               if hasPowers(channelId, author, ["cancloseraffles"]):
                  self.close(channel, channelId, message.split(" ")[2])
            elif message.split(" ")[1].lower() in ["time"]:
               if hasPowers(channelId, author, ["cantimeraffles"]):
                  self.time(channel, channelId, message.split(" ")[2])
            elif message.split(" ")[1].lower() in ["draw"]:
               if hasPowers(channelId, author, ["candrawraffles"]):
                  self.draw(channel, channelId, message.split(" ")[2])
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#raffles")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#raffles")
   
   def add(self, channel, channelId, name, author):
      if re.match("^[a-zA-Z0-9_]+$", name):
         if len(name) <= 100:
            cur.execute("SELECT id FROM raffles WHERE channelId = %s AND name = %s", (channelId, name))
            results = cur.fetchall()
            if len(results) == 0: # If the raffle does not exist
               cur.execute("INSERT INTO raffles (channelId, name, author, createdAt, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, name, author))
               BOT.addMsg(channel, "Raffle '{0}' has been created. Type '{0}' in the chat to enter.".format(name))
            else:
               BOT.addMsg(channel, "Raffle '{0}' has been reset. Type '{0}' in the chat to enter.".format(name))
         else:
            BOT.addMsg(channel, "The raffle name must not be longer than 100 characters.")
      else:
         BOT.addMsg(channel, "The raffle name must be composed of alpha-numeric characters or underscores.")
   
   def remove(self, channel, channelId, name):
      cur.execute("SELECT id FROM raffles WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) > 0: # If the raffle exists
         raffleId = results[0][0]
         cur.execute("DELETE FROM raffles WHERE id = %s", (raffleId,))
         cur.execute("DELETE FROM raffleParticipants WHERE raffleId = %s", (raffleId,))
         BOT.addMsg(channel, "Raffle '{}' has been removed.".format(name))
      else:
         BOT.addMsg(channel, "Raffle '{}' does not exist.".format(name))
   
   def open(self, channel, channelId, name):
      cur.execute("SELECT id FROM raffles WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) > 0: # If the raffle exists
         cur.execute("UPDATE raffles SET open = 1 WHERE id = %s", (results[0][0],))
         BOT.addMsg(channel, "Raffle '{0}' is now open. Type '{0}' in the chat to enter.".format(name))
      else:
         BOT.addMsg(channel, "Raffle '{}' does not exist.".format(name))
   
   def close(self, channel, channelId, name):
      cur.execute("SELECT id FROM raffles WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) > 0: # If the raffle exists
         cur.execute("UPDATE raffles SET open = 0 WHERE id = %s", (results[0][0],))
         BOT.addMsg(channel, "Raffle '{0}' has been closed. You cannot enter anymore.".format(name))
      else:
         BOT.addMsg(channel, "Raffle '{}' does not exist.".format(name))
   
   def time(self, channel, channelId, interval):
      try:
         interval = int(interval)
         if 60 <= interval <= 86400:
            cur.execute("UPDATE channels SET rafflesinterval = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (interval, channelId))
            BOT.addMsg(channel, "Open raffles are now displayed every {} seconds.".format(interval))
         else:
            BOT.addMsg(channel, "The time interval must be between 60 seconds and 86400 seconds.")
      except:
         BOT.addMsg(channel, "Invalid time interval.")
   
   def draw(self, channel, channelId, name):
      cur.execute("SELECT id FROM raffles WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) > 0: # If the raffle exists
         raffleId = results[0][0]
         cur.execute("SELECT id, name FROM raffleParticipants WHERE raffleId = %s ORDER BY RAND() LIMIT 1", (raffleId,))
         results = cur.fetchall()
         if len(results) > 0: # If the raffle has participants
            BOT.addMsg(channel, "Drawing raffle '{}'. {} was selected!".format(name, results[0][1].capitalize()))
            cur.execute("DELETE FROM raffleParticipants WHERE raffleId = %s AND userId = %s", (raffleId, results[0][0]))
         else:
            BOT.addMsg(channel, "Raffle '{}' does not have any participant.".format(name))
      else:
         BOT.addMsg(channel, "Raffle '{}' does not exist.".format(name))
   
   def turnOn(self, channel, channelId):
      cur.execute("UPDATE channels SET displayraffles = 1, timestamp = UTC_TIMESTAMP WHERE id = %s", (channelId,))
      BOT.addMsg(channel, "Now displaying raffles.")
   
   def turnOff(self, channel, channelId):
      cur.execute("UPDATE channels SET displayraffles = 0, timestamp = UTC_TIMESTAMP WHERE id = %s", (channelId,))
      BOT.addMsg(channel, "No longer displaying raffles.")
   
   def output(self, channel, channelId, name, author):
      userId = getUserId(channelId, author)
      cur.execute("SELECT id FROM raffles WHERE channelId = %s AND name = %s AND open = 1", (channelId, name))
      results = cur.fetchall()
      if len(results) > 0: # If the raffle exists
         raffleId = results[0][0]
         cur.execute("SELECT id FROM raffleParticipants WHERE raffleId = %s AND userId = %s", (raffleId, userId))
         results = cur.fetchall()
         if len(results) == 0: # If the user has not entered the raffle
            cur.execute("INSERT INTO raffleParticipants (raffleId, userId, timestamp) VALUES (%s, %s, UTC_TIMESTAMP)", (raffleId, userId))
   
   def display(self, channel, channelId):
      cur.execute("SELECT name FROM raffles WHERE channelId = %s AND open = 1", (channelId,))
      raffles = cur.fetchall()
      if len(raffles) > 0:
         if len(raffles) == 1:
            BOT.addMsg(channel, "Raffle {0} is open: Type '{0}' to enter.".format(raffles[0][0]))
         else:
            BOT.addMsg(channel, "There are {} raffles open: {}. Type their name in chat to enter.".format(len(raffles), ", ".join([raffle[0] for raffle in raffles])))
RAFFLES = raffles()

class random:
   def __init__(self):
      self.elements = [
         ["H", "Hydrogen"],
         ["He", "Helium"],
         ["Li", "Lithium"],
         ["Be", "Beryllium"],
         ["B", "Boron"],
         ["C", "Carbon"],
         ["N", "Nitrogen"],
         ["O", "Oxygen"],
         ["F", "Fluorine"],
         ["Ne", "Neon"],
         ["Na", "Sodium"],
         ["Mg", "Magnesium"],
         ["Al", "Aluminium"],
         ["Si", "Silicon"],
         ["P", "Phosphorus"],
         ["S", "Sulfur"],
         ["Cl", "Chlorine"],
         ["Ar", "Argon"],
         ["K", "Potassium"],
         ["Ca", "Calcium"],
         ["Sc", "Scandium"],
         ["Ti", "Titanium"],
         ["V", "Vanadium"],
         ["Cr", "Chromium"],
         ["Mn", "Manganese"],
         ["Fe", "Iron"],
         ["Co", "Cobalt"],
         ["Ni", "Nickel"],
         ["Cu", "Copper"],
         ["Zn", "Zinc"],
         ["Ga", "Gallium"],
         ["Ge", "Germanium"],
         ["As", "Arsenic"],
         ["Se", "Selenium"],
         ["Br", "Bromine"],
         ["Kr", "Krypton"],
         ["Rb", "Rubidium"],
         ["Sr", "Strontium"],
         ["Y", "Yttrium"],
         ["Zr", "Zirconium"],
         ["Nb", "Niobium"],
         ["Mo", "Molybdenum"],
         ["Tc", "Technetium"],
         ["Ru", "Ruthenium"],
         ["Rh", "Rhodium"],
         ["Pd", "Palladium"],
         ["Ag", "Silver"],
         ["Cd", "Cadmium"],
         ["In", "Indium"],
         ["Sn", "Tin"],
         ["Sb", "Antimony"],
         ["Te", "Tellurium"],
         ["I", "Iodine"],
         ["Xe", "Xenon"],
         ["Cs", "Cesium"],
         ["Ba", "Barium"],
         ["La", "Lanthanum"],
         ["Ce", "Cerium"],
         ["Pr", "Praseodymium"],
         ["Nd", "Neodymium"],
         ["Pm", "Promethium"],
         ["Sm", "Samarium"],
         ["Eu", "Europium"],
         ["Gd", "Gadolinium"],
         ["Tb", "Terbium"],
         ["Dy", "Dysprosium"],
         ["Ho", "Holmium"],
         ["Er", "Erbium"],
         ["Tm", "Thulium"],
         ["Yb", "Ytterbium"],
         ["Lu", "Lutetium"],
         ["Hf", "Hafnium"],
         ["Ta", "Tantalum"],
         ["W", "Tungsten"],
         ["Re", "Rhenium"],
         ["Os", "Osmium"],
         ["Ir", "Iridium"],
         ["Pt", "Platinum"],
         ["Au", "Gold"],
         ["Hg", "Mercury"],
         ["Tl", "Thallium"],
         ["Pb", "Lead"],
         ["Bi", "Bismuth"],
         ["Po", "Polonium"],
         ["At", "Astatine"],
         ["Rn", "Radon"],
         ["Fr", "Francium"],
         ["Ra", "Radium"],
         ["Ac", "Actinium"],
         ["Th", "Thorium"],
         ["Pa", "Protactinium"],
         ["U", "Uranium"],
         ["Np", "Neptunium"],
         ["Pu", "Plutonium"],
         ["Am", "Americium"],
         ["Cm", "Curium"],
         ["Bk", "Berkelium"],
         ["Cf", "Californium"],
         ["Es", "Einsteinium"],
         ["Fm", "Fermium"],
         ["Md", "Mendelevium"],
         ["No", "Nobelium"],
         ["Lr", "Lawrencium"],
         ["Rf", "Rutherfordium"],
         ["Db", "Dubnium"],
         ["Sg", "Seaborgium"],
         ["Bh", "Bohrium"],
         ["Hs", "Hassium"],
         ["Mt", "Meitnerium"],
         ["Ds", "Darmstadtium"],
         ["Rg", "Roentgenium"],
         ["Cn", "Copernicium"],
         ["Uut", "Unutrium"],
         ["Fl", "Flerovium"],
         ["Uup", "Ununpentium"],
         ["Lv", "Livermorium"],
         ["Uus", "Ununseptium"],
         ["Uuo", "Ununoctium"],
      ]
   
   def input(self, channel, channelId, message, author):
      if message.count(" ") >= 1:
         if message.split(" ")[1] in ["n", "nb", "number", "numbers", "int", "integer", "integers"]:
            if hasPowers(channelId, author, ["canrandomnumber"]):
               try:
                  start, stop = 1, 100
                  if message.count(" ") >= 2:
                     start = int(message.split(" ")[2])
                     if message.count(" ") >= 3:
                        stop = int(message.split(" ")[3])
                  self.number(channel, start, stop)
               except:
                  BOT.addMsg(channel, "The minimum and maximum must be integers.")
         elif message.split(" ")[1] in ["v", "viewer", "viewers"]:
            if hasPowers(channelId, author, ["canrandomviewer"]):
               noMods = False
               if message.count(" ") >= 2 and message.split(" ")[2] in ["false", "0", "-m"]:
                  noMods = True
               self.viewer(channel, channelId, noMods)
         elif message.split(" ")[1] in ["l", "letter", "letters"]:
            if hasPowers(channelId, author, ["canrandomletter"]):
               try:
                  start, stop = 65, 90
                  if message.count(" ") >= 2:
                     start = ord(message.split(" ")[2].upper())
                     if message.count(" ") >= 3:
                        stop = ord(message.split(" ")[3].upper())
                  self.letter(channel, start, stop)
               except:
                  BOT.addMsg(channel, "The minimum and maximum must be letters.")
         elif message.split(" ")[1] in ["d", "dice", "die"]:
            if hasPowers(channelId, author, ["canrandomdice"]):
               try:
                  nb = 1
                  if message.count(" ") >= 2:
                     nb = int(message.split(" ")[2])
                  self.dice(channel, nb)
               except:
                  BOT.addMsg(channel, "The number of dice must be an integer.")
         elif message.split(" ")[1] in ["t", "text", "texts", "s", "string", "strings", "sentence", "sentences"]:
            if hasPowers(channelId, author, ["canrandomtext"]):
               if message.count(" ") >= 2:
                  list = message.split(" ", 2)[2].replace("; ", ";").split(";")
                  self.text(channel, list)
               else:
                  BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#random")
         elif message.split(" ")[1] in ["e", "element", "elements"]:
            if hasPowers(channelId, author, ["canrandomelement"]):
               try:
                  start, stop = 1, len(self.elements)
                  if message.count(" ") >= 2:
                     start = int(message.split(" ")[2])
                     if message.count(" ") >= 3:
                        stop = int(message.split(" ")[3])
                  self.element(channel, start, stop)
               except:
                  BOT.addMsg(channel, "The minimum and maximum must be positive integers.")
         elif message.split(" ")[1] in ["f", "fruit", "fruits"]:
            if hasPowers(channelId, author, ["canrandomfruit"]):
               self.fruit(channel)
         elif message.split(" ")[1] in ["c", "colour", "colours", "color", "colors"]:
            if hasPowers(channelId, author, ["canrandomcolour"]):
               self.colour(channel)
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#random")
      else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#random")
   
   def number(self, channel, start, stop):
      BOT.addMsg(channel, "Random number between {} and {}: {}".format(start, stop, randNb(min(start, stop), max(start, stop))))
   
   def viewer(self, channel, channelId, noMods=False):
      cur.execute("SELECT name FROM users WHERE channelId = %s AND isViewer = 1{}".format(" AND isMod = 0"*noMods), (channelId,))
      results = cur.fetchall()
      if len(results) > 0:
         BOT.addMsg(channel, "Random viewer{}: {}".format(" (not moderator)"*noMods, randItem(results)[0].capitalize()))
      else:
         BOT.addMsg(channel, "There are no viewers.")
   
   def letter(self, channel, start, stop):
      if 65 <= start <= 90 and 65 <= stop <= 90:
         BOT.addMsg(channel, "Random letter between {} and {}: {}".format(chr(start), chr(stop), chr(randNb(min(start, stop), max(start, stop)))))
      else:
         BOT.addMsg(channel, "The minimum and maximum must be letters.")
   
   def dice(self, channel, nb):
      if 0 < nb <= 16:
         dice = [randNb(1, 6) for i in range(nb)]
         BOT.addMsg(channel, "Rolling {} dice: {}{}".format(nb, " ".join(["[{}]".format(dice[i]) for i in range(nb)]), " Yahtzee!"*(nb == 5 and all([dice[0] == dice[i] for i in range(5)]))))
      else:
         BOT.addMsg(channel, "You can only roll 1 to 16 dice.")
   
   def text(self, channel, list):
      BOT.addMsg(channel, "Random text: {}".format(randItem(list)))
   
   def element(self, channel, start, stop):
      if start > 0:
         if stop <= len(self.elements):
            element = randNb(start, stop)
            BOT.addMsg(channel, "Random element between {} and {}: [{}|{}] {}".format(self.elements[start-1][1], self.elements[stop-1][1], element, self.elements[element-1][0], self.elements[element-1][1]))
         else:
            BOT.addMsg(channel, "There are only {} elements in the periodic table.".format(len(self.elements)))
      else:
         BOT.addMsg(channel, "The minimum must be a positive integer.")
   
   def fruit(self, channel):
      BOT.addMsg(channel, "Random fruit: {}".format(randItem(["Apple", "Banana", "Lemon", "Tomato", "Raspberry", "Strawberry", "Blueberry", "Blackberry", "Cherry", "Kiwi", "Orange", "Fig", "Apricot", "Mango", "Olive", "Peach", "Grape", "Vanilla", "Avocado", "Clementine", "Coconut", "Coffee", "Pineapple", "Pistachio", "Pumpkin"])))
   
   def colour(self, channel):
      BOT.addMsg(channel, "Random colour: {}".format(randItem(["Red", "Green", "Blue", "Yellow", "Cyan", "Magenta", "Brown", "Purple", "Pink", "Grey", "White", "Black", "Orange"])))
RANDOM = random()

class statuses:
   def input(self, channel, channelId, message, author):
      if message.count(" ") == 1:
         if message.split(" ")[1].lower() in ["list"]:
            if hasPowers(channelId, author, ["canliststatuses"]):
               self.list(channel, channelId, None)
      elif message.count(" ") >= 2:
         if message.split(" ")[1].lower() in ["add", "new", "create", "reset", "clear"]:
            if hasPowers(channelId, author, ["canaddstatuses"]):
               self.add(channel, channelId, message.split(" ")[2], author)
         elif message.split(" ")[1].lower() in ["rem", "remove", "del", "delete"]:
            if hasPowers(channelId, author, ["canremovestatuses"]):
               self.remove(channel, channelId, message.split(" ")[2])
         elif message.split(" ")[1].lower() in ["list"]:
            if hasPowers(channelId, author, ["canliststatuses"]):
               self.list(channel, channelId, message.split(" ")[2])
         elif message.count(" ") >= 3:
            if message.split(" ")[1].lower() in ["rename", "name"]:
               if hasPowers(channelId, author, ["canrenamestatuses"]):
                  self.rename(channel, channelId, message.split(" ")[2], message.split(" ")[3])
            elif message.split(" ")[1].lower() in ["give"]:
               if hasPowers(channelId, author, ["cangivestatuses"]):
                  self.give(channel, channelId, message.split(" ")[2], message.split(" ")[3])
            elif message.count(" ") == 4:
               if message.split(" ")[1].lower() in ["set"]:
                  if hasPowers(channelId, author, ["cansetstatuses"]):
                     self.set(channel, channelId, message.split(" ")[2], message.split(" ")[3].lower(), message.split(" ")[4].lower())
               else:
                  BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#statuses")
            else:
               BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#statuses")
         else:
            BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#statuses")
      else:
         BOT.addMsg(channel, "Wrong syntax. http://osberbot.com/documentation#statuses")
   
   def add(self, channel, channelId, name, author):
      if re.match("^[a-zA-Z0-9_]+$", name):
         if len(name) <= 100:
            cur.execute("SELECT id FROM statuses WHERE channelId = %s and name = %s", (channelId, name))
            if len(cur.fetchall()) == 0: # If the status does not exist
               cur.execute("INSERT INTO statuses (channelId, name, author, createdAt, timestamp) VALUES (%s, %s, %s, UTC_TIMESTAMP, UTC_TIMESTAMP)", (channelId, name, author))
               BOT.addMsg(channel, "Status {} has been created.".format(name))
            else:
               BOT.addMsg(channel, "Status {} already exists.".format(name))
         else:
            BOT.addMsg(channel, "The status name must not be longer than 100 characters.")
      else:
         BOT.addMsg(channel, "The status name must be composed of alpha-numeric characters or underscores.")
   
   def remove(self, channel, channelId, name):
      if not name.lower() in ["default", "moderator"]:
         cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, name))
         results = cur.fetchall()
         if len(results) == 1: # If the status exists
            cur.execute("DELETE FROM statuses WHERE id = %s", (results[0][0],))
            BOT.addMsg(channel, "Status {} has been removed.".format(name))
         else:
            BOT.addMsg(channel, "Status {} does not exist.".format(name))
      else:
         BOT.addMsg(channel, "You cannot remove the Default and Moderator statuses.")
   
   def set(self, channel, channelId, name, power, value):
      cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, name))
      results = cur.fetchall()
      if len(results) == 1:
         statusId = results[0][0]
         if power in powersNames:
            if value in ["true", "1", "on"]:
               cur.execute("UPDATE statuses SET {} = 1, timestamp = UTC_TIMESTAMP WHERE id = %s".format(power), (statusId,))
               BOT.addMsg(channel, "Status {} now has power {}.".format(name, power))
            elif value in ["false", "0", "off"]:
               cur.execute("UPDATE statuses SET {} = 0, timestamp = UTC_TIMESTAMP WHERE id = %s".format(power), (statusId,))
               BOT.addMsg(channel, "Status {} no longer has power {}.".format(name, power))
            else:
               BOT.addMsg(channel, "Power value must be either true or false.")
         else:
            BOT.addMsg(channel, "Power {} does not exist.".format(power))
      else:
         BOT.addMsg(channel, "Status {} does not exist.".format(name))
   
   def rename(self, channel, channelId, name, newName):
      if not name.lower() in ["default", "moderator"]:
         cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, name))
         results = cur.fetchall()
         if len(results) == 1: # If the status exists
            statusId = results[0][0]
            cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, newName))
            if len(cur.fetchall()) == 0: # If the new status does not exist
               cur.execute("UPDATE statuses SET name = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (newName, statusId))
               BOT.addMsg(channel, "Status {} has been renamed {}.".format(name, newName))
            else:
               BOT.addMsg(channel, "Status {} already exists.".format(newName))
         else:
            BOT.addMsg(channel, "Status {} does not exist.".format(name))
      else:
         BOT.addMsg(channel, "You cannot rename the Default and Moderator statuses.")
   
   def give(self, channel, channelId, name, status):
      cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, status))
      results = cur.fetchall()
      if len(results) == 1: # If the status exists
         statusId = results[0][0]
         userId = BOT.addUser(channelId, name)
         if status.lower() in ["default", "moderator"]:
            cur.execute("UPDATE users SET hasStatus = 0, statusId = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (statusId, userId))
         else:
            cur.execute("UPDATE users SET hasStatus = 1, statusId = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (statusId, userId))
         BOT.addMsg(channel, "Status {} given to {}.".format(status, name.capitalize()))
      else:
         BOT.addMsg(channel, "Status {} does not exist.".format(status))
   
   def list(self, channel, channelId, status):
      if status == None: # Listing the statuses
         cur.execute("SELECT name FROM statuses WHERE channelId = %s", (channelId,))
         names = [result[0] for result in cur.fetchall()]
         BOT.addMsg(channel, "This channel has {} statuses: {}.".format(len(names), ", ".join(names)))
      else:
         cur.execute("SELECT id FROM statuses WHERE channelId = %s AND name = %s", (channelId, status))
         results = cur.fetchall()
         if len(results) == 1: # If the status exists
            cur.execute("SELECT name FROM users WHERE statusId = %s", (results[0][0],))
            names = [result[0] for result in cur.fetchall()]
            BOT.addMsg(channel, "This channel has {} viewers of status {}: {}.".format(len(names), status, ", ".join(names)))
         else:
            BOT.addMsg(channel, "Status {} does not exist.".format(status))
STATUSES = statuses()

class updates:
   def input(self, channel, channelId):
      cur.execute("SELECT displaynews, nextnews, newsinterval, displaypolls, nextpoll, pollsinterval, displayraffles, nextraffle, rafflesinterval FROM channels WHERE id = %s", (channelId,))
      results = cur.fetchall()
      if results[0][0] and isTime(int(results[0][1])): # News
         cur.execute("UPDATE channels SET nextnews = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (getTime()+int(results[0][2]), channelId))
         NEWS.get(channel, channelId)
      if results[0][3] and isTime(int(results[0][4])): # Polls
         cur.execute("UPDATE channels SET nextpoll = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (getTime()+int(results[0][5]), channelId))
         POLLS.display(channel, channelId)
      if results[0][6] and isTime(int(results[0][7])): # Raffles
         cur.execute("UPDATE channels SET nextraffle = %s, timestamp = UTC_TIMESTAMP WHERE id = %s", (getTime()+int(results[0][8]), channelId))
         RAFFLES.display(channel, channelId)
UPDATES = updates()

class title:
   def input(self, channel, channelId, message, author):
      if message.count(" ") >= 2:
         if message.split(" ")[1].lower() in ["set"]:
            if hasPowers(channelId, author, ["cansettitle"]):
               self.set(channel, channelId, message.split(" ", 2)[2])
         elif message.split(" ")[1].lower() in ["game"]:
            if hasPowers(channelId, author, ["cansetgame"]):
               self.game(channel, channelId, message.split(" ", 2)[2])
   
   def set(self, channel, channelId, title):
      opener = urllib2.build_opener(urllib2.HTTPHandler)
      request = urllib2.Request("https://api.twitch.tv/kraken/channels/{}".format(channel), data="channel[status]={}".format(title.replace(" ", "+")))
      request.add_header("Content-Type", "Accept: application/vnd.twitchtv.v2+json")
      request.get_method = lambda: "PUT"
      url = opener.open(request)
      print url
   
   def game(self, channel, channelId, game):
      opener = urllib2.build_opener(urllib2.HTTPHandler)
      request = urllib2.Request("https://api.twitch.tv/kraken/channels/{}".format(channel), data="channel[game]={}".format(game))
      request.add_header("Content-Type", "Accept: application/vnd.twitchtv.v2+json")
      request.get_method = lambda: "PUT"
      url = opener.open(request)
      print url
TITLE = title()

try:
   BOT.boot()
except Exception as e:
   cur.execute("INSERT INTO crashes (error, traceback, timestamp) VALUES (%s, %s, UTC_TIMESTAMP)", (e, traceback.format_exc()))
   print "OsberBot crashed: {}".format(e)
   database.commit()
   cur.close()
   database.close()