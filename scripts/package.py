"""Create a source-only release; excludes secrets, uploads, environments, and Git metadata."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parent.parent
out=root/'dist';out.mkdir(exist_ok=True)
paths=[root/p for p in ['README.md','pyproject.toml','uv.lock','Dockerfile','.dockerignore','.env.example','.gitignore','compose.yaml']]
for directory in ['app','tests','scripts','docs']:
    paths.extend(p for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
with zipfile.ZipFile(out/'acquisition-sourcing-agent.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(set(paths)):
        archive.write(p,Path('acquisition-sourcing-agent')/p.relative_to(root))
print(out/'acquisition-sourcing-agent.zip')
