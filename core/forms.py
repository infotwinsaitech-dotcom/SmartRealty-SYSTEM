from allauth.socialaccount.forms import SignupForm
from django import forms

class CustomSocialSignupForm(SignupForm):
    username = forms.CharField(max_length=150, required=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill email if available
        if self.sociallogin and self.sociallogin.account.extra_data:
            email = self.sociallogin.account.extra_data.get('email', '')
            if email and 'email' in self.fields:
                self.fields['email'].initial = email
    
    def save(self, request):
        user = super().save(request)
        user.role = 'user'
        user.save()
        return user