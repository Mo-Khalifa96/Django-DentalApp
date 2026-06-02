##Helper functions and utilities for whatsapp tasks##


#Helper function to normalize phone number for whatsapp
def normalize_phone_for_whatsapp(phone: str) -> str:
    '''
    Convert stored phone to WhatsApp-compatible international format.
    Stored format: '002001012345678' or '+2001012345678'
    WhatsApp format: '2001012345678' (no leading 00 or +)
    '''
    phone = phone.strip().replace(' ', '')
    if phone.startswith('00'):
        return phone[2:]
    if phone.startswith('+'):
        return phone[1:]
    return phone


#Helper function to build template components for custom, free-form messages
def build_custom_message_components(message_text):
    '''Build template components for the custom_message template (single variable).'''
    return [
        {
            'type': 'body',
            'parameters': [
                {'type': 'text', 'text': message_text},
            ]
        }
    ]


#Helper function to build template components for automated reminders 
def build_reminder_components(patient_name, doctor_name, appointment_date, appointment_time, clinic_name=None):
    '''
    Build template components for the appointment_reminder_en/ar template.
    sender_name: doctor name if available, otherwise clinic name.
    '''

    if not clinic_name:
        clinic_name = f"Dr. {doctor_name}'s clinic"

    return [
        {
            'type': 'body',
            'parameters': [
                {'type': 'text', 'text': patient_name},  #goes to {{1}}
                {'type': 'text', 'text': appointment_date},  #goes to {{2}}
                {'type': 'text', 'text': appointment_time},  #goes to {{3}}
                {'type': 'text', 'text': doctor_name},  #goes to {{4}}
                {'type': 'text', 'text': clinic_name},  #goes to {{5}}
            ]
        }
    ]

