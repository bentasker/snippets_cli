#!/usr/bin/env python

import urllib2
import urllib
import json
import re
import time
import ssl

import math
import sys, readline, os,stat,requests
import random
import hashlib

from datetime import datetime, timedelta



BASEDIR="http://scratch.holly.home/sniptest/snippets_bentasker_co_uk/output" # No trailing slash
AUTH=False
ADDITIONAL_HEADERS=False
DISKCACHE='/tmp/sbtcli.cache'
CACHE_TTL=900 # 15 mins


# I use this settings file to gain access to the non-public copy of my projects
if os.path.isfile(os.path.expanduser("~/.sbtcli.settings")):
    with open(os.path.expanduser("~/.sbtcli.settings"),'r') as f:
        for x in f:
            x = x.rstrip()
            if not x:
                continue
            
            # The lines are keyvalue pairs
            cfgline = x.split("=")
            if cfgline[0] == "BASEDIR":
                BASEDIR=cfgline[1]

            if cfgline[0] == "CACHE_TTL":
                CACHE_TTL=int(cfgline[1])

            if cfgline[0] == "DISKCACHE":
                DISKCACHE=cfgline[1]
                
            if cfgline[0] == "ADD_HEADER":
                if not ADDITIONAL_HEADERS:
                    ADDITIONAL_HEADERS = []
                    
                h = {
                        'name' : cfgline[1],
                        'value' : '='.join(cfgline[2:]),
                    }
                ADDITIONAL_HEADERS.append(h)


SNIPPET_URLS = {}


class MemCache(dict):
    ''' A rudimentary in-memory cache with several storage areas and classes.
    By default, the permstorage area will get flushed once an hour
    
    Filched and amended from my RequestRouter project
    
    '''
    
    def __init__(self):
        self.storage = {}
        self.lastpurge = int(time.time())
        self.disabled = False
        self.config = {}
        self.config['doSelfPurge'] = False # Disabled as entries have their own TTL
        self.config['defaultTTL'] = 900 # 15 mins
        self.config['amOffline'] = False # Disable Offline mode by default
        self.config['LRUTarget'] = 0.25 # Percentage reduction target for LRUs
        
        # Seed hashes to try and avoid deliberate hash collisions
        self.seed = random.getrandbits(32)


    def setItem(self,key,val,ttl=False):
        ''' Store an item in a specific area
        '''
        
        if self.disabled:
            return  
        
        if not ttl:
            # Use the default TTL
            ttl = self.config['defaultTTL']
        
        keyh = self.genKeyHash(key)
        now = int(time.time())
        self.storage[keyh] = { "Value": val, "SetAt": now, "TTL" : ttl, "Origkey" : key, "Last-Use": now}


    def getItem(self, key):
        ''' Retrieve an item. Will check each storage area for an entry with the specified key
        '''
        
        if self.disabled:
            return  False        
        
        keyh = self.genKeyHash(key)
        
        if keyh not in self.storage:
            return False
        
        # Check whether the ttl has expired
        if (int(time.time()) - self.storage[keyh]["TTL"]) > self.storage[keyh]["SetAt"]:
            # TTL has expired. Invalidate the object and return false
            # only if we're not currently offline though.
            if not self.config['amOffline']:
                self.invalidate(key)
                return False
        
        self.storage[keyh]["Last-Use"] = int(time.time())
        return self.storage[keyh]["Value"]


    def invalidate(self,key):
        ''' Invalidate an item within the cache
        '''
        key = self.genKeyHash(key)
        
        if key not in self.storage:
            return
        
        del self.storage[key]
    
    
    def genKeyHash(self,key):
        ''' Convert the supplied key into a hash
        
            We combine it with a seed to help make hash collision attempts harder on public facing infrastructure.
            Probably overkill, but better to have it and not need it
            
        '''
        return hashlib.sha256("%s%s" % (self.seed,key)).hexdigest()
    
    
    def __getitem__(self,val):
        ''' Magic method so that the temporary store can be accessed as if this class were a dict
        '''
        return self.getItem(val)
    
    def __setitem__(self,key,val):
        ''' Magic method so that the temporary store can be accessed as if this class were a dict
        '''
        return self.setItem(key,val)
    
            
    def flush(self):
        ''' Flush the temporary storage area and response cache
        
        Restore anything that's been 'pre' cached
        '''
        del self.storage
        self.storage = {}
        
        # Generate a new seed so it's harder to predict hashes
        self.seed = random.getrandbits(32)
        self.lastpurge = int(time.time())
        
        # Write the updated (and now empty) cache to disk so we don't end up reusing later
        self.writeToDiskCache()

        
    def selfpurge(self):
        ''' Sledgehammer for a nail. Periodically purge the permanent storage to make
        sure we don't absorb too much memory
        '''
        
        if 'doSelfPurge' in self.config and not self.config['doSelfPurge']:
            return
        
        if (int(time.time()) - self.config['defaultTTL']) > self.lastpurge:
            self.flush()


    def LRU(self):
        ''' Run a Least Recently Used flush on the cache storage
        '''
        
        items = {}
        
        # Iterate over items in the cache, pulling out the cache key and when the item was last used
        for keyh in self.storage:
            items[keyh] = self.storage[keyh]['Last-Use']
            
        # Now we want to sort our dict from smallest timestamp (i.e. least recently used) to highest
        ordered = sorted(items.items(), key=lambda x: x[1])

        # That gives us a list of tuples (key,timestamp). We want to clear the first 25% (ish)
        numitems = len(items)
        toclear = math.ceil(numitems * self.config['LRUTarget'])
        x = 0
        
        while x < toclear:
            entry = ordered[x][0]
            del self.storage[entry]           
            x = x + 1

        return x



    def writeToDiskCache(self):
        ''' Write a copy of the current cache out to disk
        '''
        
        if "DiskCache" in self.config and self.config['DiskCache']:
            p = {
                    'storage' : self.storage,
                    'lastpurge' : self.lastpurge,
                    'seed' : self.seed
                }
            
            cachejson = json.dumps(p)
            f = open(self.config['DiskCache'],'w')
            f.write(cachejson)
            f.close()

            
    def loadFromDiskCache(self):
        ''' Load previously cached values from disk (if present)
        '''
        
        if "DiskCache" in self.config and self.config['DiskCache'] and os.path.isfile(self.config['DiskCache']):
            f = open(self.config['DiskCache'],'r')
            cache = json.load(f)
            f.close()
            self.storage = cache['storage']
            self.lastpurge = cache['lastpurge']
            self.seed = cache['seed']
            


    def setConfig(self,var,value):
        ''' Set an internal config option
        '''
        self.config[var] = value





def getJSON(url):
    #print "Fetching %s" % (url,)
    
    # Check whether we have it in cache
    resp = CACHE.getItem(url)
    if resp:
        return json.loads(resp)
    
    
    if CACHE.config['amOffline']:
        print "Item not in cache and we're offline"
        return False
    
    request = urllib2.Request(url)
    
    if ADDITIONAL_HEADERS:
        for header in ADDITIONAL_HEADERS:
            request.add_header(header['name'],header['value'])
    
    response = urllib2.urlopen(request)
    jsonstr = response.read()
    #print jsonstr
    
    CACHE.setItem(url,jsonstr)
    
    return json.loads(jsonstr)



def doTestRequest():
    ''' Place a test request to work out whether we've got connectivity or not 
    '''
    url = "%s/sitemap.json" % (BASEDIR,)
    
    request = urllib2.Request(url)

    
    if ADDITIONAL_HEADERS:
        for header in ADDITIONAL_HEADERS:
            request.add_header(header['name'],header['value'])
    
    try:
        response = urllib2.urlopen(request,timeout=5)
        jsonstr = response.read()
        
        # Check we actually got json back
        # Basically checking for captive portals. Though shouldn't be an issue given we're using HTTPS
        # but also helps if there's an issue with the server

        s = json.loads(jsonstr)
        
        # If we got it, update the cache
        CACHE.setItem(url,jsonstr)
        
        return True
    
    except:
        return False





# See https://snippets.bentasker.co.uk/page-1705192300-Make-ASCII-Table-Python.html
def make_table(columns, data):
    """Create an ASCII table and return it as a string.

    Pass a list of strings to use as columns in the table and a list of
    dicts. The strings in 'columns' will be used as the keys to the dicts in
    'data.'

    """
    # Calculate how wide each cell needs to be
    cell_widths = {}
    for c in columns:
        lens = []
        values = [lens.append(len(str(d.get(c, "")))) for d in data]
        lens.append(len(c))
        lens.sort()
        cell_widths[c] = max(lens)

    # Used for formatting rows of data
    row_template = "|" + " {} |" * len(columns)

    # CONSTRUCT THE TABLE

    # The top row with the column titles
    justified_column_heads = [c.ljust(cell_widths[c]) for c in columns]
    header = row_template.format(*justified_column_heads)
    # The second row contains separators
    sep = "|" + "-" * (len(header) - 2) + "|"
    end = "-" * len(header)
    # Rows of data
    rows = []

    for d in data:
        fields = [str(d.get(c, "")).ljust(cell_widths[c]) for c in columns]
        row = row_template.format(*fields)
        rows.append(row)
    rows.append(end)
    return "\n".join([header, sep] + rows)


def stripTags(str):
    ''' Strip out HTML tags and return just the plain text
    '''
    return re.sub('<[^<]+?>', '', str)


def secondsToTime(s):
    ''' Convert a count in seconds to hours and minutes
    '''
    
    if not s:
        return "0h 0m"
    
    mins, secs = divmod(int(s),60)
    hours, mins = divmod(mins,60)
    
    return "%dh %02dm" % (hours,mins)


def formatDate(s):
    
    s = int(s)
    if s == 0:
        return ''
    
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(s))


def printSnippet(sid):
    ''' Print a Snippet
    '''
    
    urlpath = getSnippetUrlFromId(sid)
    
    if not urlpath:
        print "NOT FOUND"
        return False
    
    url = "%s/%s" % (BASEDIR,urlpath)
    snip = getJSON(url)
    
    if not snip or not snip['name']:
        print "Snippet Not Found"
        return
    
    prev = CACHE.getItem('Navi-now')
    CACHE.setItem('Navi-last',prev)
    CACHE.setItem('Navi-now',sid)

    print "%s: %s (%s)\n" % (sid,snip['name'],snip['lang'])
    
    print "-------------\nDetails\n-------------\n"
    
    print "Language: %s" % (snip['lang'],)
    
    if "license" in snip and len(snip['license']) > 0:
            print "License: %s" % (snip['license'],)
    
    
    print "\n-------------\nDescription\n-------------\n\n%s\n" % (snip['description'])


    if "requires" in snip and len(snip['requires']) > 0:
            print "-------------\nRequires\n-------------\n%s\n" % (snip['requires'],)
    


    if "basedon" in snip and len(snip['basedon']) > 0:
            print "Based On\n-------------\n\n%s\n" % (snip['basedon'],)
    

    if "similar" in snip and len(snip['similar']) > 0:
            print "Similar To\n-------------\n\n%s\n" % (snip['similar'],)


    print "\n-------------\nSnippet\n-------------\n\n%s" % (snip['snippet'])
    
    if "usage" in snip and len(snip['usage']) > 0:
            print "-------------\nUsage Example\n-------------\n\n%s" % (snip['usage'],)
    
    print ''





def getSnippetUrlFromId(sid):
    
    dictkey = 'snip-%s' % (sid,)
    if dictkey not in SNIPPET_URLS:
        url = "%s/sitemap.json" % (BASEDIR, )
        plist = getJSON(url)
        buildSnippetIDMappings(plist['entries'])

    if dictkey not in SNIPPET_URLS:
        # Obviously an invalid snippet
        return False
    
    # Otherwise return the stored path
    return SNIPPET_URLS[dictkey]
    

def buildSnippetIDMappings(snippets):
    ''' Populate a dict mapping URLs to IDs
    '''
    
    for sn in snippets:
        dictkey = 'snip-%s' % (sn['id'],)
        if dictkey not in SNIPPET_URLS:
            SNIPPET_URLS[dictkey] = sn['href']
            
    
    
    
def printSnippetList():
    ''' Grab a copy of the sitemap and print the entries in a table
    '''
    url = "%s/sitemap.json" % (BASEDIR, )
    plist = getJSON(url)


    if not plist:
        print "No Results"
        return
    
    # This is not the most efficient way to do it, but it'll do for now
    # update the dict mapping IDs to URLs
    buildSnippetIDMappings(plist['entries'])
    
    # Now output the table
    print buildIssueTable(plist['entries'])
    


def doSnippetSearch(title=False,lang=False,similar=False,searchstring=False):
    ''' Run a search against the sitemap
    '''
    
    url = "%s/sitemap.json" % (BASEDIR, )
    plist = getJSON(url)


    if not plist:
        print "No Results"
        return

    buildSnippetIDMappings(plist['entries'])    

    # Iterate over the entries checking for the search string
    matches = []
    
    if lang:
        lang = lang.lower()
 
 
    if searchstring:
        searchstring = searchstring.lower()
 
    for snip in plist['entries']:
        # Title search
        if title and title.lower() in snip['name'].lower():
            if not lang or lang == snip['primarylanguage'].lower():
                matches.append(snip)
                continue

        # Search for phrases in "similar"
        if similar and similar.lower() in snip['similar'].lower():
            if not lang or lang == snip['primarylanguage'].lower():
                matches.append(snip)
                continue


        if searchstring and (searchstring in snip['name'].lower() or
                             searchstring in snip['keywords'].lower() or
                             searchstring in snip['primarylanguage'].lower()):
            
            if not lang or lang == snip['primarylanguage'].lower():
                matches.append(snip)
                continue            

            
        # Language only search
        if lang and lang == snip['primarylanguage'].lower():
            matches.append(snip)
            continue

    print "Search results - String: %s, title: %s, lang: %s, similarto: %s" % (searchstring,title,lang,similar)
        
    print buildIssueTable(matches)


    
def buildIssueTable(issues):
    ''' Print a list of changes in tabular form
    '''
    
    Cols = ['Snippet ID','Title','Language']
    Rows = []
    
    for chg in issues:
        p = {
                'Snippet ID' : chg['id'],
                'Title': chg['name'],
                'Language' : chg['primarylanguage']
            }
        Rows.append(p)
        
    return make_table(Cols,Rows)
        


# CLI related functions begin
def runInteractive(display_prompt,echo_cmd=False):
    
        # Trigger the periodic auto flushes
        CACHE.selfpurge()
        
	try:
	    readline.read_history_file(os.path.expanduser("~/.sbtcli.history"))
	except: 
	    pass # Ignore FileNotFoundError, history file doesn't exist

	while True:
	    try:
		command = raw_input(display_prompt)

	    except EOFError:
		print("")
		break

	    if command == "q":
		break

	    elif command.startswith("#") or command == "" or command == " ":
		continue

	    if echo_cmd:
		print "> " + command

	    readline.write_history_file(os.path.expanduser("~/.sbtcli.history"))
	    processCommand(command)


def processCommand(cmd):
    ''' Process the command syntax to work out which functions need to be called
    '''
    
    if re.match('[0-9]+',cmd):
        return printSnippet(cmd)
        

    # We now need to build the command, but take into account that strings may be wrapped in quotes
    # these shoudld be treated as a single argument 

    # Split the command out to a list
    origcmdlist = cmd.split(' ')
    cmdlist = []
    NEEDQUOTE=False
    ENDSWITHQUOTE=False
    txtbuffer=''
    
    for entry in origcmdlist:
        if entry[0] == '"' or entry[0] == "'":
            # Starts with a quote.
            NEEDQUOTE=True
        
        if entry[-1] == '"' or entry[-1] == "'":
            ENDSWITHQUOTE=True
        
        if NEEDQUOTE and not ENDSWITHQUOTE:
            # Need a quote, just append it to the buffer for now
            txtbuffer += entry.replace("'","").replace('"',"")
            
            # Reinstate the original space
            txtbuffer += " "
    
        # Does it end with a quote?
        if ENDSWITHQUOTE:
            # It does. Append to the buffer (known bug here!)
            txtbuffer += entry.replace("'","").replace('"',"")
            NEEDQUOTE=False
            entry = txtbuffer
            txtbuffer = ''
            
        if not NEEDQUOTE:
            # Append the command segment
            cmdlist.append(entry.rstrip())


    if cmdlist[0] == 'p' or cmdlist[0] == 'back':
        # Navigation command to go back to the last issue viewed
        lastview = CACHE.getItem('Navi-last')
        if not lastview:
            print "You don't seem to have viewed a snippet previously"
            return
        return printSnippet(lastview)

    if cmdlist[0] == "snippet":
        return printSnippet(cmdlist[1])

    if cmdlist[0] == "cache":
        return parseCacheOptions(cmdlist)
    
    if cmdlist[0] == "list":
        # TODO - change this to be snippets related
        return printSnippetList()
    
    if cmdlist[0] == "lang":
        # TODO - change this to be snippets related
        return doSnippetSearch(lang=cmdlist[1])
    
    
    if cmdlist[0] == "set":
        return parseSetCmd(cmdlist)
    
    if cmdlist[0] == "search":
        return parseSearchCmd(cmdlist)    
    


def parseSearchCmd(cmdlist):
    ''' Handle search commands
    '''
    
    
    if len(cmdlist) >= 3 and cmdlist[1] == "similarto":
        return doSnippetSearch(similar=cmdlist[2])
    
    if len(cmdlist) >= 4 and cmdlist[2] == "lang":
        return doSnippetSearch(title=cmdlist[1],lang=cmdlist[3])

    if len(cmdlist) >= 3 and cmdlist[2] == "title":
        return doSnippetSearch(title=cmdlist[1])

    
    return doSnippetSearch(searchstring=cmdlist[1])




def parseSetCmd(cmdlist):
    ''' Used to set various internals
    '''


    if cmdlist[1] == "defaultttl":
        CACHE.config['defaultTTL'] = int(cmdlist[2])
        print "Default TTL set to %s" % (cmdlist[2])

    if cmdlist[1] == "lrutarget":
        CACHE.config['LRUTarget'] = cmdlist[2]
        print "LRU Target set to %s%" % (cmdlist[2])
        
    if cmdlist[1] == "Offline":
        CACHE.config['amOffline'] = True
        print "Offline mode enabled"
        
    if cmdlist[1] == "Online":
        CACHE.config['amOffline'] = False
        print "Offline mode disabled"
        

def parseCacheOptions(cmdlist):
    ''' Utility functions to aid troubleshooting if the cache causes any headaches
    '''
    
    if cmdlist[1] == "dump":
        # Dump the contents of the cache
        Cols = ['Key','Expires','Value']
        Rows = []
        
        for entry in CACHE.storage:
            p = {
                'Key' : CACHE.storage[entry]['Origkey'],
                'Expires' : time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(CACHE.storage[entry]['SetAt'] + CACHE.storage[entry]['TTL'])),
                'Value' : CACHE.storage[entry]['Value'],
                }
            Rows.append(p)
        print make_table(Cols,Rows)


    if cmdlist[1] == "fetch":
        if re.match('[A-Z]+-[0-9]+',cmdlist[2]):
            url = "%s/browse/%s.json" % (BASEDIR,cmdlist[2])
            getJSON(url)
            print "Written to cache"
            return
            
        # Fetch the specified URL 
        getJSON(cmdlist[2])
        print "Written to cache"
        return

    if cmdlist[1] == "LRU":
        count = CACHE.LRU()
        print "LRU Triggered. %s items removed" % (count,)


    if cmdlist[1] == "flush":
        # Flush the cache
        CACHE.flush()
        print "Cache flushed"

    if cmdlist[1] == "get":
        f = CACHE.getItem(cmdlist[2])
        if not f:
            print "Not in Cache"
            return
        
        print f


    if cmdlist[1] == "invalidate":
        CACHE.invalidate(cmdlist[2])
        print "Invalidated"


        
    if cmdlist[1] == "print":
        # Print a list of keys and when they expire
        Cols = ['Key','Expires']
        Rows = []
        
        for entry in CACHE.storage:
            p = {
                'Key' : CACHE.storage[entry]['Origkey'],
                'Expires' : time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(CACHE.storage[entry]['SetAt'] + CACHE.storage[entry]['TTL']))
                }
            Rows.append(p)
        print make_table(Cols,Rows)


    
    

CACHE = MemCache()
if DISKCACHE:
    CACHE.setConfig('DiskCache',DISKCACHE)
    CACHE.loadFromDiskCache()

if CACHE_TTL:
    CACHE.setConfig('defaultTTL',CACHE_TTL)


if not doTestRequest():
    print "Enabling Offline mode"
    CACHE.setConfig('amOffline',True)

if __name__ == "__main__":
    if len(sys.argv) < 2:
            # Launch interactive mode
            
            # If commands are being redirected/piped, we don't want to display the prompt after each
            mode = os.fstat(sys.stdin.fileno()).st_mode
            if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
                    display_prompt = ""
                    echo_cmd = True
            else:
                    display_prompt = "sbtcli> "
                    echo_cmd = False

            runInteractive(display_prompt,echo_cmd)

            # Save the most recent view history
            lastview = CACHE.getItem('Navi-now')
            CACHE.setItem('Navi-last',lastview, ttl=99999999)
            CACHE.writeToDiskCache()
            sys.exit()


    # Otherwise, pull the command from the commandline arguments

    # Process them first to handle quoted strings
    for i,val in enumerate(sys.argv):
        if " " in val:
            sys.argv[i] = "'%s'" % (val,)
        
        
    command=" ".join(sys.argv[1:])
    processCommand(command)
    CACHE.writeToDiskCache()




