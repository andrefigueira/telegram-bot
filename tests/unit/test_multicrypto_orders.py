"""Tests for multi-crypto order service."""

import pytest
import tempfile
import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.multicrypto_orders import (
    MultiCryptoOrderService, encrypt_address, decrypt_address
)
from bot.services.crypto_swap import CryptoSwapService, SwapOrder, SwapStatus
from bot.models_multitenant import (
    MultiTenantDatabase, OrderState, SwapState
)


class TestEncryption:
    """Test address encryption/decryption."""

    def test_encrypt_decrypt_address(self):
        """Test encrypting and decrypting an address."""
        key = "a" * 64  # 32 bytes in hex
        original = "123 Main Street, City, Country"

        encrypted = encrypt_address(original, key)
        assert encrypted != original

        decrypted = decrypt_address(encrypted, key)
        assert decrypted == original

    def test_different_keys_produce_different_ciphertext(self):
        """Test that different keys produce different encrypted output."""
        key1 = "a" * 64
        key2 = "b" * 64
        address = "Test Address"

        enc1 = encrypt_address(address, key1)
        enc2 = encrypt_address(address, key2)

        assert enc1 != enc2

    def test_decrypt_with_wrong_key_fails(self):
        """Test decryption fails with wrong key."""
        key1 = "a" * 64
        key2 = "b" * 64
        address = "Test Address"

        encrypted = encrypt_address(address, key1)

        with pytest.raises(Exception):
            decrypt_address(encrypted, key2)


class TestMultiCryptoOrderService:
    """Test MultiCryptoOrderService functionality."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def swap_service(self):
        """Create a mock swap service."""
        return CryptoSwapService(testnet=True)

    @pytest.fixture
    def order_service(self, db, swap_service):
        """Create order service instance."""
        return MultiCryptoOrderService(db, swap_service)

    @pytest.fixture
    def tenant_with_product(self, db):
        """Create a tenant with a product."""
        tenant = db.create_tenant("shop@test.com", "hash", "1.0")
        tenant = db.update_tenant(
            tenant.id,
            monero_wallet_address="4TestWalletAddress" + "A" * 77,
            shop_name="Test Shop"
        )

        product = db.create_product(
            tenant.id, "Test Product", Decimal("1.5"), 10,
            description="A test product"
        )

        return tenant, product

    # ==================== SUPPORTED METHODS TESTS ====================

    @pytest.mark.asyncio
    async def test_get_supported_payment_methods(self, order_service):
        """Test getting supported payment methods."""
        methods = await order_service.get_supported_payment_methods()

        assert "xmr" in methods
        assert "btc" in methods
        assert "eth" in methods
        assert "sol" in methods

    # ==================== ORDER CREATION TESTS ====================

    @pytest.mark.asyncio
    async def test_create_order_xmr_direct(self, order_service, tenant_with_product):
        """Test creating an order with direct XMR payment."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=2,
            delivery_address="123 Main St",
            payment_coin="xmr"
        )

        assert result is not None
        assert result["order_id"] is not None
        assert result["product_name"] == "Test Product"
        assert result["quantity"] == 2
        assert Decimal(result["total_xmr"]) == Decimal("3.0")  # 1.5 * 2
        assert result["payment_coin"] == "XMR"
        assert result["payment_address"] == tenant.monero_wallet_address
        assert result["swap_id"] is None

    @pytest.mark.asyncio
    async def test_create_order_btc_swap(self, order_service, tenant_with_product):
        """Test creating an order with BTC payment (swap required)."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            delivery_address="456 Oak Ave",
            payment_coin="btc"
        )

        assert result is not None
        assert result["payment_coin"] == "BTC"
        assert result["swap_id"] is not None
        assert result["swap_id"].startswith("mock_")
        assert result["payment_address"].startswith("bc1qtest")

    @pytest.mark.asyncio
    async def test_create_order_eth_swap(self, order_service, tenant_with_product):
        """Test creating an order with ETH payment."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            delivery_address="789 Pine St",
            payment_coin="eth"
        )

        assert result is not None
        assert result["payment_coin"] == "ETH"
        assert result["payment_address"].startswith("0x")

    @pytest.mark.asyncio
    async def test_create_order_unsupported_coin(self, order_service, tenant_with_product):
        """Test creating order with unsupported coin fails."""
        tenant, product = tenant_with_product

        with pytest.raises(ValueError, match="Unsupported payment method"):
            await order_service.create_order(
                tenant.id, product.id, 12345, 1, "Address", "doge"
            )

    @pytest.mark.asyncio
    async def test_create_order_tenant_not_found(self, order_service):
        """Test creating order for non-existent tenant fails."""
        with pytest.raises(ValueError, match="Tenant not found"):
            await order_service.create_order(
                "nonexistent", 1, 12345, 1, "Address", "xmr"
            )

    @pytest.mark.asyncio
    async def test_create_order_no_wallet(self, order_service, db):
        """Test creating order when tenant has no wallet fails."""
        tenant = db.create_tenant("nowallet@test.com", "hash", "1.0")
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)

        with pytest.raises(ValueError, match="no Monero wallet"):
            await order_service.create_order(
                tenant.id, product.id, 12345, 1, "Address", "xmr"
            )

    @pytest.mark.asyncio
    async def test_create_order_product_not_found(self, order_service, tenant_with_product):
        """Test creating order for non-existent product fails."""
        tenant, _ = tenant_with_product

        with pytest.raises(ValueError, match="Product not found"):
            await order_service.create_order(
                tenant.id, 99999, 12345, 1, "Address", "xmr"
            )

    @pytest.mark.asyncio
    async def test_create_order_inactive_product(self, order_service, db, tenant_with_product):
        """Test creating order for inactive product fails."""
        tenant, product = tenant_with_product
        db.update_product(product.id, tenant.id, active=False)

        with pytest.raises(ValueError, match="not available"):
            await order_service.create_order(
                tenant.id, product.id, 12345, 1, "Address", "xmr"
            )

    @pytest.mark.asyncio
    async def test_create_order_insufficient_inventory(self, order_service, tenant_with_product):
        """Test creating order with insufficient inventory fails."""
        tenant, product = tenant_with_product

        with pytest.raises(ValueError, match="Insufficient inventory"):
            await order_service.create_order(
                tenant.id, product.id, 12345, 100, "Address", "xmr"
            )

    @pytest.mark.asyncio
    async def test_create_order_decrements_inventory(self, order_service, db, tenant_with_product):
        """Test that creating order decrements inventory."""
        tenant, product = tenant_with_product
        original_inventory = product.inventory

        await order_service.create_order(
            tenant.id, product.id, 12345, 3, "Address", "xmr"
        )

        updated = db.get_product(product.id, tenant.id)
        assert updated.inventory == original_inventory - 3

    @pytest.mark.asyncio
    async def test_create_order_calculates_commission(self, order_service, db, tenant_with_product):
        """Test that commission is calculated correctly."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 2, "Address", "xmr"
        )

        order = db.get_order(result["order_id"], tenant.id)
        # Commission = total * rate = 3.0 * 0.05 = 0.15
        assert order.commission_xmr == Decimal("0.15")

    # ==================== PAYMENT STATUS TESTS ====================

    @pytest.mark.asyncio
    async def test_check_order_payment_xmr(self, order_service, db, tenant_with_product):
        """Test checking payment status for XMR order."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address", "xmr"
        )

        status = await order_service.check_order_payment(
            result["order_id"], tenant.id
        )

        assert status["order_id"] == result["order_id"]
        assert status["state"] == "pending"
        assert status["payment_coin"] == "xmr"
        assert status["swap_status"] is None

    @pytest.mark.asyncio
    async def test_check_order_payment_swap(self, order_service, db, tenant_with_product):
        """Test checking payment status for swap order."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address", "btc"
        )

        status = await order_service.check_order_payment(
            result["order_id"], tenant.id
        )

        # Mock swap service returns complete status
        assert status["swap_status"] == "complete"
        assert status["state"] == "paid"

    @pytest.mark.asyncio
    async def test_check_order_payment_not_found(self, order_service, tenant_with_product):
        """Test checking payment for non-existent order."""
        tenant, _ = tenant_with_product

        with pytest.raises(ValueError, match="Order not found"):
            await order_service.check_order_payment(99999, tenant.id)

    # ==================== SWAP PROCESSING TESTS ====================

    @pytest.mark.asyncio
    async def test_process_pending_swaps(self, order_service, db, tenant_with_product):
        """Test processing pending swap orders."""
        tenant, product = tenant_with_product

        # Create multiple swap orders
        await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address 1", "btc"
        )
        await order_service.create_order(
            tenant.id, product.id, 12346, 1, "Address 2", "eth"
        )

        results = await order_service.process_pending_swaps()

        # Mock service returns complete for all
        assert results["checked"] == 2
        assert results["completed"] == 2

    # ==================== ORDER MANAGEMENT TESTS ====================

    @pytest.mark.asyncio
    async def test_mark_order_fulfilled(self, order_service, db, tenant_with_product):
        """Test marking an order as fulfilled."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address", "xmr"
        )

        # Mark as paid first
        db.update_order_state(result["order_id"], tenant.id, OrderState.PAID)

        order = order_service.mark_order_fulfilled(result["order_id"], tenant.id)

        assert order is not None
        assert order.state == OrderState.FULFILLED

    @pytest.mark.asyncio
    async def test_cancel_order_restores_inventory(self, order_service, db, tenant_with_product):
        """Test cancelling order restores inventory."""
        tenant, product = tenant_with_product
        original_inventory = product.inventory

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 3, "Address", "xmr"
        )

        # Verify inventory decreased
        updated = db.get_product(product.id, tenant.id)
        assert updated.inventory == original_inventory - 3

        # Cancel order
        order_service.cancel_order(result["order_id"], tenant.id)

        # Verify inventory restored
        restored = db.get_product(product.id, tenant.id)
        assert restored.inventory == original_inventory

    @pytest.mark.asyncio
    async def test_get_order_delivery_address(self, order_service, tenant_with_product):
        """Test getting decrypted delivery address."""
        tenant, product = tenant_with_product
        original_address = "123 Secret Location"

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, original_address, "xmr"
        )

        decrypted = order_service.get_order_delivery_address(
            result["order_id"], tenant.id, tenant.encryption_key
        )

        assert decrypted == original_address

    @pytest.mark.asyncio
    async def test_get_orders(self, order_service, db, tenant_with_product):
        """Test getting orders for a tenant."""
        tenant, product = tenant_with_product

        # Create multiple orders
        await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address 1", "xmr"
        )
        await order_service.create_order(
            tenant.id, product.id, 12346, 1, "Address 2", "btc"
        )

        orders = order_service.get_orders(tenant.id)
        assert len(orders) == 2

    @pytest.mark.asyncio
    async def test_get_orders_by_state(self, order_service, db, tenant_with_product):
        """Test filtering orders by state."""
        tenant, product = tenant_with_product

        result1 = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address 1", "xmr"
        )
        await order_service.create_order(
            tenant.id, product.id, 12346, 1, "Address 2", "xmr"
        )

        # Mark first as paid
        db.update_order_state(result1["order_id"], tenant.id, OrderState.PAID)

        pending = order_service.get_orders(tenant.id, state=OrderState.PENDING)
        assert len(pending) == 1

        paid = order_service.get_orders(tenant.id, state=OrderState.PAID)
        assert len(paid) == 1

    @pytest.mark.asyncio
    async def test_create_order_swap_failure(self, order_service, db, tenant_with_product):
        """Test creating order when swap creation fails."""
        tenant, product = tenant_with_product

        # Mock swap service to return None
        with patch.object(
            order_service.swap_service, 'create_swap',
            new_callable=AsyncMock, return_value=None
        ):
            with pytest.raises(ValueError, match="Unable to create swap"):
                await order_service.create_order(
                    tenant.id, product.id, 12345, 1, "Address", "btc"
                )

    @pytest.mark.asyncio
    async def test_create_order_inventory_decrement_fails(self, order_service, db, tenant_with_product):
        """Test creating order when inventory decrement fails."""
        tenant, product = tenant_with_product

        # Mock db to fail inventory decrement
        with patch.object(db, 'decrement_inventory', return_value=False):
            with pytest.raises(ValueError, match="Failed to reserve inventory"):
                await order_service.create_order(
                    tenant.id, product.id, 12345, 1, "Address", "xmr"
                )

    @pytest.mark.asyncio
    async def test_check_order_payment_swap_failed(self, order_service, db, tenant_with_product):
        """Test checking payment status when swap failed."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address", "btc"
        )

        # Mock swap service to return failed status
        with patch.object(
            order_service.swap_service, 'check_swap_status',
            new_callable=AsyncMock, return_value=SwapStatus.FAILED
        ):
            status = await order_service.check_order_payment(
                result["order_id"], tenant.id
            )

            assert status["swap_status"] == "failed"
            assert status["state"] == "cancelled"
            assert "failed" in status["message"].lower()

    @pytest.mark.asyncio
    async def test_check_order_payment_swap_expired(self, order_service, db, tenant_with_product):
        """Test checking payment status when swap expired."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address", "btc"
        )

        with patch.object(
            order_service.swap_service, 'check_swap_status',
            new_callable=AsyncMock, return_value=SwapStatus.EXPIRED
        ):
            status = await order_service.check_order_payment(
                result["order_id"], tenant.id
            )

            assert status["swap_status"] == "expired"
            assert status["state"] == "cancelled"

    @pytest.mark.asyncio
    async def test_check_order_payment_swap_waiting(self, order_service, db, tenant_with_product):
        """Test checking payment status when swap is waiting."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address", "btc"
        )

        with patch.object(
            order_service.swap_service, 'check_swap_status',
            new_callable=AsyncMock, return_value=SwapStatus.WAITING
        ):
            status = await order_service.check_order_payment(
                result["order_id"], tenant.id
            )

            assert status["swap_status"] == "waiting"
            assert "in progress" in status["message"].lower()

    @pytest.mark.asyncio
    async def test_process_pending_swaps_with_failures(self, order_service, db, tenant_with_product):
        """Test processing pending swaps with failed swaps."""
        tenant, product = tenant_with_product

        # Create a swap order
        await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address 1", "btc"
        )

        # Mock swap service to return failed status
        with patch.object(
            order_service.swap_service, 'check_swap_status',
            new_callable=AsyncMock, return_value=SwapStatus.FAILED
        ):
            results = await order_service.process_pending_swaps()

            assert results["checked"] == 1
            assert results["failed"] == 1

    @pytest.mark.asyncio
    async def test_process_pending_swaps_with_exception(self, order_service, db, tenant_with_product):
        """Test processing pending swaps handles exceptions gracefully."""
        tenant, product = tenant_with_product

        await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address 1", "btc"
        )

        with patch.object(
            order_service.swap_service, 'check_swap_status',
            new_callable=AsyncMock, side_effect=Exception("Network error")
        ):
            results = await order_service.process_pending_swaps()

            assert results["checked"] == 1
            # Error was caught, no completed or failed count increased
            assert results["completed"] == 0
            assert results["failed"] == 0

    @pytest.mark.asyncio
    async def test_get_order_returns_order(self, order_service, db, tenant_with_product):
        """Test get_order returns the order."""
        tenant, product = tenant_with_product

        result = await order_service.create_order(
            tenant.id, product.id, 12345, 1, "Address", "xmr"
        )

        order = order_service.get_order(result["order_id"], tenant.id)
        assert order is not None
        assert order.id == result["order_id"]

    def test_cancel_nonexistent_order(self, order_service, tenant_with_product):
        """Test cancelling non-existent order returns None."""
        tenant, _ = tenant_with_product

        result = order_service.cancel_order(99999, tenant.id)
        assert result is None

    def test_mark_fulfilled_nonexistent_order(self, order_service, tenant_with_product):
        """Test marking non-existent order as fulfilled returns None."""
        tenant, _ = tenant_with_product

        result = order_service.mark_order_fulfilled(99999, tenant.id)
        assert result is None
