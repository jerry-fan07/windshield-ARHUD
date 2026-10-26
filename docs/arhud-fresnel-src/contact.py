"""Contact sheet of PDF pages (out/pages/*.png) via headless Chrome: python3 contact.py first last out.png"""
import os, sys, subprocess, glob
HERE = os.path.dirname(os.path.abspath(__file__))
a, b, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
files = sorted(glob.glob(os.path.join(HERE, "out", "pages", "p-*.png")))
sel = [f for f in files if a <= int(os.path.basename(f)[2:-4]) <= b]
cells = "".join(f'<div><img src="file://{f}"><span>{int(os.path.basename(f)[2:-4])}</span></div>' for f in sel)
html = f"""<!doctype html><html><head><style>body{{margin:0;background:#999;font:14px Helvetica}}
#g{{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;padding:6px;width:1500px}}
div{{position:relative;background:#fff}} img{{width:100%;display:block}} span{{position:absolute;top:2px;left:4px;color:#d00;font-weight:700}}</style></head>
<body><div id="g">{cells}</div></body></html>"""
p = os.path.join(HERE, "out", "contact.html"); open(p, "w").write(html)
js = os.path.join(HERE, "out", "contact.js")
open(js, "w").write("""const p=require('puppeteer-core');(async()=>{const b=await p.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--allow-file-access-from-files']});
const g=await b.newPage();await g.setViewport({width:1512,height:800});await g.goto('file://'+process.argv[2]);const e=await g.$('#g');await e.screenshot({path:process.argv[3]});await b.close();})();""")
subprocess.run(["node", js, p, out], check=True, cwd=HERE)
