from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
from distutils import file_util, dir_util

class Command(BaseCommand):
    help = 'Copies vendor files from node_modues folder'

    def handle(self, *args, **options):
        main_vendor_css_folder = os.path.join(
            settings.BASE_DIR, 'main', 'static', 'main', 'vendor', 'css')
        main_vendor_js_folder = os.path.join(
            settings.BASE_DIR, 'main', 'static', 'main', 'vendor', 'js')
        # main_vendor_icons_folder = os.path.join(
        #     settings.BASE_DIR, 'main', 'static', 'main', 'vendor', 'icons')

        file_util.copy_file(os.path.join(settings.BASE_DIR, 'node_modules', 'jquery',
            'dist', 'jquery.min.js'), main_vendor_js_folder)
        file_util.copy_file(os.path.join(settings.BASE_DIR, 'node_modules', 'bootstrap',
            'dist', 'css', 'bootstrap.min.css'), main_vendor_css_folder)
        file_util.copy_file(os.path.join(settings.BASE_DIR, 'node_modules', 'bootstrap',
            'dist', 'js', 'bootstrap.bundle.min.js'), main_vendor_js_folder)
        # dir_util.copy_tree(os.path.join(settings.BASE_DIR, 'node_modules', 'bootstrap-icons',
        #     'icons'), main_vendor_icons_folder)
        
        

