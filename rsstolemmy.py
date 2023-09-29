#!/usr/bin/python3

import argparse
import feedparser
import time
import json
import re
import string
import pyotp
import markdownify
from pythorhead import Lemmy

def get_args():
  parser = argparse.ArgumentParser(description="RSS to Lemmy",
             formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("-c", "--config-file", help="config file", default="./.rsstolemmy_config.json")
  parser.add_argument("-t", "--test", help="test - print output and abort", action="store_true")
  args = parser.parse_args()
  a = vars(args)

  return(a)

def get_config(config_file):
  try:
    with open(config_file) as f:
      config = json.load(f)
  except:
    print("error reading config file")
    return None

  return config

def lemmy_login(userauth):
  lemmy = Lemmy(userauth["instance"])
  ok = lemmy.log_in(userauth["username"], userauth["password"])

  if ok is False:
    if "totp" in userauth:
      print("Retrying with TOTP code")
      totp = pyotp.TOTP(userauth["totp"], digest="SHA256")
      code = totp.now()
    else:
      code = input("Enter TOTP code:")

    ok = lemmy.log_in(userauth["username"], userauth["password"], code)
    if ok is False:
      print("error logging in")
      return None

  return lemmy


#### start ####

a = get_args()
config = get_config(a["config_file"])

if config is None:
  exit(1)


for rss in config:
  descf=f'./{rss}.json'

  update = 0
  nonewposts = 0
  newscount = 0

  try:
    with open(descf) as f:
      desclist = json.load(f)
  except:
    desclist = {}
    if(a["test"] is False):
      newscount = 100

  lemmy = lemmy_login(config[rss])

  news = feedparser.parse(config[rss]["feed"])

  #print(news.entries)

  for item in news.entries:

    #print(item)

    title = item.title
    desc = markdownify.markdownify(item.description)
    link = item.link
    guid = item.link
    
    if "category" in item:
      cat = [t.term for t in item.get('tags', [])]
    else:
      cat = ""

    regex = re.compile('[^a-zA-Z0-9]')
    guid = regex.sub('', guid)

    print(title)
    print(desc)
    print(link)
    #print(guid)
    print('----------------------')

    if guid in list(desclist):
      print(' - already posted')
      nonewposts = 1

      if (desclist[guid]["desc"] != desc) or (desclist[guid]["title"] != title):
        print(' - updating...')
        update = 1
      else:
        update = 0
    else:
      update = 0

    if (update == 0) and (nonewposts == 1):
      print('[no update, not posting new news, nothing to do]')
      continue

    desclist[guid] = {}
    desclist[guid]["desc"] = desc
    desclist[guid]["title"] = title

    match = True

    if "include_filter" in config[rss]:
      match = False
      for filter in config[rss]["include_filter"]:
        if filter in desc:
          print(f'[({filter}) include filter matched]')
          match = True
        else:
          print('[filter not matched]')
      
    if ((match is True) and ("include_cats" in config[rss])):
      match = False
      for filter in config[rss]["include_cats"]:
        if filter in cat:
          print(f'[({filter}) include cat matched]')
          match = True
        else:
          print('[cat filter not matched]') 

    if ((a["test"] is False) and (match is True)):

      comm = config[rss]["community"]

      if update == 0:
        community_id = lemmy.discover_community(comm)
        post = lemmy.post.create(community_id, title, body=desc, url=link)
        desclist[guid]["id"] = post["post_view"]["post"]["id"]

      if update == 1:
        if ("id" in desclist[guid]):
          post = lemmy.post.edit(desclist[guid]["id"], name=title, body=desc)

      with open(descf, 'w') as outfile:
        json.dump(desclist, outfile)

    newscount += 1

    if newscount > 5:
      break


