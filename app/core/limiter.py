from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize Limiter using Client IP
limiter = Limiter(key_func=get_remote_address)