from django.urls import path
from . import views

app_name = "subscriptions"

urlpatterns = [
    path("pricing/", views.pricing, name="pricing"),
    path("apply-coupon/", views.apply_coupon, name="apply_coupon"),
    path("remove-coupon/", views.remove_coupon, name="remove_coupon"),
    path("create-order/", views.create_razorpay_order, name="create_order"),
    path("payment-callback/", views.razorpay_callback, name="razorpay_callback"),
    path("webhook/", views.razorpay_webhook, name="razorpay_webhook"),
    path("check-status/<str:order_id>/", views.check_payment_status, name="check_status"),
    path("my-subscription/", views.my_subscription, name="my_subscription"),
]