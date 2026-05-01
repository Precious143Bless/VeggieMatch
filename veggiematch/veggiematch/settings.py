# settings.py
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ===================== DETECT PYTHONANYWHERE ENVIRONMENT =====================
ON_PYTHONANYWHERE = 'PYTHONANYWHERE_DOMAIN' in os.environ

# ===================== SECURITY SETTINGS =====================
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if os.getenv('DEBUG', 'False') == 'True' or ON_PYTHONANYWHERE:
        SECRET_KEY = 'dev-only-insecure-secret-key-do-not-use-in-production'
    else:
        raise RuntimeError('SECRET_KEY environment variable is not set.')

# ===================== HOSTS =====================
if ON_PYTHONANYWHERE:
    # Your PythonAnywhere domain
    ALLOWED_HOSTS = ['PreciousBless.pythonanywhere.com']
    DEBUG = False
else:
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

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'veggiematch.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# ===================== DATABASE (SQLite for PythonAnywhere) =====================
if ON_PYTHONANYWHERE:
    # Use SQLite on PythonAnywhere free tier
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }
else:
    # Local development - use SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ===================== STATIC & MEDIA FILES =====================
STATIC_URL = '/static/'
if ON_PYTHONANYWHERE:
    # FIXED: Updated paths for your nested structure
    STATIC_ROOT = '/home/PreciousBless/VeggieMatch/VeggieMatch/staticfiles'
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, 'static'),
    ]
    MEDIA_ROOT = '/home/PreciousBless/VeggieMatch/VeggieMatch/media'
else:
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    MEDIA_ROOT = BASE_DIR / 'media'

MEDIA_URL = '/media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===================== SESSION =====================
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ===================== HTTPS / SECURITY =====================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ===================== SEMAPHORE SMS =====================
SEMAPHORE_API_KEY = os.getenv('SEMAPHORE_API_KEY', '')
SEMAPHORE_SENDER = os.getenv('SEMAPHORE_SENDER', 'VeggieMatch')

# ===================== OTP & TIMER =====================
OTP_EXPIRY_MINUTES = 10
POST_TIMER_HOURS = 2
