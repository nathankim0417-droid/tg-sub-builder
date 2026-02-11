import stripe
from app.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_checkout_session(plan_name: str, price_cents: int, metadata: dict) -> str:
    session = stripe.checkout.Session.create(
        mode="payment",  # easiest MVP first (one-time payment)
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": price_cents,
                "product_data": {"name": plan_name},
            },
            "quantity": 1,
        }],
        success_url=settings.FRONTEND_SUCCESS_URL,
        cancel_url=settings.FRONTEND_CANCEL_URL,
        metadata=metadata,
    )
    return session.url
