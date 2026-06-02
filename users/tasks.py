from users.models import User 
from django.conf import settings 
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from datetime import date, datetime, timedelta


#Custom function to get login url
def get_login_url():
    protocol = settings.SITE_PROTOCOL 
    domain = settings.SITE_DOMAIN 
    path = 'api/auth/login/'
    return f"{protocol}://{domain}/{path}"

def get_password_reset_link(uid, token):
    protocol = settings.SITE_PROTOCOL 
    domain = settings.SITE_DOMAIN 
    path = 'api/auth/password-reset'
    return f"{protocol}://{domain}/{path}/{uid}/{token}"


#Define task for sending reset email (for Django-Q)
def send_password_reset_email(email):
    user = User.objects.get(email__iexact=email)   #already verified by serializer
    uid = urlsafe_base64_encode(force_bytes(user.id))
    token = default_token_generator.make_token(user)

    #Get reset url 
    reset_link = get_password_reset_link(uid, token)

    #Email message 
    html_message = render_to_string('emails/password_reset_email.html', 
                    context={'name': user.name,'reset_link': reset_link})
    
    plain_message = (f"Hi {user.name},\n\nYou're receiving this email because you requested a password reset for your account.\n\n"
                     f"To reset your password, click the link below. This link will expire in 1 hour.\n{reset_link}\n\n\n"
                     f"If you didn't request a password reset, you can ignore this message or contact the support team.")
                     #f'Regards,\nStackk Team')
    
    #Send email 
    send_mail(
        subject='Reset Your Password',
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL, 
        recipient_list=[email],
        fail_silently=False
    )


#Define task for sending confirmation email (for Django-Q)
def password_reset_successful_email(name, email):
    #Email message
    html_message = render_to_string('emails/password_reset_successful_email.html',
                    context={'name': name,'login_url': get_login_url()})
    
    plain_message = (f'Hi {name},\n\nyour password has been reset successfully.\n'
                     f'You can now log in using your new credentials.\n'
                     f'To login now, click the following link:\n{get_login_url()}\n\n'
                     f'If you did not perform this action, please contact our support team immediately.')
                     #f'Regards,\nStackk Team')
    
    send_mail(
        subject='Your password was reset successfully',
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL, 
        recipient_list=[email],
        fail_silently=False
    )
    

    #ALTERNATIVELY, 
    # from django.core.mail import EmailMultiAlternatives
    # email_message = EmailMultiAlternatives(
    #     subject='Your password was reset successfully',
    #     body=plain_message,          #plain text is the base body
    #     from_email=settings.DEFAULT_FROM_EMAIL,
    #     to=[email]
    # )
    # email_message.attach_alternative(html_message, 'text/html') 
    # email_message.send()