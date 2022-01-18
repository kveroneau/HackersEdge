import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

SECRET_KEY = 'XXXX'

ADMINS = (
    ('Your Name', 'your_email@example.com'),
)
MANAGERS = ADMINS
DEBUG = True
TEMPLATE_DEBUG = DEBUG
INTERNAL_IPS = ('127.0.0.1',)

ALLOWED_HOSTS = []

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'fluent_dashboard',
    'admin_tools',
    'admin_tools.theming',
    'admin_tools.menu',
    'admin_tools.dashboard',
    'django.contrib.admin',
    'debug_toolbar',
    'django_extensions',
    'registration',
    'captcha',
    'south',
    'selectable',
    'dajaxice',
    'dajax',
    'accounts',
    'forums',
    'help_center',
    'pm',
    'henet'
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

AUTHENTICATION_BACKENDS = (
    'accounts.backends.OTPAuth',
)

ROOT_URLCONF = 'hedemos.urls'
WSGI_APPLICATION = 'hedemos.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(PROJECT_ROOT, 'sqlite.db'),
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache',
    }
}
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_L10N = True
USE_TZ = True

MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media')
MEDIA_URL = 'http://localhost:8080/'
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'static')
STATIC_URL = '/s/'
STATICFILES_DIRS = (
    os.path.join(PROJECT_ROOT, 'assets'),
)
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'dajaxice.finders.DajaxiceFinder',
)
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'django.template.loaders.eggs.Loader',
)
TEMPLATE_DIRS = (
    os.path.join(PROJECT_ROOT, 'templates'),
)
TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.request',
    'accounts.context_processors.open_access',
)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DAJAXICE_MEDIA_PREFIX = 'AJAX'
#LOGIN_URL = '/accounts/login/'
LOGIN_URL = '/index.xml#/accounts/login.xml'
LOGIN_REDIRECT_URL = '/accounts/Characters/'

ACCOUNT_ACTIVATION_DAYS = 7

RECAPTCHA_PUBLIC_KEY = 'XXXX'
RECAPTCHA_PRIVATE_KEY = 'XXXX'

ADMIN_TOOLS_INDEX_DASHBOARD = 'fluent_dashboard.dashboard.FluentIndexDashboard'
ADMIN_TOOLS_APP_INDEX_DASHBOARD = 'fluent_dashboard.dashboard.FluentAppIndexDashboard'
ADMIN_TOOLS_MENU = 'fluent_dashboard.menu.FluentMenu'
ADMIN_MEDIA_PREFIX = STATIC_URL+'admin/'

FLUENT_DASHBOARD_APP_ICONS = {
    'forums/post': 'view-calendar-journal.png',
    'forums/thread': 'view-conversation-balloon.png',
    'forums/topic': 'folder.png',
    'help_center/topic': 'folder-txt.png',
    'help_center/guide': 'view-choose.png',
    'accounts/character': 'preferences-contact-list.png',
    'accounts/hostpool': 'server-database.png',
    'accounts/userprofile': 'preferences-contact-list.png',
    'accounts/invite': 'feed-subscribe.png',
    'pm/todoitem': 'mail-mark-task.png',
    'pm/category': 'folder-favorites.png',
    'pm/snippet': 'documentation.png',
    'henet/hostfile': 'system-file-manager.png',
    'henet/hosttemplate': 'utilities-file-archiver.png',
    'henet/machineconnector': 'preferences-plugin.png',
    'henet/machinetype': 'utilities-system-monitor.png',
}

FLUENT_DASHBOARD_APP_GROUPS = (
    ('Forum', {
        'models': ('forums.*',),
    }),
    ('Help Center', {
        'models': ('help_center.*',),
    }),
    ('Administration', {
        'models': (
            'django.contrib.auth.*',
            'django.contrib.sites.*',
            'registration.*',
        ),
    }),
    ("Hacker's Edge", {
        'models': (
            'accounts.*',
            'henet.models.MachineConnector',
            'henet.models.MachineType',
        ),
    }),
    ("Mission Designer", {
        'models': (
            'henet.models.HostTemplate',
            'henet.models.HostFile',
        ),
    }),
    ("Project Management", {
        'models': ('pm.*',),
    }),
    ('Applications', {
        'models': ('*',),
        'module': 'AppList',
        'collapsible': True,
    }),
)

# Hacker's Edge specific settings
GAME_SERVER = 'http://localhost:4080/'
SVN_URL = 'XXXX'
HACKER_TOKEN = '12345'

# Twitter settings
TOKEN = 'XXXX'
TOKEN_KEY = 'XXXX'
CONSUMER_SECRET = 'XXXX'
CONSUMER_KEY = 'XXXX'
