import os
import sys
import subprocess

def system(cmd):
    subprocess.check_call(cmd, shell=True)

if len(sys.argv) == 1:
	print 'usage: python compress-image.py task-id...'
	sys.exit(1)

for task in sys.argv[1:]:
	print 'compressing', task
	# this convoluted method creates a compressed image as a diff of a base
	# image called base.qcow2, which must exist. it's usually worth it though:
	# this turns 9GB full-disk images into ~800MB diffs that can be mounted
	# using qemu-nbd!
	vdi = '%s-full.vdi' % task
	full = '%s-full.qcow2' % task
	sparse = '%s-sparse.qcow2' % task
	compressed = '%s.qcow2' % task
	system('qemu-img convert -O qcow2 temp-images/%s temp-images/%s'
			% (vdi, full))
	system('qemu-img create -q -f qcow2 -F qcow2 -b %s temp-images/%s'
			% (full, sparse))
	system('cd temp-images && qemu-img rebase -f qcow2 -F qcow2 ' +
			'-b base.qcow2 %s' % sparse)
	os.remove('temp-images/' + full)
	system('qemu-img convert -c -f qcow2 -O qcow2 -B base.qcow2 ' +
			'temp-images/%s temp-images/%s' % (sparse, compressed))
	os.remove('temp-images/' + sparse)
	os.remove('temp-images/' + vdi)
