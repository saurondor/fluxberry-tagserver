import RPi.GPIO as GPIO
import time
pins = [5, 6, 13, 19, 26]
pin = 5
# blinking function
def blink(pin):
        GPIO.output(pin,GPIO.LOW)
        time.sleep(0.02)
        GPIO.output(pin,GPIO.HIGH)
        time.sleep(0.01)
        return
# to use Raspberry Pi bcm pin numbers
GPIO.setmode(GPIO.BCM)
# set up GPIO output channel
for j in pins:
	pin = j
	GPIO.setup(pin, GPIO.OUT)
	for i in range(0,50):
        	blink(pin)
GPIO.cleanup()
