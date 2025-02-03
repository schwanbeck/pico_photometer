try:
    from micropython import const
except ModuleNotFoundError:
    def const(arg):
        return arg
try:
    from ucollections import namedtuple
except ModuleNotFoundError:
    from collections import namedtuple

# unsigned 16 bit integer maximum
MAX_U16 = const(65535)

# Global PWM duty frequency to max u16 (no specific reason)
PWM_FREQUENCY = MAX_U16

# Set range of duty cycles to test, currently 0, 500, 1000, ..., 3500
# If only one is desired, for example 3500, set this to
# PWM_DUTY_CYCLES = [3500]
# PWM_DUTY_CYCLES = [i for i in range(0, PWM_FREQUENCY//2, 3000)]
# [0%, 4.5%, 13%, 25%, 50%, 100%]
PWM_DUTY_CYCLES = [
    0,
    # 3000,
    9000,
    PWM_FREQUENCY // 4,
    PWM_FREQUENCY // 2,
    PWM_FREQUENCY
]
# PWM_DUTY_CYCLES = [0, 9000, PWM_FREQUENCY // 4, PWM_FREQUENCY // 2, PWM_FREQUENCY]

# Pairs for LED anodes and photoresistor anodes
RESISTOR_LED_GPIO_PAIRS = [
    # (LED anode GPIO pin number, Resistor anode GPIO pin number)
    (0, 8),
    (1, 9),
    (2, 10),
    (3, 11),
    (4, 12),
    (5, 13),
    (6, 14),
    (7, 15),
]

# How often to repeat a measurement:
MEASUREMENT_REPEATS = const(11)
# How many seconds to wait between repeats (.2: 200 ms):
MEASUREMENT_REPEAT_INTERVAL_SECONDS = const(.2)
# How many seconds between each measurement cycle (300 = 5 minutes):
MEASUREMENT_FREQUENCY_SECONDS = const(900)
# How long to wait before a measurement for the first time (so LED is at right setting):
# @todo: 3
MEASUREMENT_LED_WARMUP_SECONDS = const(2)

# Total length of measurement for default values:
# 8 measurements * (2 warmup seconds + (5 repeats * .2 interval seconds)) equals roughly 24 seconds
# 8 measurements * (3 warmup seconds + (11 repeats * .2 interval seconds)) equals roughly 41.6 seconds

NR_LED_ANODE = 'NR_LED_ANODE'
PWM_LED_ANODE = 'PWM_LED_ANODE'
NR_RESISTOR_ANODE = 'NR_RESISTOR_ANODE'
PIN_RESISTOR_ANODE = 'PIN_RESISTOR_ANODE'
PWM_CORRECTIVE_RATIO = 'PWM_CORRECTIVE_RATIO'

DATE = 'Date'
CHANNEL = 'Channel'
DETECTOR = 'Detector'
INTENSITY = 'Intensity'

SEPERATOR = '\t'

# create namedtuple to hold LED and resistor pairs
NAMEDTUPLE_LED_RESISTOR_PAIR = namedtuple(
    "NAMEDTUPLE_LED_RESISTOR_PAIR",
    [
        NR_LED_ANODE,
        PWM_LED_ANODE,
        NR_RESISTOR_ANODE,
        PIN_RESISTOR_ANODE,
        PWM_CORRECTIVE_RATIO,
    ]
)

# Analog-to-Digital converter GPIO pins: 26, 27 and 28 (Pico W anyway)
# Future possibility to use more, cuts measurement time, but that shouldn't be critical
# See: https://www.raspberrypi.com/documentation/microcontrollers/images/pico-pinout.svg
PIN_ADC0 = const(26)
