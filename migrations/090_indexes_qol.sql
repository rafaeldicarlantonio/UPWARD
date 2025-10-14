-- QoL indexes you’ll thank yourself for later
create index if not exists ix_messages_created on public.messages(created_at);
create index if not exists ix_memories_type_created on public.memories(type, created_at desc);
create index if not exists ix_entities_type on public.entities(type);
