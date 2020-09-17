#!/usr/bin/python
import argparse
import time
import requests
import os
import subprocess
def logit(msg):
	global logfile

#	with open(logfile,'a',0) as f:
	logfile.write(time.strftime('%a %d %b %Y %H:%M:%S: ') + msg + '\n')
	logfile.flush()

def RobustPing(dests, verbose=True):
	global badping, testfile, destindex, lastdest, null, simnet
	dest = dests[destindex]
	lastdest = dest
	destindex = (destindex + 1)%len(dests)

	if simnet: # for testing set destinations to ~L ~R
		if os.path.isfile(testfile):
			logit("Simulate good ping of "+dest)
			return True
		else:
			logit("Simulate failed ping of "+dest)
			return False
	ok = False
	pingcmd = 'ping -c 1 -W 1 ' + dest
	for i in range(10):
		p = subprocess.call(pingcmd, shell=True, stdout=null, stderr=null)
		if p == 0:
			ok = True # one success in loop is success
			break
		else:
			badping = badping + 1
			if verbose:
				logit('Ping failure to: ' + dest + ' ' + str(badping))
			else:
				if badping % 100 == 0:
					logit('Ping failure count = '+str(badping))
	return ok

def IssueReset(cmdtoissue):
	tries = 5
	success = False
	while not success:
		try:
			r = requests.get(cmdtoissue)
			logit('Reset try response (tries = {}): {}'.format(tries, r.status_code))
			if r.status_code == 200:
				success = True
		except Exception as E:
			logit('Exception trying to do reset (tries  {}): {}'.format(tries, E))
			tries = tries - 1
			if tries > 0:
				time.sleep(15)
			else:
				logit('Reset failed multiple times - restart watchdog')
				raise ConnectionAbortedError

badping = 0
destindex = 0
lastdest = ''
netup = True
netdowntime = 0
resettime = 0
null = open('/dev/null','a')

parser = argparse.ArgumentParser(description='Reset modem on prolonged internet outage')
parser.add_argument('-i', '--interval', default = 60, type = int, help = 'ping interval in seconds')
parser.add_argument('-o', '--outage', default = 30, type = int, help = 'reset after this many minutes')
parser.add_argument('-w', '--wait', default = 120, type = int, help = 'time to wait after modem reset')
parser.add_argument('--dests',nargs='*',default='8.8.8.8')
parser.add_argument('--logfile',default = 'modemwatch.log', type=argparse.FileType('a'))
parser.add_argument('-v', '--verbose',default = False, action='store_true')
parser.add_argument('--simreset',default=False,action='store_true')
parser.add_argument('--simnet',default=False,action='store_true')
parser.add_argument('-c', '--confirm',default=12, type = int, help = 'interval in hours for issuing log messages confirming running')
parser.add_argument('--testfile',default='simnetup')
parser.add_argument('--cmdm', default='')
parser.add_argument('--cmdr', default='')
parser.add_argument('--modem',default='modempower.pdxhome')
parser.add_argument('--router',default='routerpower.pdxhome')
parser.add_argument('--dualdevices',default=False,action='store_true')
parser.add_argument('--interdelay', default=1,type=int,help = 'delay between modem reset and router reset')
args = parser.parse_args()
logfile = args.logfile
if args.cmdm == '':
	cmdm = 'http://'+args.modem+'/cm?cmnd=Power1%20ON'
else:
	cmdm = args.cmdm
if args.cmdr == '':
	cmdr = 'http://'+args.router+'/cm?cmnd=Power1%20ON'
else:
	cmdr = args.cmdm

simreset = args.simreset
simnet = args.simnet
if simnet:
	args.interval = 1
	args.outage = .25
	args.wait = 10
	logfile.seek(0)
	logfile.truncate()
	logit('Truncated log for testing')
testfile = args.testfile
confirminterval = args.confirm * 60 * 60
nextconfirm = time.time()+confirminterval

#print(args)
logit('*********************************************')
logit('Modemwatch starting')
for arg, val in vars(args).items():
	logit('    '+ repr(arg)+' = '+repr(val))
while True:
	while netup:
		if (time.time() > nextconfirm) and (confirminterval != 0):
			logit('Confirm watchdog running')
			nextconfirm = time.time() + confirminterval
		time.sleep(args.interval)
		if RobustPing(args.dests):
			if args.verbose:
				logit('Ping ok: ' + lastdest)
		else:
			now = time.time()
			netdowntime = now
			resettime = now
			netup = False
			logit('Ping fail: ' + lastdest + ' Net marked down ')
	while not netup:
		time.sleep(args.interval)
		if RobustPing(args.dests,verbose=args.verbose):
			logit('Network back up')
			netup = True
		else:
			now = time.time()
			logit('Ping continues fail: '+ lastdest + ' Down {0:.0f} seconds {1:.0f} to reset'.format(now - netdowntime,args.outage*60 - (now-resettime)))
			if now - resettime > args.outage*60:
				if simreset:
					logit('Test modem reset; delay {} seconds: {}'.format(args.wait, cmdm))
					if args.dualdevices: logit('Test router reset; delay {} seconds: {}'.format(args.wait, cmdr))
				else:
					logit('Issue modem reset')
					IssueReset(cmdm)
					if args.dualdevices:
						time.sleep(args.interdelay)
						logit('Issue router reset')
						IssueReset(cmdr)
					logit('Delay {0:d} seconds'.format(args.wait))


				time.sleep(args.wait)
				resettime = time.time()
				logit('Resuming network testing')



