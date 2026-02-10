from unittest.mock import MagicMock

import pytest

from services.staging_management.staging_service import StagingManagementService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def staging_service(mock_db):
    return StagingManagementService(database=mock_db)


def test_get_all_slots(staging_service, mock_db):
    # Setup
    mock_cursor = MagicMock()
    mock_db.get_cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.description = [("slot_id",), ("slot_name",), ("status",)]
    mock_cursor.fetchall.return_value = [(1, "staging-1", "Available"), (2, "staging-2", "In Use")]

    # Execute
    slots = staging_service.get_all_slots()

    # Verify
    assert len(slots) == 2
    assert slots[0]["slot_name"] == "staging-1"
    assert slots[1]["status"] == "In Use"
    mock_cursor.execute.assert_called_once()


def test_get_slot_by_id(staging_service, mock_db):
    # Setup
    mock_cursor = MagicMock()
    mock_db.get_cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.description = [("slot_id",), ("slot_name",)]
    mock_cursor.fetchone.return_value = (1, "staging-1")

    # Execute
    slot = staging_service.get_slot_by_id(1)

    # Verify
    assert slot["slot_id"] == 1
    assert slot["slot_name"] == "staging-1"
    mock_cursor.execute.assert_called_once()
    args = mock_cursor.execute.call_args[0]
    assert args[1] == (1,)


def test_update_slot_status(staging_service, mock_db):
    # Setup
    mock_cursor = MagicMock()
    mock_db.get_cursor.return_value.__enter__.return_value = mock_cursor

    # Execute
    staging_service.update_slot_status(1, "In Use", owner="test-user", branch="test-branch")

    # Verify
    mock_cursor.execute.assert_called_once()
    args = mock_cursor.execute.call_args[0]
    assert args[1][0] == "In Use"
    assert args[1][1] == "test-user"
    assert args[1][2] == "test-branch"


def test_release_slot(staging_service, mock_db):
    # Setup
    mock_cursor = MagicMock()
    mock_db.get_cursor.return_value.__enter__.return_value = mock_cursor

    # Execute
    staging_service.release_slot(1)

    # Verify
    mock_cursor.execute.assert_called_once()
    args = mock_cursor.execute.call_args[0]
    assert args[1][0] == 1
