#!/usr/bin/env python3

import json
import re
import time
import ssl

import math
import sys, readline, os,stat
import random
import requests
import hashlib

from datetime import datetime, timedelta



BASEDIR="https://snippets.bentasker.co.uk" # No trailing slash
AUTH=False
ADDITIONAL_HEADERS=False
UPDATE_ANALYTICS=True


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
                
            if cfgline[0] == "ADD_HEADER":
                if not ADDITIONAL_HEADERS:
                    ADDITIONAL_HEADERS = []
                    
                h = {
                        'name' : cfgline[1],
                        'value' : '='.join(cfgline[2:]),
                    }
                ADDITIONAL_HEADERS.append(h)


SNIPPET_URLS = {}


def updateAnalytics(pgview):
    ''' Send a ping to Piwik
    
    This helps me track which snippets people actually find useful.
    
    A flag to disable this will be provided later
    '''

    if not UPDATE_ANALYTICS:
        return False

    url = 'https://piwik.bentasker.co.uk/piwik.php'

    headers = {
        "User-agent": "sbt_cli",
        "Referer": pgview
        }
    
    params = {
        "idsite":"1",
        "rec":"1",
        "url": pgview
        }
    
    response = requests.get(url,headers=headers,params=params)



def getJSON(url,ttl=False):
    #print "Fetching %s" % (url,)
        
    headers = {}
    if ADDITIONAL_HEADERS:
        for header in ADDITIONAL_HEADERS:
            headers[header['name']] = header['value']
    
    response = requests.get(url,headers=headers)
    
    return response.json()



def doTestRequest():
    ''' Place a test request to work out whether we've got connectivity or not 
    '''
    url = "%s/sitemap.json" % (BASEDIR,)

    headers = {}
    if ADDITIONAL_HEADERS:
        for header in ADDITIONAL_HEADERS:
            headers[header['name']] = header['value']    
            
    try:
        response = requests.get(url,headers=headers)
        jsonstr = response.text
        
        # Check we actually got json back
        # Basically checking for captive portals. Though shouldn't be an issue given we're using HTTPS
        # but also helps if there's an issue with the server
        s = response.json()        
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


def printSnippet(sid):
    ''' Print a Snippet
    '''
    
    urlpath = getSnippetUrlFromId(sid)
    
    if not urlpath:
        print("NOT FOUND")
        return False
    
    url = "%s%s" % (BASEDIR,urlpath)
    
    # Snippets rarely, if ever, change so we can use a long ttl (30 days)
    snip = getJSON(url,ttl=2592000)
    
    if not snip or not snip['name']:
        print("Snippet Not Found")
        return
    
    print("%s: %s (%s)\n" % (sid,snip['name'],snip['lang']))
    
    print("-------------\nDetails\n-------------\n")
    
    print("Language: %s" % (snip['lang'],))
    
    if "license" in snip and len(snip['license']) > 0:
            print("License: %s" % (snip['license'],))
    
    
    print("\n-------------\nDescription\n-------------\n\n%s\n" % (snip['description']))


    if "requires" in snip and len(snip['requires']) > 0:
            print("-------------\nRequires\n-------------\n%s\n" % (snip['requires'],))
    


    if "basedon" in snip and len(snip['basedon']) > 0:
            print("Based On\n-------------\n\n%s\n" % (snip['basedon'],))
    

    if "similar" in snip and len(snip['similar']) > 0:
            print("Similar To\n-------------\n\n%s\n" % (snip['similar'],))


    print("\n-------------\nSnippet\n-------------\n\n%s" % (snip['snippet']))
    
    if "usage" in snip and len(snip['usage']) > 0:
            print("-------------\nUsage Example\n-------------\n\n%s" % (snip['usage'],))
    
    
    print("HTML Link\n----------")
    pageurl = "{}{}".format(BASEDIR,urlpath.replace("/json","").replace(".json",".html"))
    print(pageurl)
    
    print('')
    updateAnalytics(pageurl)
    



def getSnippetUrlFromId(sid):
    ''' Take a snippet ID and find out what the url path is
    '''
    
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
        print("No Results")
        return
    
    # This is not the most efficient way to do it, but it'll do for now
    # update the dict mapping IDs to URLs
    buildSnippetIDMappings(plist['entries'])
    
    # Now output the table
    print(buildIssueTable(plist['entries']))
    updateAnalytics(BASEDIR.replace("/json",""))
    


def doSnippetSearch(title=False,lang=False,similar=False,searchstring=False):
    ''' Run a search against the sitemap
    '''
    
    url = "%s/sitemap.json" % (BASEDIR, )
    plist = getJSON(url)


    if not plist:
        print("No Results")
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

    if len(matches) == 1:
        return printSnippet(matches[0]['id'])

    print("Search results - String: %s, title: %s, lang: %s, similarto: %s" % (searchstring,title,lang,similar))
        
    print(buildIssueTable(matches))

    search_page = "{}/search.html#srchtrm={}&_=_&srchfields=TSKD&searchLang=ANY".format(BASEDIR.replace("/json",""),searchstring)
    updateAnalytics(search_page)


    
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
               print("> " + command)

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


    if cmdlist[0] == "snippet":
        return printSnippet(cmdlist[1])
    
    if cmdlist[0] == "list":
        # TODO - change this to be snippets related
        return printSnippetList()
    
    if cmdlist[0] == "lang":
        # TODO - change this to be snippets related
        return doSnippetSearch(lang=cmdlist[1])
    
    if cmdlist[0] == "search":
        return parseSearchCmd(cmdlist)    

    # If none of the above matched, reformat the command and treat it as a search
    c = ["search", ' '.join(cmdlist[0:])]
    return parseSearchCmd(c)


def parseSearchCmd(cmdlist):
    ''' Handle search commands
    '''
    
    
    if len(cmdlist) >= 3 and cmdlist[2] == "similarto":
        return doSnippetSearch(similar=cmdlist[1])
    
    if len(cmdlist) >= 4 and cmdlist[2] == "lang":
        return doSnippetSearch(title=cmdlist[1],lang=cmdlist[3])

    if len(cmdlist) >= 3 and cmdlist[2] == "title":
        return doSnippetSearch(title=cmdlist[1])

    
    return doSnippetSearch(searchstring=cmdlist[1])


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
            sys.exit()


    # Otherwise, pull the command from the commandline arguments

    # Process them first to handle quoted strings
    for i,val in enumerate(sys.argv):
        if " " in val:
            sys.argv[i] = "'%s'" % (val,)
        
        
    command=" ".join(sys.argv[1:])
    processCommand(command)





