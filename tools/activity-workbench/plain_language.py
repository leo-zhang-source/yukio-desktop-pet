"""Presentation only: keep technical evidence local, name its role in the story.

An extension identifies a kind of object, never its purpose. For example an
unknown PNG becomes '这张图片', not an invented 'App 封面图'. An explicit caption
such as '雪绪 App 封面图' stays available to the model and is preferred in prose.
"""
import re


def object_name(token):
    suffix=token.lower().rstrip('`\"\'）)]}').rsplit('.',1)[-1]
    if suffix in {'png','jpg','jpeg','webp','gif','svg','heic','ico'}:return '这张图片'
    if suffix in {'mov','mp4','webm'}:return '这段视频'
    if suffix in {'html','htm','css'}:return '相关页面'
    if suffix in {'md','pdf','docx','txt','xlsx','csv'}:return '这份资料'
    if suffix in {'jsonl','sqlite','db','log'}:return '活动记录'
    if suffix in {'json','toml','yaml','yml','ini','plist'}:return '相关设置'
    if suffix in {'zip','dmg','exe','app','pkg'}:return '安装包'
    if suffix in {'py','js','cjs','mjs','ts','tsx','jsx','swift','sh','ps1','c','h','cpp'}:return '相关程序'
    return '相关项目'


def plain_words(text, language='zh'):
    if not isinstance(text,str):return ''
    # Prefer visible descriptions in links and pictures. Do not expose a URL or
    # storage location just because it appears in an assistant's public note.
    # Clipped diagnostics often contain an opening brace without a closing one.
    # Do not require balanced JSON to keep a terminal dump out of the story.
    text=re.sub(r'(?:\{|\[)\s*["\'][\w.-]+["\']\s*[:=].*?(?=[。！？\n]|$)', '', text)
    text=re.sub(r'\b(?:link|dir|isfile|isdir|exists)\s+(?:True|False|true|false)\b.*?(?=[。！？\n]|$)', '', text)
    text=re.sub(r'```.*?(?:```|$)','相关修改',text,flags=re.S)
    text=re.sub(r'!?\[([^\]\n]*)\]\([^\n)]*\)',lambda m:m[1] or '相关资料',text)
    # A slash between explicit UI labels is a separator, not a storage path.
    # Only preserve readable, quoted labels attached to a UI noun. Real paths
    # (including quoted paths) still go through the normal removal below.
    def ui_label(match):
        label=match[1]
        if re.fullmatch(r'[\u4e00-\u9fff A-Za-z]{1,24}/[\u4e00-\u9fff A-Za-z]{1,24}',label):
            return '“'+label.replace('/','、')+'”'+match[2]
        return match[0]
    text=re.sub(r'“([^”\n]{1,60})”(按钮|入口|选项|功能|页面)',ui_label,text)
    def inline(match):
        value=match[1]
        readable=re.fullmatch(r'[\u4e00-\u9fff A-Za-z]{1,35}',value)
        return value if readable and (re.search(r'[\u4e00-\u9fff]',value) or value in {'Yukio','Codex','Claude','Mac','Windows','GitHub','App'}) else object_name(value)
    text=re.sub(r'`([^`\n]+)`',inline,text)
    text=re.sub(r'https?://[^\s，。；：“”‘’（）<>]+','相关页面',text)
    text=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b','连接位置',text)
    text=re.sub(r'(?:~|[A-Za-z]:)?[/\\][^\s，。；：“”‘’（）()<>\"`]+',lambda m:object_name(m[0]),text)
    text=re.sub(r'(?<![\w.])[\w.-]+\.(?:png|jpe?g|webp|gif|svg|heic|ico|mov|mp4|webm|html?|css|md|pdf|docx|txt|xlsx|csv|jsonl|sqlite|db|log|json|toml|ya?ml|ini|plist|zip|dmg|exe|app|pkg|py|c?js|mjs|tsx?|jsx|swift|sh|ps1|cpp|[ch])(?![\w.])',lambda m:object_name(m[0]),text,flags=re.I)
    text=re.sub(r'(?:图片|图像)(?:编号|ID|id)[：: ]*[A-Za-z0-9_-]+','这张图片',text)
    text=re.sub(r'\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\b[0-9a-f]{16,}\b','相关记录',text,flags=re.I)
    text=re.sub(r'\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b','相关处理',text)
    # "let the app find videos" and "return to the page" are ordinary English,
    # not variable declarations or return statements.
    text=re.sub(r'\b(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=(?!=)[^。；\n]+','相关处理',text)
    text=re.sub(r'(?m)^\s*(?:from [\w.]+ import [\w., *]+|import [\w., ]+|def \w+\([^\n]*):?\s*$','相关处理',text)
    text=re.sub(r'\b[A-Za-z_$][\w.$]*\([^()\n]*\)','相关处理',text)
    text=re.sub(r'\{[^{}\n]*[":=][^{}\n]*\}','相关记录',text)
    text=re.sub(r'(?im)^(?:\$ |>>> |Traceback\b|(?:SELECT|INSERT INTO|UPDATE \w+ SET|CREATE TABLE)\b|(?:git|npm|node|python3?|ssh|rsync|curl|ls|cd|chmod)\s+)[^\n]*','程序记录',text)
    text=re.sub(r'["\'][A-Za-z_][\w.-]*["\']\s*:\s*[^。！？\n]+','程序记录',text)
    text=re.sub(r'\b(?:True|False|None|null|undefined)\b','',text)
    text=re.sub(r'(?<!\w)(?:--?[A-Za-z][\w-]*|[A-Za-z_$][\w.$]*\s*(?:==|!=|=>|:=)\s*[^，。；\n]+)','',text)
    text=re.sub(r'\b[a-z][a-z]+(?:[A-Z][A-Za-z0-9]*)+\b',lambda m:m[0] if m[0] in {'macOS','iOS','iPhone','iPad','iCloud','iMac','webOS'} else '相关处理',text)
    text=re.sub(r'(?:其中一项)?返回退出码\s*\d+[：:;；]?', '检查已返回；',text)
    text=re.sub(r'\s+',' ',text).replace('`','').strip(' ;；:：,，')
    if language=='en':
        for old,new in {'这张图片':'the image','这段视频':'the video','相关页面':'the page','这份资料':'the document','活动记录':'the activity history','相关设置':'the settings','安装包':'the app package','相关程序':'the program','相关项目':'the project','相关修改':'the changes','相关处理':'the operation','相关记录':'the record','程序记录':'program output','连接位置':'the connection destination'}.items():text=text.replace(old,new)
    return text


def readable_fragment(text):
    """Only conversational sentences may become a local story, never diagnostics.

    Keep the original, exact excerpt in the private evidence used for the model.
    This decision does not classify a command as successful or infer its purpose.
    """
    if not isinstance(text,str):return ''
    if re.search(r'[{}]|\b(?:True|False|None|null|Traceback)\b|退出码|exit code|\blink\s+\w+\s+dir\b|(?:==|=>|:=)',text):return ''
    value=plain_words(text)
    if value.count('相关处理')>1:return ''
    return value
