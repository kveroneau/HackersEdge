from dajaxice.decorators import dajaxice_register
from forums.models import Post
from django.contrib.auth.decorators import login_required
from dajax.core import Dajax

@login_required
@dajaxice_register(method='GET')
def get_absolute_url(req, post_id):
    dajax = Dajax()
    try:
        post = Post.objects.get(pk=post_id)
        dajax.redirect(post.thread.get_absolute_url())
    except Post.DoesNotExist:
        dajax.alert("That post doesn't seem to exist...")
    return dajax.json()
