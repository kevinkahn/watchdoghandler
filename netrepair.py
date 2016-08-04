import pyping
import os
import time
from datetime import timedelta


def updatestateandfilestamp(state):
	global recoverystate, statusfile
	with open(statusfile,'w',0) as f:
		f.write(state)
	logit('Recovery state changed - was: ' + recoverystate + ' now: ' + state)
	recoverystate = state



def touch():
	with open(statusfile,'a'):
		os.utime(statusfile, None)

def logit(msg):
	global logfile, netstate, recoverystate
	with open(logfile,'a',0) as f:
		f.write(time.strftime('%a %d %b %Y %H:%M:%S ') + msg + ' (' + recoverystate + ')\n')

def getuptime():
	with open('/proc/uptime', 'r') as f:
		up_seconds = float(f.readline().split()[0])
	up_string = str(timedelta(seconds=up_seconds))
	return up_seconds, up_string

router = '192.168.1.1'
google = '8.8.8.8'
# google = '192.168.3.3'
statusfile = '/home/pi/watchdog/lastcheck'
logfile = '/home/pi/watchdog/watchdog.log'

uptimebeforechecks = 10 # seconds to wait after reboot for pi network to stabilize

basecycletime = 30  # seconds to sleep per cycle
glitchtime = 60  # seconds to wait for net to spontaneously fix itself
modemtimelimit = 4 * 60  # this times basecycletime is how long to wait for modem to come up
routertimelimit = 2 * 60  # this times basecycletime is how long to wait for router to come up
ISPtimelimit = 60 * 60 # delay when it looks like ISP outage

modemcount = 0
routercount = 0
ISPcount = 0

recoverystate = '-------'
logit("Startup")

# on startup get the status from the previous run/boot cycle or initialize if missing

if os.path.isfile(statusfile):
	with open(statusfile, 'r', 0) as g:
		recoverystate = g.readline()
else:
	updatestateandfilestamp('unknown')


logit("Up: "+getuptime()[1])

while True:
	# should set a reasonably short t/o on these to avoid setting the cycle too far off
	cyclestart = time.time()
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
		if recoverystate <> 'watching':
			# just came up so log it
			logit('Network is up - was: ' + recoverystate + ' modemcnt: ' + str(modemcount) + ' routercnt: ' + str(
				routercount))
			updatestateandfilestamp('watching')
		else:
			touch()
		netlastseen = cyclestart  # note last seen ok time to allow for glitches

	elif (routerup.ret_code == 0) and (cyclestart > netlastseen + glitchtime):
		# net down router up - modem down or ISP down
		if recoverystate == 'rebootingmodem':
			# already started the reboot so just count cycles - do need to write watched file though
			modemcount += basecycletime
			touch()
			logit('Waiting on modem: '+str(modemcount))
			if modemcount > modemtimelimit:
				logit('Probable ISP outage ')
				ISPcount = 0
				updatestateandfilestamp('ISPoutage')
		elif recoverystate == 'ISPoutage':
			ISPcount += basecycletime
			touch()
			if ISPcount > ISPtimelimit:
				updatestateandfilestamp('TotalReset')
				logit('Long ISP outage - trying a total reset')
				# power cycle modem and router and Pi todo
				print "Reboot all - ISP"
				# exit??
		else:
			# not already doing anything about the outage - reboot modem (should we wait a cycle or 2?
			updatestateandfilestamp('rebootingmodem')
			modemcount = 0
			logit('Start modem reboot')
			print "Reboot modem"

			# cycle the power on modem todo
	elif cyclestart > netlastseen + glitchtime:  # allow for short net outages
		# No router response and can't tell about modem of course
		# Could reboot router first but Pi is more likely to have failed to try it first
		if recoverystate == 'watching':
			updatestateandfilestamp('rebootedpi')  # set recoverystate to "rebootedpi" so we know after restart
			print "Reboot pi"
		# todo reboot the pi end exit this program so the watchdog goes off if the reboot doesn't happen
		elif recoverystate == 'rebootedpi':
			# just rebooted pi but didn't get the network so reboot the router
			updatestateandfilestamp('rebootingrouter')
			routercount = 0
			logit('Start router reboot')

			print "Reboot router"

			#cycle the power todo

		elif recoverystate == 'rebootingrouter':
			# have started the modem reboot so wait on that
			routercount += basecycletime
			touch()
			logit("Waiting on router " + str(routercount))

			# if routercount get too high?
			#  routercount should get us about 90 seconds
			# wait 10 minutes and then cycle everything modem then router then pi
		else:
			logit('Unknown state error: ' + recoverystate)  # huh?  or perhaps check for initial?
		# reboot system - something seriously wrong todo

	else:
		logit("Net lost - outage time: " + str(cyclestart - netlastseen))
		touch()

	# sleep awaiting events
	cycleend = time.time()
	time.sleep(basecycletime - (cycleend - cyclestart))
