"""Create a consistent SQLite backup or PostgreSQL pg_dump backup."""
import os, sys, subprocess
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine

url = make_url(os.getenv('DATABASE_URL', 'sqlite:///./invitations.db'))
folder = Path(os.getenv('BACKUP_DIR', './backups')); folder.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
if url.get_backend_name() == 'sqlite':
    source = Path(url.database or 'invitations.db').resolve()
    if not source.exists(): raise SystemExit(f'Database SQLite introuvable: {source}')
    target = folder / f'invitations-{stamp}.db'
    src = create_engine(url.render_as_string(hide_password=False))
    dst = create_engine(f'sqlite:///{target.as_posix()}')
    with src.connect() as a, dst.connect() as b: a.connection.driver_connection.backup(b.connection.driver_connection)
    dst.dispose(); src.dispose()
else:
    target = folder / f'invitations-{stamp}.dump'
    env = os.environ.copy()
    if url.password: env['PGPASSWORD'] = url.password
    cmd = ['pg_dump', '--format=custom', '--no-owner', '--file', str(target), '--host', url.host or 'localhost', '--port', str(url.port or 5432), '--username', url.username or '', url.database or '']
    subprocess.run(cmd, check=True, env=env)
print(target)
