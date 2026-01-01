"""Tests for payout service."""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from bot.services.payout import PayoutService
from bot.models import Database, PlatformSettings, Payout, Order, Vendor


class TestPayoutService:
    """Test PayoutService functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return MagicMock(spec=Database)

    @pytest.fixture
    def payout_service(self, mock_db):
        """Create PayoutService with mock db."""
        with patch('bot.services.payout.get_settings'):
            return PayoutService(mock_db)

    # Platform Settings Tests

    def test_get_setting_exists(self, payout_service, mock_db):
        """Test getting an existing setting."""
        mock_setting = MagicMock(spec=PlatformSettings)
        mock_setting.value = "test_value"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_setting)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_setting("test_key")

        assert result == "test_value"

    def test_get_setting_not_exists(self, payout_service, mock_db):
        """Test getting a nonexistent setting returns default."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_setting("nonexistent", "default")

        assert result == "default"

    def test_set_setting_new(self, payout_service, mock_db):
        """Test setting a new value."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.set_setting("new_key", "new_value")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_set_setting_update(self, payout_service, mock_db):
        """Test updating an existing setting."""
        mock_setting = MagicMock(spec=PlatformSettings)
        mock_setting.value = "old_value"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_setting)))
        mock_db.session = MagicMock(return_value=mock_session)

        payout_service.set_setting("key", "new_value")

        assert mock_setting.value == "new_value"
        mock_session.commit.assert_called_once()

    def test_get_platform_commission_rate_default(self, payout_service, mock_db):
        """Test getting default commission rate."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_platform_commission_rate()

        assert result == Decimal("0.05")

    def test_get_platform_commission_rate_custom(self, payout_service, mock_db):
        """Test getting custom commission rate."""
        mock_setting = MagicMock(spec=PlatformSettings)
        mock_setting.value = "0.10"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_setting)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_platform_commission_rate()

        assert result == Decimal("0.10")

    def test_get_platform_commission_rate_invalid(self, payout_service, mock_db):
        """Test getting invalid commission rate returns default."""
        mock_setting = MagicMock(spec=PlatformSettings)
        mock_setting.value = "invalid"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_setting)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_platform_commission_rate()

        assert result == Decimal("0.05")

    def test_set_platform_commission_rate(self, payout_service, mock_db):
        """Test setting commission rate."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_db.session = MagicMock(return_value=mock_session)

        payout_service.set_platform_commission_rate(Decimal("0.08"))

        mock_session.add.assert_called_once()

    def test_get_platform_wallet(self, payout_service, mock_db):
        """Test getting platform wallet."""
        mock_setting = MagicMock(spec=PlatformSettings)
        mock_setting.value = "wallet123"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_setting)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_platform_wallet()

        assert result == "wallet123"

    def test_get_platform_wallet_empty(self, payout_service, mock_db):
        """Test getting empty platform wallet returns None."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_platform_wallet()

        assert result is None

    def test_set_platform_wallet(self, payout_service, mock_db):
        """Test setting platform wallet address."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_db.session = MagicMock(return_value=mock_session)

        payout_service.set_platform_wallet("4A123456789wallet")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    # Payment Split Tests

    def test_calculate_split(self, payout_service, mock_db):
        """Test calculating vendor/platform split."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_db.session = MagicMock(return_value=mock_session)

        vendor_share, platform_share = payout_service.calculate_split(Decimal("1.0"))

        assert vendor_share == Decimal("0.95")
        assert platform_share == Decimal("0.05")

    def test_calculate_split_custom_rate(self, payout_service, mock_db):
        """Test calculating split with custom vendor rate."""
        vendor_share, platform_share = payout_service.calculate_split(
            Decimal("1.0"),
            vendor_commission_rate=Decimal("0.10")
        )

        assert vendor_share == Decimal("0.90")
        assert platform_share == Decimal("0.10")

    # Payout Management Tests

    def test_create_payout(self, payout_service, mock_db):
        """Test creating a payout record."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)

        def set_id(payout):
            payout.id = 1

        mock_session.refresh = MagicMock(side_effect=set_id)
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.create_payout(
            order_id=1,
            vendor_id=2,
            amount_xmr=Decimal("0.5")
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.order_id == 1
        assert result.vendor_id == 2
        assert result.amount_xmr == Decimal("0.5")
        assert result.status == "PENDING"

    def test_get_pending_payouts(self, payout_service, mock_db):
        """Test getting pending payouts."""
        mock_payout1 = MagicMock(spec=Payout)
        mock_payout1.status = "PENDING"
        mock_payout2 = MagicMock(spec=Payout)
        mock_payout2.status = "PENDING"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_payout1, mock_payout2])
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_pending_payouts()

        assert len(result) == 2

    def test_get_vendor_payouts(self, payout_service, mock_db):
        """Test getting payouts for a vendor."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.vendor_id = 1

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_payout])
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.get_vendor_payouts(1)

        assert len(result) == 1

    def test_mark_payout_sent(self, payout_service, mock_db):
        """Test marking a payout as sent."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.id = 1
        mock_payout.status = "PENDING"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_payout)
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.mark_payout_sent(1, "tx123hash")

        assert result.status == "SENT"
        assert result.tx_hash == "tx123hash"
        mock_session.commit.assert_called_once()

    def test_mark_payout_sent_not_found(self, payout_service, mock_db):
        """Test marking nonexistent payout as sent."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.mark_payout_sent(999, "tx123")

        assert result is None

    def test_mark_payout_confirmed(self, payout_service, mock_db):
        """Test marking a payout as confirmed."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.id = 1
        mock_payout.status = "SENT"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_payout)
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.mark_payout_confirmed(1)

        assert result.status == "CONFIRMED"
        mock_session.commit.assert_called_once()

    def test_mark_payout_confirmed_not_found(self, payout_service, mock_db):
        """Test marking nonexistent payout as confirmed."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.mark_payout_confirmed(999)

        assert result is None

    def test_mark_payout_failed(self, payout_service, mock_db):
        """Test marking a payout as failed."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.id = 1
        mock_payout.status = "PENDING"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_payout)
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.mark_payout_failed(1, "Insufficient funds")

        assert result.status == "FAILED"
        mock_session.commit.assert_called_once()

    def test_mark_payout_failed_not_found(self, payout_service, mock_db):
        """Test marking nonexistent payout as failed."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        result = payout_service.mark_payout_failed(999, "error")

        assert result is None

    # Process Payouts Tests

    @pytest.mark.asyncio
    async def test_process_payouts_no_pending(self, payout_service, mock_db):
        """Test processing when no pending payouts."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.services.payments.MoneroPaymentService'):
            result = await payout_service.process_payouts()

        assert result['processed'] == 0
        assert result['sent'] == 0
        assert result['failed'] == 0
        assert result['skipped'] == 0

    @pytest.mark.asyncio
    async def test_process_payouts_no_vendor_wallet(self, payout_service, mock_db):
        """Test processing payout when vendor has no wallet."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.id = 1
        mock_payout.vendor_id = 1
        mock_payout.status = "PENDING"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.wallet_address = None

        def mock_session_factory():
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)
            mock_session.exec = MagicMock(return_value=[mock_payout])
            mock_session.get = MagicMock(return_value=mock_vendor)
            return mock_session

        mock_db.session = mock_session_factory

        with patch('bot.services.payments.MoneroPaymentService'):
            result = await payout_service.process_payouts()

        assert result['processed'] == 1
        assert result['skipped'] == 1

    @pytest.mark.asyncio
    async def test_process_payouts_no_payment_wallet(self, payout_service, mock_db):
        """Test processing payout when payment service has no wallet."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.id = 1
        mock_payout.vendor_id = 1
        mock_payout.amount_xmr = Decimal("0.5")
        mock_payout.status = "PENDING"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendor.wallet_address = "wallet123"  # Vendor HAS a wallet

        call_count = 0

        def mock_session_factory():
            nonlocal call_count
            call_count += 1
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            if call_count == 1:
                mock_session.exec = MagicMock(return_value=[mock_payout])
            else:
                mock_session.get = MagicMock(return_value=mock_vendor)
            return mock_session

        mock_db.session = mock_session_factory

        with patch('bot.services.payments.MoneroPaymentService') as mock_payment_cls:
            mock_payment = MagicMock()
            # Payment service's _get_wallet returns None
            mock_payment._get_wallet = MagicMock(return_value=None)
            mock_payment_cls.return_value = mock_payment

            result = await payout_service.process_payouts()

        assert result['processed'] == 1
        assert result['skipped'] == 1

    @pytest.mark.asyncio
    async def test_process_payouts_success(self, payout_service, mock_db):
        """Test successful payout processing."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.id = 1
        mock_payout.vendor_id = 1
        mock_payout.amount_xmr = Decimal("0.5")
        mock_payout.status = "PENDING"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendor.wallet_address = "wallet123"

        call_count = 0

        def mock_session_factory():
            nonlocal call_count
            call_count += 1
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            if call_count == 1:
                # First call: get_pending_payouts
                mock_session.exec = MagicMock(return_value=[mock_payout])
            else:
                # Subsequent calls: get vendor
                mock_session.get = MagicMock(return_value=mock_vendor)
            return mock_session

        mock_db.session = mock_session_factory

        with patch('bot.services.payments.MoneroPaymentService') as mock_payment_cls:
            mock_wallet = MagicMock()
            mock_tx = MagicMock()
            mock_tx.hash = "tx123hash"
            mock_wallet.transfer = MagicMock(return_value=mock_tx)

            mock_payment = MagicMock()
            mock_payment._get_wallet = MagicMock(return_value=mock_wallet)
            mock_payment_cls.return_value = mock_payment

            # Mock mark_payout_sent to update payout
            def mark_sent(payout_id, tx_hash):
                mock_payout.status = "SENT"
                mock_payout.tx_hash = tx_hash
                return mock_payout

            with patch.object(payout_service, 'mark_payout_sent', side_effect=mark_sent):
                result = await payout_service.process_payouts()

        assert result['processed'] == 1
        assert result['sent'] == 1

    @pytest.mark.asyncio
    async def test_process_payouts_transfer_error(self, payout_service, mock_db):
        """Test payout processing when transfer fails."""
        mock_payout = MagicMock(spec=Payout)
        mock_payout.id = 1
        mock_payout.vendor_id = 1
        mock_payout.amount_xmr = Decimal("0.5")
        mock_payout.status = "PENDING"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendor.wallet_address = "wallet123"

        call_count = 0

        def mock_session_factory():
            nonlocal call_count
            call_count += 1
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            if call_count == 1:
                mock_session.exec = MagicMock(return_value=[mock_payout])
            else:
                mock_session.get = MagicMock(return_value=mock_vendor)
            return mock_session

        mock_db.session = mock_session_factory

        with patch('bot.services.payments.MoneroPaymentService') as mock_payment_cls:
            mock_wallet = MagicMock()
            mock_wallet.transfer = MagicMock(side_effect=Exception("Insufficient funds"))

            mock_payment = MagicMock()
            mock_payment._get_wallet = MagicMock(return_value=mock_wallet)
            mock_payment_cls.return_value = mock_payment

            def mark_failed(payout_id, error):
                mock_payout.status = "FAILED"
                return mock_payout

            with patch.object(payout_service, 'mark_payout_failed', side_effect=mark_failed):
                result = await payout_service.process_payouts()

        assert result['processed'] == 1
        assert result['failed'] == 1

    # Platform Stats Tests

    def test_get_platform_stats(self, payout_service, mock_db):
        """Test getting platform statistics."""
        mock_order = MagicMock(spec=Order)
        mock_order.state = "PAID"
        mock_order.commission_xmr = Decimal("0.05")

        mock_pending_payout = MagicMock(spec=Payout)
        mock_pending_payout.status = "PENDING"
        mock_pending_payout.amount_xmr = Decimal("0.5")

        mock_sent_payout = MagicMock(spec=Payout)
        mock_sent_payout.status = "SENT"
        mock_sent_payout.amount_xmr = Decimal("0.3")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)

        call_count = [0]

        def mock_exec(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return [mock_order]
            elif call_count[0] == 2:
                return [mock_pending_payout]
            else:
                return [mock_sent_payout]

        mock_session.exec = mock_exec
        mock_db.session = MagicMock(return_value=mock_session)

        # Mock the methods used internally
        with patch.object(payout_service, 'get_platform_commission_rate', return_value=Decimal("0.05")):
            with patch.object(payout_service, 'get_platform_wallet', return_value="wallet123"):
                result = payout_service.get_platform_stats()

        assert result['total_orders'] == 1
        assert result['paid_orders'] == 1
        assert result['commission_rate'] == Decimal("0.05")
        assert result['platform_wallet'] == "wallet123"
