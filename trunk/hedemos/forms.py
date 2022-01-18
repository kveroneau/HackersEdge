from registration.forms import RegistrationFormUniqueEmail
#from simplemathcaptcha.fields import MathCaptchaField
from captcha.fields import ReCaptchaField
from django import forms

#class RegistrationCaptchaForm(RegistrationFormUniqueEmail):
#    captcha = MathCaptchaField(required=True)

class ContactForm(forms.Form):
    name = forms.CharField(max_length=40)
    email = forms.EmailField(help_text='Used to contact you back about your inquiry.')
    subject = forms.CharField(max_length=80)
    message = forms.CharField(widget=forms.Textarea)
    captcha = ReCaptchaField(attrs={'theme': 'black'})
