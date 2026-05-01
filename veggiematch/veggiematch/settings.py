# settings.py
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ===================== ENVIRONMENT DETECTION =====================
# Detect if running on Render.com
ON_RENDER = os.environ.get('RENDER') == 'true'
# Detect if running on PythonAnywhere (legacy)
ON_PYTHONANYWHERE = 'PYTHONANYWHERE_DOMAIN' in os.environ

# ===================== SECURITY SETTINGS =====================
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if os.getenv('DEBUG', 'False') == 'True' or ON_RENDER or ON_PYTHONANYWHERE:
        SECRET_KEY = 'dev-only-insecure-secret-key-do-not-use-in-production'
    else:
        raise RuntimeError('SECRET_KEY environment variable is not set.')

# ===================== HOSTS =====================
if ON_RENDER:
    # Your Render.com domain (replace 'veggiematch' with your actual app name)
    ALLOWED_HOSTS = ['veggiematch.onrender.com', 'localhost', '127.0.0.1']
    DEBUG = False
elif ON_PYTHONANYWHERE:
    # Your PythonAnywhere domain
    ALLOWED_HOSTS = ['PreciousBless.pythonanywhere.com', 'localhost', '127.0.0.1']
    DEBUG = False
else:
    # Local development
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']
    DEBUG = os.getenv('DEBUG', 'False') == 'True'

# ===================== INSTALLED APPS =====================
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

# ===================== MIDDLEWARE =====================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For serving static files on Render
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'veggiematch.urls'

# ===================== TEMPLATES =====================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Add templates directory
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'veggiematch.wsgi.application'

# ===================== DATABASE =====================
# SQLite configuration for all environments

if ON_RENDER:
    # On Render.com - use persistent disk at /var/data
    # Make sure you've added a persistent disk mounted at /var/data
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': '/var/data/db.sqlite3',  # Persistent disk path
        }
    }
elif ON_PYTHONANYWHERE:
    # On PythonAnywhere
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }
else:
    # Local development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ===================== STATIC & MEDIA FILES =====================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Additional static files directories
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # Custom static files
]

# WhiteNoise compression for better performance
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (user uploads)
MEDIA_URL = '/media/'
if ON_RENDER:
    # On Render.com - store media on persistent disk
    MEDIA_ROOT = '/var/data/media'
elif ON_PYTHONANYWHERE:
    # On PythonAnywhere - use absolute path
    MEDIA_ROOT = '/home/PreciousBless/VeggieMatch/VeggieMatch/media'
else:
    # Local development
    MEDIA_ROOT = BASE_DIR / 'media'

# Create media directory if it doesn't exist
if not os.path.exists(MEDIA_ROOT):
    os.makedirs(MEDIA_ROOT, exist_ok=True)

# ===================== SESSION =====================
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ===================== DEFAULT PRIMARY KEY =====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===================== HTTPS / SECURITY =====================
if not DEBUG:
    # Redirect all HTTP to HTTPS
    SECURE_SSL_REDIRECT = True
    # HTTP Strict Transport Security (HSTS)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Additional security headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ===================== SEMAPHORE SMS (Philippines) =====================
SEMAPHORE_API_KEY = os.getenv('SEMAPHORE_API_KEY', '')
SEMAPHORE_SENDER = os.getenv('SEMAPHORE_SENDER', 'VeggieMatch')

# ===================== OTP & TIMER SETTINGS =====================
# OTP expiry in minutes
OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', '10'))

# Default post timer in hours
POST_TIMER_HOURS = int(os.getenv('POST_TIMER_HOURS', '2'))

# ===================== LOGGING (for debugging) =====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'core': {  # Your app logs
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ===================== ADDITIONAL RENDER.COM SETTINGS =====================
if ON_RENDER:
    # Disable Django's automatic database connections to prevent timeouts
    CONN_MAX_AGE = 0
    # Ensure proper proxy headers handling
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
    USE_X_FORWARDED_PORT = True

# ===================== DISABLE HTTPS REDIRECT FOR LOCAL DEVELOPMENT =====================
if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False