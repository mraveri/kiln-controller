import threading
import logging
import json
import time
import datetime
import pickle
import os
import subprocess
import re

# data analysis libraries:
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
from scipy.interpolate import interp1d
from scipy.integrate import trapz
from . import utilities as utilities

# email imports:
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from . import oven as Oven
log = logging.getLogger(__name__)

"""
import lib.utilities as utilities
import lib.ovenMonitor as ovenMonitor
import lib.oven as Oven

oven = Oven.Oven(simulate=True)
self = ovenMonitor.OvenMonitor(oven)
self.load_record_from_file('/Users/marco/Desktop/ceramics/kiln-controller/storage/history/2021_01_01-23_02.pickle')
analysis_settings = {}
filename = '.'
"""


class OvenMonitor(threading.Thread):

    def __init__(self, oven, analysis_settings={}):
        self.last_profile = None
        self.last_log = []
        self.started = None
        self.recording = False
        self.observers = []
        threading.Thread.__init__(self)
        self.daemon = True
        self.oven = oven
        self.analysis_settings = analysis_settings
        self.start()

    def run(self):
        while True:
            oven_state = self.oven.get_state()
            # record state for any new clients that join
            if oven_state.get("state") == self.oven.STATE_RUNNING:
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

    def record(self, profile, emails=[]):
        self.last_profile = profile
        self.last_log = []
        self.started = datetime.datetime.now()
        self.recording = True
        # add email recepients:
        self.email_destination = emails
        # we just turned on, add first state for nice graph
        self.last_log.append(self.oven.get_state())

    def add_observer(self, observer):
        if self.last_profile:
            p = {
                "name": self.last_profile.name,
                "data": self.last_profile.data,
                "type": "profile"
            }
        else:
            p = None

        backlog = {
            'type': "backlog",
            'profile': p,
            'log': self.lastlog_subset(),
        }
        print(backlog)
        backlog_json = json.dumps(backlog)
        try:
            print(backlog_json)
            observer.send(backlog_json)
        except:
            log.error("Could not send backlog to new observer")

        self.observers.append(observer)

    def notify_all(self, message):
        message_json = json.dumps(message)
        log.debug("sending to %d clients: %s" % (len(self.observers), message_json))
        for wsock in self.observers:
            if wsock:
                try:
                    wsock.send(message_json)
                except:
                    log.error("could not write to socket %s" % wsock)
                    self.observers.remove(wsock)
            else:
                self.observers.remove(wsock)

    def load_record_from_file(self, filename):
        """
        Load record from file:
        """
        # print feedback:
        log.info('Opening record file: ' + filename)
        # get the Pickled file:
        with open(filename, 'rb') as handle:
            tmp_dict = pickle.load(handle)
        self.__dict__.update(tmp_dict)

    def save_record_to_file(self, filename):
        """
        Save record to file:
        """
        # get file name:
        out_name = filename + '/' + self.started.strftime('%Y_%m_%d-%H_%M') + '.pickle'
        # print feedback:
        log.info('Saving out record to file: '+out_name)
        # save out as Pickle:
        out_dict = {'last_profile': self.__dict__['last_profile'],
                    'last_log': self.__dict__['last_log'],
                    'started': self.__dict__['started'],
                    'recording': self.__dict__['recording'],
                    'analysis_settings': self.__dict__['analysis_settings']}
        with open(out_name, 'wb') as handle:
            pickle.dump(out_dict, handle,
                        protocol=pickle.HIGHEST_PROTOCOL
                        )
        #
        return out_name

    def analyse_results(self, filename):
        """
        Produce analysis plots and analyse the data after the fire.
        """
        # print feedback:
        log.info('Analyzing results')

        # get analysis options:
        smoothing_scale = self.analysis_settings.get('smoothing_scale', 1./60.)
        unload_temperature = self.analysis_settings.get('unload_temperature', 122.)
        peak_zoom = self.analysis_settings.get('peak_zoom', 300.)

        # output product:
        results = []

        # get the data:
        time = np.array([event['runtime'] for event in self.last_log])
        time = (time - time[0]) / 3600.
        temperature = np.array([event['temperature'] for event in self.last_log])

        # interpolate data and get data on equispaced grid:
        temp_f = interp1d(time, temperature, kind='linear')
        equi_time = np.linspace(time[0], time[-1], len(time))
        time_spacing = equi_time[1] - equi_time[0]
        equi_temp = temp_f(equi_time)
        del(temp_f)

        # smooth the data with reflective boundaries to avoid artefacts:
        extra_ind = int(min(10 * smoothing_scale, time[-1]-time[0]) / time_spacing)
        up_tape = equi_temp[-extra_ind-1:-1][::-1]
        dn_tape = equi_temp[1:extra_ind+1][::-1]
        up_time = np.linspace(time[-1], time[-1] + time_spacing * extra_ind, extra_ind+1)[1:]
        dn_time = np.linspace(time[0] - time_spacing * extra_ind, time[0], extra_ind+1)[:-1]
        smooth_temp = utilities.smooth_gaussian(x=np.concatenate((dn_time, equi_time, up_time)),
                                                y=np.concatenate((dn_tape, equi_temp, up_tape)),
                                                sigma=smoothing_scale)[extra_ind:-extra_ind]

        # now cut the data to highlight the fire regime:
        filter = temperature > unload_temperature
        if np.all(np.logical_not(filter)):
            ind_min, ind_max = 0, len(filter)-1
        else:
            ind_min, ind_max = np.where(filter)[0][0], np.where(filter)[0][-1]
        temperature = temperature[ind_min:ind_max+1]
        time = time[ind_min:ind_max+1]

        filter = np.logical_and(time[0] <= equi_time, equi_time <= time[-1])
        if np.all(np.logical_not(filter)):
            ind_min, ind_max = 0, len(filter)-1
        else:
            ind_min, ind_max = np.where(filter)[0][0], np.where(filter)[0][-1]
        smooth_temp = smooth_temp[ind_min:ind_max+1]
        equi_time = equi_time[ind_min:ind_max+1]

        equi_time = equi_time - time[0]
        time = time - time[0]

        # fixed plot width per hour:
        cm_to_inch = 2.54
        plot_height = 10.  # in cm
        cm_per_hour = plot_height/2.
        plot_width = max(plot_height, cm_per_hour*time[-1])
        plot_height, plot_width = plot_height/cm_to_inch, plot_width/cm_to_inch

        ###############################################################
        # prepare report:
        report = {}
        # maximum temperature:
        report['max_t'] = np.amax(temperature)
        report['max_t_smooth'] = np.amax(smooth_temp)
        # fire duration:
        filter = temperature > unload_temperature
        report['fire_duration'] = trapz(filter.astype(np.float), x=time)

        ###############################################################
        # plot temperature and temperature derivative:
        fig, ax = plt.subplots(nrows=2, sharex=True, figsize=(plot_width, 2.*plot_height))

        # data:
        ax[0].plot(time, temperature, ls='-', lw=1., zorder=999, label='temp')
        ax[0].plot(equi_time, smooth_temp, ls='-', lw=1., zorder=999, label='avg temp')

        time_der = (equi_time[:-1]+equi_time[1:])/2.
        temperature_der = (smooth_temp[1:] - smooth_temp[:-1]) / (equi_time[1:] - equi_time[:-1])
        ax[1].plot(time_der, temperature_der, ls='-', lw=1., zorder=999)
        ax[1].axhline(0., ls='--', lw=1., color='k')

        # plot limits:
        ax[0].set_xlim([np.amin(time), np.amax(time)])
        ax[1].set_xlim([np.amin(time_der), np.amax(time_der)])

        # labels:
        ax[0].set_ylabel('temperature [F]')
        ax[1].set_xlabel('time [hours]')
        ax[1].set_ylabel('temperature ramp [F/hour]')

        # axis:
        for _ax in ax:
            _ax.xaxis.set_major_locator(MaxNLocator(nbins=max(5, int(np.amax(time))), integer=True))
            _ax.xaxis.set_minor_locator(AutoMinorLocator())
            _ax.yaxis.set_minor_locator(AutoMinorLocator())
            _ax.grid(which='major', lw=1., ls='--', zorder=0)
            _ax.grid(which='minor', lw=.5, ls='--', zorder=0)

        # finalize the plot:
        ax[0].set_title('Fire started '+self.started.strftime('%Y/%m/%d %H:%M'))
        ax[0].legend()
        plt.tight_layout()
        plt.savefig(filename+'/1_full_results.pdf')
        plt.close()
        results.append(filename+'/1_full_results.pdf')

        ###############################################################
        # plot around peak:
        T_max = report['max_t']
        temp_min = np.amin(temperature)
        T_min = max(temp_min, T_max - peak_zoom)

        if temp_min < T_min:

            fig, ax = plt.subplots(nrows=2, sharex=True, figsize=(plot_width, 2.*plot_height))

            # data:
            filter = temperature > T_min
            ax[0].plot(time[filter], temperature[filter], ls='-', lw=1., zorder=999)
            ax[0].set_xlim([np.amin(time[filter]), np.amax(time[filter])])

            filter = smooth_temp > T_min
            ax[0].plot(equi_time[filter], smooth_temp[filter], ls='-', lw=1., zorder=999)
            ax[1].plot(time_der[filter[1:]], temperature_der[filter[1:]], ls='-', lw=1., zorder=999)
            ax[1].set_xlim([np.amin(time_der[filter[1:]]), np.amax(time_der[filter[1:]])])

            # labels:
            ax[0].set_ylabel('temperature [F]')
            ax[1].set_xlabel('time [hours]')
            ax[1].set_ylabel('temperature ramp [F/hour]')

            # axis:
            for _ax in ax:
                _ax.xaxis.set_major_locator(MaxNLocator(nbins=max(5, int(np.amax(time))), integer=True))
                _ax.xaxis.set_minor_locator(AutoMinorLocator())
                _ax.yaxis.set_minor_locator(AutoMinorLocator())
                _ax.grid(which='major', lw=1., ls='--', zorder=0)
                _ax.grid(which='minor', lw=.5, ls='--', zorder=0)

            # finalize the plot:
            ax[0].set_title('Fire started '+self.started.strftime('%Y/%m/%d %H:%M'))
            plt.tight_layout()
            plt.savefig(filename+'/2_peak_results.pdf')
            plt.close()
            results.append(filename+'/2_peak_results.pdf')

        # print feedback:
        log.debug('Produced plots')
        #
        return results, report

    def send_email_report(self, filename, sender_name, sender_user, password):
        """
        Send email report of the firing
        """
        # print feedback:
        log.info('Sending email results')

        # save data out:
        record_path = self.save_record_to_file(filename)
        # plot files:
        plot_files, report = self.analyse_results(filename)
        # create message:
        msg = MIMEMultipart()
        msg['Subject'] = '[kiln report] ' + self.started.strftime('%Y/%m/%d %H:%M')
        msg['From'] = sender_name + ' <'+sender_user+'>'
        msg['To'] = ", ".join(self.email_destination)
        # email body:
        msg.attach(MIMEText('Raw peak temperature = '+str(round(report['max_t'], 2))+' F'+'\n' \
                   + 'Average peak temperature = '+str(round(report['max_t_smooth'], 2))+' F'+'\n' \
                   + 'Firing duration = '+str(round(report['fire_duration'], 3))+' hours'
                            ))
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

        # print feedback:
        log.debug('Email sent')

    def send_email_start(self, sender_name, sender_user, password):
        """
        Send email to monitor fire
        """
        # print feedback:
        log.info('Sending email at beginning of fire')

        # create message:
        msg = MIMEMultipart()
        msg['Subject'] = '[kiln report] ' + self.started.strftime('%Y/%m/%d %H:%M')
        msg['From'] = sender_name + ' <'+sender_user+'>'
        msg['To'] = ", ".join(self.email_destination)
        # get the address of the server:
        try:
            result = subprocess.run(['journalctl', '-u', 'internet_spawn.service'], stdout=subprocess.PIPE).stdout.decode('utf-8')
            result = [strings for strings in result.split('\n') if 'your url is:' in strings][-1]
            name = re.search('your url is: https://(.*).loca.lt', result).group(1)
            name = 'http://'+name+'.loca.lt'
        except Exception as ex:
            logging.error('internet_spawn.service does not seem to be running.')
            logging.error(ex)
            return

        # email body:
        msg.attach(MIMEText('Kiln monitor started, you can follow the fire at'+name+'\n'))
        # send the email:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(sender_user, password)
        server.send_message(msg)
        server.close()

        # print feedback:
        log.debug('Initial email sent')
