"""Export d'un rapport HTML autonome : treemap interactive (zoom, infobulles), sans dépendance."""
from __future__ import annotations

import html
import json
import time
from typing import List, Optional

from .cleanup import SAFETY_LABEL, Finding
from .formatting import human_size
from .models import Node

MAX_CHILDREN = 60
MAX_DEPTH = 7


def trim(node: Node, depth: int = 0) -> list:
    """Arbre compact [nom, taille, mtime, enfants] : les plus gros éléments seulement."""
    kids: List[list] = []
    if node.children and depth < MAX_DEPTH:
        ordered = sorted(node.children, key=lambda k: k.size, reverse=True)
        kids = [trim(k, depth + 1) for k in ordered[:MAX_CHILDREN]]
        rest = ordered[MAX_CHILDREN:]
        if rest:
            kids.append(["(%d autres)" % len(rest), sum(k.size for k in rest), 0, []])
    return [node.name, node.size, round(node.mtime), kids]


def export_html(root: Node, path: str, findings: Optional[List[Finding]] = None,
                used: int = 0, total: int = 0) -> str:
    data = json.dumps(trim(root), separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    rows = ""
    if findings:
        rows = "".join(
            "<tr><td>%s</td><td>%s</td><td class=r>%s</td><td>%s</td></tr>" % (
                html.escape(f.path), html.escape(f.rule.label), human_size(f.size),
                SAFETY_LABEL[f.rule.safety]) for f in findings[:25])
        rows = ("<h2>Gains rapides</h2><table><tr><th>Dossier</th><th>Nature</th><th>Taille</th>"
                "<th>Risque</th></tr>%s</table>" % rows)
    meta = html.escape(path) + " · " + human_size(root.size)
    if total:
        meta += " · disque %s utilisé sur %s" % (human_size(used), human_size(total))
    meta += " · " + time.strftime("%d/%m/%Y %H:%M")
    return (_TEMPLATE.replace("__TITLE__", html.escape(path)).replace("__META__", meta)
            .replace("__ROWS__", rows).replace("__DATA__", data).replace("__BASE__", json.dumps(path)))


_TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DiskMap — __TITLE__</title>
<style>
:root{--bg:#14161a;--bg2:#1c1f26;--fg:#e6e6e6;--dim:#8a8f98;--acc:#3b6fd4}
@media (prefers-color-scheme:light){:root{--bg:#f4f5f7;--bg2:#fff;--fg:#1c1f26;--dim:#5b616b}}
*{box-sizing:border-box}body{margin:0;font:14px system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{padding:12px 16px;background:var(--bg2)}h1{margin:0;font-size:18px}.meta{color:var(--dim);margin-top:4px}
#bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:8px 16px}
#crumbs a{color:#7fb0ff;cursor:pointer}#crumbs span{color:var(--dim);margin:0 4px}
select,button{background:var(--bg2);color:var(--fg);border:1px solid var(--dim);border-radius:4px;padding:3px 8px}
#map{display:block;width:calc(100% - 32px);margin:0 16px;height:70vh;min-height:360px}
#tip{position:fixed;pointer-events:none;background:#000d;color:#fff;padding:4px 8px;border-radius:4px;display:none;font-size:12px;max-width:420px}
main{padding:8px 16px 32px}table{border-collapse:collapse;width:100%;max-width:900px}
td,th{padding:4px 8px;border-bottom:1px solid #8884;text-align:left}.r{text-align:right}
text{font:11px system-ui,sans-serif;fill:#fff;pointer-events:none}
</style></head><body>
<header><h1>DiskMap</h1><div class="meta">__META__</div></header>
<div id="bar"><span id="crumbs"></span><span style="flex:1"></span>
<label>Couleur&nbsp;<select id="mode"><option value="type">Type</option><option value="age">Ancienneté</option></select></label></div>
<svg id="map"></svg><div id="tip"></div>
<main>__ROWS__<p class="meta">Généré par DiskMap 2 — rapport statique, aucun fichier n'a été modifié.</p></main>
<script>
const DATA=__DATA__,BASE=__BASE__;let stack=[DATA],mode="type";
const svg=document.getElementById("map"),tip=document.getElementById("tip"),NS="http://www.w3.org/2000/svg";
const units=["o","Ko","Mo","Go","To"];
function human(b){let i=0;while(b>=1024&&i<4){b/=1024;i++}return(i?b.toFixed(1):b)+" "+units[i]}
function hsl(h,s,l){return"hsl("+h+","+s+"%,"+l+"%)"}
function extColor(n){const i=n.lastIndexOf(".");let h=0;if(i>0)for(const c of n.slice(i+1).toLowerCase())h=(h*31+c.charCodeAt(0))%360;return hsl(h,45,38)}
const HUES=[18,40,60,150,200,225];
function ageColor(m){if(m<=0)return"#3a3a3a";const d=(Date.now()/1000-m)/86400;
 const i=d<30?0:d<180?1:d<365?2:d<730?3:d<1825?4:5;return hsl(HUES[i],55,i<2?42:36)}
function squarify(items,x,y,w,h){items=items.filter(n=>n[1]>0).sort((a,b)=>b[1]-a[1]);const out=[];
 if(w<1||h<1||!items.length)return out;const k=w*h/items.reduce((s,n)=>s+n[1],0);
 let row=[],rx=x,ry=y,rw=w,rh=h,i=0;
 const worst=(r,s)=>{const a=r.map(n=>n[1]*k),t=a.reduce((p,c)=>p+c,0);return Math.max(s*s*Math.max(...a)/(t*t),t*t/(s*s*Math.min(...a)))};
 const place=()=>{const s=row.reduce((p,n)=>p+n[1]*k,0);
  if(rw>=rh){const c=s/rh;let cy=ry;for(const n of row){const hh=n[1]*k/c;out.push([n,rx,cy,c,hh]);cy+=hh}rx+=c;rw-=c}
  else{const c=s/rw;let cx=rx;for(const n of row){const ww=n[1]*k/c;out.push([n,cx,ry,ww,c]);cx+=ww}ry+=c;rh-=c}row=[]};
 while(i<items.length){const side=Math.min(rw,rh);if(side<=0)break;
  if(!row.length||worst(row.concat([items[i]]),side)<=worst(row,side)){row.push(items[i]);i++}else place()}
 if(row.length)place();return out}
function path(){return stack.slice(1).reduce((p,n)=>p+"/"+n[0],BASE.replace(/[\\\/]$/,""))}
function el(t,a){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e}
function draw(){svg.innerHTML="";const W=svg.clientWidth,H=svg.clientHeight;svg.setAttribute("viewBox","0 0 "+W+" "+H);
 const cur=stack[stack.length-1];
 (function rec(node,x,y,w,h,depth,pp,chain){
  for(const[n,rx,ry,rw,rh]of squarify(node[3],x,y,w,h)){if(rw<1.5||rh<1.5)continue;
   const dir=n[3].length>0,p=pp+"/"+n[0];
   const fill=dir?hsl(220,12,Math.min(20+depth*6,60)):(mode==="age"?ageColor(n[2]):extColor(n[0]));
   const r=el("rect",{x:rx,y:ry,width:rw,height:rh,fill:fill,stroke:"#14161a"});
   r.addEventListener("mousemove",e=>{tip.style.display="block";tip.style.left=e.clientX+12+"px";tip.style.top=e.clientY+12+"px";
     tip.textContent=p+" — "+human(n[1])+(n[2]>0?" — modifié le "+new Date(n[2]*1000).toLocaleDateString():"")});
   r.addEventListener("mouseleave",()=>tip.style.display="none");
   if(dir)r.addEventListener("click",()=>{stack=stack.concat(chain,[n]);draw()});
   svg.appendChild(r);
   const lab=n[0]+"  "+human(n[1]);
   if(dir&&depth<2&&rw>40&&rh>34){label(lab,rx,ry,rw);rec(n,rx+2,ry+16,rw-4,rh-18,depth+1,p,chain.concat([n]))}
   else if(rw>46&&rh>16)label(lab,rx,ry,rw)}
 })(cur,0,0,W,H,0,path(),[]);
 const c=document.getElementById("crumbs");c.innerHTML="";
 stack.forEach((n,i)=>{if(i){const s=document.createElement("span");s.textContent="›";c.appendChild(s)}
  const a=document.createElement("a");a.textContent=i?n[0]:BASE;a.onclick=()=>{stack=stack.slice(0,i+1);draw()};c.appendChild(a)});
 c.appendChild(document.createTextNode("  "+human(cur[1])))}
function label(t,x,y,w){const m=Math.floor((w-8)/6.2);if(m<3)return;if(t.length>m)t=t.slice(0,m-1)+"…";
 const e=el("text",{x:x+4,y:y+13});e.textContent=t;svg.appendChild(e)}
document.getElementById("mode").onchange=e=>{mode=e.target.value;draw()};
addEventListener("resize",draw);draw();
</script></body></html>
"""
