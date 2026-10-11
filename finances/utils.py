from datetime import date
from decimal import Decimal


#Helper Functions for financial operations
def get_quarter(today: date):
    month, year = today.month, today.year

    if month in [1,2,3]:
        # start_date = date(year=year, month=1, day=1)
        # end_date = date(year=year, month=3, day=31)
        return (date(year, 1, 1), date(year, 3, 31))
    elif month in [4,5,6]:
        return (date(year, 4, 1), date(year, 6, 30))
    elif month in [7,8,9]:
        return (date(year, 7, 1), date(year, 9, 30))
    elif month in [10,11,12]:
        return (date(year, 10, 1), date(year, 12, 31))


def calculate_subtotal(quantity, unitPrice):
    return round(quantity * unitPrice, 2)

def calculate_discount_from_perc(discount_perc, subtotal):
    return round(discount_perc*subtotal / 100, 2)

def calculate_subtotalAfterDiscount(subtotal, discount):
    return round(subtotal + discount, 2)

def calculate_grandTotal(subtotal, vat=0.0, discount=0.0):
    vat, discount = Decimal(vat), Decimal(discount)
    return round((subtotal + vat) - discount, 2)        
