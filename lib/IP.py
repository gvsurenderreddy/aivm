#!/usr/bin/python
#-*- coding: utf-8 -*-

import random
from IPy import IP as ip

class DHCP:
	def __hash__(self):
		return hash(random.random())
	
	def __eq__(self, other):
		return hash(self) == hash(other)
	
	def __str__(self):
		return "<DHCP>"


class _IP:
	def __init__(self, address, netmask, gateway):
		self.address = ip(address)
		self.gateway = ip(gateway)
	
	def __hash__(self):
		return hash(self.getAddress()) + hash(self.getLongNetmask()) + hash(self.getGateway())
	
	def __eq__(self, other):
		return hash(self) == hash(other)
	
	def __str__(self):
		return "<address: %s/%s, gateway: %s>" % (self.getAddress(), self.getShortNetmask(), self.getGateway())
	
	def getAddress(self):
		return str(self.address)
	
	def getLongNetmask(self):
		return str(self.netmask.netmask())
	
	def getShortNetmask(self):
		return str(self.netmask.prefixlen())
	
	def getGateway(self):
		return str(self.gateway)


class IPv4(_IP):
	def __init__(self, address, netmask, gateway):
		_IP.__init__(self, address, netmask, gateway)
		
		if netmask[0] != "/":
			netmask = "/%s" % netmask
		
		self.netmask = ip("0%s" % netmask)


class IPv6(_IP):
	def __init__(self, address, netmask, gateway):
		_IP.__init__(self, address, netmask, gateway)
		
		if netmask[0] != "/":
			netmask = "/%s" % netmask
		
		self.netmask = ip("::%s" % netmask)
