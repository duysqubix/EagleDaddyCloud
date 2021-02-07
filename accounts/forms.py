from django.contrib.auth.forms import AuthenticationForm
from django import forms


class LogInForm(AuthenticationForm):

    username = forms.CharField(widget=forms.TextInput(
        attrs={
            'class': 'form-control',
            'placeholder': '',
            'id': 'username'
        }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': "form-control",
        'id': 'password',
    }))
