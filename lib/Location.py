#!/usr/bin/python
#-*- coding: utf-8 -*-

import os
import urllib2
import subprocess
import ConfigParser

from System import System
from DefaultConfig import DC
from Logging import Logging


class _Image:
	def __init__(self, path):
		self.path = path
	
	def __hash__(self):
		return hash(self.getPath())
	
	def __eq__(self, other):
		return hash(self) == hash(other)
	
	def getPath(self):
		return self.path
	
	def getInstallPath(self):
		return self.getPath()
	
	def prepare(self):
		raise NotImplemented("Not implemented method prepare().")
	
	def finalize(self):
		raise NotImplemented("Not implemented method finalize().")
	
	def runHttpd(self):
		return False


class HttpDir(_Image):
	def __init__(self, path):
		_Image.__init__(self, path)
	
	def prepare(self):
		pass
	
	def finalize(self):
		pass


class LocalIso(_Image):
	#defaultMountPoint = "/media/install-virt"
	defaultMountPoint = DC.get("location", "mount-point")
	
	def __init__(self, path, mountPoint=defaultMountPoint):
		_Image.__init__(self, path)
		
		self.createdMountPoint = False
		self.mountPoint = mountPoint
	
	def getInstallPath(self):
		return self.mountPoint
	
	def mount(self):
		if not os.path.exists(self.mountPoint) or not os.path.isdir(self.mountPoint):
			Logging.debug("Creating mounting point: %s" % self.mountPoint)
			os.makedirs(self.mountPoint)
			self.createdMountPoint = True
		
		if not os.path.exists(self.getPath()):
			raise IOError("Path '%s' does not exists." % self.getPath())
		
		Logging.debug("Mounting %s to %s." % (self.getPath(), self.mountPoint))
		
		mountProcess = subprocess.Popen(["/bin/mount", '-o', 'loop', self.getPath(), self.mountPoint])
		mountProcess.wait()
		
		if mountProcess.returncode == 0 and len(os.listdir(self.mountPoint)) > 0:
			treeinfo = "%s/.treeinfo" % self.mountPoint
			
			if not os.path.exists(treeinfo):
				Logging.warn("The image doesn't contain .treeinfo file.")
			else:
				cp = ConfigParser.ConfigParser()
				cp.read(treeinfo)
				
				if cp.has_section("general") and cp.has_option("general", "arch"):
					arch = cp.get("general", "arch")
					imagesArch = "images-%s" % arch
					
					if cp.has_section(imagesArch):
						if (not cp.has_option(imagesArch, "kernel")
								or not cp.has_option(imagesArch, "initrd")):
							raise IOError("There's no kernel or initrd option"
											" in '%s' section in .treeinfo file."
											% imagesArch)
					
			
			return True
		
		return False
	
	def umount(self):
		if os.path.exists(self.mountPoint) and os.path.isdir(self.mountPoint):
			Logging.debug("Unmounting %s." % self.mountPoint)
			
			mountProcess = subprocess.Popen(["/bin/umount", self.mountPoint])
			mountProcess.wait()
			
			if mountProcess.returncode == 0 and len(os.listdir(self.mountPoint)) == 0:
				if self.createdMountPoint:
					Logging.debug("Deleting mounting point: %s" % self.mountPoint)
					os.rmdir(self.mountPoint)
					self.createdMountPoint = False
				
				return True
		
		return False
	
	def prepare(self):
		return self.mount()
	
	def finalize(self):
		return self.umount()
	
	def runHttpd(self):
		return True


class HttpIso(LocalIso):
	#defaultTempStorage = "/tmp"
	defaultTempStorage = DC.get("location", "iso-temp-storage")
	
	def __init__(self, path, mountPoint=LocalIso.defaultMountPoint,
					tempStorage=defaultTempStorage):
		LocalIso.__init__(self, path, mountPoint)
		
		self.tempStorage = tempStorage
		self.downloaded = False
	
	def download(self):
		fileName = self.path.rsplit("/", 1)
		filePath = "%s/%i-%s" % (self.tempStorage, hash(self), fileName[1])
		
		if os.path.exists(filePath):
			self.path = filePath
			self.downloaded = True
			return self.downloaded
		
		Logging.debug("Trying download %s to %s." % (self.path, filePath))
		
		try:
			httpRequest = urllib2.urlopen(self.path)
		
		except urllib2.HTTPError as e:
			return None
		
		
		if (not os.path.exists(self.tempStorage)
				or not os.access(self.tempStorage, os.W_OK)
				or System.getFreeSpace(self.tempStorage) < int(httpRequest.info().get("Content-Length"))):
			
			return None
		
		try:
			iso = file(filePath, "w")
			while 1:
				buf = httpRequest.read(16*1024)
				
				if not buf:
					break
				
				iso.write(buf)
			
			iso.close()
		
		except IOError as e:
			return None
		
		self.path = filePath
		self.downloaded = os.path.exists(filePath)
		
		return self.downloaded
	
	def prepare(self):
		if not self.downloaded:
			self.download()
		
		return LocalIso.prepare(self)
	
	def finalize(self):
		return LocalIso.finalize(self)
	
	def __del__(self):
		if self.downloaded and os.path.exists(self.path):
			Logging.debug("Trying unlink file %s." % self.path)
			os.unlink(self.path)
	