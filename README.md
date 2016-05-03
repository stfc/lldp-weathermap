# LLDP Weathermap Link Manager

Use neighbour discovery information from your network devices to update links between nodes on a weathermap.
Designed for use with Observium or LibreNMS.

## Usage

Copy `makeweathermap.defaults` to `makeweathermap.cfg` and configure for your installation.

This tool will not generate a complete weathermap, it must be given a partial map to built upon.

In the `[weathermap]` section, `filename` should be set to the desired output file for use by PHP Weathermap, `header` should be set to a base weathermap file (perhaps generated with PHP Weathermap's inbuilt editor).

When you are happy with the behaviour, configure a cron job to run the script, ideally just before the weathermap poller is run. For example:

    */5 * * * *   poller    cd /opt/makeweathermap/ &&
    nice ./makeweathermap.py > /dev/null 2>&1 &&
    nice /opt/observium/html/weathermap/map-poller.php > /dev/null 2>&1
