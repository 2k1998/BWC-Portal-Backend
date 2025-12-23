import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import models  # noqa: E402
from routers.rentals import update_rental_on_return  # noqa: E402
from schemas import RentalUpdate  # noqa: E402


class DummyUser:
    def __init__(self):
        self.id = 1
        self.email = "admin@example.com"
        self.role = "admin"


class UpdateRentalReturnTests(unittest.TestCase):
    def _build_rental(self, locked=False):
        rental = models.Rental(
            id=1,
            customer_name="Test",
            customer_surname="User",
            rental_days=1,
            return_datetime=None,
            start_kilometers=100,
            gas_tank_start=models.GasTankLevel.full,
            company_id=1,
            car_id=1,
            is_locked=locked,
        )
        return rental

    def _build_db(self, rental):
        rental_query = MagicMock()
        rental_query.filter.return_value.first.return_value = rental

        db = MagicMock()
        db.query.return_value = rental_query
        return db, rental_query

    def test_return_updates_when_unlocked(self):
        rental = self._build_rental(locked=False)
        db, rental_query = self._build_db(rental)
        user = DummyUser()

        payload = RentalUpdate(end_kilometers=150, gas_tank_end=models.GasTankLevel.empty)

        result = update_rental_on_return(rental_id=1, rental_update=payload, db=db, current_user=user)

        rental_query.filter.assert_called_once()
        self.assertEqual(result.end_kilometers, 150)
        self.assertEqual(result.gas_tank_end, models.GasTankLevel.empty)
        self.assertTrue(result.is_locked)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(rental)

    def test_return_updates_even_when_locked(self):
        rental = self._build_rental(locked=True)
        db, rental_query = self._build_db(rental)
        user = DummyUser()

        payload = RentalUpdate(end_kilometers=200, gas_tank_end=models.GasTankLevel.half)

        result = update_rental_on_return(rental_id=1, rental_update=payload, db=db, current_user=user)

        rental_query.filter.assert_called_once()
        self.assertEqual(result.end_kilometers, 200)
        self.assertEqual(result.gas_tank_end, models.GasTankLevel.half)
        self.assertTrue(result.is_locked)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(rental)


if __name__ == "__main__":
    unittest.main()
