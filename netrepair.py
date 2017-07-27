#!/usr/bin/python
import os
import sys
import time
import requests
import subprocess
import yaml
import cgitb
from datetime import timedelta
from subprocess import call

# TODO add some checks to the VPN?

import RPi.GPIO as GPIO
badping = 0
totalping = 0
null = open('/dev/null','a')

def RobustPing(dest):
	global totalping, badping, null
	#print dest
	if dest[0] == '~': # for testing set destinations to ~L ~R
		if os.path.isfile(dest):
			logit("Simulate good ping of "+dest)
			return True
		else:
			logit("Simulate failed ping of "+dest)
			return False
	ok = False
	cmd = 'ping -c 1 -W 1 ' + dest
	# todo should make this a loop that tries until success or 10 failures
	for i in range(10):
		totalping = totalping + 1
		p = subprocess.call(cmd, shell=True, stdout=null, stderr=null)
		if p == 0:
			ok = True # one success in loop is success
			break
		else:
			badping = badping + 1
			logit('Ping failure to: ' + dest + ' ' + str(badping))
	return ok



def GetPrinterStatus():
	global APIkey
	hdr = {'X-Api-Key': APIkey}
	try:
		r = requests.get('http://127.0.0.1:5000/api/connection', headers=hdr)
		if r.status_code == 200:
			x = r.json()
			# print x['current']['state']  # returns Closed, Operational, Printing
			return x['current']['state']
		else:
			logit("OctoPrint non success code: "+ str(r.status_code))
			return "NoOctoPrint"
	except:
		logit("Octoprint didn't respond")
		return"NoOctoPrint comms"


class Device(object):
	def __init__(self, n, port, dt):
		self.pin = port
		self.resettime = time.time()  # initialize to current time to handle case where a reset op was in progress
		self.name = n
		self.delaytime = dt
		if self.pin <> 0:
			GPIO.setup(port, GPIO.OUT, initial=GPIO.HIGH)

	def reset(self):
		self.resettime = time.time()
		if self.delaytime <> 0:
			logit('Reset: ' + self.name + ' at ' + str(self.resettime))
			if self.pin <> 0:
				GPIO.output(self.pin, 0)
				time.sleep(5)
				GPIO.output(self.pin, 1)
		else:
			# not controlling device
			logit("No reset, not controlling:" + self.name)


	def waitforit(self):
		if self.delaytime <> 0:
			logit('Waiting on '+self.name+' next action in '+str(self.resettime+self.delaytime-time.time()))
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
		touch()
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
	touch()
	logit('State change: ' + recoverystate + ' to: ' + state)
	recoverystate = state

def touch():
	global statusfile
	with open(statusfile,'a'):
		os.utime(statusfile, None)


def logit(msg, lowfreq=False):
	global logfile, recoverystate, logskip, logskipstart, deferredPiReboot,currentlyprinting,cyclecount
#	if lowfreq:
#		if cyclecount < logskip:
#			return
#		elif cyclecount > logskip:
#			logskip = cyclecount + logskipstart
#			return
	with open(logfile,'a',0) as f:
		f.write('(' + str(cyclecount)+') ' + time.strftime('%a %d %b %Y %H:%M:%S ') + msg + ' (' + recoverystate + ')'+
		str(deferredPiReboot)+'/'+str(currentlyprinting)+'\n')

def getuptime():
	with open('/proc/uptime', 'r') as f:
		up_seconds = float(f.readline().split()[0])
	up_string = str(timedelta(seconds=up_seconds))
	return up_seconds, up_string

dirname = '/home/pi/watchdog'
cwd = os.getcwd()
os.chdir(dirnm)
q = [k for k in os.listdir('.') if 'watchdog.log' in k]
if "watchdog.log." + str(20) in q:
	os.remove('watchdog.log.20')
for i in range(19, 0, -1):
	if "watchdog.log." + str(i) in q:
		os.rename('watchdog.log.' + str(i), "watchdog.log." + str(i + 1))
try:
	os.rename('watchdog.log', 'watchdog.log.1')
except:
	pass
with open('watchdog.log', 'w') as f:
	f.write('New logfile at: '+time.strftime('%a %d %b %Y %H:%M:%S'))

os.chmod('watchdog.log', 0o555)
os.chdir(cwd)

statusfile = '/home/pi/watchdog/lastcheck'
logfile = '/home/pi/watchdog/watchdog.log'
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.cleanup()
cgitb.enable(format='text')
with open(logfile, 'a', 0) as f:  # really should be a logit call but vars not exist yet
	f.write("------------------------------------------------\n")
	f.write(time.strftime('%a %d %b %Y %H:%M:%S ') + "Starting " + getuptime()[1] +'\n')

time.sleep(10) # let the system clock reset
sys.stdout = open('/home/pi/watchdog/master.log', 'a', 0)
sys.stderr = open('/home/pi/watchdog/master.err', 'a', 0)
print >> sys.stderr, "------------"
print >> sys.stderr, "Start at: " + time.strftime('%a %d %b %Y %H:%M:%S ')
print >> sys.stdout, "------------"
print >> sys.stdout, "Start at: " + time.strftime('%a %d %b %Y %H:%M:%S ')
with open('/home/pi/watchdog/netwatch.yaml') as y:
	params = yaml.load(y)

p = params['pinghosts']
routerIP = p['localip']
externalIP = p['remoteip']
print 'Router:',routerIP,'External:',externalIP

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
prforcedoff = False
if monitorprinter:
	APIkey = p['key']
	offafter = p['offafter']*60
	prport = p['port']
	waitprinter = p['waitonreboot']
	prmaxwait = p['waitmaxhrs']*60*60
	proffcmd = p['offcmd']
	prforcedoff = False  # have never forced the printer power off - might be on but bot connected

cyclecount = 0
logskip = 1 # on first pass cyclecount will get incremented to 1 and low freq will print
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
lastps = "--------"

logit("Up: "+getuptime()[1])
with open(logfile, 'a', 0) as f:
    call("iwconfig",stdout=f)
time.sleep(5)  # not sure it's need but want system to get through most of the boot - there were some failures
while True:
	cyclestart = time.time()
	cyclecount += 1

	if monitorprinter:
		ps = GetPrinterStatus()
		c2 = time.time()
		if lastps <> ps:
			logit("Printer state changed from "+lastps+' to '+ps)
		lastps = ps
		logit("Printer state: "+ps,lowfreq=True)
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
		elif ps in ('Operational',"Offline"):
			if cyclestart - lastprinting > offafter:
				# turn it off
				logit("Power off printer from "+ ps)
				GPIO.output(prport, 1)
				subprocess.call('//home/pi/scripts/webcam stop', shell=True)
			else:
				# not idle long enough to power off
				prforcedoff = False  # make sure if it disconnects for some reason we power it off eventually
		else:
			pass
			logit('Unknown printer state: ' + ps)


	externalnetup = RobustPing(externalIP)
	localrouterup = RobustPing(routerIP)

	uptime_seconds, uptime_string = getuptime()


	if externalnetup:
		# All is well - clear any reset in progress and just get back to watching
		deferredPiReboot = False # clear any deferred reboot since net has recovered
		if recoverystate <> 'watching':
			# just came up so log it
			logit('Network up from: ' + recoverystate)
			updatestateandfilestamp('watching')
		else:
			touch()
			logit('Network ok, up: '+ getuptime()[1]+' '+str(badping)+'/'+str(totalping),lowfreq=True)
		netlastseen = cyclestart  # note last seen ok time
	elif deferredPiReboot:
		if currentlyprinting:
			touch()
			logit('Still deferring', lowfreq=True)
		else:
			# execute the deferred reboot
			pireboot('Printing ended reboot', 98)
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
			with open(logfile, 'a', 0) as f:
				call("iwconfig", stdout=f)
			waitonrouterhack = 20
		elif recoverystate == 'picommsunknown':
			touch()
			waitonrouterhack -= 1
			if waitonrouterhack > 0:
				logit("Trying to ride out router weirdness: " + str(waitonrouterhack))
				with open(logfile, 'a', 0) as f:
					call("iwconfig", stdout=f)
			else:
				# comms have been down in weird way for many cycles so start the reboots
				# Could reboot router first but Pi is more likely to have failed to try it first
				pireboot('No local comms', 91)
		else:
			touch()
			pireboot('Unknown state error 2: ' + recoverystate, 93)  # huh?  or perhaps check for initial?
	# sleep awaiting events
	cycleend = time.time()
	sleepduration = basecycletime - (cycleend - cyclestart)
	#print time.strftime('%a %d %b %Y %H:%M:%S '),cyclestart, c2, cycleend, sleepduration
	try:
		time.sleep(sleepduration)
	except:
		logit("Main sleep exception: "+ str(sleepduration)+" Start: " + str(cyclestart) + " Mid: " + str(c2) + " End: "+ str(cycleend))
		time.sleep(6)  # wait a bit anyway