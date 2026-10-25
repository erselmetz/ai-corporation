"""Shared projected-3D Brain widget. Every point/group derives from real input IDs."""
import hashlib
import math
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QRadialGradient, QPen
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QListWidget, QStackedWidget, QSpinBox, QFrame)
from .theme import TOKENS


def vector(identifier):
    digest=hashlib.sha256(identifier.encode()).digest()
    values=[int.from_bytes(digest[i:i+4],'big')/2147483648-1 for i in (0,4,8)]
    length=math.sqrt(sum(v*v for v in values)) or 1
    return tuple(v/length for v in values)


class BrainScene(QWidget):
    picked=Signal(object,object)

    def __init__(self, reduced_motion=lambda:False):
        super().__init__()
        self.setAccessibleName('Brain source and chunk visualization')
        self.setAccessibleDescription('Positions group real chunks by source. Distance is a layout, not model understanding. Use List for keyboard access.')
        self.nodes=[]; self.edges=[]; self.raw=[]; self.limit=300; self.angle=0; self.locations={}; self.points=[]
        self.highlights=set(); self.glows={}; self.selected=None; self.reduced_motion=reduced_motion
        self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(33)
        self.setMinimumSize(100,100)

    def set_graph(self, graph):
        self.raw=[dict(n) for n in graph.get('nodes',[]) if isinstance(n.get('id'),str)]
        self.edges=list(graph.get('edges',[])); self.regroup()

    def regroup(self):
        by_source={}
        for node in self.raw:
            if node.get('kind')=='chunk': by_source.setdefault(node.get('cluster',node['id']),[]).append(node)
        self.nodes=[]
        # Each displayed group names its actual members; no synthetic chunks or
        # invented links are introduced to fill an empty scene.
        sources=sorted(by_source)
        flat=[node for members in by_source.values() for node in members]
        if len(flat)<=self.limit:
            self.nodes=flat
        elif len(sources)>self.limit:
            width=math.ceil(len(sources)/self.limit)
            for start in range(0,len(sources),width):
                members=[n for key in sources[start:start+width] for n in by_source[key]]
                self.nodes.append({'id':'group:'+members[0]['id'],'kind':'group','members':members,'cluster':members[0]['cluster']})
        else:
            quota=max(1,self.limit//max(1,len(sources)))
            for key in sources:
                members=by_source[key]
                if len(members)<=quota: self.nodes.extend(members)
                else:
                    for node in members[:max(0,quota-1)]: self.nodes.append(node)
                    tail=members[max(0,quota-1):]
                    self.nodes.append({'id':'group:'+tail[0]['id'],'kind':'group','members':tail,'cluster':key})
        self.locations={}
        for node in self.nodes:
            core=node.get('trust')=='shipped knowledge'
            center=vector(str(node.get('cluster',node['id'])))
            offset=vector(node['id'])
            radius=.22 if core else .67
            self.locations[node['id']]=tuple(radius*a+.15*b for a,b in zip(center,offset))
        self.update()

    def tick(self):
        if self.isVisible() and self.nodes and not self.reduced_motion() and self.selected is None:
            self.angle+=.004; self.update()

    def glow(self, color, bright):
        dpr=self.devicePixelRatioF(); key=(color.name(),bright,dpr)
        if key not in self.glows:
            pixmap=QPixmap(round(40*dpr),round(40*dpr)); pixmap.setDevicePixelRatio(dpr); pixmap.fill(Qt.GlobalColor.transparent)
            painter=QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            gradient=QRadialGradient(QPointF(20,20),18)
            center=QColor(color); center.setAlpha(255 if bright else 190)
            edge=QColor(color); edge.setAlpha(0)
            gradient.setColorAt(0,center); gradient.setColorAt(.2,center); gradient.setColorAt(1,edge)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(gradient); painter.drawEllipse(QPointF(20,20),18,18); painter.end()
            self.glows[key]=pixmap
        return self.glows[key]

    def paintEvent(self, event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor(TOKENS.background))
        if not self.nodes:
            painter.setPen(QColor(TOKENS.muted)); painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'No chunks yet'); return
        scale=min(self.width(),self.height())*.53; cx=self.width()/2; cy=self.height()/2
        projected={}
        for node in self.nodes:
            x,y,z=self.locations[node['id']]; x,z=x*math.cos(self.angle)+z*math.sin(self.angle),z*math.cos(self.angle)-x*math.sin(self.angle)
            projected[node['id']]=(QPointF(cx+x*scale,cy+y*scale),z)
        # Only actual source-membership links can light up. Grouped markers
        # aggregate existing members rather than claiming extra relationships.
        source_links={}
        for edge in self.edges:
            if edge.get('kind')=='same-source':
                source_links.setdefault(edge.get('from'),set()).add(edge.get('to'))
        clusters={}
        for node in self.nodes: clusters.setdefault(node.get('cluster'),[]).append(node)
        for cluster, members in clusters.items():
            if len(members)<2: continue
            source_ids=source_links.get('source:'+str(cluster),set())
            # Draw the real shared-source relationship via a source hub, not an
            # invented similarity edge between chunks.
            actual=[n for n in members if any(m['id'] in source_ids for m in n.get('members',[n]))]
            if len(actual)<2: continue
            hub=vector(str(cluster));hub_radius=.22 if actual[0].get('trust')=='shipped knowledge' else .67
            hub_point=QPointF(cx+(hub[0]*math.cos(self.angle)+hub[2]*math.sin(self.angle))*hub_radius*scale,cy+hub[1]*hub_radius*scale)
            for node in actual:
                hot=any(m['id'] in self.highlights for m in node.get('members',[node]))
                painter.setPen(QPen(QColor('#edb94e' if hot else '#504229'),1.5 if hot else .6))
                painter.drawLine(hub_point,projected[node['id']][0])
        self.points=[]
        for node in sorted(self.nodes,key=lambda n:projected[n['id']][1]):
            point,z=projected[node['id']]
            digest=hashlib.sha256(str(node.get('cluster',node['id'])).encode()).digest()
            color=QColor.fromHsvF(int.from_bytes(digest[:2],'big')/65536,.45+digest[2]/1024,.8+digest[3]/1280)
            hot=any(m['id'] in self.highlights for m in node.get('members',[node]))
            radius=(9 if node.get('kind')=='group' else 5)*(1+z*.2)
            pixmap=self.glow(color,hot)
            painter.drawPixmap(QRectF(point.x()-radius*2,point.y()-radius*2,radius*4,radius*4),pixmap,QRectF(pixmap.rect()))
            if node.get('kind')=='group':
                painter.setPen(QColor(TOKENS.text)); painter.drawEllipse(point,radius,radius)
            self.points.append((point,radius,node))

    def mousePressEvent(self, event):
        pos=event.position()
        for point,radius,node in reversed(self.points):
            if (pos-point).manhattanLength()<=max(14,radius*2):
                self.selected=node['id']; self.picked.emit(node,point); return
        self.selected=None; self.picked.emit(None,pos)


class BrainPanel(QWidget):
    inspect_requested=Signal(str)
    forget_requested=Signal(object)
    full_requested=Signal()
    refresh_requested=Signal()
    search_requested=Signal(str)

    def __init__(self, reduced_motion=lambda:False):
        super().__init__()
        self.graph={'nodes':[],'edges':[]}; self.selected=None; self.anchor=QPointF(10,10)
        self.search_hits=None
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        tools=QHBoxLayout(); layout.addLayout(tools)
        self.full=QPushButton('Open Brain'); self.full.setAccessibleName('Open full-window Brain'); self.full.clicked.connect(self.full_requested)
        tools.addWidget(self.full)
        self.fallback=QPushButton('List'); self.fallback.setAccessibleName('Brain list fallback'); self.fallback.clicked.connect(self.toggle_list); tools.addWidget(self.fallback)
        self.cap=QSpinBox(); self.cap.setRange(50,2000); self.cap.setValue(300); self.cap.setSingleStep(50); self.cap.setPrefix('Dots: '); self.cap.setMaximumWidth(135); self.cap.setAccessibleName('Maximum visible Brain nodes'); self.cap.setToolTip('More nodes can reduce rendering speed. Groups retain their real members.')
        refresh=QPushButton('↻'); refresh.setAccessibleName('Refresh Brain'); refresh.clicked.connect(self.refresh_requested); tools.addWidget(refresh)
        tools.addStretch()
        from PySide6.QtWidgets import QLineEdit
        self.search=QLineEdit(); self.search.setAccessibleName('Search your Brain'); self.search.setPlaceholderText('Find in your Brain…'); self.search.setMaxLength(2000)
        self.search.returnPressed.connect(lambda:self.search_requested.emit(self.search.text().strip()) if self.search.text().strip() else None)
        search_row=QHBoxLayout(); search_row.addWidget(self.search,1); search_row.addWidget(self.cap); layout.addLayout(search_row)
        self.coverage=QLabel('Loading your Brain…'); self.coverage.setWordWrap(True); self.coverage.setTextFormat(Qt.TextFormat.PlainText); self.coverage.setAccessibleName('Brain coverage and search result count'); layout.addWidget(self.coverage)
        self.stack=QStackedWidget(); layout.addWidget(self.stack,1)
        self.scene=BrainScene(reduced_motion); self.stack.addWidget(self.scene)
        self.list=QListWidget(); self.list.setAccessibleName('Retained Brain chunks'); self.stack.addWidget(self.list)
        self.scene.picked.connect(self.picked); self.list.itemActivated.connect(lambda item:self.picked(item.data(Qt.ItemDataRole.UserRole),QPointF(20,60)))
        self.cap.valueChanged.connect(self.set_cap)
        self.card=QFrame(self); self.card.setObjectName('panel'); self.card.setStyleSheet('QFrame#panel { border: 1px solid #edb94e; border-radius: 8px; }')
        card=QVBoxLayout(self.card); self.title=QLabel(); self.title.setWordWrap(True); self.title.setTextFormat(Qt.TextFormat.PlainText); card.addWidget(self.title)
        self.snippet=QPlainTextEdit(); self.snippet.setReadOnly(True); self.snippet.setAccessibleName('Selected chunk reference'); self.snippet.setMaximumHeight(130); card.addWidget(self.snippet)
        row=QHBoxLayout(); card.addLayout(row)
        self.forget=QPushButton('Forget note'); self.forget.setAccessibleName('Forget selected note'); self.forget.clicked.connect(self.confirm_forget); row.addWidget(self.forget)
        close=QPushButton('Close'); close.setAccessibleName('Close Brain node card'); close.clicked.connect(self.close_card); row.addWidget(close)
        self.card.hide(); self.pending_forget=False
        self.search.textChanged.connect(self.clear_search)

    def clear_search(self):
        self.search_hits=None; self.scene.highlights.clear(); self.scene.update(); self.fill_list(); self.update_coverage()

    def set_cap(self,value):
        self.scene.limit=value; self.scene.regroup(); self.close_card(); self.update_coverage()

    def update_coverage(self):
        loaded=sum(n.get('kind')=='chunk' for n in self.graph.get('nodes',[]))
        total=self.graph.get('total_chunks',loaded)
        core=self.graph.get('core_chunks',0)
        self.coverage.setText(f'{loaded}/{total} chunks loaded · {len(self.scene.nodes)} markers'+(f' · {core} shipped core' if core else ''))

    def set_graph(self,graph):
        self.graph=graph; self.scene.set_graph(graph); self.close_card(); self.search_hits=None; self.fill_list(); self.update_coverage()

    def fill_list(self):
        self.list.clear()
        from PySide6.QtWidgets import QListWidgetItem
        nodes=self.graph.get('nodes',[]) if self.search_hits is None else self.search_hits
        for node in nodes:
            if node.get('kind')!='chunk': continue
            item=QListWidgetItem(str(node.get('source','Note'))+' · '+str(node.get('snippet',''))[:80]); item.setData(Qt.ItemDataRole.UserRole,node); self.list.addItem(item)

    def show_hits(self,hits):
        self.search_hits=[dict(hit,kind='chunk',snippet=hit['text']) for hit in hits]
        self.fill_list(); self.coverage.setText(f'{len(hits)} matches · use List to inspect')

    def toggle_list(self):
        self.stack.setCurrentIndex(1-self.stack.currentIndex()); self.fallback.setText('3D view' if self.stack.currentIndex() else 'List'); self.close_card()

    def picked(self,node,point):
        if node is None: self.close_card(); return
        self.selected=node; self.anchor=point; self.pending_forget=False; self.forget.setText('Forget note')
        self.card.setFixedWidth(max(160,min(330,self.width()-16)))
        self.snippet.setMaximumHeight(min(130,max(50,self.height()-140)))
        self.card.move(max(4,min(round(point.x()+18),self.width()-self.card.width()-4)),max(45,min(round(point.y()),self.height()-235)))
        if node.get('kind')=='group':
            self.title.setText(f"{len(node['members'])} real chunks grouped here")
            self.snippet.setPlainText('Switch to List to inspect each retained chunk.'); self.forget.hide()
        else:
            self.title.setText('Loading selected chunk…'); self.snippet.clear(); self.forget.hide(); self.inspect_requested.emit(node['id'])
        self.card.adjustSize(); self.card.show(); self.card.raise_()

    def show_detail(self,detail):
        if not self.selected or self.selected['id']!=detail['id']: return
        self.selected=detail
        source=str(detail['source']).replace('\\','/').split('/')[-1]
        caption=str(detail['date']) if detail.get('read_only') else 'Saved '+str(detail['date'])[:10]+' · reference material'
        self.title.setText(source+'\n'+caption)
        self.title.setToolTip(str(detail['source']))
        self.snippet.setPlainText(detail['snippet']); self.forget.setVisible(not detail.get('read_only',False)); self.card.adjustSize()

    def confirm_forget(self):
        if not self.selected or self.selected.get('read_only'):return
        if not self.pending_forget:
            self.pending_forget=True; self.forget.setText('Confirm forget'); self.title.setText('Forget this note and its derived index? This removes all chunks of this note. Close to cancel.'); self.card.adjustSize()
        else:
            selected=self.selected; self.close_card(); self.forget_requested.emit(selected)

    def close_card(self):
        self.card.hide(); self.selected=None; self.scene.selected=None; self.pending_forget=False

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            if self.property('fullWindow'): self.full_requested.emit()
            else: self.close_card()
            event.accept()
        else: super().keyPressEvent(event)
