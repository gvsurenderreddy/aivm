#!/usr/bin/python

import os
import sys
import re

class Units:
	convertTable = { "b": 1, "kb": 1e3, "kib": 1.024e3, "mb": 1e6, "mib": 1.024e6,
					"gb": 1e9, "gib": 1.024e9, "tb": 1e12, "tib": 1.024e12 }
	
	def __init__(self, value):
		if isinstance(value, str) or isinstance(value, unicode):
			self.value = value
			self.value = self.convertFrom()
			
			if not self.value:
				raise ValueError("Bad format of value '%s'." % str(self.value))
		
		elif isinstance(value, int) or isinstance(value, float):
			self.value = value
		
		else:
			self.value = None
	
	def getValue(self):
		return self.value
	
	def convertFrom(self):
		if self.value == None:
			return None
		
		self.value = self.value.strip().replace(" ", "").lower()
		
		match = re.match("(-?\d+)([a-z]{1,3})", self.value)
		
		if match:
			number = int(match.group(1))
			unit = match.group(2)
			
			return number*self.convertTable[unit]
		
		return None
	
	def convertTo(self, unit):
		if self.value == None or unit == None:
			return None
		
		unit = unit.lower()
		
		if not unit in self.convertTable:
			return None
		
		return self.value/self.convertTable[unit]


if __name__ == "__main__":
	print Units("8199 MB").convertTo("kB")
	print Units(8000).convertTo("KiB")
