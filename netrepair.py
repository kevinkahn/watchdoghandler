#!/usr/bin/python
import os
import sys
import time
import requests
import subprocess
import yaml
from datetime import timedelta

# todo add some checks to the VPN?

import RPi.GPIO as GPIO
import pyping
badping = 0
totalping = 0



def RobustPing(dest):
	global totalping, badping
	ok = False
	# todo should make this a loop that tries until success or 10 failures
	for i in range(10):
		totalping = totalping + 1
		try:
			netup = pyping.ping(dest, timeout=5, count=1)
		except:
			logit('External Ping Exception')
			inetup.ret_code = 1 # just assume bad this loop
		if netup.ret_code == 0:
			ok = True # one success in loop is success
			break
		else:
			badping = badping + 1
			logit('Ping failure to:' + dest + ' ' + str(badping))
			#logit('Ping Failure to: ' + dest + ' ''+ str(netup.ret_code) + str(netup.output))
	return ok


def GetPrinterStatus():
	global APIkey
	hdr = {'X-Api-Key': APIkey}
	r = requests.get('http://127.0.0.1:5000/api/connection', headers=hdr)
	if r.status_code == 200:
		x = r.json()
		# print x['current']['state']  # returns Closed, Operational, Printing
		return x['current']['state']
	else:
		#	print "OctoPrint not responding"
		return "NoOctoPrint"


class Device(object):
	def __init__(self, n, port, dt):
		self.pin = port
		self.resettime = time.time()  # initialize to current time to handle case where a reset op was in progress
		self.name = n
		self.delaytime = dt
		if self.pin <> 0:
			GPIO.setup(port, GPIO.OUT, initial=0)

	def reset(self):
		self.resettime = time.time()
		if self.delaytime <> 0:
			logit('Reset: ' + self.name + ' at ' + str(self.resettime))
			if self.pin <> 0:
				GPIO.output(self.pin, 1)
				time.sleep(5)
				GPIO.output(self.pin, 0)
		else:
			# not controlling device
			logit("No reset, not controlling:" + self.name)


	def waitforit(self):
		if self.delaytime <> 0:
			return self.resettime + self.delaytime > time.time()
		else:
			# not controlling the device so never wait
			return False

	# this is safe against time jumping forward as it does late in boot
	# just won't wait as long as expected


def pireboot(msg, ecode):
	# cause the Pi to reboot - first gently, then violently, then via the hw timer
	global noaction, currentlyprinting, deferredPiReboot
	logit("REBOOT: "+msg)
	if currentlyprinting:
		deferredPiReboot = True
		logit('Defer reboot - printing')
		return

	updatestateandfilestamp('rebootedpi')
	if noaction:
		logit('Supressed reboot')
		# print 'Supressed reboot'
		return
	subprocess.call('sudo reboot now', shell=True)
	time.sleep(60)  # this should never finish
	# why are we still running - drastic measures called for
	logit("Violent reset " + msg)
	with open('/proc/sys/kernel/sysrq') as s:
		s.write('1')
	with open('/proc/sysrq-trigger') as s:
		s.write('b')
	logit("Post violent kill " + msg)
	#print "PiReboot: " + str(ecode)
	sys.exit(ecode)


# last try is the
#  time expiry


def updatestateandfilestamp(state):
	global recoverystate, statusfile
	with open(statusfile,'w',0) as f:
		f.write(state)
	logit('State change: ' + recoverystate + ' to: ' + state)
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
sys.stdout = open('/home/pi/watchdog/master.log', 'a', 0)
sys.stderr = open('/home/pi/watchdog/master.err', 'a', 0)
with open('/home/pi/watchdog/netwatch.yaml') as y:
	params = yaml.load(y)

p = params['pinghosts']
routerIP = p['localip']
externalIP = p['remoteip']

noaction = params['noaction']
basecycletime = params['cycletime']  # seconds
logskipstart = params['lowfreq']

p = params['modem']
modemctl = p['controlled']
if modemctl:
	modem = Device('modem', p['port'], p['bootwait']*60)
else:
	modem = Device('modemnull', 0, 0)

p = params['router']
routerctl = p['controlled']
if routerctl:
	router = Device('router', p['port'], p['bootwait']*60)
else:
	router = Device('routernull', 0, 0)

p = params['ISP']
ISP = Device('ISP', 0, p['ISPhours']*60*60)
outagebeforepireset = p['maxISPwait']*60*60

p = params['printer']
monitorprinter = p['controlled']
offafter = prport = proffcmd = 0
if monitorprinter:
	APIkey = p['key']
	offafter = p['offafter']*60
	prport = p['port']
	waitprinter = p['waitonreboot']
	prmaxwait = p['waitmaxhrs']*60*60
	proffcmd = p['offcmd']
	prforcedoff = False  # have never forced the printer power off - might be on but bot connected

statusfile = '/home/pi/watchdog/lastcheck'
logfile = '/home/pi/watchdog/watchdog.log'

uptimebeforechecks = 10 # seconds to wait after reboot for pi network to stabilize

logskip = 0
lastprinting = time.time()
deferredPiReboot = False  # prevents reboot while printer is active
currentlyprinting = False  # never want to defer if not controlling a printer

if monitorprinter:
	GPIO.setup(prport, GPIO.OUT, initial=proffcmd)

recoverystate = '-------'
logit("Startup")

# on startup get the status from the previous run/boot cycle or initialize if missing

if os.path.isfile(statusfile):
	with open(statusfile, 'r', 0) as g:
		recoverystate = g.readline()
else:
	updatestateandfilestamp('unknown')
netlastseen = 0

logit("Up: "+getuptime()[1])
time.sleep(5)  # not sure it's need but want system to get through most of the boot - there were some failures
while True:
	cyclestart = time.time()

	if monitorprinter:
		ps = GetPrinterStatus()
		if ps == 'Printing':
			lastprinting = cyclestart
			currentlyprinting = True
			prforcedoff = False  # make sure if it finishes but disconnects before we notice we still power off
		elif ps == 'Closed':
			currentlyprinting = False
			lastprinting = cyclestart  # fake recent printing - otherwise when turned on to operation it is immediately turned off
			# make sure power if off
			if not prforcedoff:
				logit("Power off printer from Closed")
				GPIO.output(prport, 1)
				prforcedoff = True
		elif ps == 'Operational':
			if cyclestart - lastprinting > offafter:
				# turn it off
				logit("Power off printer from Operational")
				GPIO.output(prport, 1)
				subprocess.call('//home/pi/scripts/webcam stop', shell=True)
			else:
				# not idle long enough to power off
				prforcedoff = False  # make sure if it disconnects for some reason we power it off eventually
		else:
			pass
			#logit('Unknown printer state: ' + ps)

	externalnetup = RobustPing(externalIP)
	localrouterup = RobustPing(routerIP)

	uptime_seconds, uptime_string = getuptime()

	if uptime_seconds < uptimebeforechecks:
		# Pi probably hasn't actually gotten the net up yet
		logit('Waiting minumum uptime: ' + uptime_string)
		os.utime(statusfile,None)
		time.sleep(1)
		continue

	if deferredPiReboot:
		if currentlyprinting:
			logit('Still deferring', lowfreq=True)
		else:
			# execute the deferred reboot
			pireboot('Printing ended reboot', 98)
	elif externalnetup:
		# All is well - clear any reset in progress and just get back to watching
		if recoverystate <> 'watching':
			# just came up so log it
			logit('Network up from: ' + recoverystate)
			updatestateandfilestamp('watching')
		else:
			touch()
			logit('Network ok, up: '+ getuptime()[1]+' '+str(badping)+'/'+str(totalping),lowfreq=True)
		netlastseen = cyclestart  # note last seen ok time

	elif recoverystate == 'ISPfullreset1':
		# doing a full reset so wait on modem time to reset then do modem reset
		touch()
		if modem.waitforit():
			pass
		else:
			# waited long enough for modem to reset now try router
			updatestateandfilestamp('ISPfullreset2')
			router.reset()
	elif recoverystate == 'ISPfullreset2':
		# rebooting the router during a full reset
		touch()
		if router.waitforit():
			pass
		else:
			# modem and router now cycled and net still out so assume ISP down
			logit('Full reset failed to restore')
			if time.time() > netlastseen + outagebeforepireset:
				# long enough to shoot the Pi and restart stuff
				pireboot("ISP outage limit", 99)
			else:
				# wait another ISP outage interval
				ISP.reset()
				updatestateandfilestamp('ISPoutage')

	elif localrouterup:
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
				logit('Long ISP outage - reset modem')
				modem.reset()
			#print "ISP outage modem/router reset"
		elif recoverystate == 'startmodemreboot':
			# last time through net was also down so - reboot modem (should we wait a cycle or 2?
			updatestateandfilestamp('rebootingmodem')
			modem.reset()
			logit('Start modem reboot')
		#print "Reboot modem"
		elif recoverystate == 'watching':
			# plan to do modem reboot if still down next cycle
			updatestateandfilestamp('startmodemreboot')
		elif recoverystate == "picommsunknown":
			# comms are really flakey - lost local then it came back but net out
			# best to do a reset
			pireboot("Wavering connections", 91)
		else:
			pireboot('Unknown state error 1: ' + recoverystate, 92)  # huh?  or perhaps check for initial?
	else:
		# no local ping response
		if recoverystate == 'rebootedpi':
			# just rebooted pi but didn't get the network so reboot the router
			updatestateandfilestamp('rebootingrouter')
			logit('Start router reboot')
			#print "Reboot router"
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
			pireboot('No local comms', 91)
		else:
			pireboot('Unknown state error 2: ' + recoverystate, 93)  # huh?  or perhaps check for initial?
	# sleep awaiting events
	cycleend = time.time()
	time.sleep(basecycletime - (cycleend - cyclestart))
