import requests
import json
url="http://0.0.0.0:5001"
r = requests.post(url, json={1: (225, 0, 125, 5)})



r._content

r.content

r.cookies
r.encoding
r.headers
r.json()

print(r)



pass
