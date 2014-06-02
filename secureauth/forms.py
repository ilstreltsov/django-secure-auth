# -*- coding: utf-8 -*-

from django.utils.translation import ugettext_lazy as _
from django import forms

from models import (
    UserAuthNotification, UserAuthLogging, UserAuthToken,
    UserAuthCode, UserAuthPhone, UserAuthQuestion)
from utils.sign import Sign
from utils import is_phone


class BasicForm(forms.Form):
    enabled = forms.BooleanField(label=_('Enabled'), required=False)

    def decrypt(self, key, *args):
        if len(args) > 2 and args[2] and key in args[2]:
            unsigned = Sign().unsign(args[2][key])
            if unsigned is not None:
                args[2][key] = unsigned

    def __init__(self, user, model, *args, **kwargs):
        self.user = user
        self.model = model
        super(BasicForm, self).__init__(*args, **kwargs)

    def save(self):
        if not self.user:
            return None

        try:
            data = self.model.objects.get(user=self.user)
        except self.model.DoesNotExist:
            data = self.model(user=self.user)

        return data


class CodeForm(forms.Form):
    code = forms.CharField(label=_('Code'), required=True)

    def __init__(self, user, model, *args, **kwargs):
        self.user = user
        self.model = model
        super(CodeForm, self).__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code and self.user and self.model:
            obj = self.model.objects.get(user=self.user)
            if obj.check_auth_code(self.cleaned_data.get('code'), True):
                return code
        raise forms.ValidationError(_('Entered code is wrong'))

    def save(self):
        if self.user:
            data = self.model.objects.get(user=self.user)
            data.enabled = True
            data.save()
            return data


class PhoneBasicForm(BasicForm):
    phone = forms.CharField(label=_('Phone'), required=True, max_length=16)

    def __init__(self, *args, **kwargs):
        self.decrypt('phone', *args)
        super(PhoneBasicForm, self).__init__(*args, **kwargs)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and not phone.startswith('+') or ' ' in phone:
            raise forms.ValidationError(
                _('Phone does not contain spaces and must be starts with a +'))
        elif not is_phone(phone):
            raise forms.ValidationError(
                _('The phone number entered is not valid'))
        return phone

    def save(self):
        model = super(PhoneBasicForm, self).save()
        model.phone = self.cleaned_data.get('phone')
        model.save()
        return model


class QuestionForm(BasicForm):
    question = forms.CharField(label=_('Question'), required=True)
    code = forms.CharField(label=_('code'), required=True, max_length=16)

    def __init__(self, *args, **kwargs):
        self.decrypt('code', *args)
        self.decrypt('question', *args)
        super(QuestionForm, self).__init__(*args, **kwargs)
        if args[2] and args[2].get('code'):
            self.fields['code'].widget = forms.HiddenInput()
        self.fields['code'].label = _('Answer')

    def save(self):
        model = super(QuestionForm, self).save()
        return model.set_data(
            self.cleaned_data.get('question'), self.cleaned_data.get('code'))


class NotificationForm(forms.ModelForm):
    class Meta:
        model = UserAuthNotification
        exclude = ('user',)


class LoggingForm(forms.ModelForm):
    class Meta:
        model = UserAuthLogging
        exclude = ('user',)


class ActivatePhoneForm(forms.Form):
    phone = forms.CharField(label=_('Phone'), required=True, max_length=16)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone.startswith('+') or ' ' in phone:
            raise forms.ValidationError(
                _('Phone does not contain spaces and must be starts with a +'))
        elif not is_phone(phone):
            raise forms.ValidationError(
                _('The phone number entered is not valid'))
        return phone


class DisableMethodForm(forms.Form):
    code = forms.BooleanField(label=_('Codes Auth'), required=False)
    token = forms.BooleanField(label=_('TOTP Auth'), required=False)
    phone = forms.BooleanField(label=_('SMS Auth'), required=False)
    question = forms.BooleanField(label=_('Question Auth'), required=False)
    current_password = forms.CharField(
        label=_('Current password:'), widget=forms.PasswordInput)

    def __init__(self, request, pk, *args, **kwargs):
        self._request = request
        self._pk = pk

        def get_status(model, key):
            return model.objects.filter(user_id=self._pk, enabled=1).exists()

        kwargs['initial'] = {
            'code': get_status(UserAuthCode, 'code'),
            'token': get_status(UserAuthToken, 'token'),
            'phone': get_status(UserAuthPhone, 'phone'),
            'question': get_status(UserAuthQuestion, 'question'),
        }
        super(DisableMethodForm, self).__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password', '')
        if not self._request.user.check_password(current_password):
            raise forms.ValidationError(_(u'Invalid password!'))

    def save(self):
        def set_status(model, key):
            model.objects.filter(user_id=self._pk).update(
                enabled=self.cleaned_data.get(key, False))

        set_status(UserAuthCode, 'code')
        set_status(UserAuthToken, 'token')
        set_status(UserAuthPhone, 'phone')
        set_status(UserAuthQuestion, 'question')
