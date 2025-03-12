# dbus_dtupros
Integrate Hoymiles 3rd Gen DTU-Pro S into Victron Energy's (Venus OS) ecosystem.

# Disclaimer
I wrote this script for myself. I'm not responsible if you damage something using my script.

# Purpose
Integrate Hoymiles 3rd Gen DTU-Pro S into Victron Energy's (Venus OS) ecosystem. This project is intended for people who do not want to use OpenDTU but stay with the Hoymiles DTU Pro S.

Advantages:
- Ethernet connection from DTU-Pro S to the Venus GX device (in my case, a Raspberry Pi 4 with Venus OS v3.14 installed)
- Parallel use of Hoymiles Cloud (S-Miles) and Victrons VRM
- Maintainance by Homiles (like inverter firmware updates, etc.) possible 

# Install
1. Ensure you have SSH access to your Victron GX device.
2. Copy the dbus_dtupros folder to /data/dbus_dtupros
3. Edit config.ini to your needs
4. Make install.sh executable: ```chmod +x install.sh```
5. Run ```/data/dbus-dtupros/install.sh```

# Uninstall
Run ```/data/dbus-dtupros/uninstall.sh```

# Restart
Run ```/data/dbus-dtupros/restart.sh```

# Debugging
Check logs with ```tail -n 100 -f /var/log/dbus-dtupros/current | tai64nlocal```

The service status can be checked with ```svstat /service/dbus-dtupros```

# Venus-OS
dbus_dtupros relies on the library pymodbus.
Venus-OS comes with pymodbus 2.5.3 installed. Check via ```python -m pip list | grep pymodbus```.
- Upgrade to most recent: ```pip3 install --upgrade pymodbus```
- Downgrade: ```pip3 install pymodbus==2.5.3```
Make sure you have the correct line enabled in ```dtupros.py``` (line 4 or 5, depending on your pymodbus library version).

# Inspiration
This project was highly inspired by the following projects:
- https://github.com/mr-manuel/venus-os_dbus-mqtt-pv
- https://github.com/henne49/dbus-opendtu

