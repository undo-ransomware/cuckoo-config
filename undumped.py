import io
import os
import sys
import json
import subprocess
from time import sleep
from shutil import copy

def sudo(*args):
	subprocess.check_call(['sudo'] + list(args))

def popen(cmd):
	return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout

if len(sys.argv) < 2:
	sys.stderr.write('usage: python unpack-vdi.py task-id...\n')
	sys.exit(1)
if not os.path.isfile('existing.md5'):
	sys.stderr.write('generate existing.md5 by mounting the unmodified VDI and doing:\n')
	sys.stderr.write('  find /mnt -type f -print0 | xargs -0 md5sum >existing.md5\n')
	sys.exit(1)

existing = set()
with io.open('existing.md5', 'rb') as infile:
	for line in infile:
		hash = line[0:32]
		existing.add(hash)

def dump_missing(analysis, dumped):
	undumped = analysis + 'undumped/'
	logfile = analysis + 'undumped.json'
	sudo('mkdir', '-p', undumped)
	sudo('chown', 'cuckoo.cuckoo', undumped)
	sudo('chmod', '0775', undumped)
	sudo('touch', logfile)
	sudo('chown', 'cuckoo.cuckoo', logfile)
	sudo('chmod', '0664', logfile)
	with io.open(logfile, 'wb') as log:
		for line in popen('find /mnt/Users/cuckoo -type f -print0 | xargs -0 md5sum'):
			hash = line[0:32]
			file = line[34:].rstrip()
			if hash not in existing and hash not in dumped and not file.startswith('/mnt/Users/cuckoo/AppData'):
				path = 'C:\\' + file[5:].replace('/', '\\')
				name = hash + '_' + file.decode('utf-8').split('/')[-1][-60:]
				copy(file, undumped + name)
				info = { 'path': 'undumped/' + name, 'pids': [], 'filepath': path }
				json.dump(info, log)
				log.write('\n')

for task in sys.argv[1:]:
	img = '/home/cuckoo/sandbox/temp-images/%s.vdi' % task
	analysis = '/home/cuckoo/sandbox/storage/analyses/%s/' % task
	dumped_files = 'find %s/files -type f -print0 | xargs -0 md5sum' % analysis

	if not os.path.isfile(img):
		sys.stderr.write('no image for task %s\n' % task)
		continue
	print 'task', task
	
	dumped = set()
	for line in popen(dumped_files):
		hash = line[0:32]
		dumped.add(hash)
	
	sudo('chown', 'matthias.matthias', img)
	sudo('chmod', '0400', img)
	sudo('qemu-nbd', '-c', '/dev/nbd0', img)
	sleep(1)
	try:
		sudo('mount', '-o', 'ro', '/dev/nbd0p2', '/mnt')
		try:
			dump_missing(analysis, dumped)
		except Exception as e:
			print e
			try:
				sudo('fuser', '-mvk', '/mnt')
			finally:
				raise
		finally:
			sudo('umount', '/mnt')
	except Exception as e:
		print e
		raise
	finally:
		sudo('qemu-nbd', '-d', '/dev/nbd0')
