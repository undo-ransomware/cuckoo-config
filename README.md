# Cuckoo Configuration and Tools for Analyzing Ransomware

This reposistory contains our cuckoo configuration used for analyzing
ransomware.

Cuckoo works well for analyzing ransomware, but some things sometimes do go
wrong when that ransomware is also being fed 1GB of test data to encrypt. In
particular, cuckoo sometimes fails to dump all the encrypted files. Because
these files are the most important part in our case, we snapshot the VM's disk
after each analysis and extract the encrypted files from that snapshot.

The post-analysis snapshots will be stored as compressed differential images,
relative to a base image. Differential images save lots of disk space because
the unmodified system files don't take up space in the differential image,
they only reference blocks in the base image. Compression doesn't do much for
encrypted files, but works really well for filesystem structures – which is
all the changes there are for the common case of samples that don't run. The
images used are in QEMU's QCOW2 format because that can be directly mounted
using `qemu-nbd` (VirtualBox's VDIs can't, at least not the incremental ones).

# Environment Setup

This setup treats the `cuckoo` user as untrusted and makes sure it cannot ever
execute anything as root. This isn't strictly necessary since the VM provides
full isolation, but we're doing it anyway for an additional layer of security.
It also basically does all the steps from Cuckoo's `setup.py` manually, to
give more control over versions, paths and permissions.

Our setup used Ubuntu 18.04.3 on a physical server. Newer Ubuntu version
should work, the issue being Python 2.7 for Cuckoo. Cuckoo uses VirtualBox,
so a virtual server would both need to support nesting VirtualBox and show
reasonable performance at that.

- Checkout this repo into `/opt/cuckoo/utils`. It is needed there to run the
  `undumped.py` tool, which runs commands as root and thus must not be
  writeable by the `cuckoo` user.
- Install required packages for Cuckoo and the VM image handler. Image
  handling needs the `qemu-img` and `qemu-nbd` commands, the `psql` PostgreSQL
  commandline client, and NTFS3G (ie. `mount.ntfs`). See `setup/packages.md`
  for packages, and `setup/packages.txt` for all package versions.
- Create a Python **2.7** virtualenv in `/opt/cuckoo/venv`. Python 2.7 is a
  Cuckoo 2.0.7 restriction; it doesn't work on Python 3 yet. Install the
  requirements (`pip install -r requirements.txt`) into this virtualenv. Make
  sure the virtualenv isn't writeable to the `cuckoo` user for security.
- Checkout the Cuckoo repo (ie. our slightly modified version) into
  `/opt/cuckoo/sandbox`. Again make sure it isn't writeable by the `cuckoo`
  user.
- Copy `setup/cuckoo` to `/usr/local/bin/cuckoo` (or symlink it). This
  provides the `cuckoo` command that Cuckoo would normally provide, but with
  all libraries from paths that the `cuckoo` user cannot write.
- Create the `cuckoo` user and checkout this repo into `/home/cuckoo/sandbox`.
  Copy `setup/profile` to `/home/cuckoo/.profile`.
- Create `/home/cuckoo/sandbox/storage` and make sure it has plenty of space
  (eg. we mounted a separate 500GB logical volume there). Create subdirs
  `analyses`, `baselines`, `binaries`, writeable by the `cuckoo` user
  (`/home/cuckoo/sandbox/storage` can be `root.root` and `755`).
- Setup PostgreSQL (we used 10.10) and create a user and database, both named
  `cuckoo`. No need to set a password: PostgreSQL can use peer auth over a
  UNIX socket instead.
- Setup a VirtualBox VM called `cuckoo1` containing Windows 7, prepare it with
  Cuckoo Agent, and create a snapshot with the VM running and agent started.
  (Doing this is well-documented elsewhere.)
- Copy `setup/supervisord.conf` to `/usr/local/etc/supervisord.conf`. Copy
  `setup/vboxnet.service` and `setup/supervisord.service` to
  `/etc/systemd/system`, then enable and start them
  (`systemctl enable --now vboxnet.service supervisord.service`).
- Copy `setup/user.rules` to `/etc/ufw/user.rules`. The relevant parts are TCP
  port 2042 (Cuckoo VM-to-service communication) and the `route:allow` rules
  which permit web ports and DNS unless overridden by Cuckoo Rooter. The point
  here is that `none` routing doesn't override them, so `none` means "Web".
  (Note: This overriding behavior of all other rules is one of our custom
  changes to cuckoo!) Start ufw (`sudo ufw sart`).
- As user `cuckoo`, create a reference snapshot of the VM's disk before
  analysis: Determine the disk (not VM!) UUID from `VBoxManage list vms -l`.
  Dump it as a flat image using `VBoxManage clonemedium disk $uuid base.vdi`
  and convert it to compressed QCOW2 using
  `qemu-img convert -c -O qcow2 base.vdi /home/cuckoo/sandbox/storage/analyses/base.qcow2`.
  Take good care of that file, ie. back it up somewhere safe – all disk images
  are useless without it!
- Setup the `undumped.py` tool: Mount the base image to `/mnt` using
  `sudo qemu-nbd -r -c /dev/nbd0 base.qcow2` and
  `sudo mount -o ro /dev/nbd0p2 /mnt`, then create the filelist using
  `find /mnt -type f -print0 | xargs -0 md5sum >/home/cuckoo/sandbox/storage/analyses/existing.md5`.
  Use `fdisk -l /dev/nbd0` to determine the offset of the Windows root
  partition (usually second) and adjust `STARTSECT` in `undumped.py` if it
  isn't 404 sectors (ugly but some samples ruin the partition table).
  `umount /mnt` and release the device using `qemu-nbd -d /dev/nbd0` (else
  `undumped.py` will crash because the device is busy).
- Install and configure the web interface. This is documented in the cuckoo
  docs, but use the `setup/cuckoo-*.ini` config files for correct paths. Make
  sure to front uwsgi with an Apache or NginX doing SSL termination and
  password authentication, and restrict all services to listening on localhost
  only. In particular, set `bind_ip = 127.0.0.1` in `/etc/mongodb.conf` and
  `network.host: 127.0.0.1` in `/etc/elasticsearch/elasticsearch.yml`.

# Usage

Login as user `cuckoo` (`sudo -u cuckoo -i`, should activate the virtualenv
due the the `.profile`) and `cd sandbox`. Then use

```
python run.py /path/to/sample timeout routing
```

to run a sample. `/path/to/sample` should be absolute and obviously needs to
be readable by the cuckoo service. `timeout` is in seconds – 600 (10 minutes)
is a good starting value. Some working samples will need more time than that,
but most samples don't work anyway and that already shows in the first 10
minutes. `routing` is passed to cuckoo, and in our config means:

- `drop`: no network access, outgoing traffic is logged and dropped
- `none`: web access, ports 80, 443 and DNS only
- `internet`: full Internet access – use with utmost caution!

Note that we never found a sample that actually needed network access (!).
All either worked just fine when offline, or didn't find any usable C&C
servers even when given network access. That notably includes samples from
families which are documented to upload the key to a remote service... Which
either still have a local copy allowing recovery without payment, or remove
the key entirely making recovery impossible even after payment (it's almost
certainly the latter). Bottom line: Using only `drop` won't lose much.

Wait for image creation and compression, as well as report generation to
finish (this waiting is a non-issue when batch-running samples overnight).
If the report indicates that the sample did something, or the disk image is
suspiciously large (60-80MB is typical for a dud, so anything beyond 100MB is
very suspicious), extract the encrypted victim files using the `undumped.py`
tool (where `$id` is the analysis ID as shown in the report):

```
python /opt/cuckoo/utils/undumped.py $id
```

*Watch out for IO errors!* Cuckoo does just pull the plug on the VM after
analysis, so the filesystem can be corrupt. If the victim files are affected,
re-run the analysis with a longer timeout. `undumped.py` generates
`/home/cuckoo/sandbox/storage/analyses/$id/undumped.json`, listing all files
found in the image after analysis. Those not dumped by Cuckoo will be in
`/home/cuckoo/sandbox/storage/analyses/$id/undumped`.

# Acknowledgements

This setup was created for the
[Undo Ransomware](https://prototypefund.de/project/undo-von-ransomware-mittels-machine-learning/)
Prototype Fund project.

[![Sponsored by the Federal Ministry of Education and Research](bmbf.png)](https://www.bmbf.de/)
[![A Prototype Fund Project](ptf.png)](https://prototypefund.de/)
[![Prototype Fund is an Open Knowledge Foundation Project](okfn.png)](https://okfn.de/)

Much of this configuration is just the default configuration of
[Cuckoo Sandbox](https://cuckoosandbox.org/).
