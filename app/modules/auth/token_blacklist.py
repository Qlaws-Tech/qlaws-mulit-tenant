# app/modules/auth/token_blacklist.py

class TokenBlacklistRepository:
    def __init__(self, conn):
        self.conn = conn

    async def blacklist_token(self, jti: str):
        await self.conn.execute(
            """
            INSERT INTO token_blacklist (token_hash, created_at, expires_at, tenant_id)
            VALUES (crypt($1, gen_salt('bf')),
                    now(),
                    now() + interval '30 minutes',
                    current_setting('app.current_tenant_id', true)::uuid)
            """,
            jti
        )

    async def is_token_blacklisted(self, jti: str) -> bool:
        row = await self.conn.fetchrow(
            """
            SELECT 1 FROM token_blacklist
            WHERE token_hash = crypt($1, token_hash)
            AND expires_at > now()
            LIMIT 1
            """,
            jti
        )
        return bool(row)
