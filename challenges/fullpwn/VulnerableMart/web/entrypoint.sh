#!/bin/sh
set -e

rm -f database.db
python init_db.py
rm -f init_db.py

exec python app.py
