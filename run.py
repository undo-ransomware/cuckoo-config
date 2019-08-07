import os
import re
import sys
import time
import subprocess

def popen(cmd):
	return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout

def getline(cmd, key, regex, verbose=True):
	for line in popen(cmd):
		if key in line:
			return re.search(regex, line).group(1)
		elif verbose:
			print line.rstrip()
	raise Exception('"%s" not found in output of %s' % (key, cmd))

def system(cmd):
	subprocess.check_call(cmd, shell=True)

def clonedisk(task):
	uuid = getline('VBoxManage list vms -l', 'SATA (0, 0): ',
		'\{([0-9a-f-]{36})\}', verbose=False)
	print 'rootdisk', uuid
	vdi = 'temp-images/%s-full.vdi' % task
	clone = getline('VBoxManage clonemedium disk %s %s' % (uuid, vdi),
			'Clone medium created ','UUID: ([0-9a-f-]{36})')
	print 'clone', clone
	system('VBoxManage closemedium %s' % clone)
	# run image compression in background, with idle IO priority to minimize
	# the impact on the next analysis task.
	system('ionice -c3 python compress-image.py %s &' % task)

def submit(path, timeout, route):
	return getline('cuckoo submit --package exe --timeout %s -o route=%s "%s"'
		% (timeout, route, path), 'added as task', 'task with ID #([0-9]+)')

def wait(task):
	while True:
		status = getline(
			'psql cuckoo cuckoo -c "select status from tasks where id = %s" -qt'
			% task, '', '(\S+)')
		sys.stdout.write('\r' + status + '        ')
		sys.stdout.flush()
		if 'completed' in status or 'reported' in status:
			sys.stdout.write('\n')
			return
		time.sleep(15)

if len(sys.argv) != 4:
	print 'usage: python run.py /absolute/path/to/sample timeout routing'
	sys.exit(1)
(path, timeout, route) = sys.argv[1:]
task = submit(path, timeout, route)
print 'task', task
wait(task)
clonedisk(task)
