"""Live local spawn/solve/reuse/isolation/expiry check. Cleans only its own UUID."""

import sys, os, json, tempfile, shutil, uuid, subprocess, time
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
challenge=Path(__file__).resolve().parent
root=challenge.parents[2]
if not (root.parent/'docker-backend/app/main.py').exists():
    raise SystemExit(f"Clone docker-backend beside {root} before running this check")
sys.path.insert(0,str(root.parent/'docker-backend'))
os.environ['BACKEND_API_TOKEN']='local-qa-only'
os.environ['DOCKER_PUBLIC_HOST']='127.0.0.1'
os.environ['PYTHONIOENCODING']='utf-8'
from app import main
real=main.docker_client
run_id=str(uuid.uuid4())
class ScopedManager:
    def __init__(self, manager): self.manager=manager
    def __getattr__(self, name): return getattr(self.manager,name)
    def list(self, **kwargs):
        filters=dict(kwargs.get('filters') or {})
        filters['label']=list(filters.get('label',[]))+[f'ctfd.challenge_uuid={run_id}']
        kwargs['filters']=filters
        return self.manager.list(**kwargs)
main.docker_client=SimpleNamespace(containers=ScopedManager(real.containers),networks=ScopedManager(real.networks),images=SimpleNamespace(pull=lambda image,**kw: real.images.get(image)))
main._get_challenge_config=lambda _: {'image':'stack:vulnerablemart','prefix':'codex-qa','name':'vulnerablemart'}
one=main.CreateContainerRequest(challenge_uuid=run_id,team_id=900001)
two=main.CreateContainerRequest(challenge_uuid=run_id,team_id=900002)
with tempfile.TemporaryDirectory() as temp:
    spec=json.loads((challenge/'stack.json').read_text())
    for key,service in spec['services'].items(): service['image']=f'codex-vulnerablemart-qa-{key}:latest'
    (Path(temp)/'vulnerablemart.json').write_text(json.dumps(spec))
    shutil.copy(challenge/'flags.env',Path(temp)/'vulnerablemart.env')
    os.environ['STACK_CONFIG_DIR']=temp
    try:
        before=datetime.now(timezone.utc)
        result=main.create_container(one,'Bearer local-qa-only')
        assert len(main._matching_containers(one))==3
        expires=datetime.fromisoformat(result['expires_at'].replace('Z','+00:00'))
        assert 5395<(expires-before).total_seconds()<5405
        print('PASS: one spawn created three containers with a 90-minute expiry.',flush=True)
        again=main.create_container(one,'Bearer local-qa-only')
        assert again['reused'] and again['connection_info']==result['connection_info']
        assert datetime.fromisoformat(again['expires_at'].replace('Z','+00:00'))==expires
        print('PASS: repeat Start reused all containers without extending expiry.',flush=True)
        ports={}
        for c in main._matching_containers(one):
            c.reload(); name=c.labels['ctfd.stack_service']; bindings=c.attrs['NetworkSettings']['Ports']
            for port,bind in bindings.items(): ports[(name,port)]=bind[0]['HostPort']
            env=dict(v.split('=',1) for v in c.attrs['Config']['Env'] if '=' in v)
            if name=='maintenance': assert {k for k in env if k.endswith('_FLAG')}=={'SHELL_FLAG'}
        import requests
        ready = False
        for _ in range(60):
            try:
                a=requests.get('http://127.0.0.1:'+ports['web','80/tcp'],timeout=1)
                b=requests.get('http://127.0.0.1:'+ports['portal','80/tcp'],timeout=1)
                if a.status_code==b.status_code==200:
                    ready = True
                    break
            except requests.RequestException: pass
            time.sleep(.5)
        if not ready:
            raise RuntimeError('Shop or seller portal did not become ready')
        solver=subprocess.run([sys.executable,str(challenge/'solve.py'),'--no-color','--host','127.0.0.1','--web-port',ports['web','80/tcp'],'--portal-port',ports['portal','80/tcp'],'--maint-port',ports['maintenance','50050/tcp'],'--ssh-port',ports['portal','50022/tcp']],capture_output=True,text=True,encoding='utf-8',env=os.environ,timeout=300)
        print(solver.stdout,flush=True)
        if solver.stderr: print(solver.stderr,flush=True)
        assert solver.returncode==0,'Full solve failed'
        values=dict(line.split('=',1) for line in (challenge/'flags.env').read_text().splitlines() if line and not line.startswith('#'))
        assert all(value in solver.stdout for key,value in values.items() if key.endswith('_FLAG'))
        print('PASS: all eight recovered flags match the scoring fixture.',flush=True)
        second=main.create_container(two,'Bearer local-qa-only')
        assert len(main._matching_containers(two))==3 and second['connection_info']!=result['connection_info']
        assert len(main.docker_client.networks.list())==2
        print('PASS: a second team has its own three containers, network and published ports.',flush=True)
        assert main.terminate_container(one,'Bearer local-qa-only')['removed']==3
        assert len(main._matching_containers(two))==3 and len(main.docker_client.networks.list())==1
        print('PASS: Stop removed only the first team environment.',flush=True)
        # The Docker facade scopes every list to this random QA UUID. Never reap other instances.
        main._utcnow=lambda: datetime.now(timezone.utc)+timedelta(minutes=91)
        assert main.reap_expired_containers()==3
        assert not main.docker_client.containers.list(all=True) and not main.docker_client.networks.list()
        print('PASS: expiry removed the complete second environment and its network.',flush=True)
    finally:
        for payload in (one,two): main._terminate_matching_containers(payload)
