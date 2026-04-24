import base64
import uuid
from pathlib import Path

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from datetime import timedelta

from .models import VegetablePost, BuyRecord, RescueRecord
from .forms  import PostVegetableForm, OTPForm, BuyForm, RescueForm
from .sms    import create_otp, verify_otp, send_buy_notification, send_buy_confirmation, send_rescue_notification, send_rescue_confirmation, send_expiry_warning


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sync_all_posts():
    VegetablePost.objects.filter(
        status=VegetablePost.STATUS_ACTIVE,
        expiry_time__lte=timezone.now()
    ).update(status=VegetablePost.STATUS_RESCUE)


def _notify_expiring_posts():
    """Send a one-time SMS warning to farmers whose active posts expire within 30 minutes."""
    import threading
    warning_window = timezone.now() + timedelta(minutes=30)
    posts = VegetablePost.objects.filter(
        status=VegetablePost.STATUS_ACTIVE,
        expiry_time__lte=warning_window,
        expiry_time__gt=timezone.now(),
        expiry_notified=False,
    )
    if not posts.exists():
        return
    # Mark first to avoid duplicate sends if two requests race
    ids = list(posts.values_list('pk', flat=True))
    VegetablePost.objects.filter(pk__in=ids).update(expiry_notified=True)
    for post in posts:
        mins_left = max(1, int((post.expiry_time - timezone.now()).total_seconds() // 60))
        threading.Thread(
            target=send_expiry_warning,
            args=(post.phone_number, post.farmer_name, post.vegetable, post.quantity, mins_left),
            daemon=True,
        ).start()


def splash(request):
    return render(request, 'core/splash.html')


def _save_base64_image(b64_string, subfolder):
    """Decode a base64 data-URI and save to MEDIA_ROOT. Returns relative path."""
    # Strip the data:image/...;base64, prefix
    if ',' in b64_string:
        header, data = b64_string.split(',', 1)
        ext = header.split('/')[1].split(';')[0]  # e.g. 'jpeg' or 'png'
    else:
        data = b64_string
        ext  = 'jpg'

    filename  = f"{uuid.uuid4().hex}.{ext}"
    rel_path  = f"{subfolder}/{filename}"
    full_path = Path(settings.MEDIA_ROOT) / subfolder
    full_path.mkdir(parents=True, exist_ok=True)
    (full_path / filename).write_bytes(base64.b64decode(data))
    return rel_path


# ── Home ──────────────────────────────────────────────────────────────────────

def home(request):
    _sync_all_posts()
    _notify_expiring_posts()
    posts = VegetablePost.objects.filter(status=VegetablePost.STATUS_ACTIVE).order_by('expiry_time')
    return render(request, 'core/home.html', {'posts': posts})


# ── Category ──────────────────────────────────────────────────────────────────

def category(request):
    _sync_all_posts()
    _notify_expiring_posts()
    level  = request.GET.get('level', '')
    posts  = VegetablePost.objects.filter(status=VegetablePost.STATUS_ACTIVE)
    if level in ('LOW', 'MEDIUM', 'HIGH'):
        posts = posts.filter(surplus_level=level)
    posts = posts.order_by('expiry_time')
    return render(request, 'core/category.html', {'posts': posts, 'active_level': level})


# ── Posted Veggies (all active with photos) ───────────────────────────────────

def posted_veggies(request):
    _sync_all_posts()
    posts = VegetablePost.objects.filter(status=VegetablePost.STATUS_ACTIVE).order_by('-created_at')
    return render(request, 'core/posted_veggies.html', {'posts': posts})


def post_detail(request, post_id):
    _sync_all_posts()
    post       = get_object_or_404(VegetablePost, pk=post_id)
    claim_form = ClaimForm()
    otp_form   = OTPForm()
    return render(request, 'core/post_detail.html', {'post': post, 'claim_form': claim_form, 'otp_form': otp_form})


# ── Post Vegetable ─────────────────────────────────────────────────────────────

def post_vegetable(request):
    """AJAX: validate form, store in session, send OTP."""
    if request.method == 'POST':
        form = PostVegetableForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            if not d.get('farmer_photo', '').startswith('data:image'):
                return JsonResponse({'ok': False, 'errors': {'farmer_photo': 'Please capture your face photo.'}})
            if not d.get('veggie_photo', '').startswith('data:image'):
                return JsonResponse({'ok': False, 'errors': {'veggie_photo': 'Please capture a photo of your vegetables.'}})
            # Save photos to disk now — keep only the path in session, not the raw base64
            farmer_photo_path = _save_base64_image(d['farmer_photo'], 'faces/farmers')
            veggie_photo_path = _save_base64_image(d['veggie_photo'], 'veggies')
            request.session['pending_post'] = {
                'farmer_name':        d['farmer_name'],
                'phone_number':       d['phone_number'],
                'farmer_photo_path':  farmer_photo_path,
                'vegetable':          d['vegetable'],
                'veggie_photo_path':  veggie_photo_path,
                'surplus_level':      d['surplus_level'],
                'quantity':           str(d['quantity']),
                'price_per_kg':       str(d['price_per_kg']),
                'pickup_note':        d.get('pickup_note', ''),
                'timer_minutes':      form.get_timer_minutes(),
            }
            create_otp(d['phone_number'], 'POST')
            return JsonResponse({'ok': True, 'phone': d['phone_number']})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})
    form = PostVegetableForm()
    return render(request, 'core/post.html', {'form': form})


def post_verify(request):
    pending = request.session.get('pending_post')
    if not pending:
        return JsonResponse({'ok': False, 'errors': {'__all__': 'Session expired. Please try again.'}})

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            if verify_otp(pending['phone_number'], form.cleaned_data['otp_code'], 'POST'):
                minutes      = int(pending['timer_minutes'])
                post = VegetablePost.objects.create(
                    farmer_name    = pending['farmer_name'],
                    phone_number   = pending['phone_number'],
                    farmer_photo   = pending.get('farmer_photo_path', ''),
                    vegetable      = pending['vegetable'],
                    veggie_photo   = pending.get('veggie_photo_path', ''),
                    surplus_level  = pending.get('surplus_level', 'LOW'),
                    quantity       = pending['quantity'],
                    price_per_kg   = pending['price_per_kg'],
                    pickup_note    = pending.get('pickup_note', ''),
                    expiry_time    = timezone.now() + timedelta(minutes=minutes),
                )
                del request.session['pending_post']
                label = f"{minutes // 60} hour{'s' if minutes >= 120 else ''}" if minutes >= 60 else f"{minutes} minute{'s' if minutes > 1 else ''}"
                return JsonResponse({'ok': True, 'message': f"Your post is now live for {label}! Post ID: #{post.pk}"})
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
            qty = d['quantity_kg']
            if qty > post.quantity:
                return JsonResponse({'ok': False, 'errors': {'quantity_kg': f'Cannot exceed available quantity ({post.quantity} kg).'}})
            request.session['pending_buy'] = {
                'post_id':           post.pk,
                'buyer_name':        d['buyer_name'],
                'phone_number':      d['phone_number'],
                'buyer_photo_path':  _save_base64_image(d['buyer_photo'], 'faces/buyers') if d.get('buyer_photo', '').startswith('data:image') else '',
                'quantity_kg':       str(qty),
            }
            create_otp(d['phone_number'], 'BUY', post_id=post.pk)
            return JsonResponse({'ok': True, 'phone': d['phone_number']})
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
                post        = get_object_or_404(VegetablePost, pk=pending['post_id'])
                buyer_photo = pending.get('buyer_photo_path', '')
                post.status = VegetablePost.STATUS_BOUGHT
                post.save(update_fields=['status'])
                BuyRecord.objects.create(
                    post         = post,
                    buyer_name   = pending['buyer_name'],
                    buyer_number = pending['phone_number'],
                    buyer_photo  = buyer_photo,
                    quantity_kg  = pending.get('quantity_kg', post.quantity),
                )
                send_buy_notification(
                    farmer_phone = post.phone_number,
                    buyer_name   = pending['buyer_name'],
                    buyer_phone  = pending['phone_number'],
                    vegetable    = post.vegetable,
                    quantity     = pending.get('quantity_kg', post.quantity),
                    price_per_kg = post.price_per_kg,
                    location     = post.get_full_location(),
                )
                send_buy_confirmation(
                    buyer_phone  = pending['phone_number'],
                    buyer_name   = pending['buyer_name'],
                    vegetable    = post.vegetable,
                    quantity     = pending.get('quantity_kg', post.quantity),
                    price_per_kg = post.price_per_kg,
                    farmer_name  = post.farmer_name,
                    farmer_phone = post.phone_number,
                    location     = post.get_full_location(),
                )
                del request.session['pending_buy']
                return JsonResponse({
                    'ok': True,
                    'message': f"Purchase confirmed! Pick up at: {post.get_full_location()}",
                    'farmer_name':  post.farmer_name,
                    'farmer_phone': post.phone_number,
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
    posts     = VegetablePost.objects.filter(status=VegetablePost.STATUS_RESCUE).order_by('expiry_time')
    otp_form  = OTPForm()
    return render(request, 'core/rescue.html', {'posts': posts, 'otp_form': otp_form})


def rescue_start(request, post_id):
    """GET: render rescue claim page. POST: AJAX validate + send OTP."""
    post = get_object_or_404(VegetablePost, pk=post_id, status=VegetablePost.STATUS_RESCUE)
    if request.method == 'POST':
        form = RescueForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            if d['phone_number'] == post.phone_number:
                return JsonResponse({'ok': False, 'errors': {'phone_number': 'You cannot claim your own post.'}})
            qty = d['quantity_kg']
            if qty > post.quantity:
                return JsonResponse({'ok': False, 'errors': {'quantity_kg': f'Cannot exceed remaining quantity ({post.quantity} kg).'}})
            request.session['pending_rescue'] = {
                'post_id':             post.pk,
                'claimer_name':        d['claimer_name'],
                'phone_number':        d['phone_number'],
                'claimer_photo_path':  _save_base64_image(d['claimer_photo'], 'faces/claimers') if d.get('claimer_photo', '').startswith('data:image') else '',
                'quantity_kg':         str(qty),
            }
            create_otp(d['phone_number'], 'RESCUE', post_id=post.pk)
            return JsonResponse({'ok': True, 'phone': d['phone_number']})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})
    # GET — render the full-page rescue claim form
    form = RescueForm()
    return render(request, 'core/rescue_claim.html', {'form': form, 'post': post})


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
                    post.save(update_fields=['quantity', 'status'])

                    RescueRecord.objects.create(
                        post           = post,
                        claimer_name   = pending['claimer_name'],
                        claimer_number = pending['phone_number'],
                        claimer_photo  = claimer_photo,
                        quantity_kg    = qty_claimed,
                    )

                remaining = float(post.quantity)
                send_rescue_notification(
                    farmer_phone   = post.phone_number,
                    claimer_name   = pending['claimer_name'],
                    claimer_phone  = pending['phone_number'],
                    vegetable      = post.vegetable,
                    quantity       = qty_claimed,
                    location       = post.get_full_location(),
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
                    'message': msg,
                    'farmer_name':  post.farmer_name,
                    'farmer_phone': post.phone_number,
                })
            else:
                return JsonResponse({'ok': False, 'errors': {'otp_code': '* Invalid or expired OTP.'}})
        else:
            errors = {f: e.as_text() for f, e in form.errors.items()}
            return JsonResponse({'ok': False, 'errors': errors})
    return JsonResponse({'ok': False, 'errors': {'__all__': 'Invalid request'}})


# ── Donate (farmer moves post to rescue) ─────────────────────────────────────

def donate_request(request, post_id):
    """AJAX: send OTP to farmer's number to verify they own the post."""
    post = get_object_or_404(VegetablePost, pk=post_id, status=VegetablePost.STATUS_ACTIVE)
    if request.method == 'POST':
        create_otp(post.phone_number, 'DONATE', post_id=post.pk)
        return JsonResponse({'ok': True, 'phone': post.phone_number})
    return JsonResponse({'ok': False})


def donate_verify(request, post_id):
    """AJAX: verify OTP then move post to rescue."""
    post = get_object_or_404(VegetablePost, pk=post_id, status=VegetablePost.STATUS_ACTIVE)
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '')
        if verify_otp(post.phone_number, otp_code, 'DONATE'):
            post.status = VegetablePost.STATUS_RESCUE
            post.save(update_fields=['status'])
            return JsonResponse({'ok': True, 'message': 'Post moved to Donate. Community kitchens can now claim it for free.'})
        return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP.'})
    return JsonResponse({'ok': False})


# ── Edit Post ─────────────────────────────────────────────────────────────────

def post_edit_request(request, post_id):
    """AJAX: send OTP to farmer to verify ownership before editing."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if post.status in (VegetablePost.STATUS_BOUGHT, VegetablePost.STATUS_CLAIMED):
        return JsonResponse({'ok': False, 'error': 'Cannot edit a post that has already been completed.'})
    if request.method == 'POST':
        create_otp(post.phone_number, 'EDIT', post_id=post.pk)
        return JsonResponse({'ok': True, 'phone': post.phone_number})
    return JsonResponse({'ok': False})


def post_edit_verify(request, post_id):
    """AJAX: verify OTP then return post data for editing, or save edits."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '')
        if not verify_otp(post.phone_number, otp_code, 'EDIT'):
            return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP.'})

        # If additional edit fields are provided, save them
        vegetable   = request.POST.get('vegetable', '').strip()
        quantity    = request.POST.get('quantity', '').strip()
        price_per_kg = request.POST.get('price_per_kg', '').strip()
        pickup_note = request.POST.get('pickup_note', '').strip()
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
        if pickup_note is not None:
            post.pickup_note = pickup_note
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
    """AJAX: send OTP to farmer to verify ownership before deleting."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if post.status in (VegetablePost.STATUS_BOUGHT, VegetablePost.STATUS_CLAIMED):
        return JsonResponse({'ok': False, 'error': 'Cannot delete a post that has already been completed.'})
    if request.method == 'POST':
        create_otp(post.phone_number, 'DELETE', post_id=post.pk)
        return JsonResponse({'ok': True, 'phone': post.phone_number})
    return JsonResponse({'ok': False})


def post_delete_verify(request, post_id):
    """AJAX: verify OTP then delete the post."""
    post = get_object_or_404(VegetablePost, pk=post_id)
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '')
        if verify_otp(post.phone_number, otp_code, 'DELETE'):
            post.delete()
            return JsonResponse({'ok': True, 'message': 'Post deleted successfully.'})
        return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP.'})
    return JsonResponse({'ok': False})
