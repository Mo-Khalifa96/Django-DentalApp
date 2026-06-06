from decimal import Decimal

def calculate_subtotal(quantity, unitPrice):
    return round(quantity * unitPrice, 2)

def calculate_discount_from_perc(discount_perc, subtotal):
    return round(discount_perc*subtotal / 100, 2)

def calculate_subtotalAfterDiscount(subtotal, discount):
    return round(subtotal + discount, 2)

def calculate_grandTotal(subtotal, vat=0.0, discount=0.0):
    vat, discount = Decimal(vat), Decimal(discount)
    return round((subtotal + vat) - discount, 2)        
