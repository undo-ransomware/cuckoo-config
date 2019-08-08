#!/bin/sh -e
for task in "$@"; do
	echo compressing $task
	vdi=`readlink -f disk-$task.vdi` # get absolute path
	# this convoluted method creates a compressed image as a diff of a base
	# image called base.qcow2, which must exist. doing so saves considerable
	# amounts of space: it turns 9GB full-disk images into ~800MB diffs that
	# can still be mounted directly by qemu-nbd.
	(cd storage/analyses/$task &&
		qemu-img convert -O qcow2 $vdi full.qcow2 &&
		qemu-img create -q -f qcow2 -F qcow2 -b full.qcow2 sparse.qcow2 &&
		qemu-img rebase -f qcow2 -F qcow2 -b ../base.qcow2 sparse.qcow2 &&
		qemu-img convert -c -f qcow2 -O qcow2 -B ../base.qcow2 sparse.qcow2 \
			disk.qcow2 &&
		rm -f full.qcow2 sparse.qcow2)
	rm -f $vdi
done
