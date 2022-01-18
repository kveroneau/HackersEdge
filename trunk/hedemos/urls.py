from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic.base import TemplateView
from hedemos.views import contact, index, login, logout
from dajaxice.core import dajaxice_config, dajaxice_autodiscover
from registration.backends.default.views import ActivationView
from django.contrib.auth import views as auth_views
from accounts.views import Terminal, VT100, Register

admin.autodiscover()
dajaxice_autodiscover()

auth_urls = patterns('',
                       url(r'^login/$',
                           auth_views.login,
                           {'template_name': 'registration/login.html'},
                           name='auth_login'),
                       url(r'^logout/$',
                           auth_views.logout,
                           {'template_name': 'registration/logout.html'},
                           name='auth_logoutx'),
                       url(r'^password/change/$',
                           auth_views.password_change,
                           name='auth_password_change'),
                       url(r'^password/change/done/$',
                           auth_views.password_change_done,
                           name='password_change_done'),
                       url(r'^password/reset/$',
                           auth_views.password_reset,
                           name='auth_password_reset'),
                       url(r'^password/reset/confirm/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$',
                           auth_views.password_reset_confirm,
                           name='password_reset_confirm'),
                       url(r'^password/reset/complete/$',
                           auth_views.password_reset_complete,
                           name='password_reset_complete'),
                       url(r'^password/reset/done/$',
                           auth_views.password_reset_done,
                           name='password_reset_done'),
)

account_urls = patterns('',
    url(r'', include('accounts.urls')),
    url(r'^activate/complete/$', TemplateView.as_view(template_name='registration/activation_complete.html'), name='registration_activation_complete'),
    url(r'^activate/(?P<activation_key>\w+)/$', ActivationView.as_view(), name='registration_activate'),
    url(r'^register.xml$', TemplateView.as_view(template_name='xml/register.xml', content_type='text/xml'), name='registration_register'),
    url(r'^register/complete/$', TemplateView.as_view(template_name='registration/registration_complete.html'), name='registration_complete'),
    url(r'^register/closed/$', TemplateView.as_view(template_name='registration/registration_closed.html'), name='registration_disallowed'),
    url(r'^login.xml$', login),
    url(r'^logout.xml$', logout, name='auth_logout'),
    (r'', include(auth_urls)),
)

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='homepage.html')),
    url(r'^index.xml$', index),
    url(r'^accordion.xml$', TemplateView.as_view(template_name='xml/accordion.xml', content_type='text/xml')),
    url(r'^try.xml$', TemplateView.as_view(template_name='xml/try.xml', content_type='text/xml')),
    url(r'^Email$', TemplateView.as_view(template_name='email/base.html')),
    url(r'^HENet$', 'henet.views.service'),
    url(r'^play/$', VT100.as_view(ws_url='localhost:4080/'), name='playgame'),
    url(r'^hackrun/$', Terminal.as_view(banner=True, ws_url='localhost:4080/', telnet_port='4000')),
    url(r'^selectable/', include('selectable.urls')),
    url(dajaxice_config.dajaxice_url, include('dajaxice.urls')),
    url(r'^Forums/', include('forums.urls')),
    url(r'^HelpCenter/', include('help_center.urls')),
    url(r'^ContactUs$', contact, name='contact_us'),
    url(r'^ContactUs/ThankYou$', TemplateView.as_view(template_name='contact_done.html'), name='contact_thanks'),
    url(r'^Tutorial$', TemplateView.as_view(template_name='tutorial/index.html')),
    url(r'^PrivacyPolicy$', TemplateView.as_view(template_name='privacy.html'), name='privacy'),
    url(r'^accounts/', include(account_urls)),
    url(r'^Project/', include('pm.urls')),
    url(r'^Missions/', include('henet.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^admintools/', include('admin_tools.urls')),
)
