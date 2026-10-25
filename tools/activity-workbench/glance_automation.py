"""Optional, explicit per-chat consent; no background scheduler or saved grants."""
import hashlib
import secrets
import threading
import time
from explanation import ExplanationError,encode


class GlanceAutomation:
    def __init__(self,glance,explainer,clock=time.monotonic,page_allowed=lambda:False):
        self.glance=glance;self.explainer=explainer;self.clock=clock;self.lock=threading.Lock();self.grants={};self.page_allowed=page_allowed

    def authorize(self,token,consent,page_owned=False):
        if consent is not True:raise ExplanationError('consent_required')
        if type(page_owned) is not bool:raise ValueError('Invalid page mode')
        if page_owned and not self.page_allowed():raise ExplanationError('consent_required')
        with self.explainer.lock:
            entry=self.explainer.entries.get(token)
            if not entry or self.explainer.clock()-entry['created']>300:raise ExplanationError('preview_expired')
            if not entry['payload'].get('scope',{}).get('glance'):raise ExplanationError('consent_required')
            selection=entry['selection']
            if set(selection)!={'client','key'}:raise ExplanationError('consent_required')
            fingerprint=hashlib.sha256(encode(entry['payload']).encode()).hexdigest()
        with self.lock:
            now=self.clock();self.grants={k:v for k,v in self.grants.items() if v['expires']>now and v.get('lease_until',float('inf'))>now}
            if len(self.grants)>=8:raise ExplanationError('busy')
            grant=secrets.token_urlsafe(32)
            self.grants[grant]=dict(selection=dict(selection),expires=now+7200,checked=now,fingerprint=fingerprint,busy=False,page_owned=page_owned)
            if page_owned:self.grants[grant]['lease_until']=now+120
        return dict(grant=grant,interval_seconds=180,expires_in_seconds=7200)

    def heartbeat(self,grant):
        with self.lock:
            now=self.clock();entry=self.grants.get(grant)
            if (not entry or not entry.get('page_owned') or not self.page_allowed()
                    or entry['expires']<=now or entry['lease_until']<=now):
                self.grants.pop(grant,None);raise ExplanationError('preview_expired')
            # Only a live page renews this grant. There is no model scheduler
            # in the service. A lost close notification expires after 2 min.
            entry['lease_until']=now+120;entry['expires']=now+7200
        return dict(alive=True)

    def revoke(self,grant):
        with self.lock:self.grants.pop(grant,None)
        return dict(stopped=True)

    def selection(self,grant):
        """Reuse the live page's exact chat scope for requested reading views."""
        with self.lock:
            entry=self.grants.get(grant);now=self.clock()
            if (not entry or not entry.get('page_owned') or not self.page_allowed()
                    or entry['expires']<=now or entry['lease_until']<=now):
                raise ExplanationError('preview_expired')
            return dict(entry['selection'])

    def refresh(self,grant,force=False):
        if type(force) is not bool:raise ValueError('Invalid refresh')
        with self.lock:
            entry=self.grants.get(grant);now=self.clock()
            if (not entry or entry['expires']<=now or entry.get('lease_until',float('inf'))<=now
                    or entry.get('page_owned') and not self.page_allowed()):
                self.grants.pop(grant,None);raise ExplanationError('preview_expired')
            if entry['busy']:raise ExplanationError('busy')
            if not force and now-entry['checked']<180:return dict(mode='waiting',next_seconds=int(180-now+entry['checked'])+1)
            entry['busy']=True;entry['checked']=now;selection=dict(entry['selection'])
        try:
            data,payload,refs=self.glance.prepared(**selection)
            fingerprint=hashlib.sha256(encode(payload).encode()).hexdigest()
            with self.lock:
                if self.grants.get(grant) is not entry:raise ExplanationError('consent_required')
                if not force and fingerprint==entry['fingerprint']:return dict(mode='unchanged')
            preview=self.explainer.preview_prepared(selection,payload,refs)
            with self.lock:
                if self.grants.get(grant) is not entry:raise ExplanationError('consent_required')
            result=self.explainer.generate(preview['token'],True)
            with self.lock:entry['fingerprint']=fingerprint if result.get('mode')=='model' else None
            return dict(mode='updated',result=result,references=refs,snapshot=data['snapshot'],revision=data['revision'])
        finally:
            with self.lock:entry['busy']=False
