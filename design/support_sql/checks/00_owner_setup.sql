-- users: S1, S2 support; M1 marketing; N1 support opened without a link today (new open account)
INSERT INTO users (id, login_hmac, password_hash, activated_at, display_name, profession, self_registered, terms_version, terms_accepted_at, open_registered)
VALUES
 ('11111111-1111-1111-1111-111111111111', decode(repeat('01',32),'hex'), 'scrypt$'||repeat('a',32)||'$'||repeat('b',128), now(), 'سارة', 'SUPPORT', true, '2026-10-09', now(), false),
 ('22222222-2222-2222-2222-222222222222', decode(repeat('02',32),'hex'), 'scrypt$'||repeat('a',32)||'$'||repeat('b',128), now(), 'خالد', 'SUPPORT', true, '2026-10-09', now(), false),
 ('33333333-3333-3333-3333-333333333333', decode(repeat('03',32),'hex'), 'scrypt$'||repeat('a',32)||'$'||repeat('b',128), now(), 'منى', 'MARKETING', true, '2026-10-09', now(), false),
 ('44444444-4444-4444-4444-444444444444', decode(repeat('04',32),'hex'), 'scrypt$'||repeat('a',32)||'$'||repeat('b',128), now(), 'نورة', 'SUPPORT', true, '2026-10-09', now(), true);
