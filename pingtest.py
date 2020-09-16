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


def RobustPing(dest):
	global totalping, badping
	ok = False
	# todo should make this a loop that tries until success or 10 failures
	for i in range(100):
		try:
			netup = pyping.ping(dest, timeout=5, count=1)
		except:
			print 'External Ping Exception'
			inetup.ret_code = 1 # just assume bad this loop
		if netup.ret_code == 0:
			ok = True # one success in loop is success
		else:
			badping = badping + 1
			print 'Ping failure to:' + dest + ' ' + str(badping)
			#logit('Ping Failure to: ' + dest + ' ''+ str(netup.ret_code) + str(netup.output))

def PingSh(dest):
	global badping
	null = open('/dev/null','a')
	for i in range(100):
		cmd = 'ping -c 1 '+dest

		p = subprocess.call(cmd,shell=True,stdout=null,stderr=null)
		print 'RETURN CODE: ', p
		if p <> 0:
			badping = badping + 1

RobustPing('8.8.8.8')
print badping
badping = 0
PingSh('8.8.8.8')
print badping
