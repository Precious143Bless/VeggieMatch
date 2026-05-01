import base64
import uuid
from pathlib import Path

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
from datetime import timedelta
from django.db.models import Q, Sum
from django.core.paginator import Paginator

from .models import VegetablePost, BuyRecord, RescueRecord
from .forms  import PostVegetableForm, OTPForm, BuyForm, RescueForm, GlobalSearchForm
from .sms    import create_otp, verify_otp, send_buy_notification, send_buy_confirmation, send_rescue_notification, send_rescue_confirmation, send_expiry_warning, send_auto_rescue_notification


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_phone(phone):
    """Return a masked phone number, e.g. 09465539995 → 09*******995"""
    s = str(phone).strip()
    if len(s) <= 6:
        return s
    return s[:2] + '*' * (len(s) - 5) + s[-3:]

def _sync_all_posts():
    import threading
    # Fetch posts that need converting before the bulk update
    expiring = list(VegetablePost.objects.filter(
        status=VegetablePost.STATUS_ACTIVE,
        expiry_time__lte=timezone.now(),
        donated_at__isnull=True,
    ))
    if not expiring:
        return
    ids = [p.pk for p in expiring]
    VegetablePost.objects.filter(pk__in=ids).update(
        status=VegetablePost.STATUS_RESCUE,
        donated_at=timezone.now(),
    )
    # Notify each farmer their post was auto-moved to donate
    for post in expiring:
        threading.Thread(
            target=send_auto_rescue_notification,
            args=(post.phone_number, post.farmer_name, post.vegetable, post.quantity),
            daemon=True,
        ).start()


def _cleanup_old_otps():
    """Delete OTP records older than 24 hours. Runs at most once per hour via a session timestamp."""
    from .models import OTPVerification
    cutoff = timezone.now() - timedelta(hours=24)
    OTPVerification.objects.filter(created_at__lt=cutoff).delete()


def _maybe_cleanup_old_otps(request):
    """Throttle OTP cleanup to once per hour using a session timestamp."""
    last = request.session.get('_otp_cleanup_ts', 0)
    now  = timezone.now().timestamp()
    if now - last >= 3600:
        _cleanup_old_otps()
        request.session['_otp_cleanup_ts'] = now


def _notify_expiring_posts():
    """Send a one-time SMS warning to farmers whose active posts expire within 30 minutes."""
    import threading
    warning_window = timezone.now() + timedelta(minutes=30)
    # Fetch into a list first — single DB hit, avoids re-evaluating the queryset after the bulk update
    posts = list(VegetablePost.objects.filter(
        status=VegetablePost.STATUS_ACTIVE,
        expiry_time__lte=warning_window,
        expiry_time__gt=timezone.now(),
        expiry_notified=False,
    ))
    if not posts:
        return
    ids = [p.pk for p in posts]
    VegetablePost.objects.filter(pk__in=ids).update(expiry_notified=True)
    for post in posts:
        mins_left = max(1, int((post.expiry_time - timezone.now()).total_seconds() // 60))
        threading.Thread(
            target=send_expiry_warning,
            args=(post.phone_number, post.farmer_name, post.vegetable, post.quantity, mins_left),
            daemon=True,
        ).start()


def _recalc_surplus(post):
    """Update surplus_level to match the current remaining quantity."""
    qty = float(post.quantity)
    if qty >= 100:
        post.surplus_level = VegetablePost.SURPLUS_HIGH
    elif qty >= 20:
        post.surplus_level = VegetablePost.SURPLUS_MEDIUM
    else:
        post.surplus_level = VegetablePost.SURPLUS_LOW


MANAGE_UNLOCK_TTL = 15 * 60  # seconds — manage session expires after 15 minutes


def _is_manage_unlocked(request, post_id):
    """Return True if this post was unlocked via manage OTP within the last 15 minutes."""
    unlocked = request.session.get('manage_unlocked')
    if not isinstance(unlocked, dict):
        return False
    ts = unlocked.get(str(post_id))
    if ts is None:
        return False
    if timezone.now().timestamp() - ts > MANAGE_UNLOCK_TTL:
        unlocked.pop(str(post_id), None)
        request.session['manage_unlocked'] = unlocked
        return False
    return True


def _set_manage_unlocked(request, post_id):
    """Record that this post was unlocked, with the current timestamp."""
    unlocked = request.session.get('manage_unlocked')
    if not isinstance(unlocked, dict):
        unlocked = {}
    unlocked[str(post_id)] = timezone.now().timestamp()
    request.session['manage_unlocked'] = unlocked


def _clear_manage_unlocked(request, post_id):
    """Remove the manage unlock for this post (e.g. after delete)."""
    unlocked = request.session.get('manage_unlocked')
    if not isinstance(unlocked, dict):
        request.session['manage_unlocked'] = {}
        return
    unlocked.pop(str(post_id), None)
    request.session['manage_unlocked'] = unlocked


def splash(request):
    return render(request, 'core/splash.html')


def _save_base64_image(b64_string, subfolder):
    """Decode a base64 data-URI and save to MEDIA_ROOT. Returns relative path."""
    if ',' in b64_string:
        header, data = b64_string.split(',', 1)
        ext = header.split('/')[1].split(';')[0]
    else:
        data = b64_string
        ext  = 'jpg'

    filename  = f"{uuid.uuid4().hex}.{ext}"
    rel_path  = f"{subfolder}/{filename}"
    full_path = Path(settings.MEDIA_ROOT) / subfolder
    full_path.mkdir(parents=True, exist_ok=True)
    (full_path / filename).write_bytes(base64.b64decode(data))
    return rel_path


def _delete_file(rel_path):
    """Silently delete a MEDIA_ROOT-relative file if it exists."""
    if not rel_path:
        return
    try:
        full = Path(settings.MEDIA_ROOT) / rel_path
        if full.exists():
            full.unlink()
    except Exception:
        pass


def _clear_pending(request, key, photo_fields):
    """Delete any photos and remove a pending session key before overwriting it."""
    existing = request.session.get(key)
    if existing:
        for field in photo_fields:
            _delete_file(existing.get(field, ''))
        del request.session[key]


def _cleanup_expired_pending(request):
    """
    If a pending_* session key exists but its OTP has expired, delete the
    associated photo files and remove the session key so it doesn't linger.
    """
    from .models import OTPVerification

    for key, photo_fields in (
        ('pending_post',   ['farmer_photo_path', 'veggie_photo_path']),
        ('pending_buy',    ['buyer_photo_path']),
        ('pending_rescue', ['claimer_photo_path']),
    ):
        pending = request.session.get(key)
        if not pending:
            continue

        phone   = pending.get('phone_number', '')
        purpose = {'pending_post': 'POST', 'pending_buy': 'BUY', 'pending_rescue': 'RESCUE'}[key]

        # Check if a valid (unused, unexpired) OTP still exists
        still_valid = OTPVerification.objects.filter(
            phone_number=phone,
            purpose=purpose,
            is_used=False,
            expires_at__gt=timezone.now(),
        ).exists()

        if not still_valid:
            # OTP gone or expired — clean up photos and session key
            for field in photo_fields:
                _delete_file(pending.get(field, ''))
            del request.session[key]


# ── Home ──────────────────────────────────────────────────────────────────────

def home(request):
    _sync_all_posts()
    _notify_expiring_posts()
    _cleanup_expired_pending(request)
    _maybe_cleanup_old_otps(request)
    posts = VegetablePost.objects.filter(status=VegetablePost.STATUS_ACTIVE).order_by('expiry_time')
    donate_posts = VegetablePost.objects.filter(status=VegetablePost.STATUS_RESCUE).order_by('-created_at')[:1]
    impact = {
        'kg_rescued':   RescueRecord.objects.aggregate(total=Sum('quantity_kg'))['total'] or 0,
        'posts_donated': VegetablePost.objects.filter(status__in=[VegetablePost.STATUS_RESCUE, VegetablePost.STATUS_CLAIMED]).count(),
        'kg_sold':      BuyRecord.objects.aggregate(total=Sum('quantity_kg'))['total'] or 0,
    }
    return render(request, 'core/home.html', {'posts': posts, 'donate_posts': donate_posts, 'impact': impact})


# ── Posted Veggies (all active with photos) ───────────────────────────────────

def posted_veggies(request):
    _sync_all_posts()
    posts = VegetablePost.objects.filter(status=VegetablePost.STATUS_ACTIVE).order_by('-created_at')
    return render(request, 'core/posted_veggies.html', {'posts': posts})



# ── Post Vegetable ─────────────────────────────────────────────────────────────

def post_vegetable(request):
    """AJAX: validate form, store in session, send OTP."""
    if request.method == 'POST':
        form = PostVegetableForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            post_type = request.POST.get('post_type', 'sell')
            is_donation = post_type == 'donate'
            if not d.get('farmer_photo', '').startswith('data:image'):
                return JsonResponse({'ok': False, 'errors': {'farmer_photo': 'Please capture your face photo.'}})
            if not d.get('veggie_photo', '').startswith('data:image'):
                return JsonResponse({'ok': False, 'errors': {'veggie_photo': 'Please capture a photo of your vegetables.'}})
            # Validate price only for sell posts
            if not is_donation:
                price = d.get('price_per_kg')
                if price is None or price < 1:
                    return JsonResponse({'ok': False, 'errors': {'price_per_kg': 'Minimum price is ₱1 per kg.'}})
            # Save photos to disk now — keep only the path in session, not the raw base64
            farmer_photo_path = _save_base64_image(d['farmer_photo'], 'faces/farmers')
            veggie_photo_path = _save_base64_image(d['veggie_photo'], 'veggies')
            _clear_pending(request, 'pending_post', ['farmer_photo_path', 'veggie_photo_path'])
            request.session['pending_post'] = {
                'farmer_name':        d['farmer_name'],
                'phone_number':       d['phone_number'],
                'farmer_photo_path':  farmer_photo_path,
                'vegetable':          d['vegetable'],
                'veggie_photo_path':  veggie_photo_path,
                'surplus_level':      d['surplus_level'],
                'quantity':           str(d['quantity']),
                'price_per_kg':       str(d['price_per_kg']),
                'pickup_address':     d.get('pickup_address', 'La Trinidad Trading Post, Benguet'),
                'pickup_note':        d.get('pickup_note', ''),
                'timer_minutes':      form.get_timer_minutes(),
                'post_type':          request.POST.get('post_type', 'sell'),
            }
            result = create_otp(d['phone_number'], 'POST')
            if not result['ok']:
                return JsonResponse({'ok': False, 'errors': {'phone_number': result['error']}})
            return JsonResponse({'ok': True, 'phone': _mask_phone(d['phone_number'])})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})
    form = PostVegetableForm()
    return render(request, 'core/post.html', {
        'form': form,
        'force_type': request.GET.get('type', ''),  # 'sell' hides donate toggle
    })


def post_verify(request):
    pending = request.session.get('pending_post')
    if not pending:
        return JsonResponse({'ok': False, 'errors': {'__all__': 'Session expired. Please try again.'}})

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            if verify_otp(pending['phone_number'], form.cleaned_data['otp_code'], 'POST'):
                minutes      = int(pending['timer_minutes'])
                is_donation  = pending.get('post_type') == 'donate'
                post = VegetablePost.objects.create(
                    farmer_name    = pending['farmer_name'],
                    phone_number   = pending['phone_number'],
                    farmer_photo   = pending.get('farmer_photo_path', ''),
                    vegetable      = pending['vegetable'],
                    veggie_photo   = pending.get('veggie_photo_path', ''),
                    surplus_level  = pending.get('surplus_level', 'LOW'),
                    quantity       = pending['quantity'],
                    price_per_kg   = 0 if is_donation else pending['price_per_kg'],
                    pickup_address = pending.get('pickup_address', 'La Trinidad Trading Post, Benguet'),
                    pickup_note    = pending.get('pickup_note', ''),
                    # Donations go straight to RESCUE; null expiry = no timer
                    status         = VegetablePost.STATUS_RESCUE if is_donation else VegetablePost.STATUS_ACTIVE,
                    donated_at     = timezone.now() if is_donation else None,
                    expiry_time    = None if is_donation else timezone.now() + timedelta(minutes=minutes),
                )
                del request.session['pending_post']
                if is_donation:
                    return JsonResponse({
                        'ok':          True,
                        'is_donation': True,
                        'message':     'Your donation is now live! Community kitchens can claim it for free.',
                        'post_id':     post.pk,
                        'vegetable':   post.vegetable,
                        'quantity':    str(post.quantity),
                        'location':    post.get_full_location(),
                        'farmer_name': post.farmer_name,
                        'phone':       _mask_phone(post.phone_number),
                    })
                label = f"{minutes // 60} hour{'s' if minutes >= 120 else ''}" if minutes >= 60 else f"{minutes} minute{'s' if minutes > 1 else ''}"
                return JsonResponse({
                    'ok':           True,
                    'is_donation':  False,
                    'message':      f"Your post is now live for {label}!",
                    'post_id':      post.pk,
                    'vegetable':    post.vegetable,
                    'quantity':     str(post.quantity),
                    'price_per_kg': str(post.price_per_kg),
                    'location':     post.get_full_location(),
                    'expiry_label': label,
                    'farmer_name':  post.farmer_name,
                    'phone':        _mask_phone(post.phone_number),
                })
            else:
                return JsonResponse({'ok': False, 'errors': {'otp_code': '* Invalid or expired OTP.'}})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})

    return JsonResponse({'ok': False, 'errors': {'__all__': 'Invalid request'}})


# ── Buy (was Claim) ───────────────────────────────────────────────────────────

def buy_start(request, post_id):
    """GET: render full-page buy form. POST: AJAX validate + send OTP."""
    _sync_all_posts()
    post = get_object_or_404(VegetablePost, pk=post_id, status=VegetablePost.STATUS_ACTIVE)

    if request.method == 'POST':
        form = BuyForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            if d['phone_number'] == post.phone_number:
                return JsonResponse({'ok': False, 'errors': {'phone_number': 'You cannot buy your own post.'}})
            # Duplicate buy guard — same phone can't buy the same post twice
            if BuyRecord.objects.filter(post=post, buyer_number=d['phone_number']).exists():
                return JsonResponse({'ok': False, 'errors': {'phone_number': 'You have already purchased from this post.'}})
            qty = d['quantity_kg']
            if qty > post.quantity:
                return JsonResponse({'ok': False, 'errors': {'quantity_kg': f'Cannot exceed available quantity ({post.quantity} kg).'}})
            _clear_pending(request, 'pending_buy', ['buyer_photo_path'])
            request.session['pending_buy'] = {
                'post_id':           post.pk,
                'buyer_name':        d['buyer_name'],
                'phone_number':      d['phone_number'],
                'buyer_photo_path':  _save_base64_image(d['buyer_photo'], 'faces/buyers') if d.get('buyer_photo', '').startswith('data:image') else '',
                'quantity_kg':       str(qty),
            }
            result = create_otp(d['phone_number'], 'BUY', post_id=post.pk)
            if not result['ok']:
                return JsonResponse({'ok': False, 'errors': {'phone_number': result['error']}})
            return JsonResponse({'ok': True, 'phone': _mask_phone(d['phone_number'])})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})

    form = BuyForm()
    return render(request, 'core/buy.html', {'form': form, 'post': post})


def buy_verify(request):
    pending = request.session.get('pending_buy')
    if not pending:
        return JsonResponse({'ok': False, 'errors': {'__all__': 'Session expired. Please try again.'}})

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            if verify_otp(pending['phone_number'], form.cleaned_data['otp_code'], 'BUY'):
                from django.db import transaction
                from decimal import Decimal

                qty_bought = Decimal(pending.get('quantity_kg', '0'))

                with transaction.atomic():
                    post = get_object_or_404(
                        VegetablePost.objects.select_for_update(),
                        pk=pending['post_id'],
                        status=VegetablePost.STATUS_ACTIVE,
                    )
                    if qty_bought > post.quantity:
                        return JsonResponse({
                            'ok': False,
                            'errors': {'__all__': f'Only {post.quantity} kg remaining. Please go back and update your quantity.'},
                        })

                    buyer_photo   = pending.get('buyer_photo_path', '')
                    post.quantity -= qty_bought
                    if post.quantity <= 0:
                        post.quantity = 0
                        post.status   = VegetablePost.STATUS_BOUGHT
                    _recalc_surplus(post)
                    post.save(update_fields=['quantity', 'status', 'surplus_level'])

                    BuyRecord.objects.create(
                        post         = post,
                        buyer_name   = pending['buyer_name'],
                        buyer_number = pending['phone_number'],
                        buyer_photo  = buyer_photo,
                        quantity_kg  = qty_bought,
                    )
                send_buy_notification(
                    farmer_phone     = post.phone_number,
                    buyer_name       = pending['buyer_name'],
                    buyer_phone      = pending['phone_number'],
                    vegetable        = post.vegetable,
                    quantity         = qty_bought,
                    price_per_kg     = post.price_per_kg,
                    location         = post.get_full_location(),
                    buyer_photo_url  = request.build_absolute_uri(settings.MEDIA_URL + buyer_photo) if buyer_photo else '',
                )
                send_buy_confirmation(
                    buyer_phone  = pending['phone_number'],
                    buyer_name   = pending['buyer_name'],
                    vegetable    = post.vegetable,
                    quantity     = qty_bought,
                    price_per_kg = post.price_per_kg,
                    farmer_name  = post.farmer_name,
                    farmer_phone = post.phone_number,
                    location     = post.get_full_location(),
                )
                del request.session['pending_buy']
                msg = f"Purchase confirmed! Pick up at: {post.get_full_location()}"
                if float(post.quantity) > 0:
                    msg += f" ({float(post.quantity):g} kg still available.)"
                return JsonResponse({
                    'ok': True,
                    'message':           msg,
                    'ref':               f"BUY-{post.pk:05d}",
                    'vegetable':         post.vegetable,
                    'quantity':          str(qty_bought),
                    'price_per_kg':      str(post.price_per_kg),
                    'location':          post.get_full_location(),
                    'farmer_name':       post.farmer_name,
                    'farmer_phone':      post.phone_number,
                    'farmer_photo_url':  post.farmer_photo.url if post.farmer_photo else '',
                    'buyer_photo_url':   request.build_absolute_uri(settings.MEDIA_URL + buyer_photo) if buyer_photo else '',
                })
            else:
                return JsonResponse({'ok': False, 'errors': {'otp_code': '* Invalid or expired OTP.'}})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})

    return JsonResponse({'ok': False, 'errors': {'__all__': 'Invalid request'}})


# ── Rescue ────────────────────────────────────────────────────────────────────

def rescue_list(request):
    _sync_all_posts()
    posts = VegetablePost.objects.filter(status=VegetablePost.STATUS_RESCUE).order_by('expiry_time')
    return render(request, 'core/donate.html', {'posts': posts})


def rescue_start(request, post_id):
    """GET: render rescue claim page. POST: AJAX validate + send OTP."""
    post = get_object_or_404(VegetablePost, pk=post_id, status=VegetablePost.STATUS_RESCUE)
    if request.method == 'POST':
        form = RescueForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            if d['phone_number'] == post.phone_number:
                return JsonResponse({'ok': False, 'errors': {'phone_number': 'You cannot claim your own post.'}})
            # Duplicate claim guard — same phone can't claim the same post twice
            if RescueRecord.objects.filter(post=post, claimer_number=d['phone_number']).exists():
                return JsonResponse({'ok': False, 'errors': {'phone_number': 'You have already claimed this post.'}})
            qty = d['quantity_kg']
            if qty > post.quantity:
                return JsonResponse({'ok': False, 'errors': {'quantity_kg': f'Cannot exceed remaining quantity ({post.quantity} kg).'}})
            _clear_pending(request, 'pending_rescue', ['claimer_photo_path'])
            request.session['pending_rescue'] = {
                'post_id':             post.pk,
                'claimer_name':        d['claimer_name'],
                'phone_number':        d['phone_number'],
                'claimer_photo_path':  _save_base64_image(d['claimer_photo'], 'faces/claimers') if d.get('claimer_photo', '').startswith('data:image') else '',
                'quantity_kg':         str(qty),
            }
            result = create_otp(d['phone_number'], 'RESCUE', post_id=post.pk)
            if not result['ok']:
                return JsonResponse({'ok': False, 'errors': {'phone_number': result['error']}})
            return JsonResponse({'ok': True, 'phone': _mask_phone(d['phone_number'])})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})
    form = RescueForm()
    return render(request, 'core/donate_claim.html', {'form': form, 'post': post})


def rescue_verify(request):
    """AJAX: verify OTP and complete rescue claim."""
    pending = request.session.get('pending_rescue')
    if not pending:
        return JsonResponse({'ok': False, 'errors': {'__all__': 'Session expired. Please try again.'}})

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            if verify_otp(pending['phone_number'], form.cleaned_data['otp_code'], 'RESCUE'):
                from django.db import transaction
                from decimal import Decimal

                qty_claimed = Decimal(pending.get('quantity_kg', '0'))

                with transaction.atomic():
                    # Re-fetch with lock to prevent race conditions
                    post = get_object_or_404(
                        VegetablePost.objects.select_for_update(),
                        pk=pending['post_id'],
                        status=VegetablePost.STATUS_RESCUE,
                    )

                    # Guard: someone else may have claimed the remaining stock
                    if qty_claimed > post.quantity:
                        return JsonResponse({
                            'ok': False,
                            'errors': {'__all__': f'Only {post.quantity} kg remaining. Please go back and update your quantity.'},
                        })

                    claimer_photo = pending.get('claimer_photo_path', '')

                    # Deduct quantity
                    post.quantity -= qty_claimed
                    # Close the post only when fully claimed
                    if post.quantity <= 0:
                        post.quantity = 0
                        post.status   = VegetablePost.STATUS_CLAIMED
                    _recalc_surplus(post)
                    post.save(update_fields=['quantity', 'status', 'surplus_level'])

                    RescueRecord.objects.create(
                        post           = post,
                        claimer_name   = pending['claimer_name'],
                        claimer_number = pending['phone_number'],
                        claimer_photo  = claimer_photo,
                        quantity_kg    = qty_claimed,
                    )

                remaining = float(post.quantity)
                send_rescue_notification(
                    farmer_phone        = post.phone_number,
                    claimer_name        = pending['claimer_name'],
                    claimer_phone       = pending['phone_number'],
                    vegetable           = post.vegetable,
                    quantity            = qty_claimed,
                    location            = post.get_full_location(),
                    claimer_photo_url   = request.build_absolute_uri(settings.MEDIA_URL + claimer_photo) if claimer_photo else '',
                )
                send_rescue_confirmation(
                    claimer_phone  = pending['phone_number'],
                    claimer_name   = pending['claimer_name'],
                    vegetable      = post.vegetable,
                    quantity       = qty_claimed,
                    farmer_name    = post.farmer_name,
                    farmer_phone   = post.phone_number,
                    location       = post.get_full_location(),
                )
                del request.session['pending_rescue']

                msg = 'Claim confirmed! Thank you for helping reduce food waste.'
                if remaining > 0:
                    msg += f' ({remaining:g} kg still available for others.)'

                return JsonResponse({
                    'ok': True,
                    'message':            msg,
                    'ref':                f"CLAIM-{post.pk:05d}",
                    'vegetable':          post.vegetable,
                    'quantity':           str(qty_claimed),
                    'location':           post.get_full_location(),
                    'farmer_name':        post.farmer_name,
                    'farmer_phone':       post.phone_number,
                    'farmer_photo_url':   post.farmer_photo.url if post.farmer_photo else '',
                    'claimer_photo_url':  request.build_absolute_uri(settings.MEDIA_URL + claimer_photo) if claimer_photo else '',
                })
            else:
                return JsonResponse({'ok': False, 'errors': {'otp_code': '* Invalid or expired OTP.'}})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})
    return JsonResponse({'ok': False, 'errors': {'__all__': 'Invalid request'}})


# ── Donate (farmer moves post to rescue) ─────────────────────────────────────

def donate_request(request, post_id):
    """AJAX: send OTP to farmer's number to verify they own the post, or skip if manage-unlocked."""
    post = get_object_or_404(VegetablePost, pk=post_id, status=VegetablePost.STATUS_ACTIVE)
    if request.method == 'POST':
        if _is_manage_unlocked(request, post.pk):
            return JsonResponse({'ok': True, 'phone': _mask_phone(post.phone_number), 'skip_otp': True})
        result = create_otp(post.phone_number, 'DONATE', post_id=post.pk)
        if not result['ok']:
            return JsonResponse({'ok': False, 'error': result['error']})
        return JsonResponse({'ok': True, 'phone': _mask_phone(post.phone_number)})
    return JsonResponse({'ok': False})


def donate_verify(request, post_id):
    """AJAX: verify OTP (or use manage session) then move post to rescue."""
    post = get_object_or_404(VegetablePost, pk=post_id, status=VegetablePost.STATUS_ACTIVE)
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '')
        unlocked = _is_manage_unlocked(request, post.pk)
        if unlocked or verify_otp(post.phone_number, otp_code, 'DONATE', post_id=post.pk):
            post.status = VegetablePost.STATUS_RESCUE
            post.donated_at = timezone.now()
            post.save(update_fields=['status', 'donated_at'])
            return JsonResponse({'ok': True, 'message': 'Post moved to Donate. Community kitchens can now claim it for free.'})
        return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP.'})
    return JsonResponse({'ok': False})



# ── Manage Post (single OTP unlocks donate/edit/delete) ──────────────────────

def manage_request(request, post_id):
    """AJAX: send OTP to farmer to unlock manage actions."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if post.status in (VegetablePost.STATUS_BOUGHT, VegetablePost.STATUS_CLAIMED):
        return JsonResponse({'ok': False, 'error': 'This post has already been completed.'})
    if request.method == 'POST':
        result = create_otp(post.phone_number, 'MANAGE', post_id=post.pk)
        if not result['ok']:
            return JsonResponse({'ok': False, 'error': result['error']})
        return JsonResponse({'ok': True, 'phone': _mask_phone(post.phone_number)})
    return JsonResponse({'ok': False})


def manage_verify(request, post_id):
    """AJAX: verify OTP then store manage token in session."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '')
        if verify_otp(post.phone_number, otp_code, 'MANAGE', post_id=post.pk):
            # Store unlocked post id in session with timestamp — expires after 15 minutes
            _set_manage_unlocked(request, post.pk)
            return JsonResponse({'ok': True})
        return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP.'})
    return JsonResponse({'ok': False})


# ── Edit Post ─────────────────────────────────────────────────────────────────

def post_edit_request(request, post_id):
    """AJAX: send OTP to farmer to verify ownership before editing, or skip if manage-unlocked."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if post.status in (VegetablePost.STATUS_BOUGHT, VegetablePost.STATUS_CLAIMED):
        return JsonResponse({'ok': False, 'error': 'Cannot edit a post that has already been completed.'})
    if request.method == 'POST':
        if _is_manage_unlocked(request, post.pk):
            return JsonResponse({'ok': True, 'phone': _mask_phone(post.phone_number), 'skip_otp': True})
        result = create_otp(post.phone_number, 'EDIT', post_id=post.pk)
        if not result['ok']:
            return JsonResponse({'ok': False, 'error': result['error']})
        return JsonResponse({'ok': True, 'phone': _mask_phone(post.phone_number)})
    return JsonResponse({'ok': False})


def post_edit_verify(request, post_id):
    """AJAX: verify OTP (or use manage session) then save edits."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '')
        unlocked = _is_manage_unlocked(request, post.pk)
        if not unlocked and not verify_otp(post.phone_number, otp_code, 'EDIT', post_id=post.pk):
            return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP.'})

        # If additional edit fields are provided, save them
        vegetable     = request.POST.get('vegetable', '').strip()
        quantity      = request.POST.get('quantity', '').strip()
        price_per_kg  = request.POST.get('price_per_kg', '').strip()
        surplus_level = request.POST.get('surplus_level', '').strip()

        if vegetable:
            post.vegetable = vegetable
        if quantity:
            try:
                post.quantity = float(quantity)
            except ValueError:
                pass
        if price_per_kg:
            try:
                post.price_per_kg = float(price_per_kg)
            except ValueError:
                pass
        # Only update pickup_note if the field was explicitly sent in the request
        if 'pickup_note' in request.POST:
            post.pickup_note = request.POST.get('pickup_note', '').strip()
        if surplus_level in ('LOW', 'MEDIUM', 'HIGH'):
            post.surplus_level = surplus_level
        post.save()

        return JsonResponse({
            'ok': True,
            'post': {
                'vegetable':    post.vegetable,
                'quantity':     str(post.quantity),
                'price_per_kg': str(post.price_per_kg),
                'pickup_note':  post.pickup_note,
                'surplus_level': post.surplus_level,
            }
        })
    return JsonResponse({'ok': False})


# ── Delete Post ───────────────────────────────────────────────────────────────

def post_delete_request(request, post_id):
    """AJAX: send OTP to farmer to verify ownership before deleting, or skip if manage-unlocked."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if post.status in (VegetablePost.STATUS_BOUGHT, VegetablePost.STATUS_CLAIMED):
        return JsonResponse({'ok': False, 'error': 'Cannot delete a post that has already been completed.'})
    if request.method == 'POST':
        if _is_manage_unlocked(request, post.pk):
            return JsonResponse({'ok': True, 'phone': _mask_phone(post.phone_number), 'skip_otp': True})
        result = create_otp(post.phone_number, 'DELETE', post_id=post.pk)
        if not result['ok']:
            return JsonResponse({'ok': False, 'error': result['error']})
        return JsonResponse({'ok': True, 'phone': _mask_phone(post.phone_number)})
    return JsonResponse({'ok': False})


def post_delete_verify(request, post_id):
    """AJAX: verify OTP (or use manage session) then delete the post."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '')
        unlocked = _is_manage_unlocked(request, post.pk)
        if unlocked or verify_otp(post.phone_number, otp_code, 'DELETE', post_id=post.pk):
            _clear_manage_unlocked(request, post.pk)
            post.delete()
            return JsonResponse({'ok': True, 'message': 'Post deleted successfully.'})
        return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP.'})
    return JsonResponse({'ok': False})


# ── Expiry Notify (called by client-side timer) ───────────────────────────────

def notify_expiry(request, post_id):
    """AJAX POST: send a one-time expiry warning SMS for a specific post.
    The client timer calls this when the countdown crosses the warning threshold.
    Guard: only sends if expiry_notified is still False, then flips it atomically."""
    if request.method != 'POST':
        return JsonResponse({'ok': False})

    import threading
    from django.db import transaction

    with transaction.atomic():
        try:
            post = VegetablePost.objects.select_for_update().get(
                pk=post_id,
                status=VegetablePost.STATUS_ACTIVE,
                expiry_notified=False,
            )
        except VegetablePost.DoesNotExist:
            # Already notified or post no longer active — silently ignore
            return JsonResponse({'ok': False, 'reason': 'already_notified'})

        post.expiry_notified = True
        post.save(update_fields=['expiry_notified'])

    mins_left = max(1, int((post.expiry_time - timezone.now()).total_seconds() // 60))
    threading.Thread(
        target=send_expiry_warning,
        args=(post.phone_number, post.farmer_name, post.vegetable, post.quantity, mins_left),
        daemon=True,
    ).start()
    return JsonResponse({'ok': True})


# ── Global Search ──────────────────────────────────────────────────────────────

def global_search(request):
    form = GlobalSearchForm(request.GET or None)
    qs = VegetablePost.objects.filter(
        status__in=[VegetablePost.STATUS_ACTIVE, VegetablePost.STATUS_RESCUE]
    ).order_by('-created_at')

    if form.is_valid():
        q = form.cleaned_data.get('q')
        status = form.cleaned_data.get('status') or ''
        if q:
            qs = qs.filter(
                Q(vegetable__icontains=q) |
                Q(farmer_name__icontains=q) |
                Q(pickup_address__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)

    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    return render(request, 'core/global_search.html', {
        'form': form,
        'posts': posts,
    })
