insert into public.roles(role_key, label) values
  ('general','General'),
  ('pro','Pro'),
  ('scholars','SUAPS Scholars'),
  ('analytics','SUAPS Analytics'),
  ('ops','Operations')
on conflict(role_key) do nothing;

-- Create an admin/you user placeholder if you want
-- replace [email] with your email
insert into public.users(email, display_name)
select '[your@email]'::text, 'You'
where not exists (select 1 from public.users where email='[your@email]');

-- Grant yourself analytics role so writes work
insert into public.user_roles(user_id, role_key)
select id, 'analytics' from public.users where email='[your@email]'
on conflict do nothing;

-- Whitelist a few safe domains (examples)
insert into public.external_sources_whitelist(source_id, label, priority, url_pattern, enabled) values
  ('wikipedia','Wikipedia', 10, 'https://*.wikipedia.org/*', true),
  ('arxiv','arXiv', 9, 'https://arxiv.org/*', true),
  ('doi','DOI', 8, 'https://doi.org/*', true)
on conflict (source_id) do nothing;
