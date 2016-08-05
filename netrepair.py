import os
import sys
import time
from datetime import timedelta

import RPi.GPIO as GPIO
import pyping


class device(object):
	def __init__(self, n, port, dt):
		self.pin = port
		self.resettime = time.time()  # initialize to current time to handle case where a reset op was in progress
		self.name = n
		self.delaytime = dt
		if self.pin <> 0:
			GPIO.setup(port, GPIO.OUT, initial=0)

	def reset(self):
		self.resettime = time.time()
		logit('Reset: ' + self.name + ' at ' + str(self.resettime))
		if self.pin <> 0:
			GPIO.output(self.pin, 1)
			time.sleep(5)
			GPIO.output(self.pin, 0)

	def waitforit(self):
		return self.resettime + self.delaytime > time.time()

	# this is safe against time jumping forward as it does late in boot
	# just won't wait as long as expected


def updatestateandfilestamp(state):
	global recoverystate, statusfile
	with open(statusfile,'w',0) as f:
		f.write(state)
	logit('Recovery state changed - was: ' + recoverystate + ' now: ' + state)
	recoverystate = state

def touch():
	with open(statusfile,'a'):
		os.utime(statusfile, None)


def logit(msg, lowfreq=False):
	global logfile, recoverystate, logskip, logskipstart
	if lowfreq:
		logskip += 1
		if logskip < logskipstart:
			return
		else:
			logskip = 0
	with open(logfile,'a',0) as f:
		f.write(time.strftime('%a %d %b %Y %H:%M:%S ') + msg + ' (' + recoverystate + ')\n')

def getuptime():
	with open('/proc/uptime', 'r') as f:
		up_seconds = float(f.readline().split()[0])
	up_string = str(timedelta(seconds=up_seconds))
	return up_seconds, up_string


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.cleanup()

routerIP = '192.168.1.1'
googleIP = '8.8.8.8'

modem = device('modem', 4, 1*60)
router = device('router', 17, 4*60)
ISP = device('ISP', 0, 60*60)

logskip = 0
logskipstart = 10

# google = '192.168.3.3'
statusfile = '/home/pi/watchdog/lastcheck'
logfile = '/home/pi/watchdog/watchdog.log'

uptimebeforechecks = 10 # seconds to wait after reboot for pi network to stabilize

basecycletime = 30  # seconds to sleep per cycle

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
	cyclestart = time.time()
	inetup = pyping.ping(googleIP, timeout=100, count=2)
	routerup = pyping.ping(routerIP)
	print cyclestart, inetup.ret_code, routerup.ret_code
	# print inetup.avg_rtt, routerup.avg_rtt
	uptime_seconds, uptime_string = getuptime()

	if uptime_seconds < uptimebeforechecks:
		# Pi probably hasn't actually gotten the net up yet
		logit('Waiting on minumum uptime: ' + uptime_string)
		os.utime(statusfile,None)
		time.sleep(1)
		continue

	if inetup.ret_code == 0:
		# All is well - clear any reset in progress and just get back to watching
		if recoverystate <> 'watching':
			# just came up so log it
			logit('Network is up - was: ' + recoverystate)
			updatestateandfilestamp('watching')
		else:
			touch()
			logit('Network ok', lowfreq=True)
		netlastseen = cyclestart  # note last seen ok time to allow for glitches

	elif recoverystate == 'ISPfullreset1':
		# doing a full reset so wait on modem time to reset then do modem reset
		touch()
		if modem.waitforit():
			pass
		else:
			# waited long enough for modem to reset now try router
			recoverystate = 'ISPfullreset2'
			router.reset()
	elif recoverystate == 'ISPfullreset2':
		# rebooting the router during a full reset
		touch()
		if router.waitforit():
			pass
		else:
			# modem and router now cycled and net still out so assume ISP down
			logit('Full reset failed to restore network')
			ISP.reset()
			updatestateandfilestamp('ISPoutage')  # todo at some point should we reboot the Pi?

	elif routerup.ret_code == 0:
		# net down router up - modem down or ISP down
		if recoverystate == 'rebootingmodem':
			# already started the reboot so just wait for that to finish
			touch()
			if modem.waitforit():
				logit('Waiting on modem: ')
			else:
				logit('Probable ISP outage ')
				ISP.reset()
				updatestateandfilestamp('ISPoutage')
		elif recoverystate == 'ISPoutage':
			# long wait for ISP to come back before trying a modem/router reset
			touch()
			if ISP.waitforit():
				logit('ISP out', lowfreq=True)
			else:
				updatestateandfilestamp('ISPfullreset1')
				logit('Long ISP outage - reset modem again')
				modem.reset()
				print "ISP outage modem/router reset"
		elif recoverystate == 'startmodemreboot':
			# last time through net was also down so - reboot modem (should we wait a cycle or 2?
			updatestateandfilestamp('rebootingmodem')
			modem.reset()
			logit('Start modem reboot')
			print "Reboot modem"
		elif recoverystate == 'watching':
			# plan to do modem reboot if still down next cycle
			updatestateandfilestamp('startmodemreboot')
		else:
			logit('Unknown state error 1: ' + recoverystate)  # huh?  or perhaps check for initial?
			updatestateandfilestamp('unknown')
			print "Reboot pi"
			# subprocess.call('sudo reboot now', shell=True)
			time.sleep(5)
			sys.exit(2)


	else:
		# no local ping response
		if recoverystate == 'rebootedpi':
			# just rebooted pi but didn't get the network so reboot the router
			updatestateandfilestamp('rebootingrouter')
			logit('Start router reboot')
			print "Reboot router"
			router.reset()
		elif recoverystate == 'rebootingrouter':
			# have started the modem reboot so wait on that
			touch()
			if router.waitforit():
				logit("Waiting on router ")
			else:
				updatestateandfilestamp('FullResetStart')
			# todo if routercount get too high?
			# wait 10 minutes and then cycle everything modem then router then pi
		elif recoverystate == 'watching':
			# net was fine a moment ago to pend action for next cycle
			updatestateandfilestamp('picommsunknown')
		elif recoverystate == 'picommsunknown':
			# comms were down last cycle so start the reboots
			# Could reboot router first but Pi is more likely to have failed to try it first
			updatestateandfilestamp('rebootedpi')  # set recoverystate to "rebootedpi" so we know after restart
			print "Reboot pi"
			# subprocess.call('sudo reboot now', shell=True)
			time.sleep(5)
			sys.exit(1)

		else:
			logit('Unknown state error 2: ' + recoverystate)  # huh?  or perhaps check for initial?
			updatestateandfilestamp('unknown')
			print "Reboot pi"
			# subprocess.call('sudo reboot now', shell=True)
			time.sleep(5)
			sys.exit(3)

	# sleep awaiting events
	cycleend = time.time()
	time.sleep(basecycletime - (cycleend - cyclestart))
