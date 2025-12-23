import os
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import models  # noqa: E402
from routers.cars import delete_car  # noqa: E402


class DummyUser:
    def __init__(self):
        self.id = 1
        self.email = "admin@example.com"
        self.role = "admin"


class DeleteCarSafetyCheckTests(unittest.TestCase):
    def _build_db_mocks(self, rental_count):
        car = models.Car(
            id=1,
            manufacturer="Toyota",
            model="Camry",
            license_plate="ABC123",
            vin="VIN123456789",
            company_id=1,
        )

        car_query = MagicMock()
        car_query.filter.return_value.first.return_value = car

        rental_filter = MagicMock()
        rental_filter.count.return_value = rental_count

        rental_query = MagicMock()
        rental_query.filter.return_value = rental_filter

        db = MagicMock()
        db.query.side_effect = [car_query, rental_query]
        return db, car, rental_query

    def test_delete_car_blocked_when_active_rental_exists(self):
        db, _, rental_query = self._build_db_mocks(rental_count=1)
        user = DummyUser()

        with self.assertRaises(HTTPException) as context:
            delete_car(car_id=1, db=db, current_user=user)

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("active rental records", context.exception.detail)

        filter_args, _ = rental_query.filter.call_args
        self.assertEqual(str(filter_args[0]), str(models.Rental.car_id == 1))
        self.assertEqual(str(filter_args[1]), str(models.Rental.is_locked == False))

        db.delete.assert_not_called()
        db.commit.assert_not_called()

    def test_delete_car_allowed_when_rentals_are_locked(self):
        db, car, rental_query = self._build_db_mocks(rental_count=0)
        user = DummyUser()

        delete_car(car_id=1, db=db, current_user=user)

        filter_args, _ = rental_query.filter.call_args
        self.assertEqual(str(filter_args[0]), str(models.Rental.car_id == 1))
        self.assertEqual(str(filter_args[1]), str(models.Rental.is_locked == False))

        db.delete.assert_called_once_with(car)
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
