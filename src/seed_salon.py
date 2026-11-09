"""Compatibility entry point for the isolated setup_demo management command."""

import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], 'setup_demo', *sys.argv[1:]])


if __name__ == '__main__':
    main()
