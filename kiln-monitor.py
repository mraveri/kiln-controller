"""
This application only monitors the kiln without controlling it
"""
#!/usr/bin/env python

import os
import sys
import logging
import json

import bottle
import gevent
import geventwebsocket
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler
from geventwebsocket import WebSocketError

# import ngrok:
try:
    from pyngrok import ngrok
    has_ngrok = True
except Exception as ex:
    print(ex)
    has_ngrok = False

# Import config file:
try:
    sys.dont_write_bytecode = True
    import config
    sys.dont_write_bytecode = False
except:
    print("Could not import config file.")
    print("Copy config.py.EXAMPLE to config.py and adapt it for your setup.")
    exit(1)

logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger("kiln-monitor")
log.info("Starting kiln monitor")

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, script_dir + '/lib/')
profile_path = os.path.join(script_dir, "storage", "profiles")
history_path = os.path.join(script_dir, "storage", "history")

from lib.oven import Oven, Profile
from lib.ovenMonitor import OvenMonitor
import lib.utilities as utilities

app = bottle.Bottle()
oven = Oven()

# prepare settings and start monitor:
analysis_settings = {'smoothing_scale': config.smoothing_scale}
ovenMonitor = OvenMonitor(oven, analysis_settings=analysis_settings)

# spawn website:
if has_ngrok:
    try:
        tunnel = ngrok.connect(config.listening_port, "http",
                               name='kiln-monitor',
                               bind_tls=True,
                               inspect=False,
                               crt=script_dir+'/kiln-monitor.crt',
                               key=script_dir+'/kiln-monitor.key',
                               auth=config.uname+':'+config.password)
        ovenMonitor.tunnel_website = tunnel.public_url
        log.info("Monitor reachable at %s" % tunnel.public_url)
    except Exception as ex:
        logging.error(ex)
        has_ngrok = False


@app.route('/')
def index():
    return bottle.redirect('/picoreflow/index_monitor.html')


@app.post('/api')
def handle_api():
    log.info("/api is alive")
    log.info(bottle.request.json)

    # run a kiln schedule
    if bottle.request.json['cmd'] == 'run':
        wanted = bottle.request.json['profile']
        log.info('api requested run of profile = %s' % wanted)

        # start at a specific minute in the schedule
        # for restarting and skipping over early parts of a schedule
        startat = 0;
        if 'startat' in bottle.request.json:
            startat = bottle.request.json['startat']

        # get the wanted profile/kiln schedule
        profile = find_profile(wanted)
        if profile is None:
            return { "success" : False, "error" : "profile %s not found" % wanted }

        # FIXME juggling of json should happen in the Profile class
        profile_json = json.dumps(profile)
        profile = Profile(profile_json)
        oven.run_profile(profile, startat=startat)
        ovenMonitor.record(profile)

    if bottle.request.json['cmd'] == 'stop':
        log.info("api stop command received")
        oven.abort_run()

    return {"success": True}


def find_profile(wanted):
    '''
    given a wanted profile name, find it and return the parsed
    json profile object or None.
    '''
    # load all profiles from disk
    profiles = get_profiles()
    json_profiles = json.loads(profiles)

    # find the wanted profile
    for profile in json_profiles:
        if profile['name'] == wanted:
            return profile
    return None


@app.route('/picoreflow/:filename#.*#')
def send_static(filename):
    log.debug("serving %s" % filename)
    return bottle.static_file(filename, root=os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "public"))


def get_websocket_from_request():
    env = bottle.request.environ
    wsock = env.get('wsgi.websocket')
    if not wsock:
        log.critical('Expected WebSocket request.')
    return wsock

@app.route('/control')
def handle_control():
    wsock = get_websocket_from_request()
    log.info("websocket (control) opened")
    while True:
        try:
            message = wsock.receive()
            log.info("Received (control): %s" % message)
            msgdict = json.loads(message)
            if msgdict.get("cmd") == "RUN":
                log.info("RUN command received")
                profile_obj = msgdict.get('profile')
                emails = msgdict.get('mailto', '')
                emails = emails.replace(' ', '').split(',')
                emails = list(filter(None, emails))
                if profile_obj:
                    profile_json = json.dumps(profile_obj)
                    profile = Profile(profile_json)
                oven.run_profile(profile)
                ovenMonitor.record(profile, emails)
                if len(ovenMonitor.email_destination) > 0:
                    ovenMonitor.send_email_start(config.sender_name,
                                                 config.gmail_user,
                                                 config.gmail_password)
            elif msgdict.get("cmd") == "SIMULATE":
                log.info("SIMULATE command received")
                #profile_obj = msgdict.get('profile')
                #if profile_obj:
                #    profile_json = json.dumps(profile_obj)
                #    profile = Profile(profile_json)
                #simulated_oven = Oven(simulate=True, time_step=0.05)
                #simulation_watcher = OvenMonitor(simulated_oven)
                #simulation_watcher.add_observer(wsock)
                #simulated_oven.run_profile(profile)
                #simulation_watcher.record(profile)
            elif msgdict.get("cmd") == "STOP":
                log.info("Stop command received")
                oven.abort_run()
                # plot and send email:
                if len(ovenMonitor.email_destination) > 0:
                    ovenMonitor.send_email_report(history_path,
                                                  config.sender_name,
                                                  config.gmail_user,
                                                  config.gmail_password)
                else:
                    ovenMonitor.save_record_to_file(history_path)

        except WebSocketError as ex1:
            print('WebSocketError', ex1)
            break
        except TypeError as ex2:
            print('TypeError', ex2)
            break
    log.info("websocket (control) closed")


@app.route('/storage')
def handle_storage():
    wsock = get_websocket_from_request()
    log.info("websocket (storage) opened")
    while True:
        try:
            message = wsock.receive()
            if not message:
                break
            log.debug("websocket (storage) received: %s" % message)

            try:
                msgdict = json.loads(message)
            except:
                msgdict = {}

            if message == "GET":
                log.info("GET command received")
                wsock.send(get_profiles())
            elif msgdict.get("cmd") == "DELETE":
                log.info("DELETE command received")
                profile_obj = msgdict.get('profile')
                if delete_profile(profile_obj):
                  msgdict["resp"] = "OK"
                wsock.send(json.dumps(msgdict))
                #wsock.send(get_profiles())
            elif msgdict.get("cmd") == "PUT":
                log.info("PUT command received")
                profile_obj = msgdict.get('profile')
                #force = msgdict.get('force', False)
                force = True
                if profile_obj:
                    #del msgdict["cmd"]
                    if save_profile(profile_obj, force):
                        msgdict["resp"] = "OK"
                    else:
                        msgdict["resp"] = "FAIL"
                    log.debug("websocket (storage) sent: %s" % message)

                    wsock.send(json.dumps(msgdict))
                    wsock.send(get_profiles())
        except WebSocketError:
            break
    log.info("websocket (storage) closed")


@app.route('/config')
def handle_config():
    wsock = get_websocket_from_request()
    log.info("websocket (config) opened")
    while True:
        try:
            message = wsock.receive()
            wsock.send(get_config())
        except WebSocketError:
            break
    log.info("websocket (config) closed")


@app.route('/status')
def handle_status():
    wsock = get_websocket_from_request()
    ovenMonitor.add_observer(wsock)
    log.info("websocket (status) opened")
    while True:
        try:
            message = wsock.receive()
            wsock.send("Your message was: %r" % message)
        except WebSocketError:
            break
    log.info("websocket (status) closed")


###############################################################################
# Profile handling:


def get_profiles():
    try:
        profile_files = os.listdir(profile_path)
    except:
        profile_files = []
    profiles = []
    for filename in profile_files:
        with open(os.path.join(profile_path, filename), 'r') as f:
            profiles.append(json.load(f))
    return json.dumps(profiles)


def save_profile(profile, force=False):
    profile_json = json.dumps(profile)
    filename = profile['name']+".json"
    filepath = os.path.join(profile_path, filename)
    if not force and os.path.exists(filepath):
        log.error("Could not write, %s already exists" % filepath)
        return False
    with open(filepath, 'w+') as f:
        f.write(profile_json)
        f.close()
    log.info("Wrote %s" % filepath)
    return True


def delete_profile(profile):
    profile_json = json.dumps(profile)
    filename = profile['name']+".json"
    filepath = os.path.join(profile_path, filename)
    os.remove(filepath)
    log.info("Deleted %s" % filepath)
    return True


def get_config():
    return json.dumps({"temp_scale": config.temp_scale,
                       "time_scale_slope": config.time_scale_slope,
                       "time_scale_profile": config.time_scale_profile,
                       "kwh_rate": config.kwh_rate,
                       "currency_type": config.currency_type})

###############################################################################
# Main functions and run


def main():
    ip = config.listening_ip
    port = config.listening_port
    log.info("listening on %s:%d" % (ip, port))

    server = WSGIServer((ip, port), app,
                        handler_class=WebSocketHandler, certfile=script_dir+'/kiln-monitor.crt', keyfile=script_dir+'/kiln-monitor.key')
    server.serve_forever()


if __name__ == "__main__":
    main()
