# Volatility
# Copyright (C) 2007-2013 Volatility Foundation
#
# This file is part of Volatility.
#
# Volatility is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Volatility is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Volatility.  If not, see <http://www.gnu.org/licenses/>.
#

import re
import volatility.obj as obj
import volatility.plugins.mac.common as common
import volatility.utils as utils
import volatility.plugins.mac.pstasks as pstasks 

class mac_calendar(pstasks.mac_tasks):
    """Gets calendar events from Calendar.app"""

    def calculate(self):
        common.set_plugin_members(self)

        ##-----------------------------------------------------------
        # Local Calendar Events
        ##-----------------------------------------------------------

        guid_re = re.compile("[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}")
        guid_length = 36
        seen = []

        for page, size in self.addr_space.get_available_pages():

            data = self.addr_space.read(page, size)
            if not data:
                continue
            
            for offset in utils.iterfind(data, "local_"):
                event = obj.Object("String", 
                                    offset = page + offset, 
                                    vm = self.addr_space, encoding = "utf8", 
                                    length = 512)
                if "ACCEPTED" not in str(event):
                    continue

                # determine where the next field starts 
                field_len = len("local_") + guid_length 
                next_field = str(event)[field_len:]

                # the next field is either a description or GUID
                match = guid_re.search(next_field)

                if match.start() == 0:
                    description = ""
                    last_field = next_field[guid_length:]
                else:
                    description = next_field[:match.start()]
                    last_field = next_field[match.start() + guid_length:]
                
                location = last_field.split("ACCEPTED")[0]

                if (description, location) in seen:
                    continue

                seen.append((description, location))
                yield None, description, location

        ##-----------------------------------------------------------
        # Shared / Global Calendar Events
        ##-----------------------------------------------------------

        procs = pstasks.mac_tasks.calculate(self)
        guid_re2 = re.compile("\x25\x00\x00\x00[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\x00")

        for proc in procs:
            space = proc.get_process_address_space()
            for map in proc.get_proc_maps():    
                # only read/write without filebacks 
                if not (map.get_perms() == "rw-" and not map.get_path()):
                    continue
                pages = (map.links.end - map.links.start) / 4096
                for i in range(pages):
                    start = map.links.start + i * 4096
                    data = space.zread(start, 4096)
                    for match in guid_re2.finditer(data):
                        event = obj.Object("String", offset = start + match.start() + 40 + 40, vm = space, length = 128)
                        yield proc, "", event
                        
    def render_text(self, outfd, data):

        for proc, description, event in data:       
    
            if proc == None:
                tp = "Local Calendar Item"
                source = "Kernel Memory"
            else:
                tp = "Other"
                source = "Process {0} (PID {1})".format(proc.p_comm, proc.p_pid)

            outfd.write("Source: {0}\n".format(source))
            outfd.write("Type: {0}\n".format(tp))
            outfd.write("Description: {0}\n".format(description or "<No description>"))
            outfd.write("Event: {0}\n".format(event))
            outfd.write("Status: ACCEPTED\n\n") 