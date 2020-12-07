# SBTCLI


## About

A python based commandline utility to fetch the json representations from Snippet entries at [https://snippets.bentasker.co.uk](https://snippets.bentasker.co.uk) and display them as plain text.

Basically a tool for my own convenience, allows me to grab and search snippets without leaving the comfort of my terminal.

It's currently *very* rough and ready.


### Features

* Pipe support
* Offline reading mode
* Shortcuts for the lazy
* Search mechanism



### Analytics

By default, the script will make a call to my Analytics system - this allows me to see things that people are either finding useful or are searching for so that I can improve the snippets collection. In order to disable this analytics call, just set

    UPDATE_ANALYTICS=False
    
toward the top of `sbt_cli.py`


## Usage


Commands can be parsed in one of three ways

* Piped (e.g. `echo 4 | ./sbt_cli.py`)
* Interactivey (`./sbt_cli.py`)
* As arguments (`./sbt_cli.py 4`)

Where something intended as single argument contains a space, it should be quoted:

    ./sbt_cli.py search 'RTMP Server'

  
### General

    [Num] - Jump to the specified Snippet ID (e.g. 4)
    [Search phrase] - Search snippets for phrase
    list - List all snippets in the system
    help - Display this output


### Snippet View

    [Snippet ID] - Display the specified snippet
    snippet [Num] - Display the specified snippet


### Search

If only a single snippet matches the given search, it will be printed directly


    search [search phrase] - Search globally for any snippet with the phrase in title, keywords or similar to
    search [search phrase] title - Search globally for any snippet with the phrase in title
    search [search phrase] lang [language] - Filter search results to only include specified language
    search [search phrase] similarto - Search for snippets that contain [string] in the list of things they're similar to
    lang [language] - Output all snippets marked as being written for [language]



## TODO

* Trigger pager for particularly long output
    
    
## Copyright


SBTCli is Copyright (C) 2017 B Tasker. All Rights Reserved.
Released under the GNU GPL V2 License, see LICENSE.
