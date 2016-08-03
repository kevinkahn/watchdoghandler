import pyping
import os
import time
from datetime import timedelta

def updatestateandfilestamp(ns,rs):
	global netstate, recoverystate, statusfile
	with open(statusfile,'w',0) as f:
		f.writelines(ns)
		f.writelines(rs)
	netstate = ns
	recoverystate = rs

def touch():
	with open(statusfile,'a'):
		os.utime(statusfile, None)

def logit(msg):
	global logfile, netstate, recoverystate
	with open(logfile,'a',0) as f:
		f.write(time.strftime('%a %d %b %Y %H:%M:%S ')+msg+' '+netstate+' '+recoverystate+'\n')

def getuptime():
	with open('/proc/uptime', 'r') as f:
		up_seconds = float(f.readline().split()[0])
	up_string = str(timedelta(seconds=uptime_seconds))
	return up_seconds, up_string

router = '192.168.1.1'
google = '8.8.8.8'
statusfile = '/home/pi/watchdog/lastcheck'
logfile = '/home/pi/watchdog/watchdog.log'

uptimebeforechecks = 10 # seconds to wait after reboot for pi network to stabilize

basecycletime = 5 # seconds to sleep per cycle
glitchtime = 5 # seconds to wait for net to spontaneously fix itself
modemtimelimit = 4 * 60  # this times basecycletime is how long to wait for modem to come up
routertimelimit = 2 * 60  # this times basecycletime is how long to wait for router to come up
ISPtimelimit = 60 * 60 # delay when it looks like ISP outage

modemcount = 0
routercount = 0
ISPcount = 0

# on startup get the status from the previous run/boot cycle or initialize if missing

if os.path.isfile(statusfile):
	with open(statusfile, 'r', 0) as g:
		netstate = g.readline()
		recoverystate = g.readline()
else:
	updatestateandfilestamp('unknown','watching')

logit("Startup")
logit("Up: "+getuptime()[1])

while True:
	# should set a reasonably short t/o on these to avoid setting the cycle too far off
	inetup = pyping.ping(google)
	routerup = pyping.ping(router)

	uptime_seconds, uptime_string = getuptime()

	if uptime_seconds < uptimebeforechecks:
		# system probably hasn't actually gotten the net up yet
		logit('Waiting on minumum uptime: ' + uptime_string)
		os.utime(statusfile,None)
		time.sleep(1)
		continue

	if inetup.ret_code == 0:
		# All is well
		if netstate <> 'netup':
			# just came up so log it
			logit('Network is up - was: ' + netstate + '/' + recoverystate + 'modemcnt: ' + str(modemcount) + 'routercnt: ' + str(routercount))
		updatestateandfilestamp('netup','watching')

	elif routerup.ret_code == 0:
		# net down router up - modem down or ISP down
		if recoverystate == 'rebootingmodem':
			# already started the reboot so just count cycles - do need to write watched file though
			modemcount += basecycletime
			touch()
			logit('Waiting on modem: '+str(modemcount))
			if modemcount > modemtimelimit:
				logit('Probably ISP outage ')
				ISPcount = 0
				updatestateandfilestamp('onlylocal','ISPoutage')
		elif recoverystate == 'ISPoutage':
			ISPcount += basecycletime
			touch()
			if ISPcount > ISPtimelimit:
				updatestateandfilestamp('onlylocal','TotalReset')
				logit('Long ISP outage - trying a total reset')
				# power cycle modem and router and Pi todo
				print "Reboot all - ISP"
				# exit??
		else:
			# not already doing anything about the outage - reboot modem (should we wait a cycle or 2?
			# update file to local, restartingmodem
			updatestateandfilestamp('onlylocal','rebootingmodem')
			modemcount = 0
			logit('Start modem reboot')
			print "Reboot modem"

			# cycle the power on modem todo
	else:
		# No router response and can't tell about modem of course
		if recoverystate == 'watching':
			# reboot the pi - do this here with a sys reboot call or let watchdog do it?
			# set recoverystate to "rebootedpi" so we know after restart todo
			print "Reboot pi"
		elif recoverystate == 'rebootedpi':
			# just rebooted pi but didn't get the network so reboot the router
			updatestateandfilestamp('nonet', 'rebootingrouter')
			routercount = 0
			logit('Start router reboot')

			print "Reboot router"

			#cycle the power todo

		elif recoverystate == 'rebootingrouter':
			# have started the modem reboot so wait on that
			routercount += basecycletime
			updatestateandfilestamp('nonet','rebootingrouter')
			logit("Waiting on router " + str(routercount))

			# if routercount get too high?
			#  routercount should get us about 90 seconds
			# wait 10 minutes and then cycle everything modem then router then pi
		else:
			# huh?  or perhaps check for initial?
			pass

	# sleep awaiting events
	time.sleep(basecycletime)




