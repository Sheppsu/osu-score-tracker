import os
import sqlite3 as sql


def get_db():
    if not os.path.isfile("data.db"):
        print("Need to run create_db.py first")
        quit()

    return sql.connect("data.db")


def get_settings():
    if not os.path.isfile(".env"):
        print("Need a .env file to run")
        quit()

    with open(".env") as f:
        settings = dict(map(lambda l: l.split("="), filter(lambda l: l.strip() != "", f.read().split("\n"))))

    for key in ("CLIENT_ID", "CLIENT_SECRET", "USER_ID"):
        if key not in settings:
            print(f"Missing {key} in .env (check that casing is all caps)")
            quit()

    return settings
