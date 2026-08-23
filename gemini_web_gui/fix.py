import re
with open('src/App.tsx', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('await fetch(/api/build', 'await fetch(`${API}/api/build`')
text = text.replace('"1px solid ${C.border}"', '`1px solid ${C.border}`')
with open('src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(text)
