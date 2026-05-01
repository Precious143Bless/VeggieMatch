# WSGI configuration for VeggieMatch Django project
import os
import sys

# ==================== PATHS ====================
# Your Django project path (inner folder where manage.py is)
DJANGO_PROJECT_PATH = '/home/PreciousBless/VeggieMatch/veggiematch'

# Add the project path to Python path
if DJANGO_PROJECT_PATH not in sys.path:
    sys.path.append(DJANGO_PROJECT_PATH)

# Add parent directory if needed
PARENT_PATH = '/home/PreciousBless/VeggieMatch'
if PARENT_PATH not in sys.path:
    sys.path.append(PARENT_PATH)

# ==================== DJANGO SETTINGS ====================
# Point to your Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'veggiematch.settings'

# ==================== VIRTUAL ENVIRONMENT ====================
# Activate virtual environment
VENV_PATH = '/home/PreciousBless/.virtualenvs/veggiematch-env'
activate_script = os.path.join(VENV_PATH, 'bin', 'activate_this.py')

try:
    if os.path.exists(activate_script):
        with open(activate_script) as f:
            exec(f.read(), {'__file__': activate_script})
    else:
        # Fallback: add virtual env site-packages to path
        site_packages = os.path.join(VENV_PATH, 'lib', 'python3.10', 'site-packages')
        if os.path.exists(site_packages):
            sys.path.insert(0, site_packages)
except Exception as e:
    print(f"Virtual environment activation warning: {e}")

# ==================== DJANGO APPLICATION ====================
# Initialize Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
