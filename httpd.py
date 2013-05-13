#!/usr/bin/python

import sys
import os
import SimpleHTTPServer
import SocketServer
import shutil
import re
import posixpath
import urllib
import logging

class InstallVMHttpd(SimpleHTTPServer.SimpleHTTPRequestHandler):
	def send_head(self):
		"""Common code for GET and HEAD commands.

		This sends the response code and MIME headers.

		Return value is either a file object (which has to be copied
		to the outputfile by the caller unless the command was HEAD,
		and must be closed by the caller under all circumstances), or
		None, in which case the caller has nothing further to do.

		"""
		
		self.f_length = None
		
		path = self.translate_path(self.path)
		f = None
		if os.path.isdir(path):
			if not self.path.endswith('/'):
			    # redirect browser - doing basically what apache does
			    self.send_response(301)
			    self.send_header("Location", self.path + "/")
			    self.end_headers()
			    return None
			for index in "index.html", "index.htm":
			    index = os.path.join(path, index)
			    if os.path.exists(index):
			        path = index
			        break
			else:
			    return self.list_directory(path)
		ctype = self.guess_type(path)
		try:
			# Always read in binary mode. Opening files in text mode may cause
			# newline translations, making the actual size of the content
			# transmitted *less* than the content-length!
			f = open(path, 'rb')
		except IOError:
			self.send_error(404, "File not found")
			return None

		f_range = self.headers.get("Range")
		
		#if f_range:
		self.send_response(206 if f_range else 200)
		#else:
		#	self.send_response(200)
		
		self.send_header("Content-type", ctype)
		fs = os.fstat(f.fileno())
		self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
		
		content_length = fs[6]
		
		if f_range:
			# get tuple (position, length)
			num_range = self.get_range(f_range, fs[6])
			if num_range:
				self.send_header("Content-Range", "%s/%i" % (f_range.replace("=", " "), fs[6]))
				# set read position in file
				f.seek(num_range[0])
				
				# set length to read
				self.f_length = content_length = num_range[1]
		
		self.send_header("Content-Length", str(content_length))
		self.end_headers()
		
		return f


	def copyfile(self, source, outputfile):
		"""Copy all data between two file objects.

		The SOURCE argument is a file object open for reading
		(or anything with a read() method) and the DESTINATION
		argument is a file object open for writing (or
		anything with a write() method).

		The only reason for overriding this would be to change
		the block size or perhaps to replace newlines by CRLF
		-- note however that this the default server uses this
		to copy binary data as well.

		"""
		if self.f_length:
			bufsize = 4096
			length = self.f_length
			remain = length % bufsize
			
			while length > remain:
				buf = source.read(bufsize)
				
				if not buf:
					break
				
				outputfile.write(buf)
				length -= bufsize
			
			outputfile.write(source.read(remain))
		else:
			shutil.copyfileobj(source, outputfile)


	def translate_path(self, path):
		"""Translate a /-separated PATH to the local filename syntax.

		Components that mean special things to the local file system
		(e.g. drive or directory names) are ignored.  (XXX They should
		probably be diagnosed.)

		"""
		# abandon query parameters
		path = path.split('?',1)[0]
		path = path.split('#',1)[0]
		path = posixpath.normpath(urllib.unquote(path))
		words = path.split('/')
		words = filter(None, words)
		
		path = sys.argv[1]
		
		for word in words:
			drive, word = os.path.splitdrive(word)
			head, word = os.path.split(word)
			if word in (os.curdir, os.pardir): continue
			path = os.path.join(path, word)
		
		return path
	

	def get_range(self, http_range, size):
		"""
			Return tuple (position, length) where position is start
			byte in file for read and length is count of bytes for read.
			
			Keyword arguments:
			http_range -- value of HTTP Range field
			size -- size of readed file
		"""
		match = re.match("^bytes=(\d+)?-(\d+)?$", http_range)
		
		if match:
			start = int(match.group(1)) if match.group(1) else None
			end = int(match.group(2)) if match.group(2) else None
			
			if start == None:
				return (size-end, end+1)
			elif end == None:
				return (start, size-start+1)
			elif start != None and end != None:
				return (start, end-start+1)
		
		return None


def main():
	port = 8080
	
	if len(sys.argv) < 2 or len(sys.argv) > 3:
		logging.error("%s takes 1 or 2 arguments: the first is path to directory, the second optional argument is port number (default is 8080)", sys.argv[0])
		exit(-1)
	elif len(sys.argv) > 1:
		sys.argv[1] = os.path.abspath(sys.argv[1])
		
		if not os.access(sys.argv[1], os.F_OK | os.R_OK | os.X_OK):
			logging.error("Given directory %s is not exists or isn't readable.", sys.argv[1])
			exit(-1)
		
		if len(sys.argv) > 2:
			try:
				port = int(sys.argv[2])
			except ValueError as e:
				logging.error("Given port number is not natural number.")
				exit(-1)

	try:
		httpd = SocketServer.TCPServer(("", port), InstallVMHttpd)
		
		logging.info("serving at port %i", port)
		httpd.serve_forever()
	except IOError as e:
		logging.error(e)
		exit(-1)


if __name__ == "__main__":
	main()

