from pathlib import Path
import shutil
from sqlalchemy import select
from .config import settings
from .db import Session, Project, Membership, Repository, Ticket, Snapshot, Job
from .indexer import git


def seed():
    if settings.auth_mode != 'demo':
        raise RuntimeError('Demo seeding is disabled outside demo authentication')
    root = settings.local_repo_root.resolve() / 'python-service'
    root.mkdir(parents=True, exist_ok=True)
    for source in Path('examples/python-service').iterdir():
        if source.is_file() and source.suffix in ('.py', '.md'):
            shutil.copyfile(source, root / source.name)
    if not (root / '.git').exists():
        git('init', root)
        git('-C', root, 'add', 'upload.py', 'pricing.py', 'users.py', 'README.md')
        git('-C', root, '-c', 'user.name=BugHound-Ai Demo', '-c', 'user.email=demo@localhost', 'commit', '-m', 'Seed intentional Python diagnosis fixtures')
    sha = git('-C', root, 'rev-parse', 'HEAD').decode().strip()
    with Session() as db:
        if db.get(Project, 'project-demo'):
            repo = db.scalar(select(Repository).where(Repository.project_id == 'project-demo', Repository.name == 'python-support-service'))
            if repo:
                repo.remote_url = str(root)
                db.commit()
            print('Demo already seeded. Fixture commit:', sha)
            return
        db.add_all([Project(id='project-demo', tenant_id='tenant-demo', name='Python Support Service'),
                    Project(id='project-other', tenant_id='tenant-other', name='Separate tenant')])
        db.flush()
        db.add_all([Membership(subject=s, project_id='project-demo', role=r) for s, r in [('customer', 'customer'), ('engineer', 'engineer'), ('admin', 'admin')]])
        db.add(Membership(subject='other', project_id='project-other', role='customer'))
        repo = Repository(project_id='project-demo', name='python-support-service', remote_url=str(root))
        db.add(repo)
        db.flush()
        snapshot = Snapshot(repository_id=repo.id, commit_sha=sha)
        db.add(snapshot)
        db.flush()
        db.add(Job(project_id='project-demo', kind='INDEX', target_id=snapshot.id))
        db.add_all([
            Ticket(project_id='project-demo', customer_id='customer', title='PDF upload crashes at the size limit', description='Uploading a five megabyte PDF raises a server error instead of accepting the file.', expected_behavior='Accept PDF files up to and including five MiB.', actual_behavior='A ValueError is raised by the upload handler.', reproduction_steps=['Select a PDF exactly five MiB in size', 'Upload the file', 'Observe the error']),
            Ticket(project_id='project-demo', customer_id='customer', title='Percentage discount produces the wrong total', description='A twenty percent discount on a 200 subtotal returns 180 instead of 160.', expected_behavior='Apply discount as a percentage of subtotal.', actual_behavior='The discount number is subtracted directly.', reproduction_steps=['Create an order with a subtotal of 200', 'Apply a twenty percent discount']),
            Ticket(project_id='project-demo', customer_id='customer', title='Incomplete user profile fails to display', description='A user profile without a display_name field causes a KeyError.', expected_behavior='Show Guest when display name is missing.', actual_behavior='The profile page crashes.', reproduction_steps=['Load a profile with no display_name', 'Open profile page'])])
        db.commit()
    print('Seeded demo. Fixture commit:', sha)


if __name__ == '__main__':
    seed()
