from django.urls import path
from . import views

urlpatterns = [
    path('',                                   views.splash,              name='splash'),
    path('home/',                              views.home,                name='home'),
    path('category/',                          views.category,            name='category'),
    path('posted/',                            views.posted_veggies,      name='posted_veggies'),

    # Post vegetable
    path('post/',                              views.post_vegetable,      name='post_vegetable'),
    path('post/verify/',                       views.post_verify,         name='post_verify'),

    # Manage (single OTP unlocks donate/edit/delete for a post)
    path('post/<int:post_id>/manage/',         views.manage_request,      name='manage_request'),
    path('post/<int:post_id>/manage/verify/',  views.manage_verify,       name='manage_verify'),

    # Edit (verify must come before the base path)
    path('post/<int:post_id>/edit/verify/',    views.post_edit_verify,    name='post_edit_verify'),
    path('post/<int:post_id>/edit/',           views.post_edit_request,   name='post_edit_request'),

    # Delete
    path('post/<int:post_id>/delete/verify/',  views.post_delete_verify,  name='post_delete_verify'),
    path('post/<int:post_id>/delete/',         views.post_delete_request, name='post_delete_request'),

    # Donate
    path('post/<int:post_id>/donate/verify/',  views.donate_verify,       name='donate_verify'),
    path('post/<int:post_id>/donate/',         views.donate_request,      name='donate_request'),

    # Buy (verify before parameterised route)
    path('buy/verify/',                        views.buy_verify,          name='buy_verify'),
    path('buy/<int:post_id>/',                 views.buy_start,           name='buy_start'),

    # Rescue / Donate listings (verify before parameterised route)
    path('rescue/',                            views.rescue_list,         name='rescue_list'),
    path('rescue/verify/',                     views.rescue_verify,       name='rescue_verify'),
    path('rescue/<int:post_id>/',              views.rescue_start,        name='rescue_start'),

    # Search
    path('search/', views.global_search, name='global_search'),
]
