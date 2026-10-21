-- Maple Classic Market on Supabase: the group market's database.
-- Paste ALL of this into Supabase (SQL Editor > New query), then press Run. Running it again is safe: it changes
-- nothing that is already there and keeps every listing and key.
--
-- What is here:
--   maple_rows   the listings friends' MapleReader apps send (one scan line each, kept 35 days)
--   maple_keys   who may send (only a scrambled copy of each key is kept)
--   maple_seen   when each person last sent something ("2 scanning now")
--   maple_icons  which item pictures are kept (the pictures themselves are in Storage, bucket "icons")
-- The website (Vercel) reaches these only through the maple_* functions, with the secret key. Nobody else can read
-- or change anything: row level security is on with no rules, and the functions are not open to the public.
--
-- Your own commands (run them here, in the SQL Editor):
--   select maple_add_key('Gunther');      -- a key for a friend (shown once: send it to them privately)
--   select * from maple_people;           -- who has a key
--   select maple_revoke('Gunther');       -- stop their key working
--   select maple_restore('Gunther');      -- let their newest key work again
--   select maple_purge('Gunther');        -- delete every listing they sent
--   select * from maple_stats;            -- listings per person

create table if not exists maple_rows (
  id bigserial primary key,
  h text unique not null,                -- the line's fingerprint: two friends sending the same row keep one
  line text not null,
  who text not null,
  at double precision not null           -- when it arrived (seconds since 1970)
);
create index if not exists maple_rows_at on maple_rows (at);
create index if not exists maple_rows_who on maple_rows (lower(who));
create table if not exists maple_keys (
  h text primary key,                    -- sha256 of the key
  name text not null,
  active boolean not null default true,
  created timestamptz not null default now()
);
create table if not exists maple_seen (who text primary key, last double precision not null);
create table if not exists maple_icons (slug text primary key, kind text not null);

alter table maple_rows enable row level security;
alter table maple_keys enable row level security;
alter table maple_seen enable row level security;
alter table maple_icons enable row level security;

-- The item pictures: public to read (the market page shows them), written only by the website.
do $$
begin
  if exists (select 1 from information_schema.tables where table_schema = 'storage' and table_name = 'buckets') then
    insert into storage.buckets (id, name, public) values ('icons', 'icons', true) on conflict (id) do nothing;
  end if;
end $$;

-- ---------- what the website uses ----------
create or replace function maple_who(p_hash text) returns text language sql stable as $$
  select name from maple_keys where h = p_hash and active order by created desc limit 1
$$;

create or replace function maple_store(p_who text, p_lines json, p_now double precision) returns json
language plpgsql as $$
declare
  total int := json_array_length(p_lines);
  added int;
begin
  with ins as (
    insert into maple_rows (h, line, who, at)
    select encode(sha256(convert_to(t.l, 'UTF8')), 'hex'), t.l, p_who, p_now
    from json_array_elements_text(p_lines) with ordinality as t(l, n)
    order by t.n
    on conflict (h) do nothing
    returning 1)
  select count(*) into added from ins;
  if total > 0 then
    insert into maple_seen (who, last) values (p_who, p_now) on conflict (who) do update set last = excluded.last;
  end if;
  delete from maple_rows where at < p_now - 35 * 86400;   -- pages keep 30 days; older rows are no use to anyone
  return json_build_object('added', added, 'dupes', total - added);
end $$;

create or replace function maple_feed(p_start bigint, p_now double precision, p_lim int) returns json
language plpgsql stable as $$
declare
  top bigint;
  st bigint := greatest(coalesce(p_start, 0), 0);
  rst boolean;
  nxt bigint;
  txt text;
  scanning int;
begin
  select coalesce(max(id), 0) into top from maple_rows;
  rst := st > top;                                          -- the database was cleared: start over
  if rst then st := 0; end if;
  if st = 0 then                                            -- a page starting from nothing: only the days it keeps
    select coalesce(min(id), top + 1) - 1 into st from maple_rows where at >= p_now - 30 * 86400;
  end if;
  select coalesce(string_agg(s.line || E'\n', '' order by s.id), ''), coalesce(max(s.id), st) into txt, nxt
  from (select id, line from maple_rows where id > st order by id limit p_lim) s;
  select count(*) into scanning from maple_seen where last > p_now - 600;
  return json_build_object('text', txt, 'next', nxt, 'more', nxt < top, 'reset', rst,
                           'status', json_build_object('scanning', scanning, 'total', top));
end $$;

-- First picture of an item wins, except a clear one replaces a faded (sold-row) one; at most 20,000 in all
create or replace function maple_icon_ok(p_slug text, p_kind text) returns boolean language sql stable as $$
  select case
    when k.kind = 'normal' then false
    when k.kind = 'faded' and p_kind <> 'normal' then false
    when k.kind is null and (select count(*) from maple_icons) >= 20000 then false
    else true end
  from (select (select kind from maple_icons where slug = p_slug) as kind) k
$$;
create or replace function maple_icon_set(p_slug text, p_kind text) returns boolean language sql as $$
  insert into maple_icons (slug, kind) values (p_slug, case when p_kind = 'normal' then 'normal' else 'faded' end)
  on conflict (slug) do update set kind = excluded.kind
  returning true
$$;
create or replace function maple_icon_list() returns json language sql stable as $$
  select coalesce(json_agg(slug order by slug), '[]'::json) from maple_icons
$$;

-- ---------- your own commands ----------
create or replace function maple_add_key(p_name text) returns text language plpgsql as $$
declare k text;
begin
  p_name := btrim(p_name);
  if p_name = '' or length(p_name) > 40 then raise exception 'Give a name of 1 to 40 characters.'; end if;
  if exists (select 1 from maple_keys where lower(name) = lower(p_name) and active) then
    raise exception '% already has a key that works. To give them a new one, first run: select maple_revoke(''%'');', p_name, p_name;
  end if;
  k := 'mm-' || substr(replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''), 1, 32);
  insert into maple_keys (h, name) values (encode(sha256(convert_to(k, 'UTF8')), 'hex'), p_name);
  return k;   -- shown only this once: only a scrambled copy is kept
end $$;
create or replace function maple_revoke(p_name text) returns text language plpgsql as $$
declare n int;
begin
  update maple_keys set active = false where lower(name) = lower(btrim(p_name)) and active;
  get diagnostics n = row_count;
  return case when n > 0 then p_name || '''s key no longer works.' else 'No working key named ' || p_name || '.' end;
end $$;
create or replace function maple_restore(p_name text) returns text language plpgsql as $$
declare k text;
begin
  if exists (select 1 from maple_keys where lower(name) = lower(btrim(p_name)) and active) then
    return p_name || '''s newest key already works; older keys stay revoked.';
  end if;
  select h into k from maple_keys where lower(name) = lower(btrim(p_name)) order by created desc limit 1;
  if k is null then return 'No key named ' || p_name || '.'; end if;
  update maple_keys set active = true where h = k;
  return p_name || '''s key works again.';
end $$;
create or replace function maple_purge(p_name text) returns text language plpgsql as $$
declare n int;
begin
  delete from maple_rows where lower(who) = lower(btrim(p_name));
  get diagnostics n = row_count;
  return 'Deleted ' || n || ' listings sent by ' || p_name || '. Pages pick this up after "Reload all".';
end $$;
create or replace view maple_people as
  select name, case when active then 'works' else 'revoked' end as key, created::date as since
  from maple_keys order by lower(name), created;
create or replace view maple_stats as
  select who, count(*) as listings, to_timestamp(max(at)) as last_sent from maple_rows group by who order by 2 desc;

-- ---------- nobody but the website (and you, here) may use any of it ----------
do $$
declare r record;
begin
  for r in select unnest(array['public', 'anon', 'authenticated']) as role loop
    if r.role = 'public' or exists (select 1 from pg_roles where rolname = r.role) then
      execute format('revoke all on maple_rows, maple_keys, maple_seen, maple_icons, maple_people, maple_stats from %s', r.role);
      execute format('revoke all on sequence maple_rows_id_seq from %s', r.role);
      execute format('revoke execute on function maple_who(text), maple_store(text, json, double precision), '
        'maple_feed(bigint, double precision, int), maple_icon_ok(text, text), maple_icon_set(text, text), maple_icon_list(), '
        'maple_add_key(text), maple_revoke(text), maple_restore(text), maple_purge(text) from %s', r.role);
    end if;
  end loop;
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute on function maple_who(text), maple_store(text, json, double precision), maple_feed(bigint, double precision, int),
      maple_icon_ok(text, text), maple_icon_set(text, text), maple_icon_list() to service_role;
    revoke execute on function maple_add_key(text), maple_revoke(text), maple_restore(text), maple_purge(text) from service_role;
  end if;
end $$;
