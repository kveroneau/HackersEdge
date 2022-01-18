from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape
from accounts.forms import InviteForm

register = template.Library()

@register.filter
def yesnoicon(value):
    icon = "check" if value else "cancel"
    return mark_safe('<span class="ui-icon ui-icon-%s" style="float:left;"></span>' % icon)

@register.filter
def ratingicon(value):
    return mark_safe('<span class="ui-icon ui-icon-star" style="float:left;"></span>' * value)

@register.filter
def link(value):
    try:
        return mark_safe('<a href="%s">%s</a>' % (escape(value.get_absolute_url()), escape(value)))
    except AttributeError:
        return value

@register.simple_tag
def showicon(icon):
    return mark_safe('<span class="ui-icon ui-icon-%s" style="float:left;"></span>' % icon)

@register.simple_tag
def invite_form():
    form = InviteForm()
    return mark_safe(form.as_table())
