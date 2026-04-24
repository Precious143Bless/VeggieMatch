from django.db import models
from django.utils import timezone


class VegetablePost(models.Model):
    STATUS_ACTIVE  = 'ACTIVE'
    STATUS_BOUGHT  = 'BOUGHT'    # was CLAIMED
    STATUS_RESCUE  = 'RESCUE'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_BOUGHT, 'Bought'),
        (STATUS_RESCUE, 'Available for Donate'),
    ]

    SURPLUS_LOW    = 'LOW'
    SURPLUS_MEDIUM = 'MEDIUM'
    SURPLUS_HIGH   = 'HIGH'
    SURPLUS_CHOICES = [
        (SURPLUS_LOW,    'Low Surplus (5–20 kg)'),
        (SURPLUS_MEDIUM, 'Medium Surplus (20–100 kg)'),
        (SURPLUS_HIGH,   'High Surplus (100+ kg)'),
    ]

    farmer_name    = models.CharField(max_length=100)
    phone_number   = models.CharField(max_length=20)
    farmer_photo   = models.ImageField(upload_to='faces/farmers/', blank=True, null=True)
    vegetable      = models.CharField(max_length=100)
    veggie_photo   = models.ImageField(upload_to='veggies/', blank=True, null=True)
    surplus_level  = models.CharField(max_length=10, choices=SURPLUS_CHOICES, default=SURPLUS_LOW)
    quantity       = models.DecimalField(max_digits=8, decimal_places=2)
    price_per_kg   = models.DecimalField(max_digits=8, decimal_places=2, default=1.00)
    pickup_address = models.CharField(max_length=255, default='La Trinidad Trading Post, Benguet')
    pickup_note    = models.CharField(max_length=255, blank=True)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at     = models.DateTimeField(auto_now_add=True)
    expiry_time    = models.DateTimeField()

    def is_expired(self):
        return timezone.now() >= self.expiry_time

    def get_full_location(self):
        if self.pickup_note:
            return f"{self.pickup_address} — {self.pickup_note}"
        return self.pickup_address

    def __str__(self):
        return f"{self.vegetable} – {self.farmer_name} [{self.status}]"

    class Meta:
        db_table = 'core_vegetablepost'
        indexes  = [
            models.Index(fields=['status']),
            models.Index(fields=['expiry_time']),
        ]


class BuyRecord(models.Model):
    """Buyer purchases vegetables from an active post."""
    post         = models.OneToOneField(VegetablePost, on_delete=models.CASCADE, related_name='buy')
    buyer_name   = models.CharField(max_length=100)
    buyer_number = models.CharField(max_length=20)
    buyer_photo  = models.ImageField(upload_to='faces/buyers/', blank=True, null=True)
    quantity_kg  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    bought_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_buyrecord'


class RescueRecord(models.Model):
    """Community kitchen/person claims a rescued (donated) post for free."""
    post           = models.OneToOneField(VegetablePost, on_delete=models.CASCADE, related_name='rescue')
    claimer_name   = models.CharField(max_length=100)
    claimer_number = models.CharField(max_length=20)
    claimer_photo  = models.ImageField(upload_to='faces/claimers/', blank=True, null=True)
    quantity_kg    = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    claimed_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_rescuerecord'


class OTPVerification(models.Model):
    PURPOSE_POST   = 'POST'
    PURPOSE_BUY    = 'BUY'
    PURPOSE_RESCUE = 'RESCUE'
    PURPOSE_DONATE = 'DONATE'
    PURPOSE_EDIT   = 'EDIT'
    PURPOSE_DELETE = 'DELETE'
    PURPOSE_CHOICES = [
        (PURPOSE_POST,   'Post'),
        (PURPOSE_BUY,    'Buy'),
        (PURPOSE_RESCUE, 'Rescue'),
        (PURPOSE_DONATE, 'Donate'),
        (PURPOSE_EDIT,   'Edit'),
        (PURPOSE_DELETE, 'Delete'),
    ]

    phone_number = models.CharField(max_length=20)
    otp_code     = models.CharField(max_length=6)
    purpose      = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    post_id      = models.BigIntegerField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField()
    is_used      = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and timezone.now() <= self.expires_at

    class Meta:
        db_table = 'core_otpverification'
        indexes  = [
            models.Index(fields=['phone_number', 'purpose']),
        ]
