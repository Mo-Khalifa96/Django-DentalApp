from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        from utils.seed import run_seed
        while True:
            try:
                run_seed(num_users=25,
                         num_patients=100,
                         num_visits=200,
                         num_appointments=120,
                         num_plans=60,
                         num_recalls=60,
                         num_lab_orders=40,
                         num_waiting_room=10,
                         num_schedule_exceptions=30,
                         num_sterilization_logs=50
                        )
                
                break   #break upon successful seeding
            
            except Exception as exc:
                import traceback
                print(f'\nSeeding error: {exc}')
                traceback.print_exc()
                print('\nRetrying...\n', '=' * 50)

#NOTE: Run this using the command: 
 # python manage.py seed 
