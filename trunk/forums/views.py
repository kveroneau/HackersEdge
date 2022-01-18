from django.shortcuts import get_object_or_404, redirect, render
from forums.models import Thread, Topic, Post
from forums.forms import PostForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import mail_admins
from django.core import mail
from django.template.context import Context
from django.template.loader import get_template
from django.core.mail.message import EmailMultiAlternatives
from django.conf import settings
from django.views.generic.list import ListView
import twitter, urllib2, json

class ThreadList(ListView):
    model = Thread
    paginate_by = 20
    def get_queryset(self):
        self.topic = get_object_or_404(Topic, slug=self.kwargs['slug'])
        return super(ThreadList, self).get_queryset().filter(topic=self.topic)
    def get_context_data(self, **ctx):
        ctx = super(ThreadList, self).get_context_data(**ctx)
        ctx['topic'] = self.topic
        return ctx

class PostList(ListView):
    model = Post
    paginate_by = 10
    def get_queryset(self):
        self.thread = get_object_or_404(Thread, pk=self.kwargs['pk'])
        return super(PostList, self).get_queryset().filter(thread=self.thread)
    def get_context_data(self, **ctx):
        ctx = super(PostList, self).get_context_data(**ctx)
        ctx['thread'] = self.thread
        return ctx

def send_mass_mail(subject, template_name, recipient_list, extra_ctx={}):
    conn = mail.get_connection()
    msgs = []
    for who in recipient_list:
        ctx = Context({'user':who})
        ctx.update(extra_ctx)
        message = get_template('email/%s.txt' % template_name).render(ctx)
        html = get_template('email/%s.html' % template_name).render(ctx)
        msg = EmailMultiAlternatives(subject, message, to=[who.email])
        msg.attach_alternative(html, "text/html")
        msgs.append(msg)
    conn.open()
    conn.send_messages(msgs)
    conn.close()

@login_required
def post(req, pk=None):
    if req.method == 'POST':
        thread = get_object_or_404(Thread, pk=pk)
        form = PostForm(req.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = req.user
            post.username = req.user.username
            post.thread = thread
            post.save()
            thread.save()
            user_list = []
            for p in thread.post_set.all():
                if p.user != req.user and p.user not in user_list:
                    user_list.append(p.user)
            send_mass_mail('Reply to forum post: %s' % thread.subject, 'forum_reply', user_list, {'post_url':thread.get_absolute_url()})
            mail_admins('New Forum Post: %s' % post.subject, 'New message posted by %s' % post.username)
            messages.success(req, 'Post has been created.')
        return redirect(thread)

@login_required
def new_thread(req, slug=None):
    topic = get_object_or_404(Topic, slug=slug)
    if req.method == 'POST':
        form = PostForm(req.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = req.user
            post.username = req.user.username
            thread = Thread(subject=post.subject, started_by=post.username, topic=topic, valid_group=topic.valid_group)
            thread.save()
            post.thread = thread
            post.save()
            mail_admins('New Forum Thread: %s' % post.subject, 'New message posted by %s' % post.username)
            messages.success(req, 'Thread has been created.')
            if slug in ('news', 'devblog',):
                t = twitter.Twitter(auth=twitter.OAuth(settings.TOKEN, settings.TOKEN_KEY, settings.CONSUMER_KEY, settings.CONSUMER_SECRET))
                t.statuses.update(status='%s: %s -- http://www.hackers-edge.com%s #gamedev #indiegamedev' % (topic.title, thread.subject, thread.get_absolute_url()))
                req = urllib2.Request('https://discordapp.com/api/webhooks/XXXX')
                req.add_header('User-Agent', 'Hackers-Edge/1.0')
                req.add_header('Content-Type', 'application/json')
                req.add_data(json.dumps({'content':'%s: %s -- http://www.hackers-edge.com%s' % (topic.title, thread.subject, thread.get_absolute_url())}))
                r = urllib2.urlopen(req)
                if r.code != 204:
                    messages.error(req, 'Unable to post message into Discord.')
            return redirect(thread)
    else:
        form = PostForm()
    return render(req, "forums/new_thread.html", {'form':form, 'topic':topic})

@login_required
def lock_thread(req, pk=None):
    thread = get_object_or_404(Thread, pk=pk)
    if req.user.username == thread.started_by:
        thread.is_locked = True
        thread.save()
        messages.success(req, "Thread locked.")
    else:
        messages.error(req, "Access denied.")
    return redirect(thread)
