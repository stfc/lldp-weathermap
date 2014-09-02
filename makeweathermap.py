#!/usr/bin/python

import MySQLdb as mdb

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
    placer_list = []
    name = []
    if_gone = []
    if_gone_reverse = []
    check = 0
    primary_key = 0

    count = [0]*8

    # Connects to the observium database

    con = mdb.connect(
        config.get('database', 'hostname'),
        config.get('database', 'username'),
        config.get('database', 'password'),
        config.get('database', 'schema'),
    )

    file0 = open(config.get('weathermap', 'filename'), 'w')

    header = open('header.txt').read()

    #Writesthe header of the config file
    file0.write(header)

    with con:
        cur = con.cursor()
        cur.execute("select hostname, ifSpeed from devices join ports on devices.device_id = ports.device_id where (hostname like ('swt%') and hostname not like ('swt%7%t%') ) or (hostname like ('%rtr-x%')) group by hostname")
        rows = cur.fetchall()

        for row in rows:
            row = str(row)

            compos = row.find(",")
            dotpos   = row.find(".")

            #removes the .pcs... at the end of name if present
            if dotpos > 1:
                hostname = (row[2:dotpos])
            else:
                hostname = (row[2:compos-1])

            speed = row[compos+2:len(row)-2]

            #Finds an identifiable part of any switch the is worth watching
            #To make spacing even between nodes they are assigned row so the number in each can be counted

            #The placer_list holds a value which coresponds to which row the node should be placed
            #No_ is used to count the ammount of nodes in a row

            if "swt-z9000" in hostname:
                name.append(hostname)
                placer_list.append(1)
                count[1] = count[1] +1

            #This is for the current switches with a 40Gb link
            elif "swt-s4810" in hostname and speed == "10000000000":
                name.append(hostname)
                placer_list.append(2)
                count[2] = count[2]+1

            elif "swt-s4810" in hostname:
                name.append(hostname)
                placer_list.append(3)
                count[3] = count[3]+1

            elif "s60" in hostname:
                name.append(hostname)
                placer_list.append(5)
                count[5] = count[5]+1

            elif "swt-5" in hostname:
                name.append(hostname)
                placer_list.append(6)
                count[6] = count[6]+1

            elif "rtr" in hostname:
                name.append(hostname)
                placer_list.append(7)
                count[7] = count[7] +1

            else :
                name.append(hostname)
                placer_list.append(4)
                count[4] = count[4]+1


    #Works out how many pixels to put between each node on a row
    spacing = [0]*len(count)
    for i, v in enumerate(count):
        spacing[i] = 1800/(v+1)
        count[i] = float(0.5)

    #This writes all the infomation for NODES to the confing file
    #The str(int( is used as decimals in the config file will stop the nodes being placed

    for current in range(0, len(name)):
        file0.write("NODE " + str(name[current]) + "\n")
        file0.write("    LABEL " + str(name[current]) +"\n")

        rank = placer_list[current]
        icon = config.get('icons', 'rank%d' % rank)

        file0.write("    ICON images/%s.png\n" % icon)
        file0.write("    POSITION " + str(int(spacing[rank] * count[rank])) + " %s\n" % config.get('offsets', 'rank%d' % rank))
        count[rank] = count[rank] + 1

        file0.write("\n")

    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    #This part deals with the links

    with con:
        cur = con.cursor()

        cur.execute("select links.remote_hostname, devices.hostname, links.local_port_id, ifSpeed, ifIndex, devices.device_id,port_id from links join ports on ports.port_id=links.local_port_id join devices on devices.device_id=ports.device_id where (remote_hostname like ('%swt%') and hostname like ('%swt%')) or (hostname like ('%rtr%') and (remote_hostname like ('%swt%') or remote_hostname like ('%rtr%')))")
        rows = cur.fetchall()

        for row in rows:
            remote_hostname_raw, local_hostname_raw, graph_number, interface_speed, interface_index, device_id, port_id = row

            local_hostname = local_hostname_raw.split('.', 1)[0]
            remote_hostname = remote_hostname_raw.split('.', 1)[0]

            #writes all the lines to file
            names = remote_hostname + local_hostname
            #used to check if the link has already happend in reverse (from the other nodes perspective )
            names_reverse = local_hostname + remote_hostname


            if names in if_gone_reverse:
                check = check +1 # seeing what is rejected (no effect on anything)

            else :
                file0.write("LINK " + remote_hostname + "-" + local_hostname + "-" + str(primary_key) +  "\n")
                file0.write("    WIDTH %d\n" % (interface_speed / 10000000000))
                file0.write("    BANDWIDTH %dG\n" % (interface_speed / 1000000000))
                file0.write("    OVERLIBGRAPH /graph.php?height=100&width=512&id=" + str(graph_number) + "&type=port_bits&legend=no \n")
                file0.write("    INFOURL /device/device=" + str(device_id) + "/tab=port/port=" + str(graph_number) + "/\n")
                file0.write("    TARGET /opt/observium/rrd/" + local_hostname_raw + "/port-" + str(interface_index) + ".rrd:INOCTETS:OUTOCTETS\n")
                if names in if_gone:
                    file0.write("    NODES " + local_hostname + ":10:10 " + remote_hostname + ":10:10\n")
                else:
                    file0.write("    NODES " + local_hostname + ":-10:-10 " + remote_hostname + ":-10:-10\n")
                file0.write("\n")

                #The primary key is used in the LINK line to stop links from being deleted as they had the same name
                #As some nodes will have 2 links connecting them

                primary_key = primary_key +1
                if_gone.append(names)
                if_gone_reverse.append(names_reverse)

    file0.close()

if __name__ == "__main__":
    from ConfigParser import SafeConfigParser
    CONFIG = SafeConfigParser()
    CONFIG.readfp(open('makeweathermap.defaults'))
    CONFIG.read(['makeweathermap.cfg'])
    main(CONFIG)
