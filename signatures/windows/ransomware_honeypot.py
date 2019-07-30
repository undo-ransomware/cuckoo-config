# Copyright (C) 2012,2015 Claudio "nex" Guarnieri (@botherder), Optiv, Inc. (brad.spengler@optiv.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

try:
    import re2 as re
except ImportError:
    import re

from lib.cuckoo.common.abstracts import Signature

USERDIR = r'^[A-Z]?:\\(Users|Documents and Settings)\\[^\\]+\\'

class ADS(Signature):
    name = "ransomware_honeypot"
    description = "Interacts with %d of the ransomware victim files"
    severity = 3
    categories = ["ransomware"]
    authors = ["Matthias Fratz"]
    minimum = "2.0"

    def on_complete(self):
        count = 0
        for filepath in self.get_files():
            if re.match(USERDIR, filepath, re.IGNORECASE) and not re.match(
                    USERDIR + r'AppData\\', filepath, re.IGNORECASE):
                self.mark_ioc("file", filepath)
                count += 1

        if self.has_marks():
            self.description = self.description % count
            if self.has_marks(20):
                self.severity = 5
            return True
        return False
