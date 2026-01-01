"""Tests for postage service."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from bot.services.postage import PostageService
from bot.models import Database, PostageType


class TestPostageService:
    """Test PostageService functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return MagicMock(spec=Database)

    @pytest.fixture
    def postage_service(self, mock_db):
        """Create PostageService with mock db."""
        return PostageService(mock_db)

    def test_add_postage_type(self, postage_service, mock_db):
        """Test adding a new postage type."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        # Mock refresh to set ID
        def set_id(postage):
            postage.id = 1

        mock_session.refresh = MagicMock(side_effect=set_id)

        result = postage_service.add_postage_type(
            vendor_id=1,
            name="Express Shipping",
            price_fiat=Decimal("9.99"),
            currency="USD",
            description="2-3 day delivery"
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.vendor_id == 1
        assert result.name == "Express Shipping"
        assert result.price_fiat == Decimal("9.99")
        assert result.is_active is True

    def test_add_postage_type_minimal(self, postage_service, mock_db):
        """Test adding postage type with minimal fields."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)
        mock_session.refresh = MagicMock()

        result = postage_service.add_postage_type(
            vendor_id=1,
            name="Standard",
            price_fiat=Decimal("4.99")
        )

        assert result.currency == "USD"  # Default
        assert result.description is None

    def test_get_postage_type(self, postage_service, mock_db):
        """Test getting a postage type by ID."""
        mock_postage = MagicMock(spec=PostageType)
        mock_postage.id = 1
        mock_postage.name = "Express"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_postage)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.get_postage_type(1)

        mock_session.get.assert_called_once_with(PostageType, 1)
        assert result == mock_postage

    def test_get_postage_type_not_found(self, postage_service, mock_db):
        """Test getting a nonexistent postage type."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.get_postage_type(999)

        assert result is None

    def test_list_by_vendor(self, postage_service, mock_db):
        """Test listing postage types for a vendor."""
        mock_postage1 = MagicMock(spec=PostageType)
        mock_postage1.vendor_id = 1
        mock_postage1.is_active = True
        mock_postage2 = MagicMock(spec=PostageType)
        mock_postage2.vendor_id = 1
        mock_postage2.is_active = False

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_postage1, mock_postage2])
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.list_by_vendor(1)

        assert len(result) == 2
        mock_session.exec.assert_called_once()

    def test_list_by_vendor_active_only(self, postage_service, mock_db):
        """Test listing only active postage types."""
        mock_postage = MagicMock(spec=PostageType)
        mock_postage.vendor_id = 1
        mock_postage.is_active = True

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_postage])
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.list_by_vendor(1, active_only=True)

        assert len(result) == 1
        mock_session.exec.assert_called_once()

    def test_update_postage_type(self, postage_service, mock_db):
        """Test updating a postage type."""
        mock_postage = MagicMock(spec=PostageType)
        mock_postage.id = 1
        mock_postage.name = "Standard"
        mock_postage.price_fiat = Decimal("4.99")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_postage)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.update_postage_type(
            1,
            name="Premium",
            price_fiat=Decimal("14.99")
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result == mock_postage

    def test_update_postage_type_not_found(self, postage_service, mock_db):
        """Test updating a nonexistent postage type."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.update_postage_type(999, name="Test")

        assert result is None
        mock_session.add.assert_not_called()

    def test_update_postage_type_invalid_attribute(self, postage_service, mock_db):
        """Test updating with invalid attribute (should be ignored)."""
        mock_postage = MagicMock(spec=PostageType)
        mock_postage.id = 1
        mock_postage.name = "Standard"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_postage)
        mock_db.session = MagicMock(return_value=mock_session)

        # Pass an invalid attribute that doesn't exist on PostageType
        result = postage_service.update_postage_type(
            1,
            name="Premium",
            invalid_field="should be ignored"
        )

        # Should still update valid fields and return the postage
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result == mock_postage

    def test_toggle_active(self, postage_service, mock_db):
        """Test toggling postage type active status."""
        mock_postage = MagicMock(spec=PostageType)
        mock_postage.id = 1
        mock_postage.is_active = True

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_postage)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.toggle_active(1)

        assert result.is_active is False
        mock_session.commit.assert_called_once()

    def test_toggle_active_to_true(self, postage_service, mock_db):
        """Test toggling inactive postage type to active."""
        mock_postage = MagicMock(spec=PostageType)
        mock_postage.id = 1
        mock_postage.is_active = False

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_postage)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.toggle_active(1)

        assert result.is_active is True

    def test_toggle_active_not_found(self, postage_service, mock_db):
        """Test toggling a nonexistent postage type."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.toggle_active(999)

        assert result is None

    def test_delete_postage_type(self, postage_service, mock_db):
        """Test deleting a postage type."""
        mock_postage = MagicMock(spec=PostageType)
        mock_postage.id = 1

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_postage)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.delete_postage_type(1)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_postage)
        mock_session.commit.assert_called_once()

    def test_delete_postage_type_not_found(self, postage_service, mock_db):
        """Test deleting a nonexistent postage type."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get = MagicMock(return_value=None)
        mock_db.session = MagicMock(return_value=mock_session)

        result = postage_service.delete_postage_type(999)

        assert result is False
        mock_session.delete.assert_not_called()
