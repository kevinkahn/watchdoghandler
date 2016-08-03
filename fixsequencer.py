#!/usr/bin/python

from datetime import timedelta
import sys
import syslog
import pyping


"""
if uptime < startupt: ignore and return 0

if counter < tryntimes: incr counter and return 0
file with time of last call to repair
 if now within 2 sec of last call ?

 maybe use the test call to set a time?
compute interval from last good ping
get uptime
if uptime less than 30 sec and
"""

syslog.syslog(''.join(str(e) for e in sys.argv))
syslog.syslog('Watchdog error ' + str(sys.argv[1]))

with open('/proc/uptime', 'r') as f:
    uptime_seconds = float(f.readline().split()[0])
    uptime_string = str(timedelta(seconds = uptime_seconds))
syslog.syslog("fixseq")
syslog.syslog(uptime_string)
print(uptime_string)
sys.exit(0)
