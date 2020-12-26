Kiln Monitor Hardware Set-up
============================

To make this minimal electronic soldering capabilities are needed.

## Parts

### Enclosure:

You can pick the enclosure you prefer.
The file (link) contains a 3D model of the one we use and that can be mounted on a camera stand. This has the space to mount all the things that are needed.
The model can be 3D printed relatively easily.

1. Enclosure (3d print model)
2. Screws (list sizes)
3. Camera stand bolt (dimensions?)

### Raspberry and Thermocouple:

These go as in the main readme with the addition of status leds and camera for monitoring.

1. Raspberry pi zero w
2. USB and HDMI adapters for external monitor and keyboard
3. Power adapter for pi
4. SD card fast and 16 Gb
5. Heat sink
6. Camera module
7. Thermocouple amplifier
8. Thermocouple and thermocouple cable
9. 3 led of possibly different color, 3 resistors (what value)
10. misc cables to solder

### Other things you might need:x

But not necessarily.

1. Electronic soldering equipment
2. Screwdrivers of different sizes (most noticeably M1, M2, M3 that are less common)
3. 3D printer for enclosure
4. a wi-fi connection (although probably not really necessary)


## Mounting


Soldering work

Thermocouple reader to GPIO


### External status leds:

The pi puts out about 3.3V from its ports. Depending on the leds you have use
an online tool like:

https://ohmslawcalculator.com/led-resistor-calculator

to dimension the resistence that goes with the led.

**Power led**

Power led to serial
GPIO14 pin 8, GND pin 6



Two led to GPIO

GPIO12 pin 32, GND pin 30
GPIO16 pin 36, GND pin 34
