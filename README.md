# Cuckoo Configuration and Tools for Analyzing Ransomware

This reposistory contains our cuckoo configuration used for analyzing
ransomware.

Cuckoo works well for analyzing ransomware, but some things sometimes do go
wrong when that ransomware is also being fed 1GB of test data to encrypt. In
particular, cuckoo sometimes fails to dump all the encrypted files. Because
these files are the most important part in our case, we snapshot the VM's disk
after each analysis and extract the encrypted files from that snapshot.

# Usage

Use `python run.py /path/to/sample timeout routing` to run a sample.
`/path/to/sample` should be absolute and obviously needs to be readable by the
cuckoo service. `timeout` is in seconds – 600 (10 minutes) is a good starting
value. Some working samples will need more time, but most samples don't work
anyway and that already shows in the first 10 minutes. `routing` is passed to
cuckoo, and in our config means:

- `drop`: no network access, outgoing traffic is logged and dropped
- `none`: web access, ports 80, 443 and DNS only
- `internet`: full Internet access – use with utmost caution!

Note that `python` is hard-to-get Python 2.7, which is however needed anyway
until cuckoo transitions to Python 3.

# Acknowledgements

This setup was created for the
[Undo Ransomware](https://prototypefund.de/project/undo-von-ransomware-mittels-machine-learning/)
Prototype Fund project.

[![Sponsored by the Federal Ministry of Education and Research](bmbf.png)](https://www.bmbf.de/)
[![A Prototype Fund Project](ptf.png)](https://prototypefund.de/)
[![Prototype Fund is an Open Knowledge Foundation Project](okfn.png)](https://okfn.de/)

Much of this configuration is just the default configuration of
[Cuckoo Sandbox](https://cuckoosandbox.org/).
