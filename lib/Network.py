#!/usr/bin/python
#-*- coding: utf-8 -*-

import os
import re
import sys
import pty
import time
import logging
import libvirt
import tempfile
import subprocess
import ConfigParser
import xml.dom.minidom as xml

import Guest
import IP
import ConfigParserXML
from Logging import Logging

from DefaultConfig import DC


class Network:
	#defaultConfig = "../etc/network.xml"
	defaultConfig = DC.get("network", "config")
	
	def __init__(self, config=defaultConfig):
		self.config = config
		self.network = None
	
	def getAddresses(self):
		conn = libvirt.open(DC.get("virsh", "connect"))
		xmlDescStr = self.network.XMLDesc(0)
		xmlDesc = xml.parseString(xmlDescStr)
		
		return xmlDesc.getElementsByTagName("ip")
	
	def _getIPInformation(self, filterFunction):
		addresses = self.getAddresses()
		
		if addresses:
			ip = filter(filterFunction, addresses)
			
			return ip[0]
	
	def _getIPAddress(self, filterFunction):
		return self._getIPInformation(filterFunction).getAttribute("address")
	
	def _getIPv6Prefix(self, filterFunction):
		return self._getIPInformation(filterFunction).getAttribute("prefix")
	
	def getIPv4Address(self):
		return self._getIPAddress(lambda x: not x.hasAttribute("family") or x.getAttribute("family") == "ipv4")
	
	def getIPv6Address(self):
		return self._getIPAddress(lambda x: x.getAttribute("family") == "ipv6")
	
	def getIPv6Prefix(self):
		return self._getIPv6Prefix(lambda x: x.getAttribute("family") == "ipv6")
	
	def getInterface(self):
		xmlDesc = self.network.XMLDesc(0)
		networkXml = xml.parseString(xmlDesc)
		
		bridges = networkXml.getElementsByTagName("bridge")
		
		if bridges:
			bridge = bridges[0]
			
			return bridge.getAttribute("name")
	
	def parseName(self):
		def parseElementData(element):
			textNodes = filter(lambda x: x.nodeType == x.TEXT_NODE, element.childNodes)
			data = map(lambda x: x.data.strip(), textNodes)
			
			return "".join(data)
		
		configFile = file(self.config, "r")
		xmlConfig = xml.parse(configFile)
		
		name = xmlConfig.getElementsByTagName("name")
		
		return parseElementData(name[0])
	
	def check(self):
		network = self.parseName()
		
		Logging.info("Checking network '%s'..." % network)
		
		conn = libvirt.open(DC.get("virsh", "connect"))
		networks = conn.listNetworks()
		
		if not network in networks:
			return True
		
		return False
	
	def create(self):
		Logging.info("Creating the network ...")
		conn = libvirt.open(DC.get("virsh", "connect"))
		configFile = file(self.config, "r")
		#print configFile.read()
		self.network = conn.networkDefineXML(configFile.read())
		self.network.setAutostart(1)
		self.network.create()
		
		return
	
	def makeDNS(self, dnsDict):
		document = xml.Document()
		dns = document.createElement("dns")
		
		for host in dnsDict:
			hostXml = document.createElement("host")
			hostXml.setAttribute("ip", host)
			
			hostname1 = document.createTextNode("%s.%s" % (dnsDict[host], DC.get("network", "domain")))
			hostname2 = document.createTextNode("%s" % dnsDict[host])
			
			hostnameXml1 = document.createElement("hostname")
			hostnameXml1.appendChild(hostname1)
			hostnameXml2 = document.createElement("hostname")
			hostnameXml2.appendChild(hostname2)
			
			hostXml.appendChild(hostnameXml1)
			hostXml.appendChild(hostnameXml2)
			dns.appendChild(hostXml)
		
		return dns
	
	def insertDNS(self, dnsDict):
		conn = libvirt.open(DC.get("virsh", "connect"))
		xmlDesc = self.network.XMLDesc(0)
		
		Logging.debug("Inserting DNS entries: %s" % str(dnsDict))
		
		localDns = self.makeDNS(dnsDict)
		
		networkXml = xml.parseString(xmlDesc)
		dns = networkXml.getElementsByTagName("dns")
		
		if dns:
			dns = dns[0]
			for entry in localDns.getElementsByTagName("host"):
				dns.appendChild(entry)
		else:
			networkXml.documentElement.appendChild(localDns)
		
		
		self.network.destroy()
		self.network.undefine()
		
		self.network = conn.networkDefineXML(networkXml.documentElement.toxml())
		self.network.setAutostart(1)
		self.network.create()
		
		
		values = {'addr': self.getIPv6Address(), 'prefix': self.getIPv6Prefix(),
					'interface': self.getInterface()}
		
		if (DC.has_option("network", "manual-route")
				and DC.get("network", "manual-route", True)):
			cmd = DC.get("network", "manual-route", False, values)
			cmd = cmd.replace("\n", " ")
			
			subprocess.Popen(cmd, shell=True)
		else:
			Logging.warning("Manual route not set. Skipping.")
		
		return


class NetworkSetterError(Exception):
	pass


class NetworkSetter:
	def __init__(self, guest):
		self.guest = guest
		self.configPath = guest.getNetworkSettingsFile()
		
		self.config = ConfigParser.ConfigParser()
		
		if self.configPath:
			self.config.read(self.configPath)
		
		
		self.stdin = None
		self.stdout = None
		self.process = None
		
		self.setValues()
	
	def setValues(self):
		self.values = {
			'hostname': self.guest.getHostName(),
		}
	
	def run(self):
		if self.configPath and self.config.sections():
			self.start()
			self.login()
			self.setNetwork()
			output = self.getNetwork()
			self.stop()
			
			return output
		else:
			Logging.warning("Network settings not set. Skipping setting"
							" network on guest '%s'.", self.guest.getHostName())
			
			return {}
	
	def start(self):
		master, slave = pty.openpty()
		self.stdin = os.fdopen(master, "w")
		self.stdout = tempfile.NamedTemporaryFile("w")
		
		virshStart = DC.get("virsh", "start", False, self.values)
		
		self.process = subprocess.Popen(virshStart, shell=True, stdin=slave,
											stdout=self.stdout, stderr=self.stdout,
											close_fds=True)
	
	def stop(self):
		self.stdin.write("\n\npoweroff\n\n")
		
		for i in xrange(0, 30):
			if self.process.poll() != None:
				break
			
			if i > 20:
				virshDestroy = DC.get("virsh", "destroy", False, self.values)
				
				subprocess.Popen(virshDestroy, shell=True)
			
			time.sleep(1)
	
	def login(self):
		count = phase = loginCount = 0
		lastText = ""
		
		stdoutRead = open(self.stdout.name)
		
		while self.process.poll() == None:
			output = stdoutRead.read()
			
			if output:
				lastText = output.lower()
				count = 0
			else:
				count += 1
			
			
			if phase == 0 and re.search("login: ", lastText):
				self.stdin.write("%s\n" % self.config.get("auth", "login"))
				phase = 1
			
			if phase == 1 and re.search("password: ", lastText):
				self.stdin.write("%s\n\n\n" % self.config.get("auth", "password"))
				time.sleep(2)
				self.stdin.write("echo ==AUTH-OK==\n")
				
				phase = 2
			
			if phase == 2 and "\n==auth-ok==" in lastText:
				break
			
			
			if count > 30:
				raise NetworkSetterError("Bad authentication in guest '%s'." % self.guest.getHostName())
			
			time.sleep(1)
		
		stdoutRead.close()
	
	def getNetwork(self):
		self.stdin.write("\n")
		
		stdoutRead = open(self.stdout.name)
		stdoutRead.seek(0, os.SEEK_END)
		
		Logging.info("Getting network settings...")
		
		command = self.config.get("commands", "get")
		self.stdin.write("%s\necho ==GET-NETWORK-DONE==\n\n" % command)
		
		addresses = ""
		i = 0
		while not "\n==GET-NETWORK-DONE==" in addresses:
			addresses += stdoutRead.read()
			
			if i > 50:
				raise NetworkSetterError("Error occured while getting network settings from guest '%s'." % self.guest.getHostName())
			
			i += 1
			time.sleep(1)
		
		
		Logging.debug("Raw network settings: %s" % str(addresses))
		
		inets = re.findall("inet6?\s+([a-f0-9:./]+)", addresses)
		
		ipAddresses = map(lambda inet: inet.split("/"), inets)
		ipAddresses = filter(lambda ip: not ip[0].startswith("fe80"), ipAddresses)
		
		Logging.debug("Processed network settings: %s" % str(ipAddresses))
		
		ipDict = {}
		
		for ip in ipAddresses:
			ipDict[ip[0]] = self.guest.getHostName()
		
		time.sleep(2)
		stdoutRead.close()
		
		return ipDict
	
	def setNetwork(self):
		self.stdin.write("\n")
		
		stdoutRead = open(self.stdout.name)
		stdoutRead.seek(0, os.SEEK_END)
		
		Logging.info("Trying set network...")
		
		settings = self.prepareData()
		commands = self.config.get("commands", "set", False, { "settings": settings })
		
		Logging.debug("Commands to write:\n%s" % str(commands))
		
		singleCommands = commands.split("\n")
		
		for cmd in singleCommands:
			self.stdin.write("%s\n" % cmd)
			time.sleep(0.1)
		
		self.stdin.write("\necho ==SET-NETWORK-DONE==\n\n")
		
		time.sleep(1)
		
		output = ""
		i = 0
		while not "\n==SET-NETWORK-DONE==" in output:
			output += stdoutRead.read()
			
			if i > 50:
				raise NetworkSetterError("Error occured while setting network settings from guest '%s'." % self.guest.getHostName())
			
			i += 1
			time.sleep(1)
		
		time.sleep(1)
		
		stdoutRead.close()
	
	def prepareData(self):
		ipv4 = self.guest.getIPv4()
		ipv6 = self.guest.getIPv6()
		
		self.values['dns-servers'] = self.getDNSServers()
		self.values['domain'] = DC.get("network", "domain")
		
		config = ""
		config += self.config.get("settings", "all", False, self.values)
		
		ipv4Values = {}
		ipv6Values = {}
		
		if not ipv4:
			ipv4Settings = self.config.get("settings", "ipv4-disabled", False, ipv4Values)
		elif isinstance(ipv4, IP.IPv4):
			ipv4Values = { "address": ipv4.getAddress(), "netmask-full": ipv4.getLongNetmask(),
				"netmask-prefix": ipv4.getShortNetmask(), "gateway": ipv4.getGateway(),
				"domain": DC.get("network", "domain"),
			}
			
			ipv4Settings = self.config.get("settings", "ipv4-static", False, ipv4Values)
		elif isinstance(ipv4, IP.DHCP):
			ipv4Settings = self.config.get("settings", "ipv4-dhcp", False, ipv4Values)
		
		config += "%s\n" % ipv4Settings
		
		if not ipv6:
			ipv6Settings = self.config.get("settings", "ipv6-disabled", False, ipv6Values)
		elif isinstance(ipv6, IP.IPv6):
			ipv6Values = { "address": ipv6.getAddress(), "netmask-full": ipv6.getLongNetmask(),
				"netmask-prefix": ipv6.getShortNetmask(), "gateway": ipv6.getGateway(),
				"domain": DC.get("network", "domain"),
			}
			
			ipv6Settings = self.config.get("settings", "ipv6-static", False, ipv6Values)
		elif isinstance(ipv6, IP.DHCP):
			ipv6Settings = self.config.get("settings", "ipv6-dhcp", False, ipv6Values)
		
		config += "%s\n" % ipv6Settings
		
		
		return config
	
	def getDNSServers(self):
		pattern = self.config.get("settings", "dns", True)
		pattern += "\n"
		dns = ""
		i = 1
		
		#print self.guest.network
		#print self.guest.network.network
		#print self.guest.network.network.network
		
		dnsIPv6 = self.guest.network.network.getIPv6Address()
		if dnsIPv6:
			dns += pattern % { "number": i, "address": dnsIPv6 }
			i += 1
		
		dnsIPv4 = self.guest.network.network.getIPv4Address()
		if dnsIPv4:
			dns += pattern % { "number": i, "address": dnsIPv4 }
			i += 1
		
		self.values['dns-servers'] = dns
		
		return dns


if __name__ == "__main__":
	pass