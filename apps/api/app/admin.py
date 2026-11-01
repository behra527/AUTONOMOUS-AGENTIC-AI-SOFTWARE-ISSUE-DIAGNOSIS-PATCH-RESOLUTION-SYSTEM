"""Operator-only CLI; no public endpoint can grant its own membership."""
import argparse
from sqlalchemy import select
from .db import Session, Project, Membership, AuditEvent


def main():
    parser = argparse.ArgumentParser(description='Provision project access for verified OIDC subjects')
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create-project')
    create.add_argument('--tenant-id', required=True)
    create.add_argument('--name', required=True)
    grant = commands.add_parser('grant-role')
    grant.add_argument('--project-id', required=True)
    grant.add_argument('--subject', required=True)
    grant.add_argument('--role', required=True, choices=['customer', 'engineer', 'reviewer', 'admin'])
    args = parser.parse_args()
    with Session() as db:
        if args.command == 'create-project':
            project = Project(tenant_id=args.tenant_id, name=args.name)
            db.add(project)
            db.flush()
            db.add(AuditEvent(project_id=project.id, actor='operator-cli', action='PROJECT_CREATED', target_id=project.id))
            db.commit()
            print('Project ID:', project.id)
        else:
            if not db.get(Project, args.project_id):
                parser.error('Project does not exist')
            member = db.scalar(select(Membership).where(Membership.project_id == args.project_id, Membership.subject == args.subject))
            if member:
                member.role = args.role
            else:
                member = Membership(project_id=args.project_id, subject=args.subject, role=args.role)
                db.add(member)
            db.flush()
            db.add(AuditEvent(project_id=args.project_id, actor='operator-cli', action='MEMBERSHIP_PROVISIONED', target_id=member.id))
            db.commit()
            print('Project membership saved.')


if __name__ == '__main__':
    main()
