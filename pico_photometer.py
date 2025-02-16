#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2023 Julian Schwanbeck (schwan@umn.edu)
##Explanation
This file performs the photometer function.
This file is part of pico_photometer. pico_photometer is free software: you can distribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. pico_photometer is distributed in
the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with pico_photometer. If
not, see <https://www.gnu.org/licenses/>.
"""

import time
import sys
from micropython import opt_level
from machine import Pin, PWM, ADC  # , RTC
from ucollections import namedtuple
import os
from Photometer.constants import (
    PIN_ADC0,
    MEASUREMENT_REPEATS,
    SEPERATOR,
    PWM_FREQUENCY,
    MEASUREMENT_REPEAT_INTERVAL_SECONDS,
    MAX_U16,
    MEASUREMENT_LED_WARMUP_SECONDS,
    MEASUREMENT_FREQUENCY_SECONDS,
    RESISTOR_LED_GPIO_PAIRS,
    PWM_DUTY_CYCLES,
    NAMEDTUPLE_LED_RESISTOR_PAIR,
)

# import errno

# Change for code optimisation
# See https://docs.micropython.org/en/latest/library/micropython.html?highlight=const#micropython.opt_level
opt_level(0)

# Indicator LED for fun
WORKING_INDICATOR_LED = Pin("LED", mode=Pin.OUT, value=0)

MEASURE_ADC0 = ADC(Pin(PIN_ADC0))


def get_time_string() -> str:
    """ Return time string based on pico internal clock

    :return: Time string in the form of YYYYMMDD-HHMMSS
    """
    # timest"%04d-%02d-%02d %02d:%02d:%02d"%(timestamp[0:3] + timestamp[4:7])
    # return "%04d-%02d-%02d %02d:%02d:%02d"%(timestamp[0:3] + timestamp[4:7])
    # Both don't always work currently - mpremote setrtc argument is faulty
    lt = time.localtime()
    # lt = RTC.datetime()
    return f"{lt[0]}{lt[1]:02d}{lt[2]:02d}-{lt[3]:02d}{lt[4]:02d}{lt[5]:02d}"


class DummyWorkingLED:
    """ Dummy class in case a working LED pin can't be used. """

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def on(*args, **kwargs) -> None:
        pass

    @staticmethod
    def off(*args, **kwargs) -> None:
        pass


class Photometer:
    """ Raspberry Pico based fixed wavelength photometer

    """

    def __init__(
            self,
            measurement_led_warmup_seconds: float = MEASUREMENT_LED_WARMUP_SECONDS,
            measurement_repeats: int = MEASUREMENT_REPEATS,
            measurement_repeat_interval_seconds: float = MEASUREMENT_REPEAT_INTERVAL_SECONDS,
            measurement_frequency_seconds: int = MEASUREMENT_FREQUENCY_SECONDS,
            pwm_duty_cycles: list[int] = None,
            resistor_led_gpio_pairs: list[(int, int)] | None = None,
            write_path_accessible_for_pi: str | None = None,
            working_led: Pin | None = None,
            pwm_frequency: int = PWM_FREQUENCY,
            adc_pin: int | None = None,
    ):
        """ Initialize Photometer.

        # Example usage:
        photometer = Photometer(
            # Give the photoresistor 2 seconds to get up to speed:
            measurement_led_warmup_seconds=2,

            # Wait 200 ms between measurements:
            measurement_repeat_interval_seconds=.2,

            # Measure 5 times per sample:
            measurement_repeats=5,

            # Measure every 15 minutes:
            measurement_frequency_seconds=900,

            # Defaults to GPIO 0-7 for LEDs and GPIO 8-15 for photoresistors
            # ie. [(0, 8), (1, 9), ..., (7, 15)]
            resistor_led_gpio_pairs=None,

            # Optional, change according to whether it's a pico W or regular:
            working_led= Pin("LED", mode=Pin.OUT, value=0),
        )
        # Test if photoresistors and LEDs are working
        photometer.perform_self_test()
        # Start Measuring
        photometer.main_loop()

        :param measurement_led_warmup_seconds: Wait this long to let the LED shine before taking first measurement.
            Allows the Photoresistor to acclimatise.
        :param measurement_repeats: How many measurements to take
        :param measurement_repeat_interval_seconds: How long to wait in between measurements
        :param measurement_frequency_seconds: How long to wait between measurement cycles
        :param pwm_duty_cycles: List of lamp intensity values to test
        :param resistor_led_gpio_pairs: List of tuples indicating which GPIO pairs controls which LED/Photoresistor
        :param write_path_accessible_for_pi: Path for output .csv file
        :param working_led: Active measuring indicator LED, optional
        :param pwm_frequency: Frequency for PWM modulation, will be used to set LEDs to fully on
        :param adc_pin: GPIO number for analog-to-digital converter output, defaults to ADC0 / GPIO pin 26
        """

        assert any([resistor_led_gpio_pairs, RESISTOR_LED_GPIO_PAIRS]), \
            "No GPIO pairs specified!"
        self.working_led = working_led if working_led else DummyWorkingLED()
        self.adc = ADC(Pin(adc_pin if adc_pin is not None else PIN_ADC0))
        # Initialise time point
        self.utc_time_point_then = time.time()
        # Write to the PC that's controlling the Pi or supplied path
        self.file_path = f"/remote/{get_time_string()}_output.csv" if write_path_accessible_for_pi is None \
            else write_path_accessible_for_pi
        self.file_writable = True
        # self.dict_pins_led = {a: PWM(Pin(a), freq=PWM_FREQUENCY, duty_u16=0) for a in PINS_LED_ANODE}
        # self.dict_pins_resistors = {a: Pin(a, mode=Pin.OUT, value=0) for a in PINS_RESISTORS_ANODE}
        self.pwm_frequency = pwm_frequency
        # Take pairs of GPIO LED anodes / GPIO Resistor anodes and convert them into dictionary
        # Each entry holds the GPIO Pin value, as well as the initialized instance of the GPIO Pin
        # PWM anodes for LEDs are set to the global frequency and initialized with an off-duty cycle
        # Resistor anode pins are set to output pins and logical off
        # Named tuples are chosen as to have an easier time referencing values later
        self.dict_pin_pairs = {}

        for number, (pin_led, pin_resistor) in enumerate(
                # Go with RESISTOR_LED_GPIO_PAIRS unless resistor_led_gpio_pairs has been specified
                resistor_led_gpio_pairs if resistor_led_gpio_pairs else RESISTOR_LED_GPIO_PAIRS
        ):
            try:
                # This used to work but there appears to be a bug with PWM initialisation
                _pwm = PWM(Pin(pin_led, Pin.OUT, value=0), freq=self.pwm_frequency, duty_u16=0)
            except TypeError:
                _pwm = PWM(Pin(pin_led, Pin.OUT, value=0))
                _pwm.freq(self.pwm_frequency)
                _pwm.duty_u16(0)
            self.dict_pin_pairs[number] = NAMEDTUPLE_LED_RESISTOR_PAIR(
                NR_LED_ANODE=pin_led,
                PWM_LED_ANODE=_pwm,
                NR_RESISTOR_ANODE=pin_resistor,
                PIN_RESISTOR_ANODE=Pin(pin_resistor, mode=Pin.OUT, value=0),
                PWM_CORRECTIVE_RATIO=1,
            )

        # Convenience conversion so we can iterate over the keys
        self.keys_pin_pairs = list(self.dict_pin_pairs.keys())

        self.measurement_led_warmup_seconds = measurement_led_warmup_seconds
        self.measurement_repeat_interval_seconds = measurement_repeat_interval_seconds
        self.measurement_repeats = measurement_repeats
        self.measurement_frequency_seconds = measurement_frequency_seconds
        self.pwm_duty_cycles = pwm_duty_cycles if pwm_duty_cycles else PWM_DUTY_CYCLES
        # First round: perform measurement directly, don't wait for self.measurement_repeat_interval_seconds
        self.first_call = True

        self.reset_pins()

        print(self.file_path)

    @staticmethod
    def change_pair_settings(
            namedtuple_led_resistor_pair: namedtuple,
            value: int,
            corrective_ratio_value: float | None = None,
            photoresistor_gpio_on: bool = True,
    ) -> None:
        """ Function to set LED brightness via pulse width modulation and select/deselect photoresistor GPIO.

        The value for PWM has to be within [0, MAX_U16] and will be changed by the offset ratio defined for each LED.
        In case the ratio makes the value go over, MAX_U16 will be used instead.

        :param namedtuple_led_resistor_pair: used NAMEDTUPLE_LED_RESISTOR_PAIR instance
        :param value: value to set brightness to
        :param corrective_ratio_value: Overwrite the corrective_ratio_value if given,
            use namedtuple_led_resistor_pair corrective_ratio_value if None
        :param photoresistor_gpio_on: whether to switch on or off
        :return: None
        """

        assert 0 <= value <= MAX_U16, \
            f"Pulse width modulation outside of allowable range [0, {MAX_U16}]: {value}"
        assert corrective_ratio_value is None or 0 < corrective_ratio_value < 2, \
            f"Given ratio_value out of bounds (0, 2): {corrective_ratio_value}"

        _ratio_value = corrective_ratio_value if corrective_ratio_value else \
            namedtuple_led_resistor_pair.PWM_CORRECTIVE_RATIO

        # Set duty to given value times corrective ratio or MAX_U16, depending which is lower
        namedtuple_led_resistor_pair.PWM_LED_ANODE.duty_u16(
            int(min(value * _ratio_value, MAX_U16))
        )
        if photoresistor_gpio_on:
            namedtuple_led_resistor_pair.PIN_RESISTOR_ANODE.on()
        else:
            namedtuple_led_resistor_pair.PIN_RESISTOR_ANODE.off()

    @staticmethod
    def format_result(
            namedtuple_led_resistor_pair: namedtuple,
            led_duty_power: int,
            result_list: list[str | int],
    ) -> str:
        """ Format results, spaced by tabs.

        Time - nr LED anode - nr resistor anode - LED power - result(s)
        Uses NAMEDTUPLE_LED_RESISTOR_PAIR to get numbers of GPIO pin for LED and photoresistor

        :param namedtuple_led_resistor_pair: used NAMEDTUPLE_LED_RESISTOR_PAIR instance
        :param led_duty_power: used LED duty power setting
        :param result_list: list of results
        :return: Formatted result string for .csv
        """

        return SEPERATOR.join(
            str(i) for i in [
                get_time_string(),
                namedtuple_led_resistor_pair.NR_LED_ANODE,
                namedtuple_led_resistor_pair.NR_RESISTOR_ANODE,
                led_duty_power,
            ] + result_list
        )

    def reset_pins(self) -> None:
        """ Reset used GPIO pins to no output / off state

        :return: None
        """

        for pin_pair in self.dict_pin_pairs.values():
            self.change_pair_settings(
                namedtuple_led_resistor_pair=pin_pair,
                value=0,
                photoresistor_gpio_on=False,
            )
        # self.working_led.off()

    def read_light(
            self,
            adc_pin: int | None = None
    ) -> int:
        """ Read analog-to-digital converter output, defaults to ADC0 / GPIO pin 26

        :param adc_pin: GPIO number, defaults to ADC0 / GPIO pin 26 if None
        :return: 16 bit reading from ADC
        """

        if adc_pin is not None:
            return ADC(Pin(adc_pin)).read_u16()
        return self.adc.read_u16()

    def perform_measurement(
            self,
            namedtuple_led_resistor_pair: namedtuple,
            led_duty_power: int,
            measurement_led_warmup_seconds: int | None = None,
            measurement_repeats: int | None = None,
            measurement_repeat_interval_seconds: int | None = None,
            cleanup_after: bool = True,
    ) -> list[int]:
        """ Perform measurement on selected LED / photoresistor at specified LED duty power

        :param namedtuple_led_resistor_pair: used NAMEDTUPLE_LED_RESISTOR_PAIR instance
        :param led_duty_power: used LED duty power setting
        :param measurement_led_warmup_seconds: Specify to overwrite class measurement_led_warmup_seconds definition
        :param measurement_repeats: Specify to overwrite class measurement_repeats definition
        :param measurement_repeat_interval_seconds: Specify to overwrite class measurement_repeat_interval_seconds
            definition
        :param cleanup_after: Whether to switch off the LED and deselect the Photoresistor after measurement
        :return: list of measured results
        """

        result = []
        # Set values to default or specified
        measurement_repeats = self.measurement_repeats if measurement_repeats is None else measurement_repeats
        measurement_led_warmup_seconds = self.measurement_led_warmup_seconds if \
            measurement_led_warmup_seconds is None else measurement_led_warmup_seconds
        measurement_repeat_interval_seconds = self.measurement_repeat_interval_seconds if \
            measurement_repeat_interval_seconds is None else measurement_repeat_interval_seconds

        # Set LED duty power, select photoresistor
        self.change_pair_settings(
            namedtuple_led_resistor_pair=namedtuple_led_resistor_pair,
            value=led_duty_power,
        )

        if measurement_led_warmup_seconds:
            # Wait so photoresistor has time to acclimate
            time.sleep(measurement_led_warmup_seconds)

        # Measure n times, wait between measurements
        for i in range(0, measurement_repeats):
            result.append(self.read_light())
            time.sleep(measurement_repeat_interval_seconds)

        if cleanup_after:
            # Switch LED off, deselect photoresistor
            self.change_pair_settings(
                namedtuple_led_resistor_pair=namedtuple_led_resistor_pair,
                value=0,
                photoresistor_gpio_on=False,
            )
        return result

    def perform_self_test(self) -> None:
        """Perform check of all Photoresistors without and with light.

        To speed up the process, bring all to correct state, then do an abbreviated reading.
        End results are currently printed to screen for manual inspection, but could be automatically used.

        :return: None
        """

        dark_values = {}
        bright_values = {}

        # Switch off light, wait for acclimatisation
        self.reset_pins()
        time.sleep(2)
        # Get dark values
        for key in self.keys_pin_pairs:
            dark_values[key] = self.perform_measurement(
                namedtuple_led_resistor_pair=self.dict_pin_pairs[key],
                led_duty_power=0,
                measurement_led_warmup_seconds=0,
            )

        # Switch everything to maximum, which should be self.pwm_frequency, wait again for acclimatisation
        for key in self.keys_pin_pairs:
            self.change_pair_settings(
                namedtuple_led_resistor_pair=self.dict_pin_pairs[key],
                value=self.pwm_frequency,
                photoresistor_gpio_on=False,
            )
        time.sleep(2)
        # Get bright values
        for key in self.keys_pin_pairs:
            bright_values[key] = self.perform_measurement(
                namedtuple_led_resistor_pair=self.dict_pin_pairs[key],
                led_duty_power=self.pwm_frequency,
                measurement_led_warmup_seconds=0,
            )
        print('Average dark values:')
        for k, v in dark_values.items():
            print(f"GPIO LED {self.dict_pin_pairs[k].NR_LED_ANODE}: {sum(v) / len(v)} (min: {min(v)}, max: {max(v)})")
        print('Average bright values:')
        for k, v in bright_values.items():
            print(f"GPIO LED {self.dict_pin_pairs[k].NR_LED_ANODE}: {sum(v) / len(v)} (min: {min(v)}, max: {max(v)})")
        self.reset_pins()

    def perform_blank(self):
        # @todo: create self correcting blank function to set PWM_CORRECTIVE_RATIO
        pass

    def save_result(
            self,
            result: str,
    ) -> None:
        """ Print result, write result to file if possible.

        :param result: Result string
        :return: None
        """

        print(result)
        result += "\n"
        try:
            with open(self.file_path, 'a+') as f:
                f.write(result)
        except OSError as er:
            if self.file_writable:
                print(er)
                print(f"File could be written to. This warning will now be suppressed. \nFile: {self.file_path}")
                self.file_writable = False
            pass

    def measurement_cycle_save(
            self,
            namedtuple_led_resistor_pair: namedtuple,
            led_duty_power: int,
    ) -> None:
        """ Perform measurement, format results, then save result to file

        :param namedtuple_led_resistor_pair: used NAMEDTUPLE_LED_RESISTOR_PAIR instance
        :param led_duty_power: used LED duty power setting
        :return: None
        """

        result = self.perform_measurement(
            led_duty_power=led_duty_power,
            namedtuple_led_resistor_pair=namedtuple_led_resistor_pair,
        )
        result = self.format_result(
            namedtuple_led_resistor_pair=namedtuple_led_resistor_pair,
            led_duty_power=led_duty_power,
            result_list=result,
        )
        self.save_result(result)

    def measure_pwm_duty_cycles(self) -> None:
        """ Perform the whole measurement cycle with all LED/photoresistor pairs at every LED power setting

        :return: None
        """

        for key in self.keys_pin_pairs:
            for led_duty_power in self.pwm_duty_cycles:
                self.measurement_cycle_save(
                    namedtuple_led_resistor_pair=self.dict_pin_pairs[key],
                    led_duty_power=led_duty_power,
                )

    def has_time_passed(
            self,
    ) -> (bool, int):
        """ Check if time has passed since last measurement

        :return: True if time has passed / False otherwise, time remaining
        """

        now = time.time()
        delta = now - self.utc_time_point_then
        print(f"Time: {get_time_string()} ({now}) Last measurement: {self.utc_time_point_then} Delta: {delta} s")
        print(f"Next measurement in: {self.measurement_frequency_seconds - delta} s")
        if self.first_call or delta >= self.measurement_frequency_seconds:
            self.first_call = False
            self.utc_time_point_then = now
            return True, self.measurement_frequency_seconds - delta
        return False, self.measurement_frequency_seconds - delta

    def main_loop(self) -> None:
        """ Main function loop

        Waits until time has passed, then starts to measure.
        Working LED is set to on (if it exists) to indicate active measuring.

        :return: None
        """

        try:
            while True:
                while True:
                    # Wait for time to pass, print remaining time
                    has_time_passed, current_timedelta = self.has_time_passed()
                    if has_time_passed:
                        break
                    # Count down in minutes so we can see progress on StdOut
                    time.sleep(int(min(current_timedelta, 60)))
                    # Could replace with machine.idle() / .lightsleep(), might need different data recording method

                # Measure
                self.working_led.on()
                self.measure_pwm_duty_cycles()
                self.working_led.off()
        # except KeyboardInterrupt:
        #     pass
        except Exception as ex:
            # exc_type, exc_obj, exc_tb = sys.exc_info()
            # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            # print(exc_type, fname, exc_tb.tb_lineno)
            print(f"{ex}")
            try:
                with open('./error.log', ) as f:
                    f.write(f"{ex}")
            except OSError:
                pass
        finally:
            self.reset_pins()
            self.working_led.off()


if __name__ == "__main__":
    print(os.getcwd())
    photometer = Photometer(
        measurement_led_warmup_seconds=MEASUREMENT_LED_WARMUP_SECONDS,
        measurement_repeat_interval_seconds=MEASUREMENT_REPEAT_INTERVAL_SECONDS,
        measurement_repeats=MEASUREMENT_REPEATS,
        measurement_frequency_seconds=MEASUREMENT_FREQUENCY_SECONDS,
        resistor_led_gpio_pairs=None,
        working_led=WORKING_INDICATOR_LED,
    )
    try:
        photometer.perform_self_test()
        photometer.main_loop()
    except KeyboardInterrupt:
        print("Keyboard Interrupt")
    finally:
        photometer.reset_pins()
        sys.exit()
