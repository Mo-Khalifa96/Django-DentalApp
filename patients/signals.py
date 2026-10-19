from django.db.models import Q, Sum
from django.dispatch import receiver
from decimal import Decimal, ROUND_UP
from patients.models import TreatmentPlan
from finances.utils import round_decimal_up
from django.db.models.signals import pre_save, post_save
from finances.models import Bill, Transaction, InstallmentPlan, Installment


#Signal to record treatment cost before update
@receiver(pre_save, sender=TreatmentPlan)
def preserve_treatment_cost_before_update(sender, instance, **kwargs):
    if not instance._state.adding:  #update
        try:
            instance.totalCost_old = TreatmentPlan.all_objects.get(id=instance.id).totalCost
        except:
            instance.totalCost_old = None


#Signal to update installment plan details upon treatment plan updates
@receiver(post_save, sender=TreatmentPlan)
def update_treatment_relations_upon_cost_updates(sender, instance, **kwargs):
    #return on creates
    if instance._state.adding:  #update
        return 

    #Get treatment's installment plan (if any)
    plan = InstallmentPlan.objects.filter(treatment=instance).first()

    #Determine if treatment cost changed
    totalCost_old = getattr(instance, 'totalCost_old', None)
    
    if instance.totalCost != totalCost_old:
        #get cost difference
        cost_difference = round(instance.totalCost - (totalCost_old or 0), 2)

        #Determine if treatment has an installment has an installment plan
        if plan:
            #Else, update the installment plan
            #update amount per installment on the plan
            remaining_installments = plan.installments.filter(
                type='installment', paidAt__isnull=True
            ).order_by('-sequence')

            # Installment.objects.filter(
            #     installmentPlan=plan, type='installment', paidAt__isnull=True
            # ).order_by('-sequence')

            if remaining_installments:
                #update installment plan's total amount
                plan.totalAmount = Decimal(str(plan.totalAmount + cost_difference))
                
                #Determine the direction of change
                if cost_difference > 0:  #positive increase
                    #get any unpaid down payment
                    unpaid_downPayment = plan.installments.filter(
                        type='down_payment', paidAt__isnull=True
                    ).aggregate(down_payment=Sum('amount', default=Decimal('0')))['down_payment']

                    #calculate total remaining
                    total_remaining = plan.totalAmount - (plan.totalPaid or Decimal('0')) - unpaid_downPayment
                    total_remaining = max(total_remaining, Decimal('0'))

                    #calculate amount per installment (normal rounding)
                    amount_per_installment = round_decimal_up(total_remaining/len(remaining_installments))
                    remaining_installments.update(amount=amount_per_installment)

                    #account for last installment's rounding
                    last_installment = remaining_installments[0]
                    # last_installment.amount = round_decimal_up(amount_per_installment, rounding=ROUND_UP)
                    last_installment.amount = total_remaining - amount_per_installment * (len(remaining_installments) - 1)
                    last_installment.save(update_fields=['amount'])
                
                else:  #negative decrease
                    #subtract from remaining installments (in reverse order)
                    cost_difference = abs(cost_difference)  #turn to positive
                    for installment in remaining_installments:  #last comes out first
                        if cost_difference <= 0:
                            break
                        amount_to_remove = min(installment.amount, cost_difference)
                        installment.amount = Decimal(str(installment.amount - amount_to_remove))
                        cost_difference = Decimal(str(cost_difference - amount_to_remove))
                    
                    #bulk update installments
                    Installment.objects.bulk_update(remaining_installments, fields=['amount'])

                    #if cost outlives remaining installments, add remaining as deposit to be returned
                    if cost_difference > 0:
                        #Create a deposit with the overpaid money
                        Transaction.autogenerate_deposit_after_reducing_costs_below_paid(
                            treatment=instance, plan=plan, amount=cost_difference
                        )
            
            #else, installment plan is settled fully...
            else:
                #Determine the direction of change
                if cost_difference > 0:
                    #Issue a bill with the remaining amount
                    Bill.objects.create(
                        patient=instance.patient,
                        treatment=instance,
                        branch=(instance.patient.branch or plan.branch),
                        subtotal=Decimal(str(abs(cost_difference))),
                        totalAmount=Decimal(str(abs(cost_difference))),
                        discount=Decimal('0'),
                        totalPaid=Decimal('0'),
                        currency=(instance.currency or plan.currency),
                        description=("This bill was autogenerated to cover additional expenses after treatment plan "
                                     "cost increased beyond what the patient's installment plan covered and paid for.")
                    )
                    
                else:
                    #record the total amount decreased on the installment plan
                    plan.totalAmount = Decimal(str(plan.totalAmount + cost_difference))
                    
                    #Create a deposit with the overpaid money
                    Transaction.autogenerate_deposit_after_reducing_costs_below_paid(
                        treatment=instance, plan=plan, amount=cost_difference
                    )
        
            #update installment plan's amount
            plan.save(update_fields=['totalAmount', 'updatedAt'])

            #update the total amount on the associated bill too (if found)
            active_bill = plan.active_bill  #retrieve once to avoid caching
            if active_bill:
                active_bill.totalAmount = plan.totalAmount
                active_bill.save(update_fields=['totalAmount', 'treatmentTitle', 'procedures', 'updatedAt'])
        
        else:
            #Else, treatment has no installment plan...
            #Determine if treatment has a bill without a visit or if bill has the same total as treatment
            treatment_bill = instance.treatment_bills.filter(
                Q(treatment_id=instance.id, isDepositBill=False) 
                & (Q(visits__isnull=True) | Q(subtotal=totalCost_old))
            ).first()

            if treatment_bill:
                if cost_difference > 0:
                    #Assign increased amount
                    treatment_bill.totalAmount = instance.totalCost
                
                else:  #cost decreased
                    #Handle cost reductions
                    cost_difference = abs(cost_difference)  #use positive cost
                    #calculate total remaining on bill
                    remaining_amount = treatment_bill.totalAmount - (treatment_bill.totalPaid or Decimal('0'))
                    
                    #calculate amount to remove from bill
                    amount_to_remove = min(remaining_amount, cost_difference) if remaining_amount > 0 else Decimal('0')
                    
                    #if there's an amount to remove, remove and update cost difference
                    if amount_to_remove > 0:
                        treatment_bill.totalAmount = Decimal(str(treatment_bill.totalAmount - amount_to_remove))
                        cost_difference = Decimal(str(cost_difference - amount_to_remove))


                    #if money still found after reduction, create a deposit
                    if cost_difference > 0:
                        #create a deposit with the overpaid money
                        Transaction.autogenerate_deposit_after_reducing_costs_below_paid(
                            treatment=instance, amount=cost_difference
                        )

                #save changes to treatment bill
                treatment_bill.save(update_fields=[
                    'totalAmount', 'treatmentTitle', 'procedures', 'updatedAt'
                ])
