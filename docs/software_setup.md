Kiln Monitor Software Set-up
============================

These instructions work for a headless set up that requires no external monitor but intensive command line work. It should be possible to do most of this with a monitor as well but I have not tried.

## General set-up

This part takes care of setting up the Raspberry and the OS. Each of this steps should have infinite tutorials online if needed.

In particular I use mac-os and I'll write commands for that. This should be morally similar for linux but definitely not for windows.

Main reference is this page:

    https://www.raspberrypi.org/documentation/configuration/wireless/headless.md

Start by burning the Raspbian image to an SD card.

    https://www.raspberrypi.org/software/

I use the Raspberry Pi OS (32 bits) other options might work as well.

After this is done we have to go to the SD card and mingle with it a bit.
Most of this material can be found looking online for a headless set up of the raspberry pi tutorial.
Go to the drive that was just installed (you might need to remove the SD and pop it in again).

    cd /Volumes/boot/

Then give the following command to enable ssh login:

    touch ssh

Then instruct the pi to connect to the wifi:

    touch wpa_supplicant.conf

This file contains the connection details that the pi will use.
Edit the wpa_supplicant.conf file following the instructions at:

    https://www.raspberrypi.org/documentation/configuration/wireless/headless.md
    https://www.raspberrypi.org/documentation/configuration/wireless/wireless-cli.md

Add all your wi-fi connections, as an example in my case my home wi-fi and studio wi-fi. My file looks something like this:

    ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
    update_config=1
    country=US

    network={
     ssid="name"
     psk="password"
     priority=1
     id_str="home"
    }

    network={
     ssid="name"
     psk="password"
     priority=2
     id_str="studio"
    }

Now the pi is ready to be powered up and configured. Remove the SD card and place it in the pi. Power it up and give it a little time to connect to the wi-fi. Then ssh to the raspberry as:

    ssh pi@raspberrypi.local

and, when prompted, give it the default password:

    raspberry

If you are not able to connect it might mean that the pi and the computer are not in the same network or that the wpa_supplicant.conf file is not properly configured.

Now we run a full system update:

    sudo apt-get update
    sudo apt-get full-upgrade -y

Leave the pi finish, it might take a while.
If connection drops in this stage it is likely that you have to restart the whole installation as a failure in updating likely corrupts the system.

Now we run the config script:

    sudo raspi-config

Navigating the script we make sure that:

1. 3p1 enable the camera
2. 3p4 enable SPI
3. 3p5 enable I2C
4. 5l2 to set the time zone
5. 6a1 to expand partition and use the full SD card

If you want to change the network name of the pi from the default raspberrypi you can edit the file:

    sudo nano /etc/hostname

then change raspberrypi to the name you chose in the file:

    sudo nano /etc/hosts

You should really do this if you plan to expose to the whole internet the monitor.

Now reboot with:

    sudo reboot

Notice that when you want to reconnect you have to use the new hostname.

**Setting up security:**

It is now time to step up the security of the pi. This is a crucial step to the security of the entire system and should not be overlooked.

We are planning to expose the pi to the whole internet so we need to be extra carefull.

We follow the instructions at:

    https://www.raspberrypi.org/documentation/configuration/security.md

Change password, take a note of the password and make it strong.

Then make sudo require a password.

Then we set up an ssh key login that does not require password, like https://www.raspberrypi.org/documentation/remote-access/ssh/passwordless.md#copy-your-public-key-to-your-raspberry-pi

And we disable the possibility of logging in without the password. This prevents any computer that does not have the key to log in the pi and makes the system far more secure.

## Kiln-Monitor installation

First we download the software from github:

    cd $HOME
    git clone https://github.com/mraveri/kiln-controller.git
    cd kiln-controller

If you want to reinstall the software just remove the kiln-controller folder and restart from here.

Then we use the installation script in the script directory:

    ./script/install_on_pi

This will go on for a while. You can check the script content to see what this is doing.

The installer creates two empty files: mail_credentials.txt and log_credentials.txt

The first file is used to set up email notifications.
Open mail_credentials and fill three lines with the email address that will send emails, the password and its name. I use a dummy gmail account and my credential file looks like this:

    name@gmail.com
    password
    Name Sending Email

The second file is used to protect connecting to the pi web interface.
Open the file and write:

    username
    password

These should definitely be different from your raspberry user and password.
These are not encrypted but should not be accessible from anybody that does
not have access to the physical pi and your computer...

If you want more security you can make these files accessible only to root:

    chmod 600 log_credentials.txt mail_credentials.txt
    sudo chown root:root log_credentials.txt mail_credentials.txt

Go to ngrok. Register and authenticate.

Then reboot the pi.

Now turn on the leds by:



Now turn on wi-fi management with led by giving:

    sudo ./script/wifi_setup

And since we want the monitor to run at startup we give:

    sudo ./script/start-monitor-on-boot

These are instructions for deployment, if you want to develop the code refer to the
standard instructions.

## LED

Blacklist audio, check if necessary
https://www.raspberrypi.org/forums/viewtopic.php?t=151460

Install all drivers, manually if necessary.
