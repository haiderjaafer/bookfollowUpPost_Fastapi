# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.')],
    hiddenimports=[
        # Database drivers
        'aioodbc',
        'pyodbc',
        
        # Passlib handlers (already included)
        'passlib.handlers.bcrypt',
        'passlib.handlers.sha2_crypt',
        'passlib.handlers.pbkdf2',
        'passlib.handlers.argon2',
        'passlib.handlers.scrypt',
        'passlib.handlers.django',
        'passlib.handlers.ldap_digests',
        'passlib.handlers.misc',
        'passlib.handlers.mysql',
        'passlib.handlers.oracle',
        'passlib.handlers.postgres',
        'passlib.handlers.roundup',
        'passlib.handlers.sun_md5_crypt',
        'passlib.handlers.windows',
        
        # SQLAlchemy async support
        'sqlalchemy.ext.asyncio',
        'sqlalchemy.ext.asyncio.engine',
        'sqlalchemy.ext.asyncio.session',
        'sqlalchemy.ext.asyncio.base',
        'sqlalchemy.pool',
        'sqlalchemy.pool.impl',
        'sqlalchemy.pool.events',
        'sqlalchemy.engine.events',
        'sqlalchemy.dialects',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.aiosqlite',
        'sqlalchemy.dialects.postgresql',
        'sqlalchemy.dialects.postgresql.asyncpg',
        'sqlalchemy.dialects.mysql',
        'sqlalchemy.dialects.mysql.aiomysql',
        
        # Async database drivers
        'aiosqlite',
        'asyncpg',
        'aiomysql',
        
        # FastAPI and dependencies
        'fastapi',
        'fastapi.routing',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.responses',
        'starlette.requests',
        'uvicorn',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.websockets',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        
        # Pydantic (FastAPI dependency)
        'pydantic',
        'pydantic.fields',
        'pydantic.validators',
        'pydantic.json',
        
        # JSON and serialization
        'json',
        'orjson',
        'ujson',
        
        # Async support
        'asyncio',
        'concurrent.futures',
        
        # Logging and debugging
        'logging',
        'logging.config',
        
        # Environment and config
        'dotenv',
        'python-dotenv',
        
        # HTTP clients (if used)
        'httpx',
        'aiohttp',
        
        # JWT (if using authentication)
        'jose',
        'python-jose',
        'python-jose.jwt',
        'cryptography',
        
        # Date/time handling
        'datetime',
        'dateutil',
        'python-dateutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyd = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyd,
    a.scripts,
    [],
    exclude_binaries=True,
    name='run',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    cofile_version='1.0.0.0'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='run'
)