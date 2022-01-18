#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    sys.stdout.write(chr(27)+']2;Django'+chr(7))
    
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hedemos.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
