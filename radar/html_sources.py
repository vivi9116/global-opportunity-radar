"""Read server-rendered public HTML; no browser, login or challenge solving."""
from html.parser import HTMLParser
import re
from urllib.parse import urljoin
from .analysis import clean

VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
class Node:
    def __init__(self,tag='',attrs=None,parent=None):self.tag=tag;self.attrs=dict(attrs or []);self.parent=parent;self.children=[]
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child,Node):yield from child.walk()
    def text(self):
        if self.tag in {'script','style','noscript'}:return ''
        return clean(' '.join(child.text() if isinstance(child,Node) else child for child in self.children))
    def has_class(self,name):return name in self.attrs.get('class','').split()
    def first(self,predicate):return next((node for node in self.walk() if predicate(node)),None)

class Document(HTMLParser):
    def __init__(self,raw):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(raw)
    def handle_starttag(self,tag,attrs):
        node=Node(tag,attrs,self.stack[-1]);self.stack[-1].children.append(node)
        if tag not in VOID:self.stack.append(node)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):self.stack[-1].children.append(data)

def warrior(raw):
    doc=Document(raw);items=[]
    for article in (node for node in doc.root.walk() if node.tag=='article' and node.has_class('ArticleSnapshot')):
        heading=article.first(lambda n:n.has_class('ArticleSnapshot-title'))
        link=heading.first(lambda n:n.tag=='a' and n.attrs.get('href')) if heading else None
        body=article.first(lambda n:n.attrs.get('itemprop')=='description')
        date=article.first(lambda n:n.tag=='time' and n.attrs.get('datetime'))
        if not link:continue
        from .parsers import timestamp
        items.append({'title':heading.text(),'body':body.text() if body else '', 'url':link.attrs['href'].split('?')[0],'published_at':timestamp(date.attrs['datetime']) if date else None,'body_scope':'公开列表摘要；未把摘要当作整楼正文'})
    if not items:raise ValueError('公开讨论页中未找到ArticleSnapshot主题，页面结构可能改变。')
    return items[:30]

def trustmrr(raw):
    doc=Document(raw);items=[];seen=set()
    for table in (node for node in doc.root.walk() if node.tag=='table'):
        rows=[n for n in table.walk() if n.tag=='tr'];headers=[]
        for row in rows:
            heads=[n.text() for n in row.walk() if n.tag=='th']
            if heads:headers=heads;continue
            cells=[n for n in row.walk() if n.tag=='td']
            if not cells or not headers or 'MRR' not in headers:continue
            link=row.first(lambda n:n.tag=='a' and n.attrs.get('href','').startswith('/startup/'))
            if not link:continue
            url=urljoin('https://trustmrr.com',link.attrs['href'])
            if url in seen:continue
            seen.add(url);fields=dict(zip(headers,[n.text() for n in cells]))
            title_node=cells[1].first(lambda n:n.tag=='a' and n.attrs.get('href','').startswith('/startup/')) if len(cells)>1 else None
            title=title_node.text() if title_node else fields.get('Startup') or url.rsplit('/',1)[-1]
            metrics=[{'label':k,'value':v,'nature':'平台公开显示的订阅/营收指标；不是净利润或本监控台独立到账核验'} for k,v in fields.items() if k in {'MRR','MoM Growth'} and v not in {'_','—','-',''}]
            items.append({'title':title[:200],'body':'；'.join(k+': '+v for k,v in fields.items() if k!='#'),'url':url,'published_at':None,'platform_metrics':metrics,'body_scope':'公开排行榜表格；数据定义与核验方式以平台说明为准'})
    if not items:raise ValueError('公开排行榜中没有可读取的MRR行，未把营销文字补成数字。')
    def mrr(item):
        value=next((m['value'] for m in item['platform_metrics'] if m['label']=='MRR'),'')
        match=re.search(r'[\d,]+(?:\.\d+)?',value)
        return float(match.group().replace(',','')) if match else float('inf')
    small=[item for item in items if 100<=mrr(item)<=20000]
    return sorted(small or items,key=mrr)[:35]
