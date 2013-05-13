#!/usr/bin/python
#-*- coding: utf-8 -*-

import os
import pty
import signal
import time
import subprocess
import libvirt
import datetime
import random
import ConfigParser
import xml.dom.minidom as xml

from System import System
from Units import Units
from DefaultConfig import DC
from Logging import Logging


class InstallationError(Exception):
	pass


class DefaultHandler:
	def __init__(self, stdin, stdout, process):
		self.stdin = stdin
		self.stdout = stdout
		self.process = process
		
		self.log = open(self.stdout.name)
	
	def handle(self):
		count = 0
		lastText = ""
		
		while self.process.poll() == None:
			output = self.log.read()
			
			if output:
				lastText = output.lower()
				count = 0
			else:
				count += 1
			
			if count > 2 and lastText.endswith("login: "):
				break
			elif count > 30 and ("traceback" in lastText or 
									"error" in lastText or "dead" in lastText):
				raise InstallationError("Installation is frozen."
											" Shutting down installation.")
			
			
			time.sleep(5)
		
		if self.process.poll() not in [0, None]:
			raise InstallationError("Bad insallation of virtual machine."
										" Shutting down installation.")


#def createDisk(path):
    #conn = libvirt.open(None)
    #defaultStoragePool = conn.storagePoolLookupByName("default")
    #defaultStoragePool.refresh(0)

    #diskXML = """
	#<volume>
		#<name>%s</name>
		#<capacity>5368709120</capacity>
		#<allocation>0</allocation>
		#<target>
			#<format type='raw'/>
		#</target>
	#</volume>
    #"""
    #diskXML = diskXML % os.path.basename(path)
    
    #defaultStoragePool.createXML(diskXML, 0)


class Httpd:
	#defaultCmd   = "/root/svn/xchury1_bp/httpd.py %(path)s %(port)i"
	defaultCmd = DC.get("httpd", "command", True)
	
	ports = eval(DC.get("httpd", "ports"))
	
	
	def __init__(self, path, guest, command=defaultCmd):
		self.path = path
		self.guest = guest
		self.command = command
		
		self.process = None
		
		self.port = Httpd.getPort()
	
	def __str__(self):
		#hostIP = System.getHostPrivateIP("installvm")
		hostIP = self.guest.network.network.getIPv4Address()
		
		return "http://%s:%i" % (hostIP, self.port)
	
	@staticmethod
	def getPort():
		if Httpd.ports:
			port = Httpd.ports[0]
			Httpd.ports = Httpd.ports[1:]
			
			return port
		else:
			return random.randrange(20000, 40000)
	
	def start(self):
		values = {'path': self.path, 'port': self.port}
		
		devnull = open("/dev/null", "w")
		self.process = subprocess.Popen(self.command % values, shell=True, stdout=devnull, stderr=devnull)
		
		return self.process
	
	def kill(self):
		Httpd.ports.append(self.port)
		
		return self.process.kill()
	
	def running(self):
		return self.process and self.process.poll() == None


class VirtInstall:
	#defaultInstall = ("/usr/bin/virt-install"
					#" --name '%(hostname)s'"
					#" --ram %(memorysize)i"
					#" --vcpus %(vcpus)i"
					#" --location '%(location)s'"
					#" --disk '%(storage)s'"
					#" --network '%(network)s'"
					#" --graphics none"
					#" --extra-args 'ks=%(kspath)s console=tty0 console=ttyS0,115200'"
					##" --memballoon none"
					#" --wait 120"
					#" --noreboot")
	
	#defaultDestroy = "/usr/bin/virsh destroy %(hostname)s"
	
	
	#defaultLog     = "/tmp/installVM-%(hostname)s.log"
	
	#defaultKsFile  = "/root/svn/xchury1_bp/ks/fedora18.cfg"
	
	defaultInstall = DC.get("virt-install", "install", True)
	defaultDestroy = DC.get("virsh", "destroy", True)
	
	defaultLog = DC.get("virt-install", "log", True)
	defaultKsFile = DC.get("virt-install", "default-ks")
	
	
	def __init__(self, guest, cmdInstall=defaultInstall, cmdDestroy=defaultDestroy,
					log=defaultLog, ksFile=defaultKsFile):
		
		self.guest = guest
		
		self.cmdInstall = cmdInstall
		self.cmdDestroy = cmdDestroy
		
		self.log    = log
		self.ksFile = ksFile
		
		self.values = {}
	
	def install(self, handler=DefaultHandler):
		self.setValues()
		destroy = None
		servers = self.startHttpd()
		
		master, slave = pty.openpty()
		
		stdin = os.fdopen(master, "w")
		
		logPath = self.log % self.values
		Logging.debug("Trying write install log of VM '%s' to %s."
										% (self.guest.getHostName(), logPath))
		stdout = open(logPath, "w")
		
		try:
			self.cmdInstall = self.cmdInstall.replace("\n", " ")
			
			Logging.info("Trying install guest '%s'..." % self.guest.getHostName())
			Logging.debug(self.cmdInstall % self.values)
			
			process = subprocess.Popen(self.cmdInstall % self.values, shell=True,
										stdin=slave, stdout=stdout, stderr=stdout,
										close_fds=True)
			
			analyzator = handler(stdin, stdout, process)
			analyzator.handle()
		except InstallationError as e:
			destroy = subprocess.Popen(self.cmdDestroy % self.values, shell=True)
			Logging.info("Check installation log for details: %s" % logPath)
			raise e
		finally:
			if servers[0]: servers[0].kill()
			if servers[1]: servers[1].kill()
		
		if destroy:
			return not destroy.wait()
		
		Logging.info("Guest '%s' installed." % self.guest.getHostName())
		
		return
	
	def setValues(self):
		self.values = {
			"hostname":    self.guest.getHostName(),
			"memorysize":  Units(self.guest.getMemorySize()).convertTo("MB"),
			"storage":     self.guest.getStorageFile(),
			"vcpus":       self.guest.getVcpuCount() or 1,
			"network":     self.guest.getNetwork(),
		}
	
	def startHttpd(self):
		locationHttpd = ksHttpd = None
		imageFile = self.guest.getImageFile()
		ksFile = self.guest.getKsFile()
		
		
		if imageFile.runHttpd():
			locationHttpd = Httpd(imageFile.getInstallPath(), self.guest)
			locationHttpd.start()
			self.values["location"] = str(locationHttpd)
		else:
			self.values["location"] = imageFile.getInstallPath()
		
		
		if ksFile and ksFile.startswith("http://"):
			self.values["kspath"] = ksFile
		else:
			ksFile = ksFile if ksFile else self.ksFile
			
			if (not os.path.exists(ksFile)
					or not os.access(ksFile, os.R_OK)):
				raise InstallationError("Kickstart file does not exists!")
			
			ksHttpd = Httpd(os.path.dirname(ksFile), self.guest)
			ksHttpd.start()
			self.values["kspath"] = "%s/%s" % (ksHttpd, os.path.basename(ksFile))
		
		
		if ((locationHttpd and not locationHttpd.running()) or
				(ksHttpd and not ksHttpd.running())):
			raise InstallationError("Httpd for installation is not running."
										" Used port is propablby allocated"
										" by another process.")
		
		return (locationHttpd, ksHttpd)



if __name__ == "__main__":
	pass
	
	
