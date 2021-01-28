#!/bin/bash


if [ "$DATABASE" = "postgresdb" ]; then
    echo "Waiting for postgres.."

    while ! nc -z "$DATABASE_HOST" $DATABASE_PORT; do 
        sleep 0.1
    done


    echo "PostgreSQL started..."
fi
python manage.py makemigrations
python manage.py migrate

echo "Running tests..."
echo "######################## TESTING #####################################"
python manage.py test -v 2 --force-color
echo "######################################################################"

tail -f /dev/null