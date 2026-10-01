-- Run once in Supabase SQL editor.
create table if not exists ai_drafts (
  id uuid primary key,
  payload jsonb not null,                    -- written by the pipeline only
  status text not null default 'needs_review', -- needs_review | edited | approved | rejected | published
  edited jsonb,                              -- admin edits live here, never overwritten by the pipeline
  reviewed_by uuid, reviewed_at timestamptz,
  created_at timestamptz default now()
);
alter table ai_drafts enable row level security;   -- no policies = only the service key can access
-- Admin dashboard: add a policy for your admin users, e.g.
-- create policy admin_all on ai_drafts for all using ((select role from profiles where id = auth.uid()) = 'admin');
-- Storage: create a PRIVATE bucket named "posters" (admin views via signed URLs).
