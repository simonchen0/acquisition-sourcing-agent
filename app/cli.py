import argparse
import getpass
import os
from sqlalchemy import select
from .db import init_db, Session, User
from .security import hash_password

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action', choices=['init-db','create-user','setup']); parser.add_argument('--email')
    args=parser.parse_args(); init_db()
    if args.action=='init-db': print('Database initialized.'); return
    if args.action=='setup':
        with Session() as db:
            if db.scalar(select(User.id).limit(1)):
                print('Database initialized; an account already exists. No credentials changed.'); return
    email=(args.email or os.getenv('ADMIN_EMAIL') or input('Email: ')).strip().lower()
    if '@' not in email or len(email)>254: raise SystemExit('Invalid email.')
    password=os.getenv('ADMIN_PASSWORD') or getpass.getpass('Password (12+ characters): ')
    if args.action=='setup' and not os.getenv('ADMIN_PASSWORD') and password!=getpass.getpass('Confirm password: '): raise SystemExit('Passwords did not match.')
    with Session() as db:
        if db.scalar(select(User).where(User.email==email)): raise SystemExit('Account already exists; no password was changed.')
        db.add(User(email=email,password=hash_password(password))); db.commit()
    print('Account created. Credentials were not stored in source files.')

if __name__=='__main__': main()
