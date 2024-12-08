# forms.py (create this new file in your app directory)
from django import forms
from django.contrib.auth.models import User

class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    account = forms.CharField(max_length=20)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_account(self):
        account = self.cleaned_data.get('account')
        if User.objects.filter(username=account).exists():
            raise forms.ValidationError("This account name is already taken.")
        return account

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

