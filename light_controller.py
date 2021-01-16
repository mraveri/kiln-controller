###############################################################################
# Initial imports:
###############################################################################

from flask import Flask, request, jsonify
from waitress import serve
import board
import neopixel
import time

###############################################################################
# Settings:
###############################################################################

num_leds = 8
neopixel_gpio_pin = board.D18
neopixel_brightness = 0.2
host = "0.0.0.0"
port = 5001

###############################################################################
# Predefined colors:
###############################################################################

RED = (255, 0, 0)
YELLOW = (255, 150, 0)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
PURPLE = (180, 0, 255)

###############################################################################
# Effects:
###############################################################################


def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        return (0, 0, 0)
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def color_chase(color, wait, pixels):
    for i in range(num_leds):
        pixels[i] = color
        time.sleep(wait)
        pixels.show()
    time.sleep(0.5)


def rainbow_cycle(wait, pixels):
    for j in range(255):
        for i in range(num_leds):
            rc_index = (i * 256 // num_leds) + j
            pixels[i] = wheel(rc_index & 255)
        pixels.show()
        time.sleep(wait)

###############################################################################
# Main app:
###############################################################################


def main():

    # initialize server:
    app = Flask(__name__)

    # initialize pixels:
    pixels = neopixel.NeoPixel(neopixel_gpio_pin,
                               num_leds,
                               brightness=neopixel_brightness)
    pixels.fill((0, 0, 0))

    # some initial fireworks:
    pixels.fill((0, 0, 0))
    color_chase(RED, 0.0, pixels)
    color_chase(YELLOW, 0.0, pixels)
    color_chase(GREEN, 0.0, pixels)
    color_chase(CYAN, 0.0, pixels)
    color_chase(BLUE, 0.0, pixels)
    color_chase(PURPLE, 0.0, pixels)
    rainbow_cycle(0, pixels)
    pixels.fill((0, 0, 0))
    pixels[0] = GREEN

    @app.route('/', methods=['POST'])
    def color_pixels():

        if request.method == 'POST':
            command = request.get_json()
            # execute effects first:
            for key in command.keys():
                if key == 'color_chase':
                    color_chase(command['color_chase'][0], command['color_chase'][1], pixels)
                elif key == 'rainbow_cycle':
                    rainbow_cycle(command['rainbow_cycle'], pixels)
                elif key == 'fill':
                    pixels.fill(command[key])
                elif key == 'brightness':
                    pixels.brightness = command[key]
            # set colors as instructed:
            for key in command.keys():
                try:
                    ind = int(key)
                    pixels[ind] = command[key]
                except ValueError:
                    pass
            # get state:
            state = {}
            for ind, pix in enumerate(pixels):
                state[ind] = list(list(pix))
            #
            return jsonify(state), 200

    serve(app, host=host, port=port)


if __name__ == '__main__':
    main()
