-- Add application-owned roles to user profiles.
-- Supabase Auth verifies identity; this column is the app authorization source.

alter table user_profiles
add column if not exists role text not null default 'learner';

alter table user_profiles
drop constraint if exists user_profiles_role_check;

alter table user_profiles
add constraint user_profiles_role_check
check (role in ('learner', 'admin'));

-- Grant admin manually with:
-- update public.user_profiles
-- set role = 'admin'
-- where email = 'your-email@gmail.com';
