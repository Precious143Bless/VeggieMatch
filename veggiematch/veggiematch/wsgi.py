# WSGI configuration for VeggieMatch
import os
import sys

# IMPORTANT: Point to the inner folder where manage.py is
path = '/home/PreciousBless/VeggieMatch/veggiematch'
if path not in sys.path:
    sys.path.append(path)

# Add parent directory to path as well (for imports)
parent_path = '/home/PreciousBless/VeggieMatch'
if parent_path not in sys.path:
    sys.path.append(parent_path)

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'veggiematch.settings'

# Activate virtual environment
activate_this = '/home/PreciousBless/.virtualenvs/veggiematch-env/bin/activate_this.py'
try:
    with open(activate_this) as file_:
        exec(file_.read(), dict(__file__=activate_this))
except FileNotFoundError:
    pass

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
