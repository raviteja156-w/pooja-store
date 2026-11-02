-- Run once in Supabase > SQL Editor
create table if not exists kv (k text primary key, v jsonb);
alter table kv enable row level security;
