"""Request-local presentation language; never alter saved evidence or settings."""
from contextvars import ContextVar
from contextlib import contextmanager
import json
import re
from functools import lru_cache
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

@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent/'dist/en.json').read_text())

@lru_cache(maxsize=1)
def _phrases():
    # Longest first: a complete warning takes precedence over a short label.
    return re.compile('|'.join(re.escape(s) for s in sorted(catalog(),key=len,reverse=True) if re.search(r'[\u3400-\u9fff]',s)))

def english_text(value):
    words=catalog()
    if value in words:return words[value]
    translated=_phrases().sub(lambda m:words[m[0]],value)
    # Translate composed UI sentences only when every Chinese fragment is known.
    # Partial replacements must never corrupt an original chat name or quotation.
    if translated==value or re.search(r'[\u3400-\u9fff]',translated):return value
    return translated.translate(str.maketrans({'。':'. ','；':'; ','：':': ','，':', ','（':' (', '）':')','、':', '})).strip()

def localize(value):
    words=catalog() if current_language()=='en' else {}
    prose={'text','quote','title','content','explanation','reason','action','result','goal','goal_short',
           'before','now','next','benefit','display','name','label','note','sent','status_label','use_note'}
    def walk(item,key=None):
        if isinstance(item,str):
            if key in {'id','key','client','session_id','source_id','agent_id','event_id','evidence_id','evidence_ids','call_id','target_id','token','grant','revision','source_fingerprint','content_fingerprint','required','allowed'}:return item
            if key in ('quote','excerpt'):
                return plain_words(item,'zh' if re.search(r'[\u3400-\u9fff]',item) else 'en')
            translated=english_text(item) if words and key not in ('quote','excerpt') else item
            return plain_words(translated,current_language()) if key in prose else translated
        if isinstance(item,list):return [walk(x,key) for x in item]
        if isinstance(item,dict):
            original_title='title_source' in item or ('client' in item and 'key' in item)
            quoted=item.get('kind') in ('user','assistant','operation_note')
            result={}
            for k,v in item.items():
                if k=='reason' and isinstance(v,str) and re.fullmatch(r'[a-z]+(?:_[a-z]+)+',v):result[k]=v
                elif isinstance(v,str) and (k=='name' or (k=='title' and original_title)):result[k]=v
                elif isinstance(v,str) and k=='text' and quoted:result[k]=plain_words(v,'zh' if re.search(r'[\u3400-\u9fff]',v) else 'en')
                else:result[k]=walk(v,k)
            if words and not quoted and item.get('basis') in ('inference','unknown') and isinstance(result.get('text'),str) and re.search(r'[\u3400-\u9fff]',result['text']):
                result['text']='An English explanation of this note is not available yet. Its supporting notes retain the original wording.'
            return result
        return item
    return walk(value)
