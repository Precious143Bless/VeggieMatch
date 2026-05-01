# Simple WSGI configuration for Django
import os
import sys

# Add your project directory to the path
path = '/home/PreciousBless/VeggieMatch/veggiematch'
if path not in sys.path:
    sys.path.append(path)

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'veggiematch.settings'

# Set Python path for virtual environment
venv_path = '/home/PreciousBless/.virtualenvs/veggiematch-env/lib/python3.10/site-packages'
if os.path.exists(venv_path):
    sys.path.append(venv_path)

# Create WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
