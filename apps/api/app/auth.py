from functools import lru_cache
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from .config import settings
from .db import Membership, get_db

DEMO_USERS = {'demo-customer': 'customer', 'demo-engineer': 'engineer', 'demo-admin': 'admin', 'demo-other': 'other'}


@lru_cache
def jwks():
    return jwt.PyJWKClient(settings.oidc_jwks_url, timeout=5)


def principal(authorization: str = Header(default='')):
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Authentication required')
    token = authorization[7:]
    if settings.auth_mode == 'demo':
        if token not in DEMO_USERS:
            raise HTTPException(401, 'Invalid demo identity')
        return DEMO_USERS[token]
    if settings.auth_mode != 'oidc' or not all([settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url]):
        raise HTTPException(503, 'Identity provider is not configured')
    try:
        key = jwks().get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=settings.oidc_audience,
                            issuer=settings.oidc_issuer, options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']})
        return claims['sub']
    except jwt.PyJWTError:
        raise HTTPException(401, 'Invalid or expired identity') from None


def authorize(db, subject, project_id, internal=False, admin=False):
    member = db.scalar(select(Membership).where(Membership.subject == subject, Membership.project_id == project_id))
    if not member:
        raise HTTPException(404, 'Resource not found')
    if admin and member.role != 'admin':
        raise HTTPException(403, 'Administrator permission required')
    if internal and member.role not in ('engineer', 'reviewer', 'admin'):
        raise HTTPException(403, 'Internal access required')
    return member
