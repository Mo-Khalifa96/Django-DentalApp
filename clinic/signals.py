from users.models import User
from clinic.models import Branch
from django.dispatch import receiver
from django.db.models.signals import post_save


#Signal for assigning any new branch to all admin users
@receiver(post_save, sender=Branch)
def update_admin_branches(sender, instance, created, **kwargs):
    if created:  #triggers on creation only
        #add new branch to admin list of branches
        admins = User.objects.prefetch_related('branches').filter(role='admin')
        for admin in admins:
            admin.branches.add(instance)


#Signal for assigning all branches to new admin users
@receiver(post_save, sender=User)
def assign_branches_to_new_admin(sender, instance, created, **kwargs):
    if created and instance.role == 'admin':
        instance.branches.set(Branch.objects.all())
