from socket import *
from time import gmtime, strftime
import RPi.GPIO as GPIO
import threading
import time
import socket
import mysql.connector
import binascii
import datetime
from datetime import datetime
from Queue import Queue
import os

BUFF = 1024
READER_0_LED = 5
READER_1_LED = 6
WATCHDOG_LED = 26
BUZZER_LED = 13
TIEMPOMETA_LED = 19
DATABASE = 'speedway'
DB_HOSTNAME = 'localhost'
DB_USER = 'speedway'
DB_PASSWORD = 'speedway'

class TagServer():
    
        # blinking function
    def blink(self, pin):
        GPIO.output(pin,GPIO.LOW)
        time.sleep(0.02)
        GPIO.output(pin,GPIO.HIGH)
        time.sleep(0.01)
        return


    def __init__(self):
	    pins = [5, 6, 13, 19, 26]
	    pin = 5
	    # to use Raspberry Pi bcm pin numbers
	    GPIO.setmode(GPIO.BCM)
	    not_connected = True
	    # set up GPIO output channel
	    for j in pins:
		    pin = j
		    GPIO.setup(pin, GPIO.OUT)
		    for i in range(0,20):
            		self.blink(pin)
            while not_connected:
                try:
                    self.cnx = mysql.connector.connect(host=DB_HOSTNAME,database=DATABASE,user=DB_USER,password=DB_PASSWORD)
                    not_connected = False
                except Exception as error:
                    print(error)
                    time.sleep(5)
                    
            # load settings
            print 'Starting client listener'
            self.client_listener = ClientListener(10201, '0.0.0.0')
            self.client_listener.daemon = True
            self.client_listener.start()
            # start reader listeneres
            cursor = self.cnx.cursor()
            query = ("SELECT id, address, port, status FROM readers")
            cursor.execute(query)
            for (id, address, port, status) in cursor:
                print("{} - {}, {} reader status {}".format(id, address,  port,  status))
                reader0 = SpeedwayReader(id, address, port, self)
	        reader0.daemon = True
                try:
                    reader0.connect_to_reader()
                except Exception as error:
                    print(error)
                reader0.start()
            cursor.close()
            print 'Initialized server process!'
        
    def notify_reading(self, reading):
        self.client_listener.notify_reading(reading)

class Reader():

    def __init__(self, clientsock, addr,  event):
        print 'Init connection to ' + addr

# Listens to incomming client connections
class ClientListener(threading.Thread):
    
    
    def __init__(self,  port,  hostname):
        threading.Thread.__init__(self)
        print 'Initializing client listener'
        self.port = port
        self.hostname = hostname
        self.workers = []
        
    def notify_reading(self,  reading):
        GPIO.output(WATCHDOG_LED,GPIO.HIGH)
        print "Reading "+reading
        if len(reading) > 10:
            GPIO.output(BUZZER_LED,GPIO.LOW)
            time.sleep(0.02)
            GPIO.output(BUZZER_LED,GPIO.HIGH)
            time.sleep(0.02)
            GPIO.output(BUZZER_LED,GPIO.LOW)
            time.sleep(0.02)
            GPIO.output(BUZZER_LED,GPIO.HIGH)
        time.sleep(0.02)
        GPIO.output(WATCHDOG_LED,GPIO.LOW)
        for worker in self.workers:
            if (worker.is_connected()):
                worker.notify_reading(reading )
        for worker in self.workers:
            if (not worker.is_connected()):
                try:
                    self.workers.remove(worker)
                except Exception as error:
                    print error
        if len(self.workers) == 0:
            GPIO.output(WATCHDOG_LED,GPIO.HIGH)

    
    def run(self):
        print 'Running listener ' + self.hostname + ' ' + str(self.port)
        ADDR = (self.hostname, self.port)
        serversock = socket.socket(AF_INET, SOCK_STREAM)
        serversock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        serversock.bind(ADDR)
        serversock.listen(5)
        while 1:
            print 'waiting for connection... listening on port', self.port
            clientsock, addr = serversock.accept()
            client_worker = ClientWorker(clientsock)
	    client_worker.daemon = True
            self.workers.append(client_worker)
            client_worker.start()
            print '...connected from:', addr
            GPIO.output(WATCHDOG_LED,GPIO.LOW)

	    

# Handles a connection with a particular client
class ClientWorker(threading.Thread):
    
    def __init__(self,  socket):
        self.cnx = mysql.connector.connect(host=DB_HOSTNAME,database=DATABASE,user=DB_USER,password=DB_PASSWORD)
        threading.Thread.__init__(self)
        print 'Initializing new client worker'
        # get current reading ID
        self.socket = socket
        self.readings = Queue()
        self.socket_connected = True
        t1 = threading.Thread(target=self.command_listener)
        t1.daemon = True
        t1.start()
    
    def notify_reading(self,  reading):
        self.readings.put(reading)

    def is_connected(self): 
        return self.socket_connected
        
    def clear_readings(self):
        cursor = self.cnx.cursor()
        query = ("DELETE FROM readings")
        cursor.execute(query)
        self.cnx.commit()
    
    def rewind_readings(self):
        cursor = self.cnx.cursor()
        query = ("SELECT id, antenna, reader, epc, tid, user_data, rssi, time_millis FROM readings")
        cursor.execute(query)
        for (id, antenna, reader, epc, tid, user_data, rssi, time_millis) in cursor:
            data_row = "{},{},{},{},{},{},{}\r\n".format(reader, antenna,  epc, time_millis, rssi, tid, user_data)
            self.notify_reading(data_row)
        cursor.close()
        self.cnx.commit()
        
    def handle_time_command(self, commands):
        if commands[1] == "set":
            print "set time"
            command_line = 'date %s' % commands[2]
            print command_line
            os.system(command_line)
            data_row = strftime("%Y-%m-%d %H:%M:%S\r\n", gmtime())
            self.notify_reading(data_row)
        if commands[1] == "get":
            print "get time"
            data_row = strftime("%Y-%m-%d %H:%M:%S\r\n", gmtime())
            self.notify_reading(data_row)

    def handle_command(self, command):
        print "command :" + command + ":"
        commands = command.split()
        if len(commands) > 0:
            if commands[0] == "clear":
	            print "clear command"
	            self.clear_readings()
            if commands[0] == "rewind":
	            print "rewind command"
	            self.rewind_readings()
            if commands[0] == "time":
	            print "time command"
	            self.handle_time_command(commands)
    
    def command_listener(self):
        print 'Init command listener as threaded function'
        while self.socket_connected:
            command = self.socket.recv(BUFF)
            self.handle_command(command.rstrip('\r\n'))
            if not command:
                print 'Conection closed'
                self.socket.close()
                self.socket_connected = False
                GPIO.output(WATCHDOG_LED,GPIO.HIGH)
                break
            else:
                print command
        
    
    def run(self):
        print 'Starting client worker ' + str(self.__hash__)
        # get all readings greater than current ID
        while 1:
            try:
                data = self.readings.get(True, 60)
                self.socket.send(data)
            except:
                print 'Client worker ' + str(self.__hash__) + " running"

class SpeedwayReader(threading.Thread):

    def __del__(self):
        self.cnx.close()

    def __init__(self, id, addr, port, server):
        threading.Thread.__init__(self)
        
        self.connected = 1
        self.socket_connected = 0
        self.id = id
        self.watchdog_event = threading.Event()
        self.cnx = mysql.connector.connect(host=DB_HOSTNAME,database=DATABASE,user=DB_USER,password=DB_PASSWORD)
        self.addr = addr
        self.port = port
        self.server = server
        print 'Starting watchdog'
        self.watchdog_event.clear()
        t1 = threading.Thread(target=self.watchdog,  args=(self.watchdog_event, ))
        t1.daemon = True
        t1.start()
        self.readings = Queue()
        t2 = threading.Thread(target=self.log_readings)
        t2.daemon = True
        t2.start()

    def log_message(self,  message):
        print '** ' + self.addr + "\n\t" + message
        
    def log_readings(self):
        print '** starting read logger'
        cursor = self.cnx.cursor()
        add_reading = ("INSERT INTO readings "
                       "(antenna, reader, epc, tid, user_data, time_millis, read_time, rssi) "
                       "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
        while 1:
            executed_command = False
            command_counter = 0
            try:
                while not self.readings.empty():
                    reading = self.readings.get(True, 10)
                    print 'log data...'
                    #self.socket.send(data)
                    try:
                        #print 'saving data'
                        data_reading = (reading.antenna,  self.id,  reading.epc, reading.tid, reading.user_data, reading.time_millis, reading.read_time,  reading.rssi)
                        cursor.execute(add_reading, data_reading)
                        executed_command = True
                        command_counter += 1
                    except Exception as error:
                        print error
            except:
                print 'No readings to store in database, ' + str(self.__hash__) + " running"
            if executed_command:
                print '-- commit ' + str(command_counter) + ' commands'
                self.cnx.commit()

    
    def watchdog(self,  event):
        counter = 0
        while 1:
            if self.id == 1:
                time.sleep(1)
                GPIO.output(READER_0_LED,GPIO.HIGH)
                time.sleep(0.05)
                GPIO.output(READER_0_LED,GPIO.LOW)            
            if self.id == 2:
                time.sleep(1)
                GPIO.output(READER_1_LED,GPIO.HIGH)
                time.sleep(0.05)
                GPIO.output(READER_1_LED,GPIO.LOW)
            if event.isSet():
                counter = 0
                self.watchdog_event.clear()
            else:
                counter += 1
            if counter > 12:
                self.clientsock.close()
                self.socket_connected = 0
                self.log_message("Watchdog closed connection. Triggering reconnect") #log on console

    def blink_keepalive(self):
        if self.id == 1:
            GPIO.output(READER_0_LED,GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(READER_0_LED,GPIO.LOW)
            time.sleep(0.05)
            GPIO.output(READER_0_LED,GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(READER_0_LED,GPIO.LOW)
            time.sleep(0.05)
        if self.id == 2:
            GPIO.output(READER_1_LED,GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(READER_1_LED,GPIO.LOW)
            time.sleep(0.05)
            GPIO.output(READER_1_LED,GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(READER_1_LED,GPIO.LOW)
            time.sleep(0.05)


    def connect_to_reader(self):
        self.log_message('Connecting to server')
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(1)
        client_socket.connect((self.addr, self.port))
        self.clientsock = client_socket
        self.socket_connected = 1
        self.log_message('Connected to server!')
        if self.id == 1:
            GPIO.output(READER_0_LED,GPIO.LOW)
        if self.id == 2:
            GPIO.output(READER_1_LED,GPIO.LOW)
        self.watchdog_event.set()

    def response(self,  data):
        self.watchdog_event.set()
        self.log_message('Reader data: ' + data)
        reader = "0"
        rows = data.splitlines()
        for row in rows:
            #print 'Row:'+row
            fields = row.split(',')
            #print len(fields)
            read_time = None
            log_data = True
            reading = TagReading()
            try:
                if len(fields) == 1:
                    antenna = None
                    epc = 'keepalive'
                    time_millis = None
                    rssi = None
                    tid = None
                    user_data = None
                    log_data = False
		    blink = threading.Thread(target=self.blink_keepalive)
        	    blink.daemon = True
		    blink.start()	
                elif len(fields) == 5:
                    reading.antenna = fields[0]
                    reading.epc = fields[1]
                    reading.time_millis = fields[2]
                    reading.rssi = fields[3]
                    reading.tid = fields[4]
                    reading.user_data = None
                    try:
                        ms = float(reading.time_millis)//1000000.0
                        reading.read_time = datetime.utcfromtimestamp(ms)
                    except Exception as error:
                        self.log_message(error)
                elif len(fields) == 6:
                    reading.antenna = fields[0]
                    reading.epc = fields[1]
                    reading.time_millis = fields[2]
                    reading.rssi = fields[3]
                    reading.tid = fields[4]
                    reading.user_data = fields[5]
                    try:
                        ms = float(reading.time_millis)//1000000.0
                        reading.read_time = datetime.utcfromtimestamp(ms)
                    except Exception as error:
                        self.log_message(error)
                if log_data:
                    self.readings.put(reading)
            except Exception as error:
                self.log_message(error)
                

    
    def run(self):
        keepalive_counter = 0
        retry_counter = 1
        while self.connected:
            while self.socket_connected:
                try:
                    data = self.clientsock.recv(BUFF)
                    time_now = datetime.today()
                    print("notify reading "+data)
                    if not data: 
                        self.clientsock.close()
                        self.socket_connected = 0
                        self.log_message(self.addr, "- closed connection") #log on console
                        GPIO.output(READER_0_LED,GPIO.HIGH)
                        break
                    data = data.splitlines()
                    print("notify reading rows "+str(len(data)))
                    for row in data:
                        print("sending data row "+row)
                        self.server.notify_reading(str(self.id) + ","+ row+"\r\n")
                        repr(self.response(row))
                except Exception:
                    data_timeout = 1
            if self.id == 1:
                GPIO.output(READER_0_LED,GPIO.HIGH)
            if self.id == 2:
                GPIO.output(READER_1_LED,GPIO.HIGH)
            #self.event.clear()
            self.log_message('Waiting to reconnect. Retry:' + str(retry_counter))
            if retry_counter < 20:
                time.sleep(0.1)     
            elif retry_counter < 100:
                time.sleep(10)
                if self.id == 1:
                    GPIO.output(READER_0_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_0_LED,GPIO.HIGH)
                    time.sleep(0.3)
                    GPIO.output(READER_0_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_0_LED,GPIO.HIGH)
                if self.id == 2:
                    GPIO.output(READER_1_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_1_LED,GPIO.HIGH)
                    time.sleep(0.3)
                    GPIO.output(READER_1_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_1_LED,GPIO.HIGH)
            else:
                time.sleep(60)
                if self.id == 1:
                    GPIO.output(READER_0_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_0_LED,GPIO.HIGH)
                    time.sleep(0.3)
                    GPIO.output(READER_0_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_0_LED,GPIO.HIGH)
                if self.id == 2:
                    GPIO.output(READER_1_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_1_LED,GPIO.HIGH)
                    time.sleep(0.3)
                    GPIO.output(READER_1_LED,GPIO.LOW)
                    time.sleep(0.3)
                    GPIO.output(READER_1_LED,GPIO.HIGH)

            try:
                self.connect_to_reader()
                retry_counter = 1
            except Exception:
                retry_counter = retry_counter + 1
                self.log_message('Unable to connect')

class TagReading:
    def __init__(self):
        self.antenna = ""
        self.epc = ""
        self.time_millis = 0
        self.rssi = 0
        self.tid = ""
        self.user_data = ""
        self.read_time = ""
