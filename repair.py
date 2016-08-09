#! /usr/bin/python
from datetime import timedelta
import sys, time


def getuptime():
	with open('/proc/uptime', 'r') as f:
		up_seconds = float(f.readline().split()[0])
	up_string = str(timedelta(seconds=up_seconds))
	return up_seconds, up_string


logfile = '/home/pi/watchdog/repair.log'

code = sys.argv[1]

ups, upstr = getuptime()

if ups < 60:
	with open(logfile, 'a', 0) as f:
		f.write(time.strftime('%a %d %b %Y %H:%M:%S ') + 'Ignoring code: ' + str(code) + ' uptime: ' + upstr + '\n')
	sys.exit(0)
else:
	with open(logfile, 'a', 0) as f:
		f.write(time.strftime('%a %d %b %Y %H:%M:%S ') + 'Acking hang code: ' + str(code) + ' uptime: ' + upstr + '\n')
	sys.exit(int(code))
