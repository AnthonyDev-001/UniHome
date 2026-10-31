from django.contrib import admin
from .models import Profile

admin.site.register(Profile)
admin.site.site_header = 'UniHome administration'
admin.site.site_title = 'UniHome'
