# create_database_if_not_exists.py

import MySQLdb
from django.conf import settings

def create_database_if_not_exists():
    db_params = settings.DATABASES['default']
    db_name = db_params['NAME']
    user = db_params['USER']
    password = db_params['PASSWORD']
    host = db_params['HOST'] or 'localhost'
    port = int(db_params['PORT']) if db_params['PORT'] else 3306

    # Connect without specifying the DB name
    connection = MySQLdb.connect(
        host=host, user=user, passwd=password, port=port
    )

    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
    cursor.close()
    connection.close()

