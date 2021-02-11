from django.urls import path
from django.contrib.auth.views import LoginView
from .views import SignUpView, validate_username
from .forms import LogInForm

urlpatterns = [
    path('signup', SignUpView.as_view(), name='signup'),
    path('login', LoginView.as_view(authentication_form=LogInForm)),
    path('validate_username', validate_username, name='validate_username')
]
