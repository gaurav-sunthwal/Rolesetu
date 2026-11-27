#!/usr/bin/env bash
# Keeps the main and backup databases equal by copying from whichever one changed since
# the last sync. Never overwrites a database holding changes the other lacks: if both
# changed, it stops and fails so a person decides. See docs/runbooks/database-backup.md
#
# Usage: db-sync.sh [auto|main-to-backup|backup-to-main]
# Env:   MAIN_DATABASE_URL, BACKUP_DATABASE_URL (postgresql://...?sslmode=require)
set -euo pipefail

mode=${1:-auto}
export PGTZ=UTC PGDATESTYLE=ISO  # same row text on every run, so fingerprints compare
# pg_dump needs a direct connection; Neon's pooler host has "-pooler" in it.
MAIN=${MAIN_DATABASE_URL/-pooler./.}
BACKUP=${BACKUP_DATABASE_URL/-pooler./.}

q() { psql "$1" -X -tA -v ON_ERROR_STOP=1 -c "$2"; }

# md5 over every row of every public table: changes whenever any row is added, edited or removed.
fingerprint() {
  psql "$1" -X -tA -v ON_ERROR_STOP=1 <<'SQL'
select coalesce(
  'select md5(string_agg(t || '':'' || n || '':'' || h, '','' order by t)) from ('
    || string_agg(format('select %L as t, count(*) as n, coalesce(sum(hashtext(x::text)), 0) as h from public.%I x', relname, relname), ' union all ')
    || ') s',
  'select ''empty''')
from pg_class where relnamespace = 'public'::regnamespace and relkind = 'r'
\gexec
SQL
}

# Last fingerprint saved by a sync, kept outside public so it is never copied or fingerprinted.
stored() { q "$1" "select fp from sync_meta.state where id = 1" 2>/dev/null || echo none; }
save() {
  q "$1" "create schema if not exists sync_meta;
    create table if not exists sync_meta.state (id int primary key, fp text not null, synced_at timestamptz not null);
    insert into sync_meta.state values (1, '$2', now())
    on conflict (id) do update set fp = excluded.fp, synced_at = excluded.synced_at" >/dev/null
}
tables() { q "$1" "select count(*) from pg_tables where schemaname = 'public'"; }

copy() {  # copy <from-name> <from-url> <to-name> <to-url> <from-fingerprint>
  if [ "$(tables "$2")" = 0 ]; then
    echo "::error::$1 has no tables; refusing to copy an empty database over $3."; exit 1
  fi
  # Undo point: the target as it was, uploaded as a workflow artifact.
  pg_dump --format=custom --no-owner --no-acl --exclude-schema=sync_meta --file=undo-"$3".dump "$4"
  pg_dump --format=custom --no-owner --no-acl --exclude-schema=sync_meta --file=db.dump "$2"
  # One transaction: if anything fails, the target keeps everything it had.
  pg_restore --clean --if-exists --no-owner --no-acl --single-transaction --exit-on-error --dbname="$4" db.dump
  save "$2" "$5"
  save "$4" "$(fingerprint "$4")"
  echo "Copied $1 → $3. $3 is at migration $(q "$4" "select version_num from alembic_version")."
}

for name in main backup; do
  url=$([ "$name" = main ] && echo "$MAIN" || echo "$BACKUP")
  if ! q "$url" "select 1" >/dev/null 2>&1; then
    echo "::warning::The $name database can't be reached (Neon compute quota used up?). Nothing copied; will try again next run."
    exit 0
  fi
done

fm=$(fingerprint "$MAIN"); fb=$(fingerprint "$BACKUP")
sm=$(stored "$MAIN"); sb=$(stored "$BACKUP")

case "$mode" in
  main-to-backup) copy main "$MAIN" backup "$BACKUP" "$fm" ;;
  backup-to-main) copy backup "$BACKUP" main "$MAIN" "$fb" ;;
  auto)
    if [ "$(tables "$BACKUP")" = 0 ]; then
      echo "Backup is empty: first copy from main."; copy main "$MAIN" backup "$BACKUP" "$fm"
    elif [ "$fm" = "$sm" ] && [ "$fb" = "$sb" ]; then
      echo "Neither database changed since the last sync. Nothing to do."
    elif [ "$fb" = "$sb" ]; then
      echo "Main changed: copying main → backup."; copy main "$MAIN" backup "$BACKUP" "$fm"
    elif [ "$fm" = "$sm" ]; then
      echo "Backup changed (the app is running on it): copying backup → main."; copy backup "$BACKUP" main "$MAIN" "$fb"
    else
      echo "::error::Both databases changed since the last sync, so either copy would lose data. Nothing was copied. See docs/runbooks/database-backup.md, 'Both changed'."
      exit 1
    fi ;;
  *) echo "Unknown mode: $mode"; exit 1 ;;
esac
