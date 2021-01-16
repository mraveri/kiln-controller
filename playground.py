from flask import Flask, render_template, url_for, request, redirect, jsonify, abort
from flask_wtf import CSRFProtect, FlaskForm
import os

app = Flask(__name__)



@app.route('/', methods=['POST'])
def hello_world():

    if request.method == 'POST':
        command = request.get_json()
        for key in command.keys():

            #print(isinstance(key, int))
            print(type(key), type(command[key][0]))
            print(key, command[key])

            try:
                cmd = int(key)
            except ValueError:
                cmd = key

            print(list(command[cmd]))

            print(cmd)


    return jsonify(command), 200


from waitress import serve
#app.run(host='0.0.0.0', port=5001)
serve(app, host="0.0.0.0", port=5001)


pass
