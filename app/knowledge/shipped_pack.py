"""Immutable shipped guidance and a separate, rebuildable embedding cache."""
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from threading import Lock
from .native_brain import NativeBrain, normalized


PACK_PATH=Path(__file__).with_name('knowledge_pack.json')


class ShippedPack:
    def __init__(self,embedding=None,cache_root=None):
        data=PACK_PATH.read_bytes()
        if len(data)>65536:raise ValueError('Shipped knowledge pack exceeds its size bound')
        self.digest=sha256(data).hexdigest();self.data=json.loads(data)
        self.entries=self.data['entries']
        if not 1<=len(self.entries)<=100 or len({e['id'] for e in self.entries})!=len(self.entries):raise ValueError('Invalid shipped knowledge entries')
        if any(not isinstance(e['text'],str) or len(e['text'])>2000 for e in self.entries):raise ValueError('Invalid shipped knowledge text')
        self.index=NativeBrain(embedding,prefixed=True)
        # This derived cache never writes to private OwnerKnowledgeStore rows.
        root=Path(cache_root) if cache_root is not None else self.index.cache_path.parent
        self.index.cache_path=root/'shipped-pack-cache'/self.digest/'embeddings.sqlite3'
        self.matrix=None

    def instant(self,text):
        if not isinstance(text,str) or len(text)>128:return None
        key=' '.join(text.casefold().strip().split()).rstrip('!?.,')
        for item in self.data['instant_replies']:
            if key in item['matches']:return item['reply']
        return None

    @property
    def instructions(self):
        return '\n'.join([self.data['persona'],*self.data['rules']])

    def retrieve(self,query,limit=3):
        if not isinstance(query,str) or not 1<=len(query)<=8192 or limit not in (2,3):raise ValueError('Invalid pack retrieval request')
        try:
            with self.index.model_slot(),self.index.lock:
                if self.matrix is None:self.matrix=self.index.vectors([entry['text'] for entry in self.entries])
                query_vector=normalized(self.index.embedding.embed_one(self.index._key(query,query=True)))
                if any(len(v)!=len(query_vector) for v in self.matrix):raise ValueError('Embedding dimensions changed')
                scores=[sum(a*b for a,b in zip(vector,query_vector)) for vector in self.matrix]
            mode='semantic'
        except (ValueError,RuntimeError,OSError,sqlite3.Error):
            terms=set(re.findall(r'\w+',query.casefold()))
            scores=[len(terms & set(re.findall(r'\w+',e['text'].casefold()))) for e in self.entries]
            mode='lexical'
        selected=sorted(zip(scores,self.entries),key=lambda pair:pair[0],reverse=True)[:limit]
        return {'pack_hash':self.digest,'mode':mode,'entries':[dict(entry) for _,entry in selected]}

    def context(self,query,observer=None):
        result=self.retrieve(query)
        if observer is not None:
            observer({'pack_hash':self.digest,'mode':result['mode'],
                      'ids':['core:'+self.digest+':'+e['id'] for e in result['entries']]})
        return '\n'.join('[shipped:'+e['id']+'] '+e['text'] for e in result['entries'])

    def graph(self):
        cluster='core:'+self.digest;source='source:'+cluster
        nodes=[{'id':source,'kind':'source','cluster':cluster,'source':'Shipped Core Knowledge'}]
        for entry in self.entries:
            nodes.append({'id':cluster+':'+entry['id'],'kind':'chunk','cluster':cluster,
                          'source':'Shipped Core Knowledge · '+entry['id'],'snippet':entry['text'],
                          'trust':'shipped knowledge','read_only':True})
        return {'nodes':nodes,'edges':[{'from':source,'to':n['id'],'kind':'same-source'} for n in nodes[1:]],'total_chunks':len(self.entries)}

    def inspect(self,identifier):
        node=next((n for n in self.graph()['nodes'] if n['id']==identifier and n['kind']=='chunk'),None)
        if node is None:raise KeyError('Shipped core entry unavailable')
        return {**node,'date':'Shipped pack v'+str(self.data['version'])}


_pack=None
_pack_lock=Lock()


def shipped_pack():
    global _pack
    with _pack_lock:
        if _pack is None:_pack=ShippedPack()
        return _pack
