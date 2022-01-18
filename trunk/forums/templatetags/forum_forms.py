from django import template
from forums.forms import PostForm
import markdown as md

register = template.Library()

@register.simple_tag
def post_form(subject):
    form = PostForm(initial={'subject':subject, 'body':''})
    return form

@register.filter
def markdown(value):
    return md.markdown(value)
