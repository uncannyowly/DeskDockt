"""Direct TLS connection, authenticated by a phone-displayed SHA-256 pin."""
import hashlib
import hmac
import socket
import ssl
from urllib.parse import urlsplit

def endpoint(value):
    parsed=urlsplit(value)
    if parsed.scheme!='wifi' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Use wifi://PHONE_ADDRESS:PORT')
    port=19674 if parsed.port is None else parsed.port
    if not 1024<=port<=65535:raise ValueError('Wi-Fi port must be between 1024 and 65535')
    return parsed.hostname,port

def connect(value,fingerprint):
    host,port=endpoint(value)
    pin=fingerprint.replace(':','').replace(' ','').lower()
    if len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):
        raise ValueError('Copy the TLS SHA-256 fingerprint displayed on the phone')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    # This self-signed device certificate is verified by its out-of-band pin below.
    context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
    raw=socket.create_connection((host,port),timeout=8)
    try:
        secure=context.wrap_socket(raw,server_hostname=host)
        digest=hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest()
        if not hmac.compare_digest(digest,pin):
            secure.close();raise ConnectionError('Phone certificate does not match. Check the fingerprint on the phone.')
        return secure
    except Exception:raw.close();raise
