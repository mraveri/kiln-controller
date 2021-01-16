import requests
import json
url="http://0.0.0.0:5001"
r = requests.post(url, json={1: (225, 0, 125, 5)})


test = '[1,2,3]'


clean_char = ['[', ']', '{', '}', '(', ')', ' ']
for ch in clean_char:
    test = test.replace(ch, '')

[int(n) for n in test.split(',')]



r._content

r.content

r.cookies
r.encoding
r.headers
r.json()

print(r)



pass
