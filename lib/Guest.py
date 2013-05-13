#!/usr/bin/python
#-*- coding: utf-8 -*-

import os
import subprocess
import libvirt
import ConfigParser

from System import System
from Units import Units
from VirtInstall import VirtInstall

from DefaultConfig import DC
from Logging import Logging

import Location
import IP



class Storage:
	defaultBus = "virtio"
	
	def __init__(self, path, size, pool=None, bus=defaultBus):
		self.path = path
		self.size = size
		self.pool = pool or "default"
		self.bus = bus
		
		if not self.path:
			raise ValueError("Path is empty.")
		
		if not self.size:
			raise ValueError("Size is empty.")
	
	def __hash__(self):
		return hash(self.path) + hash(self.pool)
	
	def __eq__(self, other):
		return hash(self) == hash(other)
	
	def __str__(self):
		path = os.path.basename(self.path)
		
		return "vol=%s/%s,bus=%s" % (self.pool, path, self.bus)
	
	def create(self):
		conn = libvirt.open(DC.get("virsh", "connect"))
		
		try:
			storagePool = conn.storagePoolLookupByName(self.pool)
			storagePool.refresh(0)
		except:
			Logging.errorExit("There is no '%s' libvirt storage pool." % self.pool)
		
		path = os.path.basename(self.path)
		size = Units(self.size).convertTo("B")
		
		diskXML = """
		<volume>
			<name>%s</name>
			<capacity>%i</capacity>
			<allocation>0</allocation>
			<target>
				<format type='raw'/>
			</target>
		</volume>
		"""
		diskXML = diskXML % (path, size)
		
		try:
			storage = storagePool.createXML(diskXML, 0)
		except Exception as e:
			Logging.errorExit("%s (name: %s)" % (str(e), path))
		
		return storage


class Network:
	defaultModel = "virtio"
	
	def __init__(self, network, model=defaultModel):
		self.network = network
		self.model = model
	
	def __str__(self):
		if self.network.network:
			return "network=%s,model=%s" % (self.network.network.name(), self.model)


class Guest:
	def __init__(self, hostName, memorySize, vcpuCount, imageFile, ksFile,
					networkSettingsFile, storageFile, ipv4, ipv6):
		self.hostName = hostName
		self.memorySize = memorySize
		self.vcpuCount = vcpuCount
		self.ksFile = ksFile
		self.networkSettingsFile = networkSettingsFile
		
		self.storageFile = storageFile
		self.imageFile = imageFile
		
		self.ipv4 = ipv4
		self.ipv6 = ipv6
		
		self.network = None
	
	def __hash__(self):
		return (hash(self.hostName) + hash(self.memorySize) + hash(self.ksFile)
				+ hash(self.storageFile) + hash(self.imageFile) + hash(self.ipv4)
				+ hash(self.ipv6))
	
	def __eq__(self, other):
		return hash(self) == hash(other)
	
	def __str__(self):
		return ("Hostname: %s, memory size: %s, IPv4: %s, IPv6: %s"
				% (self.hostName, self.memorySize, self.ipv4, self.ipv6))
	
	def getHostName(self):
		return self.hostName
	
	def getMemorySize(self):
		return self.memorySize
	
	def getVcpuCount(self):
		return self.vcpuCount
	
	def getKsFile(self):
		return self.ksFile
	
	def getNetworkSettingsFile(self):
		return self.networkSettingsFile
	
	def getStorageFile(self):
		return self.storageFile
	
	def getImageFile(self):
		return self.imageFile
	
	def getIPv4(self):
		return self.ipv4
	
	def getIPv6(self):
		return self.ipv6
	
	def getNetwork(self):
		return self.network
	
	def setNetwork(self, network):
		self.network = Network(network)
	
	def install(self, onlyPrepare=False):
		try:
			self.imageFile.prepare()
		
			if onlyPrepare:
				self.imageFile.finalize()
				return
			
			self.storageFile.create()
			
			vInstall = VirtInstall(self)
			vInstall.install()
		finally:
			self.imageFile.finalize()
		
		