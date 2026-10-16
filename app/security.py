import base64
import hashlib
import hmac
import secrets
from urllib.parse import urlsplit
from . import config
from cryptography.fernet import Fernet


def hash_password(password):
    if len(password) < 12 or len(password) > 1024:
        raise ValueError('Use a password of 12–1024 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
    return base64.b64encode(salt + digest).decode()


def verify_password(password, stored):
    try:
        raw = base64.b64decode(stored)
        return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac('sha256', password.encode(), raw[:16], 600000))
    except (ValueError, TypeError): return False


def safe_public_url(url):
    try:
        p = urlsplit(url)
        import ipaddress
        host = p.hostname or ''
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443): return None
        if not host or '.' not in host or host.lower().endswith(('.local', '.internal', '.localhost')): return None
        try:
            if not ipaddress.ip_address(host).is_global: return None
        except ValueError: pass
        return url
    except ValueError: return None


def cipher():
    key = __import__('os').getenv('DOCUMENT_ENCRYPTION_KEY')
    if not key:
        path = config.DATA / 'document.key'
        import tempfile, os
        fd, temporary = tempfile.mkstemp(dir=config.DATA, prefix='.document-key-')
        try:
            with os.fdopen(fd,'wb') as f: f.write(Fernet.generate_key())
            try: os.link(temporary,path)
            except FileExistsError: pass
        finally: os.unlink(temporary)
        key = path.read_bytes()
    return Fernet(key)
