#! /usr/bin/python
from datetime import timedelta
import sys, time


def getuptime():
	with open('/proc/uptime', 'r') as f:
		up_seconds = float(f.readline().split()[0])
	up_string = str(timedelta(seconds=up_seconds))
	return up_seconds, up_string


logfile12 = '/home/pi/watchdog/repair.log'  # delete
logfile = '/home/pi/watchdog/watchdog.log'

code = sys.argv[1]

ups, upstr = getuptime()

if ups < 600:
	# for now 10 minutes to allow fixing things if my watchdog fails
	with open(logfile, 'a', 0) as f:
		f.write(time.strftime('%a %d %b %Y %H:%M:%S ') + '***** Ignoring code: ' + str(code) + ' uptime: ' + upstr + '\n')
	sys.exit(0)
else:
	with open(logfile, 'a', 0) as f:
		f.write(time.strftime('%a %d %b %Y %H:%M:%S ') + '***** Watchdog saw hang: ' + str(code) + ' uptime: ' + upstr + '\n')
	sys.exit(int(code))






