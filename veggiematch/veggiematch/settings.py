# settings.py
from pathlib import Path
from dotenv import load_dotenv
import os
import dj_database_url
import re

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ===================== ENVIRONMENT DETECTION =====================
# Detect if running on Render.com or production
ON_RENDER = os.environ.get('RENDER') == 'true'
ON_SUPABASE = os.environ.get('DATABASE_URL') is not None

# ===================== SECURITY SETTINGS =====================
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if os.getenv('DEBUG', 'False') == 'True' or ON_RENDER:
        SECRET_KEY = 'dev-only-insecure-secret-key-do-not-use-in-production'
    else:
        raise RuntimeError('SECRET_KEY environment variable is not set.')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

# For production, set ALLOWED_HOSTS in .env as comma-separated values
if ON_RENDER:
    # Your Render.com domain (replace 'veggiematch' with your actual app name)
    ALLOWED_HOSTS = ['veggiematch.onrender.com', 'localhost', '127.0.0.1']
else:
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For serving static files
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
        'DIRS': [BASE_DIR / 'templates'],  # Add templates directory if exists
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

# ===================== DATABASE CONFIGURATION =====================
# Use PostgreSQL in production (Supabase/Render), SQLite for local development

if ON_RENDER or os.getenv('DATABASE_URL'):
    # Production: Use PostgreSQL (Supabase or Render PostgreSQL)
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise RuntimeError('DATABASE_URL environment variable is not set for production!')
    
    # Ensure SSL mode is set
    if 'sslmode' not in database_url:
        database_url += '?sslmode=require'
    
    # Force IPv4 connection by disabling IPv6 resolution
    # This helps with Render's IPv6 connectivity issues to Supabase
    import socket
    original_getaddrinfo = socket.getaddrinfo
    
    def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # Force IPv4 (AF_INET) instead of IPv6 (AF_INET6)
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    
    # Apply the IPv4-only patch
    socket.getaddrinfo = ipv4_only_getaddrinfo
    
    # Configure the database
    DATABASES = {
        'default': dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
    
    # Add connection options for better reliability and IPv4 forcing
    DATABASES['default']['OPTIONS'] = {
        'connect_timeout': 10,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
        'sslmode': 'require',
    }
    
    # Also try to extract and set hostaddr if possible (bypasses DNS)
    try:
        # Parse the host from DATABASE_URL
        host_match = re.search(r'@([^:/]+)', database_url)
        if host_match:
            original_host = host_match.group(1)
            # Try to resolve to IPv4 address
            import socket
            try:
                ipv4_addr = socket.gethostbyname(original_host)
                # Override host with IP address to force IPv4
                DATABASES['default']['HOST'] = ipv4_addr
            except socket.gaierror:
                pass
    except Exception:
        pass
        
else:
    # Local development: Use SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ===================== STATIC & MEDIA FILES =====================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Only add STATICFILES_DIRS if the directory exists
static_dir = BASE_DIR / 'static'
if static_dir.exists():
    STATICFILES_DIRS = [static_dir]
else:
    STATICFILES_DIRS = []  # Empty list if directory doesn't exist

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
if ON_RENDER:
    # On Render, media files go to the persistent disk (if you add one)
    # Without a disk, they will be ephemeral
    MEDIA_ROOT = '/var/data/media' if os.path.exists('/var/data') else BASE_DIR / 'media'
else:
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
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000   # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ===================== SEMAPHORE SMS =====================
SEMAPHORE_API_KEY = os.getenv('SEMAPHORE_API_KEY', '')
SEMAPHORE_SENDER = os.getenv('SEMAPHORE_SENDER', 'VeggieMatch')

# ===================== OTP & TIMER =====================
OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', '10'))
POST_TIMER_HOURS = int(os.getenv('POST_TIMER_HOURS', '2'))

# ===================== LOGGING =====================
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
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'ERROR',  # Change to 'DEBUG' to see SQL queries
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
