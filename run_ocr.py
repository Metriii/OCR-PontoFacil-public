import urllib.request

path = r'C:\Users\usr-ti02\Pontos\alexandre.jpg'
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

with open(path, 'rb') as f:
    data = f.read()

body_bytes = (
    ('--' + boundary + '\r\n').encode() +
    b'Content-Disposition: form-data; name="modelo"\r\n\r\n' +
    b'modelo-4\r\n' +
    ('--' + boundary + '\r\n').encode() +
    b'Content-Disposition: form-data; name="arquivos"; filename="alexandre.jpg"\r\n' +
    b'Content-Type: image/jpeg\r\n\r\n' +
    data + b'\r\n' +
    ('--' + boundary + '--\r\n').encode()
)

req = urllib.request.Request('http://localhost:8000/processar', data=body_bytes,
                            headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
r = urllib.request.urlopen(req, timeout=600)
print(r.read().decode('utf-8')[:500])
