#!/usr/bin/python3

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

import pymysql as mdb
from math import sqrt
from PIL import Image, ImageDraw
from re import split as re_split

from weathermap_parser import WeathermapParser

K = 10**3
M = 10**6
G = 10**9
T = 10**12


def atoi(text):
    return int(text) if text.isdigit() else text


def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [ atoi(c) for c in re_split(r'(\d+)', text[0]) ]


def process_nodes(con, config, weathermap):
    nodes = []

    with con:
        cur = con.cursor()
        cur.execute("select devices.hostname, devices.device_id from links join ports on ports.port_id=links.local_port_id join devices on devices.device_id=ports.device_id group by devices.hostname")
        devices = cur.fetchall()

        cur.execute("select remote_hostname from links group by remote_hostname")
        links = cur.fetchall()

        hostnames = set()

        name_filters = []
        if config.get('autoplace', 'filter'):
            name_filters = config.get('autoplace', 'filter').split()

        if config.get('autoplace', 'exclude'):
            name_excludes = config.get('autoplace', 'exclude').split()

        for name in devices + links:
            name = name[0]

            if name.startswith(tuple(name_filters)) and not name.startswith(tuple(name_excludes)):
                if not '.' in name:
                    hostnames.add(name + '.pscs.internal')
                hostnames.add(name.lower())
                print('Included host "%s"' % name)
            else:
                print('Excluded host "%s"' % name)

        # Turn devices into a lookup table for device ids
        devices = [ (n, i) for n, i in devices ]
        devices = dict(devices)


        for hostname_raw in hostnames:
            hostname = hostname_raw.lower()
            if not '.' in hostname:
                hostname = hostname + '.pscs.internal'

            icon = 'network-hub-generic'
            if "swt-z9000" in hostname:
                icon = 'network-switch-qsfp-128'
            elif "swt-s4810" in hostname:
                icon = 'network-switch-sfp-64'
            elif "swt-s4048" in hostname:
                icon = 'network-switch-sfp-64'
            elif "s60" in hostname:
                icon = 'network-switch-utp-64'
            elif "swt-55" in hostname:
                icon = 'network-switch-utp-64'
            elif "swt-56" in hostname:
                icon = 'network-switch-utp-64'
            elif "stack" in hostname:
                icon = 'network-switch-stack-64'
            elif "rtr" in hostname:
                icon = 'network-router-blue-64'
            elif hostname.startswith('hv'):
                icon = 'generic-2u-server'
            elif hostname.startswith('sn'):
                icon = 'generic-2u-SAN'

            if icon:
                nodes.append((hostname, icon))


    count_i = 0
    count_j = 0


    position_i = config.getint('autoplace', 'initial_i')
    position_j = config.getint('autoplace', 'initial_j')
    position_pattern = config.get('autoplace', 'pattern')
    position_spacing = config.getint('autoplace', 'spacing')
    position_wrap = config.getboolean('autoplace', 'wrap')
    position_limit = config.getint('autoplace', 'limit')
    name_pattern = config.get('autoplace', 'name')

    nodes.sort(key=natural_keys)

    for name, icon in nodes:
        name = name.replace(' ', '_')
        node = 'NODE %s' % name

        if config.getboolean('autoplace', 'enabled'):
            if node not in weathermap['NODES']:
                weathermap['NODES'][node] = dict()

        #icon = config.get('icons', 'rank%d' % rank)
        if node in weathermap['NODES']:
            if 'LABEL' not in weathermap['NODES'][node]:
                weathermap['NODES'][node]['LABEL'] = name_pattern % name.split('.', 1)[0]

            if 'ICON' not in weathermap['NODES'][node]:
                weathermap['NODES'][node]['ICON'] = "images/%s.png" % icon

            if 'INFOURL' not in weathermap['NODES'][node] and name in devices:
                weathermap['NODES'][node]['INFOURL'] = '/device/device=%d/' % devices[name]

            if 'POSITION' not in weathermap['NODES'][node]:
                if position_wrap and count_i * position_spacing > position_limit:
                    count_i = 0
                    count_j += 1
                count_i += 1
                weathermap['NODES'][node]['POSITION'] = position_pattern.format(i=position_i + position_spacing * count_i, j=position_j + position_spacing * count_j)

    return weathermap


def process_links(con, config, weathermap):
    if_count = {}
    if_max = {}
    primary_key = 0
    cur = con.cursor()
    img_debug = Image.new('RGBA', (1920, 1080), (0, 0, 0, 255))
    draw_debug = ImageDraw.Draw(img_debug)

    base_ifspeed = config.getint('links', 'base_ifspeed')

    cur.execute("""
        select links.remote_hostname, devices.hostname, links.local_port_id, ports.ifName, remote_port, ifSpeed, ifIndex, devices.device_id
        from links
        join ports on ports.port_id=links.local_port_id
        join devices on devices.device_id=ports.device_id
        where links.remote_hostname not like '%%.gridpp.rl.ac.uk'
            and links.remote_hostname not like '%%.fds.rl.ac.uk'
            and ifSpeed >= %s
            and ifName not like 'ManagementEthernet%%'
            and remote_port not like 'ManagementEthernet%%'
            and ifAlias not like '%%mgt%%'
            and ifAlias not like '%%man%%'
    """ % config.get('links', 'min_ifspeed'))
    rows = cur.fetchall()

    for row in rows:
        remote_hostname_raw, local_hostname_raw, local_port_id, local_port_name, remote_port, interface_speed, interface_index, device_id = row

        local_hostname = local_hostname_raw.replace(' ', '_').lower() or 'unknown'
        remote_hostname = remote_hostname_raw.replace(' ', '_').lower() or 'unknown'

        if not '.' in local_hostname:
             local_hostname = local_hostname + '.pscs.internal'

        if not '.' in remote_hostname:
             remote_hostname = remote_hostname + '.pscs.internal'

        if local_hostname == 'unknown' or remote_hostname == 'unknown' or remote_hostname == 'not_advertised':
            print("Skipping link '%s' -> '%s'" % (local_hostname, remote_hostname))
            continue


        if local_hostname == 'unknown':
            continue
        if remote_hostname == 'unknown':
            continue

        #writes all the lines to file
        names = remote_hostname + local_hostname
        #used to check if the link has already happend in reverse (from the other nodes perspective )
        names_reverse = local_hostname + remote_hostname

        else:
            if names not in if_count:
                if_count[names] = 1
            if_count[names] += 1
            if_max[names] = if_count[names]

            if 'NODE %s' % local_hostname in weathermap['NODES'] or 'NODE %s' % remote_hostname in weathermap['NODES']:
                link_name = "LINK %s-%s-%s" % (local_hostname, remote_hostname, primary_key)
                if link_name not in weathermap['LINKS']:
                    weathermap['LINKS'][link_name] = {}
                weathermap['LINKS'][link_name]['WIDTH'] = "%d" % round(max(1, interface_speed / base_ifspeed))
                weathermap['LINKS'][link_name]['BANDWIDTH'] = "%dG" % (interface_speed / G)
                weathermap['LINKS'][link_name]['OVERLIBGRAPH'] = "/graph.php?height=200&width=512&id=%s&type=port_bits&legend=yes" % local_port_id
                weathermap['LINKS'][link_name]['OVERLIBCAPTION'] = "%dGbps link from [%s] (%s) to [%s] (%s)" % (interface_speed / G, local_hostname, local_port_name, remote_hostname, remote_port)
                weathermap['LINKS'][link_name]['INFOURL'] = "/device/device=%s/tab=port/port=%s/" % (device_id, local_port_id)
                weathermap['LINKS'][link_name]['TARGET'] = "/data/librenms/rrd/%s/port-id%s.rrd:INOCTETS:OUTOCTETS" % (local_hostname_raw, local_port_id)

                weathermap['LINKS'][link_name]['NODES'] = "%s %s" % (local_hostname.replace(' ', '_'), remote_hostname.replace(' ', '_'))

            #The primary key is used in the LINK line to stop links from being deleted as they had the same name
            #As some nodes will have 2 links connecting them

            primary_key = primary_key +1

    # Post process link offsets
    print()
    print('Processing Link Offsets')
    print('=======================')
    print()
    for link_name, link in weathermap['LINKS'].items():
        if 'NODES' not in link:
            continue
        try:
            node1, node2 = link['NODES'].split()
        except ValueError:
            print('Unable to split link "%s"' % link['NODES'])
            continue
        width = 2
        if 'WIDTH' in link:
            width = int(link['WIDTH'])
        names = node2 + node1
        #print(node1, node2)

        xd, yd = 0, 0
        xt, yt = 0, 0
        try:
            x1, y1 = weathermap['NODES']['NODE %s' % node1]['POSITION'].split()
            x2, y2 = weathermap['NODES']['NODE %s' % node2]['POSITION'].split()

            x1, y1 = int(x1), int(y1)
            x2, y2 = int(x2), int(y2)

            # origin
            draw_debug.ellipse((x1-2, y1-2, x1+2, y1+2), (255,0,0,255))

            # target
            draw_debug.ellipse((x2-2, y2-2, x2+2, y2+2), (0,255,0,255))

            # midpoint
            xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
            draw_debug.ellipse((xm-2, ym-2, xm+2, ym+2), (200,200,200,255))

            # direct route
            draw_debug.line((x1, y1, xm, ym), (150,50,50,255))
            draw_debug.line((xm, ym, x2, y2), (50,150,50,255))

            # delta and length
            xd, yd = abs(x1 - x2), abs(y1 - y2)
            length = sqrt(xd**2 + yd**2)

            # tangent
            xt, yt = (y1 - y2) / length, (x1 - x2) / -length

            # tangent from mid-point
            draw_debug.line((xm, ym, xm + xt * 50, ym + yt * 50), (100,0,0,255))
            draw_debug.line((xm, ym, xm - xt * 50, ym - yt * 50), (50,0,0,255))
            draw_debug.text((xm+4, ym+12), "%.2f" % length, fill=(0,250,250,255))
        except KeyError:
            pass

        try:
            if if_count[names] > 1 and (xd > 0 or yd > 0):
                spacing = max(8, width * 4)

                # initial (max) offsets
                xo = xt * if_max[names] * spacing
                yo = yt * if_max[names] * spacing

                # stepped offsets
                xo += -xt * if_count[names] * spacing
                yo += -yt * if_count[names] * spacing

                # via coordinates
                xv = int(xm + xo)
                yv = int(ym + yo)

                # origin to via
                draw_debug.line((x1, y1, xv, yv), (200,100,0,255))

                # via to target
                draw_debug.line((xv, yv, x2, y2), (100,200,0,255))

                # via
                draw_debug.text((xv+4, yv+4), str(spacing), fill=(250,250,0,255))
                draw_debug.ellipse((xv-2, yv-2, xv+2, yv+2), (150,150,0,255))
                img_debug.putpixel((xv, yv), (255, 255, 0, 255))

                weathermap['LINKS'][link_name]['VIA'] = "%d %d" % (xm + xo, ym + yo)
                #weathermap['LINKS'][link_name]['NODES'] = "%s:%d:%d %s:%d:%d" % (node2, xo, yo, node1, xo, yo)
                if_count[names] -= 1
                print(if_count[names])
        except KeyError:
            pass

    img_debug.save("/tmp/links_%s.png" % config.get('weathermap', 'name'), "PNG")

    return weathermap


def main(config):
    """
    Produce a .conf file that holds the necessary headings/nodes/links

    The node positions are currently decided by their name any changes to or new node names will result in the nodes being missed
    The link thickness (representing the connection speed) only represents 40GB or 1Gb
    To use this take the ConfigFile that produces and overwrite the existing configfile in /data/librenms/html/weathermap/configs

    Uses information retrieved by lldp protocol stored in the librenms database

    If any naming conventions are changed or new nodes want to be displayed there are 3 things that need updating
    1) SQL search on line 122 modify the where statements (currently anything with swt or rtr-x in its name is included but anything with note[swt and then 7 then t is excluded].
    2) from line 148 will decide where the node is placed on the bottom row. 3) SQL search on line 258 modify the where statements (currently links a combination of with swt or rtr in the name is selected)
    """

    # Connect to the librenms database
    con = mdb.connect(
        config.get('database', 'hostname'),
        config.get('database', 'username'),
        config.get('database', 'password'),
        config.get('database', 'schema'),
    )


    parser = WeathermapParser()

    weathermap = parser.load(config.get('weathermap', 'header'))

    weathermap['GLOBALS']['HTMLOUTPUTFILE'] = 'output/%s.html' % config.get('weathermap', 'name')
    weathermap['GLOBALS']['IMAGEOUTPUTFILE'] = 'output/%s.png' % config.get('weathermap', 'name')
    weathermap['GLOBALS']['TITLE'] = config.get('weathermap', 'title')

    with con:
        if config.getboolean('weathermap', 'links'):
            weathermap = process_links(con, config, weathermap)
        weathermap = process_nodes(con, config, weathermap)

    # Write output to file
    with open(config.get('weathermap', 'filename'), 'w') as output_file:
        output_file.write(parser.dump(weathermap))
        output_file.close()

if __name__ == "__main__":
    from configparser import SafeConfigParser
    CONFIG = SafeConfigParser()
    CONFIG.readfp(open('makeweathermap.defaults'))
    CONFIG.read(['makeweathermap.cfg'])
    main(CONFIG)
