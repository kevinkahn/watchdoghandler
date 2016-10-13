#!/bin/bash
# Setup the watchdog stuff
apt-get install -y watchdog
pip install PyYAML
pip install pyping
cp support/watchdog.service /lib/systemd/system
cp support/watchdog.conf /etc
cp support/nethealth.service /etc/systemd/system
chmod a+x repair.py
chmod a+x netrepair.py
echo dtparam=watchdog=on >> /boot/config.txt
systemctl daemon-reload
systemctl enable watchdog
systemctl enable nethealth
systemctl start nethealth
systemctl start watchdog