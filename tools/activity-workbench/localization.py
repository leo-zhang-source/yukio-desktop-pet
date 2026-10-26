"""Request-local presentation language; never alter saved evidence or settings."""
from contextvars import ContextVar
from contextlib import contextmanager
import json
from pathlib import Path
from plain_language import plain_words

_language=ContextVar('workbench_language',default='zh')

def normalize_language(value):
    first=str(value or 'zh').split(',')[0].split(';')[0].lower()
    return 'zh' if first.startswith('zh') else 'en'

def current_language():return _language.get()

@contextmanager
def language_context(value):
    token=_language.set(normalize_language(value))
    try:yield
    finally:_language.reset(token)

def catalog():
    return json.loads((Path(__file__).parent/'dist/en.json').read_text())

def english_text(value):return catalog().get(value,value)

def localize(value):
    words=catalog() if current_language()=='en' else {}
    prose={'text','quote','title','content','explanation','reason','action','result','goal','goal_short',
           'before','now','next','benefit','display','name','label','note','sent','status_label','use_note'}
    def walk(item,key=None):
        if isinstance(item,str):
            translated=words.get(item,item)
            return plain_words(translated,current_language()) if key in prose else translated
        if isinstance(item,list):return [walk(x,key) for x in item]
        if isinstance(item,dict):return {k:walk(v,k) for k,v in item.items()}
        return item
    return walk(value)
