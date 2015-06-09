from socket import *
from tcp_read_handler import SpeedwayReader
from tcp_read_handler import TagServer
import thread
import threading
import mysql.connector
import time


if __name__=='__main__':
    print 'Starting server process'
    server = TagServer()
    #port = 14150
    #host = 'speedwayr-11-49-c4.attlocal.net'
    #event = '708f40aeabcd4a35a36385bdc5ad35b7'
    #reader0 = SpeedwayReader(port, host,  event)
    #reader0.start()
    #print 'Connecting to reader 1'
    #reader1 = SpeedwayReader(port, host,  event)
    #reader1.start()
    
    while 1:
        print 'Main app running'
        time.sleep(300)
