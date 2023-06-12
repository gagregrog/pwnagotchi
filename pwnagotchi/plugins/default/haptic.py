import pwnagotchi.plugins as plugins
import logging
import RPi.GPIO as GPIO
import time
from threading import Thread

class Buzzer:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(pin, GPIO.OUT)
        self.thread = None

    def buzz(self, duration):
        if self.thread is None:
            self.thread = Thread(target=self.__buzz, args=(duration,))
            self.thread.start()

    def __buzz(self, duration):
        try:
            print('start')
            GPIO.output(self.pin, 1)
            time.sleep(duration)
        except:
            print('error')
            logging.warn('[haptic] error in haptic thread')
        finally:
            print('end')
            GPIO.output(self.pin, 0)
            self.thread = None

class Haptic(plugins.Plugin):
    __author__ = 'gagregrog@gmail.com'
    __version__ = '1.0.0'
    __license__ = 'MIT'
    __description__ = 'A plugin to provide haptic feed back when your pwnagotchi does interesting things'

    def __init__(self):
        self.buzzer = None

    def on_loaded(self):
        buzzer_gpio = self.options.get('gpio')
        if not buzzer_gpio:
            logging.warn('[haptic] plugin misconfigured. Please provide "main.plugins.haptic.gpio = yourGpioNumber"')
            return None

        logging.info('[haptic] plugin loaded and ready on pin {}'.format(buzzer_gpio))

        self.buzzer = Buzzer(buzzer_gpio)
        self.buzzer.buzz(2)

    def on_handshake(self, agent, filename, access_point, client_station):
        self.buzzer.buzz(4)

    def on_association(self, agent, access_point):
        self.buzzer.buzz(1)

    def on_deauthentication(self, agent, access_point, client_station):
        self.buzzer.buzz(2.5)

    def on_peer_detected(self, agent, peer):
        self.buzzer.buzz(8)
