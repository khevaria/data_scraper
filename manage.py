#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # 1. Set the default settings module for Django.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'data_scrapper.settings')

    # 2. Initialize Django so it can load settings properly.
    import django
    django.setup()

    # 3. Now that Django is set up, we can safely import the DB creation function.
    from create_database_if_not_exists import create_database_if_not_exists

    # 4. Call the function to ensure the database exists.
    create_database_if_not_exists()

    # 5. Finally, import and execute the usual Django management command.
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
