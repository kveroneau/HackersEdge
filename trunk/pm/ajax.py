from dajaxice.decorators import dajaxice_register
from dajax.core import Dajax
from pm.models import Category, Snippet

class Ajax(Dajax):
    """
    This class exists because I was testing out a different implementation of the front-end to see how things would function.
    """
    def slideDown(self, element_id):
        self.script("$('%s').slideDown();" % element_id)
    def slideUp(self, element_id):
        self.script("$('%s').slideUp();" % element_id)
    def fadeIn(self, element_id):
        self.script("$('%s').fadeIn();" % element_id)
    def fadeOut(self, element_id):
        self.script("$('%s').fadeOut();" % element_id)
    def fadeToggle(self, element_id):
        self.script("$('%s').fadeToggle();" % element_id)
    def flash(self, msg, level='info'):
        self.script('append_message({"tag":"%s", "message":"%s"});' % (level, msg))
    def clearFlash(self, level='info'):
        self.remove_css_class('#message', 'alert alert-%s' % level)
        self.slideUp('#message')
    def error(self, msg):
        self.flash(msg, 'error')
    def setSnippet(self, snippet):
        self.assign('#snippet_id', 'innerHTML', snippet.pk)
        self.assign('#title', 'value', snippet.title)
        self.assign('#snippet', 'value', snippet.content)

@dajaxice_register(name='snippets.app_init')
def app_init(req):
    dajax = Ajax()
    if not req.user.is_superuser:
        dajax.alert('Not authenticated.')
        return dajax.json()
    category_dropdown = '<select id="category" onchange="updateItems();">'
    for category in Category.objects.all():
        category_dropdown+='<option value="%s">%s</option>' % (category.pk, category.title)
    dajax.assign('#category_div', 'innerHTML', category_dropdown+'</select>')
    dajax.script("Dajaxice.snippets.get_items(Dajax.process, {'category':1});")
    return dajax.json()

@dajaxice_register(name='snippets.get_items')
def get_items(req, category):
    dajax = Ajax()
    if not req.user.is_superuser:
        dajax.alert('Not authenticated.')
        return dajax.json()
    items = ''
    for snippet in Snippet.objects.filter(category_id=category):
        items+='<li><a href="#" onclick="return getItem(%s);">%s</a></li>' % (snippet.pk, snippet.title)
    if items == '':
        items = '<li>Category empty</li>'
    dajax.assign('#items', 'innerHTML', items)
    return dajax.json()

@dajaxice_register(name='snippets.add_item')
def add_item(req, category):
    dajax = Ajax()
    if not req.user.is_superuser:
        dajax.alert('Not authenticated.')
        return dajax.json()
    snippet = Snippet.objects.create(title='Untitled', content='Blank', category_id=category)
    dajax.setSnippet(snippet)
    dajax.script("Dajaxice.snippets.get_items(Dajax.process, {'category':%s});" % category)
    dajax.flash('A new item has been added.')
    return dajax.json()

@dajaxice_register(name='snippets.get_item')
def get_item(req, snippet_id):
    dajax = Ajax()
    if not req.user.is_superuser:
        dajax.alert('Not authenticated.')
        return dajax.json()
    try:
        snippet = Snippet.objects.get(pk=snippet_id)
    except Snippet.DoesNotExist:
        dajax.alert('The snippet does not exist!')
        return dajax.json()
    dajax.setSnippet(snippet)
    return dajax.json()

@dajaxice_register(name='snippets.save_item')
def save_item(req, snippet_id, title, content, category):
    dajax = Ajax()
    if not req.user.is_superuser:
        dajax.alert('Not authenticated.')
        return dajax.json()
    try:
        snippet = Snippet.objects.get(pk=snippet_id)
    except Snippet.DoesNotExist:
        dajax.alert('The snippet does not exist!')
        return dajax.json()
    snippet.title = title
    snippet.content = content
    snippet.category_id = category
    snippet.save()
    dajax.script("Dajaxice.snippets.get_items(Dajax.process, {'category':%s});" % category)
    dajax.flash('The snippet has been saved successfully.')
    return dajax.json()
