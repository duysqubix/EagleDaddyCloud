from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views import generic
from django.http import HttpResponseRedirect
from django.shortcuts import render

from ClientAccount.models import ClientAccount


class SignUpView(generic.CreateView):
    form_class = UserCreationForm
    template_name = 'registration/signup.html'

    def post(self, request, *args, **kwargs):
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.save()
            account = ClientAccount(user=user)
            account.save()
            return HttpResponseRedirect(reverse_lazy('login'))
        return render(request, self.template_name, {'form': form})
