"""
Settings module for BetterBundle Admin Dashboard
"""

import os
from decouple import config

# Determine which settings to use
ENVIRONMENT = config('ENVIRONMENT', default='development')

if ENVIRONMENT == 'production':
    from .production import *
else:
    from .development import *
