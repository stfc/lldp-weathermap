#!/usr/bin/python

# Copyright 2014-2016 Science & Technology Facilities Council
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import MySQLdb as mdb

from weathermap_parser import WeathermapParser

K = 10**3
M = 10**6
G = 10**9
T = 10**12

def process_nodes(con, config, weathermap):
    nodes = []

    with con:
        cur = con.cursor()
        cur.execute("select devices.hostname, devices.device_id from links join ports on ports.port_id=links.local_port_id join devices on devices.device_id=ports.device_id group by devices.hostname")
        devices = cur.fetchall()

        cur.execute("select remote_hostname from links group by remote_hostname")
        links = cur.fetchall()

        hostnames = set()

        for name in devices + links:
            name = name[0]
            if name.startswith('swt') or name.startswith('rtr'):
                hostnames.add(name.split('.', 1)[0])

        # Turn devices into a lookup table for device ids
        devices = [ (n.split('.', 1)[0], i) for n, i in devices ]
        devices = dict(devices)

        for hostname in hostnames:
            hostname = hostname.split('.', 1)[0]

            #Finds an identifiable part of any switch the is worth watching
            #To make spacing even between nodes they are assigned row so the number in each can be counted

            #The placer_list holds a value which coresponds to which row the node should be placed
            #No_ is used to count the ammount of nodes in a row

            icon = 'network-hub-generic'
            if "swt-z9000" in hostname:
                icon = 'network-switch-qsfp-128'
            elif "swt-s4810" in hostname:
                icon = 'network-switch-sfp-96'
            elif "s60" in hostname:
                icon = 'network-switch-utp-96'
            elif "stack" in hostname:
                icon = 'network-switch-stack-64'
            elif "rtr" in hostname:
                icon = 'network-router-blue-64'

            if icon:
                nodes.append((hostname, icon))


    count = 0
    for name, icon in nodes:
        node = 'NODE %s' % name

        if node not in weathermap['NODES']:
            weathermap['NODES'][node] = dict()

        #icon = config.get('icons', 'rank%d' % rank)
        if 'LABEL' not in weathermap['NODES'][node]:
            weathermap['NODES'][node]['LABEL'] = '%s (auto placed)' % name.split('.', 1)[0]

        if 'ICON' not in weathermap['NODES'][node]:
            weathermap['NODES'][node]['ICON'] = "images/%s.png" % icon

        if 'INFOURL' not in weathermap['NODES'][node] and name in devices:
            weathermap['NODES'][node]['INFOURL'] = '/device/device=%d/' % devices[name]

        if 'POSITION' not in weathermap['NODES'][node]:
            count += 1
            weathermap['NODES'][node]['POSITION'] = "%s %s" % (1800, 50 * count)

    return weathermap


def process_links(con, config, weathermap):
    if_gone = []
    if_gone_reverse = []
    check = 0
    primary_key = 0
    cur = con.cursor()

    cur.execute("""
        select links.remote_hostname, devices.hostname, links.local_port_id, ports.ifName, remote_port, ifSpeed, ifIndex, devices.device_id
        from links join ports on ports.port_id=links.local_port_id join devices on devices.device_id=ports.device_id
        where links.remote_hostname not like '%%.gridpp.rl.ac.uk' and links.remote_hostname not like '%%.fds.rl.ac.uk' and ifSpeed > %s and ifName not like 'ManagementEthernet%%'
    """, M)
    rows = cur.fetchall()

    for row in rows:
        remote_hostname_raw, local_hostname_raw, graph_number, local_port, remote_port, interface_speed, interface_index, device_id = row

        local_hostname = local_hostname_raw.split('.', 1)[0] or 'unknown'
        remote_hostname = remote_hostname_raw.split('.', 1)[0] or 'unknown'

        if local_hostname == 'unknown':
            continue
        if remote_hostname == 'unknown':
            continue

        #writes all the lines to file
        names = remote_hostname + local_hostname
        #used to check if the link has already happend in reverse (from the other nodes perspective )
        names_reverse = local_hostname + remote_hostname


        if names in if_gone_reverse:
            check = check +1 # seeing what is rejected (no effect on anything)

        else:
            if 'NODE %s' % local_hostname in weathermap['NODES'] or 'NODE %s' % remote_hostname in weathermap['NODES']:
                link_name = "LINK %s-%s-%s" % (local_hostname, remote_hostname, primary_key)
                if link_name not in weathermap['LINKS']:
                    weathermap['LINKS'][link_name] = {}
                weathermap['LINKS'][link_name]['WIDTH'] = "%d" % (max(1, interface_speed / (10 * G)))
                weathermap['LINKS'][link_name]['BANDWIDTH'] = "%dG" % (interface_speed / G)
                weathermap['LINKS'][link_name]['OVERLIBGRAPH'] = "/graph.php?height=200&width=512&id=%s&type=port_bits&legend=yes" % graph_number
                weathermap['LINKS'][link_name]['OVERLIBCAPTION'] = "%dGbps link from [%s] (%s) to [%s] (%s)" % (interface_speed / G, local_hostname, local_port, remote_hostname, remote_port)
                weathermap['LINKS'][link_name]['INFOURL'] = "/device/device=%s/tab=port/port=%s/" % (device_id, graph_number)
                weathermap['LINKS'][link_name]['TARGET'] = "/opt/observium/rrd/%s/port-%s.rrd:INOCTETS:OUTOCTETS" % (local_hostname_raw, interface_index)
                if names in if_gone:
                    weathermap['LINKS'][link_name]['NODES'] = "" + local_hostname + ":10:10 " + remote_hostname + ":10:10"
                else:
                    weathermap['LINKS'][link_name]['NODES'] = "" + local_hostname + ":-10:-10 " + remote_hostname + ":-10:-10"

            #The primary key is used in the LINK line to stop links from being deleted as they had the same name
            #As some nodes will have 2 links connecting them

            primary_key = primary_key +1
            if_gone.append(names)
            if_gone_reverse.append(names_reverse)

    return weathermap


def main(config):
    """
    Produce a .conf file that holds the necessary headings/nodes/links

    The node positions are currently decided by their name any changes to or new node names will result in the nodes being missed
    The link thickness (representing the connection speed) only represents 40GB or 1Gb

    To use this take the ConfigFile that produces and overwrite the existing configfile in /opt/observium/html/weathermap/configs

    Uses information retrieved by lldp protocol stored in the observium database

    If any naming conventions are changed or new nodes want to be displayed there are 3 things that need updating
    1) SQL search on line 122 modify the where statements (currently anything with swt or rtr-x in its name is included but anything with note[swt and then 7 then t is excluded].
    2) from line 148 will decide where the node is placed on the bottom row. 3) SQL search on line 258 modify the where statements (currently links a combination of with swt or rtr in the name is selected)
    """

    # Connect to the observium database
    con = mdb.connect(
        config.get('database', 'hostname'),
        config.get('database', 'username'),
        config.get('database', 'password'),
        config.get('database', 'schema'),
    )


    parser = WeathermapParser()

    weathermap = parser.load(config.get('weathermap', 'header'))

    with con:
        weathermap = process_links(con, config, weathermap)
        weathermap = process_nodes(con, config, weathermap)

    # Write output to file
    with open(config.get('weathermap', 'filename'), 'w') as output_file:
        output_file.write(parser.dump(weathermap))
        output_file.close()

if __name__ == "__main__":
    from ConfigParser import SafeConfigParser
    CONFIG = SafeConfigParser()
    CONFIG.readfp(open('makeweathermap.defaults'))
    CONFIG.read(['makeweathermap.cfg'])
    main(CONFIG)
