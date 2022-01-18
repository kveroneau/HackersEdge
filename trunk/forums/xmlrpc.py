from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http.response import HttpResponse
from django.core.exceptions import PermissionDenied
from forums.models import Topic, Thread, Post
from django.contrib.auth.models import User

dispatcher = SimpleXMLRPCDispatcher()

class ForumService:
    def topic_list(self):
        topics = []
        for topic in Topic.objects.all():
            topics.append({'title':topic.title,
                           'slug':topic.slug,
                           'description':topic.description})
        return topics
    def thread_list(self, topic_slug):
        try:
            topic = Topic.objects.get(slug=topic_slug)
        except Topic.DoesNotExist:
            return False
        threads = []
        for thread in topic.thread_set.all():
            threads.append({'subject':thread.subject,
                            'pk':thread.pk,
                            'started_by':thread.started_by,
                            'started_on':thread.started_on,
                            'last_updated':thread.last_updated})
        return threads
    def post_list(self, thread_pk):
        try:
            thread = Thread.objects.get(pk=int(thread_pk))
        except Thread.DoesNotExist:
            return False
        posts = []
        for post in thread.post_set.all():
            posts.append({'subject':post.subject,
                          'body':post.body,
                          'username':post.username,
                          'posted':post.posted})
        return posts
    def post_reply(self, thread_pk, username, body):
        try:
            thread = Thread.objects.get(pk=int(thread_pk))
        except Thread.DoesNotExist:
            return False
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return False
        Post.objects.create(subject=thread.subject, body=body, user=user, username=username, thread=thread)
        thread.save()
        return True

dispatcher.register_instance(ForumService())

@csrf_exempt
@require_POST
def rpc_service(req):
    if req.META['REMOTE_ADDR'] not in ('127.0.0.1',):
        raise PermissionDenied
    response = HttpResponse(mimetype='application/xml')
    response.write(dispatcher._marshaled_dispatch(req.body))
    response['Content-length'] = str(len(response.content))
    return response
