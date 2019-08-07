import io
import os
import sys
import json
import subprocess
from time import sleep
from shutil import copy
from xattr import getxattr
from binascii import hexlify

# start sector of the C: partition. needed for satana which destroys the partition table.
STARTSECT = 206848

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
			if file.startswith('/mnt/Users/cuckoo/AppData'):
				continue

			filepath = 'C:\\' + file[5:].replace('/', '\\')
			if hash in existing:
				path = None
			elif hash in dumped:
				path = dumped[hash]
			else:
				path = 'undumped/' + hash + '_' + file.decode('utf-8').split('/')[-1][-60:]
				copy(file, analysis + path)
				dumped[hash] = path
			# see https://www.tuxera.com/community/ntfs-3g-advanced/extended-attributes/
			times = hexlify(getxattr(file, 'system.ntfs_times_be'))
			info = { 'path': path, 'md5': hash, 'filepath': filepath, 'times': times }
			json.dump(info, log)
			log.write('\n')

for task in sys.argv[1:]:
	img = '/home/cuckoo/sandbox/temp-images/%s.vdi' % task
	analysis = '/home/cuckoo/sandbox/storage/analyses/%s/' % task
	dumped_files = 'cd %s && find files -type f -print0 | xargs -0 md5sum' % analysis

	if not os.path.isfile(img):
		sys.stderr.write('no image for task %s\n' % task)
		continue
	print 'task', task
	
	dumped = dict()
	for line in popen(dumped_files):
		hash = line[0:32]
		file = line[34:].rstrip()
		dumped[hash] = file
	
	sudo('chown', 'matthias.matthias', img)
	sudo('chmod', '0400', img)
	sudo('qemu-nbd', '-c', '/dev/nbd0', '-o', str(STARTSECT * 512), img)
	sleep(1)
	try:
		sudo('mount', '-o', 'ro', '/dev/nbd0', '/mnt')
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
