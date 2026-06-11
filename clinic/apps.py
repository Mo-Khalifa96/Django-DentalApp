from django.apps import AppConfig


class ClinicConfig(AppConfig):
    name = 'clinic'

    def ready(self):
        import clinic.signals