#!/usr/bin/python

import os
import sys
import subprocess
import ConfigParser
import xml.dom.minidom as xml
import libvirt

from Units import Units
from DefaultConfig import DC
from Logging import Logging


class System:
	hostMemory = Units(DC.get("system", "host-memory")).getValue()
	
	@staticmethod
	def getLineStartsWith(filePath, text):
		try:
			fileObj = open(filePath)
		except:
			return None
		
		for line in fileObj:
			if line.lower().startswith(text.lower()):
				fileObj.close()
				
				return line
		
		fileObj.close()
		
		return None
	
	@staticmethod
	def getTotalMemory(filePath=DC.get("system", "memory-info")):
		if os.path.exists(filePath):
			memfree = System.getLineStartsWith(filePath, "MemTotal")
			line = memfree.split(":")
			
			if len(line) == 2:
				return line[1].strip()
		
		return None
	
	@staticmethod
	def checkCPU(filePath=DC.get("system", "cpu-info")):
		if os.path.exists(filePath):
			flags = System.getLineStartsWith(filePath, "flags")
			line = flags.split(":")
			
			if len(line) == 2:
				return "vmx" in line[1] or "svm" in line[1]
		
		return None
	
	@staticmethod
	def getFreeSpace(path):
		if os.path.exists(path):
			vfstat = os.statvfs(path)
			
			return int(vfstat.f_bavail * vfstat.f_frsize)
		
		return None
	
	@staticmethod
	def checkEnoughMemory(guests):
		totalMemory = Units(System.getTotalMemory()).getValue()
		memoryForGuests = 0.0
		
		memory = map(lambda g: Units(g.getMemorySize()).getValue(), guests)
		
		if None in memory:
			raise ValueError("Some of guests hasn't set memory size"
								" or cannot be parsed.")
		
		memoryForGuests = reduce(lambda x, y: x + y, memory)
		
		return (totalMemory - memoryForGuests) > System.hostMemory
	
	@staticmethod
	def getHostPrivateIP(network="default"):
		conn = libvirt.open(DC.get("virsh", "connect"))
		virtNetwork = conn.networkLookupByName(network)
		
		#process = subprocess.Popen(command, shell=True, stdin=None,
									#stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		#process.wait()
		
		document = xml.parseString(virtNetwork.XMLDesc(0))
		ip = document.getElementsByTagName("ip")
		
		if ip:
			ip = filter(lambda x: not x.hasAttribute("family")
							or x.getAttribute("family") == "ipv4", ip)
			
			return ip[0].getAttribute("address")


if __name__ == "__main__":
	print System.getTotalMemory()
	print System.checkCPU()
