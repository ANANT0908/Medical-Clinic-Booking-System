import pytz
import os
from datetime import datetime
from uuid import UUID
from sqlalchemy import text
from app.database import get_db

class QuotaManager:
    def __init__(self, max_discounts=100):
        self.max_discounts = max_discounts
        self.ist = pytz.timezone('Asia/Kolkata')
    
    async def acquire_quota(self, transaction_id: UUID):
        # MOCK IMPLEMENTATION FOR LOCAL TESTING
        if os.getenv("PROJECT_ID") == "local-project":
            return await self.acquire_quota_mock(transaction_id)

        # Get today in IST
        today = datetime.now(self.ist).date()
        
        # Call database function (handles locking)
        async with get_db() as db:
            # Note: We must use autocommit or commit explicitly for side effects if not managed by transaction block
            # But the function itself does logic. 
            # In SQLAlchemy async, we execute text.
            stmt = text("SELECT acquire_quota(:p_date, :p_max, :p_transaction_id)")
            result = await db.execute(
                stmt,
                {"p_date": today, "p_max": self.max_discounts, "p_transaction_id": transaction_id}
            )
            # Commit needed for the INSERT/UPDATE inside the function to persist
            await db.commit()
            acquired = result.scalar()
        
        if acquired:
            return (True, "Quota acquired")
        else:
            return (False, "Daily discount quota reached. Please try again tomorrow.")
            
    async def acquire_quota_mock(self, transaction_id: UUID):
        # Simple in-memory mock
        today = datetime.now(self.ist).strftime('%Y-%m-%d')
        if not hasattr(self, '_mock_quota'):
            self._mock_quota = {} # date -> count
            self._mock_allocations = set()
            
        used = self._mock_quota.get(today, 0)
        
        if used < self.max_discounts:
            self._mock_quota[today] = used + 1
            self._mock_allocations.add(str(transaction_id))
            print(f"[MOCK DB] Acquired quota for {transaction_id}. Used: {self._mock_quota[today]}/{self.max_discounts}")
            return (True, "Quota acquired")
        else:
            return (False, "Daily discount quota reached. Please try again tomorrow.")

    async def release_quota(self, transaction_id: UUID):
        """Compensation logic"""
        if os.getenv("PROJECT_ID") == "local-project":
             print(f"[MOCK DB] Released quota for {transaction_id}")
             # In a real mock we would decrement, but for simplicity just ack
             return True

        async with get_db() as db:
            stmt = text("SELECT release_quota(:p_transaction_id)")
            result = await db.execute(
                stmt,
                {"p_transaction_id": transaction_id}
            )
            await db.commit()
            return result.scalar()

