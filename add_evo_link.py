import sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

HTML_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"

with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

# Add "Combo Evolution" link next to "Back to site"
OLD = '&larr; Back to site</a>\n</p>'
NEW = '&larr; Back to site</a>\n  &nbsp;&middot;&nbsp;\n  <a href="/combo_evo.html" style="color:#94a3b8;text-decoration:none;"\n     onmouseover="this.style.textDecoration=\'underline\'"\n     onmouseout="this.style.textDecoration=\'none\'">Combo Evolution &#8594;</a>\n</p>'

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    print("Added Combo Evolution link to backtest.html")
elif 'combo_evo' in html:
    print("Link already present")
else:
    print("ERROR: anchor not found")
    import sys; sys.exit(1)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)
print("Done")
