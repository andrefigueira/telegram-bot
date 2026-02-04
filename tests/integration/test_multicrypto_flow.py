"""Integration tests for multi-cryptocurrency order flow."""

import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from datetime import datetime

from bot.models import Database, Product, Vendor, Order
from bot.services.orders import OrderService
from bot.services.catalog import CatalogService
from bot.services.vendors import VendorService
from bot.services.payment_factory import PaymentServiceFactory


@pytest.fixture
def test_db():
    """Create test database."""
    db = Database("sqlite:///:memory:")
    yield db


@pytest.fixture
def test_vendor(test_db):
    """Create test vendor with all wallet addresses."""
    vendors = VendorService(test_db)
    vendor = vendors.add_vendor(
        Vendor(
            telegram_id=12345,
            name="Test Vendor",
            wallet_address="4AdUndXHHZ6cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx3skxNgYeYTRj5UzqtReoS44qo9mtmXCqY45DJ852K5Jv2684Rge",
            btc_wallet_address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            eth_wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2"
        )
    )
    return vendor


@pytest.fixture
def test_product(test_db, test_vendor):
    """Create test product."""
    catalog = CatalogService(test_db)
    product = catalog.add_product(
        Product(
            name="Test Product",
            description="A test product",
            price_fiat=Decimal("50.00"),
            currency="USD",
            price_xmr=Decimal("0.33"),
            inventory=100,
            vendor_id=test_vendor.id
        )
    )
    return product


@pytest.fixture
def order_service(test_db, test_vendor):
    """Create order service with mocked payment services."""
    with patch('bot.services.orders.get_settings') as mock_settings:
        mock_settings.return_value.encryption_key = "dGVzdC1rZXktZm9yLXRlc3RpbmctcHVycG9zZXMtb25seQ=="
        mock_settings.return_value.environment = "development"

        # Mock payment services
        with patch('bot.services.orders.PaymentService'):
            catalog = CatalogService(test_db)
            vendors = VendorService(test_db)
            payments = None  # Will be mocked

            service = OrderService(test_db, payments, catalog, vendors)
            return service


class TestMultiCurrencyOrderCreation:
    """Test creating orders with different currencies."""

    def test_create_order_with_xmr(self, order_service, test_product):
        """Test creating order with XMR payment."""
        with patch('bot.services.bitcoin_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "development"

            with patch('bot.services.orders.fiat_to_crypto') as mock_convert:
                async def mock_fiat_to_crypto(amount, fiat, crypto):
                    rates = {"XMR": 150, "BTC": 45000, "ETH": 3000}
                    return amount / Decimal(str(rates[crypto]))

                mock_convert.side_effect = mock_fiat_to_crypto

                order_data = order_service.create_order(
                    product_id=test_product.id,
                    quantity=2,
                    address="123 Test St",
                    payment_currency="XMR"
                )

                assert order_data["payment_currency"] == "XMR"
                assert "payment_address" in order_data
                assert "payment_id" in order_data
                assert order_data["total_crypto"] > 0
                assert order_data["confirmations_required"] == 10

    def test_create_order_with_btc(self, order_service, test_product):
        """Test creating order with BTC payment."""
        with patch('bot.services.bitcoin_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "development"
            mock_settings.return_value.blockcypher_api_key = None

            with patch('bot.services.orders.fiat_to_crypto') as mock_convert:
                async def mock_fiat_to_crypto(amount, fiat, crypto):
                    rates = {"XMR": 150, "BTC": 45000, "ETH": 3000}
                    return amount / Decimal(str(rates[crypto]))

                mock_convert.side_effect = mock_fiat_to_crypto

                order_data = order_service.create_order(
                    product_id=test_product.id,
                    quantity=1,
                    address="456 Test Ave",
                    payment_currency="BTC"
                )

                assert order_data["payment_currency"] == "BTC"
                assert order_data["payment_address"] == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
                assert order_data["confirmations_required"] == 6

    def test_create_order_with_eth(self, order_service, test_product):
        """Test creating order with ETH payment."""
        with patch('bot.services.ethereum_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "development"
            mock_settings.return_value.etherscan_api_key = "test"

            with patch('bot.services.orders.fiat_to_crypto') as mock_convert:
                async def mock_fiat_to_crypto(amount, fiat, crypto):
                    rates = {"XMR": 150, "BTC": 45000, "ETH": 3000}
                    return amount / Decimal(str(rates[crypto]))

                mock_convert.side_effect = mock_fiat_to_crypto

                order_data = order_service.create_order(
                    product_id=test_product.id,
                    quantity=1,
                    address="789 Test Blvd",
                    payment_currency="ETH"
                )

                assert order_data["payment_currency"] == "ETH"
                assert order_data["payment_address"].startswith("0x")
                assert order_data["confirmations_required"] == 12


class TestOrderDatabaseStorage:
    """Test that orders are stored correctly in database."""

    def test_order_stores_payment_currency(self, test_db, test_vendor, test_product):
        """Test that payment currency is stored in database."""
        with test_db.session() as session:
            order = Order(
                product_id=test_product.id,
                vendor_id=test_vendor.id,
                quantity=1,
                payment_id="test123",
                address_encrypted="encrypted_address",
                payment_currency="BTC",
                payment_amount_crypto=Decimal("0.002"),
                commission_crypto=Decimal("0.0001"),
                commission_xmr=Decimal("0.01"),
                postage_xmr=Decimal("0")
            )
            session.add(order)
            session.commit()
            session.refresh(order)

            # Verify stored values
            assert order.payment_currency == "BTC"
            assert order.payment_amount_crypto == Decimal("0.002")
            assert order.commission_crypto == Decimal("0.0001")

    def test_order_backward_compatibility(self, test_db, test_vendor, test_product):
        """Test that old orders without payment_currency still work."""
        with test_db.session() as session:
            order = Order(
                product_id=test_product.id,
                vendor_id=test_vendor.id,
                quantity=1,
                payment_id="test456",
                address_encrypted="encrypted_address",
                commission_xmr=Decimal("0.01"),
                postage_xmr=Decimal("0")
            )
            session.add(order)
            session.commit()
            session.refresh(order)

            # Should default to XMR
            assert order.payment_currency == "XMR"


@pytest.mark.asyncio
class TestPaymentVerificationFlow:
    """Test payment verification for different currencies."""

    async def test_verify_btc_payment(self):
        """Test verifying BTC payment with mock transaction."""
        with patch('bot.services.bitcoin_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "production"
            mock_settings.return_value.blockcypher_api_key = None

            service = PaymentServiceFactory.create("BTC")

            # Mock finding payment
            from unittest.mock import Mock
            mock_tx = Mock()
            mock_tx.hash = "test_hash"
            mock_tx.received_btc = Decimal("0.001")
            mock_tx.confirmations = 6

            with patch.object(service.api, 'find_payment', new_callable=AsyncMock) as mock_find:
                mock_find.return_value = mock_tx

                result = await service.check_paid(
                    payment_id="test123",
                    expected_amount=Decimal("0.001"),
                    address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    created_at=datetime.utcnow()
                )

                assert result is True
