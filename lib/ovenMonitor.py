import threading
import logging
import json
import time
import datetime
import pickle
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


from oven import Oven
log = logging.getLogger(__name__)


class OvenMonitor(threading.Thread):

    def __init__(self, oven):
        self.last_profile = None
        self.last_log = []
        self.started = None
        self.recording = False
        self.observers = []
        threading.Thread.__init__(self)
        self.daemon = True
        self.oven = oven
        self.start()

# FIXME - need to save runs of schedules in near-real-time
# FIXME - this will enable re-start in case of power outage
# FIXME - re-start also requires safety start (pausing at the beginning
# until a temp is reached)
# FIXME - re-start requires a time setting in minutes.  if power has been
# out more than N minutes, don't restart
# FIXME - this should not be done in the Watcher, but in the Oven class

    def run(self):
        while True:
            oven_state = self.oven.get_state()
            # record state for any new clients that join
            if oven_state.get("state") == Oven.STATE_RUNNING:
                self.last_log.append(oven_state)
            else:
                self.recording = False
            self.notify_all(oven_state)
            time.sleep(self.oven.time_step)

    def lastlog_subset(self, maxpts=50):
        '''send about maxpts from lastlog by skipping unwanted data'''
        totalpts = len(self.last_log)
        if (totalpts <= maxpts):
            return self.last_log
        every_nth = int(totalpts / (maxpts - 1))
        return self.last_log[::every_nth]

    def record(self, profile):
        self.last_profile = profile
        self.last_log = []
        self.started = datetime.datetime.now()
        self.recording = True
        # we just turned on, add first state for nice graph
        self.last_log.append(self.oven.get_state())

    def add_observer(self,observer):
        if self.last_profile:
            p = {
                "name": self.last_profile.name,
                "data": self.last_profile.data,
                "type" : "profile"
            }
        else:
            p = None

        backlog = {
            'type': "backlog",
            'profile': p,
            'log': self.lastlog_subset(),
            #'started': self.started
        }
        print (backlog)
        backlog_json = json.dumps(backlog)
        try:
            print (backlog_json)
            observer.send(backlog_json)
        except:
            log.error("Could not send backlog to new observer")

        self.observers.append(observer)

    def notify_all(self, message):
        message_json = json.dumps(message)
        log.debug("sending to %d clients: %s"%(len(self.observers),message_json))
        for wsock in self.observers:
            if wsock:
                try:
                    wsock.send(message_json)
                except:
                    log.error("could not write to socket %s"%wsock)
                    self.observers.remove(wsock)
            else:
                self.observers.remove(wsock)

    def load_record_from_file(self, filename):
        """
        Load record from file:
        """
        # get date stamp:
        name = os.path.basename(filename).split('.')[0]
        date = datetime.datetime.strptime(name, '%Y_%m_%d-%H_%M')
        # get the Pickled file:
        with open(name, 'rb') as handle:
            self.last_log = pickle.load(handle)

    def save_record_to_file(self, filename):
        """
        Save record to file:
        """
        # get file name:
        out_name = filename + '/' + self.started.strftime('%Y_%m_%d-%H_%M') + '.pickle'
        # print feedback:
        log.info('Saving out record to file: '+out_name)
        # save out as Pickle:
        with open(out_name, 'wb') as handle:
            pickle.dump(self.last_log, handle, protocol=pickle.HIGHEST_PROTOCOL)
        #
        return out_name

    def produce_plots(self, filename):
        """
        Produce analysis plots
        """
        # output product:
        results = []

        # get the data:
        time = np.array([event['runtime'] for event in self.last_log])
        time = (time - time[0]) / 3600.
        temperature = np.array([event['temperature'] for event in self.last_log])

        # fixed plot width per hour:
        cm_to_inch = 2.54
        plot_height = 10. # in cm
        cm_per_hour = plot_height/2.
        plot_width = max(plot_height, cm_per_hour*time[-1])

        ###############################################################
        # plot temperature:
        fig, ax = plt.subplots(figsize=(plot_height/cm_to_inch, plot_width/cm_to_inch))
        ax.plot(time, temperature, ls='-', lw=1., zorder=999)
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        plt.grid(which='major', lw=1., ls='--', zorder=0)
        plt.grid(which='minor', lw=.5, ls='--', zorder=0)
        plt.xlim([np.amin(time), np.amax(time)])
        plt.title('Fire started '+self.started.strftime('%Y/%m/%d %H:%M'))
        plt.xlabel('time [hours]')
        plt.ylabel('temperature [F]')
        plt.tight_layout()
        plt.savefig(filename+'/1_temperature.pdf')
        plt.close()
        results.append(filename+'/1_temperature.pdf')

        ###############################################################
        # plot temperature variation:
        time_der = (time[:-1]+time[1:])/2.
        temperature_der = (temperature[1:] - temperature[:-1]) / (time[1:] - time[:-1])

        fig, ax = plt.subplots(figsize=(plot_height/cm_to_inch, plot_width/cm_to_inch))
        ax.plot(time_der, temperature_der, ls='-', lw=1., zorder=999)
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        plt.grid(which='major', lw=1., ls='--', zorder=0)
        plt.grid(which='minor', lw=.5, ls='--', zorder=0)
        plt.xlim([np.amin(time_der), np.amax(time_der)])
        plt.title('Fire started '+self.started.strftime('%Y/%m/%d %H:%M'))
        plt.xlabel('time [hours]')
        plt.ylabel('temperature ramp [F/hour]')
        plt.tight_layout()
        plt.savefig(filename+'/2_temperature_ramp.pdf')
        plt.close()
        results.append(filename+'/2_temperature_ramp.pdf')

        #
        return results

    def send_email_report(self, filename, sender_name, sender_user,
                          destination, password):
        """
        Send email report of the firing
        """
        # save data out:
        record_path = self.save_record_to_file(filename)
        # plot files:
        plot_files = self.produce_plots(filename)
        # create message:
        msg = MIMEMultipart()
        msg['Subject'] = '[kiln report] ' + self.started.strftime('%Y/%m/%d %H:%M')
        msg['From'] = sender_name + ' <'+sender_user+'>'
        msg['To'] = ", ".join(destination)
        # attach plots:
        for plot in plot_files:
            msg.attach(MIMEText('\n\n', "plain"))
            with open(plot, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
            attach.add_header('Content-Disposition', 'attachment',
                              filename=str(os.path.basename(plot)))
            msg.attach(attach)
        # attach raw data:
        msg.attach(MIMEText('\n\n', "plain"))
        with open(record_path, "rb") as f:
            attach = MIMEApplication(f.read(), _subtype="pdf")
        attach.add_header('Content-Disposition', 'attachment',
                          filename=str(os.path.basename(record_path)))
        msg.attach(attach)
        # send the email:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(sender_user, password)
        server.send_message(msg)
        server.close()
