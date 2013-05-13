#!/usr/bin/python
#-*- coding: utf-8 -*-

import ConfigParser

DEFAULT_CONFIG = "./etc/default.conf"

DC = ConfigParser.ConfigParser()
DC.read(DEFAULT_CONFIG)