#!/usr/bin/python
#-*- coding: utf-8 -*-

import logging

class Logging(logging.RootLogger):
	def errorExit(self, msg, *args, **kwargs):
		self.error(msg, *args, **kwargs)
		
		exit(1)

Logging = Logging(logging.DEBUG)
hdlr = logging.StreamHandler()
hdlr.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
Logging.addHandler(hdlr)
#Logging = logging