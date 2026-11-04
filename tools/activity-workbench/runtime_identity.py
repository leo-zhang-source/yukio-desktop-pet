"""Local service identity for safe launcher reuse; no paths sent to the model."""
import hashlib
import ast
import json
from pathlib import Path
from page_explanation_policy import enabled as page_policy_enabled

ROOT=Path(__file__).resolve().parent
FILES=('agent_explanation.py','chat_catalog.py','work_understanding.py','history_review.py','reading_view.py','page_explanation_policy.py','plain_language.py','task_summary.py','project_context.py','handoff_view.py','server.py','source_context.py','glance_view.py','glance_automation.py','dist/history.html','dist/glance.js','dist/history-review.js','dist/i18n.js','dist/en.json','dist/glance.css','history_view.py','context_view.py','explanation.py','runtime_identity.py','localization.py','collector_status.py','dist/index.html','dist/app.js','dist/context.js','dist/explanation.js','dist/style.css')
def identity(databases,model_config=None):
    digest=hashlib.sha256()
    for name in FILES:
        digest.update(name.encode());digest.update((ROOT/name).read_bytes())
    digest.update((ROOT/'launcher.py').read_bytes())
    core=ROOT/'core/yukio'
    if not core.is_dir():core=ROOT.parents[1]/'YukioWin/yukio'
    pending=['activity_collector_cli'];seen=set()
    while pending:
        name=pending.pop()
        if name in seen:continue
        seen.add(name);raw=(core/(name+'.py')).read_bytes()
        digest.update(name.encode());digest.update(raw)
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node,ast.ImportFrom) and node.level and node.module:
                dependency=node.module.split('.')[0]
                if (core/(dependency+'.py')).is_file():pending.append(dependency)
    scope=hashlib.sha256(json.dumps({k:str(Path(v).resolve()) for k,v in databases.items()},sort_keys=True).encode()).hexdigest()
    parents={Path(v).parent.resolve() for v in databases.values()}
    from agent_explanation import configuration
    directory=next(iter(parents)) if len(parents)==1 else None
    model_config=model_config or configuration(directory)
    config=hashlib.sha256(json.dumps(model_config,sort_keys=True).encode()).hexdigest()
    automatic=page_policy_enabled(next(iter(parents)) if len(parents)==1 else None,model_config)
    return dict(service='yukio-activity-workbench',build=digest.hexdigest(),database_scope=scope,model_configuration=config,automatic_page_explanation=automatic)
