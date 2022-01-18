from hedemos.forms import ContactForm
from django.shortcuts import render, redirect
from django.core.mail import mail_admins
from django.contrib.auth.forms import AuthenticationForm
from django.utils.http import is_safe_url
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.http.response import HttpResponse

def contact(req):
    if req.method == 'POST':
        form = ContactForm(req.POST)
        if form.is_valid():
            message = """Hello Kevin!
Someone used the contact form to contact us today!  Here is the message they sent you:

Name: %s
Email : %s
Subject: %s
Message:
%s
""" % (form.cleaned_data['name'], form.cleaned_data['email'], form.cleaned_data['subject'], form.cleaned_data['message'])
            mail_admins('ContactForm', message)
            return redirect('contact_thanks')
    else:
        form = ContactForm()
    return render(req, "contact_form.html", {'form':form})

def index(req):
    if req.GET.has_key('next'):
        return render(req, 'xml/login.xml', content_type='text/xml', dictionary={'next':req.GET['next']})
    return render(req, 'xml/homepage.xml', content_type='text/xml')

def login(req):
    redirect_to = req.GET.get('next', '/accounts/Characters/')
    if req.method == 'POST':
        form = AuthenticationForm(req, data=req.POST)
        if form.is_valid():
            if not is_safe_url(url=redirect_to, host=req.get_host()):
                redirect_to = '/accounts/Characters/'
            auth_login(req, form.get_user())
            return HttpResponse(b'{"st":"xlink", "xml":"%s", "id":"hash"}' % redirect_to, content_type='application/json')
    else:
        return redirect('/accounts/Characters/')
    return HttpResponse(b'{"st":"error", "msg":"Invalid Username and/or Password."}', content_type='application/json')

def logout(req):
    auth_logout(req)
    return render(req, 'xml/logout.xml', content_type='text/xml')
