import io
import os
import sys
import json
import struct
import hashlib
import subprocess
from time import sleep
from shutil import copy
from xattr import getxattr
from binascii import hexlify

ANALYSES = '/home/cuckoo/sandbox/storage/analyses'
MOUNTPOINT = '/mnt'
NBD_DEV = '/dev/nbd0'
USERDIR_WINDOWS = 'C:\\Users\\cuckoo'
# start sector of the C: partition. needed for satana which destroys the partition table.
STARTSECT = 206848

BASE_MANIFEST = os.path.join(ANALYSES, 'base.json')
USERDIR_LINUX = os.path.join(MOUNTPOINT, USERDIR_WINDOWS[3:].replace('\\', '/'))

def sudo(*args):
	subprocess.check_call(['sudo'] + list(args))

def md5sum(file):
	with io.open(file, 'rb') as fd:
		digest = hashlib.md5()
		while True:
			data = fd.read(8192)
			if not len(data):
				break
			digest.update(data)
		return digest.hexdigest()

def scan_files(userdir):
	for line in subprocess.Popen('find -type f -print0 | xargs -0 md5sum',
			shell=True, stdout=subprocess.PIPE, cwd=userdir).stdout:
		hash = line[0:32]
		file = line[34:].rstrip()
		if file[0:2] == './':
			file = file[2:]
		if not file.startswith('AppData/'):
			yield hash, file

def ntfstime(blob, offset):
	return struct.unpack('>Q', blob[offset:offset+8])[0]

def copy_missing(target_dir, target_relpath, logfile, dumped):
	with io.open(logfile, 'wb') as log:
		for hash, file in scan_files(USERDIR_LINUX):
			filepath = USERDIR_WINDOWS + '\\' + file.replace('/', '\\')
			absfile = os.path.join(USERDIR_LINUX, file)

			if hash not in dumped:
				# 55 4-byte UTF-8 characters + hash is guaranteed to always fit
				# the Linux 255 character limit, and prevents impractically
				# long filenames. some samples do generate massive filenames,
				# and so does using Wikipedia articles as victim files...
				filename = hash + '_' + file.decode('utf-8').split('/')[-1][-55:]
				copy(os.path.join(USERDIR_LINUX, file),
						os.path.join(target_dir, filename))
				dumped[hash] = os.path.join(target_relpath, filename)

			times = getxattr(absfile, 'system.ntfs_times_be')
			# for the format of the raw NTFS times, see
			# https://www.tuxera.com/community/ntfs-3g-advanced/extended-attributes/
			info = { 'path': dumped[hash], 'md5': hash, 'filepath': filepath,
				'time_create': ntfstime(times, 0),
				'time_write': ntfstime(times, 8),
				'time_access': ntfstime(times, 16),
				'time_attrib_change': ntfstime(times, 24) }
			json.dump(info, log)
			log.write('\n')

def dump_image(image, target_dir, target_relpath, logfile, dumped):
	sudo('mkdir', '-p', target_dir)
	sudo('chown', 'cuckoo.cuckoo', target_dir)
	sudo('chmod', '0775', target_dir)
	sudo('touch', logfile)
	sudo('chown', 'cuckoo.cuckoo', logfile)
	sudo('chmod', '0664', logfile)
	sudo('chmod', '0444', image)

	sudo('qemu-nbd', '-r', '-c', NBD_DEV, '-o', str(STARTSECT * 512), image)
	sleep(1)
	try:
		sudo('mount', '-o', 'ro', NBD_DEV, MOUNTPOINT)
		try:
			copy_missing(target_dir, target_relpath, logfile, dumped)
		except Exception as e:
			print e
			try:
				sudo('fuser', '-mvk', MOUNTPOINT)
			finally:
				raise
		finally:
			sudo('umount', MOUNTPOINT)
	except Exception as e:
		print e
		raise
	finally:
		sudo('qemu-nbd', '-d', NBD_DEV)

if len(sys.argv) < 2:
	sys.stderr.write('usage: python dump.py task-id...\n')
	sys.exit(1)
if sys.argv[1] == '--base':
	dump_image(os.path.join(ANALYSES, 'base.qcow2'),
			os.path.join(ANALYSES, 'base'), 'base', BASE_MANIFEST, dict())
	sys.exit(0)
if not os.path.isfile(BASE_MANIFEST):
	sys.stderr.write('%s doesn\'t exist!\n' % BASE_MANIFEST)
	sys.stderr.write('generate it from base.qcow2 by running:\n')
	sys.stderr.write('  python dump.py --base\n')
	sys.exit(1)

base = dict()
with io.open(BASE_MANIFEST, 'rb') as infile:
	for line in infile:
		data = json.loads(line)
		base[data['md5']] = os.path.join('..', data['path'])

for task in sys.argv[1:]:
	analysis = os.path.join(ANALYSES, task)
	image = os.path.join(analysis, 'disk.qcow2')

	if not os.path.isfile(image):
		sys.stderr.write('no disk image for task %s\n' % image)
		continue
	print 'task', task
	
	dumped = dict()
	with io.open(os.path.join(analysis, 'files.json'), 'rb') as infile:
		for line in infile:
			data = json.loads(line)
			hash = md5sum(os.path.join(analysis, data['path']))
			dumped[hash] = data['path']
	dumped.update(base)
	dump_image(image, os.path.join(analysis, 'disk'), 'disk',
			os.path.join(analysis, 'disk.json'), dumped)
