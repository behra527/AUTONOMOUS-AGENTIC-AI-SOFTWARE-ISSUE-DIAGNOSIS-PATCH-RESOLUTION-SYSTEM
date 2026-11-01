from sqlalchemy import select
from app.db import Session, Attachment
from app.redaction import sanitize_log
from conftest import headers
from test_pipeline import BODY


def test_sanitized_attachments_persist_and_stay_private(client):
    ticket = client.post('/api/v1/projects/p1/tickets',headers=headers('customer'),json=BODY).json()['id']
    route=f'/api/v1/tickets/{ticket}/attachments'
    content='Authorization: Bearer very-secret-value\npassword=supersecret\nuser@example.com\nValueError: upload failed'
    response=client.post(route,headers=headers('customer'),json={'filename':'trace.log','content':content})
    assert response.status_code==201 and response.json()['redacted']
    with Session() as db:
        row=db.scalar(select(Attachment))
        assert 'very-secret-value' not in row.content and 'supersecret' not in row.content
        assert 'user@example.com' not in row.content and 'ValueError' in row.content
    assert client.get(route,headers=headers('other')).status_code==404
    assert client.get(route,headers=headers()).status_code==200
    assert client.post(route,headers=headers('customer'),json={'filename':'../trace.log','content':'bad'}).status_code==422
    assert client.post(route,headers=headers('customer'),json={'filename':'source.py','content':'bad'}).status_code==422
    for i in range(4):
        assert client.post(route,headers=headers('customer'),json={'filename':f'trace{i}.log','content':'normal trace'}).status_code==201
    assert client.post(route,headers=headers('customer'),json={'filename':'sixth.log','content':'trace'}).status_code==409


def test_private_key_is_redacted():
    clean,redacted=sanitize_log('-----BEGIN RSA PRIVATE KEY-----\nsecret\n-----END RSA PRIVATE KEY-----\ntraceback')
    assert redacted and 'secret' not in clean and 'traceback' in clean
