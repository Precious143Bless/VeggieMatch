from django import forms
import re

# Accepts: +639XXXXXXXXX, 09XXXXXXXXX, 9XXXXXXXXX (PH mobile)
_PH_PHONE_RE = re.compile(r'^(?:\+63|0)9\d{9}$')

def validate_ph_phone(value):
    normalized = value.strip().replace(' ', '').replace('-', '')
    if not _PH_PHONE_RE.match(normalized):
        raise forms.ValidationError(
            'Enter a valid Philippine mobile number (e.g. +639171234567 or 09171234567).'
        )


class PostVegetableForm(forms.Form):
    farmer_name  = forms.CharField(
        max_length=100, label='Your Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
    )
    phone_number = forms.CharField(
        max_length=20, label='Phone Number',
        validators=[validate_ph_phone],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+63 9XX XXX XXXX'}),
    )
    farmer_photo = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    vegetable    = forms.CharField(
        max_length=100, label='Vegetable Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Cabbage, Carrots, Pechay...'}),
    )
    veggie_photo = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    surplus_level = forms.ChoiceField(
        choices=[('LOW','🟡 Low Surplus (5–20 kg)'),('MEDIUM','🟠 Medium Surplus (20–100 kg)'),('HIGH','🔴 High Surplus (100+ kg)')],
        label='Surplus Level',
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
    )
    quantity     = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0.1, label='Quantity (kg)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10', 'step': '0.1'}),
    )
    price_per_kg = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=1, label='Price per kg (₱)', initial=1,
        required=False,  # not required for donations
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 25', 'step': '0.5'}),
    )
    pickup_note  = forms.CharField(
        max_length=255, required=False, label='Further Instructions',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Stall 12, near the main gate'}),
        help_text='Optional — stall number or landmark to help buyers find you.',
    )
    timer_value  = forms.IntegerField(
        min_value=1, label='Duration', initial=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2', 'min': '1'}),
    )
    timer_unit   = forms.ChoiceField(
        choices=[('hours', 'Hours'), ('minutes', 'Minutes')], initial='hours', label='Unit',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_price_per_kg(self):
        price = self.cleaned_data.get('price_per_kg')
        # Price is optional for donations — validated as 0 server-side
        if price is not None and price < 1:
            # Only raise if it's not a donation (post_type checked in view)
            pass
        return price if price is not None else None

    def clean(self):
        cleaned = super().clean()
        level = cleaned.get('surplus_level')
        qty   = cleaned.get('quantity')
        limits = {'LOW': (5, 20), 'MEDIUM': (20, 100), 'HIGH': (100, 99999)}
        hints  = {'LOW': '5–20 kg', 'MEDIUM': '20–100 kg', 'HIGH': '100+ kg'}
        if level and qty is not None and level in limits:
            mn, mx = limits[level]
            if not (mn <= qty <= mx):
                self.add_error('quantity', f'{level.capitalize()} surplus must be {hints[level]}.')
        return cleaned

    def clean_farmer_photo(self):
        return self.cleaned_data.get('farmer_photo', '')

    def clean_veggie_photo(self):
        return self.cleaned_data.get('veggie_photo', '')

    def get_timer_minutes(self):
        val  = self.cleaned_data.get('timer_value', 2)
        unit = self.cleaned_data.get('timer_unit', 'hours')
        return val * 60 if unit == 'hours' else val


class OTPForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6, min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center otp-input',
            'placeholder': '_ _ _ _ _ _', 'maxlength': '6',
            'inputmode': 'numeric', 'autocomplete': 'one-time-code',
        }),
        label='Enter 6-digit OTP',
    )


class BuyForm(forms.Form):
    buyer_name   = forms.CharField(
        max_length=100, label='Your Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
    )
    phone_number = forms.CharField(
        max_length=20, label='Phone Number',
        validators=[validate_ph_phone],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+63 9XX XXX XXXX'}),
    )
    quantity_kg  = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0.1,
        label='How many kg do you need?',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 5', 'step': '0.1'}),
    )
    buyer_photo  = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_buyer_photo(self):
        return self.cleaned_data.get('buyer_photo', '')


class RescueForm(forms.Form):
    claimer_name  = forms.CharField(
        max_length=100, label='Your Name or Organization',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Juan dela Cruz or Benguet Community Kitchen'}),
    )
    phone_number  = forms.CharField(
        max_length=20, label='Phone Number',
        validators=[validate_ph_phone],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+63 9XX XXX XXXX'}),
    )
    quantity_kg   = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0.1,
        label='How many kg do you need?',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10', 'step': '0.1'}),
    )
    claimer_photo = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_claimer_photo(self):
        return self.cleaned_data.get('claimer_photo', '')


class GlobalSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'placeholder': 'Search vegetable, farmer or address...',
            'class': 'form-control',
            'aria-label': 'Search'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Any'), ('ACTIVE', 'Posted'), ('RESCUE', 'Donate')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
