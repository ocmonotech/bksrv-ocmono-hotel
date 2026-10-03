"""Online payment gateway adapter selection and mock checkout."""

from app.modules.payments.models import PaymentProvider
from app.modules.payments.providers.base import OnlineCheckoutRequest, ProviderCredentials
from app.modules.payments.providers.online_common import is_mock_credentials
from app.modules.payments.providers.registry import get_payment_provider


def test_mock_credentials_detect_demo():
    assert is_mock_credentials(
        ProviderCredentials(merchant_id="DEMO-RAZORPAY", api_key="demo-key", config={"mode": "mock"})
    )


def test_live_credentials_not_mock():
    assert not is_mock_credentials(
        ProviderCredentials(
            merchant_id="rzp_live_abc",
            client_id="rzp_live_abc",
            api_key="sk_live_secret_value_here",
            config={"mode": "live"},
        )
    )


def test_registry_returns_http_for_live_credentials():
    from app.modules.payments.providers.razorpay import RazorpayProvider

    creds = ProviderCredentials(
        client_id="rzp_test_key",
        api_key="rzp_test_secret_long",
        config={"mode": "live"},
    )
    adapter = get_payment_provider(PaymentProvider.RAZORPAY, creds)
    assert isinstance(adapter, RazorpayProvider)


def test_registry_returns_mock_for_demo_credentials():
    from app.modules.payments.providers.mock import MockRazorpayProvider

    creds = ProviderCredentials(
        merchant_id="DEMO-RAZORPAY",
        api_key="demo-key",
        config={"mode": "mock"},
    )
    adapter = get_payment_provider(PaymentProvider.RAZORPAY, creds)
    assert isinstance(adapter, MockRazorpayProvider)


async def test_mock_checkout_and_verify_decline():
    adapter = get_payment_provider(
        PaymentProvider.CASHFREE,
        ProviderCredentials(api_key="demo-key", config={"mode": "mock"}),
    )
    checkout = await adapter.create_online_checkout(
        ProviderCredentials(api_key="demo-key", config={"mode": "mock"}),
        OnlineCheckoutRequest(order_id="ORD-1", amount_inr=100),
    )
    assert checkout.success
    declined = await adapter.verify_online_payment(
        ProviderCredentials(api_key="demo-key", config={"mode": "mock"}),
        provider_order_id=checkout.provider_order_id or "ORD-1",
        payment_session_id=checkout.payment_session_id,
        card_last4="0000",
    )
    assert declined.paid is False
