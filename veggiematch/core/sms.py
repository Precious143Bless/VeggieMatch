import random
import string
import requests
from datetime import timedelta
from django.utils import timezone
from django.conf import settings


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def _send_semaphore(phone_number, message):
    """Send SMS via Semaphore API. Returns True on success."""
    api_key = getattr(settings, 'SEMAPHORE_API_KEY', '')
    sender  = getattr(settings, 'SEMAPHORE_SENDER', 'VeggieMatch')

    if not api_key:
        # Dev fallback — print to console
        print(f"[DEV SMS] To {phone_number}: {message}")
        return True

    try:
        resp = requests.post(
            'https://api.semaphore.co/api/v4/messages',
            data={
                'apikey':      api_key,
                'number':      phone_number,
                'message':     message,
                'sendername':  sender,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        print(f"[SMS ERROR] Semaphore {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        print(f"[SMS ERROR] {e}")
        return False


def send_otp(phone_number, otp_code, purpose):
    message_map = {
        'POST':   f"[VeggieMatch] Your OTP to post vegetables: {otp_code}. Valid for {settings.OTP_EXPIRY_MINUTES} mins.",
        'BUY':    f"[VeggieMatch] Your OTP to buy this item: {otp_code}. Valid for {settings.OTP_EXPIRY_MINUTES} mins.",
        'RESCUE': f"[VeggieMatch] Your OTP to claim this rescue item: {otp_code}. Valid for {settings.OTP_EXPIRY_MINUTES} mins.",
        'DONATE': f"[VeggieMatch] Your OTP to move your post to Donate: {otp_code}. Valid for {settings.OTP_EXPIRY_MINUTES} mins.",
        'EDIT':   f"[VeggieMatch] Your OTP to edit your post: {otp_code}. Valid for {settings.OTP_EXPIRY_MINUTES} mins.",
        'DELETE': f"[VeggieMatch] Your OTP to delete your post: {otp_code}. Valid for {settings.OTP_EXPIRY_MINUTES} mins.",
    }
    return _send_semaphore(phone_number, message_map.get(purpose, f"[VeggieMatch] Your OTP: {otp_code}"))


def send_buy_notification(farmer_phone, buyer_name, buyer_phone, vegetable, quantity, price_per_kg, location, buyer_photo_url=''):
    """Notify farmer when their post is bought."""
    message = (
        f"[VeggieMatch] Your post was bought!\n"
        f"Item: {vegetable} ({quantity} kg)\n"
        f"Buyer: {buyer_name}\n"
        f"Contact: {buyer_phone}\n"
        f"Pickup: {location}\n"
        f"Please prepare for pickup."
    )
    if buyer_photo_url:
        message += f"\nBuyer Photo: {buyer_photo_url}"
    return _send_semaphore(farmer_phone, message)


def send_buy_confirmation(buyer_phone, buyer_name, vegetable, quantity, price_per_kg, farmer_name, farmer_phone, location):
    """Send buyer their order summary + farmer contact."""
    message = (
        f"[VeggieMatch] Purchase confirmed!\n"
        f"Item: {vegetable} ({quantity} kg)\n"
        f"Total: ~\u20b1{float(price_per_kg) * float(quantity):.0f}\n"
        f"Pickup: {location}\n"
        f"Farmer: {farmer_name}\n"
        f"Farmer No.: {farmer_phone}"
    )
    return _send_semaphore(buyer_phone, message)


def send_rescue_notification(farmer_phone, claimer_name, claimer_phone, vegetable, quantity, location, claimer_photo_url=''):
    """Notify farmer when their donated post is claimed."""
    message = (
        f"[VeggieMatch] Your donated post was claimed!\n"
        f"Item: {vegetable} ({quantity} kg)\n"
        f"Claimer: {claimer_name}\n"
        f"Contact: {claimer_phone}\n"
        f"Pickup: {location}\n"
        f"Thank you for donating!"
    )
    if claimer_photo_url:
        message += f"\nClaimer Photo: {claimer_photo_url}"
    return _send_semaphore(farmer_phone, message)


def send_rescue_confirmation(claimer_phone, claimer_name, vegetable, quantity, farmer_name, farmer_phone, location):
    """Send claimer their claim summary + farmer contact."""
    message = (
        f"[VeggieMatch] Claim confirmed!\n"
        f"Item: {vegetable} ({quantity} kg) - FREE\n"
        f"Pickup: {location}\n"
        f"Farmer: {farmer_name}\n"
        f"Farmer No.: {farmer_phone}\n"
        f"Thank you for helping reduce food waste!"
    )
    return _send_semaphore(claimer_phone, message)


def send_expiry_warning(farmer_phone, farmer_name, vegetable, quantity, minutes_left):
    """Warn farmer their post is about to expire so they can donate proactively."""
    message = (
        f"[VeggieMatch] Hi {farmer_name}, your post is expiring soon!\n"
        f"Item: {vegetable} ({quantity} kg)\n"
        f"Expires in: ~{minutes_left} minutes\n"
        f"Tip: Open VeggieMatch and tap Donate to let the community claim it for free instead of wasting it."
    )
    return _send_semaphore(farmer_phone, message)


def create_otp(phone_number, purpose, post_id=None):
    from core.models import OTPVerification
    import threading

    OTPVerification.objects.filter(
        phone_number=phone_number, purpose=purpose, is_used=False
    ).update(is_used=True)

    code = generate_otp()
    otp  = OTPVerification.objects.create(
        phone_number = phone_number,
        otp_code     = code,
        purpose      = purpose,
        post_id      = post_id,
        expires_at   = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    )
    threading.Thread(target=send_otp, args=(phone_number, code, purpose), daemon=True).start()
    return {'ok': True, 'otp': otp}


def verify_otp(phone_number, otp_code, purpose):
    from core.models import OTPVerification

    try:
        otp = OTPVerification.objects.filter(
            phone_number=phone_number,
            otp_code=otp_code,
            purpose=purpose,
            is_used=False,
        ).latest('created_at')
    except OTPVerification.DoesNotExist:
        return False

    if not otp.is_valid():
        return False

    otp.is_used = True
    otp.save(update_fields=['is_used'])
    return True
