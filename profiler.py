
import os
import django

#Boot up Django inside the Locust script
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DentalTech.settings.dev")
django.setup()


if django.conf.settings.DEBUG:
    from users.models import User
    from finances.models import Bill, Invoice
    from clinic.models import Branch, Inventory, Procedure, Lab
    from patients.models import Patient, Appointment, TreatmentPlan
    from locust import HttpUser, task, between


    #Set up silk profiler
    class SilkProfiler(HttpUser):
        wait_time = between(0.1, 0.5)  #or change to more realistic times: (5, 30) -- viewing time 5sec - 30sec

        def on_start(self):
            #Authenticate and get access token
            response = self.client.post(
                "/api/auth/login/", 
                json={"email": "admin@clinic.com", "password": "Admin123"}
            )
            self.token = response.json().get("access")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

            #Fetch necessary ids
            self.user_id = User.objects.only('id').order_by('?').first().id
            self.doctor_id = User.objects.filter(role='dentist').only('id').order_by('?').first().id
            self.branch_id = Branch.objects.only('id').order_by('?').first().id
            self.patient_id = Patient.objects.only('id').order_by('?').first().id
            self.appointment_id = Appointment.objects.only('id').order_by('?').first().id
            
            self.treatment = TreatmentPlan.objects.only('id', 'patient').filter(patient__isnull=False).order_by('?').first()
            self.treatment_id = self.treatment.id
            self.treatmemnt_patient_id = self.treatment.patient.id

            self.lab_id = Lab.objects.only('id').order_by('?').first().id
            self.procedure_id = Procedure.objects.only('id').order_by('?').first().id
            self.inventory_id = Inventory.objects.only('id').order_by('?').first().id
            self.bill_id = Bill.objects.only('id').order_by('?').first().id
            self.invoice_id = Invoice.objects.only('id').order_by('?').first().id


        @task
        def hit_endpoints(self):
            endpoints = [
                #auth endpoints
                '/api/auth/me/',
                '/api/auth/me/preferences/',

                #users endpoints
                '/api/users/',
                f'/api/users/{self.user_id}/', 
                '/api/doctor-schedules/',
                f'/api/doctor-schedules/{self.doctor_id}/', 

                #patients endpoints
                '/api/patients/',
                f'/api/patients/{self.patient_id}/',
                f'/api/patients/{self.patient_id}/dental-chart/',
                f'/api/patients/{self.patient_id}/visits/',
                f'/api/patients/{self.patient_id}/treatment-plans/',
                f'/api/patients/{self.treatmemnt_patient_id}/treatment-plans/{self.treatment_id}/',
                f'/api/treatment-plans/{self.treatment_id}/',
                '/api/appointments/',
                f'/api/appointments/{self.appointment_id}/',
                '/api/recalls/',

                #clinic endpoints
                '/api/branches/',
                f'/api/branches/{self.branch_id}/',
                '/api/dashboard/stats/',
                '/api/dashboard/appointments-today/',
                '/api/procedures/',
                f'/api/procedures/{self.procedure_id}/',
                '/api/waiting-room/',
                '/api/inventory/',
                f'/api/inventory/{self.inventory_id}/',
                '/api/labs/',
                f'/api/labs/{self.lab_id}/',
                '/api/lab-orders/',
                '/api/sterilization/',
                # '/api/insurance/',
                # f'/api/insurance/{insurance_id}/',

                #finances endpoints
                '/api/bills/',
                f'/api/bills/{self.bill_id}/',
                '/api/transactions/',
                '/api/invoices/',
                f'/api/invoices/{self.invoice_id}/',
                '/api/invoices/tax-config/',

                #others
                '/api/roles/',
                '/api/permissions/',
            ]

            for _ in range(5):
                for url in endpoints:
                    self.client.get(url)
                
            self.environment.runner.quit() #stop profiler after one full pass


# To start the profiler, run:
#  locust -f profiler.py --host=http://localhost:8000
