import logging
import os
from passlib.hash import sha256_crypt
import lib.utilities as utilities

########################################################################
#
#   General options

# Logging
log_level = logging.INFO
log_format = '%(asctime)s %(levelname)s %(name)s: %(message)s'

# Server
listening_ip = "0.0.0.0"
listening_port = 8081

# Cost Estimate
kwh_rate = 0.18  # Rate in currency_type to calculate cost to run job
currency_type = "$"   # Currency Symbol to show when calculating cost to run job

########################################################################
#
#   GPIO Setup (BCM SoC Numbering Schema)
#
#   Check the RasPi docs to see where these GPIOs are
#   connected on the P1 header for your board type/rev.
#   These were tested on a Pi B Rev2 but of course you
#   can use whichever GPIO you prefer/have available.

# Outputs
gpio_heat = 23  # Switches zero-cross solid-state-relay
heater_invert = 0  # Switches the polarity of the heater control

### Thermocouple Adapter selection:
#   max31855 - bitbang SPI interface
#   max31855spi - kernel SPI interface
#   max6675 - bitbang SPI interface
max31855 = 1
max6675 = 0
max31855spi = 0 # if you use this one, you MUST reassign the default GPIO pins

### Thermocouple Connection (using bitbang interfaces)
gpio_sensor_cs = 27
gpio_sensor_clock = 22
gpio_sensor_data = 17

### Thermocouple SPI Connection (using adafrut drivers + kernel SPI interface)
spi_sensor_chip_id = 0

### duty cycle of the entire system in seconds. Every N seconds a decision
### is made about switching the relay[s] on & off and for how long.
### The thermocouple is read five times during this period and the highest
### value is used.
sensor_time_wait = 2

########################################################################
#
#   PID parameters

pid_kp = 25  # Proportional
pid_ki = 1088  # Integration
pid_kd = 217  # Derivative was 217

########################################################################
#
#   Temperature reading led:

gpio_led = 12

########################################################################
#
#   Simulation parameters

sim_t_env = 25.0  # deg C
sim_c_heat = 100.0  # J/K  heat capacity of heat element
sim_c_oven = 5000.0  # J/K  heat capacity of oven
sim_p_heat = 5450.0  # W    heating power of oven
sim_R_o_nocool = 1.0  # K/W  thermal resistance oven -> environment
sim_R_o_cool = 0.05  # K/W  " with cooling
sim_R_ho_noair = 0.1  # K/W  thermal resistance heat element -> oven
sim_R_ho_air = 0.05  # K/W  " with internal air circulation

########################################################################
#
#   Time and Temperature parameters

temp_scale = "f"  # c = Celsius | f = Fahrenheit - Unit to display
time_scale_slope = "h"  # s = Seconds | m = Minutes | h = Hours - Slope displayed in temp_scale per time_scale_slope
time_scale_profile = "m"  # s = Seconds | m = Minutes | h = Hours - Enter and view target time in time_scale_profile

# emergency shutoff the kiln if this temp is reached.
# when solid state relays fail, they usually fail closed.  this means your
# kiln receives full power until your house burns down.
# this should not replace you watching your kiln or use of a kiln-sitter
emergency_shutoff_temp = 2250

# not used yet
# if measured value is N degrees below set point
warning_temp_low = 5

# not used yet
# if measured value is N degrees above set point
warning_temp_high = 5

# thermocouple offset
# If you put your thermocouple in ice water and it reads 36F, you can
# set set this offset to -4 to compensate.  This probably means you have a
# cheap thermocouple.  Invest in a better thermocouple.
thermocouple_offset = 0

########################################################################
#
#   Analysis settings:

# smoothing scale for plots, in hours. Default is 1 minute
smoothing_scale = 1./60.
# cool temperature:
unload_temperature = 122.  # F for 50 C
# zoom around peak for plots:
peak_zoom = 300.

########################################################################
#
#   Authentication and email settings:
here = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger(__name__)


def helper_error_logging():
    log.critical('Error with authentication file. \n'
                 + 'Create the file: '+here+'/log_credentials.txt \n'
                 + 'With your choice of username and password to log to the kiln monitor \n'
                 + 'First line should be the desired username \n'
                 + 'Second line should be desired password'
                 )
    raise ValueError


def helper_error_mail():
    log.critical('Error with email credentials file. \n'
                 + 'Create the file: '+here+'/mail_credentials.txt \n'
                 + 'With your gmail email and password to be able to send emails \n'
                 + 'First line should be gmail email address \n'
                 + 'Second line should be gmail email password \n'
                 + 'Third line should be the human name that sends the email \n'
                 + 'We suggest creating a dummy gmail address for this.')
    raise ValueError


# import credentials for logging in:
if os.path.isfile(here+'/log_credentials.txt'):
    with open(here+'/log_credentials.txt', 'r') as file:
        log_cred = file.read()
else:
    helper_error_logging()

# import email logging credentials:
if os.path.isfile(here+'/mail_credentials.txt'):
    with open(here+'/mail_credentials.txt', 'r') as file:
        mail_cred = file.read()
else:
    helper_error_mail()

# now parse:
log_cred = log_cred.split('\n')
mail_cred = mail_cred.split('\n')

gmail_user = mail_cred[0]
gmail_password = mail_cred[1]
sender_name = mail_cred[2]

## if the credential file contains one line only we assume it has already be encrypted:
#if os.path.isfile(here+'/salt.txt'):
#    key = log_cred[0]
#    gmail_user = bytes(mail_cred[0], encoding='utf-8')
#    gmail_password = bytes(mail_cred[1], encoding='utf-8')
#    sender_name = bytes(mail_cred[2], encoding='utf-8')
#    with open(here+'/salt.txt', 'rb') as file:
#        salt = file.read()
#else:
#    uname = log_cred[0]
#    password = log_cred[1]
#    gmail_user = mail_cred[0]
#    gmail_password = mail_cred[1]
#    sender_name = mail_cred[2]
#    # hash uname and password:
#    key = sha256_crypt.hash(uname+password)
#    # encrypt the gmail credentials:
#    salt, cipher = utilities.generate_salt_cipher(uname+password, salt=None)
#    gmail_user = cipher.encrypt(bytes(gmail_user, encoding='utf-8'))
#    gmail_password = cipher.encrypt(bytes(gmail_password, encoding='utf-8'))
#    sender_name = cipher.encrypt(bytes(sender_name, encoding='utf-8'))
#    # write and replace the old files:
#    with open(here+'/log_credentials.txt', 'w') as file:
#        file.write(key)
#    with open(here+'/mail_credentials.txt', 'w') as file:
#        file.write(gmail_user.decode("utf-8")+'\n')
#        file.write(gmail_password.decode("utf-8")+'\n')
#        file.write(sender_name.decode("utf-8")+'\n')
#    with open(here+'/salt.txt', 'wb') as file:
#        file.write(salt)
#    # clean:
#    del uname, password
