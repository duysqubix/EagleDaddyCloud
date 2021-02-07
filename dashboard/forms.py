from django import forms


class NewHubConnectForm(forms.Form):
    connect_passphrase = forms.CharField(widget=forms.TextInput(
        attrs={'class': "form-control"}))
