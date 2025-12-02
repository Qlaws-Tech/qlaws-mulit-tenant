
# create environment
conda create -p venv python==3.11.9
conda activate /home/soham/qlaws-backend/qlaws-mulit-tenant/venv
pip install -r requirements.txt
(or)
 rm -rf .venv
python3.11.9 -m venv .venv
source .venv/bin/activate

#check environment
pip install slowapi 
pip install pytest
pip install redis


#Install New Libraries - SMTP, Rate Limiting, and Redis.
pip install aiosmtplib slowapi redis httpx

pip install cryptography pyotp pytest-asyncio
pip install "bcrypt==4.0.1"
pip install asyncpg fastapi
pip install slowapi redis


chmod 777 entrypoint.sh

-- setup for Local DB
--container_name: postgres_multi_tenant
--Host : host.docker.internal
--DATABASE_NAME=authz_db
--#DATABASE_USER=qlaws_app
--#DATABASE_PASSWORD=app_password
--port=5432

