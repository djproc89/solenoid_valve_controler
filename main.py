import network
import time
import socket
import machine
import ntptime
import json

# loading config
with open("config.json") as file:
    cfg = json.load(file)
    
with open("time.json") as file:
    time_cfg = json.load(file)

    def convert(hours):
        l = []
        for h in hours:
            t = h.split(":")
            if len(t) != 3:
                print(f"Wrong hour in {h}")
                continue
            l.append(int(t[0]) * 3600 + int(t[1]) * 60 + int(t[2]))
        return l
    
    open_hour = convert(time_cfg["open_hour"])
    close_hour = convert(time_cfg["close_hour"])

class WiFi:
    
    def __init__(self, ssid, passwd):
        self.ssid = ssid
        self.passwd = passwd
        self.wlan = network.WLAN(network.STA_IF)
        self.next_try = 0
        self.connect()
    
    def connect(self):
        try:
            self.wlan.active(True)
            self.wlan.connect(self.ssid, self.passwd)
            for _ in range(int(cfg["WIFI_TRIES"])):
                print("Connecting...")
                time.sleep(cfg["WIFI_DELAY"])
                if self.wlan.isconnected():
                    print("Connected!")
                    print(self.wlan.ifconfig())
                    self.next_try = 0
                    return
            
            print(f"Not connected with {self.ssid}!")
            self.next_try = time.time() + 30
            
        except:
            print(f"Not connected with {self.ssid}!")
    
    def is_connected(self):
        return self.wlan.isconnected()
    
    def loop(self):
        if not self.is_connected():
            if self.next_try != 0 and time.time() > self.next_try:
                self.connect()
            if self.next_try == 0:
                self.next_try = time.time() + 30  

class Valve:
    
    # statuses:
    # closing = 0
    # close = 1
    # opening = 2
    # open = 3
    
    def __init__(self, open_pin, close_pin):
        self.open_pin = machine.Pin(open_pin, machine.Pin.OUT)
        self.close_pin = machine.Pin(close_pin, machine.Pin.OUT)
        self.status = 3
        self.start_time = 0
        self.close()
    
    def open(self):
        if self.status == 2 or self.status == 3:
            return
        
        print("Opening...")
        self.close_pin.value(0)
        self.start_time = time.time()
        self.status = 2
    
    def close(self):
        if self.status == 0 or self.status == 1:
            return
        
        print("Closing...")
        self.open_pin.value(0)
        self.start_time = time.time()
        self.status = 0
        
    def switch(self):
        if self.status == 0 or self.status == 1:
            self.open()
        else:
            self.close()
        
    
    def loop(self):
        # closing
        if self.status == 0:
            self.close_pin.value(1)
            if time.time() - self.start_time > cfg["VALVE_DELAY"]:
                self.status = 1
                print("Closed")
        # close
        elif self.status == 1:
            self.close_pin.value(0)
        # opening
        elif self.status == 2:
            self.open_pin.value(1)
            if time.time() - self.start_time > cfg["VALVE_DELAY"]:
                self.status = 3
                print("Opened")
        # open
        elif self.status == 3:
            self.open_pin.value(0)

class Led:
    
    # statuses:
    # off = 0
    # on = 1
    # blink_on = 2
    # blink_off = 3
    
    def __init__(self, pin):
        self.pin = machine.Pin(pin, machine.Pin.OUT)
        self.status = 0
        
    def blink(self, delay):
        self.status = 2
        self.delay = delay
        self.start = time.time()
        
    def on(self):
        self.status = 1
        
    def off(self):
        self.status = 0

        
    def loop(self):
        if self.status == 0:
            self.pin.value(0)
        elif self.status == 1:
            self.pin.value(1)
        elif self.status == 2:
            self.pin.value(1)
            if time.time() - self.start > self.delay:
                self.status = 3
                self.start = time.time()
        elif self.status == 3:
            self.pin.value(0)
            if time.time() - self.start > self.delay:
                self.status = 3
                self.start = time.time()

# getting local time 
def get_actual_time():
    return time.time() + int(cfg["TIMEZONE"]) * 3600

# getting gm local time 
def get_gm_actual_time():
    return time.gmtime(get_actual_time())

# print local time in the console
def print_time(t = get_gm_actual_time()):
    year, month, day, hour, minute, second, _, _ = t
    print(f"{year}.{month:02d}.{day:02d} {hour:02d}:{minute:02d}:{second:02d}")

# sync time witn NTP server
def sync_time(host):
    try:
        print(f"Time syncronisation with {host}")
        ntptime.host = host
        ntptime.settime()
        print_time()
    except:
        print("Time not synced!")
    

# pin configuration
wlan_led = machine.Pin('LED', machine.Pin.OUT)
button = machine.Pin(cfg["BUTTON_PIN"], machine.Pin.IN, machine.Pin.PULL_UP)
green = machine.Pin(cfg["GREEN_LED_PIN"], machine.Pin.OUT)
red = machine.Pin(cfg["RED_LED_PIN"], machine.Pin.OUT)

# connect with wifi
wifi = WiFi(cfg["WIFI_SSID"], cfg["WIFI_PASSWD"])

time.sleep(2)

# update time
sync_time(cfg["NTP_HOST"])

# setting valve object
valve = Valve(cfg["OPEN_PIN"], cfg["CLOSE_PIN"])

while True:
    # valve and diodes loops
    valve.loop()
    wifi.loop()
    
    # indicates of valve status
    if valve.status == 3:
        green.on()
        red.off()
    elif valve.status == 1:
        green.off()
        red.on()
    else:
        green.on()
        red.on()

    # indicates of wifi connection
    if wifi.is_connected() == False:
        wlan_led.off()
    else:
        wlan_led.on()
        
    # button pressed 
    if button.value() == False:
        valve.switch()
        time.sleep(0.4)
    
    # check open hour
    if open_hour.count(get_actual_time() % 86400) > 0:
        valve.open()
    
    # check close hour
    if close_hour.count(get_actual_time() % 86400) > 0:
        valve.close()
    
    # sync time with ntp once per NTP_REFRESH seconds
    if get_actual_time() % int(cfg["NTP_REFRESH"]) == 0:
        sync_time(cfg["NTP_HOST"])
    
    time.sleep(1)