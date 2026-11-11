import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

PASSWORDS=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
DUMMY_HASH=PASSWORDS.hash('dummy account password does not authenticate')


def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def token(): return secrets.token_urlsafe(32)


def verify_password(encoded, value):
    try:return PASSWORDS.verify(encoded or DUMMY_HASH,value)
    except (VerificationError,InvalidHashError):return False
