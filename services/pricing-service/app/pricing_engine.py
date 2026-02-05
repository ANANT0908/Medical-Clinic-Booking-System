from decimal import Decimal
from datetime import date, datetime

class PricingEngine:
    DISCOUNT_PCT = Decimal('12.0')
    HIGH_VALUE = Decimal('1000.00')
    
    async def get_services_by_ids(self, service_ids):
        # Mock data - duplicate of validation service mock for independence
        all_services = {
            1: {'id': 1, 'name': 'General Consultation', 'gender': 'both', 'base_price': 300.00},
            2: {'id': 2, 'name': 'Gynecology', 'gender': 'female', 'base_price': 500.00},
            3: {'id': 3, 'name': 'Ultrasound', 'gender': 'female', 'base_price': 800.00},
            4: {'id': 4, 'name': 'Blood Test', 'gender': 'both', 'base_price': 450.00},
            5: {'id': 5, 'name': 'Cardiology', 'gender': 'both', 'base_price': 600.00},
            6: {'id': 6, 'name': 'Urology', 'gender': 'male', 'base_price': 550.00},
            7: {'id': 7, 'name': 'Prostate Screening', 'gender': 'male', 'base_price': 700.00},
            8: {'id': 8, 'name': 'Dermatology', 'gender': 'both', 'base_price': 400.00},
        }
        class ServiceObj:
            def __init__(self, d):
                self.__dict__ = d
                self.base_price = Decimal(str(d['base_price'])) # Convert to Decimal
        
        return [ServiceObj(all_services[sid]) for sid in service_ids if sid in all_services]

    async def calculate(self, data: dict):
        # Get service prices
        services = await self.get_services_by_ids(data['service_ids'])
        base_price = sum(s.base_price for s in services)
        
        # Check R1 eligibility
        user_dob = datetime.strptime(data['user_dob'], '%Y-%m-%d').date()
        today = date.today()
        
        is_birthday = (user_dob.month == today.month and 
                      user_dob.day == today.day)
        is_female = data['user_gender'] == 'female'
        
        # Determine discount
        if is_female and is_birthday:
            eligible = True
            reason = "Female birthday discount"
        elif base_price > self.HIGH_VALUE:
            eligible = True
            reason = "High-value order"
        else:
            eligible = False
            reason = None
        
        # Calculate final price
        if eligible:
            final_price = base_price * (1 - self.DISCOUNT_PCT / 100)
        else:
            final_price = base_price
        
        return {
            "base_price": float(base_price),
            "final_price": float(final_price),
            "discount_eligible": eligible,
            "discount_percentage": float(self.DISCOUNT_PCT) if eligible else 0,
            "discount_reason": reason
        }
