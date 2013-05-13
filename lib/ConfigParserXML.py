#!/usr/bin/python
#-*- coding: utf-8 -*-

import os
import sys
import xml.dom.minidom as xml
import urllib2

import IP
import Location

from Guest import Guest, Storage
from Logging import Logging


class ConfigParser:
	def __init__(self, filePath):
		if not os.path.exists(filePath):
			raise IOError("File not found.")
		
		self.path = filePath
		self.document = None
	
	def parse(self):
		configFile = file(self.path, "r")
		self.document = xml.parse(configFile)
		
		return self.parseGuests()
	
	def parseGuests(self):
		guests = self.document.getElementsByTagName("guest")
		
		return map(self.parseGuest, guests)
	
	def parseGuest(self, guest):
		hostname = self.parseTextElement(guest, "hostname")
		memorySize = self.parseTextElement(guest, "memory-size")
		vcpuCount = self.parseTextElement(guest, "vcpu-count")
		ksFile = self.parseTextElement(guest, "ks-file")
		networkSettingsFile = self.parseTextElement(guest, "network-settings-file")
		
		storageFile = self.parseStorageFile(guest)
		imageFile = self.parseImageFile(guest)
		
		ipv4 = self.parseIP(guest, "ipv4", IP.IPv4)
		ipv6 = self.parseIP(guest, "ipv6", IP.IPv6)
		
		return Guest(hostname, memorySize, vcpuCount,
						imageFile, ksFile, networkSettingsFile,
						storageFile, ipv4, ipv6)
	
	def parseTextElement(self, parent, elementName):
		tag = parent.getElementsByTagName(elementName)
		
		if tag:
			tagString = self.parseElementData(tag[0])
			return tagString if tagString != "None" else None
		
		return None
	
	def parseElementData(self, element):
		textNodes = filter(lambda x: x.nodeType == x.TEXT_NODE, element.childNodes)
		data = map(lambda x: x.data.strip(), textNodes)
		
		return "".join(data)
	
	def parseStorageFile(self, guest):
		storageFile = guest.getElementsByTagName("storage-file")
		path = size = pool = None
		
		if storageFile:
			storageFile = storageFile[0]
			
			path = self.parseElementData(storageFile)
			pool = storageFile.getAttribute("pool")
			size = storageFile.getAttribute("size")
		
		return Storage(path, size, pool)
	
	def parseIP(self, guest, tagName, ipClass):
		ip = guest.getElementsByTagName(tagName)
		
		if ip:
			ip = ip[0]
			
			if ip.hasAttribute("method") and ip.getAttribute("method") == "dhcp":
				return IP.DHCP()
			elif ip.hasAttribute("method") and ip.getAttribute("method") == "static":
				address = self.parseTextElement(ip, "address")
				netmask = self.parseTextElement(ip, "netmask")
				gateway = self.parseTextElement(ip, "gateway")
				
				return ipClass(address, netmask, gateway)
		
		return None
	
	def parseImageFile(self, guest):
		def checkTreeinfo(url):
			url = ("%s/%s" % (url, ".treeinfo")) if url[-1] != "/" else ("%s%s" % (url, ".treeinfo"))
			
			try:
				httpRequest = urllib2.urlopen(url)
				return True
			
			except:
				return False
		
		
		path = self.parseTextElement(guest, "image-file")
		
		if path and path.startswith("http://"):
			if checkTreeinfo(path):
				return Location.HttpDir(path)
			
			elif path.endswith(".iso"):
				return Location.HttpIso(path)
			
		elif path and path.endswith(".iso"):
			return Location.LocalIso(path)
		else:
			Logging.errorExit("Image file of all guests must be set.")



if __name__ == "__main__":
	print ConfigParser("./test_scripts/config.xml").parse()
