# SBTCLI


## About

A python based commandline utility to fetch the json representations from Snippet entries at [https://snippets.bentasker.co.uk](https://snippets.bentasker.co.uk) and display them as plain text.

Basically a tool for my own convenience, allows me to grab and search snippets without leaving the comfort of my terminal.

It's currently *very* rough and ready.


### Caching

By default, pages are cached for a short time (at time of writing, 15 minutes) to avoid repeated requests to the server if a resource is continually being reviewed (or in the case of project pages, potentially re-used).

The CLI will allow you to interact with the cache to a small extent, and the cache is maintained between sessions by writing to an on-disk cache file. During execution the cache runs entirely in memory.

There's also an offline mode, which is initially toggled based upon a test request to the configured server. If the script believes that we're offline, then items in cache will not be invalidated, and attempts will not be made to fetch content from the server where an item isn't in cache. Offline mode can be manually turned on/off via the CLI (see below). It's a simplistic implementation but means I can review things without having connectivity.




### Features

* Caching to reduce number of upstream connections
* Pipe support
* CLI maintains history
* Offline reading mode
* Shortcuts for the lazy
* Search mechanism



## Usage


Commands can be parsed in one of three ways

* Piped (e.g. `echo 4 | ./sbt_cli.py`)
* Interactivey (`./sbt_cli.py`)
* As arguments (`./sbt_cli.py 4`)

Where something intended as single argument contains a space, it should be quoted:

    ./sbt_cli.py search 'RTMP Server'


### Navigation

The upstream JSON files define whether there's a 'next' or 'previous' issue, where those are available, you can switch to them by using the following keystrokes

    [p|back] - move to the previous issue you viewed
    

### General

    [Num] - Jump to the specified Snippet ID (e.g. 4)
    list - List all snippets in the system


### Snippet View

    [Snippet ID] - Display the specified snippet
    snippet [Num] - Display the specified snippet


### Search

    search [search phrase] - Search globally for any snippet with the phrase in title, keywords or similar to
    search [search phrase] title - Search globally for any snippet with the phrase in title
    search [search phrase] lang [language] - Filter search results to only include specified language
    search similarto [string] - Search for snippets that contain [string] in the list of things they're similar to
    lang [language] - Output all snippets marked as being written for [language]
    
    
### Cache Interaction

    cache dump - Dumps out keys, values and expiry times from the cache (generates a *lot* of output)
    cache fetch [issuekey|url] - Fetch the specified Issue/URL and write into cache
    cache flush - Flush all values out of the cache (will also update the ondisk cache)
    cache get [key] - Fetch the value of a specific item from the cache
    cache invalidate [key] - Invalidate a specific item from the cache
    cache LRU   - Run a least recently used cache clearance
    cache print - Print keys and expiry times (but not values) from the cache

### Set commands

    set defaultttl [seconds] - Set the default cache ttl to number of seconds
    set lrutarget [decimal] - The target percentage reduction if/when running a LRU
    set Offline - Tell the cache we're offline
    set Online - Tell the cache we're online



## TODO

* Add ability to cache entire archive
* Trigger pager for particularly long output
    
    
## Copyright


SBTCli is Copyright (C) 2017 B Tasker. All Rights Reserved.
Released under the GNU GPL V2 License, see LICENSE.
