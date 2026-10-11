import hashlib
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from wifi_transport import endpoint,connect

class WifiTests(unittest.TestCase):
    def test_addresses_and_invalid_endpoints(self):
        self.assertEqual(endpoint('wifi://192.168.1.2'),('192.168.1.2',19674))
        self.assertEqual(endpoint('wifi://[::1]:19675'),('::1',19675))
        for value in ('http://phone','wifi://user@phone','wifi://phone/path','wifi://phone:0'):
            with self.assertRaises(ValueError):endpoint(value)

    def test_real_tls_pin_verification_before_application_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cert=root/'cert.pem';key=root/'key.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                '-keyout',str(key),'-out',str(cert),'-subj','/CN=desk-dockt-test'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            pin=hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
            listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(5)
            address='wifi://127.0.0.1:'+str(listener.getsockname()[1]);received=[]
            def serve():
                for _ in range(2):
                    peer,_=listener.accept()
                    with context.wrap_socket(peer,server_side=True) as secure:
                        try:received.append(secure.recv(1))
                        except (ConnectionResetError,BrokenPipeError):received.append(b'')
            thread=threading.Thread(target=serve);thread.start()
            try:
                with connect(address,pin) as secure:secure.sendall(b'Y')
                with self.assertRaises(ConnectionError):connect(address,'0'*64)
                thread.join(6);self.assertFalse(thread.is_alive());self.assertEqual(received,[b'Y',b''])
            finally:listener.close()
