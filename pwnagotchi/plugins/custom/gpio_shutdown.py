import pwnagotchi.plugins as plugins
import logging
import RPi.GPIO as GPIO
import pwnagotchi


class GPIOShutdown(plugins.Plugin):

    __author__ = 'tomelleri.riccardo@gmail.com'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'GPIO Shutdown plugin'
    triggered = False

    def shutdown(self, channel):
        if not self.triggered:
            self.triggered = True
            logging.warning('Received shutdown command from GPIO')
            pwnagotchi.shutdown()


    def on_loaded(self):
        shutdown_gpio = self.options.get('gpio')

        if not shutdown_gpio:
            logging.warn('GPIO Shutdown plugin misconfigured. Please provide "main.plugins.gpio_shutdown.gpio = yourGpioNumber"')
            return False

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(shutdown_gpio, GPIO.IN, GPIO.PUD_UP)
        GPIO.add_event_detect(shutdown_gpio, GPIO.FALLING, callback = self.shutdown)

        logging.info("Added shutdown command to GPIO %d", shutdown_gpio)
