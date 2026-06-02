from django.core.management.base import BaseCommand
from utils.schedules import setup_scheduled_tasks  

class Command(BaseCommand):
    help = 'Set up Django-Q scheduled tasks'

    def handle(self, *args, **kwargs):
        try:
            setup_scheduled_tasks()
            self.stdout.write(self.style.SUCCESS('Scheduled tasks set up successfully!'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'Error setting up scheduled tasks: {str(exc)}'))


#NOTE: Run this using the command: 
# python manage.py setup_scheduled_tasks 
