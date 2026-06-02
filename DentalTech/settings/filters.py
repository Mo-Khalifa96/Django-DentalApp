import os
import psutil
import logging


#Custom filter to exclude web-crawler 404 requests
class RequestsFilter(logging.Filter):
    ALLOWED_PATHS = [  #TODO
            '/api/auth/',
            'api/users/'
            'api/dashboard/',
            'api/patients',
            'api/appointments',
            'api/procedures/',
            'api/treatment-plans/',
            'api/inventory/',
            'api/labs/',
            'api/lab-orders/',
            'api/waiting-room/',
            'api/doctor-schedules/',
            'api/whatsapp/',
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
            '/swagger/',
            '/schema/',
        ]

    def filter(self, record):
        if hasattr(record, 'getMessage'):
            message = record.getMessage().lower()

            #Filter DisallowedHost errors entirely
            if 'disallowedhost' in message or 'disallowed host' in message:
                return False

            #For 404 errors, only log errors relating to the app's actual urls
            if 'not found' in message or '404' in message:
                return any(path.lower() in message for path in self.ALLOWED_PATHS)

        return True


#Custom filter for Django-Q
class DjangoQFilter(logging.Filter):
    def __init__(self, memory_threshold=90):
        super().__init__()
        self.logger = logging.getLogger('django-q')
        self.memory_threshold = memory_threshold

    def _check_memory(self):
        usage, limit = None, None
        try:
            #cgroups v2 (for newer Docker versions)
            if os.path.exists('/sys/fs/cgroup/memory.current'):
                with open('/sys/fs/cgroup/memory.current') as f:
                    usage = int(f.read().strip())
                with open('/sys/fs/cgroup/memory.max') as f:
                    limit_raw = f.read().strip()
                    limit = int(limit_raw) if limit_raw.isdigit() else None
                    #Filter out unrealistic limits
                    limit = limit if limit < 9223372036854775807 else None 

            #cgroups v1 (for older Docker versions)
            elif os.path.exists('/sys/fs/cgroup/memory/memory.usage_in_bytes'):
                with open('/sys/fs/cgroup/memory/memory.usage_in_bytes') as f:
                    usage = int(f.read().strip())
                with open('/sys/fs/cgroup/memory/memory.limit_in_bytes') as f:
                    limit_raw = f.read().strip()
                    limit = int(limit_raw) if limit_raw.isdigit() else None 
            
            #fallback to psutil
            if usage is None or limit is None:
                memory_info = psutil.virtual_memory()
                usage = memory_info.used
                limit = memory_info.total

        except Exception as exc:
            self.logger.debug(f'Memory check failed: {exc}')

        return usage, limit
    
    def _get_memory_percentage(self, usage, limit):
        '''Calculate memory percentage with safety checks'''
        if not usage or not limit or limit <= 0:
            return None
        return (usage / limit) * 100

    def _format_bytes(self, bytes_value):
        '''Format bytes into human readable format'''
        if not bytes_value:
            return 'Unknown'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024:
                return f'{bytes_value:.1f} {unit}'
            bytes_value /= 1024
        return f'{bytes_value:.1f} TB'


    def filter(self, record):
        db_error_patterns = [
            'name or service not known',
            'failed to pull task from broker',
            'could not create task from schedule',
            'temporary failure in name resolution',
            'reincarnated pusher',
        ]

        if not hasattr(record, 'getMessage'):
            return True

        try:
            message = record.getMessage().lower()
        except Exception:
            return True
            
        if any(pattern in message for pattern in db_error_patterns):
            usage, limit = self._check_memory()
            memory_percentage = self._get_memory_percentage(usage, limit)

            if memory_percentage and memory_percentage >= self.memory_threshold:
                #Memory pressure -- escalate and let it through
                record.memory_info = (
                    f'MEMORY PRESSURE DETECTED: {memory_percentage:.2f}% '
                    f'({self._format_bytes(usage)}/{self._format_bytes(limit)})'
                )
                record.levelno = logging.CRITICAL
                record.levelname = 'CRITICAL'
                return True
            
            #suppress transient DB connectivity noise
            return False

        return True