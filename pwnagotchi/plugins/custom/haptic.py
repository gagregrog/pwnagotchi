import os
import time
import logging
from PIL import Image
import RPi.GPIO as GPIO
from threading import Thread
import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import Widget

MIN_DURATION = 0
MAX_DURATION = 2
DEFAULT_BUZZ_TIMES = {
    'on_loaded': 0.25,
    'on_handshake': 0.25,
    'on_association': 0.1,
    'on_deauthentication': 0.75,
    'on_peer_detected': 1.5,
}
PLUGIN_NAME = 'haptic'
ICONS_DIR = 'haptic_icons'

def info(message):
    logging.info('[{}] {}'.format(PLUGIN_NAME, message))

def warn(message):
    logging.warning('[{}] {}'.format(PLUGIN_NAME, message))

# Cretit 1: https://github.com/cyberartemio/wof-pwnagotchi-plugin
# Credits2: https://github.com/roodriiigooo/PWNAGOTCHI-CUSTOM-FACES-MOD
class Frame(Widget):
    def __init__(self, path, xy, alpha = 0, reverse = False):
        super().__init__(xy)
        self.image = Image.open(path).resize((15, 15)).convert('RGBA')
        self.alpha = alpha
        self.reverse = reverse

    def draw(self, canvas, drawer):
        r, g, b, a = self.image.split()
        alpha = Image.new('L', self.image.size, self.alpha)
        canvas.paste(self.image, self.xy, mask = alpha)
        canvas.paste(255 if self.reverse else 0, self.xy, mask = a)

class Switch:
    def __init__(self, pin, active_high=False, on_toggle=None):
        self.pin = pin
        self.active_high = active_high
        self.thread = None
        self.on_toggle = on_toggle
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        if on_toggle:
            GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self.handle_toggle, bouncetime=750)

    def handle_toggle(self, channel):
        if self.thread is None and self.on_toggle:
            self.thread = Thread(target=self.__handle_toggle, args=(channel,))
            self.thread.start()

    def __handle_toggle(self, channel):
        self.on_toggle(self.is_on())
        time.sleep(0.75)
        self.thread = None

    def is_on(self):
        reading = GPIO.input(self.pin)
        return bool(reading if self.active_high else not reading)

    def cleanup(self):
        GPIO.cleanup(self.pin)

class Buzzer:
    """
    Helper class to manage the starting / stopping of the buzzer from within a child thread
    """
    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(pin, GPIO.OUT)
        self.thread = None

    def buzz(self, duration):
        """
        Create the thread and start buzzing!
        """
        if self.thread is None:
            self.thread = Thread(target=self.__buzz, args=(duration,))
            self.thread.start()

    def __buzz(self, duration):
        """
        To be run from a seperate thread
        Turn on the instantiated pin then sleep for the duration provided
        Turn the pin off after the sleep period
        """
        try:
            GPIO.output(self.pin, 1)
            time.sleep(duration)
        except:
            warn('error in haptic thread')
        finally:
            GPIO.output(self.pin, 0)
            self.thread = None

    def cleanup(self):
        GPIO.cleanup(self.pin)

class Haptic(plugins.Plugin):
    """
    Pwnagotchi Haptic plugin to enable buzzer activity linked to lifecycle events
    """
    __author__ = 'gagregrog@gmail.com'
    __version__ = '1.0.0'
    __license__ = 'MIT'
    __description__ = 'A plugin to provide haptic feed back when your pwnagotchi does interesting things'

    def __init__(self):
        # self.options is only populated once self.on_loaded has been called
        self.icons_path = os.path.join(os.path.dirname(__file__), ICONS_DIR)
        self.buzzer = None
        self.switch = None
        self.icon = None
        self.empty_icon = None

    def on_loaded(self):
        buzzer_gpio = self.options.get('gpio')
        if not buzzer_gpio:
            warn('plugin misconfigured. Please provide "main.plugins.haptic.gpio = yourGpioNumber"')
            return None

        switch_gpio = self.options['switch'].get('gpio') if self.options.get('switch') else None
        if switch_gpio:
            active_high = self.options['switch'].get('active_high')
            info('switch is active {}'.format('high' if active_high else 'low'))
            self.switch = Switch(switch_gpio, active_high=bool(active_high), on_toggle=self.update_icon_if_needed)
            info('feedback is currently {}'.format('on' if self.switch.is_on() else 'off'))

        info('plugin loaded and ready on pin {}'.format(buzzer_gpio))
        self.get_buzz_times()
        self.buzzer = Buzzer(buzzer_gpio)
        self.handle_callback('on_loaded')

    def update_icon_if_needed(self, is_on):
        if not self.switch or self.icon_visible == is_on:
            return

        info("Switch state changed: {}".format('on' if is_on else 'off'))
        if is_on:
            self.handle_callback('on_loaded')
        with self.ui._lock:
            # add_element will overwrite the existing element if it exists
            self.ui.add_element(PLUGIN_NAME, self.icon if is_on else self.empty_icon)
        self.icon_visible = is_on

    def on_ui_setup(self, ui):
        self.ui = ui
        xy = (int(ui.width() / 2) - 5, 0)
        invert_icon = bool(self.options.get('invert_icon'))
        self.icon = Frame(path = f'{self.icons_path}/vibrate.png', xy = xy, reverse = invert_icon)
        self.empty_icon = Frame(path = f'{self.icons_path}/empty.png', xy = xy, reverse = invert_icon)
        self.icon_visible = self.switch.is_on()
        ui.add_element(PLUGIN_NAME, self.icon if (not self.switch or self.icon_visible) else self.empty_icon)

    def on_ui_update(self, ui):
        self.update_icon_if_needed(self.switch.is_on())

    def on_unload(self, ui):
        info('plugin disabled')
        if self.buzzer:
            self.buzzer.cleanup()
        if self.switch:
            self.switch.cleanup()
            if (ui.has_element(PLUGIN_NAME)):
                with ui._lock:
                    ui.remove_element(PLUGIN_NAME)

    def handle_callback(self, config_key):
        """
        Get the buzz time and buzz if it isn't set to 0
        """
        if self.buzzer is None or (self.switch and not self.switch.is_on()):
            return

        duration = self.buzz_times[config_key]
        if duration != 0:
            self.buzzer.buzz(duration)

    def on_handshake(self, agent, filename, access_point, client_station):
        self.handle_callback('on_handshake')

    def on_association(self, agent, access_point):
        self.handle_callback('on_association')

    def on_deauthentication(self, agent, access_point, client_station):
        self.handle_callback('on_deauthentication')

    def on_peer_detected(self, agent, peer):
        self.handle_callback('on_peer_detected')

    def get_buzz_times(self):
        """
        Make a map of buzz times for each supported lifecycle events
        Either use the default buzz time or the value provide in config.toml
        """
        self.buzz_times = {}
        for config_key, default_buzz_duration in DEFAULT_BUZZ_TIMES.items():
            buzz_time = self.resolve_buzz_time(config_key, default_buzz_duration)
            self.buzz_times[config_key] = buzz_time

    def resolve_buzz_time(self, config_key, default_duration):
        """
        Figure out if we can use the configured buzz time or if we should use the default
        """
        config_duration = self.options.get(config_key)
        if config_duration is None:
            return default_duration

        try:
            duration = float(config_duration)
            if duration < MIN_DURATION or duration > MAX_DURATION:
                warn('invalid option for main.plugins.haptic.{}. Value must be >= {} and <= {}. Got: {}. Using default: {}'.format(config_key, MIN_DURATION, MAX_DURATION, duration, default_duration))
                return default_duration
            return duration
        except Exception:
            warn('invalid option for main.plugins.haptic.{}. Value must be >= {} and <= {}. Got: {}. Using default: {}'.format(config_key, MIN_DURATION, MAX_DURATION, duration, default_duration))
            return default_duration
